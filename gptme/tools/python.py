"""
The assistant can execute Python code blocks.

It uses IPython to do so, and persists the IPython instance between calls to give a REPL-like experience.
"""

import dataclasses
import functools
import importlib.util
import re
import types
from collections.abc import Callable, Generator
from logging import getLogger
from typing import (
    TYPE_CHECKING,
    Literal,
    TypeVar,
    get_origin,
)

from ..message import Message
from ..util import print_preview
from .base import ConfirmFunc, ToolSpec, ToolUse

if TYPE_CHECKING:
    from IPython.terminal.embed import InteractiveShellEmbed  # fmt: skip


logger = getLogger(__name__)

# TODO: launch the IPython session in the current venv, if any, instead of the pipx-managed gptme venv (for example) in which gptme itself runs
#       would let us use libraries installed with `pip install` in the current venv
#       https://github.com/ErikBjare/gptme/issues/29

# IPython instance
_ipython: "InteractiveShellEmbed | None" = None


registered_functions: dict[str, Callable] = {}

T = TypeVar("T", bound=Callable)


def register_function(func: T) -> T:
    """Decorator to register a function to be available in the IPython instance."""
    registered_functions[func.__name__] = func
    # if ipython is already initialized, push the function to it to make it available
    if _ipython is not None:
        _ipython.push({func.__name__: func})
    return func


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


def get_functions_prompt() -> str:
    # return a prompt with a brief description of the available functions
    return "\n".join(
        f"- {callable_signature(func)}: {func.__doc__ or 'No description'}"
        for func in registered_functions.values()
    )


def _get_ipython():
    global _ipython
    from IPython.terminal.embed import InteractiveShellEmbed  # fmt: skip

    if _ipython is None:
        _ipython = InteractiveShellEmbed()
        _ipython.push(registered_functions)

    return _ipython


def execute_python(
    code: str, args: list[str], confirm: ConfirmFunc = lambda _: True
) -> Generator[Message, None, None]:
    """Executes a python codeblock and returns the output."""
    code = code.strip()
    print_preview(code, "python")
    if not confirm("Execute this code?"):
        # early return
        yield Message("system", "Aborted, user chose not to run command.")
        return

    # Create an IPython instance if it doesn't exist yet
    _ipython = _get_ipython()

    # Capture the standard output and error streams
    from IPython.utils.capture import capture_output  # fmt: skip

    with capture_output() as captured:
        # Execute the code
        result = _ipython.run_cell(code, silent=False, store_history=False)

    output = ""
    if isinstance(result.result, types.GeneratorType):
        # if the result is a generator, we need to iterate over it
        for message in result.result:
            assert isinstance(message, Message)
            yield message
        return
    if result.result is not None:
        output += f"Result:\n```\n{result.result}\n```\n\n"
    # only show stdout if there is no result
    elif captured.stdout:
        output += f"```stdout\n{captured.stdout.rstrip()}\n```\n\n"

    if captured.stderr:
        output += f"```stderr\n{captured.stderr.rstrip()}\n```\n\n"
    if result.error_in_exec:
        tb = result.error_in_exec.__traceback__
        while tb.tb_next:  # type: ignore
            tb = tb.tb_next  # type: ignore
        # type: ignore
        output += f"Exception during execution on line {tb.tb_lineno}:\n  {result.error_in_exec.__class__.__name__}: {result.error_in_exec}"

    # strip ANSI escape sequences
    # TODO: better to signal to the terminal that we don't want colors?
    output = re.sub(r"\x1b[^m]*m", "", output)
    yield Message("system", "Executed code block.\n\n" + output)


@functools.lru_cache
def get_installed_python_libraries() -> set[str]:
    """Check if a select list of Python libraries are installed."""
    candidates = [
        "numpy",
        "pandas",
        "matplotlib",
        "seaborn",
        "scipy",
        "sklearn",
        "statsmodels",
        "PIL",
    ]
    installed = set()
    for candidate in candidates:
        if importlib.util.find_spec(candidate):
            installed.add(candidate)

    return installed


instructions = """
To execute Python code in an interactive IPython session, send a codeblock using the `ipython` language tag.
It will respond with the output and result of the execution.
If you first write the code in a normal python codeblock, remember to also execute it with the ipython codeblock.
"""


examples = f"""
#### Results of the last expression will be displayed, IPython-style:
> User: What is 2 + 2?
> Assistant:
{ToolUse("ipython", [], "2 + 2").to_output()}
> System: Executed code block.
{ToolUse("result", [], "4").to_output()}

#### It can write an example and then execute it:
> User: compute fib 10
> Assistant: To compute the 10th Fibonacci number, we write a recursive function:
{ToolUse("ipython", [], '''
def fib(n):
    ...
''').to_output()}
Now, let's execute this code to get the 10th Fibonacci number:
{ToolUse("ipython", [], '''
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
fib(10)
''').to_output()}
> System: Executed code block.
{ToolUse("result", [], "55").to_output()}
""".strip()


def init() -> ToolSpec:
    python_libraries = get_installed_python_libraries()
    python_libraries_str = "\n".join(f"- {lib}" for lib in python_libraries)

    _instructions = f"""{instructions}

The following libraries are available:
{python_libraries_str}

The following functions are available in the REPL:
{get_functions_prompt()}
    """.strip()

    # create a copy with the updated instructions
    return dataclasses.replace(tool, instructions=_instructions)


tool = ToolSpec(
    name="python",
    desc="Execute Python code",
    instructions=instructions,
    examples=examples,
    execute=execute_python,
    init=init,
    block_types=[
        # "python",
        "ipython",
        "py",
    ],
)
__doc__ = tool.get_doc(__doc__)
