"""
Gives the assistant the ability to save whole files, or append to them.
"""

from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import print_preview
from .base import (
    ConfirmFunc,
    Parameter,
    ToolSpec,
    ToolUse,
)
from .patch import Patch

instructions = """
Create or overwrite a file with the given content.

The path can be relative to the current directory, or absolute.
If the current directory changes, the path will be relative to the new directory.
""".strip()

instructions_format = {
    "markdown": "To write to a file, use a code block with the language tag: `save <path>`",
}

instructions_append = """
Append the given content to a file.`.
""".strip()

instructions_format_append = {
    "markdown": """
Use a code block with the language tag: `append <path>`
to append the code block content to the file at the given path.""".strip(),
}


def examples(tool_format):
    return f"""
> User: write a hello world script to hello.py
{ToolUse("save", ["hello.py"], 'print("Hello world")').to_output(tool_format)}
> System: Saved to `hello.py`

> User: make it all-caps
{ToolUse("save", ["hello.py"], 'print("HELLO WORLD")').to_output(tool_format)}
> System: Saved to `hello.py`
""".strip()


def examples_append(tool_format):
    return f"""
> User: append a print "Hello world" to hello.py
> Assistant:
{ToolUse("append", ["hello.py"], 'print("Hello world")').to_output(tool_format)}
> System: Appended to `hello.py`
""".strip()


def execute_save(
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """Save code to a file."""

    fn = ""
    content = ""
    if code is not None and args is not None:
        fn = " ".join(args)
        if fn.startswith("save "):
            fn = fn[5:]

        # strip leading newlines
        content = code.lstrip("\n")
        # ensure it ends with a newline
        if not content.endswith("\n"):
            content += "\n"
    elif kwargs is not None:
        fn = kwargs.get("path", "")
        content = kwargs.get("content", "")

    assert fn, "No filename provided"
    assert content, "No content provided"

    # TODO: add check that it doesn't try to write a file with placeholders!
    path = Path(fn).expanduser()

    if path.exists():
        current = path.read_text()
        p = Patch(current, content)
        # TODO: if inefficient save, replace request with patch (and vice versa), or even append
        print_preview(p.diff_minimal(), "diff")

    if not confirm(f"Save to {fn}?"):
        # early return
        yield Message("system", "Save cancelled.")
        return

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
        f.write(content)
    yield Message("system", f"Saved to {fn}")


def execute_append(
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """Append code to a file."""

    fn = ""
    content = ""
    if code is not None and args is not None:
        fn = " ".join(args)
        # strip leading newlines
        content = code.lstrip("\n")
        # ensure it ends with a newline
        if not content.endswith("\n"):
            content += "\n"
    elif kwargs is not None:
        content = kwargs["content"]
        fn = kwargs["path"]

    assert fn, "No filename provided"
    assert content, "No content provided"

    if not confirm(f"Append to {fn}?"):
        # early return
        yield Message("system", "Append cancelled.")
        return

    path = Path(fn).expanduser()

    if not path.exists():
        yield Message("system", f"File {fn} doesn't exist, can't append to it.")
        return

    with open(path, "a") as f:
        f.write(content)
    yield Message("system", f"Appended to {fn}")


tool_save = ToolSpec(
    name="save",
    desc="Write text to file",
    instructions=instructions,
    instructions_format=instructions_format,
    examples=examples,
    execute=execute_save,
    block_types=["save"],
    parameters=[
        Parameter(
            name="content",
            type="string",
            description="The content to save",
            required=True,
        ),
        Parameter(
            name="path",
            type="string",
            description="The path of the file",
            required=True,
        ),
    ],
)
__doc__ = tool_save.get_doc(__doc__)

tool_append = ToolSpec(
    name="append",
    desc="Append text to file",
    instructions=instructions_append,
    instructions_format=instructions_format_append,
    examples=examples_append,
    execute=execute_append,
    block_types=["append"],
    parameters=[
        Parameter(
            name="content",
            type="string",
            description="The content to append",
            required=True,
        ),
        Parameter(
            name="path",
            type="string",
            description="The path of the file",
            required=True,
        ),
    ],
)
__doc__ = tool_append.get_doc(__doc__)
