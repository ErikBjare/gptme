import logging

import openai

from ..cache import memory
from ..message import Message
from ..util import len_tokens

logger = logging.getLogger(__name__)


@memory.cache
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


def summarize(msg: Message) -> Message:
    """Uses a cheap LLM to summarize long outputs."""
    if len_tokens(msg.content) > 200:
        # first 100 tokens
        beginning = " ".join(msg.content.split()[:150])
        # last 100 tokens
        end = " ".join(msg.content.split()[-100:])
        summary = _llm_summarize(beginning + "\n...\n" + end)
    else:
        summary = _llm_summarize(msg.content)
    return Message("system", f"Here is a summary of the response:\n{summary}")
