import logging
from typing import Generator

from ..message import Message
from .python import execute_python
from .shell import execute_shell
from .summarize import summarize

logger = logging.getLogger(__name__)


__all__ = [
    "execute_codeblock",
    "execute_python",
    "execute_shell",
    "summarize",
]


def execute_msg(msg: Message, ask: bool) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    # get all markdown code blocks
    # we support blocks beginning with ```python and ```bash
    codeblocks = [codeblock for codeblock in msg.content.split("```")[1::2]]
    for codeblock in codeblocks:
        yield from execute_codeblock(codeblock, ask)


def execute_codeblock(codeblock: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    codeblock_lang = codeblock.splitlines()[0].strip()
    codeblock = codeblock[len(codeblock_lang) :]
    if codeblock_lang in ["python"]:
        yield from execute_python(codeblock, ask=ask)
    elif codeblock_lang in ["terminal", "bash", "sh"]:
        yield from execute_shell(codeblock, ask=ask)
    else:
        logger.warning(f"Unknown codeblock type {codeblock_lang}")
