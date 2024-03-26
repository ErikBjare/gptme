import logging
from collections.abc import Generator
from dataclasses import dataclass
from xml.etree import ElementTree

from ..message import Message
from .base import ToolSpec
from .browser import tool as browser_tool
from .patch import execute_patch
from .python import execute_python
from .python import tool as python_tool
from .save import execute_save
from .save import tool as save_tool
from .shell import execute_shell
from .shell import tool as shell_tool
from .subagent import tool as subagent_tool
from .summarize import summarize

logger = logging.getLogger(__name__)


__all__ = [
    "execute_codeblock",
    "execute_python",
    "execute_shell",
    "execute_save",
    "summarize",
    "ToolSpec",
]


# TODO: init as empty list and add tools after they are initialized?
all_tools: list[ToolSpec] = [
    save_tool,
    python_tool,
    shell_tool,
    browser_tool,
    subagent_tool,
]
loaded_tools: list[ToolSpec] = []


@dataclass
class ToolUse:
    tool: str
    args: dict[str, str]
    content: str


def init_tools() -> None:
    """Runs initialization logic for tools."""
    for tool in all_tools:
        load_tool(tool)


def load_tool(tool: ToolSpec) -> None:
    """Loads a tool."""
    if tool not in loaded_tools:
        # FIXME: when are tools first initialized? do we need to store if they have been initialized?
        if tool.init:
            tool.init()
        loaded_tools.append(tool)
    else:
        logger.warning(f"Tool '{tool.name}' already loaded")


def execute_msg(msg: Message, ask: bool) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    # get all markdown code blocks
    for codeblock in get_codeblocks(msg.content):
        try:
            # yield from execute_codeblock(codeblock, ask)
            yield from execute_tooluse(codeblock_to_tooluse(codeblock), ask)
        except Exception as e:
            logger.exception(e)
            yield Message(
                "system",
                content=f"An error occurred: {e}",
            )
            break

    # TODO: execute them in order with codeblocks
    for tooluse in get_tooluse_xml(msg.content):
        if tooluse.tool in [t.name for t in all_tools]:
            yield from execute_tooluse(tooluse, ask)


def codeblock_to_tooluse(codeblock: str) -> ToolUse:
    """Parses a codeblock into a ToolUse"""
    lang_or_fn = codeblock.splitlines()[0].strip()
    codeblock_content = codeblock[len(lang_or_fn) :]

    # the first word is the command, the rest are arguments
    # if the first word contains a dot or slash, it is a filename
    cmd = lang_or_fn.split(" ")[0]
    is_filename = "." in cmd or "/" in cmd

    if lang_or_fn in ["python", "py"]:
        return ToolUse("python", {}, codeblock_content)
    elif lang_or_fn in ["bash", "sh"]:
        return ToolUse("shell", {}, codeblock_content)
    elif lang_or_fn.startswith("patch "):
        fn = lang_or_fn[len("patch ") :]
        return ToolUse("patch", {"file": fn}, codeblock_content)
    elif lang_or_fn.startswith("append "):
        fn = lang_or_fn[len("append ") :]
        return ToolUse("save", {"file": fn, "append": "true"}, codeblock_content)
    elif is_filename:
        return ToolUse("save", {"file": lang_or_fn}, codeblock_content)
    else:
        raise ValueError(f"Unknown codeblock type '{lang_or_fn}'")


def execute_codeblock(codeblock: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    lang_or_fn = codeblock.splitlines()[0].strip()
    codeblock_content = codeblock[len(lang_or_fn) :]

    # the first word is the command, the rest are arguments
    # if the first word contains a dot or slash, it is a filename
    cmd = lang_or_fn.split(" ")[0]
    is_filename = "." in cmd or "/" in cmd

    if lang_or_fn in ["python", "py"]:
        yield from execute_python(codeblock_content, ask=ask)
    elif lang_or_fn in ["bash", "sh"]:
        yield from execute_shell(codeblock_content, ask=ask)
    elif lang_or_fn.startswith("patch "):
        fn = lang_or_fn[len("patch ") :]
        yield from execute_patch(f"```{codeblock}```", ask, {"file": fn})
    elif lang_or_fn.startswith("append "):
        fn = lang_or_fn[len("append ") :]
        yield from execute_save(
            codeblock_content, ask, args={"file": fn, "append": "true"}
        )
    elif is_filename:
        yield from execute_save(codeblock_content, ask, args={"file": lang_or_fn})
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


def get_codeblocks(content: str) -> Generator[str, None, None]:
    """Returns all codeblocks in a message."""
    for codeblock in ("\n" + content).split("\n```")[1::2]:
        yield codeblock + "\n"


def get_tooluse_xml(content: str) -> Generator[ToolUse, None, None]:
    """Returns all tool-use tags in a message.

    Example:
      <tool-use>
      <python>
      print("Hello, world!")
      </python>
      </tool-use>
    """
    if "<tool-use>" not in content:
        return

    # TODO: this requires a strict format, should be more lenient
    root = ElementTree.fromstring(content)
    for tooluse in root.findall("tool-use"):
        for child in tooluse:
            yield ToolUse(tooluse.tag, child.attrib, child.text or "")


def get_tool(tool_name: str) -> ToolSpec:
    """Returns a tool by name."""
    for tool in all_tools:
        if tool.name == tool_name:
            return tool
    raise ValueError(f"Tool '{tool_name}' not found")


def execute_tooluse(tooluse: ToolUse, ask: bool) -> Generator[Message, None, None]:
    """Executes a tool-use tag and returns the output."""
    tool = get_tool(tooluse.tool)
    if tool.execute:
        tooluse.args.copy()
        yield from tool.execute(tooluse.content, ask, tooluse.args)


def execute_tooluse_legacy(
    tooluse: ToolUse, ask: bool
) -> Generator[Message, None, None]:
    args = tooluse.args
    content = tooluse.content
    match tooluse.tool:
        case "python":
            yield from execute_python(content, ask=ask)
        case "shell":
            yield from execute_shell(content, ask=ask)
        case "patch":
            yield from execute_patch(content, ask, args)
        case "save":
            yield from execute_save(content, ask, args)
        case _:
            logger.debug(f"Unknown tool '{tooluse.tool}'")
