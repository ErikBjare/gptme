"""Caching system for RAG functionality."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import get_project_config

logger = logging.getLogger(__name__)


# Global cache instance
_cache: Optional["RAGCache"] = None


def get_cache() -> "RAGCache":
    """Get the global RAG cache instance."""
    global _cache
    if _cache is None:
        _cache = RAGCache()
    return _cache


@dataclass
class CacheEntry:
    """Entry in the cache with metadata."""

    data: Any
    timestamp: float
    ttl: float


class Cache:
    """Simple cache with TTL and size limits."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry.timestamp > entry.ttl:
            # Entry expired
            del self._cache[key]
            return None

        return entry.data

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a value in the cache."""
        # Enforce size limit
        if len(self._cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self._cache.items(), key=lambda x: x[1].timestamp)[0]
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(
            data=value, timestamp=time.time(), ttl=ttl or self.default_ttl
        )

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class RAGCache:
    """Cache for RAG functionality."""

    def __init__(self):
        config = get_project_config(Path.cwd())
        assert config
        cache_config = config.rag.get("rag", {}).get("cache", {})

        # Initialize caches with configured limits
        self.embedding_cache = Cache(
            max_size=cache_config.get("max_embeddings", 10000),
            default_ttl=cache_config.get("embedding_ttl", 86400),  # 24 hours
        )
        self.search_cache = Cache(
            max_size=cache_config.get("max_searches", 1000),
            default_ttl=cache_config.get("search_ttl", 3600),  # 1 hour
        )

    @staticmethod
    def _make_search_key(query: str, n_results: int) -> str:
        """Create a cache key for a search query."""
        return f"{query}::{n_results}"

    def get_embedding(self, text: str) -> list[float] | None:
        """Get cached embedding for text."""
        return self.embedding_cache.get(text)

    def set_embedding(self, text: str, embedding: list[float]) -> None:
        """Cache embedding for text."""
        self.embedding_cache.set(text, embedding)

    def get_search_results(
        self, query: str, n_results: int
    ) -> tuple[list[Any], dict[str, Any]] | None:
        """Get cached search results."""
        key = self._make_search_key(query, n_results)
        return self.search_cache.get(key)

    def set_search_results(
        self, query: str, n_results: int, results: tuple[list[Any], dict[str, Any]]
    ) -> None:
        """Cache search results."""
        key = self._make_search_key(query, n_results)
        self.search_cache.set(key, results)

    def clear(self) -> None:
        """Clear all caches."""
        self.embedding_cache.clear()
        self.search_cache.clear()
