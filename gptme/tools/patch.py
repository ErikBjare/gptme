"""
Gives the LLM agent the ability to patch files, by using a adapted version git conflict markers.

Example:

.. chat::

    User: patch the file `hello.py` to ask for the name of the user
    Assistant:
    ```patch hello.py
    <<<<<<< ORIGINAL
    print("Hello world")
    =======
    name = input("What is your name? ")
    print(f"hello {name}")
    >>>>>>> UPDATED
    ```
    System: Patch applied

Inspired by aider.
"""

# TODO: support multiple patches in one codeblock (or make it clear that only one patch per codeblock is supported/applied)
import re
from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec

instructions = """
To patch/modify files, we can use an adapted version of git conflict markers.

This can be used to make changes to files we have written in the past, without having to rewrite the whole file.
Only one patch block can be written per codeblock. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible.

We can also append to files by prefixing the filename with `append`."""

examples = """
> User: patch the file `hello.py` to ask for the name of the user
```patch hello.py
<<<<<<< ORIGINAL
    print("Hello world")
=======
    name = input("What is your name? ")
    print(f"hello {name}")
>>>>>>> UPDATED
```

> User: run the function when the script is run
```append hello.py
if __name__ == "__main__":
    hello()
```
""".strip()

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"


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
    re_placeholder = re.compile(r"^[ \t]*# \.\.\. ?.*$", re.MULTILINE)
    if re_placeholder.search(original) or re_placeholder.search(modified):
        # raise ValueError("placeholders in modified chunk")
        # split them by lines starting with "# ..."
        originals = re_placeholder.split(original)
        modifieds = re_placeholder.split(modified)
        if len(originals) != len(modifieds):
            raise ValueError(
                "different number of placeholders in original and modified chunks"
                f"\n{originals}\n{modifieds}"
            )
        new = content
        for orig, mod in zip(originals, modifieds):
            if orig == mod:
                continue
            new = new.replace(orig, mod)
    else:
        if original not in content:  # pragma: no cover
            raise ValueError("original chunk not found in file", original)

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
