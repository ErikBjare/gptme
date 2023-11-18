from collections.abc import Generator
from logging import getLogger

from IPython.terminal.embed import InteractiveShellEmbed
from IPython.utils.io import capture_output

from ..message import Message
from ..util import ask_execute, print_preview

logger = getLogger(__name__)

# IPython instance
_ipython = None


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

    # Create an IPython instance if it doesn't exist yet
    global _ipython
    if _ipython is None:
        _ipython = InteractiveShellEmbed()

    # Capture the standard output and error streams
    with capture_output() as captured:
        # Execute the code
        result = _ipython.run_cell(code)

    output = ""
    if captured.stdout:
        output += f"stdout:\n```\n{captured.stdout.rstrip()}\n```\n\n"
    if captured.stderr:
        output += f"stderr:\n```\n{captured.stderr.rstrip()}\n```\n\n"
    if result.error_in_exec:
        tb = result.error_in_exec.__traceback__
        while tb.tb_next:  # type: ignore
            tb = tb.tb_next  # type: ignore
        output += f"Exception during execution on line {tb.tb_lineno}:\n  {result.error_in_exec.__class__.__name__}: {result.error_in_exec}"  # type: ignore
    if result.result is not None:
        output += f"Result:\n```\n{result.result}\n```\n\n"
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
