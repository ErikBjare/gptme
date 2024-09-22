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
from itertools import islice
from pathlib import Path
from typing import Literal

import click
from pick import pick
from rich import print  # noqa: F401
from rich.console import Console

from .commands import (
    CMDFIX,
    _gen_help,
    action_descriptions,
    execute_cmd,
)
from .config import get_workspace_prompt
from .constants import MULTIPROMPT_SEPARATOR, PROMPT_USER
from .dirs import get_logs_dir
from .init import init, init_logging
from .llm import reply
from .logmanager import Conversation, LogManager, get_user_conversations
from .message import Message
from .models import get_model
from .prompts import get_prompt
from .tools import ToolUse, execute_msg, has_tool
from .tools.browser import read_url
from .util import epoch_to_age, generate_name, print_bell

logger = logging.getLogger(__name__)
print_builtin = __builtins__["print"]  # type: ignore


script_path = Path(os.path.realpath(__file__))
commands_help = "\n".join(_gen_help(incl_langtags=False))


docstring = f"""
gptme is a chat-CLI for LLMs, empowering them with tools to run shell commands, execute code, read and manipulate files, and more.

If PROMPTS are provided, a new conversation will be started with it.

If one of the PROMPTS is '{MULTIPROMPT_SEPARATOR}', the PROMPTS will form a chain,
where following prompts will be submitted after the assistant is done answering the previous one.

The interface provides user commands that can be used to interact with the system.

\b
{commands_help}"""


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
    "--model",
    default=None,
    help="Model to use, e.g. openai/gpt-4-turbo, anthropic/claude-3-5-sonnet-20240620. If only provider is given, the default model for that provider is used.",
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
    "-r",
    "--resume",
    is_flag=True,
    help="Load last conversation",
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version and configuration information",
)
@click.option(
    "--workspace",
    help="Path to workspace directory. Pass '@log' to create a workspace in the log directory.",
    default=".",
)
def main(
    prompts: list[str],
    prompt_system: str,
    name: str,
    model: str,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    interactive: bool,
    show_hidden: bool,
    version: bool,
    resume: bool,
    workspace: str,
):
    """Main entrypoint for the CLI."""
    if version:
        print_builtin(f"gptme {importlib.metadata.version('gptme-python')}")
        print_builtin(f"Logs dir: {get_logs_dir()}")
        exit(0)

    interactive = False if "PYTEST_CURRENT_TEST" in os.environ else interactive
    no_confirm = True if not interactive else no_confirm

    init_logging(verbose)

    if no_confirm:
        logger.warning("Skipping all confirmation prompts.")

    initial_msgs = [get_prompt(prompt_system, interactive=interactive)]

    if not sys.stdin.isatty():
        prompt_stdin = _read_stdin()
        if prompt_stdin:
            initial_msgs.append(Message("system", f"```stdin\n{prompt_stdin}\n```"))
            sys.stdin.close()
            try:
                sys.stdin = open("/dev/tty")
            except OSError:
                logger.warning(
                    "Failed to switch to interactive mode, continuing in non-interactive mode"
                )

    name = "resume" if resume else name

    sep = "\n\n" + MULTIPROMPT_SEPARATOR
    prompts = [p.strip() for p in "\n\n".join(prompts).split(sep) if p]
    prompt_msgs = [Message("user", p) for p in prompts]

    chat(
        prompt_msgs,
        initial_msgs,
        name,
        model,
        stream,
        no_confirm,
        interactive,
        show_hidden,
        workspace,
    )


