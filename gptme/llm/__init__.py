import logging
import shutil
import sys
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import cast

from rich import print

from ..config import get_config
from ..constants import PROMPT_ASSISTANT
from ..message import Message, format_msgs, len_tokens
from ..tools import ToolSpec, ToolUse
from ..util import console
from .llm_anthropic import chat as chat_anthropic
from .llm_anthropic import get_client as get_anthropic_client
from .llm_anthropic import init as init_anthropic
from .llm_anthropic import stream as stream_anthropic
from .llm_openai import chat as chat_openai
from .llm_openai import get_client as get_openai_client
from .llm_openai import init as init_openai
from .llm_openai import stream as stream_openai
from .models import (
    MODELS,
    PROVIDERS_OPENAI,
    Provider,
    get_summary_model,
)

logger = logging.getLogger(__name__)


def init_llm(llm: str):
    # set up API_KEY (if openai) and API_BASE (if local)
    config = get_config()

    llm = cast(Provider, llm)
    if llm in PROVIDERS_OPENAI:
        init_openai(llm, config)
        assert get_openai_client()
    elif llm == "anthropic":
        init_anthropic(config)
        assert get_anthropic_client()
    else:
        console.log(f"Error: Unknown LLM: {llm}")
        sys.exit(1)


def reply(
    messages: list[Message],
    model: str,
    stream: bool = False,
    tools: list[ToolSpec] | None = None,
) -> Message:
    if stream:
        return _reply_stream(messages, model, tools)
    else:
        print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
        response = _chat_complete(messages, model, tools)
        print(" " * shutil.get_terminal_size().columns, end="\r")
        print(f"{PROMPT_ASSISTANT}: {response}")
        return Message("assistant", response)


