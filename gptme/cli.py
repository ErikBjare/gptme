"""
GPTMe
=====

This is an AI agent called GPTMe, it is designed to be a helpful companion.

It should be able to help the user in various ways, such as:

 - Writing code
 - Using the shell and Python REPL
 - Assisting with technical tasks
 - Writing prose (such as email, code docs, etc.)
 - Acting as an executive assistant

The agent should be able to learn from the user and adapt to their needs.
The agent should always output information using GitHub Flavored Markdown.
THe agent should always output code and commands in markdown code blocks with the appropriate language tag.

Since the agent is long-living, it should be able to remember things that the user has told it,
to do so, it needs to be able to store and query past conversations in a database.
"""
# The above may be used as a prompt for the agent.

import atexit
import errno
import importlib.metadata
import io
import logging
import os
import readline  # noqa: F401
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal

import click
from dotenv import load_dotenv
from pick import pick
from rich import print  # noqa: F401
from rich.console import Console

from .commands import CMDFIX, action_descriptions, execute_cmd
from .constants import HISTORY_FILE, LOGSDIR, PROMPT_USER
from .llm import init_llm, reply
from .logmanager import LogManager, _conversations
from .message import Message
from .prompts import initial_prompt_single_message
from .tabcomplete import register_tabcomplete
from .tools import execute_msg, init_tools
from .util import epoch_to_age, generate_unique_name

logger = logging.getLogger(__name__)
print_builtin = __builtins__["print"]  # type: ignore

