import pytest
from gptme.tools.context import _ctags, _gen_context_msg
from gptme.tools.shell import ShellSession, set_shell


@pytest.fixture
def shell():
    shell = ShellSession()
    set_shell(shell)
    return shell


def test_gen_context_msg(shell):
    msg = _gen_context_msg()
    assert "gptme" in msg.content, f"Expected 'gptme' in output: {msg.content}"
    assert "$ pwd" in msg.content, f"Expected 'pwd' in output: {msg.content}"


def test_ctags(shell):
    output = _ctags()
    assert "function" in output, f"Expected 'def' in output: {output}"
