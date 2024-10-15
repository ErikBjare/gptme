"""
Gives the LLM agent the ability to patch text files, by using a adapted version git conflict markers.
"""

import difflib
import re
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from ..message import Message
from ..util import print_preview
from .base import ConfirmFunc, ToolSpec, ToolUse

instructions = f"""
To patch/modify files, we use an adapted version of git conflict markers.

This can be used to edit files, without having to rewrite the whole file.
Only one patch block can be written per codeblock. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible. Avoid placeholders, as they may make the patch fail.

To keep the patch small, try to scope the patch to imports/function/class.
If the patch is large, consider using the save tool to rewrite the whole file.

The patch block should be written in the following format:

{ToolUse("patch", ["$FILENAME"], '''
<<<<<<< ORIGINAL
$ORIGINAL_CONTENT
=======
$UPDATED_CONTENT
>>>>>>> UPDATED
'''.strip()).to_output()}
"""

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"


examples = f"""
> User: patch the file `hello.py` to ask for the name of the user
> Assistant:
{ToolUse("patch", ["hello.py"], '''
<<<<<<< ORIGINAL
def hello():
    print("Hello world")
=======
def hello():
    name = input("What is your name? ")
    print(f"Hello {name}")
>>>>>>> UPDATED
'''.strip()).to_output()}
> System: Patch applied
"""


@dataclass
class Patch:
    original: str
    updated: str

    def apply(self, content: str) -> str:
        if self.original not in content:
            raise ValueError("original chunk not found in file")
        if content.count(self.original) > 1:
            raise ValueError("original chunk not unique")
        new_content = content.replace(self.original, self.updated, 1)
        if new_content == content:
            raise ValueError("patch did not change the file")
        return new_content

    def diff_minimal(self, strip_context=False) -> str:
        """
        Show a minimal diff of the patch.
        Note that a minimal diff isn't necessarily a unique diff.
        """
        # TODO: replace previous patches with the minimal version

        diff = list(
            difflib.unified_diff(
                self.original.splitlines(),
                self.updated.splitlines(),
                lineterm="",
            )
        )[3:]
        if strip_context:
            # find first and last lines with changes
            markers = [line[0] for line in diff]
            start = min(
                markers.index("+") if "+" in markers else len(markers),
                markers.index("-") if "-" in markers else len(markers),
            )
            end = min(
                markers[::-1].index("+") if "+" in markers else len(markers),
                markers[::-1].index("-") if "-" in markers else len(markers),
            )
            diff = diff[start : len(diff) - end]
        return "\n".join(diff)

    @classmethod
    def _from_codeblock(cls, codeblock: str) -> Generator["Patch", None, None]:
        codeblock = codeblock.strip()

        # Split the codeblock into multiple patches
        patches = re.split(f"(?={re.escape(ORIGINAL)})", codeblock)

        for patch in patches:
            if not patch.strip():
                continue

            if ORIGINAL not in patch:  # pragma: no cover
                raise ValueError(f"invalid patch, no `{ORIGINAL.strip()}`", patch)

            parts = re.split(
                f"{re.escape(ORIGINAL)}|{re.escape(DIVIDER)}|{re.escape(UPDATED)}",
                patch,
            )
            if len(parts) != 4:  # pragma: no cover
                raise ValueError("invalid patch format")

            _, original, modified, _ = parts
            yield Patch(original, modified)

    @classmethod
    def from_codeblock(cls, codeblock: str) -> Generator["Patch", None, None]:
        for patch in cls._from_codeblock(codeblock):
            original, updated = patch.original, patch.updated
            re_placeholder = re.compile(r"^[ \t]*(#|//|\") \.\.\. ?.*$", re.MULTILINE)
            if re_placeholder.search(original) or re_placeholder.search(updated):
                originals = re_placeholder.split(original)
                modifieds = re_placeholder.split(updated)
                if len(originals) != len(modifieds):
                    raise ValueError(
                        "different number of placeholders in original and modified chunks"
                    )
                for orig, mod in zip(originals, modifieds):
                    if orig == mod:
                        continue
                    yield Patch(orig, mod)
            else:
                yield patch


def apply(codeblock: str, content: str) -> str:
    """
    Applies multiple patches in ``codeblock`` to ``content``.
    """
    new_content = content
    for patch in Patch.from_codeblock(codeblock):
        new_content = patch.apply(new_content)
    return new_content


def execute_patch(
    code: str,
    args: list[str],
    confirm: ConfirmFunc,
) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """
    fn = " ".join(args)
    if not fn:
        yield Message("system", "No path provided")
        return

    path = Path(fn).expanduser()
    if not path.exists():
        yield Message("system", f"File not found: {fn}")
        return

    try:
        patches = Patch.from_codeblock(code)
        patches_str = "\n\n".join(p.diff_minimal() for p in patches)
    except ValueError as e:
        yield Message("system", f"Patch failed: {e.args[0]}")
        return

    # TODO: display minimal patches
    # TODO: include patch headers to delimit multiple patches
    print_preview(patches_str, lang="diff")

    if not confirm(f"Apply patch to {fn}?"):
        print("Patch not applied")
        return

    try:
        with open(path) as f:
            original_content = f.read()

        # Apply the patch
        patched_content = apply(code, original_content)
        # TODO: if the patch is inefficient, replace request to use minimal unique patch
        with open(path, "w") as f:
            f.write(patched_content)

        # Compare token counts
        patch_len = len(code)
        full_file_len = len(patched_content)

        warnings = []
        if 1000 < full_file_len < patch_len:
            warnings.append(
                "Note: The patch was big and larger than the file. In the future, try writing smaller patches or use the save tool instead."
            )
        warnings_str = ("\n".join(warnings) + "\n") if warnings else ""

        yield Message("system", f"{warnings_str}Patch successfully applied to {fn}")
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
