from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeAlias

from ..message import Message

InitFunc: TypeAlias = Callable[[], Any]


class ExecuteFunc(Protocol):
    def __call__(
        self, code: str, ask: bool, args: list[str]
    ) -> Generator[Message, None, None]:
        ...


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
    block_types: list[str] = field(default_factory=list)
    available: bool = True
