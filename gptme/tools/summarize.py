import logging
from functools import lru_cache

import openai

from ..message import Message, format_msgs
from ..util import len_tokens

logger = logging.getLogger(__name__)


@lru_cache(maxsize=100)
def _llm_summarize(content: str) -> str:
    """Summarizes a long text using a LLM algorithm."""
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="Please summarize the following:\n" + content + "\n\nSummary:",
        temperature=0,
        max_tokens=256,
    )
    summary = response.choices[0].text
    logger.debug(
        f"Summarized long output ({len_tokens(content)} -> {len_tokens(summary)} tokens): "
        + summary
    )
    return summary


def summarize(msg: Message | list[Message]) -> Message:
    """Uses a cheap LLM to summarize long outputs."""
    # construct plaintext from message(s)
    msgs = msg if isinstance(msg, list) else [msg]
    content = "\n".join(format_msgs(msgs))
    summary = _summarize(content)
    # construct message from summary
    summary_msg = Message(
        role="system", content=f"Summary of the conversation:\n{summary})"
    )
    return summary_msg


def _summarize(s: str) -> str:
    if len_tokens(s) > 200:
        # first 100 tokens
        beginning = " ".join(s.split()[:150])
        # last 100 tokens
        end = " ".join(s.split()[-100:])
        summary = _llm_summarize(beginning + "\n...\n" + end)
    else:
        summary = _llm_summarize(s)
    return summary
