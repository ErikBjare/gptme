from collections.abc import Generator
from typing import Literal, TypedDict
from typing_extensions import Required

from anthropic import Anthropic

from .constants import TEMPERATURE, TOP_P
from .message import Message, len_tokens, msgs2dicts

anthropic: Anthropic | None = None


def init(config):
    global anthropic
    api_key = config.get_env_required("ANTHROPIC_API_KEY")
    anthropic = Anthropic(
        api_key=api_key,
        max_retries=5,
    )


def get_client() -> Anthropic | None:
    return anthropic


class MessagePart(TypedDict, total=False):
    type: Required[Literal["text", "image_url"]]
    text: str
    image_url: str
    cache_control: dict[str, str]


def chat(messages: list[Message], model: str) -> str:
    assert anthropic, "LLM not initialized"
    messages, system_messages = _transform_system_messages(messages)
    response = anthropic.beta.prompt_caching.messages.create(
        model=model,
        messages=msgs2dicts(messages, anthropic=True),  # type: ignore
        system=system_messages,  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
    )
    content = response.content
    assert content
    assert len(content) == 1
    return content[0].text  # type: ignore


def stream(messages: list[Message], model: str) -> Generator[str, None, None]:
    messages, system_messages = _transform_system_messages(messages)
    assert anthropic, "LLM not initialized"
    with anthropic.beta.prompt_caching.messages.stream(
        model=model,
        messages=msgs2dicts(messages, anthropic=True),  # type: ignore
        system=system_messages,  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
    ) as stream:
        yield from stream.text_stream


def _transform_system_messages(
    messages: list[Message],
) -> tuple[list[Message], list[MessagePart]]:
    # transform system messages into system kwarg for anthropic
    # for first system message, transform it into a system kwarg
    assert messages[0].role == "system"
    system_prompt = messages[0].content
    messages.pop(0)

    # for any subsequent system messages, transform them into a <system> message
    for i, message in enumerate(messages):
        if message.role == "system":
            messages[i] = Message(
                "user",
                content=f"<system>{message.content}</system>",
            )

    # find consecutive user role messages and merge them into a single <system> message
    messages_new: list[Message] = []
    while messages:
        message = messages.pop(0)
        if messages_new and messages_new[-1].role == "user":
            messages_new[-1] = Message(
                "user",
                content=f"{messages_new[-1].content}\n{message.content}",
            )
        else:
            messages_new.append(message)
    messages = messages_new
    system_messages: list[MessagePart] = [
        {
            "type": "text",
            "text": system_prompt,
        }
    ]

    # prompt caching for the system prompt, saving cost and reducing latency
    # https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    # if system_messages is long (>2048 tokens), we add cache_control
    if len_tokens(system_prompt) > 2048 + 500:  # margin for tokenizer diff
        system_messages[-1]["cache_control"] = {"type": "ephemeral"}

    return messages, system_messages
