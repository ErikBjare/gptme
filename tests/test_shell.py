from gptme.tools import ShellSession


def test_echo():
    # Initialize a shell session
    shell = ShellSession()

    # Run a echo command
    ret, out, err = shell.run_command("echo 'Hello World!'")
    assert err.strip() == ""  # Expecting no stderr
    assert out.strip() == "Hello World!"  # Expecting stdout to be "Hello World!"
    assert ret == 0  # Process should exit with 0

    # Close the shell session
    shell.close()


def test_cd():
    # Initialize a shell session
    shell = ShellSession()

    # Run a cd command
    ret, out, err = shell.run_command("cd /tmp")
    assert err.strip() == ""  # Expecting no stderr
    assert ret == 0  # Process should exit with 0

    # Check the current directory
    ret, out, err = shell.run_command("pwd")
    assert err.strip() == ""  # Expecting no stderr
    assert out.strip() == "/tmp"  # Should be in /tmp now
    assert ret == 0  # Process should exit with 0

    # Close the shell session
    shell.close()
