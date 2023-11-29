import errno
import importlib.metadata
import io
import logging
import os
import re
import readline  # noqa: F401
import sys
import urllib.parse
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Literal

import click
from pick import pick
from rich import print  # noqa: F401
from rich.console import Console

from .commands import CMDFIX, action_descriptions, execute_cmd
from .constants import MULTIPROMPT_SEPARATOR, PROMPT_USER
from .dirs import get_logs_dir
from .init import init, init_logging
from .llm import reply
from .logmanager import LogManager, _conversations
from .message import Message
from .prompts import get_prompt
from .tools import execute_msg
from .tools.shell import ShellSession, set_shell
from .util import epoch_to_age, generate_name

logger = logging.getLogger(__name__)
print_builtin = __builtins__["print"]  # type: ignore

LLMChoice = Literal["openai", "local"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt-4", "gpt-4-1106-preview"]


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  {CMDFIX}{cmd:11s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

If PROMPTS are provided, a new conversation will be started with it.

If one of the PROMPTS is '{MULTIPROMPT_SEPARATOR}', following prompts will run after the assistant is done answering the first one.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


@click.command(help=docstring)
@click.argument(
    "prompts",
    default=None,
    required=False,
    nargs=-1,
)
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
    interactive: bool,
    show_hidden: bool,
    version: bool,
):
    """Main entrypoint for the CLI."""
    if version:
        # print version and exit
        print_builtin(f"gptme {importlib.metadata.version('gptme-python')}")
        exit(0)

    if "PYTEST_CURRENT_TEST" in os.environ:
        interactive = False

    # init logging
    init_logging(verbose)

    if not interactive:
        no_confirm = True

    if no_confirm:
        logger.warning("Skipping all confirmation prompts.")

    # get initial system prompt
    initial_msgs = [get_prompt(prompt_system)]

    # if stdin is not a tty, we're getting piped input, which we should include in the prompt
    if not sys.stdin.isatty():
        # fetch prompt from stdin
        prompt_stdin = _read_stdin()
        if prompt_stdin:
            initial_msgs += [Message("system", f"```stdin\n{prompt_stdin}\n```")]

            # Attempt to switch to interactive mode
            sys.stdin.close()
            try:
                sys.stdin = open("/dev/tty")
            except OSError:
                # if we can't open /dev/tty, we're probably in a CI environment, so we should just continue
                logger.warning(
                    "Failed to switch to interactive mode, continuing in non-interactive mode"
                )

    # join prompts, grouped by `-` if present, since that's the separator for multiple-round prompts
    sep = "\n\n" + MULTIPROMPT_SEPARATOR
    prompts = [p.strip() for p in "\n\n".join(prompts).split(sep) if p]
    prompt_msgs = [Message("user", p) for p in prompts]

    chat(
        prompt_msgs,
        initial_msgs,
        name,
        llm,
        model,
        stream,
        no_confirm,
        interactive,
        show_hidden,
    )


def chat(
    prompt_msgs: list[Message],
    initial_msgs: list[Message],
    name: str,
    llm: str,
    model: str,
    stream: bool = True,
    no_confirm: bool = False,
    interactive: bool = True,
    show_hidden: bool = False,
):
    """
    Run the chat loop.

    Callable from other modules.
    """
    # init
    init(llm, model, interactive)

    # (re)init shell
    set_shell(ShellSession())

    # we need to run this before checking stdin, since the interactive doesn't work with the switch back to interactive mode
    logfile = get_logfile(
        name, interactive=(not prompt_msgs and interactive) and sys.stdin.isatty()
    )
    print(f"Using logdir {logfile.parent}")
    log = LogManager.load(logfile, initial_msgs=initial_msgs, show_hidden=show_hidden)

    # print log
    log.print()
    print("--- ^^^ past messages ^^^ ---")

    # main loop
    while True:
        # if prompt_msgs given, insert next prompt into log
        if prompt_msgs:
            msg = prompt_msgs.pop(0)
            msg = _include_paths(msg)
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
            if not (codeblock and is_supported_codeblock(codeblock)):
                logger.info("Non-interactive and exhausted prompts, exiting")
                exit(0)

        # ask for input if no prompt, generate reply, and run tools
        for msg in loop(log, no_confirm, model, stream=stream):  # pragma: no cover
            log.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, log):
                break


