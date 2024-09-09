from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeAlias

from ..message import Message
from ..util import transform_examples_to_chat_directives

InitFunc: TypeAlias = Callable[[], Any]


class ExecuteFunc(Protocol):
    def __call__(
        self, code: str, ask: bool, args: list[str]
    ) -> Generator[Message, None, None]: ...


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

    def get_doc(self, _doc="") -> str:
        """Returns a string about the tool to be appended to the __doc__ string of the module."""
        if _doc:
            _doc += "\n\n"
        if self.examples:
            _doc += f"\n\n# Examples\n\n{transform_examples_to_chat_directives(self.examples)}"
        return _doc
