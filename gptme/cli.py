import errno
import importlib.metadata
import logging
import os
import re
import readline  # noqa: F401
import signal
import sys
import time
import urllib.parse
from collections.abc import Generator
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Literal

import click
from pick import pick

from .commands import _gen_help, action_descriptions, execute_cmd
from .config import get_workspace_prompt
from .constants import MULTIPROMPT_SEPARATOR, PROMPT_USER
from .dirs import get_logs_dir
from .init import init, init_logging
from .llm import reply
from .logmanager import Conversation, LogManager, get_user_conversations
from .message import Message
from .models import get_model
from .prompts import get_prompt
from .tools import (
    ToolUse,
    all_tools,
    execute_msg,
    has_tool,
    init_tools,
)
from .tools.browser import read_url
from .util import (
    console,
    epoch_to_age,
    generate_name,
    print_bell,
    rich_to_str,
)

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
        print(f"gptme {importlib.metadata.version('gptme-python')}")

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


# Set up a KeyboardInterrupt handler to handle Ctrl-C during the chat loop
interruptible = False
last_interrupt_time = 0.0


def handle_keyboard_interrupt(signum, frame):  # pragma: no cover
    """
    This handler allows interruption of the assistant or tool execution when in an interruptible state,
    while still providing a safeguard against accidental exits during user input.
    """
    global last_interrupt_time
    current_time = time.time()

    if interruptible:
        raise KeyboardInterrupt

    # if current_time - last_interrupt_time <= timeout:
    #     console.log("Second interrupt received, exiting...")
    #     sys.exit(0)

    last_interrupt_time = current_time
    console.print()
    # console.log(
    #     f"Interrupt received. Press Ctrl-C again within {timeout} seconds to exit."
    # )
    console.log("Interrupted. Press Ctrl-D to exit.")


def set_interruptible():
    global interruptible
    interruptible = True


def clear_interruptible():
    global interruptible
    interruptible = False


# TODO: move to seperate file and make this simply callable with `gptme.chat("prompt")`
def chat(
    prompt_msgs: list[Message],
    initial_msgs: list[Message],
    logdir: Path,
    model: str | None,
    stream: bool = True,
    no_confirm: bool = False,
    interactive: bool = True,
    show_hidden: bool = False,
    workspace: Path | None = None,
    tool_allowlist: list[str] | None = None,
):
    """
    Run the chat loop.

    prompt_msgs: list of messages to execute in sequence.
    initial_msgs: list of history messages.
    workspace: path to workspace directory, or @log to create one in the log directory.

    Callable from other modules.
    """
    # init
    init(model, interactive, tool_allowlist)

    if model and model.startswith("openai/o1") and stream:
        logger.info("Disabled streaming for OpenAI's O1 (not supported)")
        stream = False

    console.log(f"Using logdir {logdir}")
    log = LogManager.load(
        logdir, initial_msgs=initial_msgs, show_hidden=show_hidden, create=True
    )

    # change to workspace directory
    # use if exists, create if @log, or use given path
    log_workspace = logdir / "workspace"
    if log_workspace.exists():
        assert not workspace or (
            workspace == log_workspace
        ), f"Workspace already exists in {log_workspace}, wont override."
        workspace = log_workspace
    else:
        if not workspace:
            workspace = Path.cwd()
        assert workspace.exists(), f"Workspace path {workspace} does not exist"
    console.log(f"Using workspace at {workspace}")
    os.chdir(workspace)

    workspace_prompt = get_workspace_prompt(str(workspace))
    # check if message is already in log, such as upon resume
    if (
        workspace_prompt
        and workspace_prompt not in [m.content for m in log]
        and "user" not in [m.role for m in log]
    ):
        log.append(Message("system", workspace_prompt, hide=True, quiet=True))

    # print log
    log.print()
    console.print("--- ^^^ past messages ^^^ ---")

    # main loop
    while True:
        # if prompt_msgs given, process each prompt fully before moving to the next
        if prompt_msgs:
            while prompt_msgs:
                msg = prompt_msgs.pop(0)
                if not msg.content.startswith("/"):
                    msg = _include_paths(msg)
                log.append(msg)
                # if prompt is a user-command, execute it
                if execute_cmd(msg, log):
                    continue

                # Generate and execute response for this prompt
                while True:
                    set_interruptible()
                    try:
                        response_msgs = list(step(log, no_confirm, stream=stream))
                    except KeyboardInterrupt:
                        console.log("Interrupted. Stopping current execution.")
                        log.append(Message("system", "Interrupted"))
                        break
                    finally:
                        clear_interruptible()

                    for response_msg in response_msgs:
                        log.append(response_msg)
                        # run any user-commands, if msg is from user
                        if response_msg.role == "user" and execute_cmd(
                            response_msg, log
                        ):
                            break

                    # Check if there are any runnable tools left
                    last_content = next(
                        (m.content for m in reversed(log) if m.role == "assistant"), ""
                    )
                    if not any(
                        tooluse.is_runnable
                        for tooluse in ToolUse.iter_from_content(last_content)
                    ):
                        break

            # All prompts processed, continue to next iteration
            continue

        # if:
        #  - prompts exhausted
        #  - non-interactive
        #  - no executable block in last assistant message
        # then exit
        elif not interactive:
            logger.debug("Non-interactive and exhausted prompts, exiting")
            break

        # ask for input if no prompt, generate reply, and run tools
        clear_interruptible()  # Ensure we're not interruptible during user input
        for msg in step(log, no_confirm, stream=stream):  # pragma: no cover
            log.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, log):
                break


