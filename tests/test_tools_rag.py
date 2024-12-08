"""Tests for the RAG tool."""

from unittest.mock import patch

import gptme.tools._rag_context
import gptme.tools.rag
import pytest
from gptme.message import Message
from gptme.tools._rag_context import rag_enhance_messages
from gptme.tools.rag import _HAS_RAG
from gptme.tools.rag import init as init_rag
from gptme.tools.rag import rag_index, rag_search


@pytest.fixture(autouse=True)
def reset_rag():
    """Reset the RAG manager and init state before and after each test."""

    gptme.tools._rag_context._rag_manager = None
    gptme.tools.rag._init_run = False
    yield
    gptme.tools._rag_context._rag_manager = None
    gptme.tools.rag._init_run = False


@pytest.fixture(scope="function")
def temp_docs(tmp_path):
    """Create temporary test documents."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Test Document\nThis is a test document about Python functions.")

    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Another Document\nThis document discusses testing practices.")

    return tmp_path


def test_rag_tool_init_without_gptme_rag():
    """Test RAG tool initialization when gptme-rag is not available."""
    with (
        patch("gptme.tools.rag._HAS_RAG", False),
        patch("gptme.tools.rag.get_project_config") as mock_config,
    ):
        # Mock config to disable RAG
        mock_config.return_value.rag = {"enabled": False}

        tool = init_rag()
        assert tool.name == "rag"
        assert tool.available is False


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_tool_functionality(temp_docs):
    """Test basic RAG tool functionality."""
    with (
        patch("gptme.tools.rag.get_project_config") as mock_config,
        patch("gptme.tools.rag.get_project_dir") as mock_project_dir,
    ):
        # Mock project dir to return a path
        mock_project_dir.return_value = temp_docs

        # Mock config to enable RAG
        class MockConfig:
            def __init__(self):
                self.rag = {"enabled": True}

        mock_config.return_value = MockConfig()

        # Initialize RAG
        tool = init_rag()
        assert tool.available is True

        # Test indexing
        index_result = rag_index(str(temp_docs))
        assert "Indexed" in index_result

        # Test searching
        search_result = rag_search("test document")
        assert "test document" in search_result.lower()


def test_enhance_messages_no_rag():
    """Test that enhancement works even without RAG available."""
    messages = [
        Message("user", "Tell me about Python"),
        Message("assistant", "Python is a programming language"),
    ]

    enhanced = rag_enhance_messages(messages)

    # Should be unchanged when RAG is not available
    assert len(enhanced) == len(messages)
    assert enhanced == messages
