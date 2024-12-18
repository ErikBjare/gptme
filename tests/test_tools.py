from gptme.tools import _discover_tools


def test_tool_loading_with_package():
    found = _discover_tools(["gptme.tools"])

    found_names = [t.name for t in found]

    assert "save" in found_names
    assert "python" in found_names


def test_tool_loading_with_module():
    found = _discover_tools(["gptme.tools.save"])

    found_names = [t.name for t in found]

    assert "save" in found_names
    assert "python" not in found_names
