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
from .llm.models import get_default_model, get_model
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
from .util.context import include_paths, run_precommit_checks
from .util.cost import log_costs
from .util.interrupt import clear_interruptible, set_interruptible
from .util.prompt import add_history, get_input
from .util.terminal import set_current_conv_name, terminal_state_title

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
) -> None:
    """
    Run the chat loop.

    prompt_msgs: list of messages to execute in sequence.
    initial_msgs: list of history messages.
    workspace: path to workspace directory.

    Callable from other modules.
    """
    # Set initial terminal title with conversation name
    conv_name = logdir.name
    set_current_conv_name(conv_name)

    # init
    init(model, interactive, tool_allowlist)

    default_model = get_default_model()
    assert default_model is not None, "No model loaded and no model specified"
    modelmeta = get_model(model or default_model.full)
    if not modelmeta.supports_streaming and stream:
        logger.info(
            "Disabled streaming for '%s/%s' model (not supported)",
            modelmeta.provider,
            modelmeta.model,
        )
        stream = False

    console.log(f"Using logdir {path_with_tilde(logdir)}")
    manager = LogManager.load(logdir, initial_msgs=initial_msgs, create=True)

    config = get_config()
    tool_format_with_default: ToolFormat = tool_format or cast(
        ToolFormat, config.get_env("TOOL_FORMAT", "markdown")
    )

    # By defining the tool_format at the last moment we ensure we can use the
    # configuration for subagent
    set_tool_format(tool_format_with_default)

    # Initialize workspace
    workspace = _init_workspace(workspace, logdir)
    console.log(f"Using workspace at {path_with_tilde(workspace)}")
    os.chdir(workspace)

    workspace_prompt = get_workspace_prompt(workspace)
    # FIXME: this is hacky
    # NOTE: needs to run after the workspace is set
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
                msg = include_paths(msg, workspace)
                manager.append(msg)
                # if prompt is a user-command, execute it
                if msg.role == "user" and execute_cmd(msg, manager, confirm_func):
                    continue

                # Generate and execute response for this prompt
                while True:
                    try:
                        set_interruptible()
                        response_msgs = list(
                            step(
                                manager.log,
                                stream,
                                confirm_func,
                                tool_format=tool_format_with_default,
                                workspace=workspace,
                                model=model,
                            )
                        )
                    except KeyboardInterrupt:
                        console.log("Interrupted. Stopping current execution.")
                        manager.append(Message("system", INTERRUPT_CONTENT))
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
                    has_runnable = any(
                        tooluse.is_runnable
                        for tooluse in ToolUse.iter_from_content(last_content)
                    )
                    if not has_runnable:
                        break

            # All prompts processed, continue to next iteration
            continue

        # if:
        #  - prompts exhausted
        #  - non-interactive
        #  - no executable block in last assistant message
        # then exit
        elif not interactive:
            logger.debug("Non-interactive and exhausted prompts")
            if has_tool("tts") and os.environ.get("GPTME_VOICE_FINISH", "").lower() in [
                "1",
                "true",
            ]:
                logger.info("Waiting for TTS to finish...")

                set_interruptible()
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
            break

        # ask for input if no prompt, generate reply, and run tools
        clear_interruptible()  # Ensure we're not interruptible during user input
        for msg in step(
            manager.log,
            stream,
            confirm_func,
            tool_format=tool_format_with_default,
            workspace=workspace,
        ):  # pragma: no cover
            manager.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, manager, confirm_func):
                break


def step(
    log: Log | list[Message],
    stream: bool,
    confirm: ConfirmFunc,
    tool_format: ToolFormat = "markdown",
    workspace: Path | None = None,
    model: str | None = None,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""
    default_model = get_default_model()
    assert default_model is not None, "No model loaded and no model specified"
    model = model or default_model.full
    if isinstance(log, list):
        log = Log(log)

    # Check if we have any recent file modifications, and if so, run lint checks
    if not any(
        tooluse.is_runnable
        for tooluse in ToolUse.iter_from_content(
            next((m.content for m in reversed(log) if m.role == "assistant"), "")
        )
    ):
        # Only check for modifications if the last assistant message has no runnable tools
        if check_for_modifications(log) and (failed_check_message := check_changes()):
            yield Message("system", failed_check_message, quiet=False)
            return

    # If last message was a response, ask for input.
    # If last message was from the user (such as from crash/edited log),
    # then skip asking for input and generate response
    last_msg = log[-1] if log else None
    if (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == INTERRUPT_CONTENT
        or last_msg.pinned
        or not any(role == "user" for role in [m.role for m in log])
    ):  # pragma: no cover
        inquiry = prompt_user()
        msg = Message("user", inquiry, quiet=True)
        msg = include_paths(msg, workspace)
        yield msg
        log = log.append(msg)

    # generate response and run tools
    try:
        set_interruptible()

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
    finally:
        clear_interruptible()


def prompt_user(value=None) -> str:  # pragma: no cover
    print_bell()
    # Flush stdin to clear any buffered input before prompting
    termios.tcflush(sys.stdin, termios.TCIFLUSH)
    response = ""
    with terminal_state_title("⌨️ waiting for input"):
        while not response:
            try:
                set_interruptible()
                response = prompt_input(PROMPT_USER, value)
                if response:
                    add_history(response)
            except KeyboardInterrupt:
                print("\nInterrupted. Press Ctrl-D to exit.")
            except EOFError:
                print("\nGoodbye!")
                sys.exit(0)
    clear_interruptible()
    return response


def prompt_input(prompt: str, value=None) -> str:  # pragma: no cover
    """Get input using prompt_toolkit with fish-style suggestions."""
    prompt = prompt.strip() + ": "
    if value:
        console.print(prompt + value)
        return value

    return get_input(prompt)


def check_for_modifications(log: Log) -> bool:
    """Check if there are any file modifications in last 3 messages or since last user message."""
    messages_since_user = []
    for m in reversed(log):
        if m.role == "user":
            break
        messages_since_user.append(m)

    # FIXME: this is hacky and unreliable
    has_modifications = any(
        tu.tool in ["save", "patch", "append"]
        for m in messages_since_user[:3]
        for tu in ToolUse.iter_from_content(m.content)
    )
    # logger.debug(
    #     f"Found {len(messages_since_user)} messages since user ({has_modifications=})"
    # )
    return has_modifications


def check_changes() -> str | None:
    """Run lint/pre-commit checks after file modifications."""
    return run_precommit_checks()


def _init_workspace(workspace: Path | None, logdir: Path | None = None) -> Path:
    """Initialize workspace and return the workspace path.

    If workspace is None, use current directory.
    If logdir is provided, use ``$logdir/workspace`` as workspace if it exists, else create a symlink to workspace.
    """
    if not workspace:
        workspace = Path.cwd()

    if logdir:
        log_workspace = logdir / "workspace"
        if log_workspace.exists():
            assert not workspace or (
                workspace == log_workspace.resolve()
            ), f"Workspace already exists in {log_workspace}, wont override."
            workspace = log_workspace.resolve()
        else:
            assert workspace.exists(), f"Workspace path {workspace} does not exist"
            log_workspace.symlink_to(workspace, target_is_directory=True)

    return workspace
