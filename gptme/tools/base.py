from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias
from collections.abc import Generator

from ..message import Message

InitFunc: TypeAlias = Callable[[], Any]
ExecuteFunc: TypeAlias = Callable[
    [str, bool, dict[str, str]], Generator[Message, None, None]
]


@dataclass
class ToolSpec:
    """
    A dataclass to store metadata about a tool.

    Like documentation to be included in prompt, and functions to expose to the agent in the REPL.
    """

    name: str
    desc: str
    instructions: str = ""
    examples: str = ""
    functions: list[Callable] | None = None
    init: InitFunc | None = None
    execute: ExecuteFunc | None = None
