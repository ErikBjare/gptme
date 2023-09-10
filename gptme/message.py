import io
import shutil
import sys
import textwrap
from datetime import datetime
from typing import Literal

from rich import print
from rich.console import Console
from rich.syntax import Syntax

from .constants import ROLE_COLOR


class Message:
    """A message sent to or from the AI."""

    def __init__(
        self,
        role: Literal["system", "user", "assistant"],
        content: str,
        user: str | None = None,
        pinned: bool = False,
        hide: bool = False,
    ):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content.strip()
        self.timestamp = datetime.now()
        if user:
            self.user = user
        else:
            role_names = {"system": "System", "user": "User", "assistant": "Assistant"}
            self.user = role_names[role]

        # Wether this message should be pinned to the top of the chat, and never context-trimmed.
        self.pinned = pinned
        # Wether this message should be hidden from the chat output (but still be sent to the assistant)
        self.hide = hide

    def to_dict(self):
        """Return a dict representation of the message, serializable to JSON."""
        return {
            "role": self.role,
            "content": self.content,
        }

    def __repr__(self):
        return f"<Message role={self.role} content={self.content}>"


def print_msg(
    log: Message | list[Message],
    oneline: bool = True,
    show_hidden=False,
    highlight=False,
    indent: int = 0,
) -> None:
    """Prints the log to the console."""
    # if not tty, force highlight=False (for tests and such)
    if not sys.stdout.isatty():
        highlight = False

    skipped_hidden = 0
    for msg in log if isinstance(log, list) else [log]:
        if msg.hide and not show_hidden:
            skipped_hidden += 1
            continue
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
        print(f"\n{userprefix}: {output.rstrip()}")
    if skipped_hidden:
        print(
            f"[grey30]Skipped {skipped_hidden} hidden system messages, show with --show-hidden[/]"
        )
