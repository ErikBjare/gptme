import importlib
import json
import logging
import re
import sys
import types
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import indent
from typing import (
    Any,
    Literal,
    Protocol,
    TypeAlias,
    cast,
    get_origin,
)

import json_repair
from lxml import etree

from ..codeblock import Codeblock
from ..message import Message
from ..util import clean_example, transform_examples_to_chat_directives

logger = logging.getLogger(__name__)

InitFunc: TypeAlias = Callable[[], "ToolSpec"]

ToolFormat: TypeAlias = Literal["markdown", "xml", "tool"]

# tooluse format
tool_format: ToolFormat = "markdown"
exclusive_mode = False

# Match tool name and start of JSON
toolcall_re = re.compile(r"^@(\w+):\s*({.*)", re.M | re.S)


def find_json_end(s: str, start: int) -> int | None:
    """Find the end of a JSON object by counting braces"""
    stack = []
    in_string = False
    escape = False

    for i, c in enumerate(s[start:], start):
        if escape:
            escape = False
            continue

        if c == "\\":
            escape = True
        elif c == '"' and not escape:
            in_string = not in_string
        elif not in_string:
            if c == "{":
                stack.append(c)
            elif c == "}":
                if not stack:
                    return None
                stack.pop()
                if not stack:
                    return i + 1
    return None


def extract_json(content: str, match: re.Match) -> str | None:
    """Extract complete JSON object starting from a regex match"""
    json_start = match.start(2)  # start of the JSON content
    json_end = find_json_end(content, json_start)
    if json_end is None:
        return None
    return content[json_start:json_end]


ConfirmFunc = Callable[[str], bool]


def set_tool_format(new_format: ToolFormat):
    global tool_format
    tool_format = new_format


def get_tool_format():
    return tool_format


class ExecuteFuncGen(Protocol):
    def __call__(
        self,
        code: str | None,
        args: list[str] | None,
        kwargs: dict[str, str] | None,
        confirm: ConfirmFunc,
    ) -> Generator[Message, None, None]: ...


class ExecuteFuncMsg(Protocol):
    def __call__(
        self,
        code: str | None,
        args: list[str] | None,
        kwargs: dict[str, str] | None,
        confirm: ConfirmFunc,
    ) -> Message: ...


ExecuteFunc: TypeAlias = ExecuteFuncGen | ExecuteFuncMsg


@dataclass(frozen=True)
class Parameter:
    """A wrapper for function parameters to convert them to JSON schema."""

    name: str
    type: str
    description: str | None = None
    enum: list[Any] | None = None
    required: bool = False


# TODO: there must be a better way?
def derive_type(t) -> str:
    if get_origin(t) == Literal:
        v = ", ".join(f'"{a}"' for a in t.__args__)
        return f"Literal[{v}]"
    elif get_origin(t) == types.UnionType:
        v = ", ".join(derive_type(a) for a in t.__args__)
        return f"Union[{v}]"
    else:
        return t.__name__


def callable_signature(func: Callable) -> str:
    # returns a signature f(arg1: type1, arg2: type2, ...) -> return_type
    args = ", ".join(
        f"{k}: {derive_type(v)}"
        for k, v in func.__annotations__.items()
        if k != "return"
    )
    ret_type = func.__annotations__.get("return")
    ret = f" -> {derive_type(ret_type)}" if ret_type else ""
    return f"{func.__name__}({args}){ret}"


_tools: dict[str, "ToolSpec"] = {}


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
    instructions_format: dict[str, str] = field(default_factory=dict)
    examples: str | Callable[[str], str] = ""
    functions: list[Callable] | None = None
    init: InitFunc | None = None
    execute: ExecuteFunc | None = None
    block_types: list[str] = field(default_factory=list)
    available: bool = True
    parameters: list[Parameter] = field(default_factory=list)

    def __post_init__(self):
        global _tools
        _tools[self.name] = self

    @classmethod
    def get_tool(cls, name: str) -> "ToolSpec | None":
        return _tools.get(name)

    @classmethod
    def get_tools(cls) -> dict[str, "ToolSpec"]:
        return _tools

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
        if self.get_examples():
            doc += f"""
.. rubric:: Examples

{transform_examples_to_chat_directives(self.get_examples())}\n\n
"""
        # doc += """.. rubric:: Members"""
        return doc.strip()

    def __eq__(self, other):
        if not isinstance(other, ToolSpec):
            return False
        return self.name == other.name

    def is_runnable(self):
        return bool(self.execute)

    def get_instructions(self, tool_format: ToolFormat):
        instructions = []

        if self.instructions:
            instructions.append(self.instructions)

        if tool_format in self.instructions_format:
            instructions.append(self.instructions_format[tool_format])

        if self.functions:
            instructions.append(self.get_functions_description())

        return "\n\n".join(instructions)

    def get_tool_prompt(self, examples: bool, tool_format: ToolFormat):
        prompt = ""
        prompt += f"\n\n## {self.name}"
        prompt += f"\n\n**Description:** {self.desc}" if self.desc else ""
        instructions = self.get_instructions(tool_format)
        if instructions:
            prompt += f"\n\n**Instructions:** {instructions}"
        if examples and (
            examples_content := self.get_examples(tool_format, quote=True).strip()
        ):
            prompt += f"\n\n### Examples\n\n{examples_content}"
        return prompt

    def get_examples(self, tool_format: ToolFormat = "markdown", quote=False):
        if callable(self.examples):
            examples = self.examples(tool_format)
        else:
            examples = self.examples
        # make sure headers have exactly two newlines after them
        examples = re.sub(r"\n*(\n#+.*?)\n+", r"\n\1\n\n", examples)
        return clean_example(examples, quote=quote)

    def get_functions_description(self) -> str:
        # return a prompt with a brief description of the available functions
        if self.functions:
            description = "This tool makes the following Python functions available in `ipython`:\n\n"
            return description + "\n".join(
                f"{callable_signature(func)}: {func.__doc__ or 'No description'}"
                for func in self.functions
            )
        else:
            return "None"


