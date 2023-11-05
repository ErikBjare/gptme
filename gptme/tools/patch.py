"""
Gives the LLM agent the ability to patch files, by using a adapted version git conflict markers.

Inspired by aider.
"""
import re
from pathlib import Path
from collections.abc import Generator

from ..message import Message
from ..util import ask_execute

instructions = """
To patch/modify files, we can use an adapted version of git conflict markers.

This can be used to make changes to files we have written in the past, without having to rewrite the whole file.
Only one Patches should written one per codeblock. Do not continue the codeblock after the UPDATED marker.
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


def apply(codeblock: str, content: str) -> str:
    """
    Applies the patch in ``codeblock`` to ``content``.
    """
    # TODO: support multiple patches in one codeblock,
    #       or make it clear that only one patch per codeblock is supported
    codeblock = codeblock.strip()

    # get the original and modified chunks
    original = re.split("\n<<<<<<< ORIGINAL\n", codeblock)[1]
    original, modified = re.split("\n=======\n", original)
    if ">>>>>>> UPDATED\n" not in modified:  # pragma: no cover
        raise ValueError("invalid patch", codeblock)
    modified = re.split(">>>>>>> UPDATED\n", modified)[0].rstrip("\n")

    # TODO: maybe allow modified chunk to contain "// ..." to refer to chunks in the original,
    #       and then replace these with the original chunks?

    # replace the original chunk with the modified chunk
    new = content.replace(original, modified)
    if new == content:  # pragma: no cover
        raise ValueError("patch did not change the file")

    return new


def apply_file(codeblock, filename):
    codeblock = codeblock.strip()
    _patch, filename = codeblock.splitlines()[0].split()
    assert _patch == "```patch"
    assert Path(filename).exists()

    with open(filename) as f:
        content = f.read()

    result = apply(codeblock, content)

    with open(filename, "w") as f:
        f.write(result)

    print(f"Applied patch to {filename}")


def execute_patch(codeblock: str, fn: str, ask: bool) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """
    if ask:
        confirm = ask_execute("Apply patch?")
        if not confirm:
            print("Patch not applied")
            return

    try:
        apply_file(codeblock, fn)
        yield Message("system", "Patch applied")
    except ValueError as e:
        yield Message("system", f"Patch failed: {e.args[0]}")
