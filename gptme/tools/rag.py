"""
RAG (Retrieval-Augmented Generation) tool for context-aware assistance.

The RAG tool provides context-aware assistance by indexing and searching project documentation.

.. rubric:: Installation

The RAG tool requires the ``gptme-rag`` package. Install it with::

    pip install "gptme[rag]"

.. rubric:: Configuration

Configure RAG in your ``gptme.toml``::

    [rag]
    # Storage configuration
    index_path = "~/.cache/gptme/rag"  # Where to store the index
    collection = "gptme_docs"          # Collection name for documents

    # Context enhancement settings
    max_tokens = 2000                  # Maximum tokens for context window
    auto_context = true               # Enable automatic context enhancement
    min_relevance = 0.5               # Minimum relevance score for including context
    max_results = 5                   # Maximum number of results to consider

    # Cache configuration
    [rag.cache]
    max_embeddings = 10000            # Maximum number of cached embeddings
    max_searches = 1000               # Maximum number of cached search results
    embedding_ttl = 86400             # Embedding cache TTL in seconds (24h)
    search_ttl = 3600                # Search cache TTL in seconds (1h)

.. rubric:: Features

1. Manual Search and Indexing
   - Index project documentation with ``rag index``
   - Search indexed documents with ``rag search``
   - Check index status with ``rag status``

2. Automatic Context Enhancement
   - Automatically adds relevant context to user messages
   - Retrieves semantically similar documents
   - Manages token budget to avoid context overflow
   - Preserves conversation flow with hidden context messages

3. Performance Optimization
   - Intelligent caching system for embeddings and search results
   - Configurable cache sizes and TTLs
   - Automatic cache invalidation
   - Memory-efficient storage

.. rubric:: Benefits

- Better informed responses through relevant documentation
- Reduced need for manual context inclusion
- Automatic token management
- Seamless integration with conversation flow
"""

import logging
from pathlib import Path

from ..config import get_project_config
from ..message import Message
from .base import ConfirmFunc, ToolSpec, ToolUse

logger = logging.getLogger(__name__)

try:
    import gptme_rag  # fmt: skip

    _HAS_RAG = True
except ImportError:
    logger.debug("gptme-rag not installed, RAG tool will not be available")
    _HAS_RAG = False

indexer: "gptme_rag.Indexer | None" = None

instructions = """
Use RAG to index and search project documentation.

Commands:
- index [paths...] - Index documents in specified paths
- search <query> - Search indexed documents
- status - Show index status
"""

examples = f"""
User: Index the current directory
Assistant: Let me index the current directory with RAG.
{ToolUse("rag", ["index"], "").to_output()}
System: Indexed 1 paths

User: Search for documentation about functions
Assistant: I'll search for function-related documentation.
{ToolUse("rag", ["search", "function", "documentation"], "").to_output()}
System: ### docs/api.md
Functions are documented using docstrings...

User: Show index status
Assistant: I'll check the current status of the RAG index.
{ToolUse("rag", ["status"], "").to_output()}
System: Index contains 42 documents
"""


def execute_rag(code: str, args: list[str], confirm: ConfirmFunc) -> Message:
    """Execute RAG commands."""
    assert indexer is not None, "RAG indexer not initialized"
    command = args[0] if args else "help"

    if command == "help":
        return Message("system", "Available commands: index, search, status")
    elif command == "index":
        paths = args[1:] or ["."]
        for path in paths:
            indexer.index_directory(Path(path))
        return Message("system", f"Indexed {len(paths)} paths")
    elif command == "search":
        query = " ".join(args[1:])
        docs, _ = indexer.search(query)
        return Message(
            "system",
            "\n\n".join(
                f"### {doc.metadata['source']}\n{doc.content[:200]}..." for doc in docs
            ),
        )
    elif command == "status":
        return Message(
            "system", f"Index contains {indexer.collection.count()} documents"
        )
    else:
        return Message("system", f"Unknown command: {command}")


def init() -> ToolSpec:
    """Initialize the RAG tool."""
    config = get_project_config(Path.cwd())
    if config:
        # Initialize RAG with configuration
        global indexer
        import gptme_rag  # fmt: skip

        indexer = gptme_rag.Indexer(
            persist_directory=Path(
                config.rag.get("index_path", "~/.cache/gptme/rag")
            ).expanduser(),
            # TODO: use a better default collection name? (e.g. project name)
            collection_name=config.rag.get("collection", "gptme_docs"),
        )
    return tool


tool = ToolSpec(
    name="rag",
    desc="RAG (Retrieval-Augmented Generation) for context-aware assistance",
    instructions=instructions,
    examples=examples,
    block_types=["rag"],
    execute=execute_rag,
    available=_HAS_RAG,
    init=init,
)

__doc__ = tool.get_doc(__doc__)
