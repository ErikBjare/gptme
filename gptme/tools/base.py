import logging
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from textwrap import indent
from typing import Literal, Protocol, TypeAlias

from lxml import etree

from ..codeblock import Codeblock
from ..message import Message
from ..util import transform_examples_to_chat_directives

logger = logging.getLogger(__name__)

InitFunc: TypeAlias = Callable[[], "ToolSpec"]

# tooluse format mode
# TODO: make configurable
mode: Literal["markdown", "xml"] = "markdown"
exclusive_mode = False


ConfirmFunc = Callable[[str], bool]


class ExecuteFunc(Protocol):
    def __call__(
        self, code: str, args: list[str], confirm: ConfirmFunc
    ) -> Generator[Message, None, None]: ...


@dataclass(frozen=True, eq=False)
class ToolSpec:
    """
    Tool specification. Defines a tool that can be used by the agent.

    Args:
        name: The name of the tool.
        desc: A description of the tool.
        instructions: Instructions on how to use the tool.
        examples: Example usage of the tool.
        functions: Functions registered in the IPython REPL.
        init: An optional function that is called when the tool is first loaded.
        execute: An optional function that is called when the tool executes a block.
        block_types: A list of block types that the tool will execute.
        available: Whether the tool is available for use.
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

    def get_doc(self, doc: str | None = None) -> str:
        """Returns an updated docstring with examples."""
        if not doc:
            doc = ""
        else:
            doc += "\n\n"
        if self.instructions:
            doc += f"""
.. rubric:: Instructions

.. code-block:: markdown

{indent(self.instructions, "    ")}\n\n"""
        if self.examples:
            doc += f"""
.. rubric:: Examples

{transform_examples_to_chat_directives(self.examples)}\n\n
"""
        # doc += """.. rubric:: Members"""
        return doc.strip()

    def __eq__(self, other):
        if not isinstance(other, ToolSpec):
            return False
        return self.name == other.name


@dataclass(frozen=True)
class ToolUse:
    tool: str
    args: list[str]
    content: str
    start: int | None = None

    def execute(self, confirm: ConfirmFunc) -> Generator[Message, None, None]:
        """Executes a tool-use tag and returns the output."""
        # noreorder
        from . import get_tool  # fmt: skip

        tool = get_tool(self.tool)
        if tool and tool.execute:
            try:
                yield from tool.execute(self.content, self.args, confirm)
            except Exception as e:
                # if we are testing, raise the exception
                if "pytest" in globals():
                    raise e
                yield Message("system", f"Error executing tool '{self.tool}': {e}")
        else:
            logger.warning(f"Tool '{self.tool}' is not available for execution.")

    @property
    def is_runnable(self) -> bool:
        # noreorder
        from . import get_tool  # fmt: skip

        tool = get_tool(self.tool)
        return bool(tool.execute) if tool else False

    @classmethod
    def _from_codeblock(cls, codeblock: Codeblock) -> "ToolUse | None":
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
            return ToolUse(tool.name, args, codeblock.content, start=codeblock.start)
        else:
            # no_op_langs = ["csv", "json", "html", "xml", "stdout", "stderr", "result"]
            # if codeblock.lang and codeblock.lang not in no_op_langs:
            #     logger.warning(
            #         f"Unknown codeblock type '{codeblock.lang}', neither supported language or filename."
            #     )
            return None

    @classmethod
    def iter_from_content(cls, content: str) -> Generator["ToolUse", None, None]:
        """Returns all ToolUse in a message, markdown or XML, in order."""
        # collect all tool uses
        tool_uses = []
        if mode == "xml" or not exclusive_mode:
            for tool_use in cls._iter_from_xml(content):
                tool_uses.append(tool_use)
        if mode == "markdown" or not exclusive_mode:
            for tool_use in cls._iter_from_markdown(content):
                tool_uses.append(tool_use)

        # return them in the order they appear
        assert all(x.start is not None for x in tool_uses)
        tool_uses.sort(key=lambda x: x.start or 0)
        for tool_use in tool_uses:
            yield tool_use

    @classmethod
    def _iter_from_markdown(cls, content: str) -> Generator["ToolUse", None, None]:
        """Returns all markdown-style ToolUse in a message.

        Example:
          ```ipython
          print("Hello, world!")
          ```
        """
        for codeblock in Codeblock.iter_from_markdown(content):
            if tool_use := cls._from_codeblock(codeblock):
                yield tool_use

    @classmethod
    def _iter_from_xml(cls, content: str) -> Generator["ToolUse", None, None]:
        """Returns all XML-style ToolUse in a message.

        Example:
          <tool-use>
          <ipython>
          print("Hello, world!")
          </ipython>
          </tool-use>
        """
        if "<tool-use>" not in content:
            return
        if "</tool-use>" not in content:
            return

        try:
            # Parse the content as HTML to be more lenient with malformed XML
            parser = etree.HTMLParser()
            tree = etree.fromstring(content, parser)

            for tooluse in tree.xpath("//tool-use"):
                for child in tooluse.getchildren():
                    tool_name = child.tag
                    args = list(child.attrib.values())
                    tool_content = (child.text or "").strip()

                    # Find the start position of the tool in the original content
                    start_pos = content.find(f"<{tool_name}")

                    yield ToolUse(
                        tool_name,
                        args,
                        tool_content,
                        start=start_pos,
                    )
        except etree.ParseError as e:
            logger.warning(f"Failed to parse XML content: {e}")
            return

    def to_output(self) -> str:
        if mode == "markdown":
            return self._to_markdown()
        elif mode == "xml":
            return self._to_xml()

    def _to_markdown(self) -> str:
        args = " ".join(self.args)
        return f"```{self.tool} {args}\n{self.content}\n```"

    def _to_xml(self) -> str:
        args = " ".join(self.args)
        args_str = "" if not args else f" args='{args}'"
        return f"<tool-use>\n<{self.tool}{args_str}>\n{self.content}\n</{self.tool}>\n</tool-use>"
