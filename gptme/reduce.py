import logging
from typing import Generator

from .message import Message
from .tools import summarize
from .util import len_tokens

logger = logging.getLogger(__name__)


def reduce_log(log: list[Message]) -> Generator[Message, None, None]:
    """Reduces the log to a more manageable size."""
    tokens = 0.0
    yield log[0]
    for msg in log[1:]:
        tokens += len_tokens(msg.content)
        if msg.role in ["system", "assistant"] and not msg.pinned:
            if len_tokens(msg.content) > 100:
                msg = summarize(msg)
        yield msg


TOKEN_LIMIT_SOFT = 500
TOKEN_LIMIT_HARD = 500


def limit_log(log: list[Message]) -> list[Message]:
    """
    Picks chat log messages, until the total number of tokens exceeds 2000.
    Walks in reverse order through the log, and picks messages until the total number of tokens exceeds 2000.
    Will always pick the first few system messages.
    """
    tokens = 0.0

    # Always pick the first system messages
    initial_system_msgs = []
    for msg in log:
        if msg.role != "system":
            break
        initial_system_msgs.append(msg)
        tokens += len_tokens(msg.content)

    # Pick the last messages until we exceed the token limit
    msgs = []
    for msg in reversed(log[len(initial_system_msgs) :]):
        tokens += len_tokens(msg.content)
        if tokens > TOKEN_LIMIT_HARD:
            break
        msgs.append(msg)

    if tokens > TOKEN_LIMIT_SOFT:
        logger.debug(f"Log exceeded {TOKEN_LIMIT_SOFT} tokens")
    return initial_system_msgs + list(reversed(msgs))
