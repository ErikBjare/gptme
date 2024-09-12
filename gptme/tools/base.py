import logging
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import (
    Any,
    Literal,
    Protocol,
    TypeAlias,
)
from xml.etree import ElementTree

from ..codeblock import Codeblock
from ..message import Message
from ..util import transform_examples_to_chat_directives

logger = logging.getLogger(__name__)

InitFunc: TypeAlias = Callable[[], Any]

# tooluse format mode
mode: Literal["markdown", "xml"] = "markdown"


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

    def get_doc(self, doc="") -> str:
        """Returns an updated docstring with examples."""
        if doc:
            doc += "\n\n"
        if self.examples:
            doc += (
                f"# Examples\n\n{transform_examples_to_chat_directives(self.examples)}"
            )
        return doc


@dataclass
class ToolUse:
    tool: str
    args: list[str]
    content: str

    def execute(self, ask: bool) -> Generator[Message, None, None]:
        """Executes a tool-use tag and returns the output."""
        # noreorder
        from . import get_tool  # fmt: skip

        tool = get_tool(self.tool)
        if tool.execute:
            yield from tool.execute(self.content, ask, self.args)

    @classmethod
    def from_codeblock(cls, codeblock: Codeblock) -> "ToolUse | None":
        """Parses a codeblock into a ToolUse. Codeblock must be a supported type.

        Example:
          ```lang
          content
          ```
        """
        # noreorder
        from . import get_tool_for_langtag  # fmt: skip

        if tool := get_tool_for_langtag(codeblock.lang):
            # NOTE: special case
            args = (
                codeblock.lang.split(" ")[1:]
                if tool.name != "save"
                else [codeblock.lang]
            )
            return ToolUse(tool.name, args, codeblock.content)
        else:
            if codeblock.lang:
                logger.warning(
                    f"Unknown codeblock type '{codeblock.lang}', neither supported language or filename."
                )
            return None

    @classmethod
    def iter_from_xml(cls, content: str) -> Generator["ToolUse", None, None]:
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
                yield ToolUse(
                    tooluse.tag, list(child.attrib.values()), child.text or ""
                )

    def to_output(self) -> str:
        if mode == "markdown":
            return self.to_markdown()
        elif mode == "xml":
            return self.to_xml()

    def to_markdown(self) -> str:
        args = " ".join(self.args)
        return f"```{self.tool} {args}\n{self.content}\n```"

    def to_xml(self) -> str:
        args = " ".join(self.args)
        return f"<{self.tool} args='{args}'>\n{self.content}\n</{self.tool}>"
