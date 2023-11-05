from collections.abc import Generator

import pytest
from gptme.tools.shell import ShellSession


@pytest.fixture
def shell() -> Generator[ShellSession, None, None]:
    shell = ShellSession()
    yield shell
    shell.close()


def test_echo(shell):
    ret, out, err = shell.run_command("echo 'Hello World!'")
    assert err.strip() == ""  # Expecting no stderr
    assert out.strip() == "Hello World!"  # Expecting stdout to be "Hello World!"
    assert ret == 0


def test_echo_multiline(shell):
    # tests multiline and trailing + leading whitespace
    ret, out, err = shell.run_command("echo 'Line 1  \n  Line 2'")
    assert err.strip() == ""  # Expecting no stderr
    assert (
        out.strip() == "Line 1  \n  Line 2"
    )  # Expecting stdout to be "Line 1\nLine 2"
    assert ret == 0


def test_cd(shell):
    # Run a cd command
    ret, out, err = shell.run_command("cd /tmp")
    assert err.strip() == ""  # Expecting no stderr
    assert ret == 0

    # Check the current directory
    ret, out, err = shell.run_command("pwd")
    assert err.strip() == ""  # Expecting no stderr
    assert out.strip() == "/tmp"  # Should be in /tmp now
    assert ret == 0
