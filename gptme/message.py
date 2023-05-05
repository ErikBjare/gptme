from typing import Literal
from datetime import datetime

class Message:
    """A message sent to or from the AI."""

    def __init__(
        self,
        role: Literal["system", "user", "assistant"],
        content: str,
        user: str | None = None,
    ):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content
        if user:
            self.user = user
        else:
            role_names = {"system": "System", "user": "User", "assistant": "Assistant"}
            self.user = role_names[role]
        self.timestamp = datetime.now()

    def to_dict(self):
        """Return a dict representation of the message, serializable to JSON."""
        return {
            "role": self.role,
            "content": self.content,
        }
