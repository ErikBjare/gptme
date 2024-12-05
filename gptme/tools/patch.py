"""
Gives the LLM agent the ability to patch text files, by using a adapted version git conflict markers.
"""

import difflib
import re
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from ..message import Message
from ..util.ask_execute import get_editable_text, set_editable_text, print_preview
from .base import (
    ConfirmFunc,
    Parameter,
    ToolSpec,
    ToolUse,
)

instructions = """
To patch/modify files, we use an adapted version of git conflict markers.

This can be used to edit files, without having to rewrite the whole file.
Only one patch block can be written per tool use. Extra ORIGINAL/UPDATED blocks will be ignored.
Try to keep the patch as small as possible. Avoid placeholders, as they may make the patch fail.

To keep the patch small, try to scope the patch to imports/function/class.
If the patch is large, consider using the save tool to rewrite the whole file.
""".strip()

instructions_format = {
    "markdown": f"""
The $PATH parameter MUST be on the same line as the code block start, not on the line after.

The patch block should be written in the following format:

{ToolUse("patch", ["$PATH"], '''
<<<<<<< ORIGINAL
$ORIGINAL_CONTENT
=======
$UPDATED_CONTENT
>>>>>>> UPDATED
'''.strip()).to_output("markdown")}
"""
}

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"

patch_content = """
<<<<<<< ORIGINAL
    print("Hello world")
=======
    name = input("What is your name? ")
    print(f"Hello {name}")
>>>>>>> UPDATED
""".strip()


def examples(tool_format):
    return f"""
> User: patch `src/hello.py` to ask for the name of the user
```src/hello.py
def hello():
    print("Hello world")

if __name__ == "__main__":
    hello()
```
> Assistant:
{ToolUse("patch", ["src/hello.py"], patch_content).to_output(tool_format)}
> System: Patch applied
""".strip()


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

            # First split on ORIGINAL to get the content after it
            _, after_original = re.split(re.escape(ORIGINAL), patch, maxsplit=1)

            # Then split on DIVIDER to get the original content
            if DIVIDER not in after_original:  # pragma: no cover
                raise ValueError("invalid patch format: missing =======")
            original, after_divider = re.split(
                re.escape(DIVIDER), after_original, maxsplit=1
            )

            # Finally split on UPDATED to get the modified content
            # Use UPDATED[1:] to ignore the leading newline in the marker,
            # allowing us to detect truly empty content between ======= and >>>>>>> UPDATED
            if after_divider.startswith(UPDATED[1:]):
                # Special case: empty content followed immediately by UPDATED marker
                modified = ""
            else:
                if UPDATED not in after_divider:  # pragma: no cover
                    raise ValueError("invalid patch format: missing >>>>>>> UPDATED")
                modified, _ = re.split(re.escape(UPDATED), after_divider, maxsplit=1)
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
    code: str | None,
    args: list[str] | None,
    kwargs: dict[str, str] | None,
    confirm: ConfirmFunc = lambda _: True,
) -> Generator[Message, None, None]:
    """
    Applies the patch.
    """

    fn = None
    if code is not None and args is not None:
        fn = " ".join(args)
        if not fn:
            yield Message("system", "No path provided")
            return
    elif kwargs is not None:
        code = kwargs.get("patch", "")
        fn = kwargs.get("path", "")

    assert code is not None, "No patch provided"
    assert fn is not None, "No path provided"

    if code is None:
        yield Message("system", "No patch provided")
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

    # Make patch content editable before confirmation
    set_editable_text(code, "patch")

    if not confirm(f"Apply patch to {fn}?"):
        print("Patch not applied")
        return

    # Get potentially edited content
    code = get_editable_text()

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
    parameters=[
        Parameter(
            name="path",
            type="string",
            description="The path of the file to patch.",
            required=True,
        ),
        Parameter(
            name="patch",
            type="string",
            description="The patch to apply.",
            required=True,
        ),
    ],
)
__doc__ = tool.get_doc(__doc__)
