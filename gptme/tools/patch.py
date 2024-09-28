"""
Gives the LLM agent the ability to patch text files, by using a adapted version git conflict markers.
"""

import re
from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec, ToolUse


def patch_to_output(filename: str, patch: str) -> str:
    return ToolUse("patch", [filename], patch.strip()).to_output()


instructions = f"""
To patch/modify files, we can use an adapted version of git conflict markers.

This can be used to make changes to files, without having to rewrite the whole file.
Only one patch block can be written per codeblock. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible. Avoid placeholders, as they may make the patch fail.

To keep the patch small, try to scope the patch to imports/function/class.
If the patch is large, consider using the save tool to rewrite the whole file.

The patch block should be written in the following format:

{patch_to_output("$FILENAME", '''
<<<<<<< ORIGINAL
$ORIGINAL_CONTENT
=======
$UPDATED_CONTENT
>>>>>>> UPDATED
''')}
"""

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"


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
            raise ValueError("invalid patch format")

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
                )
            for orig, mod in zip(originals, modifieds):
                if orig == mod:
                    continue
                new_content = new_content.replace(orig, mod)
        else:
            if original not in new_content:  # pragma: no cover
                raise ValueError("original chunk not found in file")
            new_content = new_content.replace(original, modified)

    if new_content == content:  # pragma: no cover
        raise ValueError("patch did not change the file")

    return new_content


def execute_patch(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """
    fn = " ".join(args)
    assert fn, "No filename provided"
    path = Path(fn).expanduser()
    if not path.exists():
        raise ValueError(f"file not found: {fn}")
    if ask:
        confirm = ask_execute(f"Apply patch to {fn}?")
        if not confirm:
            print("Patch not applied")
            return

    try:
        with open(path) as f:
            original_content = f.read()

        # Apply the patch
        patched_content = apply(code, original_content)
        with open(path, "w") as f:
            f.write(patched_content)

        # Compare token counts
        patch_tokens = len(code)
        full_file_tokens = len(patched_content)

        warnings = []
        if full_file_tokens < patch_tokens:
            warnings.append(
                "Note: The patch was larger than the file. Consider using the save tool instead."
            )
        warnings_str = ("\n" + "\n".join(warnings)) if warnings else ""

        yield Message("system", f"Patch applied to {fn}{warnings_str}")
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
