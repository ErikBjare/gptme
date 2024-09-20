"""
Gives the LLM agent the ability to patch text files, using both an adapted version of git conflict markers
and unified diff format.
"""

import re
from collections.abc import Generator
from pathlib import Path

from ..message import Message
from ..util import ask_execute
from .base import ToolSpec, ToolUse

ORIGINAL = "<<<<<<< ORIGINAL\n"
DIVIDER = "\n=======\n"
UPDATED = "\n>>>>>>> UPDATED"


def patch_to_output(filename: str, patch: str) -> str:
    return ToolUse("patch", [filename], patch.strip()).to_output()


enable_udiff = False
instructions = f"""
To patch/modify files, we can use an adapted version of git conflict markers{' or unified diff format.' if enable_udiff else '.'}

For git conflict markers (aka search/replace):
{patch_to_output("$FILENAME", '''
<<<<<<< ORIGINAL
$ORIGINAL_CONTENT
=======
$UPDATED_CONTENT
>>>>>>> UPDATED
''')}
"""

if enable_udiff:
    instructions += f"""
For unified diff format:
{patch_to_output("$FILENAME", '''
@@ -1,3 +1,3 @@
 unchanged line
-removed line
+added line
''')}
"""


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
    codeblock = codeblock.strip()
    new_content = content

    patches = re.split(f"(?={re.escape(ORIGINAL)})", codeblock)

    for patch in patches:
        if not patch.strip():
            continue

        if ORIGINAL not in patch:
            raise ValueError(f"invalid patch, no `{ORIGINAL.strip()}`", patch)

        parts = re.split(
            f"{re.escape(ORIGINAL)}|{re.escape(DIVIDER)}|{re.escape(UPDATED)}", patch
        )
        if len(parts) != 4:
            raise ValueError("invalid patch format", patch)

        _, original, modified, _ = parts

        re_placeholder = re.compile(r"^[ \t]*(#|//|\") \.\.\. ?.*$", re.MULTILINE)
        if re_placeholder.search(original) or re_placeholder.search(modified):
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
            for orig, mod in zip(originals, modifieds, strict=False):
                if orig == mod:
                    continue
                new_content = new_content.replace(orig, mod)
        else:
            if original not in new_content:
                raise ValueError("original chunk not found in file", original)
            new_content = new_content.replace(original, modified)

    return new_content


def apply_unified_diff(codeblock: str, content: str) -> str:
    lines = content.splitlines()
    hunks = parse_unified_diff(codeblock)

    for hunk in hunks:
        lines = apply_hunk(lines, hunk)

    return "\n".join(lines) + "\n"


def parse_unified_diff(codeblock: str) -> list[list[str]]:
    hunks: list[list[str]] = []
    current_hunk: list[str] = []
    for line in codeblock.strip().splitlines():
        if line.startswith("@@") or not hunks:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = []
        current_hunk.append(line)
    if current_hunk:
        hunks.append(current_hunk)
    return hunks if hunks else [codeblock.strip().splitlines()]


def apply_hunk(lines: list[str], hunk: list[str]) -> list[str]:
    if hunk[0].startswith("@@"):
        _, old_range, new_range, _ = hunk[0].split()
        start = int(old_range.split(",")[0][1:]) - 1
    else:
        start = find_hunk_start(lines, hunk)

    result = lines[:start]
    file_index = start

    for line in hunk[1:]:
        if line.startswith(" "):
            result.append(line[1:])
            file_index += 1
        elif line.startswith("+"):
            result.append(line[1:])
        elif line.startswith("-"):
            file_index += 1
        else:
            result.append(line)
            file_index += 1

    result.extend(lines[file_index:])
    return result


def find_hunk_start(lines: list[str], hunk: list[str]) -> int:
    context_before = [line[1:] for line in hunk if line.startswith(" ")][:3]
    for i in range(len(lines) - len(context_before) + 1):
        if all(
            lines[i + j].strip() == line.strip()
            for j, line in enumerate(context_before)
        ):
            return i
    return 0


def is_unified_diff(codeblock: str) -> bool:
    return bool(
        re.search(r"^@@\s+-\d+,?\d*\s+\+\d+,?\d*\s+@@", codeblock, re.MULTILINE)
    ) or all(
        line.startswith((" ", "+", "-")) for line in codeblock.strip().splitlines()
    )


def apply_file(codeblock, filename):
    """Applies a patch to a file."""
    if not Path(filename).exists():
        raise ValueError(f"file not found: {filename}")

    with open(filename, "r+") as f:
        content = f.read()

        if is_unified_diff(codeblock):
            try:
                result = apply_unified_diff(codeblock, content)
            except ValueError as e:
                raise ValueError("patch application using unified diff failed") from e
        else:
            try:
                result = apply_searchreplace(codeblock, content)
            except ValueError as e:
                raise ValueError("patch application using search/replace failed") from e

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
