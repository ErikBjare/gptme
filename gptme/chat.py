import logging
import os
import sys
import termios
from collections.abc import Generator
from pathlib import Path
from typing import cast

from .commands import execute_cmd
from .config import get_config
from .constants import INTERRUPT_CONTENT, PROMPT_USER
from .init import init
from .llm import reply
from .llm.models import get_model
from .logmanager import Log, LogManager, prepare_messages
from .message import Message
from .prompts import get_workspace_prompt
from .tools import (
    ConfirmFunc,
    ToolFormat,
    ToolUse,
    execute_msg,
    get_tools,
    has_tool,
    set_tool_format,
)
from .tools.tts import (
    audio_queue,
    speak,
    stop,
    tts_request_queue,
)
from .util import console, path_with_tilde, print_bell
from .util.ask_execute import ask_execute
from .util.context import run_precommit_checks, use_fresh_context
from .util.cost import log_costs
from .util.interrupt import Interruptible, clear_interruptible
from .util.paths import (
    find_potential_paths,
    is_url,
    process_url,
    read_text_file,
    resolve_path,
)
from .util.prompt import add_history, get_input
from .util.terminal import set_current_conv_name, terminal_state_title
from scripts.auto_rename_logs import auto_rename_logs
from gptme.util.generate_name import is_generated_name

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
    tool_format: ToolFormat | None = None,
    auto_rename: bool | None = None,
) -> None:
    """
    Run the chat loop.

    prompt_msgs: list of messages to execute in sequence.
    initial_msgs: list of history messages.
    workspace: path to workspace directory.

    Callable from other modules.
    """
    # Get auto_rename from environment if not set
    if auto_rename is None:
        auto_rename = os.environ.get("GPTME_AUTO_RENAME", "").lower() in ["1", "true"]

    # Initialize chat session
    manager, workspace, tool_format_with_default, stream = _init_chat(
        logdir=logdir,
        model=model,
        interactive=interactive,
        tool_allowlist=tool_allowlist,
        initial_msgs=initial_msgs,
        tool_format=tool_format,
        workspace=workspace,
        stream=stream,
        show_hidden=show_hidden,
    )

    def confirm_func(msg) -> bool:
        return True if no_confirm else ask_execute(msg)

    # Process all prompts first
    while prompt_msgs:
        _process_prompt(
            prompt_msgs.pop(0),
            manager,
            workspace,
            stream,
            confirm_func,
            tool_format_with_default,
            model,
            auto_rename=auto_rename,
        )

    # Exit if non-interactive
    if not interactive:
        _handle_non_interactive_exit()
        return

    # Interactive mode: process user input
    while True:
        clear_interruptible()  # Ensure we're not interruptible during user input
        for msg in step(
            manager.log,
            stream,
            confirm_func,
            tool_format=tool_format_with_default,
            workspace=workspace,
            auto_rename=auto_rename,
        ):  # pragma: no cover
            manager.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, manager, confirm_func):
                break


def _handle_non_interactive_exit() -> None:
    """Handle cleanup when exiting non-interactive mode."""
    logger.debug("Non-interactive and exhausted prompts")
    if has_tool("tts") and os.environ.get("GPTME_VOICE_FINISH", "").lower() in [
        "1",
        "true",
    ]:
        logger.info("Waiting for TTS to finish...")

        with Interruptible():
            try:
                # Wait for all TTS processing to complete
                tts_request_queue.join()
                logger.info("tts request queue joined")
                # Then wait for all audio to finish playing
                audio_queue.join()
                logger.info("audio queue joined")
            except KeyboardInterrupt:
                logger.info("Interrupted while waiting for TTS")
                stop()


def _init_chat(
    logdir: Path,
    model: str | None,
    interactive: bool,
    tool_allowlist: list[str] | None,
    initial_msgs: list[Message],
    tool_format: ToolFormat | None,
    workspace: Path | None,
    stream: bool,
    show_hidden: bool,
) -> tuple[LogManager, Path, ToolFormat, bool]:
    """Initialize the chat session."""
    _init_terminal(logdir.name)
    stream = _init_model(model, interactive, tool_allowlist, stream)
    manager = _init_log_manager(logdir, initial_msgs)
    tool_format_with_default = _init_tool_format(tool_format)
    workspace = _init_and_setup_workspace(workspace, logdir, manager)
    _print_log(manager, show_hidden)

    return manager, workspace, tool_format_with_default, stream


