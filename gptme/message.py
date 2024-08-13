import base64
import io
import logging
import shutil
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import tomlkit
from rich import print
from rich.console import Console
from rich.syntax import Syntax
from tomlkit._utils import escape_string
from typing_extensions import Self

from .constants import ROLE_COLOR
from .util import extract_codeblocks, get_tokenizer

logger = logging.getLogger(__name__)


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
        files: list[Path | str] | None = None,
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
        # Files attached to the message, could e.g. be images for vision.
        self.files = (
            [Path(f) if isinstance(f, str) else f for f in files] if files else []
        )

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

    def _content_files_list(
        self, openai: bool = False, anthropic: bool = False
    ) -> list[dict[str, Any]]:
        # combines a content message with a list of files
        content: list[dict[str, Any]] = (
            self.content
            if isinstance(self.content, list)
            else [{"type": "text", "text": self.content}]
        )
        allowed_file_exts = ["jpg", "jpeg", "png", "gif"]

        for f in self.files:
            ext = f.suffix[1:]
            if ext not in allowed_file_exts:
                logger.warning("Unsupported file type: %s", ext)
                continue
            media_type = f"image/{ext}"
            content.append(
                {
                    "type": "text",
                    "text": f"![{f.name}]({f.name}):",
                }
            )
            if anthropic:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(f.read_bytes()).decode("utf-8"),
                        },
                    }
                )
            elif openai:
                # OpenAI format
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64.b64encode(f.read_bytes()).decode('utf-8')}"
                        },
                    }
                )
            else:
                # Storage/wire format (keep files in `files` list)
                # Do nothing to integrate files into the message content
                pass

        return content

    def to_dict(self, keys=None, openai=False, anthropic=False) -> dict:
        """Return a dict representation of the message, serializable to JSON."""
        content: str | list[dict[str, Any]]
        if not anthropic and not openai:
            # storage/wire format should keep the content as a string
            content = self.content
        else:
            # OpenAI format or Anthropic format should include files in the content
            content = self._content_files_list(openai=openai, anthropic=anthropic)

        d = {
            "role": self.role,
            "content": content,
            "timestamp": self.timestamp.isoformat(),
            "files": [str(f) for f in self.files],
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
        # content = self.content.replace('"', '\\"')
        content = escape_string(self.content)
        content = content.replace("\\n", "\n")

        return f'''[message]
role = "{self.role}"
content = """
{content}
"""
files = {[str(f) for f in self.files]}
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
            files=[Path(f) for f in msg.get("files", [])],
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )

    def get_codeblocks(self) -> list[tuple[str, str]]:
        """
        Get all codeblocks from the message content, as a list of tuples (lang, content).
        """
        content_str = self.content

        # prepend newline to make sure we get the first codeblock
        if not content_str.startswith("\n"):
            content_str = "\n" + content_str

        # check if message contains a code block
        backtick_count = content_str.count("\n```")
        if backtick_count < 2:
            return []

        return extract_codeblocks(content_str)


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


def msgs2dicts(msgs: list[Message], openai=False, anthropic=False) -> list[dict]:
    """Convert a list of Message objects to a list of dicts ready to pass to an LLM."""
    return [
        msg.to_dict(keys=["role", "content"], openai=openai, anthropic=anthropic)
        for msg in msgs
    ]


# TODO: remove model assumption
def len_tokens(content: str | Message | list[Message], model: str = "gpt-4") -> int:
    """Get the number of tokens in a string, message, or list of messages."""
    if isinstance(content, list):
        return sum(len_tokens(msg.content, model) for msg in content)
    if isinstance(content, Message):
        return len_tokens(content.content, model)
    return len(get_tokenizer(model).encode(content))
