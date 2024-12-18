import logging
from collections.abc import Generator
from functools import lru_cache

from gptme.config import get_config

from ..message import Message
from .base import (
    ConfirmFunc,
    ToolFormat,
    ToolSpec,
    ToolUse,
    get_tool_format,
    set_tool_format,
)

import importlib
import pkgutil
import inspect

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
]

from .save import tool_save

loaded_tools: list[ToolSpec] = []


def _discover_tools(package_names):
    """Discover tools in a package or module, given the package name as a string."""
    tools = []
    for package_name in package_names:
        try:
            # Dynamically import the package or module
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning("Module or package %s not found", package_name)
            continue

        # Check if it's a package or a module
        if hasattr(package, "__path__"):  # It's a package
            # Iterate over modules in the package
            for _, module_name, _ in pkgutil.iter_modules(package.__path__):
                full_module_name = f"{package_name}.{module_name}"
                try:
                    module = importlib.import_module(full_module_name)
                except ModuleNotFoundError:
                    logger.warning("Missing dependency for module %s", full_module_name)
                    continue

                # Find instances of ToolSpec in the module
                for _, obj in inspect.getmembers(
                    module, lambda c: isinstance(c, ToolSpec)
                ):
                    tools.append(obj)
        else:  # It's a single module
            # Find instances of ToolSpec in the module
            for _, obj in inspect.getmembers(
                package, lambda c: isinstance(c, ToolSpec)
            ):
                tools.append(obj)

    return tools


@lru_cache
def init_tools(
    allowlist: frozenset[str] | None = None, tool_modules: frozenset[str] | None = None
) -> None:
    """Runs initialization logic for tools."""

    config = get_config()
    if allowlist is None:
        env_allowlist = config.get_env("TOOL_ALLOW_LIST")
        if env_allowlist:
            allowlist = frozenset(env_allowlist.split(","))

    if tool_modules is None:
        env_tool_modules = config.get_env("TOOL_MODULES", "gptme.tools")
        if env_tool_modules:
            tool_modules = frozenset(env_tool_modules.split(","))

    tools = sorted(_discover_tools(tool_modules))
    for tool in tools:
        if tool in loaded_tools:
            logger.warning("Tool '%s' already loaded", tool.name)
            continue
        if allowlist and tool.name not in allowlist:
            continue
        if not tool.available:
            continue
        if tool.disabled_by_default:
            if not allowlist or tool.name not in allowlist:
                continue
        if tool.init:
            tool = tool.init(loaded_tools)

        loaded_tools.append(tool)

    for tool_name in allowlist or []:
        if not has_tool(tool_name):
            raise ValueError(f"Tool '{tool_name}' not found")


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