def _init_terminal(conv_name: str) -> None:
    """Initialize terminal title with conversation name."""
    set_current_conv_name(conv_name)


def _init_model(
    model: str | None,
    interactive: bool,
    tool_allowlist: list[str] | None,
    stream: bool,
) -> bool:
    """Initialize model and return updated stream setting."""
    init(model, interactive, tool_allowlist)

    modelmeta = get_model(model)
    if not modelmeta.supports_streaming and stream:
        logger.info(
            "Disabled streaming for '%s/%s' model (not supported)",
            modelmeta.provider,
            modelmeta.model,
        )
        return False
    return stream


def _init_log_manager(logdir: Path, initial_msgs: list[Message]) -> LogManager:
    """Initialize and return the log manager."""
    console.log(f"Using logdir {path_with_tilde(logdir)}")
    return LogManager.load(logdir, initial_msgs=initial_msgs, create=True)


def _init_tool_format(tool_format: ToolFormat | None) -> ToolFormat:
    """Initialize and return the tool format."""
    config = get_config()
    tool_format_with_default: ToolFormat = tool_format or cast(
        ToolFormat, config.get_env("TOOL_FORMAT", "markdown")
    )
    set_tool_format(tool_format_with_default)
    return tool_format_with_default


def _init_and_setup_workspace(
    workspace: Path | None,
    logdir: Path,
    manager: LogManager,
) -> Path:
    """Initialize workspace and set up workspace prompt."""
    workspace = _init_workspace(workspace, logdir)
    console.log(f"Using workspace at {path_with_tilde(workspace)}")
    os.chdir(workspace)

    workspace_prompt = get_workspace_prompt(workspace)
    if (
        workspace_prompt
        and workspace_prompt not in [m.content for m in manager.log]
        and "user" not in [m.role for m in manager.log]
    ):
        manager.append(Message("system", workspace_prompt, hide=True, quiet=True))

    return workspace


def _print_log(manager: LogManager, show_hidden: bool) -> None:
    """Print the message log."""
    manager.log.print(show_hidden=show_hidden)
    console.print("--- ^^^ past messages ^^^ ---")


def _process_prompt(
    msg: Message,
    manager: LogManager,
    workspace: Path,
    stream: bool,
    confirm_func: ConfirmFunc,
    tool_format: ToolFormat,
    model: str | None = None,
    auto_rename: bool = True,
) -> None:
    """Process a single prompt message and its responses."""
    # Process and append the initial message
    msg = _prepare_message(msg, workspace)
    manager.append(msg)

    # Handle user commands
    if _is_executable_command(msg, manager, confirm_func):
        return

    # Auto-rename after first user message if name is generated
    if (
        auto_rename
        and msg.role == "user"
        and is_generated_name(manager.name)
        and any(m.role == "assistant" for m in manager.log)  # Has assistant response
    ):
        auto_rename_logs(dry_run=False, limit=1)

    # Generate and process responses
    while True:
        response_msgs = _get_response_messages(
            manager.log, stream, confirm_func, tool_format, workspace, model
        )
        if not response_msgs:  # Interrupted
            manager.append(Message("system", INTERRUPT_CONTENT))
            break

        if not _process_response_messages(response_msgs, manager, confirm_func):
            break


def _prepare_message(msg: Message, workspace: Path | None) -> Message:
    """Prepare a message by including paths if needed."""
    if msg.content.strip().startswith("/") and msg.role == "user":
        # we should not include contents in user "/commands"
        return msg
    elif msg.role == "user":
        return _include_paths(msg, workspace)
    return msg


def _is_executable_command(
    msg: Message, manager: LogManager, confirm_func: ConfirmFunc
) -> bool:
    """Check if message is an executable command and execute it if so."""
    return msg.role == "user" and execute_cmd(msg, manager, confirm_func)


