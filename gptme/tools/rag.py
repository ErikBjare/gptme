"""
RAG (Retrieval-Augmented Generation) tool for context-aware assistance.

The RAG tool provides context-aware assistance by indexing and searching project documentation.

.. rubric:: Installation

The RAG tool requires the ``gptme-rag`` package. Install it with::

    pip install "gptme[rag]"

.. rubric:: Configuration

Configure RAG in your ``gptme.toml``::

    [rag]
    enabled = true

.. rubric:: Features

1. Manual Search and Indexing

   - Index project documentation with ``rag_index``
   - Search indexed documents with ``rag_search``
   - Check index status with ``rag_status``

2. Automatic Context Enhancement

   - Automatically adds relevant context to user messages
   - Retrieves semantically similar documents
   - Manages token budget to avoid context overflow
   - Preserves conversation flow with hidden context messages

3. Performance Optimization

   - Intelligent caching system for embeddings and search results
   - Memory-efficient storage

.. rubric:: Benefits

- Better informed responses through relevant documentation
- Reduced need for manual context inclusion
- Automatic token management
- Seamless integration with conversation flow
"""

import logging
from dataclasses import replace
from pathlib import Path

from ..config import get_project_config
from ..util import get_project_dir
from ._rag_context import _HAS_RAG, get_rag_manager
from .base import ToolSpec, ToolUse

logger = logging.getLogger(__name__)

instructions = """
Use RAG to index and search project documentation.
"""

examples = f"""
User: Index the current directory
Assistant: Let me index the current directory with RAG.
{ToolUse("ipython", [], "rag_index()").to_output()}
System: Indexed 1 paths

User: Search for documentation about functions
Assistant: I'll search for function-related documentation.
{ToolUse("ipython", [], 'rag_search("function documentation")').to_output()}
System: ### docs/api.md
Functions are documented using docstrings...

User: Show index status
Assistant: I'll check the current status of the RAG index.
{ToolUse("ipython", [], "rag_status()").to_output()}
System: Index contains 42 documents
"""


def rag_index(*paths: str, glob: str | None = None) -> str:
    """Index documents in specified paths."""
    manager = get_rag_manager()
    paths = paths or (".",)
    kwargs = {"glob_pattern": glob} if glob else {}
    total_docs = 0
    for path in paths:
        total_docs += manager.index_directory(Path(path), **kwargs)
    return f"Indexed {len(paths)} paths ({total_docs} documents)"


def rag_search(query: str) -> str:
    """Search indexed documents."""
    manager = get_rag_manager()
    docs, _ = manager.search(query)
    return "\n\n".join(
        f"### {doc.metadata['source']}\n{doc.content[:200]}..." for doc in docs
    )


def rag_status() -> str:
    """Show index status."""
    manager = get_rag_manager()
    return f"Index contains {manager.get_document_count()} documents"


_init_run = False


def init() -> ToolSpec:
    """Initialize the RAG tool."""
    global _init_run
    if _init_run:
        return tool
    _init_run = True

    if not tool.available:
        return tool

    project_dir = get_project_dir()
    if project_dir and (config := get_project_config(project_dir)):
        enabled = config.rag.get("enabled", False)
        if not enabled:
            logger.debug("RAG not enabled in the project configuration")
            return replace(tool, available=False)
    else:
        logger.debug("Project configuration not found, not enabling")
        return replace(tool, available=False)

    # Initialize the shared RAG manager
    get_rag_manager()
    return tool


tool = ToolSpec(
    name="rag",
    desc="RAG (Retrieval-Augmented Generation) for context-aware assistance",
    instructions=instructions,
    examples=examples,
    functions=[rag_index, rag_search, rag_status],
    available=_HAS_RAG,
    init=init,
)

__doc__ = tool.get_doc(__doc__)
