import logging
import sys
from pathlib import Path
from time import sleep
from typing import Generator, Literal

from . import llm
from .constants import CMDFIX
from .logmanager import LogManager
from .message import (
    Message,
    msgs_to_toml,
    print_msg,
    toml_to_msgs,
)
from .tools import execute_msg, execute_python, execute_shell
from .tools.context import gen_context_msg
from .tools.summarize import summarize
from .tools.useredit import edit_text_with_editor

logger = logging.getLogger(__name__)

Actions = Literal[
    "summarize",
    "log",
    "edit",
    "rename",
    "fork",
    "summarize",
    "context",
    "save",
    "shell",
    "python",
    "replay",
    "undo",
    "impersonate",
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
    "save": "Save the last code block to a file",
    "shell": "Execute shell code",
    "python": "Execute Python code",
    "replay": "Re-execute codeblocks in the conversation, wont store output in log",
    "impersonate": "Impersonate the assistant",
    "help": "Show this help message",
    "exit": "Exit the program",
}
COMMANDS = list(action_descriptions.keys())


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
        case "log":
            log.undo(1, quiet=True)
            log.print(show_hidden="--hidden" in args)
        case "rename":
            log.undo(1, quiet=True)
            log.write()
            # rename the conversation
            print("Renaming conversation (enter 'auto' to generate a name)")
            new_name = args[0] if args else input("New name: ")
            if new_name == "auto":
                new_name = llm.generate_name(log.prepare_messages())
                assert " " not in new_name
                print(f"Generated name: {new_name}")
                confirm = input("Confirm? [y/N] ")
                if confirm.lower() not in ["y", "yes"]:
                    print("Aborting")
                    return
                log.rename(new_name, keep_date=True)
            else:
                log.rename(new_name, keep_date=False)
            print(f"Renamed conversation to {log.logfile.parent}")
        case "fork":
            # fork the conversation
            new_name = args[0] if args else input("New name: ")
            log.fork(new_name)
        case "summarize":
            msgs = log.prepare_messages()
            msgs = [m for m in msgs if not m.hide]
            summary = summarize(msgs)
            print(f"Summary: {summary}")
        case "edit":
            # edit previous messages
            # first undo the '/edit' command itself
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
            print("Applied edited messages, write /log to see the result")
        case "context":
            # print context msg
            yield gen_context_msg()
        case "undo":
            # undo the '/undo' command itself
            log.undo(1, quiet=True)
            # if int, undo n messages
            n = int(args[0]) if args and args[0].isdigit() else 1
            log.undo(n)
        case "save":
            # undo
            log.undo(1, quiet=True)

            # save the most recent code block to a file
            code = log.get_last_code_block()
            if not code:
                print("No code block found")
                return
            filename = args[0] if args else input("Filename: ")
            if Path(filename).exists():
                ans = input("File already exists, overwrite? [y/N] ")
                if ans.lower() != "y":
                    return
            with open(filename, "w") as f:
                f.write(code)
            print(f"Saved code block to {filename}")
        case "exit":
            sys.exit(0)
        case "replay":
            log.undo(1, quiet=True)
            log.write()
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
            log.write()

            longest_cmd = max(len(cmd) for cmd in COMMANDS)
            print("Available commands:")
            for cmd, desc in action_descriptions.items():
                cmd = cmd.ljust(longest_cmd)
                print(f"  /{cmd}  {desc}")