@dataclass(frozen=True)
class ToolUse:
    tool: str
    args: list[str] | None
    content: str | None
    kwargs: dict[str, str] | None = None
    start: int | None = None

    def execute(self, confirm: ConfirmFunc) -> Generator[Message, None, None]:
        """Executes a tool-use tag and returns the output."""
        # noreorder
        from . import get_tool  # fmt: skip

        tool = get_tool(self.tool)
        if tool and tool.execute:
            try:
                ex = tool.execute(
                    self.content,
                    self.args,
                    self.kwargs,
                    confirm,
                )
                if isinstance(ex, Generator):
                    yield from ex
                else:
                    yield ex
            except Exception as e:
                # if we are testing, raise the exception
                logger.exception(e)
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
        if tool_format == "xml" or not exclusive_mode:
            for tool_use in cls._iter_from_xml(content):
                tool_uses.append(tool_use)
        if tool_format == "markdown" or not exclusive_mode:
            for tool_use in cls._iter_from_markdown(content):
                tool_uses.append(tool_use)

        # return them in the order they appear
        assert all(x.start is not None for x in tool_uses)
        tool_uses.sort(key=lambda x: x.start or 0)
        for tool_use in tool_uses:
            yield tool_use

        # check if its a toolcall and extract valid JSON
        if match := toolcall_re.search(content):
            tool_name = match.group(1)
            if (json_str := extract_json(content, match)) is not None:
                try:
                    kwargs = json_repair.loads(json_str)
                    if not isinstance(kwargs, dict):
                        logger.debug(f"JSON repair result is not a dict: {kwargs}")
                        return
                    yield ToolUse(
                        tool_name, None, None, kwargs=cast(dict[str, str], kwargs)
                    )
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse JSON: {json_str}")

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

    def to_output(self, tool_format: ToolFormat = "markdown") -> str:
        if tool_format == "markdown":
            return self._to_markdown()
        elif tool_format == "xml":
            return self._to_xml()
        elif tool_format == "tool":
            return self._to_toolcall()

    def _to_markdown(self) -> str:
        assert self.args is not None
        args = " ".join(self.args)
        return f"```{self.tool}{' ' if args else ''}{args}\n{self.content}\n```"

    def _to_xml(self) -> str:
        assert self.args is not None
        args = " ".join(self.args)
        args_str = "" if not args else f" args='{args}'"
        return f"<tool-use>\n<{self.tool}{args_str}>\n{self.content}\n</{self.tool}>\n</tool-use>"

    def _to_params(self) -> dict:
        # noreorder
        from . import get_tool  # fmt: skip

        if self.kwargs is not None:
            return self.kwargs
        elif self.args is not None and self.content is not None:
            # match positional args with kwargs
            if tool := get_tool(self.tool):
                if self.args:
                    args = [*self.args, self.content]
                else:
                    args = [self.content]

                json_parameters: dict[str, str] = {}
                for index, param in enumerate(tool.parameters):
                    json_parameters[param.name] = args[index]

                return json_parameters
        return {}

    def _to_json(self) -> str:
        return json.dumps({"name": self.tool, "parameters": self._to_params()})

    def _to_toolcall(self) -> str:
        self._to_json()
        return f"@{self.tool}: {json.dumps(self._to_params(), indent=2)}"


def get_path(
    code: str | None, args: list[str] | None, kwargs: dict[str, str] | None
) -> Path:
    """Get the path from args/kwargs for save, append, and patch."""
    if code is not None and args is not None:
        fn = " ".join(args)
        if (
            fn.startswith("save ")
            or fn.startswith("append ")
            or fn.startswith("patch ")
        ):
            fn = fn.split(" ", 1)[1]
    elif kwargs is not None:
        fn = kwargs.get("path", "")
    else:
        raise ValueError("No filename provided")

    return Path(fn).expanduser()


# TODO: allow using via specifying .py paths with --tools flag
def load_from_file(path: Path) -> list[ToolSpec]:
    """Import a tool from a Python file and register the ToolSpec."""
    tools_before = set(ToolSpec.get_tools().keys())

    # import the python file
    script_dir = path.resolve().parent
    if script_dir not in sys.path:
        sys.path.append(str(script_dir))
    importlib.import_module(path.stem)

    tools_after = set(ToolSpec.get_tools().keys())
    tools_new = tools_after - tools_before
    print(f"Loaded tools {tools_new} from {path}")
    return [tool for tool_name in tools_new if (tool := ToolSpec.get_tool(tool_name))]
