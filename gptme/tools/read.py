"""
Read the contents of a file.
"""

from gptme.tools.base import ToolSpec

# Note: this isn't actually a tool, it only serves prompting purposes
tool = ToolSpec(
    name="read",
    desc="Read the contents of a file",
    instructions="""Read files using `cat`.""",
    examples="""```bash
cat file.txt
```""",
)
__doc__ = tool.get_doc(__doc__)