def loop(
    log: LogManager,
    no_confirm: bool,
    model: str,
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
        msg = Message("user", inquiry, quiet=True)
        msg = _include_paths(msg)
        yield msg

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
    """
    Returns a name for the new conversation.

    If name is "random", generates a random name.
    If name is "ask", asks the user for a name.
    If name is starts with a date, uses it as is.
    Otherwise, prepends the current date to the name.
    """
    datestr = datetime.now().strftime("%Y-%m-%d")
    logsdir = get_logs_dir()

    # returns a name for the new conversation
    if name == "random":
        # check if name exists, if so, generate another one
        for _ in range(3):
            name = generate_name()
            logpath = logsdir / f"{datestr}-{name}"
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    elif name == "ask":  # pragma: no cover
        while True:
            # ask for name, or use random name
            name = input("Name for conversation (or empty for random words): ")
            name = f"{datestr}-{name}"
            logpath = logsdir / name

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
        logpath = logsdir / name
    return logpath


def get_logfile(name: str, interactive=True) -> Path:
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    prev_conv_files = list(reversed(_conversations()))

    def is_test(name: str) -> bool:
        return "-test-" in name or name.startswith("test-")

    # filter out test conversations
    # TODO: save test convos to different folder instead
    # prev_conv_files = [f for f in prev_conv_files if not is_test(f.parent.name)]

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
            logdir = get_logs_dir() / prev_conv_files[index - 1].parent
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


def _include_paths(msg: Message) -> Message:
    """Searches the message for any valid paths and appends the contents of such files as codeblocks."""
    # TODO: add support for directories?
    assert msg.role == "user"

    # list the current directory
    cwd_files = [f.name for f in Path.cwd().iterdir()]

    # match absolute, home, relative paths, and URLs anywhere in the message
    # could be wrapped with spaces or backticks, possibly followed by a question mark
    # don't look in codeblocks, and don't match paths that are already in codeblocks
    # TODO: this will misbehave if there are codeblocks (or triple backticks) in codeblocks
    content_no_codeblocks = re.sub(r"```.*?\n```", "", msg.content, flags=re.DOTALL)
    append_msg = ""
    for word in re.split(r"[\s`]", content_no_codeblocks):
        # remove wrapping backticks
        word = word.strip("`")
        # remove trailing question mark
        word = word.rstrip("?")
        if not word:
            continue
        if (
            # if word starts with a path character
            any(word.startswith(s) for s in ["/", "~/", "./"])
            # or word is a URL
            or word.startswith("http")
            # or word is a file in the current dir,
            # or a path that starts in a folder in the current dir
            or any(word.split("/", 1)[0] == file for file in cwd_files)
        ):
            logger.debug(f"potential path/url: {word=}")
            p = _parse_prompt(word)
            if p:
                # if we found a valid path, replace it with the contents of the file
                append_msg += "\n\n" + p

    # append the message with the file contents
    if append_msg:
        msg.content += append_msg

    return msg


def _parse_prompt(prompt: str) -> str | None:
    """
    Takes a string that might be a path,
    and if so, returns the contents of that file wrapped in a codeblock.
    """
    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(
        prompt.startswith(command)
        for command in [f"{CMDFIX}{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

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

    # check if any word in prompt is a path or URL,
    # if so, append the contents as a code block
    words = prompt.split()
    paths = []
    urls = []
    for word in words:
        f = Path(word).expanduser()
        if f.exists() and f.is_file():
            paths.append(word)
            continue
        try:
            p = urllib.parse.urlparse(word)
            if p.scheme and p.netloc:
                urls.append(word)
        except ValueError:
            pass

    result = ""
    if paths or urls:
        result += "\n\n"
        if paths:
            logger.debug(f"{paths=}")
        if urls:
            logger.debug(f"{urls=}")
    for path in paths:
        result += _parse_prompt(path) or ""

    for url in urls:
        try:
            # noreorder
            from .tools.browser import read_url  # fmt: skip
        except ImportError:
            logger.warning(
                "Failed to import browser tool, skipping URL expansion."
                "You might have to install browser extras."
            )
            continue

        try:
            content = read_url(url)
            result += f"```{url}\n{content}\n```"
        except Exception as e:
            logger.warning(f"Failed to read URL {url}: {e}")

    return result


if __name__ == "__main__":
    main()
