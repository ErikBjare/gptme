import logging
from collections.abc import Generator
from functools import lru_cache

from ..message import Message
from .base import ConfirmFunc, ToolSpec, ToolUse
from .browser import tool as browser_tool
from .chats import tool as chats_tool
from .computer import tool as computer_tool
from .gh import tool as gh_tool
from .patch import tool as patch_tool
from .python import register_function
from .python import tool as python_tool
from .read import tool as tool_read
from .save import tool_append, tool_save
from .screenshot import tool as screenshot_tool
from .shell import tool as shell_tool
from .subagent import tool as subagent_tool
from .tmux import tool as tmux_tool
from .vision import tool as vision_tool
from .youtube import tool as youtube_tool

logger = logging.getLogger(__name__)


__all__ = [
    "ToolSpec",
    "ToolUse",
    "all_tools",
    "execute_msg",
]

all_tools: list[ToolSpec] = [
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
    screenshot_tool,
    vision_tool,
    computer_tool,
    # python tool is loaded last to ensure all functions are registered
    python_tool,
]
loaded_tools: list[ToolSpec] = []

# Tools that are disabled by default, unless explicitly enabled
# TODO: find a better way to handle this
tools_default_disabled = [
    "computer",
]


def init_tools(allowlist=None) -> None:
    """Runs initialization logic for tools."""
    for tool in all_tools:
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
        load_tool(tool)

    for tool_name in allowlist or []:
        if not has_tool(tool_name):
            raise ValueError(f"Tool '{tool_name}' not found")


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


def execute_msg(msg: Message, confirm: ConfirmFunc) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    for tooluse in ToolUse.iter_from_content(msg.content):
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
    """Returns a tool by name."""
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
    for tool in loaded_tools:
        if tool.name == tool_name:
            return True
    return False
