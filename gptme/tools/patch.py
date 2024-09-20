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


def apply_searchreplace(codeblock: str, content: str) -> str:
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

    return new_content


def apply_unified_diff(codeblock: str, content: str) -> str:
    """
    Applies a unified diff patch in ``codeblock`` to ``content``.
    Accepts invalid metadata (since LLMs can't reliably generate them) as long as the diff is valid, unique, and applies cleanly.
    Aider has a great writeup: https://aider.chat/docs/unified-diffs.html
    """
    # Pre-process content
    lines = [line for line in content.splitlines() if line.strip()]

    # Remove potential invalid metadata lines
    clean_diff = re.sub(r"^--- .*$\n^\+\+\+ .*$\n", "", codeblock, flags=re.MULTILINE)

    # Split the diff into chunks
    chunks = re.split(r"(?=^@@)", clean_diff, flags=re.MULTILINE)

    result_lines = []
    content_line = 0

    for chunk in chunks:
        if not chunk.strip():
            continue

        # Extract hunk header
        hunk_match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", chunk)
        if not hunk_match:
            raise ValueError("Invalid hunk header")

        start1, length1, start2, length2 = map(
            lambda x: int(x) if x else 1, hunk_match.groups()
        )

        # Extract hunk lines
        hunk_lines = chunk[hunk_match.end() :].splitlines()

        # Add unchanged lines before the hunk
        while content_line < start1 - 1:
            result_lines.append(lines[content_line])
            content_line += 1

        # Apply the changes
        i = 0
        while i < len(hunk_lines):
            line = hunk_lines[i]
            if not line.strip():
                result_lines.append(line)
                i += 1
            elif line.startswith(" "):
                if (
                    content_line < len(lines)
                    and line[1:].strip() == lines[content_line].strip()
                ):
                    result_lines.append(lines[content_line])
                    content_line += 1
                else:
                    result_lines.append(line[1:])
                i += 1
            elif line.startswith("-"):
                if (
                    content_line < len(lines)
                    and line[1:].strip() == lines[content_line].strip()
                ):
                    content_line += 1
                i += 1
            elif line.startswith("+"):
                result_lines.append(line[1:])
                i += 1
            else:
                raise ValueError(f"Invalid line in hunk: {line}")

    # Add any remaining lines from the original content
    result_lines.extend(lines[content_line:])

    return "\n".join(result_lines)


def is_searchreplace(codeblock: str) -> bool:
    """
    Check if the codeblock is a search/replace patch.
    """
    return ORIGINAL in codeblock and UPDATED in codeblock


def is_unified_diff(codeblock: str) -> bool:
    """
    Check if the codeblock is in unified diff format.
    """
    # Look for typical unified diff patterns
    unified_diff_pattern = r"(^@@\s+-\d+,?\d*\s+\+\d+,?\d*\s+@@)"
    return bool(re.search(unified_diff_pattern, codeblock, re.MULTILINE))


def apply_file(codeblock, filename):
    """Applies a patch to a file."""
    if not Path(filename).exists():
        raise ValueError(f"file not found: {filename}")

    with open(filename, "r+") as f:
        content = f.read()

        if is_searchreplace(codeblock):
            try:
                result = apply_searchreplace(codeblock, content)
            except ValueError as e:
                raise ValueError(
                    f"patch application using search/replace failed"
                ) from e
        elif is_unified_diff(codeblock):
            try:
                result = apply_unified_diff(codeblock, content)
            except ValueError as e:
                raise ValueError(
                    f"patch application using unified diff failed"
                ) from e
        else:
            raise ValueError("invalid patch format")

        if result == content:
            raise ValueError("patch did not change the file")

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
