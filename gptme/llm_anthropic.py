from collections.abc import Generator

from anthropic import Anthropic

from .constants import TEMPERATURE, TOP_P
from .message import Message, msgs2dicts

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


def chat(messages: list[Message], model: str) -> str:
    assert anthropic, "LLM not initialized"
    messages, system_messages = _transform_system_messages(messages)
    response = anthropic.messages.create(
        model=model,
        messages=msgs2dicts(messages, anthropic=True),  # type: ignore
        system=system_messages,
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
    with anthropic.messages.stream(
        model=model,
        messages=msgs2dicts(messages, anthropic=True),  # type: ignore
        system=system_messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
    ) as stream:
        yield from stream.text_stream


def _transform_system_messages(
    messages: list[Message],
) -> tuple[list[Message], str]:
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

    return messages, system_prompt
