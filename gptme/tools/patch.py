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

import re
from collections.abc import Generator
from pathlib import Path

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


def common_leading_whitespace(lines):
    """
    Returns the common leading whitespace for a list of lines.
    """
    if not lines:
        return ""
    return min(re.match(r"\s*", line).group(0) for line in lines if line.strip())


def apply(codeblock: str, content: str) -> str:
    """
    Applies the patch in ``codeblock`` to ``content``.
    """
    codeblock = codeblock.strip()

    # get the original and modified chunks
    original = re.split("<<<<<<< ORIGINAL\n", codeblock)[1]
    original, modified = re.split("=======\n", original)
    if ">>>>>>> UPDATED" not in modified:
        raise ValueError("invalid patch", codeblock)
    modified = re.split(">>>>>>> UPDATED", modified)[0].rstrip("\n")

    # calculate the common leading whitespace for each block
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()
    original_whitespace = common_leading_whitespace(original_lines)
    modified_whitespace = common_leading_whitespace(modified_lines)

    # remove the common leading whitespace from each line in the blocks
    original_no_whitespace = "\n".join(
        line[len(original_whitespace) :] for line in original_lines
    )
    modified_no_whitespace = "\n".join(
        line[len(modified_whitespace) :] for line in modified_lines
    )

    # replace the original block with the modified block in the content
    new = content.replace(original_no_whitespace, modified_no_whitespace)

    # add back the original block's leading whitespace to the modified block
    new = new.replace(
        modified_no_whitespace,
        "\n".join(
            original_whitespace + line for line in modified_no_whitespace.splitlines()
        ),
    )

    if new == content:
        raise ValueError("patch did not change the file")

    return new


def apply_file(codeblock, filename):
    codeblock = codeblock.strip()
    _patch, filename = codeblock.splitlines()[0].split()
    if not _patch == "```patch":
        raise ValueError(
            "invalid patch, codeblock is missing leading ```patch", codeblock
        )
    if not Path(filename).exists():
        raise FileNotFoundError(filename)

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
    except (ValueError, FileNotFoundError) as e:
        yield Message("system", f"Patch failed: {e.args[0]}")


if __name__ == "__main__":
    # Test 1: Original block has leading whitespace, modified block does not
    content = """
class Test:
    def method(self):
        print("Hello, world!")
"""
    patch = """
```patch test.py
<<<<<<< ORIGINAL
    def method(self):
        print("Hello, world!")
=======
def method(self):
    print("Hello, Python!")
>>>>>>> UPDATED
"""
    expected = """
class Test:
    def method(self):
        print("Hello, Python!")
"""
    assert apply(patch, content) == expected

    # Test 2: Original block does not have leading whitespace, modified block does
    content = """
def method():
    print("Hello, world!")
"""
    patch = """
```patch test.py
<<<<<<< ORIGINAL
def method():
    print("Hello, world!")
=======
    def method():
        print("Hello, Python!")
>>>>>>> UPDATED
"""
    expected = """
def method():
    print("Hello, Python!")
"""
    assert apply(patch, content) == expected

    print("All tests passed!")
