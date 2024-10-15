import json
import logging
import shutil
import textwrap
from collections.abc import Generator
from dataclasses import dataclass, field, replace
from datetime import datetime
from itertools import islice, zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, TypeAlias

from rich import print

from .dirs import get_logs_dir
from .message import Message, len_tokens, print_msg
from .prompts import get_prompt
from .reduce import limit_log, reduce_log

PathLike: TypeAlias = str | Path

logger = logging.getLogger(__name__)

RoleLiteral = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Log:
    messages: list[Message] = field(default_factory=list)

    def __getitem__(self, key):
        return self.messages[key]

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self) -> Generator[Message, None, None]:
        yield from self.messages

    def replace(self, **kwargs) -> "Log":
        return replace(self, **kwargs)

    def append(self, msg: Message) -> "Log":
        return self.replace(messages=self.messages + [msg])

    def pop(self) -> "Log":
        return self.replace(messages=self.messages[:-1])

    @classmethod
    def read_jsonl(cls, path: PathLike, limit=None) -> "Log":
        gen = _gen_read_jsonl(path)
        if limit:
            gen = islice(gen, limit)  # type: ignore
        return Log(list(gen))

    def write_jsonl(self, path: PathLike) -> None:
        with open(path, "w") as file:
            for msg in self.messages:
                file.write(json.dumps(msg.to_dict()) + "\n")

    def print(self, show_hidden: bool = False):
        print_msg(self.messages, oneline=False, show_hidden=show_hidden)


