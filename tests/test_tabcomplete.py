import re
import os
import time
import pytest
from subprocess import run, PIPE
from IPython.testing.globalipapp import get_ipython
from gptme.tabcomplete import _matches

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    original_dir = os.getcwd()
    os.chdir("/home/lame/Desktop/projects/gptme")  # Update this path to your project root
    yield
    os.chdir(original_dir)

def run_cli_command(command):
    result = run(command, shell=True, stdout=PIPE, stderr=PIPE, text=True)
    output = strip_ansi(result.stdout + result.stderr)
    print(f"Command: {command}\nOutput: {output}")  # Debugging line
    return output

@pytest.mark.parametrize("command, expected", [
    ("/exit", "Exiting"),
    ("/tokens", "Token usage"),
    ("/tools", "Available tools")
])
def test_cli_commands(command, expected):
    output = run_cli_command(f"gptme {command}")
    print(f"Command: {command}\nOutput: {output}")  # Debugging line
    assert expected in output

def test_block_ipython():
    ip = get_ipython()
    output = ip.run_cell("print('after empty line')")
    cleaned_output = strip_ansi(str(output.result))
    assert "after empty line" in cleaned_output

def test_generate_primes():
    import logging
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.ERROR)
    
    output = run_cli_command("gptme generate_primes 10")
    
    logging.getLogger().setLevel(original_level)
    assert "29" in output

def test_tmux():
    # Check if tmux is installed
    tmux_check = run_cli_command("which tmux")
    print(f"tmux installation check: {tmux_check}")

    # Run top directly
    top_output = run_cli_command("top -b -n 1")
    print(f"Direct top output: {top_output}")

    for _ in range(5):  # Retry up to 5 times
        output = run_cli_command("tmux new-session -d 'top -b -n 1' && sleep 5 && tmux capture-pane -p")
        print(f"Attempt output: {output}")
        if "%CPU" in output:
            break
        time.sleep(2)
    else:
        pytest.fail("Expected '%CPU' not found in tmux output")

@pytest.fixture
def mock_git_dir(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    return git_dir

def test_matches(mock_git_dir):
    # Change to the temporary directory
    os.chdir(mock_git_dir.parent)
    
    result = _matches("")
    assert '.git/' in result

if __name__ == "__main__":
    pytest.main([__file__])