def _get_response_messages(
    log: Log,
    stream: bool,
    confirm_func: ConfirmFunc,
    tool_format: ToolFormat,
    workspace: Path | None,
    model: str | None,
) -> list[Message]:
    """Get response messages, handling interrupts."""
    with Interruptible():
        return list(
            step(
                log,
                stream,
                confirm_func,
                tool_format=tool_format,
                workspace=workspace,
                model=model,
            )
        )


def _process_response_messages(
    response_msgs: list[Message],
    manager: LogManager,
    confirm_func: ConfirmFunc,
) -> bool:
    """
    Process response messages, executing any commands.
    Returns True if there are more messages to process, False otherwise.
    """
    for response_msg in response_msgs:
        manager.append(response_msg)
        if response_msg.role == "user" and execute_cmd(
            response_msg, manager, confirm_func
        ):
            return False

    # Check if there are any runnable tools left
    last_content = next(
        (m.content for m in reversed(manager.log) if m.role == "assistant"),
        "",
    )
    return any(
        tooluse.is_runnable for tooluse in ToolUse.iter_from_content(last_content)
    )


def step(
    log: Log | list[Message],
    stream: bool,
    confirm: ConfirmFunc,
    tool_format: ToolFormat = "markdown",
    workspace: Path | None = None,
    model: str | None = None,
    auto_rename: bool = True,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""
    if isinstance(log, list):
        log = Log(log)

    # Check for file modifications and run lint checks if needed
    if _should_check_modifications(log):
        if check_for_modifications(log) and (failed_check_message := check_changes()):
            yield Message("system", failed_check_message, quiet=False)
            return

    # Get user input if needed
    if _needs_user_input(log):
        msg = _get_user_input(workspace)
        yield msg
        log = log.append(msg)

    # Generate and execute response
    with Interruptible():
        yield from _generate_and_execute_response(
            log, stream, confirm, tool_format, workspace, model
        )


def _should_check_modifications(log: Log) -> bool:
    """Check if we should run modification checks."""
    last_assistant_msg = next(
        (m.content for m in reversed(log) if m.role == "assistant"), ""
    )
    return not any(
        tooluse.is_runnable for tooluse in ToolUse.iter_from_content(last_assistant_msg)
    )


def _needs_user_input(log: Log) -> bool:
    """Check if we need to get user input."""
    last_msg = log[-1] if log else None
    return (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == INTERRUPT_CONTENT
        or last_msg.pinned
        or not any(role == "user" for role in [m.role for m in log])
    )


def _get_user_input(workspace: Path | None) -> Message:
    """Get input from user and process it."""
    inquiry = prompt_user()
    msg = Message("user", inquiry, quiet=True)
    return _prepare_message(msg, workspace)


def _generate_and_execute_response(
    log: Log,
    stream: bool,
    confirm: ConfirmFunc,
    tool_format: ToolFormat,
    workspace: Path | None,
    model: str | None,
) -> Generator[Message, None, None]:
    """Generate response and execute any tools."""
    # performs reduction/context trimming, if necessary
    msgs = prepare_messages(log.messages, workspace)

    tools = None
    if tool_format == "tool":
        tools = [t for t in get_tools() if t.is_runnable()]

    # generate response
    with terminal_state_title("🤔 generating"):
        msg_response = reply(msgs, get_model(model).full, stream, tools)
        if os.environ.get("GPTME_COSTS") in ["1", "true"]:
            log_costs(msgs + [msg_response])

    # speak if TTS tool is available
    if has_tool("tts"):
        speak(msg_response.content)

    # log response and run tools
    if msg_response:
        yield msg_response.replace(quiet=True)
        yield from execute_msg(msg_response, confirm)


def prompt_user(value: str | None = None) -> str:  # pragma: no cover
    """Get user input with history and interrupt handling."""
    print_bell()
    termios.tcflush(sys.stdin, termios.TCIFLUSH)  # Clear input buffer

    with terminal_state_title("⌨️ waiting for input"):
        while True:
            with Interruptible():
                try:
                    response = prompt_input(PROMPT_USER, value)
                    if response:
                        add_history(response)
                        return response
                except EOFError:
                    print("\nGoodbye!")
                    sys.exit(0)


def prompt_input(prompt: str, value: str | None = None) -> str:  # pragma: no cover
    """Get input using prompt_toolkit with fish-style suggestions."""
    prompt = prompt.strip() + ": "
    if value:
        console.print(prompt + value)
        return value

    return get_input(prompt)


def _include_paths(msg: Message, workspace: Path | None = None) -> Message:
    """
    Process paths and URLs in a message, including their contents or references.

    In legacy mode (default):
    - Text file contents are included as codeblocks in the message
    - Images and other supported files are included as msg.files

    In fresh context mode (GPTME_FRESH_CONTEXT=1):
    - All files are included in msg.files
    - Contents are applied right before sending to LLM

    Args:
        msg: Message to process
        workspace: Base directory for relative paths

    Returns:
        Updated message with included file contents and/or references
    """
    if msg.role != "user":
        raise ValueError("Can only include paths in user messages")

    append_msg = ""
    files = []

    # Process each potential path/URL
    for word in find_potential_paths(msg.content):
        logger.debug(f"Processing potential path/url: {word}")

        try:
            if is_url(word):
                if not use_fresh_context():
                    append_msg += process_url(word)
            else:
                file_path = resolve_path(word, workspace)
                if file_path:
                    if not use_fresh_context() and (
                        contents := read_text_file(file_path)
                    ):
                        append_msg += f"\n\n```{word}\n{contents}\n```"
                    else:
                        files.append(file_path)
        except Exception as e:
            logger.warning(f"Failed to process {word}: {e}")

    # Update message with processed content
    if files:
        msg = msg.replace(files=msg.files + files)
    if append_msg:
        msg = msg.replace(content=msg.content + append_msg)

    return msg


def check_for_modifications(log: Log) -> bool:
    """
    Check if there are any file modifications in recent messages.

    Looks at messages since the last user message, up to a maximum of 3,
    checking for any tools that modify files.
    """
    # Get messages since last user message
    messages = list(reversed(log))
    messages_since_user = []
    for msg in messages:
        if msg.role == "user":
            break
        messages_since_user.append(msg)

    # Check for file modification tools in recent messages
    file_modifying_tools = {"save", "patch", "append"}
    return any(
        tu.tool in file_modifying_tools
        for msg in messages_since_user[:3]  # Only check last 3 messages
        for tu in ToolUse.iter_from_content(msg.content)
    )


def check_changes() -> str | None:
    """
    Run lint/pre-commit checks after file modifications.
    Returns error message if checks fail, None otherwise.
    """
    return run_precommit_checks()


def _init_workspace(workspace: Path | None, logdir: Path | None = None) -> Path:
    """Initialize and return the workspace path.

    Args:
        workspace: Path to workspace directory. If None, uses current directory.
        logdir: Path to log directory. If provided, manages workspace symlink.

    Returns:
        Path to the initialized workspace.

    The function ensures a consistent workspace setup by:
    1. Using the provided workspace or current directory
    2. If logdir provided:
       - Uses existing workspace at $logdir/workspace if it exists
       - Creates a symlink to workspace at $logdir/workspace if it doesn't
    """
    # Use current directory if no workspace specified
    workspace = workspace or Path.cwd()

    if not logdir:
        return workspace

    # Handle workspace in log directory
    log_workspace = logdir / "workspace"
    if log_workspace.exists():
        resolved_workspace = log_workspace.resolve()
        if workspace != resolved_workspace:
            raise ValueError(
                f"Workspace conflict: {log_workspace} already exists and points to "
                f"{resolved_workspace}, won't override with {workspace}"
            )
        return resolved_workspace

    # Create symlink to workspace
    if not workspace.exists():
        raise ValueError(f"Workspace path does not exist: {workspace}")
    log_workspace.symlink_to(workspace, target_is_directory=True)
    return workspace
