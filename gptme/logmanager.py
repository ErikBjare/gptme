import json
import logging
import shutil
import textwrap
from collections.abc import Generator
from copy import copy
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, TypeAlias

from rich import print

from .constants import CMDFIX
from .dirs import get_logs_dir
from .message import Message, len_tokens, print_msg
from .prompts import get_prompt
from .tools.reduce import limit_log, reduce_log

PathLike: TypeAlias = str | Path

logger = logging.getLogger(__name__)

RoleLiteral = Literal["user", "assistant", "system"]


class LogManager:
    """Manages a conversation log."""

    def __init__(
        self,
        log: list[Message] | None = None,
        logdir: PathLike | None = None,
        branch: str | None = None,
        show_hidden=False,
    ):
        self.current_branch = branch or "main"

        if logdir:
            self.logdir = Path(logdir)
        else:
            # generate tmpfile
            fpath = TemporaryDirectory().name
            logger.warning(f"No logfile specified, using tmpfile at {fpath}")
            self.logdir = Path(fpath)
        self.name = self.logdir.name

        # load branches from adjacent files
        self._branches = {self.current_branch: log or []}
        if self.logdir / "conversation.jsonl":
            _branch = "main"
            if _branch not in self._branches:
                with open(self.logdir / "conversation.jsonl") as f:
                    self._branches[_branch] = [
                        Message(**json.loads(line)) for line in f
                    ]
        for file in self.logdir.glob("branches/*.jsonl"):
            if file.name == self.logdir.name:
                continue
            _branch = file.stem
            if _branch not in self._branches:
                with open(file) as f:
                    self._branches[_branch] = [
                        Message(**json.loads(line)) for line in f
                    ]

        self.show_hidden = show_hidden
        # TODO: Check if logfile has contents, then maybe load, or should it overwrite?

    @property
    def log(self) -> list[Message]:
        return self._branches[self.current_branch]

    @property
    def logfile(self) -> Path:
        if self.current_branch == "main":
            return get_logs_dir() / self.name / "conversation.jsonl"
        return self.logdir / "branches" / f"{self.current_branch}.jsonl"

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

    def write(self, branches=True) -> None:
        """
        Writes to the conversation log.
        """
        # create directory if it doesn't exist
        Path(self.logfile).parent.mkdir(parents=True, exist_ok=True)

        # write current branch
        with open(self.logfile, "w") as file:
            for msg in self.log:
                file.write(json.dumps(msg.to_dict()) + "\n")

        # write other branches
        # FIXME: wont write main branch if on a different branch
        if branches:
            branches_dir = self.logdir / "branches"
            branches_dir.mkdir(parents=True, exist_ok=True)
            for branch, msgs in self._branches.items():
                if branch == "main":
                    continue
                branch_path = branches_dir / f"{branch}.jsonl"
                with open(branch_path, "w") as file:
                    for msg in msgs:
                        file.write(json.dumps(msg.to_dict()) + "\n")

    def print(self, show_hidden: bool | None = None):
        print_msg(self.log, oneline=False, show_hidden=show_hidden or self.show_hidden)

    def _save_backup_branch(self, type="edit") -> None:
        """backup the current log to a new branch, usually before editing/undoing"""
        branch_prefix = f"{self.current_branch}-{type}-"
        n = len([b for b in self._branches.keys() if b.startswith(branch_prefix)])
        self._branches[f"{branch_prefix}{n}"] = copy(self.log)
        self.write()

    def edit(self, new_log: list[Message]) -> None:
        """Edits the log."""
        self._save_backup_branch(type="edit")
        self._branches[self.current_branch] = new_log
        self.write()

    def undo(self, n: int = 1, quiet=False) -> None:
        """Removes the last message from the log."""
        undid = self[-1] if self.log else None
        if undid and undid.content.startswith(f"{CMDFIX}undo"):
            self.log.pop()

        # don't save backup branch if undoing a command
        if not self[-1].content.startswith(CMDFIX):
            self._save_backup_branch(type="undo")

        # Doesn't work for multiple undos in a row, but useful in testing
        # assert undid.content == ".undo"  # assert that the last message is an undo
        peek = self[-1] if self.log else None
        if not peek:
            print("[yellow]Nothing to undo.[/]")
            return

        if not quiet:
            print("[yellow]Undoing messages:[/yellow]")
        for _ in range(n):
            undid = self.log.pop()
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
        initial_msgs: list[Message] | None = None,
        branch: str = "main",
        **kwargs,
    ) -> "LogManager":
        """Loads a conversation log."""
        if not initial_msgs:
            initial_msgs = [get_prompt()]
        logsdir = get_logs_dir()
        if str(logsdir) not in str(logfile):
            # if the path was not fully specified, assume its a dir in logsdir
            logdir = logsdir / logfile
            logfile = logdir / (
                "conversation.jsonl" if branch == "main" else f"branches/{branch}.jsonl"
            )
        else:
            logdir = Path(logfile).parent
            if logdir.name == "branches":
                logdir = logdir.parent

        if branch != "main":
            logfile = logdir / f"branches/{branch}.jsonl"

        if not Path(logfile).exists():
            raise FileNotFoundError(f"Could not find logfile {logfile}")

        with open(logfile) as file:
            msgs = [Message(**json.loads(line)) for line in file.readlines()]
        if not msgs:
            msgs = initial_msgs
        return cls(msgs, logdir=logdir, branch=branch, **kwargs)

    def get_last_code_block(
        self,
        role: RoleLiteral | None = None,
        history: int | None = None,
    ) -> tuple[str, str] | None:
        """Returns the last code block in the log, if any.

        If `role` set, only check that role.
        If `history` set, only check n messages back.
        """
        msgs = self.log
        if role:
            msgs = [msg for msg in msgs if msg.role == role]
        if history:
            msgs = msgs[-history:]

        for msg in msgs[::-1]:
            codeblocks = msg.get_codeblocks()
            if codeblocks:
                return codeblocks[-1]
        return None

    def branch(self, name: str) -> None:
        """Switches to a branch."""
        self.write()
        if name not in self._branches:
            logger.info(f"Creating a new branch '{name}'")
            self._branches[name] = copy(self.log)
        self.current_branch = name

    def diff(self, branch: str) -> str | None:
        """Prints the diff between the current branch and another branch."""
        if branch not in self._branches:
            logger.warning(f"Branch '{branch}' does not exist.")
            return None

        # walk the log forwards until we find a message that is different
        diff_i: int | None = None
        for i, (msg1, msg2) in enumerate(zip_longest(self.log, self._branches[branch])):
            diff_i = i
            if msg1 != msg2:
                break
        else:
            # no difference
            return None

        # output the continuing messages on the current branch as +
        # and the continuing messages on the other branch as -
        diff = []
        for msg in self.log[diff_i:]:
            diff.append(f"+ {msg.format()}")
        for msg in self._branches[branch][diff_i:]:
            diff.append(f"- {msg.format()}")

        if diff:
            return "\n".join(diff)
        else:
            return None

    def rename(self, name: str, keep_date=False) -> None:
        """
        Rename the conversation.
        Renames the folder containing the conversation and its branches.

        If keep_date is True, we will keep the date part of conversation folder name ("2021-08-01-some-name")
        If you want to keep the old log, use fork()
        """
        if keep_date:
            name = f"{self.logfile.parent.name[:10]}-{name}"

        logsdir = get_logs_dir()
        new_logdir = logsdir / name
        if new_logdir.exists():
            raise FileExistsError(f"Conversation {name} already exists.")
        self.name = name
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.logdir.rename(logsdir / self.name)
        self.logdir = logsdir / self.name

    def fork(self, name: str) -> None:
        """
        Copy the conversation folder to a new name.
        """
        self.write()
        logsdir = get_logs_dir()
        shutil.copytree(self.logfile.parent, logsdir / name)
        self.logdir = logsdir / name
        self.write()

    def to_dict(self, branches=False) -> dict:
        """Returns a dict representation of the log."""
        d: dict[str, Any] = {
            "log": [msg.to_dict() for msg in self.log],
            "logfile": str(self.logfile),
        }
        if branches:
            d["branches"] = {
                branch: [msg.to_dict() for msg in msgs]
                for branch, msgs in self._branches.items()
            }
        return d


def _conversations() -> list[Path]:
    # NOTE: only returns the main conversation, not branches (to avoid duplicates)
    logsdir = get_logs_dir()
    return list(
        sorted(logsdir.glob("*/conversation.jsonl"), key=lambda f: f.stat().st_mtime)
    )


def get_conversations() -> Generator[dict, None, None]:
    for conv_fn in _conversations():
        with open(conv_fn) as file:
            msgs = [Message(**json.loads(line)) for line in file.readlines()]
        modified = conv_fn.stat().st_mtime
        first_timestamp = msgs[0].timestamp.timestamp() if msgs else modified
        yield {
            "name": f"{conv_fn.parent.name}",
            "path": str(conv_fn),
            "created": first_timestamp,
            "modified": modified,
            "messages": len(msgs),
            "branches": 1 + len(list(conv_fn.parent.glob("branches/*.jsonl"))),
        }
