import base64
import dataclasses
import logging
import shutil
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import tomlkit
from rich.syntax import Syntax
from tomlkit._utils import escape_string
from typing_extensions import Self

from .codeblock import Codeblock
from .constants import ROLE_COLOR
from .models import Provider
from .util import console, get_tokenizer, rich_to_str

logger = logging.getLogger(__name__)

# max tokens allowed in a single system message
# if you hit this limit, you and/or I f-ed up, and should make the message shorter
# maybe we should make it possible to store long outputs in files, and link/summarize it/preview it in the message
max_system_len = 20000


ProvidersWithFiles: list[Provider] = ["openai", "anthropic", "openrouter"]


@dataclass(frozen=True, eq=False)
class Message:
    """
    A message in the assistant conversation.

    Attributes:
        role: The role of the message sender (system, user, or assistant).
        content: The content of the message.
        pinned: Whether this message should be pinned to the top of the chat, and never context-trimmed.
        hide: Whether this message should be hidden from the chat output (but still be sent to the assistant).
        quiet: Whether this message should be printed on execution (will still print on resume, unlike hide).
               This is not persisted to the log file.
        timestamp: The timestamp of the message.
        files: Files attached to the message, could e.g. be images for vision.
    """

    role: Literal["system", "user", "assistant"]
    content: str
    pinned: bool = False
    hide: bool = False
    quiet: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    files: list[Path] = field(default_factory=list)

    def __post_init__(self):
        assert isinstance(self.timestamp, datetime)
        if self.role == "system":
            if (length := len_tokens(self)) >= max_system_len:
                logger.warning(f"System message too long: {length} tokens")

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

    def replace(self, **kwargs) -> Self:
        """Replace attributes of the message."""
        return dataclasses.replace(self, **kwargs)

    def _content_files_list(
        self,
        provider: Provider,
    ) -> list[dict[str, Any]]:
        # only these providers support files in the content
        if provider not in ProvidersWithFiles:
            raise ValueError("Provider does not support files in the content")

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
            if ext == "jpg":
                ext = "jpeg"
            media_type = f"image/{ext}"
            content.append(
                {
                    "type": "text",
                    "text": f"![{f.name}]({f.name}):",
                }
            )

            # read file
            data_bytes = f.read_bytes()
            data = base64.b64encode(data_bytes).decode("utf-8")

            # check that the file is not too large
            # anthropic limit is 5MB, seems to measure the base64-encoded size instead of raw bytes
            # TODO: use compression to reduce file size
            # print(f"{len(data)=}")
            if len(data) > 5_000_000:
                content.append(
                    {
                        "type": "text",
                        "text": "Image size exceeds 5MB. Please upload a smaller image.",
                    }
                )
                continue

            if provider == "anthropic":
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    }
                )
            elif provider == "openai":
                # OpenAI format
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{data}"},
                    }
                )
            else:
                # Storage/wire format (keep files in `files` list)
                # Do nothing to integrate files into the message content
                pass

        return content

    def to_dict(self, keys=None, provider: Provider | None = None) -> dict:
        """Return a dict representation of the message, serializable to JSON."""
        content: str | list[dict[str, Any]]
        if provider in ProvidersWithFiles:
            # OpenAI/Anthropic format should include files in the content
            # Some otherwise OpenAI-compatible providers (groq, deepseek?) do not support this
            content = self._content_files_list(provider)
        else:
            # storage/wire format should keep the content as a string
            content = self.content

        d: dict = {
            "role": self.role,
            "content": content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.files:
            d["files"] = [str(f) for f in self.files]
        if self.pinned:
            d["pinned"] = True
        if self.hide:
            d["hide"] = True
        if keys:
            return {k: d[k] for k in keys}
        return d

    def to_xml(self) -> str:
        """Converts a message to an XML string."""
        attrs = f"role='{self.role}'"
        return f"<message {attrs}>\n{self.content}\n</message>"

    def format(self, oneline: bool = False, highlight: bool = False) -> str:
        return format_msgs([self], oneline=oneline, highlight=highlight)[0]

    def print(self, oneline: bool = False, highlight: bool = True) -> None:
        print_msg(self, oneline=oneline, highlight=highlight)

    def to_toml(self) -> str:
        """Converts a message to a TOML string, for easy editing by hand in editor to then be parsed back."""
        flags = []
        if self.pinned:
            flags.append("pinned")
        if self.hide:
            flags.append("hide")
        flags_toml = "\n".join(f"{flag} = true" for flag in flags)
        files_toml = f"files = {[str(f) for f in self.files]}" if self.files else ""
        extra = (flags_toml + "\n" + files_toml).strip()

        # doublequotes need to be escaped
        # content = self.content.replace('"', '\\"')
        content = escape_string(self.content)
        content = content.replace("\\n", "\n")
        content = content.strip()

        return f'''[message]
role = "{self.role}"
content = """
{content}
"""
timestamp = "{self.timestamp.isoformat()}"
{extra}
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
            msg["content"].strip(),
            pinned=msg.get("pinned", False),
            hide=msg.get("hide", False),
            files=[Path(f) for f in msg.get("files", [])],
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )

    def get_codeblocks(self) -> list[Codeblock]:
        """
        Get all codeblocks from the message content.
        """
        content_str = self.content

        # prepend newline to make sure we get the first codeblock
        if not content_str.startswith("\n"):
            content_str = "\n" + content_str

        # check if message contains a code block
        backtick_count = content_str.count("\n```")
        if backtick_count < 2:
            return []

        return Codeblock.iter_from_markdown(content_str)


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
                    block = rich_to_str(Syntax(block.rstrip(), lang))
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
        try:
            console.print(s)
        except Exception:
            # rich can throw errors, if so then print the raw message
            logger.exception("Error printing message")
            print(s)
    if skipped_hidden:
        console.print(
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
            msg["content"].strip(),
            pinned=msg.get("pinned", False),
            hide=msg.get("hide", False),
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )
        for msg in msgs
    ]


def msgs2dicts(msgs: list[Message], provider: Provider) -> list[dict]:
    """Convert a list of Message objects to a list of dicts ready to pass to an LLM."""
    return [msg.to_dict(keys=["role", "content"], provider=provider) for msg in msgs]


# TODO: remove model assumption
def len_tokens(content: str | Message | list[Message], model: str = "gpt-4") -> int:
    """Get the number of tokens in a string, message, or list of messages."""
    if isinstance(content, list):
        return sum(len_tokens(msg.content, model) for msg in content)
    if isinstance(content, Message):
        return len_tokens(content.content, model)
    return len(get_tokenizer(model).encode(content))
