import logging
from collections.abc import Generator
from functools import lru_cache

from ..message import Message
from .base import (
    ConfirmFunc,
    ToolFormat,
    ToolSpec,
    ToolUse,
    get_tool_format,
    set_tool_format,
)
from .browser import tool as browser_tool
from .chats import tool as chats_tool
from .computer import tool as computer_tool
from .gh import tool as gh_tool
from .patch import tool as patch_tool
from .python import register_function
from .python import tool as python_tool
from .rag import tool as rag_tool
from .read import tool as read_tool
from .save import tool_append, tool_save
from .screenshot import tool as screenshot_tool
from .shell import tool as shell_tool
from .subagent import tool as subagent_tool
from .tmux import tool as tmux_tool
from .vision import tool as vision_tool
from .youtube import tool as youtube_tool

logger = logging.getLogger(__name__)


__all__ = [
    # types
    "ToolSpec",
    "ToolUse",
    "ToolFormat",
    # functions
    "execute_msg",
    "get_tool_format",
    "set_tool_format",
    # files
    "read_tool",
    "tool_append",
    "tool_save",
    "patch_tool",
    # code
    "shell_tool",
    "python_tool",
    "gh_tool",
    # vision and computer use
    "vision_tool",
    "screenshot_tool",
    "computer_tool",
    # misc
    "chats_tool",
    "rag_tool",
    "subagent_tool",
    "tmux_tool",
    "browser_tool",
    "youtube_tool",
]

loaded_tools: list[ToolSpec] = []

# Tools that are disabled by default, unless explicitly enabled
# TODO: find a better way to handle this
tools_default_disabled = [
    "computer",
    "subagent",
]


@lru_cache
def init_tools(allowlist: frozenset[str] | None = None) -> None:
    """Runs initialization logic for tools."""
    # init python tool last
    tools = list(
        sorted(ToolSpec.get_tools().values(), key=lambda tool: tool.name != "python")
    )
    loaded_tool_names = [tool.name for tool in loaded_tools]
    for tool in tools:
        if tool.name in loaded_tool_names:
            continue
        if allowlist and tool.name not in allowlist:
            continue
        if tool.init:
            tool = tool.init()
        if not tool.available:
            continue
        if tool in loaded_tools:
            continue
        if tool.name in tools_default_disabled:
            if not allowlist or tool.name not in allowlist:
                continue
        _load_tool(tool)

    for tool_name in allowlist or []:
        if not has_tool(tool_name):
            raise ValueError(f"Tool '{tool_name}' not found")


def _load_tool(tool: ToolSpec) -> None:
    """Loads a tool."""
    if tool in loaded_tools:
        logger.warning(f"Tool '{tool.name}' already loaded")
        return

    # tool init happens in init_tools to check that spec is available
    if tool.functions:
        for func in tool.functions:
            register_function(func)
    loaded_tools.append(tool)


def execute_msg(msg: Message, confirm: ConfirmFunc) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    for tooluse in ToolUse.iter_from_content(msg.content):
        if tooluse.is_runnable:
            yield from tooluse.execute(confirm)


# Called often when checking streaming output for executable blocks,
# so we cache the result.
@lru_cache
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


def get_tool(tool_name: str) -> ToolSpec | None:
    """Returns a loaded tool by name or block type."""
    # check tool names
    for tool in loaded_tools:
        if tool.name == tool_name:
            return tool
    # check block types
    for tool in loaded_tools:
        if tool_name in tool.block_types:
            return tool
    return None


def has_tool(tool_name: str) -> bool:
    """Returns True if a tool is loaded."""
    for tool in loaded_tools:
        if tool.name == tool_name:
            return True
    return False