def step(
    log: LogManager,
    no_confirm: bool,
    stream: bool = True,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""
    # If last message was a response, ask for input.
    # If last message was from the user (such as from crash/edited log),
    # then skip asking for input and generate response
    last_msg = log[-1] if log else None
    if (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == "Interrupted"
        or last_msg.pinned
        or not any(role == "user" for role in [m.role for m in log])
    ):  # pragma: no cover
        inquiry = prompt_user()
        if not inquiry:
            # Empty command, ask for input again
            return
        msg = Message("user", inquiry, quiet=True)
        msg = _include_paths(msg)
        yield msg

    # generate response and run tools
    set_interruptible()
    try:
        # performs reduction/context trimming, if necessary
        msgs = log.prepare_messages()

        for m in msgs:
            logger.debug(f"Prepared message: {m}")

        # generate response
        msg_response = reply(msgs, get_model().model, stream)

        # log response and run tools
        if msg_response:
            yield msg_response.replace(quiet=True)
            yield from execute_msg(msg_response, ask=not no_confirm)
    except KeyboardInterrupt:
        clear_interruptible()
        yield Message("system", "Interrupted")
    finally:
        clear_interruptible()


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


def prompt_user(value=None) -> str:  # pragma: no cover
    print_bell()
    set_interruptible()
    try:
        response = prompt_input(PROMPT_USER, value)
    except KeyboardInterrupt:
        print("\nInterrupted. Press Ctrl-D to exit.")
        return ""
    clear_interruptible()
    if response:
        readline.add_history(response)
    return response


def prompt_input(prompt: str, value=None) -> str:  # pragma: no cover
    prompt = prompt.strip() + ": "
    if value:
        console.print(prompt + value)
    else:
        prompt = rich_to_str(prompt, color_system="256")

        # https://stackoverflow.com/a/53260487/965332
        original_stdout = sys.stdout
        sys.stdout = sys.__stdout__
        value = input(prompt.strip() + " ")
        sys.stdout = original_stdout
    return value


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
    """
    Searches the message for any valid paths and:
     - appends the contents of such files as codeblocks.
     - include images as files.
    """
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
            contents = _parse_prompt(word)
            if contents:
                # if we found a valid path, replace it with the contents of the file
                append_msg += "\n\n" + contents

            file = _parse_prompt_files(word)
            if file:
                msg.files.append(file)

    # append the message with the file contents
    if append_msg:
        msg = msg.replace(content=msg.content + append_msg)

    return msg


def _parse_prompt(prompt: str) -> str | None:
    """
    Takes a string that might be a path,
    and if so, returns the contents of that file wrapped in a codeblock.
    """
    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(
        prompt.startswith(command)
        for command in [f"/{cmd}" for cmd in action_descriptions.keys()]
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
        raise
    except UnicodeDecodeError:
        # some files are not text files (images, audio, PDFs, binaries, etc), so we can't read them
        # TODO: but can we handle them better than just printing the path? maybe with metadata from `file`?
        # logger.warning(f"Failed to read file {prompt}: not a text file")
        return None

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

    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(
        prompt.startswith(command)
        for command in [f"/{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

    try:
        # check if prompt is a path, if so, replace it with the contents of that file
        p = Path(prompt)
        if p.exists() and p.is_file() and p.suffix[1:] in allowed_exts:
            logger.warning("Attaching file to message")
            return p
        else:
            return None
    except OSError as oserr:  # pragma: no cover
        # some prompts are too long to be a path, so we can't read them
        if oserr.errno != errno.ENAMETOOLONG:
            return None
        raise


if __name__ == "__main__":
    main()
