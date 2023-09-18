import ast
import io
from contextlib import redirect_stderr, redirect_stdout
from typing import Generator

from ..message import Message
from ..util import ask_execute, print_preview

locals_ = {}  # type: ignore


def execute_python(code: str, ask: bool) -> Generator[Message, None, None]:
    """Executes a python codeblock and returns the output."""
    code = code.strip()
    if ask:
        print_preview(code, "python")
        confirm = ask_execute()
        print()
    else:
        print("Skipping confirmation")

    if ask and not confirm:
        # early return
        yield Message("system", "Aborted, user chose not to run command.")
        return

    # remove blank lines
    code = "\n".join([line for line in code.split("\n") if line.strip()])

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


def test_execute_python():
    assert execute_python("1 + 1", ask=False) == ">>> 1 + 1\n2\n"
    assert execute_python("a = 2\na", ask=False) == ">>> a = 2\n>>> a\n2\n"
    assert execute_python("print(1)", ask=False) == ">>> print(1)\n"

    # test that vars are preserved between executions
    assert execute_python("a = 2", ask=False) == ">>> a = 2\n"
    assert execute_python("a", ask=False) == ">>> a\n2\n"


# OLD
def old(code: str):
    # parse code into statements
    try:
        statements = ast.parse(code).body
    except SyntaxError as e:
        yield Message("system", f"SyntaxError: {e}")
        return

    output = ""
    # execute statements
    for stmt in statements:
        stmt_str = ast.unparse(stmt)
        output += ">>> " + stmt_str + "\n"
        try:
            # if stmt is assignment or function def, have to use exec
            if (
                isinstance(stmt, ast.Assign)
                or isinstance(stmt, ast.AnnAssign)
                or isinstance(stmt, ast.Assert)
                or isinstance(stmt, ast.ClassDef)
                or isinstance(stmt, ast.FunctionDef)
                or isinstance(stmt, ast.Import)
                or isinstance(stmt, ast.ImportFrom)
                or isinstance(stmt, ast.If)
                or isinstance(stmt, ast.For)
                or isinstance(stmt, ast.While)
                or isinstance(stmt, ast.With)
                or isinstance(stmt, ast.Try)
                or isinstance(stmt, ast.AsyncFor)
                or isinstance(stmt, ast.AsyncFunctionDef)
                or isinstance(stmt, ast.AsyncWith)
            ):
                with io.StringIO() as buf, redirect_stdout(buf):
                    exec(stmt_str, globals(), locals_)
                    result = buf.getvalue().strip()
            else:
                result = eval(stmt_str, globals(), locals_)
            if result:
                output += str(result) + "\n"
        except Exception as e:
            output += f"{e.__class__.__name__}: {e}\n"
            break
