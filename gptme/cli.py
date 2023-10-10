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
import importlib.metadata
import io
import logging
import os
import readline  # noqa: F401
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from time import sleep
from typing import Generator, Literal

import click
from dotenv import load_dotenv
from pick import pick
from rich import print  # noqa: F401
from rich.console import Console

from .constants import HISTORY_FILE, LOGSDIR, PROMPT_USER
from .llm import init_llm, reply
from .logmanager import LogManager
from .message import (
    Message,
    msgs_to_toml,
    print_msg,
    toml_to_msgs,
)
from .prompts import initial_prompt_single_message
from .tools import execute_msg, execute_python, execute_shell
from .tools.shell import get_shell
from .tools.summarize import summarize
from .tools.useredit import edit_text_with_editor
from .util import epoch_to_age, generate_unique_name

logger = logging.getLogger(__name__)
print_builtin = __builtins__["print"]  # type: ignore

LLMChoice = Literal["openai", "llama"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt4"]

CMDFIX = "/"  # prefix for commands, e.g. /help

Actions = Literal[
    "continue",
    "summarize",
    "log",
    "edit",
    "summarize",
    "context",
    "load",
    "shell",
    "python",
    "replay",
    "undo",
    "impersonate",
    "help",
    "exit",
]

action_descriptions: dict[Actions, str] = {
    "continue": "Continue response",
    "undo": "Undo the last action",
    "log": "Show the conversation log",
    "edit": "Edit previous messages",
    "summarize": "Summarize the conversation so far",
    "load": "Load a file",
    "shell": "Execute a shell command",
    "python": "Execute a Python command",
    "replay": "Re-execute past commands in the conversation (does not store output in log)",
    "impersonate": "Impersonate the assistant",
    "help": "Show this help message",
    "exit": "Exit the program",
}
COMMANDS = list(action_descriptions.keys())


def handle_cmd(
    cmd: str, log: LogManager, no_confirm: bool
) -> Generator[Message, None, None]:
    """Handles a command."""
    cmd = cmd.lstrip(CMDFIX)
    logger.debug(f"Executing command: {cmd}")
    name, *args = cmd.split(" ")
    match name:
        case "bash" | "sh" | "shell":
            yield from execute_shell(" ".join(args), ask=not no_confirm)
        case "python" | "py":
            yield from execute_python(" ".join(args), ask=not no_confirm)
        case "continue":
            # undo '/continue' command
            log.undo(1, quiet=True)
        case "log":
            log.undo(1, quiet=True)
            log.print(show_hidden="--hidden" in args)
        case "summarize":
            msgs = log.prepare_messages()
            msgs = [m for m in msgs if not m.hide]
            summary = summarize(msgs)
            print(f"Summary: {summary}")
        case "edit":
            # edit previous messages

            # first undo the '/edit' command itself
            assert log.log[-1].content == f"{CMDFIX}edit"
            log.undo(1, quiet=True)

            # generate editable toml of all messages
            t = msgs_to_toml(reversed(log.log))  # type: ignore
            res = None
            while not res:
                t = edit_text_with_editor(t, "toml")
                try:
                    res = toml_to_msgs(t)
                except Exception as e:
                    print(f"\nFailed to parse TOML: {e}")
                    try:
                        sleep(1)
                    except KeyboardInterrupt:
                        yield Message("system", "Interrupted")
                        return
            log.log = list(reversed(res))
            log.write()
            # now we need to redraw the log so the user isn't seeing stale messages in their buffer
            # log.print()
            logger.info("Applied edited messages")
        case "context":
            # print context msg
            print(_gen_context_msg())
        case "undo":
            # if int, undo n messages
            n = int(args[0]) if args and args[0].isdigit() else 1
            log.undo(n)
        case "load":
            filename = args[0] if args else input("Filename: ")
            with open(filename) as f:
                contents = f.read()
            yield Message("system", f"# filename: {filename}\n\n{contents}")
        case "exit":
            sys.exit(0)
        case "replay":
            log.undo(1, quiet=True)
            print("Replaying conversation...")
            for msg in log.log:
                if msg.role == "assistant":
                    for msg in execute_msg(msg, ask=True):
                        print_msg(msg, oneline=False)
        case "impersonate":
            content = " ".join(args) if args else input("[impersonate] Assistant: ")
            msg = Message("assistant", content)
            yield msg
            yield from execute_msg(msg, ask=not no_confirm)
        case _:
            if log.log[-1].content != f"{CMDFIX}help":
                print("Unknown command")
            # undo the '/help' command itself
            log.undo(1, quiet=True)

            print("Available commands:")
            for cmd, desc in action_descriptions.items():
                print(f"  {cmd}: {desc}")


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  {CMDFIX}{cmd:10s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


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
    type=click.Choice(["openai", "llama"]),
)
@click.option(
    "--model",
    default="gpt-4",
    help="Model to use (gpt-3.5 not recommended)",
    type=click.Choice(["gpt-4", "gpt-3.5-turbo", "wizardcoder-..."]),
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
    if version:
        # print version and exit
        print_builtin(f"gptme {importlib.metadata.version('gptme-python')}")
        exit(0)

    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    # init
    logger.debug("Started")
    load_dotenv()
    _load_readline_history()
    init_llm(llm)  # set up API_KEY and API_BASE

    if "PYTEST_CURRENT_TEST" in os.environ:
        interactive = False

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

    # check if any prompt is a full path, if so, replace it with the contents of that file
    # TODO: add support for directories
    # TODO: maybe do this for all prompts, not just those passed on cli
    prompts = [
        f"```{p}\n{Path(p).expanduser().read_text()}\n```"
        if Path(p).expanduser().exists() and Path(p).expanduser().is_file()
        else p
        for p in prompts
    ]
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
        # if prompts exhausted and non-interactive, exit
        elif not interactive:
            logger.info("Non-interactive and exhausted prompts, exiting")
            exit(0)

        # ask for input if no prompt, generate reply, and run tools
        for msg in loop(log, no_confirm, model, llm, stream=stream):
            log.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, log):
                break


def execute_cmd(msg, log):
    """Executes any user-command, returns True if command was executed."""
    assert msg.role == "user"

    # if message starts with ., treat as command
    # when command has been run,
    if msg.content[:1] in ["/"]:
        for resp in handle_cmd(msg.content, log, no_confirm=True):
            log.append(resp)
        return True
    return False


def loop(
    log: LogManager,
    no_confirm: bool,
    model: ModelChoice,
    llm: LLMChoice,
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
    if not last_msg or (last_msg.role in ["system", "assistant"]):
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


def _gen_context_msg() -> Message:
    shell = get_shell()
    msgstr = ""

    cmd = "pwd"
    ret, pwd, _ = shell.run_command(cmd)
    assert ret == 0
    msgstr += f"$ {cmd}\n{pwd.strip()}\n"

    cmd = "git status -s"
    ret, git, _ = shell.run_command(cmd)
    if ret == 0 and git:
        msgstr += f"$ {cmd}\n{git}\n"

    return Message("system", msgstr.strip(), hide=True)


# default history if none found
history_examples = [
    "What is love?",
    "Have you heard about an open-source app called ActivityWatch?",
    "Explain 'Attention is All You Need' in the style of Andrej Karpathy.",
    "Explain how public-key cryptography works as if I'm five.",
    "Write a Python script that prints the first 100 prime numbers.",
    "Find all TODOs in the current git project",
]


def _completer(text: str, state: int) -> str | None:
    """
    Tab completion for readline.

    Completes /commands and paths in arguments.

    The completer function is called as function(text, state), for state in 0, 1, 2, …, until it returns a non-string value.
    It should return the next possible completion starting with text.
    """
    return _matches(text)[state]


@lru_cache(maxsize=1)
def _matches(text: str) -> list[str]:
    """Returns a list of matches for text to complete."""

    # if text starts with /, complete with commands or files as absolute paths
    if text.startswith("/"):
        # if no text, list all commands
        all_commands = [f"{CMDFIX}{cmd}" for cmd in COMMANDS if cmd != "help"]
        if not text[1:]:
            return all_commands
        # else, filter commands with text
        else:
            matching_files = [str(p) for p in Path("/").glob(text[1:] + "*")]
            return [
                cmd for cmd in all_commands if cmd.startswith(text)
            ] + matching_files

    # if text starts with ., complete with current dir
    elif text.startswith("."):
        if not text[1:]:
            return [str(Path.cwd())]
        else:
            all_files = [str(p) for p in Path.cwd().glob("*")]
            return [f for f in all_files if f.startswith(text)]

    # if text starts with ../, complete with parent dir
    elif text.startswith(".."):
        if not text[2:]:
            return [str(Path.cwd().parent)]
        else:
            return [str(p) for p in Path.cwd().parent.glob(text[2:] + "*")]

    # else, complete with files in current dir
    else:
        if not text:
            return [str(Path.cwd())]
        else:
            return [str(p) for p in Path.cwd().glob(text + "*")]


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

    # set up tab completion
    print("Setting up tab completion")
    readline.set_completer(_completer)
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    # https://github.com/python/cpython/issues/102130#issuecomment-1439242363
    if "libedit" in readline.__doc__:  # type: ignore
        print("Found libedit readline")
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        print("Found gnu readline")
        readline.parse_and_bind("tab: complete")

    atexit.register(readline.write_history_file, HISTORY_FILE)


def get_logfile(name: str, interactive=True) -> Path:
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    prev_conv_files = sorted(
        list(LOGSDIR.glob("*/*.jsonl")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

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
        option, index = pick(options, title)
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
