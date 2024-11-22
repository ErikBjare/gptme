import pytest
from gptme.tools.base import ToolUse
from gptme.tools import init_tools


@pytest.mark.parametrize(
    "tool_format, args, content, kwargs, expected",
    [
        (
            "markdown",
            ["test.txt"],
            "patch",
            None,
            """```patch test.txt
patch
```""",
        ),
        (
            "markdown",
            ["test.txt"],
            "patch",
            {"patch": "patch", "path": "test.txt"},
            """```patch test.txt
patch
```""",
        ),
        (
            "xml",
            ["test.txt"],
            "patch",
            None,
            """<tool-use>
<patch args='test.txt'>
patch
</patch>
</tool-use>""",
        ),
        (
            "tool",
            ["test.txt"],
            "patch",
            None,
            """{"name": "patch", "parameters": {"patch": "patch", "path": "test.txt"}}""",
        ),
        (
            "tool",
            ["test.txt"],
            "patch",
            {"patch": "patch_kwargs", "path": "test_kwargs.txt"},
            """{"name": "patch", "parameters": {"patch": "patch_kwargs", "path": "test_kwargs.txt"}}""",
        ),
    ],
)
def test_tool_use_output_patch(tool_format, args, content, kwargs, expected):
    init_tools(allowlist=["patch"])

    result = ToolUse("patch", args, content, kwargs).to_output(tool_format)

    assert result == expected
