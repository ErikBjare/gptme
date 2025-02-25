import logging
import shutil
import sys
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import cast

from rich import print as rprint

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
    get_default_model_summary,
)

logger = logging.getLogger(__name__)


def init_llm(provider: Provider):
    """Initialize LLM client for a given provider if not already initialized."""
    config = get_config()

    if provider in PROVIDERS_OPENAI and not get_openai_client(provider):
        init_openai(provider, config)
    elif provider == "anthropic" and not get_anthropic_client():
        init_anthropic(config)
    else:
        logger.debug(f"Provider {provider} already initialized or unknown")


def reply(
    messages: list[Message],
    model: str,
    stream: bool = False,
    tools: list[ToolSpec] | None = None,
) -> Message:
    init_llm(get_provider_from_model(model))
    if stream:
        config = get_config()
        break_on_tooluse = config.get_env("GPTME_BREAK_ON_TOOLUSE", "true") in [
            "1",
            "true",
        ]
        return _reply_stream(messages, model, tools, break_on_tooluse)
    else:
        rprint(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
        response = _chat_complete(messages, model, tools)
        rprint(" " * shutil.get_terminal_size().columns, end="\r")
        rprint(f"{PROMPT_ASSISTANT}: {response}")
        return Message("assistant", response)


def get_provider_from_model(model: str) -> Provider:
    """Extract provider from fully qualified model name."""
    if "/" not in model:
        raise ValueError(
            f"Model name must be fully qualified with provider prefix: {model}"
        )
    provider = model.split("/")[0]
    if provider not in MODELS:
        raise ValueError(f"Unknown provider: {provider}")
    return cast(Provider, provider)


def _get_base_model(model: str) -> str:
    """Get base model name without provider prefix."""
    return model.split("/", 1)[1]


def _chat_complete(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> str:
    provider = get_provider_from_model(model)
    if provider in PROVIDERS_OPENAI:
        return chat_openai(messages, model, tools)
    elif provider == "anthropic":
        return chat_anthropic(messages, _get_base_model(model), tools)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Iterator[str]:
    provider = get_provider_from_model(model)
    if provider in PROVIDERS_OPENAI:
        return stream_openai(messages, model, tools)
    elif provider == "anthropic":
        return stream_anthropic(messages, _get_base_model(model), tools)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _reply_stream(
    messages: list[Message],
    model: str,
    tools: list[ToolSpec] | None,
    break_on_tooluse: bool = True,
) -> Message:
    rprint(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")

    def print_clear(length: int = 0):
        length = length or shutil.get_terminal_size().columns
        rprint("\r" + " " * length, end="\r")

    output = ""
    start_time = time.time()
    first_token_time = None
    are_thinking = False
    try:
        for char in (
            char for chunk in _stream(messages, model, tools) for char in chunk
        ):
            if not output:  # first character
                first_token_time = time.time()
                print_clear()
                rprint(f"{PROMPT_ASSISTANT}: \n", end="")

            # Check for thinking tags before printing a newline
            if char == "\n" or not output:
                last_line = output.rsplit("\n", 1)[-1]
                if last_line.strip():
                    # print(f"(check line: {last_line})", end="")
                    pass

                # Check for opening tag at the end of this line
                if last_line == "<think>" or last_line == "<thinking>":
                    # Print spaces to clear the line
                    print_clear(len(last_line))
                    # Print styled version
                    rprint(f"[dim]{last_line}[/dim]", end="")
                    are_thinking = True
                # Check for closing tag
                elif last_line == "</think>" or last_line == "</thinking>":
                    print_clear(len(last_line))
                    # Print styled version
                    rprint(f"[dim]{last_line}[/dim]", end="")
                    are_thinking = False

                # Now print the newline
                rprint(char, end="")
            else:
                # Print normal characters
                if are_thinking:
                    rprint(f"[dim]{char}[/dim]", end="")
                else:
                    rprint(char, end="")

            assert len(char) == 1
            output += char

            # need to flush stdout to get the print to show up
            sys.stdout.flush()

            # Trigger the tool detection only if the line is finished.
            # Helps to detect nested start code blocks.
            if break_on_tooluse and char == "\n":
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
                f"Generation finished in {end_time - start_time:.1f}s "
                f"(ttft: {first_token_time - start_time:.2f}s, "
                f"gen: {end_time - first_token_time:.2f}s, "
                f"tok/s: {len_tokens(output, model)/(end_time - first_token_time):.1f})"
            )

    return Message("assistant", output)


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

    model = get_default_model_summary()
    assert model, "No default model set"

    if len_tokens(messages, model.model) > model.context:
        raise ValueError(
            f"Cannot summarize more than {model.context} tokens, got {len_tokens(messages, model.model)}"
        )

    summary = _chat_complete(messages, model.full, None)
    assert summary
    logger.debug(
        f"Summarized long output ({len_tokens(content, model.model)} -> {len_tokens(summary, model.model)} tokens): "
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

    model = get_default_model_summary()
    assert model, "No default model set"
    name = _chat_complete(msgs, model.full, None).strip()
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


def guess_provider_from_config() -> Provider | None:
    """
    Guess the provider to use from the configuration.
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
