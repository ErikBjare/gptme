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
import logging
import os
import readline  # noqa: F401
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal

import click
import openai
from dotenv import load_dotenv
from pick import pick
from rich import print
from rich.console import Console

from .config import get_config
from .constants import role_color
from .logmanager import LogManager, print_log
from .message import Message
from .prompts import initial_prompt
from .tools import (
    execute_codeblock,
    execute_linecmd,
    execute_python,
    execute_shell,
)
from .tools.shell import get_shell
from .util import epoch_to_age, generate_unique_name, msgs2dicts

logger = logging.getLogger(__name__)


LLMChoice = Literal["openai", "llama"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt4"]


def get_logfile(logdir: Path) -> Path:
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir / "conversation.jsonl"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def execute_msg(msg: Message) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    for line in msg.content.splitlines():
        yield from execute_linecmd(line)

    # get all markdown code blocks
    # we support blocks beginning with ```python and ```bash
    codeblocks = [codeblock for codeblock in msg.content.split("```")[1::2]]
    for codeblock in codeblocks:
        yield from execute_codeblock(codeblock)


Actions = Literal[
    "continue",
    "summarize",
    "log",
    "summarize",
    "context",
    "load",
    "shell",
    "python",
    "replay",
    "undo",
    "help",
    "exit",
]

action_descriptions: dict[Actions, str] = {
    "continue": "Continue",
    "undo": "Undo the last action",
    "log": "Show the conversation log",
    "summarize": "Summarize the conversation so far",
    "load": "Load a file",
    "shell": "Execute a shell command",
    "python": "Execute a Python command",
    "exit": "Exit the program",
    "help": "Show this help message",
    "replay": "Rerun all commands in the conversation (does not store output in log)",
}


def handle_cmd(
    cmd: str, logmanager: LogManager, no_confirm: bool
) -> Generator[Message, None, None]:
    """Handles a command."""
    cmd = cmd.lstrip(".")
    name, *args = cmd.split(" ")
    match name:
        case "bash" | "sh" | "shell":
            yield from execute_shell(" ".join(args), ask=not no_confirm)
        case "python" | "py":
            yield from execute_python(" ".join(args), ask=not no_confirm)
        case "continue":
            raise NotImplementedError
        case "log":
            logmanager.print(show_hidden="--hidden" in args)
        case "summarize":
            raise NotImplementedError
        case "context":
            # print context msg
            print(_gen_context_msg())
        case "undo":
            # if int, undo n messages
            n = int(args[0]) if args and args[0].isdigit() else 1
            logmanager.undo(n)
        case "load":
            filename = args[0] if args else input("Filename: ")
            with open(filename) as f:
                contents = f.read()
            yield Message("system", f"# filename: {filename}\n\n{contents}")
        case "exit":
            sys.exit(0)
        case "replay":
            print("Replaying conversation...")
            for msg in logmanager.log:
                if msg.role == "assistant":
                    for msg in execute_msg(msg):
                        print_log(msg, oneline=False)
        case _:
            print("Available commands:")
            for cmd, desc in action_descriptions.items():
                print(f"  {cmd}: {desc}")


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  .{cmd:10s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


@click.command(help=docstring)
@click.argument("prompt", default=None, required=False)
@click.option(
    "--prompt-system",
    default="full",
    help="System prompt. Can be 'full', 'short', or something custom.",
)
@click.option(
    "--name",
    default=None,
    help="Name of conversation. Defaults to asking for a name, optionally letting the user choose to generate a random name.",
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
    "--show-hidden",
    is_flag=True,
    help="Show hidden system messages.",
)
def main(
    prompt: str | None,
    prompt_system: str,
    name: str,
    llm: LLMChoice,
    model: ModelChoice,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    show_hidden: bool,
):
    config = get_config()
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    load_dotenv()
    _load_readline_history()

    if llm == "openai":
        if "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"]
        elif api_key := config["env"]["OPENAI_API_KEY"]:
            pass
        else:
            print("Error: OPENAI_API_KEY not set in env or config, see README.")
            sys.exit(1)
        openai.api_key = api_key
    else:
        openai.api_base = "http://localhost:8000/v1"

    if prompt_system in ["full", "short"]:
        promptmsgs = initial_prompt(short=prompt_system == "short")
    else:
        promptmsgs = [Message("system", prompt_system)]

    LOGDIR = Path("~/.local/share/gptme/logs").expanduser()
    LOGDIR.mkdir(parents=True, exist_ok=True)
    datestr = datetime.now().strftime("%Y-%m-%d")
    logpath = LOGDIR
    if name == "random":
        # check if name exists, if so, generate another one
        while not logpath or logpath.exists():
            if name == "random":
                name = generate_unique_name()
            logpath = LOGDIR / (f"{datestr}-{name}")
    elif name:
        logpath = LOGDIR / (f"{datestr}-{name}")
    else:
        # let user select between starting a new conversation and loading a previous one
        # using the library
        title = "New conversation or load previous? "
        NEW_CONV = "New conversation"
        prev_conv_files = sorted(
            list(LOGDIR.glob("*/*.jsonl")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        NEWLINE = "\n"
        prev_convs = [
            f"{f.parent.name:30s} \t{epoch_to_age(f.stat().st_mtime)} \t{len(f.read_text().split(NEWLINE)):5d} msgs"
            for f in prev_conv_files
        ]

        options = [
            NEW_CONV,
        ] + prev_convs
        option, index = pick(options, title)
        if index == 0:
            # ask for name, or use random name
            name = input("Name for conversation (or empty for random words): ")
            if not name:
                name = generate_unique_name()
            logpath = LOGDIR / f"{datestr}-{name}"
        else:
            logpath = LOGDIR / prev_conv_files[index - 1].parent

    print(f"Using logdir {logpath}")
    logfile = get_logfile(logpath)
    logmanager = LogManager.load(
        logfile, initial_msgs=promptmsgs, show_hidden=show_hidden
    )
    logmanager.print()
    print("--- ^^^ past messages ^^^ ---")

    log = logmanager.log

    # if last message was from assistant, try to run tools again
    if log[-1].role == "assistant":
        for m in execute_msg(log[-1]):
            logmanager.append(m)

    command_triggered = False

    while True:
        # if non-interactive command given on cli, exit
        if command_triggered:
            print("Command triggered, exiting")
            break

        # If last message was a response, ask for input.
        # If last message was from the user (such as from crash/edited log),
        # then skip asking for input and generate response
        last_msg = log[-1] if log else None
        if not last_msg or (
            (last_msg.role in ["system", "assistant"])
            or (log[-1].role == "user" and log[-1].content.startswith("."))
        ):
            inquiry = prompt_user(prompt)
            if prompt:
                command_triggered = True

            if not inquiry:
                # Empty command, ask for input again
                print()
                continue
            logmanager.append(Message("user", inquiry), quiet=True)

        assert log[-1].role == "user"
        inquiry = log[-1].content
        # if message starts with ., treat as command
        # when command has been run,
        if inquiry.startswith(".") or inquiry.startswith("$"):
            for msg in handle_cmd(inquiry, logmanager, no_confirm):
                logmanager.append(msg)
            if prompt:
                command_triggered = True
                print("Continue 2")
            continue

        # if large context, try to reduce/summarize
        # print response
        try:
            # performs reduction/context trimming
            msgs = logmanager.prepare_messages()

            # append temporary message with current context
            msgs += [_gen_context_msg()]

            # generate response
            msg_response = reply(msgs, model, stream)

            # log response and run tools
            if msg_response:
                logmanager.append(msg_response, quiet=True)
                for msg in execute_msg(msg_response):
                    logmanager.append(msg)
        except KeyboardInterrupt:
            print("Interrupted")


def _gen_context_msg() -> Message:
    shell = get_shell()
    msgstr = ""

    _, pwd, _ = shell.run_command("pwd")
    msgstr += f"$ pwd\n{pwd.strip()}\n"

    ret, git, _ = shell.run_command("git status -s")
    if ret == 0:
        msgstr += f"$ git status\n{git}\n"

    return Message("system", msgstr.strip(), hide=True)


CONFIG_PATH = Path("~/.config/gptme").expanduser()
CONFIG_PATH.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = CONFIG_PATH / "history"


def _load_readline_history() -> None:
    try:
        readline.read_history_file(HISTORY_FILE)
    except FileNotFoundError:
        readline.add_history("What is love?")
        readline.add_history(
            "Have you heard about an open-source app called ActivityWatch?"
        )
        readline.add_history(
            "Explain 'Attention is All You Need' in the style of Andrej Karpathy."
        )
        readline.add_history(
            "Explain how public-key cryptography works as if I'm five."
        )


PROMPT_USER = f"[bold {role_color['user']}]User[/bold {role_color['user']}]"
PROMPT_ASSISTANT = f"[bold {role_color['user']}]Assistant[/bold {role_color['user']}]"


def prompt_user(value=None) -> str:
    response = prompt_input(PROMPT_USER, value)
    if response:
        readline.add_history(response)
        readline.write_history_file(HISTORY_FILE)
    return response


def prompt_input(prompt: str, value=None) -> str:
    prompt = prompt.strip() + ": "
    if value:
        print(prompt + value)
    else:
        console = Console()
        value = console.input(prompt)
    return value


def reply(messages: list[Message], model: str, stream: bool = False) -> Message:
    if stream:
        return reply_stream(messages, model)
    else:
        print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
        response = _chat_complete(messages, model)
        print(" " * shutil.get_terminal_size().columns, end="\r")
        return Message("assistant", response)


temperature = 0
top_p = 0.1


def _chat_complete(messages: list[Message], model: str) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    response = openai.ChatCompletion.create(  # type: ignore
        model=model,
        messages=msgs2dicts(messages),
        temperature=temperature,
        top_p=top_p,
    )
    return response.choices[0].message.content


def reply_stream(messages: list[Message], model: str) -> Message:
    print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
    response = openai.ChatCompletion.create(  # type: ignore
        model=model,
        messages=msgs2dicts(messages),
        temperature=temperature,
        top_p=top_p,
        stream=True,
        max_tokens=1000,
    )

    def deltas_to_str(deltas: list[dict]):
        return "".join([d.get("content", "") for d in deltas])

    def print_clear():
        print(" " * shutil.get_terminal_size().columns, end="\r")

    deltas: list[dict] = []
    print_clear()
    print(f"{PROMPT_ASSISTANT}: ", end="")
    stop_reason = None
    try:
        for chunk in response:
            delta = chunk["choices"][0]["delta"]
            deltas.append(delta)
            delta_str = deltas_to_str(deltas)
            stop_reason = chunk["choices"][0]["finish_reason"]
            print(deltas_to_str([delta]), end="")
            # need to flush stdout to get the print to show up
            sys.stdout.flush()
            # pause inference on finished code-block, letting user run the command before continuing
            if "```" in delta_str[-5:] and "```" in delta_str[:-3]:
                # if closing a code block, wait for user to run command
                break
    except KeyboardInterrupt:
        return Message("assistant", deltas_to_str(deltas) + "... ^C Interrupted")
    finally:
        print_clear()
    logger.debug(f"Stop reason: {stop_reason}")
    return Message("assistant", deltas_to_str(deltas))


if __name__ == "__main__":
    main()
