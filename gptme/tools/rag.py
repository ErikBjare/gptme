"""
RAG (Retrieval-Augmented Generation) tool for context-aware assistance.

The RAG tool provides context-aware assistance by indexing and searching project documentation.

.. rubric:: Installation

The RAG tool requires the ``gptme-rag`` CLI to be installed::

    pipx install gptme-rag

.. rubric:: Configuration

Configure RAG in your ``gptme.toml``::

    [rag]
    enabled = true
    post_process = false # Whether to post-process the context with an LLM to extract the most relevant information
    post_process_model = "openai/gpt-4-turbo" # Which model to use for post-processing
    post_process_prompt = "" # Optional prompt to use for post-processing (overrides default prompt)

.. rubric:: Features

1. Manual Search and Indexing
   - Index project documentation with ``rag_index``
   - Search indexed documents with ``rag_search``
   - Check index status with ``rag_status``

2. Automatic Context Enhancement
   - Retrieves semantically similar documents
   - Preserves conversation flow with hidden context messages
"""

import logging
import shutil
import subprocess
import time
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from ..config import RagConfig, get_project_config
from ..message import Message
from ..util import get_project_dir
from ..llm import _chat_complete
from .base import ToolSpec, ToolUse

logger = logging.getLogger(__name__)

instructions = """
Use RAG to index and search project documentation.
"""


def examples(tool_format):
    return f"""
User: Index the current directory
Assistant: Let me index the current directory with RAG.
{ToolUse("ipython", [], "rag_index()").to_output(tool_format)}
System: Indexed 1 paths

User: Search for documentation about functions
Assistant: I'll search for function-related documentation.
{ToolUse("ipython", [], 'rag_search("function documentation")').to_output(tool_format)}
System: ### docs/api.md
Functions are documented using docstrings...

User: Show index status
Assistant: I'll check the current status of the RAG index.
{ToolUse("ipython", [], "rag_status()").to_output(tool_format)}
System: Index contains 42 documents
"""


@lru_cache
def _has_gptme_rag() -> bool:
    """Check if gptme-rag is available in PATH."""
    return shutil.which("gptme-rag") is not None


def _run_rag_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a gptme-rag command and handle errors."""
    start = time.monotonic()
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"gptme-rag command failed: {e.stderr}")
        raise RuntimeError(f"gptme-rag command failed: {e.stderr}") from e
    finally:
        cmd_str = " ".join(cmd)
        logger.info(
            f"Ran RAG: `{cmd_str[:100] if len(cmd_str) > 100 else cmd_str}` in {time.monotonic() - start:.2f}s"
        )


def rag_index(*paths: str, glob: str | None = None) -> str:
    """Index documents in specified paths."""
    paths = paths or (".",)
    cmd = ["gptme-rag", "index"]
    cmd.extend(paths)
    if glob:
        cmd.extend(["--glob", glob])

    result = _run_rag_cmd(cmd)
    return result.stdout.strip()


def rag_search(query: str, return_full: bool = False) -> str:
    """Search indexed documents."""
    cmd = ["gptme-rag", "search", query]
    if return_full:
        # shows full context of the search results
        cmd.append("--format full")

    result = _run_rag_cmd(cmd)
    return result.stdout.strip()


def rag_status() -> str:
    """Show index status."""
    cmd = ["gptme-rag", "status"]
    result = _run_rag_cmd(cmd)
    return result.stdout.strip()


def init() -> ToolSpec:
    """Initialize the RAG tool."""
    # Check if gptme-rag CLI is available
    if not _has_gptme_rag():
        logger.debug("gptme-rag CLI not found in PATH")
        return replace(tool, available=False)

    # Check project configuration
    project_dir = get_project_dir()
    if project_dir and (config := get_project_config(project_dir)):
        enabled = config.rag.enabled
        if not enabled:
            logger.debug("RAG not enabled in the project configuration")
            return replace(tool, available=False)
    else:
        logger.debug("Project configuration not found, not enabling")
        return replace(tool, available=False)

    return tool


def rag_enhance_messages(messages: list[Message]) -> list[Message]:
    """Enhance messages with context from RAG."""
    if not _has_gptme_rag():
        return messages

    # Load config
    config = get_project_config(Path.cwd())
    rag_config = config.rag if config and config.rag else RagConfig()

    if not rag_config.enabled:
        return messages

    last_msg = messages[-1] if messages else None
    if last_msg and last_msg.role == "user":
        try:
            # Get context using gptme-rag CLI
            cmd = ["gptme-rag", "search", last_msg.content, "--format", "full"]
            if rag_config.max_tokens:
                cmd.extend(["--max-tokens", str(rag_config.max_tokens)])
            if rag_config.min_relevance:
                cmd.extend(["--min-relevance", str(rag_config.min_relevance)])
            rag_result = _run_rag_cmd(cmd).stdout

            # Post-process the context with an LLM (if enabled)
            if rag_config.post_process and rag_config.post_process_model is not None:
                post_process_msgs = [
                    Message(role="system", content=rag_config.post_process_prompt),
                    Message(role="system", content=rag_result),
                    Message(
                        role="user",
                        content=f"<user_query>\n{last_msg.content}\n</user_query>",
                    ),
                ]
                start = time.monotonic()
                rag_result = _chat_complete(
                    messages=post_process_msgs,
                    model=rag_config.post_process_model,
                    tools=[],
                )
                logger.info(f"Ran RAG post-process in {time.monotonic() - start:.2f}s")

            # Create the context message
            msg = Message(
                role="system",
                content=f"Relevant context retrieved using `gptme-rag search`:\n\n{rag_result}",
                hide=True,
            )
            # Append context message right before the last user message
            messages.insert(-1, msg)
        except Exception as e:
            logger.warning(f"Error getting context: {e}")

    return messages


tool = ToolSpec(
    name="rag",
    desc="RAG (Retrieval-Augmented Generation) for context-aware assistance",
    instructions=instructions,
    examples=examples,
    functions=[rag_index, rag_search, rag_status],
    available=_has_gptme_rag(),
    init=init,
)

__doc__ = tool.get_doc(__doc__)
