"""Tests for the RAG tool and context enhancement functionality."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from gptme.message import Message
from gptme.tools._rag_context import (
    Context,
    RAGManager,
    _clear_cache,
    _get_search_results,
    enhance_messages,
)
from gptme.tools.base import ToolSpec
from gptme.tools.rag import _HAS_RAG
from gptme.tools.rag import init as init_rag
from gptme.tools.rag import rag_index, rag_search, rag_status

pytest.importorskip("gptme_rag")

# Fixtures


@pytest.fixture(scope="function")
def index_path(tmp_path):
    """Create a temporary index path."""
    return tmp_path


@pytest.fixture(scope="function")
def temp_docs(tmp_path):
    """Create temporary test documents."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Test Document\nThis is a test document about Python functions.")

    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Another Document\nThis document discusses testing practices.")

    return tmp_path


@pytest.fixture
def mock_rag_manager(index_path):
    """Create a mock RAG manager that returns test contexts."""
    with patch("gptme.tools._rag_context.gptme_rag"):
        manager = RAGManager(
            index_path=index_path,
            collection="test",
        )
        # Create mock documents
        mock_docs = [
            Mock(
                content="This is a test document about Python functions.",
                metadata={"source": "doc1.md"},
            ),
            Mock(
                content="Documentation about testing practices.",
                metadata={"source": "doc2.md"},
            ),
        ]
        mock_results = {"distances": [[0.2, 0.4]]}  # 1 - distance = relevance

        # Mock the indexer's search method
        manager.indexer.search = Mock(return_value=(mock_docs, mock_results))

        # Mock get_context to return actual Context objects
        test_contexts = [
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
        manager.get_context = Mock(return_value=test_contexts)  # type: ignore

        return manager


@pytest.fixture
def mock_rag_manager_no_context(mock_rag_manager):
    """Create a RAG manager that returns no context."""
    mock_rag_manager.get_context = Mock(return_value=[])
    return mock_rag_manager


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the search cache before each test."""
    _clear_cache()


# RAG Tool Tests


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


@pytest.mark.slow
@pytest.mark.skipif(not _HAS_RAG, reason="gptme-rag not installed")
def test_rag_index_function(temp_docs, index_path, tmp_path):
    """Test the index function."""
    with (
        patch("gptme.tools.rag.get_project_config") as mock_config,
        patch("gptme.tools.rag.get_project_dir") as mock_project_dir,
    ):
        # Mock project dir to return the temp path
        mock_project_dir.return_value = tmp_path

        # Mock config to return an object with a proper .get method
        class MockConfig:
            def __init__(self):
                self.rag = {"index_path": str(index_path), "collection": tmp_path.name}

            def get(self, key, default=None):
                return self.rag.get(key, default)

        mock_config.return_value = MockConfig()

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
def test_rag_search_function(temp_docs, index_path, tmp_path):
    """Test the search function."""
    with (
        patch("gptme.tools.rag.get_project_config") as mock_config,
        patch("gptme.tools.rag.get_project_dir") as mock_project_dir,
    ):
        # Mock project dir to return the temp path
        mock_project_dir.return_value = tmp_path

        # Mock config to return an object with a proper .get method
        class MockConfig:
            def __init__(self):
                self.rag = {"index_path": str(index_path), "collection": tmp_path.name}

            def get(self, key, default=None):
                return self.rag.get(key, default)

        mock_config.return_value = MockConfig()

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
def test_rag_status_function(temp_docs, index_path, tmp_path):
    """Test the status function."""
    with (
        patch("gptme.tools.rag.get_project_config") as mock_config,
        patch("gptme.tools.rag.get_project_dir") as mock_project_dir,
    ):
        # Mock project dir to return the temp path
        mock_project_dir.return_value = tmp_path

        # Mock config to return an object with a proper .get method
        class MockConfig:
            def __init__(self):
                self.rag = {"index_path": str(index_path), "collection": tmp_path.name}

            def get(self, key, default=None):
                return self.rag.get(key, default)

        mock_config.return_value = MockConfig()

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


# Context Enhancement Tests


def test_search_caching(mock_rag_manager):
    """Test that search results are properly cached."""
    query = "test query"
    n_results = 5

    # First search should use the manager
    docs, results = mock_rag_manager.search(query, n_results)
    assert mock_rag_manager.indexer.search.call_count == 1

    # Cache should be populated
    cached = _get_search_results(query, n_results)
    assert cached is not None
    assert cached == (docs, results)

    # Second search should use cache
    docs2, results2 = mock_rag_manager.search(query, n_results)
    assert mock_rag_manager.indexer.search.call_count == 1  # No additional calls
    assert (docs2, results2) == (docs, results)


def test_enhance_messages_with_context(mock_rag_manager):
    """Test that messages are enhanced with context."""
    with patch("gptme.tools._rag_context.RAGManager", return_value=mock_rag_manager):
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
    with patch("gptme.tools._rag_context._HAS_RAG", False):
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is a programming language"),
        ]

        enhanced = enhance_messages(messages)

        # Should be unchanged when RAG is not available
        assert len(enhanced) == len(messages)
        assert enhanced == messages


def test_enhance_messages_error_handling(mock_rag_manager):
    """Test that errors in context enhancement are handled gracefully."""
    mock_rag_manager.get_context.side_effect = Exception("Test error")

    with patch("gptme.tools._rag_context.RAGManager", return_value=mock_rag_manager):
        messages = [
            Message("user", "Tell me about Python"),
            Message("assistant", "Python is great"),
        ]

        # Should not raise an exception
        enhanced = enhance_messages(messages)

        # Messages should be unchanged when enhancement fails
        assert len(enhanced) == len(messages)
        assert enhanced == messages


def test_rag_manager_initialization():
    """Test RAG manager initialization with and without gptme-rag."""
    # Test when gptme-rag is not available
    with patch("gptme.tools._rag_context._HAS_RAG", False):
        with pytest.raises(ImportError):
            RAGManager()

    # Test when gptme-rag is available
    with patch("gptme.tools._rag_context._HAS_RAG", True):
        with patch("gptme.tools._rag_context.gptme_rag") as mock_rag:
            manager = RAGManager()
            assert isinstance(manager, RAGManager)
            mock_rag.Indexer.assert_called_once()


def test_get_context_with_relevance_filter(mock_rag_manager):
    """Test that get_context properly filters by relevance."""
    with patch("gptme.tools._rag_context.RAGManager", return_value=mock_rag_manager):
        # Create test contexts with different relevance scores
        contexts = [
            Context(content="High relevance", source="high.md", relevance=0.8),
            Context(content="Low relevance", source="low.md", relevance=0.4),
        ]

        # Mock get_context directly instead of search
        mock_rag_manager.get_context = Mock(
            return_value=[ctx for ctx in contexts if ctx.relevance >= 0.7]
        )

        messages = [Message("user", "test query")]
        enhanced = enhance_messages(messages)

        # Should only include the high relevance context
        assert len(enhanced) == 2  # Original message + context message
        assert "high.md" in enhanced[0].content
        assert "low.md" not in enhanced[0].content


def test_auto_context_disabled(mock_rag_manager):
    """Test that context enhancement respects auto_context setting."""
    mock_rag_manager.auto_context = False
    mock_rag_manager.get_context = Mock(return_value=[])  # Should not be called

    messages = [Message("user", "Tell me about Python")]
    enhanced = enhance_messages(messages)

    # No context should be added when auto_context is False
    assert len(enhanced) == 1
    assert enhanced[0].role == "user"
    assert not mock_rag_manager.get_context.called
