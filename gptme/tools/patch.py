"""
Gives the LLM agent the ability to patch text files, by using a adapted version git conflict markers.
"""

# TODO: support multiple patches in one codeblock (or make it clear that only one patch per codeblock is supported/applied)

import re
from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec, ToolUse

instructions = """
To patch/modify files, we can use an adapted version of git conflict markers.

This can be used to make changes to files, without having to rewrite the whole file.
Only one patch block can be written per codeblock. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible. Avoid placeholders, as they may make the patch fail.

To keep the patch small, try to scope the patch to imports/function/class.
If the patch is large, consider using the save tool to rewrite the whole file.
"""

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"


def patch_to_output(filename: str, patch: str) -> str:
    return ToolUse("patch", [filename], patch).to_output()


examples = f"""
> User: patch the file `hello.py` to ask for the name of the user
> Assistant: {patch_to_output("hello.py", '''
<<<<<<< ORIGINAL
def hello():
    print("Hello world")
=======
def hello():
    name = input("What is your name? ")
    print(f"Hello {name}")
>>>>>>> UPDATED
'''.strip())}
> System: Patch applied
"""


def apply(codeblock: str, content: str) -> str:
    """
    Applies multiple patches in ``codeblock`` to ``content``.
    """
    codeblock = codeblock.strip()
    new_content = content

    # Split the codeblock into multiple patches
    patches = re.split(f"(?={re.escape(ORIGINAL)})", codeblock)

    for patch in patches:
        if not patch.strip():
            continue

        if ORIGINAL not in patch:  # pragma: no cover
            raise ValueError(f"invalid patch, no `{ORIGINAL.strip()}`", patch)

        parts = re.split(
            f"{re.escape(ORIGINAL)}|{re.escape(DIVIDER)}|{re.escape(UPDATED)}", patch
        )
        if len(parts) != 4:  # pragma: no cover
            raise ValueError("invalid patch format", patch)

        _, original, modified, _ = parts

        re_placeholder = re.compile(r"^[ \t]*(#|//|\") \.\.\. ?.*$", re.MULTILINE)
        if re_placeholder.search(original) or re_placeholder.search(modified):
            # if placeholder found in content, then we cannot use placeholder-aware patching
            if re_placeholder.search(content):
                raise ValueError(
                    "placeholders found in content, cannot use placeholder-aware patching"
                )

            originals = re_placeholder.split(original)
            modifieds = re_placeholder.split(modified)
            if len(originals) != len(modifieds):
                raise ValueError(
                    "different number of placeholders in original and modified chunks"
                    f"\n{originals}\n{modifieds}"
                )
            for orig, mod in zip(originals, modifieds):
                if orig == mod:
                    continue
                new_content = new_content.replace(orig, mod)
        else:
            if original not in new_content:  # pragma: no cover
                raise ValueError("original chunk not found in file", original)
            new_content = new_content.replace(original, modified)

    if new_content == content:  # pragma: no cover
        raise ValueError("patch did not change the file")

    return new_content


def apply_file(codeblock, filename):
    if not Path(filename).exists():
        raise ValueError(f"file not found: {filename}")

    with open(filename, "r+") as f:
        content = f.read()
        result = apply(codeblock, content)
        f.seek(0)
        f.truncate()
        f.write(result)


def execute_patch(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """
    fn = " ".join(args)
    assert fn, "No filename provided"
    if ask:
        confirm = ask_execute(f"Apply patch to {fn}?")
        if not confirm:
            print("Patch not applied")
            return

    try:
        apply_file(code, fn)
        yield Message("system", f"Patch applied to {fn}")
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
