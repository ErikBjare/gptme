"""Tests for the gptme-util CLI."""

from click.testing import CliRunner

from gptme.util.cli import main


def test_tokens_count():
    """Test the tokens count command."""
    runner = CliRunner()
    result = runner.invoke(main, ["tokens", "count", "Hello, world!"])
    assert result.exit_code == 0
    assert "Token count" in result.output


def test_chats_list():
    """Test the chats list command."""
    runner = CliRunner()
    result = runner.invoke(main, ["chats", "ls"])
    assert result.exit_code == 0


def test_context_generate(tmp_path):
    """Test the context generate command."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, world!")

    runner = CliRunner()
    result = runner.invoke(main, ["context", "generate", str(test_file)])
    assert result.exit_code == 0
    assert "Hello, world!" in result.output
