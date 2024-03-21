"""
The assistant can execute Python code blocks.

It uses IPython to do so, and persists the IPython instance between calls to give a REPL-like experience.

.. chat::

    User: What is 2 + 2?
    Assistant:
    ```python
    2 + 2
    ```
    System: Executed code block.
    stdout:
    ```
    4
    ```

The user can also run Python code with the /python command:

.. chat::

    User: /python 2 + 2
    System: Executed code block.
    stdout:
    ```
    4
    ```
"""

import re
from collections.abc import Generator
from logging import getLogger
from typing import Callable, TypeVar

from IPython.terminal.embed import InteractiveShellEmbed
from IPython.utils.capture import capture_output

from ..message import Message
from ..util import ask_execute, print_preview

logger = getLogger(__name__)

# IPython instance
_ipython = None


def init_python():
    check_available_packages()


registered_functions = {}

T = TypeVar("T", bound=Callable)


def register_function(func: T) -> T:
    """Decorator to register a function to be available in the IPython instance."""
    registered_functions[func.__name__] = func
    return func


def register_function_if(condition: bool):
    if condition:
        return register_function
    else:
        return lambda x: x


def _get_ipython():
    global _ipython
    if _ipython is None:
        _ipython = InteractiveShellEmbed()
        _ipython.push(registered_functions)

    return _ipython


def execute_python(code: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a python codeblock and returns the output."""
    code = code.strip()
    if ask:
        print_preview(code, "python")
        confirm = ask_execute()
        print()
        if not confirm:
            # early return
            yield Message("system", "Aborted, user chose not to run command.")
            return
    else:
        print("Skipping confirmation")

    # Create an IPython instance if it doesn't exist yet
    _ipython = _get_ipython()

    # Capture the standard output and error streams
    with capture_output() as captured:
        # Execute the code
        result = _ipython.run_cell(code, silent=False, store_history=False)

    output = ""
    if captured.stdout:
        # remove one occurrence of the result if present, to avoid repeating the result in the output
        stdout = (
            captured.stdout.replace(str(result.result), "", 1)
            if result.result
            else captured.stdout
        )
        if stdout:
            output += f"stdout:\n```\n{stdout.rstrip()}\n```\n\n"
    if captured.stderr:
        output += f"stderr:\n```\n{captured.stderr.rstrip()}\n```\n\n"
    if result.error_in_exec:
        tb = result.error_in_exec.__traceback__
        while tb.tb_next:  # type: ignore
            tb = tb.tb_next  # type: ignore
        output += f"Exception during execution on line {tb.tb_lineno}:\n  {result.error_in_exec.__class__.__name__}: {result.error_in_exec}"  # type: ignore
    if result.result is not None:
        output += f"Result:\n```\n{result.result}\n```\n\n"

    # strip ANSI escape sequences
    # TODO: better to signal to the terminal that we don't want colors?
    output = re.sub(r"\x1b[^m]*m", "", output)
    yield Message("system", "Executed code block.\n\n" + output)


def check_available_packages():
    """Checks that essentials like numpy, pandas, matplotlib are available."""
    expected = ["numpy", "pandas", "matplotlib"]
    missing = []
    for package in expected:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        logger.warning(
            f"Missing packages: {', '.join(missing)}. Install them with `pip install gptme-python -E datascience`"
        )
