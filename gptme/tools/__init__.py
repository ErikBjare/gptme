import logging
from collections.abc import Generator

from ..message import Message
from .patch import execute_patch
from .python import execute_python, init_python
from .save import execute_save
from .shell import execute_shell
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
    codeblock_content = codeblock[len(lang_or_fn) :]

    is_filename = lang_or_fn.count(".") >= 1

    if lang_or_fn in ["python", "py"]:
        yield from execute_python(codeblock_content, ask=ask)
    elif lang_or_fn in ["bash", "sh"]:
        yield from execute_shell(codeblock_content, ask=ask)
    elif lang_or_fn.startswith("patch "):
        fn = lang_or_fn[len("patch ") :]
        yield from execute_patch(f"```{codeblock}```", fn, ask=ask)
    elif lang_or_fn.startswith("append "):
        fn = lang_or_fn[len("append ") :]
        yield from execute_save(fn, codeblock_content, ask=ask, append=True)
    elif is_filename:
        yield from execute_save(lang_or_fn, codeblock_content, ask=ask)
    else:
        assert not is_supported_codeblock(codeblock)
        logger.debug(
            f"Unknown codeblock type '{lang_or_fn}', neither supported language or filename."
        )


def is_supported_codeblock(codeblock: str) -> bool:
    """Returns whether a codeblock is supported by tools."""
    # passed argument might not be a clean string, could have leading text and even leading codeblocks
    # only check the last occurring codeblock

    msg = Message("system", content=codeblock)
    codeblocks = msg.get_codeblocks()
    if not codeblocks:
        return False

    codeblock = codeblocks[-1]
    lang_or_fn = codeblock.splitlines()[0].split("```")[1].strip()
    is_filename = "." in lang_or_fn or "/" in lang_or_fn

    if lang_or_fn in ["python", "py"]:
        return True
    elif lang_or_fn in ["bash", "sh"]:
        return True
    elif lang_or_fn.startswith("patch "):
        return True
    elif lang_or_fn.startswith("append "):
        return True
    elif is_filename:
        return True
    else:
        return False


def init_tools() -> None:
    """Runs initialization logic for tools."""
    init_python()
