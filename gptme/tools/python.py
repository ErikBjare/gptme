"""
The assistant can execute Python code blocks.

It uses IPython to do so, and persists the IPython instance between calls to give a REPL-like experience.
"""

import dataclasses
import functools
import importlib.util
import re
from collections.abc import Callable, Generator
from logging import getLogger
from typing import TYPE_CHECKING, TypeVar

from ..message import Message
from ..util.ask_execute import print_preview
from .base import (
    ConfirmFunc,
    Parameter,
    ToolSpec,
    ToolUse,
)

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


def _get_ipython():
    global _ipython
    from IPython.terminal.embed import InteractiveShellEmbed  # fmt: skip

    if _ipython is None:
        _ipython = InteractiveShellEmbed()
        _ipython.push(registered_functions)

    return _ipython


def execute_python(
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc = lambda _: True,
) -> Generator[Message, None, None]:
    """Executes a python codeblock and returns the output."""

    if code is not None and args is not None:
        code = code.strip()
    elif kwargs is not None:
        code = kwargs.get("code", "").strip()

    assert code is not None

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
    # TODO: should we include captured stdout with messages like these?
    # used by vision tool
    if isinstance(result.result, Message):
        yield result.result
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


def get_functions():
    return "\n".join([f"- {func.__name__}" for func in registered_functions.values()])


instructions = """
This tool execute Python code in an interactive IPython session.
It will respond with the output and result of the execution.
"""

instructions_format = {
    "markdown": """
To use it, send a codeblock using the `ipython` language tag.
If you first write the code in a normal python codeblock, remember to also execute it with the ipython codeblock.
"""
}


def examples(tool_format):
    return f"""
#### Results of the last expression will be displayed, IPython-style:
> User: What is 2 + 2?
> Assistant:
{ToolUse("ipython", [], "2 + 2").to_output(tool_format)}
> System: Executed code block.
{ToolUse("result", [], "4").to_output()}

#### It can write an example and then execute it:
> User: compute fib 10
> Assistant: To compute the 10th Fibonacci number, we can execute this code:
{ToolUse("ipython", [], '''
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
fib(10)
'''.strip()).to_output(tool_format)}
> System: Executed code block.
{ToolUse("result", [], "55").to_output()}
""".strip()


def init() -> ToolSpec:
    python_libraries = get_installed_python_libraries()
    python_libraries_str = "\n".join(f"- {lib}" for lib in python_libraries)

    _instructions = f"""{instructions}

The following libraries are available:
{python_libraries_str}

The following functions are available:
{get_functions()}
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
    parameters=[
        Parameter(
            name="code",
            type="string",
            description="The code to execute in the IPython shell.",
            required=True,
        ),
    ],
)
__doc__ = tool.get_doc(__doc__)
