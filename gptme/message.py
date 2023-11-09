import io
import shutil
import sys
import textwrap
from datetime import datetime
from typing import Literal

import tomlkit
from rich import print
from rich.console import Console
from rich.syntax import Syntax
from typing_extensions import Self

from .constants import ROLE_COLOR


class Message:
    """A message in the assistant conversation."""

    def __init__(
        self,
        role: Literal["system", "user", "assistant"],
        content: str,
        pinned: bool = False,
        hide: bool = False,
        quiet: bool = False,
        timestamp: datetime | str | None = None,
    ):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content.strip()
        if isinstance(timestamp, str):
            self.timestamp = datetime.fromisoformat(timestamp)
        else:
            self.timestamp = timestamp or datetime.now()

        # Wether this message should be pinned to the top of the chat, and never context-trimmed.
        self.pinned = pinned
        # Wether this message should be hidden from the chat output (but still be sent to the assistant)
        self.hide = hide
        # Wether this message should be printed on execution (will still print on resume, unlike hide)
        # This is not persisted to the log file.
        self.quiet = quiet

    def __repr__(self):
        content = textwrap.shorten(self.content, 20, placeholder="...")
        return f"<Message role={self.role} content={content}>"

    def __eq__(self, other):
        # FIXME: really include timestamp?
        if not isinstance(other, Message):
            return False
        return (
            self.role == other.role
            and self.content == other.content
            and self.timestamp == other.timestamp
        )

    def to_dict(self, keys=None):
        """Return a dict representation of the message, serializable to JSON."""
        d = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if keys:
            return {k: d[k] for k in keys}
        return d

    def format(self, oneline: bool = False, highlight: bool = False) -> str:
        return format_msgs([self], oneline=oneline, highlight=highlight)[0]

    def to_toml(self) -> str:
        """Converts a message to a TOML string, for easy editing by hand in editor to then be parsed back."""
        flags = []
        if self.pinned:
            flags.append("pinned")
        if self.hide:
            flags.append("hide")
        flags_toml = "\n".join(f"{flag} = true" for flag in flags)

        # doublequotes need to be escaped
        content = self.content.replace('"', '\\"')
        return f'''[message]
role = "{self.role}"
content = """
{content}
"""
timestamp = "{self.timestamp.isoformat()}"
{flags_toml}
'''

    @classmethod
    def from_toml(cls, toml: str) -> Self:
        """
        Converts a TOML string to a message.

        The string can be a single [[message]].
        """

        t = tomlkit.parse(toml)
        assert "message" in t and isinstance(t["message"], dict)
        msg: dict = t["message"]  # type: ignore

        return cls(
            msg["role"],
            msg["content"],
            pinned=msg.get("pinned", False),
            hide=msg.get("hide", False),
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )

    def get_codeblocks(self, content=False) -> list[str]:
        """
        Get all codeblocks.
        If `content` set, return the content of the code block, else return the whole message.
        """
        codeblocks = []
        content_str = self.content
        # prepend newline to make sure we get the first codeblock
        if not content_str.startswith("\n"):
            content_str = "\n" + content_str

        # check if message contains a code block
        backtick_count = content_str.count("\n```")
        if backtick_count < 2:
            return []
        for i in range(1, backtick_count, 2):
            codeblock_str = content_str.split("\n```")[i]
            # get codeblock language or filename from first line
            lang_or_fn = codeblock_str.split("\n")[0]
            codeblock_str = "\n".join(codeblock_str.split("\n")[1:])

            if content:
                codeblocks.append(codeblock_str)
            else:
                full_codeblock = f"```{lang_or_fn}\n{codeblock_str}\n```"
                codeblocks.append(full_codeblock)

        return codeblocks


def format_msgs(
    msgs: list[Message],
    oneline: bool = False,
    highlight: bool = False,
    indent: int = 0,
) -> list[str]:
    """Formats messages for printing to the console."""
    outputs = []
    for msg in msgs:
        userprefix = msg.role.capitalize()
        if highlight:
            color = ROLE_COLOR[msg.role]
            userprefix = f"[bold {color}]{userprefix}[/bold {color}]"
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
            output += "\n" + indent * " " if multiline else ""
            for i, block in enumerate(msg.content.split("```")):
                if i % 2 == 0:
                    output += textwrap.indent(block, prefix=indent * " ")
                    continue
                elif highlight:
                    lang = block.split("\n")[0]
                    console = Console(
                        file=io.StringIO(), width=shutil.get_terminal_size().columns
                    )
                    console.print(Syntax(block.rstrip(), lang))
                    block = console.file.getvalue()  # type: ignore
                output += f"```{block.rstrip()}\n```"
        outputs.append(f"{userprefix}: {output.rstrip()}")
    return outputs


def print_msg(
    msg: Message | list[Message],
    oneline: bool = False,
    highlight: bool = True,
    show_hidden: bool = False,
) -> None:
    """Prints the log to the console."""
    # if not tty, force highlight=False (for tests and such)
    if not sys.stdout.isatty():
        highlight = False

    msgs = msg if isinstance(msg, list) else [msg]
    msgstrs = format_msgs(msgs, highlight=highlight, oneline=oneline)
    skipped_hidden = 0
    for m, s in zip(msgs, msgstrs):
        if m.hide and not show_hidden:
            skipped_hidden += 1
            continue
        print(s)
    if skipped_hidden:
        print(
            f"[grey30]Skipped {skipped_hidden} hidden system messages, show with --show-hidden[/]"
        )


def msgs_to_toml(msgs: list[Message]) -> str:
    """Converts a list of messages to a TOML string, for easy editing by hand in editor to then be parsed back."""
    t = ""
    for msg in msgs:
        t += msg.to_toml().replace("[message]", "[[messages]]") + "\n\n"

    return t


def toml_to_msgs(toml: str) -> list[Message]:
    """
    Converts a TOML string to a list of messages.

    The string can be a whole file with multiple [[messages]].
    """
    t = tomlkit.parse(toml)
    assert "messages" in t and isinstance(t["messages"], list)
    msgs: list[dict] = t["messages"]  # type: ignore

    return [
        Message(
            msg["role"],
            msg["content"],
            pinned=msg.get("pinned", False),
            hide=msg.get("hide", False),
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )
        for msg in msgs
    ]
