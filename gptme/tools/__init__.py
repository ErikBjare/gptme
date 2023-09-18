import logging
from typing import Generator

from ..message import Message
from .python import execute_python
from .shell import execute_shell
from .save import execute_save
from .summarize import summarize

logger = logging.getLogger(__name__)


__all__ = [
    "execute_codeblock",
    "execute_python",
    "execute_shell",
    "execute_save",
    "summarize",
]


def execute_msg(msg: Message, ask: bool) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    # get all markdown code blocks
    codeblocks = [codeblock for codeblock in msg.content.split("```")[1::2]]
    for codeblock in codeblocks:
        yield from execute_codeblock(codeblock, ask)


def execute_codeblock(codeblock: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    lang_or_fn = codeblock.splitlines()[0].strip()
    codeblock = codeblock[len(lang_or_fn) :]

    is_filename = lang_or_fn.count(".") >= 1

    if lang_or_fn in ["python", "py"]:
        yield from execute_python(codeblock, ask=ask)
    elif lang_or_fn in ["terminal", "bash", "sh"]:
        yield from execute_shell(codeblock, ask=ask)
    elif is_filename:
        yield from execute_save(lang_or_fn, codeblock, ask=ask)
    else:
        logger.warning(
            f"Unknown codeblock type '{lang_or_fn}', neither supported language or filename."
        )
