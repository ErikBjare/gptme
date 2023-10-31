import shutil

import pytest
from gptme.tools.context import ctags, gen_context_msg
from gptme.tools.shell import ShellSession, set_shell


@pytest.fixture
def shell():
    shell = ShellSession()
    set_shell(shell)
    return shell


def test_gen_context_msg(shell):
    msg = gen_context_msg()
    assert "gptme" in msg.content, f"Expected 'gptme' in output: {msg.content}"
    assert "$ pwd" in msg.content, f"Expected 'pwd' in output: {msg.content}"


def test_ctags(shell):
    # if ctags not installed, skip
    if not shutil.which("ctags"):
        pytest.skip("ctags not installed")

    output = ctags()
    expected_strings = ["def", "class", "gptme"]
    for s in expected_strings:
        assert s in output, f"Expected '{s}' in output: {output}"
