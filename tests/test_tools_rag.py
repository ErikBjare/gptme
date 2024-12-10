"""Tests for the RAG tool."""

from unittest.mock import patch

from gptme.message import Message
from gptme.tools.rag import init as init_rag
from gptme.tools.rag import rag_enhance_messages


def test_rag_tool_init_without_gptme_rag():
    """Test RAG tool initialization when gptme-rag is not available."""
    with (
        patch("subprocess.run", side_effect=FileNotFoundError),
        patch("gptme.tools.rag.get_project_config") as mock_config,
    ):
        mock_config.return_value.rag = {"enabled": False}
        tool = init_rag()
        assert tool.name == "rag"
        assert tool.available is False


def test_enhance_messages_no_rag():
    """Test that enhancement works even without RAG available."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is a programming language"),
        ]

        enhanced = rag_enhance_messages(messages)

        # Should be unchanged when RAG is not available
        assert len(enhanced) == len(messages)
        assert enhanced == messages


def test_enhance_messages_disabled():
    """Test message enhancement when RAG is disabled in config."""
    with (
        patch("subprocess.run", return_value=type("Proc", (), {"returncode": 0})),
        patch("gptme.tools.rag.get_project_config") as mock_config,
    ):
        mock_config.return_value.rag = {"enabled": False}
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is a programming language"),
        ]

        enhanced = rag_enhance_messages(messages)

        # Should be unchanged when RAG is disabled
        assert len(enhanced) == len(messages)
        assert enhanced == messages
