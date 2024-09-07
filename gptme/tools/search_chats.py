import logging
from pathlib import Path

from .base import ToolSpec

logger = logging.getLogger(__name__)


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

        matching_messages = []
        for msg in log_manager.log:
            if query.lower() in msg.content.lower():
                matching_messages.append(msg)

        if matching_messages:
            results.append(
                {
                    "conversation": conv["name"],
                    "messages": matching_messages,
                }
            )

    # Sort results by the number of matching messages, in descending order
    results.sort(key=lambda x: len(x["messages"]), reverse=True)
    results = results[:max_results]

    if not results:
        print(f"No results found for query: '{query}'")
        return

    print(f"Search results for query: '{query}'")
    print(f"Found matches in {len(results)} conversation(s):")

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Conversation: {result['conversation']}")
        print(f"   Number of matching messages: {len(result['messages'])}")
        print("   Sample matches:")
        # Show up to 3 sample messages
        for j, msg in enumerate(result["messages"][:3], 1):
            content = (
                msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            )
            print(f"     {j}. {msg.role.capitalize()}: {content}")
        if len(result["messages"]) > 3:
            print(
                f"     ... and {len(result['messages']) - 3} more matching message(s)"
            )


instructions = """
To search past conversation logs, you can use the `search_chats` function in Python.
This function allows you to find relevant information from previous conversations.
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
    name="search_chats",
    desc="Search past conversation logs",
    instructions=instructions,
    examples=examples,
    functions=[search_chats],
)
