from datetime import datetime
from typing import Literal

from rich import print
from rich.markdown import Markdown

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
    msg: Message | list[Message],
    oneline: bool = True,
    show_hidden=False,
    markdown=False,
    color=True,
    do_print=True,
) -> str:
    """Prints messages to the console."""
    lines = []
    msgs = msg if isinstance(msg, list) else [msg]

    def _print(s, markdown=False):
        lines.append(s)
        if do_print:
            if markdown:
                s = Markdown(s)
            print(s)

    skipped_hidden = 0
    for msg in msgs:
        if msg.hide and not show_hidden:
            skipped_hidden += 1
            continue
        color_role = f"bold {ROLE_COLOR[msg.role]}" if color else "clear"
        userprefix = f"[{color_role}]{msg.user}[/]"

        _print(f"\n{userprefix}:")
        multiline = len(msg.content.split("\n")) > 1
        if multiline:
            _print("\n")
        # indent 2 spaces without textwrap
        _print(
            "\n".join(["  " + line for line in msg.content.split("\n")]),
            markdown=markdown,
        )
    if skipped_hidden:
        c = "grey30" if color else "clear"
        _print(
            f"[{c}]Skipped {skipped_hidden} hidden system messages, show with --show-hidden[/]"
        )

    return "\n".join(lines)
