import logging
from typing import Generator

from ..message import Message
from ..util import len_tokens
from . import summarize

logger = logging.getLogger(__name__)


# GPT-4 has a 8k token limit
TOKEN_LIMIT_SOFT = 6000
TOKEN_LIMIT_HARD = 7000


def reduce_log(
    log: list[Message], limit=TOKEN_LIMIT_SOFT
) -> Generator[Message, None, None]:
    """Reduces log until it is below `limit` tokens by continually summarizing the longest messages until below the limit."""
    # filter out pinned messages
    i, longest_msg = max(
        [(i, m) for i, m in enumerate(log) if not m.pinned],
        key=lambda t: len_tokens(t[1].content),
    )
    longest_msg = summarize(longest_msg)
    log = log[:i] + [longest_msg] + log[i + 1 :]
    tokens_total = len_tokens("".join(m.content for m in log))
    if tokens_total > limit:
        # recurse until we are below the limit
        yield from reduce_log(log, limit)
    else:
        yield from log


def limit_log(log: list[Message]) -> list[Message]:
    """
    Picks chat log messages, until the total number of tokens exceeds TOKEN_LIMIT_SOFT.
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

    # Pick the messages in latest-first order
    msgs = []
    for msg in reversed(log[len(initial_system_msgs) :]):
        tokens += len_tokens(msg.content)
        if tokens > TOKEN_LIMIT_SOFT:
            break
        msgs.append(msg)

    if tokens > TOKEN_LIMIT_SOFT:
        logger.debug(f"Log exceeded {TOKEN_LIMIT_HARD} tokens")
    return initial_system_msgs + list(reversed(msgs))
