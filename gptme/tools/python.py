import io
from contextlib import redirect_stderr, redirect_stdout
from logging import getLogger
from collections.abc import Generator

from ..message import Message
from ..util import ask_execute, print_preview

logger = getLogger(__name__)
locals_ = {}  # type: ignore


def init_python():
    check_available_packages()


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

    exc = None
    with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
        try:
            exec(code, locals_, locals_)  # type: ignore
        except Exception as e:
            exc = e
    stdout = out.getvalue().strip()
    stderr = err.getvalue().strip()
    # print(f"Completed execution: stdout={stdout}, stderr={stderr}, exc={exc}")

    output = ""
    if stdout:
        output += f"stdout:\n```\n{stdout.rstrip()}\n```\n\n"
    if stderr:
        output += f"stderr:\n```\n{stderr.rstrip()}\n```\n\n"
    if exc:
        tb = exc.__traceback__
        while tb.tb_next:  # type: ignore
            tb = tb.tb_next  # type: ignore
        output += f"Exception during execution on line {tb.tb_lineno}:\n  {exc.__class__.__name__}: {exc}"  # type: ignore
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