LLMChoice = Literal["openai", "local"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt4"]


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  {CMDFIX}{cmd:11s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


def init(verbose: bool, llm: LLMChoice):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    # init
    logger.debug("Started")
    load_dotenv()
    _load_readline_history()
    init_llm(llm)  # set up API_KEY and API_BASE
    init_tools()


@click.command(help=docstring)
@click.argument("prompts", default=None, required=False, nargs=-1)
@click.option(
    "--prompt-system",
    default="full",
    help="System prompt. Can be 'full', 'short', or something custom.",
)
@click.option(
    "--name",
    default="random",
    help="Name of conversation. Defaults to generating a random name. Pass 'ask' to be prompted for a name.",
)
@click.option(
    "--llm",
    default="openai",
    help="LLM to use.",
    type=click.Choice(["openai", "local"]),
)
@click.option(
    "--model",
    default="gpt-4",
    help="Model to use.",
)
@click.option(
    "--stream/--no-stream",
    is_flag=True,
    default=True,
    help="Stream responses",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.option(
    "-y", "--no-confirm", is_flag=True, help="Skips all confirmation prompts."
)
@click.option(
    "--interactive/--non-interactive",
    "-i/-n",
    default=True,
    help="Choose interactive mode, or not. Non-interactive implies --no-confirm, and is used in testing.",
)
@click.option(
    "--show-hidden",
    is_flag=True,
    help="Show hidden system messages.",
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version.",
)
def main(
    prompts: list[str],
    prompt_system: str,
    name: str,
    llm: LLMChoice,
    model: ModelChoice,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    show_hidden: bool,
    interactive: bool,
    version: bool,
):
    """Main entrypoint for the CLI."""

    if version:
        # print version and exit
        print_builtin(f"gptme {importlib.metadata.version('gptme-python')}")
        exit(0)

    init(verbose, llm)

    if "PYTEST_CURRENT_TEST" in os.environ:
        interactive = False
    else:
        # for some reason it bugs out shell tests in CI
        register_tabcomplete()

    if not interactive:
        no_confirm = True

    if no_confirm:
        logger.warning("Skipping all confirmation prompts.")

    if prompt_system in ["full", "short"]:
        promptmsgs = [initial_prompt_single_message(short=prompt_system == "short")]
    else:
        promptmsgs = [Message("system", prompt_system)]

    # we need to run this before checking stdin, since the interactive doesn't work with the switch back to interactive mode
    logfile = get_logfile(
        name, interactive=(not prompts and interactive) and sys.stdin.isatty()
    )
    print(f"Using logdir {logfile.parent}")
    log = LogManager.load(logfile, initial_msgs=promptmsgs, show_hidden=show_hidden)

    # if stdin is not a tty, we're getting piped input
    if not sys.stdin.isatty():
        # fetch prompt from stdin
        prompt_stdin = _read_stdin()
        if prompt_stdin:
            promptmsgs += [Message("system", prompt_stdin)]

            # Attempt to switch to interactive mode
            sys.stdin.close()
            sys.stdin = open("/dev/tty")

    # print log
    log.print()
    print("--- ^^^ past messages ^^^ ---")

    def parse_prompt(prompt: str) -> str:
        try:
            # check if prompt is a path, if so, replace it with the contents of that file
            f = Path(prompt).expanduser()
            if f.exists() and f.is_file():
                return f"```{prompt}\n{Path(prompt).expanduser().read_text()}\n```"
        except OSError as oserr:
            # some prompts are too long to be a path, so we can't read them
            if oserr.errno != errno.ENAMETOOLONG:
                pass
        except UnicodeDecodeError:
            # some files are not text files (images, audio, PDFs, binaries, etc), so we can't read them
            # TODO: but can we handle them better than just printing the path? maybe with metadata from `file`?
            pass

        words = prompt.split()
        if len(words) > 1:
            # check if substring of prompt is a path, if so, append the contents of that file
            paths = []
            for word in words:
                f = Path(word).expanduser()
                if f.exists() and f.is_file():
                    paths.append(word)
            if paths:
                prompt += "\n\n"
                for path in paths:
                    prompt += parse_prompt(path)

        return prompt

    # check if any prompt is a full path, if so, replace it with the contents of that file
    # TODO: add support for directories
    # TODO: maybe do this for all prompts, not just those passed on cli
    prompts = [parse_prompt(p) for p in prompts]
    # join prompts, grouped by `-` if present, since that's the separator for multiple-round prompts
    prompts = [p.strip() for p in "\n\n".join(prompts).split("\n\n-") if p]

    # main loop
    while True:
        # if prompts given on cli, insert next prompt into log
        if prompts:
            prompt = prompts.pop(0)
            msg = Message("user", prompt)
            log.append(msg)
            # if prompt is a user-command, execute it
            if execute_cmd(msg, log):
                continue
        # if:
        #  - prompts exhausted
        #  - non-interactive
        #  - no executable block in last assistant message
        # then exit
        elif not interactive:
            # noreorder
            from .tools import is_supported_codeblock  # fmt: skip

            codeblock = log.get_last_code_block("assistant", history=1, content=False)
            if codeblock and is_supported_codeblock(codeblock):
                # all is fine, let assistant continue
                pass
            else:
                logger.info("Non-interactive and exhausted prompts, exiting")
                exit(0)

        # ask for input if no prompt, generate reply, and run tools
        for msg in loop(log, no_confirm, model, stream=stream):
            log.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, log):
                break


def loop(
    log: LogManager,
    no_confirm: bool,
    model: ModelChoice,
    stream: bool = True,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""

    # if last message was from assistant, try to run tools again
    # FIXME: can't do this here because it will run twice
    # if log[-1].role == "assistant":
    #     yield from execute_msg(log[-1], ask=not no_confirm)

    # If last message was a response, ask for input.
    # If last message was from the user (such as from crash/edited log),
    # then skip asking for input and generate response
    last_msg = log[-1] if log else None
    if (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == "Interrupted"
        or last_msg.pinned
    ):
        inquiry = prompt_user()
        if not inquiry:
            # Empty command, ask for input again
            print()
            return
        yield Message("user", inquiry, quiet=True)

    # print response
    try:
        # performs reduction/context trimming, if necessary
        msgs = log.prepare_messages()

        for m in msgs:
            logger.debug(f"Prepared message: {m}")

        # generate response
        msg_response = reply(msgs, model, stream)

        # log response and run tools
        if msg_response:
            msg_response.quiet = True
            yield msg_response
            yield from execute_msg(msg_response, ask=not no_confirm)
    except KeyboardInterrupt:
        yield Message("system", "Interrupted")


def get_name(name: str) -> Path:
    datestr = datetime.now().strftime("%Y-%m-%d")

    # returns a name for the new conversation
    if name == "random":
        # check if name exists, if so, generate another one
        for _ in range(3):
            name = generate_unique_name()
            logpath = LOGSDIR / f"{datestr}-{name}"
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    elif name == "ask":
        while True:
            # ask for name, or use random name
            name = input("Name for conversation (or empty for random words): ")
            name = f"{datestr}-{name}"
            logpath = LOGSDIR / name

            # check that name is unique/doesn't exist
            if not logpath.exists():
                break
            else:
                print(f"Name {name} already exists, try again.")
    else:
        # if name starts with date, use as is
        try:
            datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            name = f"{datestr}-{name}"
        logpath = LOGSDIR / name
    return logpath


# default history if none found
history_examples = [
    "What is love?",
    "Have you heard about an open-source app called ActivityWatch?",
    "Explain 'Attention is All You Need' in the style of Andrej Karpathy.",
    "Explain how public-key cryptography works as if I'm five.",
    "Write a Python script that prints the first 100 prime numbers.",
    "Find all TODOs in the current git project",
]


def _load_readline_history() -> None:
    logger.debug("Loading history")
    # enabled by default in CPython, make it explicit
    readline.set_auto_history(True)
    # had some bugs where it grew to gigs, which should be fixed, but still good precaution
    readline.set_history_length(100)
    try:
        readline.read_history_file(HISTORY_FILE)
    except FileNotFoundError:
        for line in history_examples:
            readline.add_history(line)

    atexit.register(readline.write_history_file, HISTORY_FILE)


def get_logfile(name: str, interactive=True) -> Path:
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    prev_conv_files = list(reversed(_conversations()))

    # filter out test conversations
    # TODO: save test convos to different folder instead
    prev_conv_files = [f for f in prev_conv_files if "-test-" not in f.parent.name]

    NEWLINE = "\n"
    prev_convs = [
        f"{f.parent.name:30s} \t{epoch_to_age(f.stat().st_mtime)} \t{len(f.read_text().split(NEWLINE)):5d} msgs"
        for f in prev_conv_files
    ]

    # don't run pick in tests/non-interactive mode
    if interactive:
        options = [
            NEW_CONV,
        ] + prev_convs

        index: int
        _, index = pick(options, title)  # type: ignore
        if index == 0:
            logdir = get_name(name)
        else:
            logdir = LOGSDIR / prev_conv_files[index - 1].parent
    else:
        logdir = get_name(name)

    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir / "conversation.jsonl"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def prompt_user(value=None) -> str:
    response = prompt_input(PROMPT_USER, value)
    if response:
        readline.add_history(response)
    return response


def prompt_input(prompt: str, value=None) -> str:
    prompt = prompt.strip() + ": "
    if value:
        print(prompt + value)
    else:
        prompt = _rich_to_str(prompt)

        # https://stackoverflow.com/a/53260487/965332
        original_stdout = sys.stdout
        sys.stdout = sys.__stdout__
        value = input(prompt.strip() + " ")
        sys.stdout = original_stdout
    return value


def _rich_to_str(s: str) -> str:
    console = Console(file=io.StringIO(), color_system="256")
    console.print(s)
    return console.file.getvalue()  # type: ignore


def _read_stdin() -> str:
    chunk_size = 1024  # 1 KB
    all_data = ""

    while True:
        chunk = sys.stdin.read(chunk_size)
        if not chunk:
            break
        all_data += chunk

    return all_data


if __name__ == "__main__":
    main()
