"""Tests for the RAG tool."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from gptme.tools.base import ToolSpec
from gptme.tools.rag import _HAS_RAG
from gptme.tools.rag import init as init_rag
from gptme.tools.rag import rag_index, rag_search, rag_status


@pytest.fixture
def temp_docs(tmp_path):
    """Create temporary test documents."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Test Document\nThis is a test document about Python functions.")

    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Another Document\nThis document discusses testing practices.")

    return tmp_path


@pytest.mark.timeout(func_only=True)
@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_tool_init():
    """Test RAG tool initialization."""
    tool = init_rag()
    assert isinstance(tool, ToolSpec)
    assert tool.name == "rag"
    assert tool.available is True


def test_rag_tool_init_without_gptme_rag():
    """Test RAG tool initialization when gptme-rag is not available."""
    tool = init_rag()
    with (
        patch("gptme.tools.rag._HAS_RAG", False),
        patch("gptme.tools.rag.tool", replace(tool, available=False)),
    ):
        tool = init_rag()
        assert isinstance(tool, ToolSpec)
        assert tool.name == "rag"
        assert tool.available is False


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_index_function(temp_docs, tmp_path):
    """Test the index function."""
    with patch("gptme.tools.rag.get_project_config") as mock_config:
        mock_config.return_value.rag = {
            "index_path": str(tmp_path),
            "collection": "test",
        }

        # Initialize RAG
        init_rag()

        # Test indexing with specific path
        result = rag_index(str(temp_docs))
        assert "Indexed 1 paths" in result

        # Test indexing with default path
        # FIXME: this is really slow in the gptme directory,
        # since it contains a lot of files (which are in gitignore, but not respected)
        result = rag_index(glob="**/*.py")
        assert "Indexed 1 paths" in result


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_search_function(temp_docs, tmp_path):
    """Test the search function."""
    with patch("gptme.tools.rag.get_project_config") as mock_config:
        mock_config.return_value.rag = {
            "index_path": str(tmp_path),
            "collection": "test",
        }

        # Initialize RAG and index documents
        init_rag()
        rag_index(str(temp_docs))

        # Search for Python
        result = rag_search("Python")
        assert "doc1.md" in result
        assert "Python functions" in result

        # Search for testing
        result = rag_search("testing")
        assert "doc2.md" in result
        assert "testing practices" in result


@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_status_function(temp_docs, tmp_path):
    """Test the status function."""
    with patch("gptme.tools.rag.get_project_config") as mock_config:
        mock_config.return_value.rag = {
            "index_path": str(tmp_path),
            "collection": "test",
        }

        # Initialize RAG
        init_rag()

        # Check initial status
        result = rag_status()
        assert "Index contains" in result
        assert "0" in result

        # Index documents and check status again
        rag_index(str(temp_docs))
        result = rag_status()
        assert "Index contains" in result
        assert "2" in result  # Should have indexed 2 documents