def chat(
    prompt_msgs: list[Message],
    initial_msgs: list[Message],
    name: str,
    model: str | None,
    stream: bool = True,
    no_confirm: bool = False,
    interactive: bool = True,
    show_hidden: bool = False,
    workspace: str = ".",
):
    """
    Run the chat loop.

    prompt_msgs: list of messages to execute in sequence.
    initial_msgs: list of history messages.
    workspace: path to workspace directory, or @log to create one in the log directory.

    Callable from other modules.
    """
    init(model, interactive)

    if model and model.startswith("openai/o1") and stream:
        logger.info("Disabled streaming for OpenAI's O1 (not supported)")
        stream = False

    logfile = get_logfile(
        name, interactive=(not prompt_msgs and interactive) and sys.stdin.isatty()
    )
    print(f"Using logdir {logfile.parent}")
    log = LogManager.load(logfile, initial_msgs=initial_msgs, show_hidden=show_hidden)

    workspace_path = (
        logfile.parent / "workspace"
        if (logfile.parent / "workspace").exists() or workspace == "@log"
        else Path(workspace)
    )
    assert workspace_path.exists(), f"Workspace path {workspace_path} does not exist"
    os.chdir(workspace_path)
    print(f"Using workspace at {workspace_path}")

    workspace_prompt = get_workspace_prompt(str(workspace_path))
    if (
        workspace_prompt
        and workspace_prompt not in [m.content for m in log]
        and "user" not in [m.role for m in log]
    ):
        log.append(Message("system", workspace_prompt, hide=True, quiet=True))

    log.print()
    print("--- ^^^ past messages ^^^ ---")

    while True:
        if prompt_msgs:
            while prompt_msgs:
                msg = prompt_msgs.pop(0)
                if not msg.content.startswith("/"):
                    msg = _include_paths(msg)
                log.append(msg)
                if execute_cmd(msg, log):
                    continue

                while True:
                    response_msgs = list(step(log, no_confirm, stream=stream))
                    for response_msg in response_msgs:
                        log.append(response_msg)
                        if response_msg.role == "user" and execute_cmd(
                            response_msg, log
                        ):
                            break

                    last_content = next(
                        (m.content for m in reversed(log) if m.role == "assistant"), ""
                    )
                    if not any(
                        tooluse.is_runnable
                        for tooluse in ToolUse.iter_from_content(last_content)
                    ):
                        break

            continue

        elif not interactive:
            logger.debug("Non-interactive and exhausted prompts, exiting")
            break

        for msg in step(log, no_confirm, stream=stream):  # pragma: no cover
            log.append(msg)
            if msg.role == "user" and execute_cmd(msg, log):
                break


