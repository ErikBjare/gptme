import errno
import logging
import os
import re
import readline
import sys
import termios
import urllib.parse
from collections.abc import Generator
from pathlib import Path

from .commands import action_descriptions, execute_cmd
from .config import get_workspace_prompt
from .constants import PROMPT_USER
from .init import init
from .interrupt import clear_interruptible, set_interruptible
from .llm import reply
from .logmanager import Log, LogManager, prepare_messages
from .message import Message
from .models import get_model
from .tools import ToolUse, execute_msg, has_tool
from .tools.base import ConfirmFunc
from .tools.browser import read_url
from .util import (
    ask_execute,
    console,
    path_with_tilde,
    print_bell,
    rich_to_str,
)

logger = logging.getLogger(__name__)


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

    console.log(f"Using logdir {path_with_tilde(logdir)}")
    manager = LogManager.load(logdir, initial_msgs=initial_msgs, create=True)

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
    console.log(f"Using workspace at {path_with_tilde(workspace)}")
    os.chdir(workspace)

    workspace_prompt = get_workspace_prompt(str(workspace))
    # check if message is already in log, such as upon resume
    if (
        workspace_prompt
        and workspace_prompt not in [m.content for m in manager.log]
        and "user" not in [m.role for m in manager.log]
    ):
        manager.append(Message("system", workspace_prompt, hide=True, quiet=True))

    # print log
    manager.log.print(show_hidden=show_hidden)
    console.print("--- ^^^ past messages ^^^ ---")

    def confirm_func(msg) -> bool:
        if no_confirm:
            return True
        return ask_execute(msg)

    # main loop
    while True:
        # if prompt_msgs given, process each prompt fully before moving to the next
        if prompt_msgs:
            while prompt_msgs:
                msg = prompt_msgs.pop(0)
                if not msg.content.startswith("/"):
                    msg = _include_paths(msg)
                manager.append(msg)
                # if prompt is a user-command, execute it
                if execute_cmd(msg, manager, confirm_func):
                    continue

                # Generate and execute response for this prompt
                while True:
                    try:
                        set_interruptible()
                        response_msgs = list(step(manager.log, stream, confirm_func))
                    except KeyboardInterrupt:
                        console.log("Interrupted. Stopping current execution.")
                        manager.append(Message("system", "Interrupted"))
                        break
                    finally:
                        clear_interruptible()

                    for response_msg in response_msgs:
                        manager.append(response_msg)
                        # run any user-commands, if msg is from user
                        if response_msg.role == "user" and execute_cmd(
                            response_msg, manager, confirm_func
                        ):
                            break

                    # Check if there are any runnable tools left
                    last_content = next(
                        (
                            m.content
                            for m in reversed(manager.log)
                            if m.role == "assistant"
                        ),
                        "",
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
        for msg in step(manager.log, stream, confirm_func):  # pragma: no cover
            manager.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, manager, confirm_func):
                break


def step(
    log: Log | list[Message],
    stream: bool,
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""
    if isinstance(log, list):
        log = Log(log)

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
        msg = Message("user", inquiry, quiet=True)
        msg = _include_paths(msg)
        yield msg
        log = log.append(msg)

    # generate response and run tools
    try:
        set_interruptible()

        # performs reduction/context trimming, if necessary
        msgs = prepare_messages(log.messages)

        for m in msgs:
            logger.debug(f"Prepared message: {m}")

        # generate response
        msg_response = reply(msgs, get_model().model, stream)

        # log response and run tools
        if msg_response:
            yield msg_response.replace(quiet=True)
            yield from execute_msg(msg_response, confirm)
    except KeyboardInterrupt:
        clear_interruptible()
        yield Message("system", "Interrupted")
    finally:
        clear_interruptible()


def prompt_user(value=None) -> str:  # pragma: no cover
    print_bell()
    # Flush stdin to clear any buffered input before prompting
    termios.tcflush(sys.stdin, termios.TCIFLUSH)
    response = ""
    while not response:
        try:
            set_interruptible()
            response = prompt_input(PROMPT_USER, value)
        except KeyboardInterrupt:
            print("\nInterrupted. Press Ctrl-D to exit.")
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
