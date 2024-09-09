import logging
import re
import sys
from collections.abc import Generator
from time import sleep
from typing import Literal

from . import llm
from .codeblock import Codeblock
from .constants import CMDFIX
from .logmanager import LogManager
from .message import (
    Message,
    len_tokens,
    msgs_to_toml,
    print_msg,
    toml_to_msgs,
)
from .models import get_model
from .tools import (
    execute_codeblock,
    execute_msg,
    is_supported_langtag,
    loaded_tools,
)
from .useredit import edit_text_with_editor
from .util import ask_execute

logger = logging.getLogger(__name__)

Actions = Literal[
    "log",
    "edit",
    "rename",
    "fork",
    "summarize",
    "context",
    "replay",
    "undo",
    "impersonate",
    "tools",
    "tokens",
    "help",
    "exit",
]

action_descriptions: dict[Actions, str] = {
    "undo": "Undo the last action",
    "log": "Show the conversation log",
    "edit": "Edit the conversation in your editor",
    "rename": "Rename the conversation",
    "fork": "Create a copy of the conversation with a new name",
    "summarize": "Summarize the conversation",
    "replay": "Re-execute codeblocks in the conversation, wont store output in log",
    "impersonate": "Impersonate the assistant",
    "tokens": "Show the number of tokens used",
    "tools": "Show available tools",
    "help": "Show this help message",
    "exit": "Exit the program",
}
COMMANDS = list(action_descriptions.keys())


def execute_cmd(msg: Message, log: LogManager) -> bool:
    """Executes any user-command, returns True if command was executed."""
    assert msg.role == "user"

    # if message starts with ., treat as command
    # when command has been run,
    if msg.content[:1] in ["/"]:
        for resp in handle_cmd(msg.content, log, no_confirm=True):
            log.append(resp)
        return True
    return False


def handle_cmd(
    cmd: str, log: LogManager, no_confirm: bool
) -> Generator[Message, None, None]:
    """Handles a command."""
    cmd = cmd.lstrip(CMDFIX)
    logger.debug(f"Executing command: {cmd}")
    name, *args = re.split(r"[\n\s]", cmd)
    full_args = cmd.split(" ", 1)[1] if " " in cmd else ""
    match name:
        case "log":
            log.undo(1, quiet=True)
            log.print(show_hidden="--hidden" in args)
        case "rename":
            log.undo(1, quiet=True)
            log.write()
            # rename the conversation
            print("Renaming conversation (enter empty name to auto-generate)")
            new_name = args[0] if args else input("New name: ")
            rename(log, new_name, ask=not no_confirm)
        case "fork":
            # fork the conversation
            new_name = args[0] if args else input("New name: ")
            log.fork(new_name)
        case "summarize":
            msgs = log.prepare_messages()
            msgs = [m for m in msgs if not m.hide]
            summary = llm.summarize(msgs)
            print(f"Summary: {summary}")
        case "edit":
            # edit previous messages
            # first undo the '/edit' command itself
            log.undo(1, quiet=True)
            yield from edit(log)
        case "undo":
            # undo the '/undo' command itself
            log.undo(1, quiet=True)
            # if int, undo n messages
            n = int(args[0]) if args and args[0].isdigit() else 1
            log.undo(n)
        case "exit":
            sys.exit(0)
        case "replay":
            log.undo(1, quiet=True)
            log.write()
            print("Replaying conversation...")
            for msg in log.log:
                if msg.role == "assistant":
                    for reply_msg in execute_msg(msg, ask=True):
                        print_msg(reply_msg, oneline=False)
        case "impersonate":
            content = full_args if full_args else input("[impersonate] Assistant: ")
            msg = Message("assistant", content)
            yield msg
            yield from execute_msg(msg, ask=not no_confirm)
        case "tokens":
            log.undo(1, quiet=True)
            n_tokens = len_tokens(log.log)
            print(f"Tokens used: {n_tokens}")
            model = get_model()
            if model:
                print(f"Model: {model.model}")
                if model.price_input:
                    print(f"Cost (input): ${n_tokens * model.price_input / 1_000_000}")
        case "tools":
            log.undo(1, quiet=True)
            print("Available tools:")
            for tool in loaded_tools:
                print(
                    f"""
  # {tool.name}
    {tool.desc.rstrip(".")}
    tokens (example): {len_tokens(tool.examples)}"""
                )
        case _:
            # the case for python, shell, and other block_types supported by tools
            if is_supported_langtag(name):
                yield from execute_codeblock(
                    Codeblock(name, full_args), ask=not no_confirm
                )
            else:
                if log.log[-1].content != f"{CMDFIX}help":
                    print("Unknown command")
                # undo the '/help' command itself
                log.undo(1, quiet=True)
                log.write()
                help()


def edit(log: LogManager) -> Generator[Message, None, None]:  # pragma: no cover
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
    log.edit(list(reversed(res)))
    # now we need to redraw the log so the user isn't seeing stale messages in their buffer
    # log.print()
    print("Applied edited messages, write /log to see the result")


def rename(log: LogManager, new_name: str, ask: bool = True):
    if new_name in ["", "auto"]:
        new_name = llm.generate_name(log.prepare_messages())
        assert " " not in new_name
        print(f"Generated name: {new_name}")
        if ask:
            confirm = ask_execute("Confirm?")
            if not confirm:
                print("Aborting")
                return
        log.rename(new_name, keep_date=True)
    else:
        log.rename(new_name, keep_date=False)
    print(f"Renamed conversation to {log.logfile.parent}")


def _gen_help(incl_langtags: bool = True) -> Generator[str, None, None]:
    yield "Available commands:"
    max_cmdlen = max(len(cmd) for cmd in COMMANDS)
    for cmd, desc in action_descriptions.items():
        yield f"  /{cmd.ljust(max_cmdlen)}  {desc}"

    if incl_langtags:
        yield ""
        yield "To execute code with supported tools, use the following syntax:"
        yield "  /<langtag> <code>"
        yield ""
        yield "Example:"
        yield "  /sh echo hello"
        yield "  /python print('hello')"
        yield ""
        yield "Supported langtags:"
        for tool in loaded_tools:
            if tool.block_types:
                yield f"  - {tool.block_types[0]}" + (
                    f"  (alias: {', '.join(tool.block_types[1:])})"
                    if len(tool.block_types) > 1
                    else ""
                )


def help():
    for line in _gen_help():
        print(line)
