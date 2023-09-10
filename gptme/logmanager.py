import json
import textwrap
from pathlib import Path
from typing import TypeAlias

from rich import print

from .message import Message, print_msg
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
            print_msg(msg, oneline=False)

    def write(self) -> None:
        """Writes the log to the logfile."""
        write_log(self.log, self.logfile)

    def print(self, show_hidden: bool | None = None):
        print_msg(self.log, oneline=False, show_hidden=show_hidden or self.show_hidden)

    def undo(self, n: int = 1) -> None:
        """Removes the last message from the log."""
        undid = self.log[-1] if self.log else None
        if undid and undid.content.startswith(".undo"):
            self.log.pop()

        # Doesn't work for multiple undos in a row, but useful in testing
        # assert undid.content == ".undo"  # assert that the last message is an undo
        peek = self.log[-1] if self.log else None
        if not peek:
            print("[yellow]Nothing to undo.[/]")
            return

        print("[yellow]Undoing messages:[/]")
        for _ in range(n):
            undid = self.log.pop()
            print(
                f"[red]  {undid.role}: {textwrap.shorten(undid.content.strip(), width=50, placeholder='...')}[/]",
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
