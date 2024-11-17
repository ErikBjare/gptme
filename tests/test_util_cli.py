"""Tests for the gptme-util CLI."""

from pathlib import Path
from click.testing import CliRunner
import pytest

from gptme.util.cli import main


def test_tokens_count():
    """Test the tokens count command."""
    runner = CliRunner()

    # Test basic token counting
    result = runner.invoke(main, ["tokens", "count", "Hello, world!"])
    assert result.exit_code == 0
    assert "Token count" in result.output
    assert "gpt-4" in result.output  # default model

    # Test invalid model
    result = runner.invoke(
        main, ["tokens", "count", "--model", "invalid-model", "test"]
    )
    assert result.exit_code == 1
    assert "not supported" in result.output

    # Test file input
    with runner.isolated_filesystem():
        Path("test.txt").write_text("Hello from file!")
        result = runner.invoke(main, ["tokens", "count", "-f", "test.txt"])
        assert result.exit_code == 0
        assert "Token count" in result.output


def test_chats_list(mocker):
    """Test the chats list command."""
    runner = CliRunner()

    # Test empty list
    mocker.patch("gptme.util.cli.get_user_conversations", return_value=[])
    result = runner.invoke(main, ["chats", "ls"])
    assert result.exit_code == 0
    assert "No conversations found" in result.output

    # Test with conversations
    class MockConv:
        def __init__(self, name, messages, modified):
            self.name = name
            self.messages = messages
            self.modified = modified

    mock_convs = [
        MockConv("test-1", 5, "2024-01-01"),
        MockConv("test-2", 10, "2024-01-02"),
    ]
    mocker.patch("gptme.util.cli.get_user_conversations", return_value=mock_convs)

    result = runner.invoke(main, ["chats", "ls"])
    assert result.exit_code == 0
    assert "test-1" in result.output
    assert "test-2" in result.output
    assert "5 messages" in result.output
    assert "10 messages" in result.output


@pytest.mark.skip("Waiting for context module PR")
def test_context_generate(tmp_path):
    """Test the context generate command."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, world!")

    runner = CliRunner()
    result = runner.invoke(main, ["context", "generate", str(test_file)])
    assert result.exit_code == 0
    assert "Hello, world!" in result.output


def test_tools_list():
    """Test the tools list command."""
    runner = CliRunner()

    # Test basic list
    result = runner.invoke(main, ["tools", "list"])
    assert result.exit_code == 0
    assert "Available tools:" in result.output

    # Test langtags
    result = runner.invoke(main, ["tools", "list", "--langtags"])
    assert result.exit_code == 0
    assert "language tags" in result.output.lower()


def test_tools_info():
    """Test the tools info command."""
    runner = CliRunner()

    # Test valid tool
    result = runner.invoke(main, ["tools", "info", "python"])
    assert result.exit_code == 0
    assert "Tool: python" in result.output
    assert "Description:" in result.output
    assert "Instructions:" in result.output

    # Test invalid tool
    result = runner.invoke(main, ["tools", "info", "nonexistent-tool"])
    assert result.exit_code == 0  # returns 0 but shows error message
    assert "not found" in result.output
