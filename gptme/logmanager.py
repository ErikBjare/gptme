import json
import shutil
import textwrap
from pathlib import Path
from typing import TypeAlias

from rich import print
from rich.syntax import Syntax

from .constants import role_color
from .message import Message
from .prompts import initial_prompt
from .reduce import limit_log, reduce_log
from .util import len_tokens

PathLike: TypeAlias = str | Path


class LogManager:
    def __init__(
        self,
        log: list[Message] | None = None,
        logfile: PathLike | None = None,
        show_hidden=False,
    ):
        self.log = log or []
        assert logfile is not None, "logfile must be specified"
        self.logfile = logfile
        self.show_hidden = show_hidden
        # TODO: Check if logfile has contents, then maybe load, or should it overwrite?

    def append(self, msg: Message, quiet=False) -> None:
        """Appends a message to the log, writes the log, prints the message."""
        self.log.append(msg)
        self.write()
        if not quiet:
            print_log(msg, oneline=False)

    def write(self) -> None:
        """Writes the log to the logfile."""
        write_log(self.log, self.logfile)

    def print(self, show_hidden: bool | None = None):
        print_log(self.log, oneline=False, show_hidden=show_hidden or self.show_hidden)

    def undo(self, n: int = 1) -> None:
        """Removes the last message from the log."""
        undid = self.log[-1] if self.log else None
        if undid and undid.content.startswith(".undo"):
            self.log.pop()

        # Doesn't work for multiple undos in a row, but useful in testing
        # assert undid.content == ".undo"  # assert that the last message is an undo
        peek = self.log[-1] if self.log else None
        if not peek:
            print("[yellow]Nothing to undo.[/yellow]")
            return

        print("[yellow]Undoing messages:[/yellow]")
        for _ in range(n):
            undid = self.log.pop()
            print(
                f"[red]  {undid.role}: {textwrap.shorten(undid.content.strip(), width=30, placeholder='...')}[/red]",
            )
            peek = self.log[-1] if self.log else None

    def prepare_messages(self) -> list[Message]:
        """Prepares the log into messages before sending it to the LLM."""
        msgs = self.log
        msgs_reduced = list(reduce_log(msgs))

        if len(msgs) != len(msgs_reduced):
            print(
                f"Reduced log from {len_tokens(msgs)//1} to {len_tokens(msgs_reduced)//1} tokens"
            )
        msgs_limited = limit_log(msgs_reduced)
        if len(msgs_reduced) != len(msgs_limited):
            print(
                f"Limited log from {len(msgs_reduced)} to {len(msgs_limited)} messages"
            )
        return msgs_limited

    @classmethod
    def load(
        cls, logfile=None, initial_msgs=initial_prompt(), **kwargs
    ) -> "LogManager":
        """Loads a conversation log."""
        with open(logfile, "r") as file:
            msgs = [Message(**json.loads(line)) for line in file.readlines()]
        if not msgs:
            msgs = initial_msgs
        return cls(msgs, logfile=logfile, **kwargs)


def write_log(msg_or_log: Message | list[Message], logfile: PathLike) -> None:
    """
    Writes to the conversation log.
    If a single message given, append.
    If a list of messages given, overwrite.
    """
    if isinstance(msg_or_log, Message):
        msg = msg_or_log
        with open(logfile, "a") as file:
            file.write(json.dumps(msg.to_dict()) + "\n")
    elif isinstance(msg_or_log, list):
        log = msg_or_log
        with open(logfile, "w") as file:
            for msg in log:
                file.write(json.dumps(msg.to_dict()) + "\n")
    else:
        raise TypeError(
            "Expected Message or list of Messages, got " + str(type(msg_or_log))
        )


def print_log(
    log: Message | list[Message], oneline: bool = True, show_hidden=False
) -> None:
    """Prints the log to the console."""
    skipped_hidden = 0
    for msg in log if isinstance(log, list) else [log]:
        if msg.hide and not show_hidden:
            skipped_hidden += 1
            continue
        color = role_color[msg.role]
        userprefix = f"[bold {color}]{msg.user}[/bold {color}]"
        # get terminal width
        max_len = shutil.get_terminal_size().columns - len(userprefix)
        output = ""
        if oneline:
            output += textwrap.shorten(
                msg.content.replace("\n", "\\n"), width=max_len, placeholder="..."
            )
            if len(output) < 20:
                output = msg.content.replace("\n", "\\n")[:max_len] + "..."
        else:
            multiline = len(msg.content.split("\n")) > 1
            output += ("\n  " if multiline else "") + textwrap.indent(
                msg.content, prefix="  "
            )[2:]

        # find code-blocks and syntax highlight them with rich
        startstr = "```python"
        if startstr in output:
            code_start = output.find(startstr)
            code_end = (
                output[code_start + len(startstr) :].find("```")
                + code_start
                + len(startstr)
            )
            code = output[code_start + 10 : code_end]
            print(f"\n{userprefix}: {output[:code_start]}{startstr}")
            print(Syntax(code.rstrip(), "python"))
            print(f"  ```{output[code_end+3:]}")
        else:
            print(f"\n{userprefix}: {output.rstrip()}")
    if skipped_hidden:
        print(
            f"[grey30]Skipped {skipped_hidden} hidden system messages, show with --show-hidden[/]"
        )
