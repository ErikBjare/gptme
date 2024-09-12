import logging
from collections.abc import Callable, Generator

from ..codeblock import Codeblock
from ..message import Message
from .base import ToolSpec, ToolUse
from .browser import tool as browser_tool
from .chats import tool as chats_tool
from .gh import tool as gh_tool
from .patch import tool as patch_tool
from .python import get_tool as get_python_tool
from .python import register_function
from .read import tool as tool_read
from .save import tool_append, tool_save
from .shell import tool as shell_tool
from .subagent import tool as subagent_tool
from .tmux import tool as tmux_tool
from .youtube import tool as youtube_tool

logger = logging.getLogger(__name__)


__all__ = [
    "execute_codeblock",
    "ToolSpec",
    "ToolUse",
    "all_tools",
]

all_tools: list[ToolSpec | Callable[[], ToolSpec]] = [
    tool_read,
    tool_save,
    tool_append,
    patch_tool,
    shell_tool,
    subagent_tool,
    tmux_tool,
    browser_tool,
    gh_tool,
    chats_tool,
    youtube_tool,
    # python tool is loaded last to ensure all functions are registered
    get_python_tool,
]
loaded_tools: list[ToolSpec] = []


def init_tools() -> None:
    """Runs initialization logic for tools."""
    for tool in all_tools:
        if not isinstance(tool, ToolSpec):
            tool = tool()
        if not tool.available:
            continue
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
    for codeblock in Codeblock.iter_from_markdown(msg.content):
        try:
            yield from execute_codeblock(codeblock, ask)
        except Exception as e:
            logger.exception(e)
            yield Message(
                "system",
                content=f"An error occurred: {e}",
            )
            break

    # TODO: execute them in order with codeblocks
    for tooluse in ToolUse.iter_from_xml(msg.content):
        yield from tooluse.execute(ask)


def execute_codeblock(
    codeblock: Codeblock, ask: bool
) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    ToolUse.from_codeblock(codeblock)
    if tool := get_tool_for_langtag(codeblock.lang):
        if tool.execute:
            args = codeblock.lang.split(" ")[1:]
            yield from tool.execute(codeblock.content, ask, args)
    elif codeblock.lang:
        logger.info(f"Codeblock not supported: {codeblock.lang}")


def get_tool_for_langtag(lang: str) -> ToolSpec | None:
    block_type = lang.split(" ")[0]
    for tool in loaded_tools:
        if block_type in tool.block_types:
            return tool
    is_filename = "." in lang or "/" in lang
    if is_filename:
        # NOTE: special case
        return tool_save
    return None


def is_supported_langtag(lang: str) -> bool:
    return bool(get_tool_for_langtag(lang))


def get_tool(tool_name: str) -> ToolSpec:
    """Returns a tool by name."""
    for tool in loaded_tools:
        if tool.name == tool_name:
            return tool
    raise ValueError(f"Tool '{tool_name}' not found")


def has_tool(tool_name: str) -> bool:
    for tool in loaded_tools:
        if tool.name == tool_name:
            return True
    return False