class LogManager:
    """Manages a conversation log."""

    def __init__(
        self,
        log: list[Message] | None = None,
        logdir: PathLike | None = None,
        branch: str | None = None,
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
        self._branches = {self.current_branch: Log(log or [])}
        if self.logdir / "conversation.jsonl":
            _branch = "main"
            if _branch not in self._branches:
                self._branches[_branch] = Log.read_jsonl(
                    self.logdir / "conversation.jsonl"
                )
        for file in self.logdir.glob("branches/*.jsonl"):
            if file.name == self.logdir.name:
                continue
            _branch = file.stem
            if _branch not in self._branches:
                self._branches[_branch] = Log.read_jsonl(file)

        # TODO: Check if logfile has contents, then maybe load, or should it overwrite?

    @property
    def log(self) -> Log:
        return self._branches[self.current_branch]

    @log.setter
    def log(self, value: Log | list[Message]) -> None:
        if isinstance(value, list):
            value = Log(value)
        self._branches[self.current_branch] = value

    @property
    def logfile(self) -> Path:
        if self.current_branch == "main":
            return get_logs_dir() / self.name / "conversation.jsonl"
        return self.logdir / "branches" / f"{self.current_branch}.jsonl"

    def append(self, msg: Message) -> None:
        """Appends a message to the log, writes the log, prints the message."""
        self.log = self.log.append(msg)
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
        self.log.write_jsonl(self.logfile)

        # write other branches
        # FIXME: wont write main branch if on a different branch
        if branches:
            branches_dir = self.logdir / "branches"
            branches_dir.mkdir(parents=True, exist_ok=True)
            for branch, log in self._branches.items():
                if branch == "main":
                    continue
                branch_path = branches_dir / f"{branch}.jsonl"
                log.write_jsonl(branch_path)

    def _save_backup_branch(self, type="edit") -> None:
        """backup the current log to a new branch, usually before editing/undoing"""
        branch_prefix = f"{self.current_branch}-{type}-"
        n = len([b for b in self._branches.keys() if b.startswith(branch_prefix)])
        self._branches[f"{branch_prefix}{n}"] = self.log
        self.write()

    def edit(self, new_log: Log | list[Message]) -> None:
        """Edits the log."""
        if isinstance(new_log, list):
            new_log = Log(new_log)
        self._save_backup_branch(type="edit")
        self.log = new_log
        self.write()

    def undo(self, n: int = 1, quiet=False) -> None:
        """Removes the last message from the log."""
        undid = self.log[-1] if self.log else None
        if undid and undid.content.startswith("/undo"):
            self.log = self.log.pop()

        # don't save backup branch if undoing a command
        if self.log and not self.log[-1].content.startswith("/"):
            self._save_backup_branch(type="undo")

        # Doesn't work for multiple undos in a row, but useful in testing
        # assert undid.content == ".undo"  # assert that the last message is an undo
        peek = self.log[-1] if self.log else None
        if not peek:
            print("[yellow]Nothing to undo.[/]")
            return

        if not quiet:
            print("[yellow]Undoing messages:[/yellow]")
        for _ in range(n):
            undid = self.log[-1]
            self.log = self.log.pop()
            if not quiet:
                print(
                    f"[red]  {undid.role}: {textwrap.shorten(undid.content.strip(), width=50, placeholder='...')}[/]",
                )
            peek = self.log[-1] if self.log else None

    @classmethod
    def load(
        cls,
        logdir: PathLike,
        initial_msgs: list[Message] | None = None,
        branch: str = "main",
        create: bool = False,
        **kwargs,
    ) -> "LogManager":
        """Loads a conversation log."""
        if str(logdir).endswith(".jsonl"):
            logdir = Path(logdir).parent

        logsdir = get_logs_dir()
        if str(logsdir) not in str(logdir):
            # if the path was not fully specified, assume its a dir in logsdir
            logdir = logsdir / logdir
        else:
            logdir = Path(logdir)

        if branch == "main":
            logfile = logdir / "conversation.jsonl"
        else:
            logfile = logdir / f"branches/{branch}.jsonl"

        if not Path(logfile).exists():
            if create:
                logger.debug(f"Creating new logfile {logfile}")
                Path(logfile).parent.mkdir(parents=True, exist_ok=True)
                Log([]).write_jsonl(logfile)
            else:
                raise FileNotFoundError(f"Could not find logfile {logfile}")

        log = Log.read_jsonl(logfile)
        msgs = log.messages or initial_msgs or [get_prompt()]
        return cls(msgs, logdir=logdir, branch=branch, **kwargs)

    def branch(self, name: str) -> None:
        """Switches to a branch."""
        self.write()
        if name not in self._branches:
            logger.info(f"Creating a new branch '{name}'")
            self._branches[name] = self.log
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


def prepare_messages(msgs: list[Message]) -> list[Message]:
    """Prepares the messages before sending to the LLM."""
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


def _conversation_files() -> list[Path]:
    # NOTE: only returns the main conversation, not branches (to avoid duplicates)
    # returns the conversation files sorted by modified time (newest first)
    logsdir = get_logs_dir()
    return list(
        sorted(logsdir.glob("*/conversation.jsonl"), key=lambda f: -f.stat().st_mtime)
    )


@dataclass(frozen=True)
class ConversationMeta:
    name: str
    path: str
    created: float
    modified: float
    messages: int
    branches: int


def get_conversations() -> Generator[ConversationMeta, None, None]:
    """Returns all conversations, excluding ones used for testing, evals, etc."""
    for conv_fn in _conversation_files():
        log = Log.read_jsonl(conv_fn, limit=1)
        # TODO: can we avoid reading the entire file? maybe wont even be used, due to user convo filtering
        len_msgs = conv_fn.read_text().count("}\n{")
        assert len(log) <= 1
        modified = conv_fn.stat().st_mtime
        first_timestamp = log[0].timestamp.timestamp() if log else modified
        yield ConversationMeta(
            name=f"{conv_fn.parent.name}",
            path=str(conv_fn),
            created=first_timestamp,
            modified=modified,
            messages=len_msgs,
            branches=1 + len(list(conv_fn.parent.glob("branches/*.jsonl"))),
        )


def get_user_conversations() -> Generator[ConversationMeta, None, None]:
    """Returns all user conversations, excluding ones used for testing, evals, etc."""
    for conv in get_conversations():
        if any(conv.name.startswith(prefix) for prefix in ["tmp", "test-"]) or any(
            substr in conv.name for substr in ["gptme-evals-"]
        ):
            continue
        yield conv


def _gen_read_jsonl(path: PathLike) -> Generator[Message, None, None]:
    with open(path) as file:
        for line in file.readlines():
            json_data = json.loads(line)
            files = [Path(f) for f in json_data.pop("files", [])]
            if "timestamp" in json_data:
                json_data["timestamp"] = datetime.fromisoformat(json_data["timestamp"])
            yield Message(**json_data, files=files)
