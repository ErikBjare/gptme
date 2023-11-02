import json
import logging
import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator, Literal, TypeAlias

from rich import print

from .constants import CMDFIX, LOGSDIR
from .message import Message, print_msg
from .prompts import initial_prompt
from .tools.reduce import limit_log, reduce_log
from .util import len_tokens

PathLike: TypeAlias = str | Path

logger = logging.getLogger(__name__)

RoleLiteral = Literal["user", "assistant", "system"]


class LogManager:
    """Manages a conversation log."""

    def __init__(
        self,
        log: list[Message] | None = None,
        logfile: PathLike | None = None,
        show_hidden=False,
    ):
        self.log = log or []
        if logfile is None:
            # generate tmpfile
            fpath = NamedTemporaryFile(delete=False).name
            print(f"[yellow]No logfile specified, using tmpfile {fpath}.[/]")
            logfile = Path(fpath)
        self.logfile = logfile if isinstance(logfile, Path) else Path(logfile)
        self.show_hidden = show_hidden
        # TODO: Check if logfile has contents, then maybe load, or should it overwrite?

    def __getitem__(self, key):
        return self.log[key]

    def __len__(self):
        return len(self.log)

    def __iter__(self):
        return iter(self.log)

    def __bool__(self):
        return bool(self.log)

    def append(self, msg: Message) -> None:
        """Appends a message to the log, writes the log, prints the message."""
        self.log.append(msg)
        self.write()
        if not msg.quiet:
            print_msg(msg, oneline=False)

    def pop(self, index: int = -1) -> Message:
        return self.log.pop(index)

    def write(self) -> None:
        """Writes the log to the logfile."""
        write_log(self.log, self.logfile)

    def print(self, show_hidden: bool | None = None):
        print_msg(self.log, oneline=False, show_hidden=show_hidden or self.show_hidden)

    def undo(self, n: int = 1, quiet=False) -> None:
        """Removes the last message from the log."""
        undid = self[-1] if self.log else None
        if undid and undid.content.startswith(f"{CMDFIX}undo"):
            self.pop()

        # Doesn't work for multiple undos in a row, but useful in testing
        # assert undid.content == ".undo"  # assert that the last message is an undo
        peek = self[-1] if self.log else None
        if not peek:
            print("[yellow]Nothing to undo.[/]")
            return

        if not quiet:
            print("[yellow]Undoing messages:[/yellow]")
        for _ in range(n):
            undid = self.pop()
            if not quiet:
                print(
                    f"[red]  {undid.role}: {textwrap.shorten(undid.content.strip(), width=50, placeholder='...')}[/]",
                )
            peek = self[-1] if self.log else None

    def prepare_messages(self) -> list[Message]:
        """Prepares the log into messages before sending it to the LLM."""
        msgs = self.log
        msgs_reduced = list(reduce_log(msgs))

        if len_tokens(msgs) != len_tokens(msgs_reduced):
            logger.info(
                f"Reduced log from {len_tokens(msgs)//1} to {len_tokens(msgs_reduced)//1} tokens"
            )
        msgs_limited = limit_log(msgs_reduced)
        if len(msgs_reduced) != len(msgs_limited):
            logger.info(
                f"Limited log from {len(msgs_reduced)} to {len(msgs_limited)} messages"
            )
        return msgs_limited

    @classmethod
    def load(
        cls,
        logfile: PathLike,
        initial_msgs: list[Message] = list(initial_prompt()),
        **kwargs,
    ) -> "LogManager":
        """Loads a conversation log."""
        if str(LOGSDIR) not in str(logfile):
            # if the path was not fully specified, assume its a dir in LOGSDIR
            logfile = LOGSDIR / logfile / "conversation.jsonl"
        if not Path(logfile).exists():
            raise FileNotFoundError(f"Could not find logfile {logfile}")

        with open(logfile, "r") as file:
            msgs = [Message(**json.loads(line)) for line in file.readlines()]
        if not msgs:
            msgs = initial_msgs
        return cls(msgs, logfile=logfile, **kwargs)

    def get_last_code_block(
        self,
        role: RoleLiteral | None = None,
        history: int | None = None,
        content=False,
    ) -> str | None:
        """Returns the last code block in the log, if any.

        If `role` set, only check that role.
        If `history` set, only check n messages back.
        If `content` set, return the content of the code block, else return the whole message.
        """
        msgs = self.log
        if role:
            msgs = [msg for msg in msgs if msg.role == role]
        if history:
            msgs = msgs[-history:]

        for msg in msgs[::-1]:
            # check if message contains a code block
            backtick_count = msg.content.count("```")
            if backtick_count >= 2:
                if content:
                    return msg.content.split("```")[-2].split("\n", 1)[-1]
                else:
                    return msg.content
        return None

    def rename(self, name: str, keep_date=False) -> None:
        """
        rename the conversation and log file
        if keep_date is True, we will keep the date part of the log file name ("2021-08-01-some-name")
        if you want to keep the old log, use fork()
        """
        if keep_date:
            name = f"{self.logfile.parent.name[:10]}-{name}"
        (LOGSDIR / name).mkdir(parents=True, exist_ok=True)
        self.logfile.rename(LOGSDIR / name / "conversation.jsonl")
        self.logfile = LOGSDIR / name / "conversation.jsonl"

    def fork(self, name: str) -> None:
        # save and switch to a new log file without renaming the old one
        self.write()
        self.logfile = LOGSDIR / name / "conversation.jsonl"
        self.write()

    def to_dict(self) -> dict:
        return {
            "log": [msg.to_dict() for msg in self.log],
            "logfile": str(self.logfile),
        }


def write_log(msg_or_log: Message | list[Message], logfile: PathLike) -> None:
    """
    Writes to the conversation log.
    If a single message given, append.
    If a list of messages given, overwrite.
    """
    # create directory if it doesn't exist
    Path(logfile).parent.mkdir(parents=True, exist_ok=True)

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


def _conversations() -> list[Path]:
    return list(sorted(LOGSDIR.glob("*/*.jsonl"), key=lambda f: f.stat().st_mtime))


def get_conversations() -> Generator[dict, None, None]:
    for c in _conversations():
        msgs = [Message(**json.loads(line)) for line in open(c)]
        first_timestamp = msgs[0].timestamp.timestamp() if msgs else c.stat().st_mtime
        yield {
            "name": f"{c.parent.name}",
            "path": str(c),
            "created": first_timestamp,
            "modified": c.stat().st_mtime,
            "messages": len(msgs),
        }
