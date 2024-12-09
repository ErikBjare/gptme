"""
List, search, and summarize past conversation logs.
"""

import logging
import textwrap
from pathlib import Path

from ..message import Message
from .base import ToolSpec, ToolUse

logger = logging.getLogger(__name__)


def _get_matching_messages(log_manager, query: str, system=False) -> list[Message]:
    """Get messages matching the query."""
    return [
        msg
        for msg in log_manager.log
        if query.lower() in msg.content.lower()
        if msg.role != "system" or system
    ]


def list_chats(
    max_results: int = 5, metadata=False, include_summary: bool = False
) -> None:
    """
    List recent chat conversations and optionally summarize them using an LLM.

    Args:
        max_results (int): Maximum number of conversations to display.
        include_summary (bool): Whether to include a summary of each conversation.
            If True, uses an LLM to generate a comprehensive summary.
            If False, uses a simple strategy showing snippets of the first and last messages.
    """
    from ..llm import summarize  # fmt: skip
    from ..logmanager import LogManager, list_conversations  # fmt: skip

    conversations = list_conversations(max_results)
    if not conversations:
        print("No conversations found.")
        return

    print(f"Recent conversations (showing up to {max_results}):")
    for i, conv in enumerate(conversations, 1):
        if metadata:
            print()  # Add a newline between conversations
        print(f"{i:2}. {textwrap.indent(conv.format(metadata=True), '    ')[4:]}")

        log_path = Path(conv.path)
        log_manager = LogManager.load(log_path, lock=False)

        # Use the LLM to generate a summary if requested
        if include_summary:
            summary = summarize(log_manager.log.messages)
            print(
                f"\n    Summary:\n{textwrap.indent(summary.content, '    > ', predicate=lambda _: True)}"
            )
            print()


def search_chats(query: str, max_results: int = 5, system=False) -> None:
    """
    Search past conversation logs for the given query and print a summary of the results.

    Args:
        query (str): The search query.
        max_results (int): Maximum number of conversations to display.
        system (bool): Whether to include system messages in the search.
    """
    from ..logmanager import LogManager, list_conversations  # fmt: skip

    results: list[dict] = []
    for conv in list_conversations(max_results):
        log_path = Path(conv.path)
        log_manager = LogManager.load(log_path)

        matching_messages = _get_matching_messages(log_manager, query, system)

        if matching_messages:
            results.append(
                {
                    "conversation": conv,
                    "log_manager": log_manager,
                    "matching_messages": matching_messages,
                }
            )

    if not results:
        print(f"No results found for query: '{query}'")
        return

    # Sort results by the number of matching messages, in descending order
    results.sort(key=lambda x: len(x["matching_messages"]), reverse=True)

    print(f"Search results for query: '{query}'")
    print(f"Found matches in {len(results)} conversation(s):")

    for i, result in enumerate(results, 1):
        conversation = result["conversation"]
        print(f"\n{i}. {conversation.format()}")
        print(f"   Number of matching messages: {len(result['matching_messages'])}")

        # Show sample matches
        print("   Sample matches:")
        for j, msg in enumerate(result["matching_messages"][:3], 1):
            print(f"     {j}. {msg.format(max_length=100)}")
        if len(result["matching_messages"]) > 3:
            print(
                f"     ... and {len(result['matching_messages']) - 3} more matching message(s)"
            )


def read_chat(conversation: str, max_results: int = 5, incl_system=False) -> None:
    """
    Read a specific conversation log.

    Args:
        conversation (str): The name of the conversation to read.
        max_results (int): Maximum number of messages to display.
        incl_system (bool): Whether to include system messages.
    """
    from ..logmanager import LogManager, list_conversations  # fmt: skip

    for conv in list_conversations():
        if conv.name == conversation:
            log_path = Path(conv.path)
            logmanager = LogManager.load(log_path)
            print(f"Reading conversation: {conversation}")
            i = 0
            for msg in logmanager.log:
                if msg.role != "system" or incl_system:
                    print(f"{i}. {msg.format(max_length=100)}")
                    i += 1
                if i >= max_results:
                    break
            break
    else:
        print(f"Conversation '{conversation}' not found.")


def examples(tool_format):
    return f"""
### Search for a specific topic in past conversations
User: Can you find any mentions of "python" in our past conversations?
Assistant: Certainly! I'll search our past conversations for mentions of "python" using the search_chats function.
{ToolUse("ipython", [], "search_chats('python')").to_output(tool_format)}
"""


tool = ToolSpec(
    name="chats",
    desc="List, search, and summarize past conversation logs",
    examples=examples,
    functions=[list_chats, search_chats, read_chat],
)

__doc__ = tool.get_doc(__doc__)
