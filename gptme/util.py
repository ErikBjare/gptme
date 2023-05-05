from .message import Message

def len_tokens(content: str | list[Message]) -> float:
    """Approximate the number of tokens in a string by assuming words have len 4 (lol)."""
    if isinstance(content, list):
        return sum(len_tokens(msg.content) for msg in content)
    return len(content.split(" ")) / 4


def msgs2text(msgs: list[Message]) -> str:
    output = ""
    for msg in msgs:
        output += f"{msg.user}: {msg.content}\n"
    return output


def msgs2dicts(msgs: list[Message]) -> list[dict]:
    return [msg.to_dict() for msg in msgs]