def _chat_complete(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> str:
    provider = _client_to_provider()
    if provider in PROVIDERS_OPENAI:
        return chat_openai(messages, model, tools)
    elif provider == "anthropic":
        return chat_anthropic(messages, model, tools)
    else:
        raise ValueError("LLM not initialized")


def _stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Iterator[str]:
    provider = _client_to_provider()
    if provider in PROVIDERS_OPENAI:
        return stream_openai(messages, model, tools)
    elif provider == "anthropic":
        return stream_anthropic(messages, model, tools)
    else:
        raise ValueError("LLM not initialized")


def _reply_stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Message:
    print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")

    def print_clear():
        print(" " * shutil.get_terminal_size().columns, end="\r")

    output = ""
    start_time = time.time()
    first_token_time = None
    try:
        for char in (
            char for chunk in _stream(messages, model, tools) for char in chunk
        ):
            if not output:  # first character
                first_token_time = time.time()
                print_clear()
                print(f"{PROMPT_ASSISTANT}: ", end="")
            print(char, end="")
            assert len(char) == 1
            output += char

            # need to flush stdout to get the print to show up
            sys.stdout.flush()

            # Trigger the tool detection only if the line is finished.
            # Helps to detect nested start code blocks.
            if char == "\n":
                # TODO: make this more robust/general, maybe with a callback that runs on each char/chunk
                # pause inference on finished code-block, letting user run the command before continuing
                tooluses = [
                    tooluse
                    for tooluse in ToolUse.iter_from_content(output)
                    if tooluse.is_runnable
                ]
                if tooluses:
                    logger.debug("Found tool use, breaking")
                    break
    except KeyboardInterrupt:
        return Message("assistant", output + "... ^C Interrupted")
    finally:
        print_clear()
        if first_token_time:
            end_time = time.time()
            logger.debug(
                f"Generation interrupted after {end_time - start_time:.1f}s "
                f"(ttft: {first_token_time - start_time:.2f}s, "
                f"gen: {end_time - first_token_time:.2f}s, "
                f"tok/s: {len_tokens(output, model)/(end_time - first_token_time):.1f})"
            )

    return Message("assistant", output)


def _client_to_provider() -> Provider:
    openai_client = get_openai_client()
    anthropic_client = get_anthropic_client()
    assert openai_client or anthropic_client, "No client initialized"
    if openai_client:
        if "openai" in openai_client.base_url.host:
            return "openai"
        elif "openrouter" in openai_client.base_url.host:
            return "openrouter"
        elif "gemini" in openai_client.base_url.host:
            return "gemini"
        else:
            return "azure"
    elif anthropic_client:
        return "anthropic"
    else:
        raise ValueError("Unknown client type")


def _summarize_str(content: str) -> str:
    """
    Summarizes a long text using a LLM.

    To summarize messages or the conversation log,
    use `gptme.tools.summarize` instead (which wraps this).
    """
    messages = [
        Message(
            "system",
            content="You are a helpful assistant that helps summarize messages into bullet format. Dont use any preamble or heading, start directly with a bullet list.",
        ),
        Message("user", content=f"Summarize this:\n{content}"),
    ]

    provider = _client_to_provider()
    model = get_summary_model(provider)
    context_limit = MODELS[provider][model]["context"]
    if len_tokens(messages, model) > context_limit:
        raise ValueError(
            f"Cannot summarize more than {context_limit} tokens, got {len_tokens(messages, model)}"
        )

    summary = _chat_complete(messages, model, None)
    assert summary
    logger.debug(
        f"Summarized long output ({len_tokens(content, model)} -> {len_tokens(summary, model)} tokens): "
        + summary
    )
    return summary


def generate_name(msgs: list[Message]) -> str:
    """
    Generates a name for a given text/conversation using a LLM.
    """
    # filter out system messages
    msgs = [m for m in msgs if m.role != "system"]

    # TODO: filter out assistant messages? (only for long conversations? or always?)
    # msgs = [m for m in msgs if m.role != "assistant"]

    msgs = (
        [
            Message(
                "system",
                """
The following is a conversation between a user and an assistant.
You should generate a descriptive name for it.

The name should be 3-6 words describing the conversation, separated by dashes. Examples:
 - install-llama
 - implement-game-of-life
 - capitalize-words-in-python

Focus on the main and/or initial topic of the conversation. Avoid using names that are too generic or too specific.

IMPORTANT: output only the name, no preamble or postamble.
""",
            )
        ]
        + msgs
        + [
            Message(
                "user",
                "That was the context of the conversation. Now, answer with a descriptive name for this conversation according to system instructions.",
            )
        ]
    )
    model = get_summary_model(_client_to_provider())
    name = _chat_complete(msgs, model, None).strip()
    return name


def summarize(msg: str | Message | list[Message]) -> Message:
    """Uses a cheap LLM to summarize long outputs."""
    # construct plaintext from message(s)
    if isinstance(msg, str):
        content = msg
    elif isinstance(msg, Message):
        content = msg.content
    else:
        content = "\n".join(format_msgs(msg))

    summary = _summarize_helper(content)

    # construct message from summary
    content = f"Here's a summary of the conversation:\n{summary}"
    return Message(role="system", content=content)


@lru_cache(maxsize=128)
def _summarize_helper(s: str, tok_max_start=400, tok_max_end=400) -> str:
    """
    Helper function for summarizing long outputs.
    Truncates long outputs, then summarizes.
    """
    # Use gpt-4 as default model for summarization helper
    if len_tokens(s, "gpt-4") > tok_max_start + tok_max_end:
        beginning = " ".join(s.split()[:tok_max_start])
        end = " ".join(s.split()[-tok_max_end:])
        summary = _summarize_str(beginning + "\n...\n" + end)
    else:
        summary = _summarize_str(s)
    return summary


def guess_model_from_config() -> Provider | None:
    """
    Guess the model to use from the configuration.
    """

    config = get_config()

    if config.get_env("OPENAI_API_KEY"):
        console.log("Found OpenAI API key, using OpenAI provider")
        return "openai"
    elif config.get_env("ANTHROPIC_API_KEY"):
        console.log("Found Anthropic API key, using Anthropic provider")
        return "anthropic"
    elif config.get_env("OPENROUTER_API_KEY"):
        console.log("Found OpenRouter API key, using OpenRouter provider")
        return "openrouter"
    elif config.get_env("GEMINI_API_KEY"):
        console.log("Found Gemini API key, using Gemini provider")
        return "gemini"

    return None


def get_model_from_api_key(api_key: str) -> tuple[str, Provider, str] | None:
    """
    Guess the model from the API key prefix.
    """

    if api_key.startswith("sk-ant-"):
        return api_key, "anthropic", "ANTHROPIC_API_KEY"
    elif api_key.startswith("sk-or-"):
        return api_key, "openrouter", "OPENROUTER_API_KEY"
    elif api_key.startswith("sk-"):
        return api_key, "openai", "OPENAI_API_KEY"

    return None
