"""Tests for the RAG tool."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from gptme import Message
from gptme.tools.base import ToolSpec
from gptme.tools.rag import _HAS_RAG
from gptme.tools.rag import init as init_rag


@pytest.fixture
def temp_docs(tmp_path):
    """Create temporary test documents."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Test Document\nThis is a test document about Python functions.")

    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Another Document\nThis document discusses testing practices.")

    return tmp_path


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_tool_init():
    """Test RAG tool initialization."""
    tool = init_rag()
    assert isinstance(tool, ToolSpec)
    assert tool.name == "rag"
    assert tool.available is True


def test_rag_tool_init_without_gptme_rag():
    """Test RAG tool initialization when gptme-rag is not available."""
    with patch("gptme.tools.rag._HAS_RAG", False):
        tool = init_rag()
        assert isinstance(tool, ToolSpec)
        assert tool.name == "rag"
        assert tool.available is False


def _m2str(tool_execute: Generator[Message, None, None] | Message) -> str:
    """Convert a execute() call to a string."""
    if isinstance(tool_execute, Generator):
        return tool_execute.send(None).content
    elif isinstance(tool_execute, Message):
        return tool_execute.content


def noconfirm(*args, **kwargs):
    return True


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_index_command(temp_docs):
    """Test the index command."""
    tool = init_rag()
    assert tool.execute
    result = _m2str(tool.execute("", ["index", str(temp_docs)], noconfirm))
    assert "Indexed" in result

    # Check status after indexing
    result = _m2str(tool.execute("", ["status"], noconfirm))
    assert "Index contains" in result
    assert "2" in result  # Should have indexed 2 documents


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_search_command(temp_docs):
    """Test the search command."""
    tool = init_rag()
    assert tool.execute
    # Index first
    _m2str(tool.execute("", ["index", str(temp_docs)], noconfirm))

    # Search for Python
    result = _m2str(tool.execute("", ["search", "Python"], noconfirm))
    assert "doc1.md" in result
    assert "Python functions" in result

    # Search for testing
    result = _m2str(tool.execute("", ["search", "testing"], noconfirm))
    assert "doc2.md" in result
    assert "testing practices" in result


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_help_command():
    """Test the help command."""
    tool = init_rag()
    assert tool.execute
    result = _m2str(tool.execute("", ["help"], noconfirm))
    assert "Available commands" in result
    assert "index" in result
    assert "search" in result
    assert "status" in result


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_invalid_command():
    """Test invalid command handling."""
    tool = init_rag()
    assert tool.execute
    result = _m2str(tool.execute("", ["invalid"], noconfirm))
    assert "Unknown command" in result
