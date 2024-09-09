"""
Gives the LLM agent the ability to patch text files, by using a adapted version git conflict markers.
"""

# TODO: support multiple patches in one codeblock (or make it clear that only one patch per codeblock is supported/applied)
import re
from collections.abc import Generator
from pathlib import Path
from typing import Literal

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec

instructions = """
To patch/modify files, we can use an adapted version of git conflict markers.

This can be used to make changes to files, without having to rewrite the whole file.
Only one patch block can be written per codeblock. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible. Do not use placeholders, as they will make the patch fail.

We can also append to files by prefixing the filename with `append`."""

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"

mode: Literal["markdown", "xml"] = "markdown"


def patch_to_markdown(patch: str, filename: str, append: bool = False) -> str:
    _tool = "patch" if not append else "append"
    patch = patch.replace("```", "\\`\\`\\`")
    return f"```{_tool} {filename}\n{patch}\n```"


def patch_to_xml(patch: str, filename: str, append: bool = False) -> str:
    _tool = "patch" if not append else "append"
    return f"<{_tool} filename='{filename}'>\n{patch}\n</patch>"


def patch_to_output(patch: str, filename: str, append: bool = False) -> str:
    if mode == "markdown":
        return patch_to_markdown(patch, filename, append)
    elif mode == "xml":
        return patch_to_xml(patch, filename, append)
    else:
        raise ValueError(f"Invalid mode: {mode}")


examples = f"""
> User: patch the file `hello.py` to ask for the name of the user
> Assistant: {patch_to_output("hello.py", '''
<<<<<<< ORIGINAL
    print("Hello world")
=======
    name = input("What is your name? ")
    print(f"Hello {name}")
>>>>>>> UPDATED
''')}
> System: Patch applied

> User: change the codeblock to append to the file
> Assistant: {patch_to_output("patch.py", '''
<<<<<<< ORIGINAL
```save hello.py
=======
```append hello.py
>>>>>>> UPDATED
''')}


> User: run the function when the script is run
> Assistant: {patch_to_output("hello.py", '''
<<<<<<< ORIGINAL
    print("Hello world")
=======
    name = input("What is your name? ")
    print(f"Hello {name}")
>>>>>>> UPDATED
''', append=True)}
""".strip()


def apply(codeblock: str, content: str) -> str:
    """
    Applies the patch in ``codeblock`` to ``content``.
    """
    # TODO: support multiple patches in one codeblock,
    #       or make it clear that only one patch per codeblock is supported
    codeblock = codeblock.strip()

    # get the original and modified chunks
    if ORIGINAL not in codeblock:  # pragma: no cover
        raise ValueError(f"invalid patch, no `{ORIGINAL.strip()}`", codeblock)
    original = re.split(ORIGINAL, codeblock)[1]

    if DIVIDER not in original:  # pragma: no cover
        raise ValueError(f"invalid patch, no `{DIVIDER.strip()}`", codeblock)
    original, modified = re.split(DIVIDER, original)

    if UPDATED not in "\n" + modified:  # pragma: no cover
        raise ValueError(f"invalid patch, no `{UPDATED.strip()}`", codeblock)
    modified = re.split(UPDATED, modified)[0]

    # TODO: maybe allow modified chunk to contain "// ..." to refer to chunks in the original,
    #       and then replace these with the original chunks?

    # replace the original chunk with the modified chunk
    new = content.replace(original, modified)
    if new == content:  # pragma: no cover
        raise ValueError("patch did not change the file")

    return new


def apply_file(codeblock, filename):
    if not Path(filename).exists():
        raise FileNotFoundError(filename)

    with open(filename) as f:
        content = f.read()

    result = apply(codeblock, content)

    with open(filename, "w") as f:
        f.write(result)

    print(f"Applied patch to {filename}")


def execute_patch(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """
    fn = " ".join(args)
    assert fn, "No filename provided"
    if ask:
        confirm = ask_execute("Apply patch?")
        if not confirm:
            print("Patch not applied")
            return

    try:
        apply_file(code, fn)
        yield Message("system", "Patch applied")
    except (ValueError, FileNotFoundError) as e:
        yield Message("system", f"Patch failed: {e.args[0]}")


tool = ToolSpec(
    name="patch",
    desc="Apply a patch to a file",
    instructions=instructions,
    examples=examples,
    execute=execute_patch,
    block_types=["patch"],
)
__doc__ = tool.get_doc(__doc__)
