"""
Gives the assistant the ability to save whole files, or append to them.
"""

from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util.ask_execute import execute_with_confirmation
from .base import (
    ConfirmFunc,
    Parameter,
    ToolSpec,
    ToolUse,
    get_path,
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
> Assistant:
{ToolUse("save", ["hello.py"], 'print("Hello world")').to_output(tool_format)}
> System: Saved to `hello.py`
> User: make it all-caps
> Assistant:
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


def preview_save(content: str, path: Path | None) -> str | None:
    """Prepare preview content for save operation."""
    assert path
    if path.exists():
        current = path.read_text()
        p = Patch(current, content)
        diff_str = p.diff_minimal()
        return diff_str if diff_str.strip() else None
    return content


def preview_append(content: str, path: Path | None) -> str | None:
    """Prepare preview content for append operation."""
    assert path
    if path.exists():
        current = path.read_text()
        if not current.endswith("\n"):
            current += "\n"
    else:
        current = ""
    new = current + content
    return preview_save(new, path)


def execute_save_impl(
    content: str, path: Path | None, confirm: ConfirmFunc
) -> Generator[Message, None, None]:
    """Actual save implementation."""
    assert path

    # Ensure content ends with newline
    if not content.endswith("\n"):
        content += "\n"

    # Check if file exists
    if path.exists():
        if not confirm("File exists, overwrite?"):
            yield Message("system", "Save aborted: user refused to overwrite the file.")
            return

    # Check if folder exists
    if not path.parent.exists():
        if not confirm("Folder doesn't exist, create it?"):
            yield Message(
                "system", "Save aborted: user refused to create a missing folder."
            )
            return
        path.parent.mkdir(parents=True)

    # Save the file
    with open(path, "w") as f:
        f.write(content)
    yield Message("system", f"Saved to {path}")


def execute_append_impl(
    content: str, path: Path | None, confirm: ConfirmFunc
) -> Generator[Message, None, None]:
    """Actual append implementation."""
    assert path
    path_display = path
    path = path.expanduser()
    if not path.exists():
        if not confirm(f"File {path_display} doesn't exist, create it?"):
            yield Message(
                "system",
                "Append aborted: user refused to create the missing destination file.",
            )
            return

    # strip leading newlines
    # content = content.lstrip("\n")
    # ensure it ends with a newline
    if not content.endswith("\n"):
        content += "\n"

    before = path.read_text()
    if not before.endswith("\n"):
        content = "\n" + content
    with open(path, "a") as f:
        f.write(content)
    yield Message("system", f"Appended to {path_display}")


def execute_save(
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """Save code to a file."""
    yield from execute_with_confirmation(
        code,
        args,
        kwargs,
        confirm,
        execute_fn=execute_save_impl,
        get_path_fn=get_path,
        preview_fn=preview_save,
        preview_lang="diff" if get_path(code, args, kwargs).exists() else None,
        confirm_msg=f"Save to {get_path(code, args, kwargs)}?",
        allow_edit=True,
    )


def execute_append(
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """Append code to a file."""
    yield from execute_with_confirmation(
        code,
        args,
        kwargs,
        confirm,
        execute_fn=execute_append_impl,
        get_path_fn=get_path,
        preview_fn=preview_append,
        preview_lang="diff",
        confirm_msg=f"Append to {get_path(code, args, kwargs)}?",
        allow_edit=True,
    )


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
            name="path",
            type="string",
            description="The path of the file",
            required=True,
        ),
        Parameter(
            name="content",
            type="string",
            description="The content to save",
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
            name="path",
            type="string",
            description="The path of the file",
            required=True,
        ),
        Parameter(
            name="content",
            type="string",
            description="The content to append",
            required=True,
        ),
    ],
)
__doc__ = tool_append.get_doc(__doc__)
