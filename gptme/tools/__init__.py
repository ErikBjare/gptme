import logging
from collections.abc import Generator
from dataclasses import dataclass
from xml.etree import ElementTree

from ..message import Message
from .base import ToolSpec
from .browser import tool as browser_tool
from .gh import tool as gh_tool
from .patch import tool as patch_tool
from .python import execute_python, register_function
from .python import tool as python_tool
from .read import tool as tool_read
from .save import execute_save, tool_append, tool_save
from .shell import execute_shell
from .shell import tool as shell_tool
from .subagent import tool as subagent_tool
from .summarize import summarize
from .terminal import tool as terminal_tool

logger = logging.getLogger(__name__)


__all__ = [
    "execute_codeblock",
    "execute_python",
    "execute_shell",
    "execute_save",
    "summarize",
    "ToolSpec",
    "ToolUse",
    "all_tools",
]


all_tools: list[ToolSpec] = [
    tool
    for tool in [
        tool_read,
        tool_save,
        tool_append,
        patch_tool,
        python_tool,
        shell_tool,
        subagent_tool,
        terminal_tool,
        browser_tool,
        gh_tool,
    ]
    if tool.available
]
loaded_tools: list[ToolSpec] = []


@dataclass
class ToolUse:
    tool: str
    args: list[str]
    content: str

    def execute(self, ask: bool) -> Generator[Message, None, None]:
        """Executes a tool-use tag and returns the output."""
        tool = get_tool(self.tool)
        if tool.execute:
            yield from tool.execute(self.content, ask, self.args)


def init_tools() -> None:
    """Runs initialization logic for tools."""
    for tool in all_tools:
        if tool in loaded_tools:
            continue
        load_tool(tool)


def load_tool(tool: ToolSpec) -> None:
    """Loads a tool."""
    # FIXME: when are tools first initialized?
    if tool in loaded_tools:
        logger.warning(f"Tool '{tool.name}' already loaded")
        return

    if tool.init:
        tool.init()
    if tool.functions:
        for func in tool.functions:
            register_function(func)
    loaded_tools.append(tool)


def execute_msg(msg: Message, ask: bool) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    # get all markdown code blocks
    for codeblock in get_codeblocks(msg.content):
        try:
            if is_supported_codeblock(codeblock):
                yield from codeblock_to_tooluse(codeblock).execute(ask)
            else:
                logger.info(f"Codeblock not supported: {codeblock}")
        except Exception as e:
            logger.exception(e)
            yield Message(
                "system",
                content=f"An error occurred: {e}",
            )
            break

    # TODO: execute them in order with codeblocks
    for tooluse in get_tooluse_xml(msg.content):
        yield from tooluse.execute(ask)


def codeblock_to_tooluse(codeblock: str) -> ToolUse:
    """Parses a codeblock into a ToolUse. Codeblock must be a supported type."""
    lang_or_fn = codeblock.splitlines()[0].strip()
    codeblock_content = codeblock[len(lang_or_fn) :]
    if tool := get_tool_for_codeblock(lang_or_fn):
        # NOTE: special case
        args = lang_or_fn.split(" ")[1:] if tool.name != "save" else [lang_or_fn]
        return ToolUse(tool.name, args, codeblock_content)
    else:
        assert not is_supported_codeblock(codeblock)
        raise ValueError(
            f"Unknown codeblock type '{lang_or_fn}', neither supported language or filename."
        )


def execute_codeblock(codeblock: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    lang_or_fn = codeblock.splitlines()[0].strip()
    if tool := get_tool_for_codeblock(lang_or_fn):
        if tool.execute:
            args = lang_or_fn.split(" ")[1:]
            yield from tool.execute(codeblock, ask, args)
    assert not is_supported_codeblock(codeblock)
    logger.debug("Unknown codeblock, neither supported language or filename.")


# TODO: use this instead of passing around codeblocks as strings (with or without ```)
@dataclass
class Codeblock:
    lang_or_fn: str
    content: str

    @classmethod
    def from_markdown(cls, content: str) -> "Codeblock":
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        lang_or_fn = content.splitlines()[0].strip()
        return cls(lang_or_fn, content[len(lang_or_fn) :])

    @property
    def is_filename(self) -> bool:
        return "." in self.lang_or_fn or "/" in self.lang_or_fn

    @property
    def is_supported(self) -> bool:
        return is_supported_codeblock_tool(self.lang_or_fn)


def is_supported_codeblock(codeblock: str) -> bool:
    """Returns whether a codeblock is supported by tools."""
    # if the codeblock are the clean contents of a code block,
    # with a tool on the first line, without any leading or trailing whitespace or ```
    content = codeblock
    if content.startswith("```"):
        content = codeblock[3:]
        if codeblock.endswith("```"):
            content = content[:-3]
    lang_or_fn = content.splitlines()[0].strip()
    if is_supported_codeblock_tool(lang_or_fn):
        return True

    # if not, it might be a message containing a code block
    # TODO: this doesn't really make sense?
    # codeblocks = list(get_codeblocks(codeblock))
    # if codeblocks:
    #     all_supported = True
    #     for cb in codeblocks:
    #         lang_or_fn = cb.strip().splitlines()[0].strip()
    #         supported = is_supported_codeblock_tool(lang_or_fn)
    #         print(f"supported: {supported}\n{cb}")
    #         all_supported = all_supported and supported
    #     if not all_supported:
    #         return False

    if lang_or_fn not in ["json", "csv", "stdout", "stderr", "output"]:
        logger.warning(f"Unsupported codeblock type: {lang_or_fn}")
    return False


def get_tool_for_codeblock(lang_or_fn: str) -> ToolSpec | None:
    block_type = lang_or_fn.split(" ")[0]
    for tool in loaded_tools:
        if block_type in tool.block_types:
            return tool
    is_filename = "." in lang_or_fn or "/" in lang_or_fn
    if is_filename:
        # NOTE: special case
        return tool_save
    return None


def is_supported_codeblock_tool(lang_or_fn: str) -> bool:
    if get_tool_for_codeblock(lang_or_fn):
        return True
    else:
        return False


def get_codeblocks(content: str) -> Generator[str, None, None]:
    """Returns all codeblocks in a message."""
    for codeblock in ("\n" + content).split("\n```")[1::2]:
        yield codeblock + "\n"


def get_tooluse_xml(content: str) -> Generator[ToolUse, None, None]:
    """Returns all ToolUse in a message.

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
            # TODO: this child.attrib.values() thing wont really work
            yield ToolUse(tooluse.tag, list(child.attrib.values()), child.text or "")


def get_tool(tool_name: str) -> ToolSpec:
    """Returns a tool by name."""
    for tool in all_tools:
        if tool.name == tool_name:
            return tool
    raise ValueError(f"Tool '{tool_name}' not found")
