"""RAG tool for context-aware assistance."""

import logging
from pathlib import Path

import gptme_rag

from ..config import get_project_config
from ..message import Message
from .base import ConfirmFunc, ToolSpec

logger = logging.getLogger(__name__)

try:
    _HAS_RAG = True
except ImportError:
    logger.debug("gptme-rag not installed, RAG tool will not be available")
    _HAS_RAG = False

indexer: gptme_rag.Indexer | None = None


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
        docs = indexer.search(query)
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


def init_rag() -> ToolSpec:
    """Initialize the RAG tool."""
    if not _HAS_RAG:
        return ToolSpec(
            name="rag",
            desc="RAG (Retrieval-Augmented Generation) for context-aware assistance",
            available=False,
        )

    config = get_project_config(Path.cwd())
    if config:
        # Initialize RAG with configuration
        global indexer
        indexer = gptme_rag.Indexer(
            persist_directory=Path(
                config.rag.get("index_path", "~/.cache/gptme/rag")
            ).expanduser(),
            # TODO: use a better default collection name? (e.g. project name)
            collection_name=config.rag.get("collection", "gptme_docs"),
        )

    return ToolSpec(
        name="rag",
        desc="RAG (Retrieval-Augmented Generation) for context-aware assistance",
        instructions="""Use RAG to index and search project documentation.

Commands:
- index [paths...] - Index documents in specified paths
- search <query> - Search indexed documents
- status - Show index status""",
        examples="""User: Index the current directory
Assistant: Let me index the current directory with RAG.
```rag index```
System: Indexed 1 paths

User: Search for documentation about functions
Assistant: I'll search for function-related documentation.
```rag search function documentation```
System: ### docs/api.md
Functions are documented using docstrings...

User: Show index status
Assistant: I'll check the current status of the RAG index.
```rag status```
System: Index contains 42 documents""",
        block_types=["rag"],
        execute=execute_rag,
        available=True,
    )


tool = init_rag()
