"""
Gives the assistant the ability to save whole files, or append to them.
"""

from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute, print_preview
from .base import ToolSpec, ToolUse
from .patch import Patch

# FIXME: this is markdown-specific instructions, thus will confuse the XML mode
instructions = """
To write to a file, use a code block with the language tag: `save <path>`
""".strip()

instructions_append = """
To append to a file, use a code block with the language tag: `append <path>`
""".strip()

examples = f"""
> User: write a hello world script to hello.py
{ToolUse("save", ["hello.py"], 'print("Hello world")').to_output()}
> System: Saved to `hello.py`

> User: make it all-caps
{ToolUse("save", ["hello.py"], 'print("HELLO WORLD")').to_output()}
> System: Saved to `hello.py`
""".strip()

examples_append = f"""
> User: append a print "Hello world" to hello.py
> Assistant:
{ToolUse("append", ["hello.py"], 'print("Hello world")').to_output()}
> System: Appended to `hello.py`
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

    # TODO: add check that it doesn't try to write a file with placeholders!

    if ask:
        if Path(fn).exists():
            current = Path(fn).read_text()
            p = Patch(current, code)
            # TODO: if inefficient save, replace request with patch (and vice versa), or even append
            print_preview(p.diff_minimal(), "diff")

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
    desc="Write text to file",
    instructions=instructions,
    examples=examples,
    execute=execute_save,
    block_types=["save"],
)
__doc__ = tool_save.get_doc(__doc__)

tool_append = ToolSpec(
    name="append",
    desc="Append text to file",
    instructions=instructions_append,
    examples=examples_append,
    execute=execute_append,
    block_types=["append"],
)
__doc__ = tool_append.get_doc(__doc__)
