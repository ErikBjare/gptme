"""
Read the contents of a file.
"""

from . import ToolSpec, ToolUse

instructions = (
    "Read the content of the given file. Use the `cat` command with the `shell` tool."
)


def examples(tool_format):
    return f"""
> User: read file.txt
> Assistant:
{ToolUse("shell", [], "cat file.txt").to_output(tool_format)}
""".strip()


# Note: this isn't actually a tool, it only serves prompting purposes
tool = ToolSpec(
    name="read",
    desc="Read the content of a file",
    instructions=instructions,
    examples=examples,
)
__doc__ = tool.get_doc(__doc__)
