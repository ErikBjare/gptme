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

from .constants import ROLE_COLOR


class Message:
    """A message in the assistant conversation."""

    def __init__(
        self,
        role: Literal["system", "user", "assistant"],
        content: str,
        user: str | None = None,
        pinned: bool = False,
        hide: bool = False,
        quiet: bool = False,
        timestamp: datetime | None = None,
    ):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content.strip()
        self.timestamp = timestamp or datetime.now()
        if user:
            self.user = user
        else:
            role_names = {"system": "System", "user": "User", "assistant": "Assistant"}
            self.user = role_names[role]

        # Wether this message should be pinned to the top of the chat, and never context-trimmed.
        self.pinned = pinned
        # Wether this message should be hidden from the chat output (but still be sent to the assistant)
        self.hide = hide
        # Wether this message should be printed on execution (will still print on resume, unlike hide)
        self.quiet = quiet

    def to_dict(self):
        """Return a dict representation of the message, serializable to JSON."""
        return {
            "role": self.role,
            "content": self.content,
        }

    def format(self, oneline: bool = False, highlight: bool = False) -> str:
        return format_msgs([self], oneline=oneline, highlight=highlight)[0]

    def __repr__(self):
        return f"<Message role={self.role} content={self.content}>"


def format_msgs(
    msgs: list[Message],
    oneline: bool = False,
    highlight: bool = False,
    indent: int = 0,
) -> list[str]:
    """Formats messages for printing to the console. Stores the result in msg.output"""
    outputs = []
    for msg in msgs:
        color = ROLE_COLOR[msg.role]
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
            output += "\n" + indent * " " if multiline else ""
            for i, block in enumerate(msg.content.split("```")):
                if i % 2 == 0:
                    output += textwrap.indent(block, prefix=indent * " ")
                elif highlight:
                    lang = block.split("\n")[0]
                    console = Console(
                        file=io.StringIO(), width=shutil.get_terminal_size().columns
                    )
                    console.print(Syntax(block.rstrip(), lang))
                    block = console.file.getvalue()  # type: ignore
                    output += f"```{block.rstrip()}\n```"
                else:
                    output += "```" + block.rstrip() + "\n```"
        outputs.append(f"\n{userprefix}: {output.rstrip()}")
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


def msg_to_toml(msg: Message) -> str:
    """Converts a message to a TOML string, for easy editing by hand in editor to then be parsed back."""
    # TODO: escape msg.content
    flags = []
    if msg.pinned:
        flags.append("pinned")
    if msg.hide:
        flags.append("hide")
    if msg.quiet:
        flags.append("quiet")

    # doublequotes need to be escaped
    content = msg.content.replace('"', '\\"')
    return f'''[message]
role = "{msg.role}"
content = """
{content}
"""
timestamp = "{msg.timestamp.isoformat()}"
'''


def msgs_to_toml(msgs: list[Message]) -> str:
    """Converts a list of messages to a TOML string, for easy editing by hand in editor to then be parsed back."""
    t = ""
    for msg in msgs:
        t += msg_to_toml(msg).replace("[message]", "[[messages]]") + "\n\n"

    return t


def toml_to_msg(toml: str) -> Message:
    """
    Converts a TOML string to a message.

    The string can be a single [[message]].
    """

    t = tomlkit.parse(toml)
    assert "message" in t and isinstance(t["message"], dict)
    msg: dict = t["message"]  # type: ignore

    return Message(
        msg["role"],
        msg["content"],
        user=msg.get("user"),
        pinned=msg.get("pinned", False),
        hide=msg.get("hide", False),
        quiet=msg.get("quiet", False),
        timestamp=datetime.fromisoformat(msg["timestamp"]),
    )


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
            user=msg.get("user"),
            pinned=msg.get("pinned", False),
            hide=msg.get("hide", False),
            quiet=msg.get("quiet", False),
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )
        for msg in msgs
    ]


def test_toml():
    msg = Message(
        "system",
        '''Hello world!
"""Difficult to handle string"""
''',
    )
    t = msg_to_toml(msg)
    print(t)
    m = toml_to_msg(t)
    print(m)
    assert msg.content == m.content
    assert msg.role == m.role
    assert msg.timestamp.date() == m.timestamp.date()
    assert msg.timestamp.timetuple() == m.timestamp.timetuple()

    msg2 = Message("user", "Hello computer!")
    ts = msgs_to_toml([msg, msg2])
    print(ts)
    ms = toml_to_msgs(ts)
    print(ms)
    assert len(ms) == 2
    assert ms[0].role == msg.role
    assert ms[0].timestamp.timetuple() == msg.timestamp.timetuple()
    assert ms[0].content == msg.content
    assert ms[1].content == msg2.content
