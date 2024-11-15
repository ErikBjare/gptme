"""Tests for context enhancement functionality."""

import pytest
from unittest.mock import Mock, patch

from gptme.context import Context, RAGContextProvider, enhance_messages
from gptme.message import Message


@pytest.fixture
def mock_rag_provider():
    """Create a mock RAG provider that returns test contexts."""
    provider = Mock()
    provider.get_context.return_value = [
        Context(
            content="This is a test document about Python functions.",
            source="doc1.md",
            relevance=0.8,
        ),
        Context(
            content="Documentation about testing practices.",
            source="doc2.md",
            relevance=0.6,
        ),
    ]
    return provider


def test_enhance_messages_with_context(mock_rag_provider):
    """Test that messages are enhanced with context."""
    with patch("gptme.context.RAGContextProvider", return_value=mock_rag_provider):
        messages = [
            Message("system", "Initial system message"),
            Message("user", "Tell me about Python functions"),
            Message("assistant", "Here's what I know about functions..."),
        ]

        enhanced = enhance_messages(messages)

        # Should have one extra message for the context
        assert len(enhanced) == 4

        # Check that context was added before the user message
        assert enhanced[0].role == "system"  # Original system message
        assert enhanced[1].role == "system"  # Added context
        assert "Relevant context:" in enhanced[1].content
        assert "doc1.md" in enhanced[1].content
        assert "doc2.md" in enhanced[1].content
        assert enhanced[1].hide is True  # Context should be hidden

        # Original messages should remain unchanged
        assert enhanced[2].role == "user"
        assert enhanced[3].role == "assistant"


def test_enhance_messages_no_rag():
    """Test that enhancement works even without RAG available."""
    with patch("gptme.context.RAGContextProvider._has_rag", False):
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is a programming language"),
        ]

        enhanced = enhance_messages(messages)

        # Should be unchanged when RAG is not available
        assert len(enhanced) == len(messages)
        assert enhanced == messages


def test_enhance_messages_error_handling(mock_rag_provider):
    """Test that errors in context providers are handled gracefully."""
    mock_rag_provider.get_context.side_effect = Exception("Test error")

    with patch("gptme.context.RAGContextProvider", return_value=mock_rag_provider):
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is great"),
        ]

        # Should not raise an exception
        enhanced = enhance_messages(messages)

        # Messages should be unchanged when provider fails
        assert len(enhanced) == len(messages)
        assert enhanced == messages


def test_rag_provider_initialization():
    """Test RAG provider initialization with and without gptme-rag."""
    # Test when gptme-rag is not available
    with patch("gptme.context.RAGContextProvider._has_rag", False):
        provider = RAGContextProvider()
        assert provider.get_context("test query") == []

    # Test when gptme-rag is available
    with patch("gptme.context.RAGContextProvider._has_rag", True):
        with patch("gptme.context.gptme_rag") as mock_rag:
            provider = RAGContextProvider()
            assert provider._has_rag is True
            mock_rag.Indexer.assert_called_once()
