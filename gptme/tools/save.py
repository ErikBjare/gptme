"""
Gives the assistant the ability to save whole files, or append to them.
"""

from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import print_preview
from .base import ConfirmFunc, ToolSpec, ToolUse
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
    code: str,
    args: list[str],
    confirm: ConfirmFunc,
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

    if Path(fn).exists():
        current = Path(fn).read_text()
        p = Patch(current, code)
        # TODO: if inefficient save, replace request with patch (and vice versa), or even append
        print_preview(p.diff_minimal(), "diff")

    if not confirm(f"Save to {fn}?"):
        # early return
        yield Message("system", "Save cancelled.")
        return

    path = Path(fn).expanduser()

    # if the file exists, ask to overwrite
    if path.exists():
        if not confirm("File exists, overwrite?"):
            # early return
            yield Message("system", "Save cancelled.")
            return

    # if the folder doesn't exist, ask to create it
    if not path.parent.exists():
        if not confirm("Folder doesn't exist, create it?"):
            # early return
            yield Message("system", "Save cancelled.")
            return
        path.parent.mkdir(parents=True)

    print("Saving to " + fn)
    with open(path, "w") as f:
        f.write(code)
    yield Message("system", f"Saved to {fn}")


def execute_append(
    code: str, args: list[str], confirm: ConfirmFunc
) -> Generator[Message, None, None]:
    """Append code to a file."""
    fn = " ".join(args)
    assert fn, "No filename provided"
    # strip leading newlines
    code = code.lstrip("\n")
    # ensure it ends with a newline
    if not code.endswith("\n"):
        code += "\n"

    if not confirm(f"Append to {fn}?"):
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
