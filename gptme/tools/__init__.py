import logging
from collections.abc import Generator
from dataclasses import dataclass
from xml.etree import ElementTree

from ..message import Message
from .base import ToolSpec
from .browser import has_browser_tool
from .browser import tool as browser_tool
from .patch import execute_patch
from .patch import tool as patch_tool
from .python import execute_python, register_function
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
    "ToolUse",
    "all_tools",
]


all_tools: list[ToolSpec] = [
    save_tool,
    patch_tool,
    python_tool,
    shell_tool,
    subagent_tool,
] + ([browser_tool] if has_browser_tool() else [])
loaded_tools: list[ToolSpec] = []


@dataclass
class ToolUse:
    tool: str
    args: dict[str, str]
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
            # yield from execute_codeblock(codeblock, ask)
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
        assert not is_supported_codeblock(codeblock)
        raise ValueError(
            f"Unknown codeblock type '{lang_or_fn}', neither supported language or filename."
        )


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

    return False


def is_supported_codeblock_tool(lang_or_fn: str) -> bool:
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
            yield ToolUse(tooluse.tag, child.attrib, child.text or "")


def get_tool(tool_name: str) -> ToolSpec:
    """Returns a tool by name."""
    for tool in all_tools:
        if tool.name == tool_name:
            return tool
    raise ValueError(f"Tool '{tool_name}' not found")
