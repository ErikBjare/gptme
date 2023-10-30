"""
Gives the LLM agent the ability to patch files, by using a adapted version git conflict markers.

Inspired by aider.
"""

import re
from pathlib import Path
from typing import Generator

from ..message import Message
from ..util import ask_execute

instructions = """
# Patching files

The LLM agent can patch files, by using a adapted version git conflict markers.
This can be used to make changes to files we have written in the past, without having to rewrite the whole file.

## Example

> User: Patch the file `hello.py` to ask for the name of the user.
```hello.py
def hello():
    print("hello world")
```

> Assistant:
```patch hello.py
<<<<<<< ORIGINAL
    print("hello world")
=======
    name = input("What is your name? ")
    print(f"hello {name}")
>>>>>>> UPDATED
```
"""


def apply(codeblock: str, content: str) -> str:
    """
    Applies the patch to the file.
    """
    # TODO: support multiple patches in one file, or make it clear that this is not supported (one patch per codeblock)
    codeblock = codeblock.strip()

    # get the original chunk
    original = re.split("\n<<<<<<< ORIGINAL\n", codeblock)[1]
    original = re.split("\n=======\n", original)[0]

    # get the modified chunk
    modified = re.split("\n=======\n", codeblock)[1]
    modified = re.split("\n>>>>>>> UPDATED\n", modified)[0]

    # replace the original chunk with the modified chunk
    content = content.replace(original, modified)

    return content


def apply_file(codeblock, filename):
    codeblock = codeblock.strip()
    _patch, filename = codeblock.splitlines()[0].split()
    assert _patch == "```patch"
    assert Path(filename).exists()

    with open(filename, "r") as f:
        content = f.read()

    result = apply(codeblock, content)

    with open(filename, "w") as f:
        f.write(result)

    print(f"Applied patch to {filename}")


def execute_patch(codeblock: str, fn: str, ask: bool) -> Generator[Message, None, None]:
    """
    Executes the patch.
    """
    if ask:
        confirm = ask_execute("Apply patch?")
        if not confirm:
            print("Patch not applied")
            return

    apply_file(codeblock, fn)
    yield Message("system", "Patch applied")
