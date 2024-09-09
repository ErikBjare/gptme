"""
List, search, and summarize past conversation logs.
"""

import logging
from pathlib import Path
from textwrap import indent

from ..llm import summarize as llm_summarize
from ..message import Message
from ..util import transform_examples_to_chat_directives
from .base import ToolSpec

logger = logging.getLogger(__name__)


def _format_message_snippet(msg: Message, max_length: int = 100) -> str:
    """Format a message snippet for display."""
    first_newline = msg.content.find("\n")
    max_length = min(max_length, first_newline) if first_newline != -1 else max_length
    content = msg.content[:max_length]
    return f"{msg.role.capitalize()}: {content}" + (
        "..." if len(content) <= len(msg.content) else ""
    )


def _get_matching_messages(log_manager, query: str) -> list[Message]:
    """Get messages matching the query."""
    return [msg for msg in log_manager.log if query.lower() in msg.content.lower()]


def _summarize_conversation(log_manager, include_summary: bool) -> list[str]:
    """Summarize a conversation."""
    summary_lines = []
    if include_summary:
        summary = llm_summarize(log_manager.log)
        summary_lines.append(indent(f"Summary: {summary.content}", "   "))
    else:
        non_system_messages = [msg for msg in log_manager.log if msg.role != "system"]
        if non_system_messages:
            first_msg = non_system_messages[0]
            last_msg = non_system_messages[-1]

            summary_lines.append(
                f"   First message: {_format_message_snippet(first_msg)}"
            )
            if last_msg != first_msg:
                summary_lines.append(
                    f"   Last message:  {_format_message_snippet(last_msg)}"
                )

    summary_lines.append(f"   Total messages: {len(log_manager.log)}")
    return summary_lines


def list_chats(max_results: int = 5, include_summary: bool = False) -> None:
    """
    List recent chat conversations and optionally summarize them using an LLM.

    Args:
        max_results (int): Maximum number of conversations to display.
        include_summary (bool): Whether to include a summary of each conversation.
            If True, uses an LLM to generate a comprehensive summary.
            If False, uses a simple strategy showing snippets of the first and last messages.
    """
    # noreorder
    from ..logmanager import LogManager, get_conversations  # fmt: skip

    conversations = list(get_conversations())[:max_results]

    if not conversations:
        print("No conversations found.")
        return

    print(f"Recent conversations (showing up to {max_results}):")
    for i, conv in enumerate(conversations, 1):
        print(f"\n{i}. {conv['name']}")
        if "created_at" in conv:
            print(f"   Created: {conv['created_at']}")

        log_path = Path(conv["path"])
        log_manager = LogManager.load(log_path)

        summary_lines = _summarize_conversation(log_manager, include_summary)
        print("\n".join(summary_lines))


def search_chats(query: str, max_results: int = 5) -> None:
    """
    Search past conversation logs for the given query and print a summary of the results.

    Args:
        query (str): The search query.
        max_results (int): Maximum number of conversations to display.
    """
    # noreorder
    from ..logmanager import LogManager, get_conversations  # fmt: skip

    conversations = list(get_conversations())
    results = []

    for conv in conversations:
        log_path = Path(conv["path"])
        log_manager = LogManager.load(log_path)

        matching_messages = _get_matching_messages(log_manager, query)

        if matching_messages:
            results.append(
                {
                    "conversation": conv["name"],
                    "log_manager": log_manager,
                    "matching_messages": matching_messages,
                }
            )

    # Sort results by the number of matching messages, in descending order
    results.sort(key=lambda x: len(x["matching_messages"]), reverse=True)
    results = results[:max_results]

    if not results:
        print(f"No results found for query: '{query}'")
        return

    print(f"Search results for query: '{query}'")
    print(f"Found matches in {len(results)} conversation(s):")

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Conversation: {result['conversation']}")
        print(f"   Number of matching messages: {len(result['matching_messages'])}")

        summary_lines = _summarize_conversation(
            result["log_manager"], include_summary=False
        )
        print("\n".join(summary_lines))

        print("   Sample matches:")
        for j, msg in enumerate(result["matching_messages"][:3], 1):
            print(f"     {j}. {_format_message_snippet(msg)}")
        if len(result["matching_messages"]) > 3:
            print(
                f"     ... and {len(result['matching_messages']) - 3} more matching message(s)"
            )


instructions = """
The chats tool allows you to list, search, and summarize past conversation logs.
"""

examples = """
### Search for a specific topic in past conversations
User: Can you find any mentions of "python" in our past conversations?
Assistant: Certainly! I'll search our past conversations for mentions of "python" using the search_chats function.
```python
search_chats("python")
```
"""

tool = ToolSpec(
    name="chats",
    desc="List, search, and summarize past conversation logs",
    instructions=instructions,
    examples=examples,
    functions=[list_chats, search_chats],
)

__doc__ = tool.get_doc(__doc__)