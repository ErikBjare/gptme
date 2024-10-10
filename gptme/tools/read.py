"""
Read the contents of a file.
"""

from . import ToolSpec, ToolUse

instructions = "Read files using `cat`"
examples = f"""
User: read file.txt
Assistant:
{ToolUse("shell", [], "cat file.txt").to_output()}
"""

# Note: this isn't actually a tool, it only serves prompting purposes
tool = ToolSpec(
    name="read",
    desc="Read the contents of a file",
    instructions=instructions,
    examples=examples,
)
__doc__ = tool.get_doc(__doc__)
