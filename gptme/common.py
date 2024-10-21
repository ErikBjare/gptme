class Message:
    """Represents a message in the conversation."""
    
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        """Convert the message to a dictionary representation."""
        return {
            "role": self.role,
            "content": self.content
        }

    def __repr__(self):
        return f"Message(role={self.role}, content={self.content})"
