"""Shared RAG context functionality."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_project_config
from ..message import Message

logger = logging.getLogger(__name__)

# Constant collection name to ensure consistency
DEFAULT_COLLECTION = "gptme-default"

try:
    import gptme_rag  # type: ignore # fmt: skip

    _HAS_RAG = True
except ImportError:
    logger.debug("gptme-rag not installed, RAG functionality will not be available")
    _HAS_RAG = False


# Shared RAG manager instance
_rag_manager: "RAGManager | None" = None

# Simple in-memory cache for search results
_search_cache: dict[str, tuple[list[Any], dict]] = {}


def get_rag_manager() -> "RAGManager":
    """Get or create the shared RAG manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
    return _rag_manager


def _get_search_results(query: str, n_results: int) -> tuple[list[Any], dict] | None:
    """Get cached search results."""
    return _search_cache.get(f"{query}::{n_results}")


def _set_search_results(
    query: str, n_results: int, results: tuple[list[Any], dict]
) -> None:
    """Cache search results."""
    _search_cache[f"{query}::{n_results}"] = results


@dataclass
class Context:
    """Context information to be added to messages."""

    content: str
    source: str
    relevance: float


class ContextProvider(ABC):
    """Base class for context providers."""

    @abstractmethod
    def get_context(self, query: str, max_tokens: int = 1000) -> list[Context]:
        """Get relevant context for a query."""
        pass


class RAGManager:
    """Manages RAG functionality for both context enhancement and tool use."""

    def __init__(self, index_path: Path | None = None, collection: str | None = None):
        if not _HAS_RAG:
            raise ImportError("gptme-rag not installed")

        # Load config
        config = get_project_config(Path.cwd())
        self.config = config.rag if config and config.rag else {}

        # Use config values if not overridden by parameters
        self.index_path = index_path or Path("~/.cache/gptme/rag").expanduser()
        self.collection = collection or DEFAULT_COLLECTION

        # Initialize the indexer
        self.indexer = gptme_rag.Indexer(
            persist_directory=self.index_path,
            collection_name=self.collection,
        )

        # Context enhancement configuration
        self.context_assembler = gptme_rag.ContextAssembler(
            max_tokens=self.config.get("max_tokens", 2000)
        )
        self.auto_context = self.config.get("auto_context", True)
        self.min_relevance = self.config.get("min_relevance", 0.5)
        self.max_results = self.config.get("max_results", 5)

    def search(
        self, query: str, n_results: int | None = None
    ) -> tuple[list[Any], dict]:
        """Search the index with caching."""
        n_results = n_results or self.max_results

        # Check cache
        if cached := _get_search_results(query, n_results):
            logger.debug(f"Using cached search results for query: {query}")
            return cached

        # Perform search
        docs, results = self.indexer.search(query, n_results=n_results)

        # Cache results
        _set_search_results(query, n_results, (docs, results))
        logger.debug(f"Cached search results for query: {query}")

        return docs, results

    def get_context(self, query: str, max_tokens: int = 1000) -> list[Context]:
        """Get relevant context using RAG."""
        if not self.auto_context:
            return []

        try:
            docs, results = self.search(query)
            contexts = []

            for i, doc in enumerate(docs):
                # Calculate relevance score (1 - distance)
                relevance = 1.0 - results["distances"][0][i]

                # Skip if below minimum relevance
                if relevance < self.min_relevance:
                    continue

                contexts.append(
                    Context(
                        content=doc.content,
                        source=doc.metadata.get("source", "unknown"),
                        relevance=relevance,
                    )
                )

            # Sort by relevance
            contexts.sort(key=lambda x: x.relevance, reverse=True)
            return contexts

        except Exception as e:
            logger.warning(f"Error getting RAG context: {e}")
            return []

    def index_directory(self, path: Path, **kwargs) -> int:
        """Index a directory and return number of documents indexed."""
        return self.indexer.index_directory(path, **kwargs)

    def get_document_count(self) -> int:
        """Get the total number of documents in the index."""
        return self.indexer.collection.count()


def rag_enhance_messages(messages: list[Message]) -> list[Message]:
    """Enhance messages with context from available providers."""
    if not _HAS_RAG:
        return messages

    try:
        rag_manager = RAGManager()
    except Exception as e:
        logger.warning(f"Failed to initialize RAG manager: {e}")
        return messages

    enhanced_messages = []

    for msg in messages:
        if msg.role == "user":
            # Get context from RAG
            try:
                contexts = rag_manager.get_context(msg.content)

                # Add context as a system message before the user message
                if contexts:
                    context_msg = "Relevant context:\n\n"
                    for ctx in contexts:
                        context_msg += f"### {ctx.source}\n{ctx.content}\n\n"

                    enhanced_messages.append(
                        Message(role="system", content=context_msg, hide=True)
                    )
            except Exception as e:
                logger.warning(f"Error getting context: {e}")

        enhanced_messages.append(msg)

    return enhanced_messages
