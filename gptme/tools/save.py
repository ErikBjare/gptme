"""
Gives the assistant the ability to save code to a file.

Example:

.. chat::

    User: write hello world to hello.py
    Assistant:
    ```save hello.py
    print("hello world")
    ```
    System: Saved to hello.py
"""
from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec

instructions = """
To save code to a file, use a code block with the filepath as the language.
""".strip()

examples = """
> User: write a Hello world script to hello.py
```save hello.py
print("Hello world")
```
Saved to `hello.py`.
""".strip()


def execute_save(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """Save code to a file."""
    fn = " ".join(args)
    if fn.startswith("save "):
        fn = fn[5:]
    assert fn, "No filename provided"
    # strip leading newlines
    code = code.lstrip("\n")
    # ensure it ends with a newline
    if not code.endswith("\n"):
        code += "\n"

    if ask:
        confirm = ask_execute(f"Save to {fn}?")
        print()
    else:
        confirm = True
        print("Skipping confirmation.")

    if ask and not confirm:
        # early return
        yield Message("system", "Save cancelled.")
        return

    path = Path(fn).expanduser()

    # if the file exists, ask to overwrite
    if path.exists():
        if ask:
            overwrite = ask_execute("File exists, overwrite?")
            print()
        else:
            overwrite = True
            print("Skipping overwrite confirmation.")
        if not overwrite:
            # early return
            yield Message("system", "Save cancelled.")
            return

    # if the folder doesn't exist, ask to create it
    if not path.parent.exists():
        if ask:
            create = ask_execute("Folder doesn't exist, create it?")
            print()
        else:
            create = True
            print("Skipping folder creation confirmation.")
        if create:
            path.parent.mkdir(parents=True)
        else:
            # early return
            yield Message("system", "Save cancelled.")
            return

    print("Saving to " + fn)
    with open(path, "w") as f:
        f.write(code)
    yield Message("system", f"Saved to {fn}")


def execute_append(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """Append code to a file."""
    fn = " ".join(args)
    assert fn, "No filename provided"
    # strip leading newlines
    code = code.lstrip("\n")
    # ensure it ends with a newline
    if not code.endswith("\n"):
        code += "\n"

    if ask:
        confirm = ask_execute(f"Append to {fn}?")
        print()
    else:
        confirm = True
        print("Skipping append confirmation.")

    if ask and not confirm:
        # early return
        yield Message("system", "Append cancelled.")
        return

    path = Path(fn).expanduser()

    if not path.exists():
        yield Message("system", f"File {fn} doesn't exist, can't append to it.")
        return

    with open(path, "a") as f:
        f.write(code)
    yield Message("system", f"Appended to {fn}")


tool_save = ToolSpec(
    name="save",
    desc="Save code to a file",
    instructions=instructions,
    examples=examples,
    execute=execute_save,
    block_types=["save"],
)

instructions_append = """
To append code to a file, use a code block with the language: append <filepath>
""".strip()

examples_append = """
> User: append a print "Hello world" to hello.py
> Assistant:
```append hello.py
print("Hello world")
```
> System: Appended to `hello.py`.
""".strip()

tool_append = ToolSpec(
    name="append",
    desc="Append code to a file",
    instructions=instructions_append,
    examples=examples_append,
    execute=execute_append,
    block_types=["append"],
)
