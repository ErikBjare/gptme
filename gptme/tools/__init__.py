import logging
from typing import Generator

from ..message import Message
from .python import execute_python
from .shell import execute_shell
from .summarize import summarize

logger = logging.getLogger(__name__)


__all__ = [
    "execute_linecmd",
    "execute_codeblock",
    "execute_python",
    "execute_shell",
    "summarize",
]


# DEPRECATED
def execute_linecmd(line: str) -> Generator[Message, None, None]:
    """Executes a line command and returns the response."""
    if line.startswith("terminal: "):
        cmd = line[len("terminal: ") :]
        yield from execute_shell(cmd)
    elif line.startswith("python: "):
        cmd = line[len("python: ") :]
        yield from execute_python(cmd)


def execute_codeblock(codeblock: str) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    codeblock_lang = codeblock.splitlines()[0].strip()
    codeblock = codeblock[len(codeblock_lang) :]
    if codeblock_lang in ["python"]:
        yield from execute_python(codeblock)
    elif codeblock_lang in ["terminal", "bash", "sh"]:
        yield from execute_shell(codeblock)
    else:
        logger.warning(f"Unknown codeblock type {codeblock_lang}")
