"""
Gives the assistant the ability to save code to a file.

Example:

.. chat::

    User: write hello world to hello.py
    Assistant:
    ```hello.py
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
When you send a message containing Python code (and is not a file block), it will be executed in a stateful environment.
Python will respond with the output of the execution.
""".strip()

examples = """
> User: write a Hello world script to hello.py
```hello.py
print("Hello world")
```
Saved to `hello.py`.
""".strip()


def execute_save(
    code: str, ask: bool, args: dict[str, str]
) -> Generator[Message, None, None]:
    """Save the code to a file."""
    fn = args.get("file")
    assert fn, "No filename provided"
    append = args.get("append", False)
    action = "save" if not append else "append"
    # strip leading newlines
    code = code.lstrip("\n")

    if ask:
        confirm = ask_execute(f"{action.capitalize()} to {fn}?")
        print()
    else:
        confirm = True
        print(f"Skipping {action} confirmation.")

    if ask and not confirm:
        # early return
        yield Message("system", f"{action.capitalize()} cancelled.")
        return

    path = Path(fn).expanduser()

    if append:
        if not path.exists():
            yield Message("system", f"File {fn} doesn't exist, can't append to it.")
            return

        with open(path, "a") as f:
            f.write(code)
        yield Message("system", f"Appended to {fn}")
        return

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


tool = ToolSpec(
    name="save",
    desc="Allows saving code to a file.",
    instructions=instructions,
    examples=examples,
    execute=execute_save,
)
