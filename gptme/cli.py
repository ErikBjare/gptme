import importlib.metadata
import logging
import os
import signal
import sys
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Literal

import click
from pick import pick

from .chat import chat
from .commands import _gen_help
from .constants import MULTIPROMPT_SEPARATOR
from .dirs import get_logs_dir
from .init import init_logging
from .interrupt import handle_keyboard_interrupt
from .logmanager import Conversation, get_user_conversations
from .message import Message
from .prompts import get_prompt
from .tools import all_tools, init_tools
from .util import epoch_to_age, generate_name

logger = logging.getLogger(__name__)


script_path = Path(os.path.realpath(__file__))
commands_help = "\n".join(_gen_help(incl_langtags=False))
available_tool_names = ", ".join([tool.name for tool in all_tools if tool.available])


docstring = f"""
gptme is a chat-CLI for LLMs, empowering them with tools to run shell commands, execute code, read and manipulate files, and more.

If PROMPTS are provided, a new conversation will be started with it.
PROMPTS can be chained with the '{MULTIPROMPT_SEPARATOR}' separator.

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
    "-n",
    "--name",
    default="random",
    help="Name of conversation. Defaults to generating a random name.",
)
@click.option(
    "-m",
    "--model",
    default=None,
    help="Model to use, e.g. openai/gpt-4o, anthropic/claude-3-5-sonnet-20240620. If only provider given, a default is used.",
)
@click.option(
    "-w",
    "--workspace",
    default=None,
    help="Path to workspace directory. Pass '@log' to create a workspace in the log directory.",
)
@click.option(
    "-r",
    "--resume",
    is_flag=True,
    help="Load last conversation",
)
@click.option(
    "-y",
    "--no-confirm",
    is_flag=True,
    help="Skips all confirmation prompts.",
)
@click.option(
    "-n",
    "--non-interactive",
    "interactive",
    default=True,
    flag_value=False,
    help="Force non-interactive mode. Implies --no-confirm.",
)
@click.option(
    "--system",
    "prompt_system",
    default="full",
    help="System prompt. Can be 'full', 'short', or something custom.",
)
@click.option(
    "-t",
    "--tools",
    "tool_allowlist",
    default=None,
    multiple=True,
    help=f"Comma-separated list of tools to allow. Available: {available_tool_names}.",
)
@click.option(
    "--no-stream",
    "stream",
    default=True,
    flag_value=False,
    help="Don't stream responses",
)
@click.option(
    "--show-hidden",
    is_flag=True,
    help="Show hidden system messages.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show verbose output.",
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version and configuration information",
)
def main(
    prompts: list[str],
    prompt_system: str,
    name: str,
    model: str | None,
    tool_allowlist: list[str] | None,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    interactive: bool,
    show_hidden: bool,
    version: bool,
    resume: bool,
    workspace: str | None,
):
    """Main entrypoint for the CLI."""
    if version:
        # print version
        print(f"gptme {importlib.metadata.version('gptme')}")

        # print dirs
        print(f"Logs dir: {get_logs_dir()}")

        exit(0)

    if "PYTEST_CURRENT_TEST" in os.environ:
        interactive = False

    # init logging
    init_logging(verbose)

    if not interactive:
        no_confirm = True

    if no_confirm:
        logger.warning("Skipping all confirmation prompts.")

    if tool_allowlist:
        # split comma-separated values
        tool_allowlist = [tool for tools in tool_allowlist for tool in tools.split(",")]

    # early init tools to generate system prompt
    init_tools(tool_allowlist)

    # get initial system prompt
    initial_msgs = [get_prompt(prompt_system, interactive=interactive)]

    # if stdin is not a tty, we might be getting piped input, which we should include in the prompt
    was_piped = False
    if not sys.stdin.isatty():
        # fetch prompt from stdin
        prompt_stdin = _read_stdin()
        if prompt_stdin:
            # TODO: also append if existing convo loaded/resumed
            initial_msgs += [Message("system", f"```stdin\n{prompt_stdin}\n```")]
            was_piped = True

            # Attempt to switch to interactive mode
            sys.stdin.close()
            try:
                sys.stdin = open("/dev/tty")
            except OSError:
                # if we can't open /dev/tty, we're probably in a CI environment, so we should just continue
                logger.warning(
                    "Failed to switch to interactive mode, continuing in non-interactive mode"
                )

    # join prompts, grouped by `-` if present, since that's the separator for "chained"/multiple-round prompts
    sep = "\n\n" + MULTIPROMPT_SEPARATOR
    prompts = [p.strip() for p in "\n\n".join(prompts).split(sep) if p]
    prompt_msgs = [Message("user", p) for p in prompts]

    if resume:
        logdir = get_logdir_resume()
    # don't run pick in tests/non-interactive mode, or if the user specifies a name
    elif (
        interactive
        and name == "random"
        and not prompt_msgs
        and not was_piped
        and sys.stdin.isatty()
    ):
        logdir = pick_log()
    else:
        logdir = get_logdir(name)

    if workspace == "@log":
        workspace_path: Path | None = logdir / "workspace"
        assert workspace_path  # mypy not smart enough to see its not None
        workspace_path.mkdir(parents=True, exist_ok=True)
    else:
        workspace_path = Path(workspace) if workspace else None

    # register a handler for Ctrl-C
    signal.signal(signal.SIGINT, handle_keyboard_interrupt)

    chat(
        prompt_msgs,
        initial_msgs,
        logdir,
        model,
        stream,
        no_confirm,
        interactive,
        show_hidden,
        workspace_path,
        tool_allowlist,
    )


def get_name(name: str) -> str:
    """
    Returns a name for the new conversation.

    If name is "random", generates a random name.
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
            name = f"{datestr}-{name}"
            logpath = logsdir / name
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    else:
        # if name starts with date, use as is
        try:
            datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            name = f"{datestr}-{name}"
    return name


def pick_log(limit=20) -> Path:  # pragma: no cover
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    LOAD_MORE = "Load more"
    gen_convs = get_user_conversations()
    convs: list[Conversation] = []

    # load conversations
    convs.extend(islice(gen_convs, limit))

    # filter out test conversations
    # TODO: save test convos to different folder instead
    # def is_test(name: str) -> bool:
    #     return "-test-" in name or name.startswith("test-")
    # prev_conv_files = [f for f in prev_conv_files if not is_test(f.parent.name)]

    prev_convs = [
        f"{conv.name:30s} \t{epoch_to_age(conv.modified)} \t{conv.messages:5d} msgs"
        for conv in convs
    ]

    options = (
        [
            NEW_CONV,
        ]
        + prev_convs
        + [LOAD_MORE]
    )

    index: int
    _, index = pick(options, title)  # type: ignore
    if index == 0:
        return get_logdir("random")
    elif index == len(options) - 1:
        return pick_log(limit + 100)
    else:
        return get_logdir(convs[index - 1].name)


def get_logdir(logdir: Path | str | Literal["random"]) -> Path:
    if logdir == "random":
        logdir = get_logs_dir() / get_name("random")
    elif isinstance(logdir, str):
        logdir = get_logs_dir() / logdir

    logdir.mkdir(parents=True, exist_ok=True)
    return logdir


def get_logdir_resume() -> Path:
    if conv := next(get_user_conversations(), None):
        return Path(conv.path).parent
    else:
        raise ValueError("No previous conversations to resume")


def _read_stdin() -> str:
    chunk_size = 1024  # 1 KB
    all_data = ""

    while True:
        chunk = sys.stdin.read(chunk_size)
        if not chunk:
            break
        all_data += chunk

    return all_data
