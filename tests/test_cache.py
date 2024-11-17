"""Tests for the caching system."""

import time
from unittest.mock import Mock, patch


from gptme.cache import Cache, RAGCache, get_cache
from gptme.context import RAGContextProvider


def test_cache_basic_operations():
    """Test basic cache operations."""
    cache = Cache(max_size=2)

    # Set and get
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    # Missing key
    assert cache.get("missing") is None

    # Clear
    cache.clear()
    assert cache.get("key1") is None


def test_cache_ttl():
    """Test cache TTL functionality."""
    cache = Cache(default_ttl=0.1)  # 100ms TTL

    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    # Wait for TTL to expire
    time.sleep(0.2)
    assert cache.get("key1") is None


def test_cache_size_limit():
    """Test cache size limiting."""
    cache = Cache(max_size=2)

    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")  # Should evict oldest entry

    assert cache.get("key1") is None  # Evicted
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"


def test_rag_cache_search_results():
    """Test RAG cache with search results."""
    cache = RAGCache()

    # Mock search results
    docs = [Mock(content="test content")]
    results = {"distances": [[0.1]]}

    # Cache results
    cache.set_search_results("test query", 5, (docs, results))

    # Get cached results
    cached = cache.get_search_results("test query", 5)
    assert cached is not None
    cached_docs, cached_results = cached

    assert len(cached_docs) == 1
    assert cached_docs[0].content == "test content"
    assert cached_results["distances"] == [[0.1]]


def test_rag_cache_embeddings():
    """Test RAG cache with embeddings."""
    cache = RAGCache()

    embedding = [0.1, 0.2, 0.3]
    cache.set_embedding("test text", embedding)

    cached = cache.get_embedding("test text")
    assert cached == embedding


def test_get_cache_singleton():
    """Test that get_cache returns a singleton instance."""
    cache1 = get_cache()
    cache2 = get_cache()
    assert cache1 is cache2


def test_rag_context_provider_with_cache():
    """Test RAG context provider with caching."""
    with patch("gptme.context.RAGContextProvider._has_rag", True):
        provider = RAGContextProvider()

        # Mock the indexer's search method
        mock_docs = [Mock(content="test content", metadata={"source": "test.md"})]
        mock_results = {"distances": [[0.1]]}
        provider.indexer.search = Mock(return_value=(mock_docs, mock_results))

        # First call should use indexer
        contexts = provider.get_context("test query")
        assert len(contexts) == 1
        assert provider.indexer.search.call_count == 1

        # Second call should use cache
        contexts = provider.get_context("test query")
        assert len(contexts) == 1
        # Search should not be called again
        assert provider.indexer.search.call_count == 1
