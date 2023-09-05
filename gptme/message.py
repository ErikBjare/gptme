from datetime import datetime
from typing import Literal


class Message:
    """A message sent to or from the AI."""

    def __init__(
        self,
        role: Literal["system", "user", "assistant"],
        content: str,
        user: str | None = None,
        pinned: bool = False,
    ):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content.strip()
        if user:
            self.user = user
        else:
            role_names = {"system": "System", "user": "User", "assistant": "Assistant"}
            self.user = role_names[role]

        # Wether this message should be pinned to the top of the chat, and never context-trimmed.
        self.pinned = pinned
        self.timestamp = datetime.now()

    def to_dict(self):
        """Return a dict representation of the message, serializable to JSON."""
        return {
            "role": self.role,
            "content": self.content,
        }

    def __repr__(self):
        return f"<Message role={self.role} content={self.content}>"
