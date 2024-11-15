"""Context providers for enhancing messages with relevant context."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import gptme_rag

from .cache import get_cache
from .config import get_project_config
from .message import Message

logger = logging.getLogger(__name__)


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


class RAGContextProvider(ContextProvider):
    """Context provider using RAG."""

    def __init__(self):
        try:
            self._has_rag = True

            config = get_project_config(Path.cwd())
            assert config

            # Storage configuration
            self.indexer = gptme_rag.Indexer(
                persist_directory=config.rag.get("index_path", "~/.cache/gptme/rag"),
                collection_name=config.rag.get("collection", "gptme_docs"),
            )

            # Context enhancement configuration
            self.context_assembler = gptme_rag.ContextAssembler(
                max_tokens=config.rag.get("max_tokens", 2000)
            )
            self.auto_context = config.rag.get("auto_context", True)
            self.min_relevance = config.rag.get("min_relevance", 0.5)
            self.max_results = config.rag.get("max_results", 5)
        except ImportError:
            logger.debug(
                "gptme-rag not installed, RAG context provider will not be available"
            )
            self._has_rag = False

    def get_context(self, query: str, max_tokens: int = 1000) -> list[Context]:
        """Get relevant context using RAG."""
        if not self._has_rag or not self.auto_context:
            return []

        try:
            # Check cache first
            cache = get_cache()
            cached_results = cache.get_search_results(query, self.max_results)

            if cached_results:
                docs, results = cached_results
                logger.debug(f"Using cached search results for query: {query}")
            else:
                # Search with configured limits
                docs, results = self.indexer.search(query, n_results=self.max_results)
                # Cache the results
                cache.set_search_results(query, self.max_results, (docs, results))
                logger.debug(f"Cached search results for query: {query}")

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


def enhance_messages(messages: list[Message]) -> list[Message]:
    """Enhance messages with context from available providers."""
    providers = [RAGContextProvider()]
    enhanced_messages = []

    for msg in messages:
        if msg.role == "user":
            # Get context from all providers
            contexts = []
            for provider in providers:
                try:
                    contexts.extend(provider.get_context(msg.content))
                except Exception as e:
                    logger.warning(f"Error getting context from provider: {e}")

            # Add context as a system message before the user message
            if contexts:
                context_msg = "Relevant context:\n\n"
                for ctx in contexts:
                    context_msg += f"### {ctx.source}\n{ctx.content}\n\n"

                enhanced_messages.append(
                    Message(role="system", content=context_msg, hide=True)
                )

        enhanced_messages.append(msg)

    return enhanced_messages
