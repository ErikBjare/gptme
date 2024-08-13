"""
A tool to summarize long outputs.
"""

import logging
from functools import lru_cache

from ..llm import summarize as _summarize
from ..message import Message, format_msgs, len_tokens

logger = logging.getLogger(__name__)


def summarize(msg: Message | list[Message]) -> Message:
    """Uses a cheap LLM to summarize long outputs."""
    # construct plaintext from message(s)
    msgs = msg if isinstance(msg, list) else [msg]
    content = "\n".join(format_msgs(msgs))
    logger.info(f"{content[:200]=}")
    summary = _summarize_helper(content)
    logger.info(f"{summary[:200]=}")

    # construct message from summary
    content = f"Here's a summary of the conversation so far:\n{summary}"
    return Message(role="system", content=content)


@lru_cache(maxsize=128)
def _summarize_helper(s: str, tok_max_start=400, tok_max_end=400) -> str:
    """
    Helper function for summarizing long outputs.
    Truncates long outputs, then summarizes.
    """
    if len_tokens(s) > tok_max_start + tok_max_end:
        beginning = " ".join(s.split()[:tok_max_start])
        end = " ".join(s.split()[-tok_max_end:])
        summary = _summarize(beginning + "\n...\n" + end)
    else:
        summary = _summarize(s)
    return summary