def step(
    log: LogManager,
    no_confirm: bool,
    stream: bool = True,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""

    last_msg = log[-1] if log else None
    if (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == "Interrupted"
        or last_msg.pinned
    ):  # pragma: no cover
        inquiry = prompt_user()
        if not inquiry:
            print()
            return
        msg = Message("user", inquiry, quiet=True)
        msg = _include_paths(msg)
        yield msg

    try:
        msgs = log.prepare_messages()

        for m in msgs:
            logger.debug(f"Prepared message: {m}")

        msg_response = reply(msgs, get_model().model, stream)

        if msg_response:
            yield msg_response.replace(quiet=True)
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

    if name == "random":
        for _ in range(3):
            name = generate_name()
            logpath = logsdir / f"{datestr}-{name}"
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    elif name == "ask":  # pragma: no cover
        while True:
            name = input("Name for conversation (or empty for random words): ")
            name = f"{datestr}-{name}"
            logpath = logsdir / name

            if not logpath.exists():
                break
            else:
                print(f"Name {name} already exists, try again.")
    else:
        try:
            datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            name = f"{datestr}-{name}"
        logpath = logsdir / name
    return logpath


def get_logfile(
    name: str | Literal["random", "resume"], interactive=True, limit=20
) -> Path:
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    LOAD_MORE = "Load more"
    gen_convs = get_user_conversations()
    convs: list[Conversation] = []
    try:
        convs.append(next(gen_convs))
    except StopIteration:
        pass

    if name == "resume":
        if convs:
            return Path(convs[0].path)
        else:
            raise ValueError("No previous conversations to resume")

    convs.extend(islice(gen_convs, limit - 1))

    prev_convs = [
        f"{conv.name:30s} \t{epoch_to_age(conv.modified)} \t{conv.messages:5d} msgs"
        for conv in convs
    ]

    if interactive and name in ["random"]:
        options = [NEW_CONV] + prev_convs + [LOAD_MORE]

        _, index = pick(options, title)  # type: ignore
        if index == 0:
            logdir = get_name(name)
        elif index == len(options) - 1:
            return get_logfile(name, interactive, limit + 100)
        else:
            logdir = get_logs_dir() / convs[index - 1].name
    else:
        logdir = get_name(name)

    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir / "conversation.jsonl"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def prompt_user(value=None) -> str:  # pragma: no cover
    print_bell()
    response = prompt_input(PROMPT_USER, value)
    if response:
        readline.add_history(response)
    return response


def prompt_input(prompt: str, value=None) -> str:  # pragma: no cover
    prompt = prompt.strip() + ": "
    if value:
        print(prompt + value)
    else:
        prompt = _rich_to_str(prompt)

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
    return "".join(iter(lambda: sys.stdin.read(chunk_size), ""))


def _include_paths(msg: Message) -> Message:
    """
    Searches the message for any valid paths and:
     - appends the contents of such files as codeblocks.
     - include images as files.
    """
    assert msg.role == "user"

    cwd_files = [f.name for f in Path.cwd().iterdir()]

    content_no_codeblocks = re.sub(r"```.*?\n```", "", msg.content, flags=re.DOTALL)
    append_msg = ""
    for word in re.split(r"[\s`]", content_no_codeblocks):
        word = word.strip("`").rstrip("?")
        if not word:
            continue
        if (
            any(word.startswith(s) for s in ["/", "~/", "./"])
            or word.startswith("http")
            or any(word.split("/", 1)[0] == file for file in cwd_files)
        ):
            logger.debug(f"potential path/url: {word=}")
            contents = _parse_prompt(word)
            if contents:
                append_msg += "\n\n" + contents

            file = _parse_prompt_files(word)
            if file:
                msg.files.append(file)

    if append_msg:
        msg = msg.replace(content=msg.content + append_msg)

    return msg


def _parse_prompt(prompt: str) -> str | None:
    """
    Takes a string that might be a path,
    and if so, returns the contents of that file wrapped in a codeblock.
    """
    if any(
        prompt.startswith(command)
        for command in [f"{CMDFIX}{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

    try:
        f = Path(prompt).expanduser()
        if f.exists() and f.is_file():
            return f"```{prompt}\n{Path(prompt).expanduser().read_text()}\n```"
    except OSError as oserr:
        if oserr.errno != errno.ENAMETOOLONG:
            pass
        raise
    except UnicodeDecodeError:
        return None

    words = prompt.split()
    paths = [word for word in words if Path(word).expanduser().is_file()]
    urls = [
        word
        for word in words
        if urllib.parse.urlparse(word).scheme and urllib.parse.urlparse(word).netloc
    ]

    result = "\n\n" if paths or urls else ""
    for path in paths:
        result += _parse_prompt(path) or ""

    if not has_tool("browser"):
        logger.warning("Browser tool not available, skipping URL read")
    else:
        for url in urls:
            try:
                content = read_url(url)
                result += f"```{url}\n{content}\n```"
            except Exception as e:
                logger.warning(f"Failed to read URL {url}: {e}")

    return result


def _parse_prompt_files(prompt: str) -> Path | None:
    """
    Takes a string that might be a image path or PDF, to be attached to the message, and returns the path.
    """
    allowed_exts = ["png", "jpg", "jpeg", "gif", "pdf"]

    if any(
        prompt.startswith(command)
        for command in [f"{CMDFIX}{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

    try:
        p = Path(prompt)
        if p.exists() and p.is_file() and p.suffix[1:] in allowed_exts:
            logger.warning("Attaching file to message")
            return p
        else:
            return None
    except OSError as oserr:
        if oserr.errno != errno.ENAMETOOLONG:
            return None
        raise


if __name__ == "__main__":
    main()
