import base64
import logging
from collections.abc import Generator
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypedDict,
)

from anthropic import NOT_GIVEN
from typing_extensions import Required

from ..tools.base import ToolSpec, Parameter

from ..constants import TEMPERATURE, TOP_P
from ..message import Message, len_tokens, msgs2dicts

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from anthropic import Anthropic  # fmt: skip
    from anthropic.types.beta.prompt_caching import PromptCachingBetaToolParam

anthropic: "Anthropic | None" = None

ALLOWED_FILE_EXTS = ["jpg", "jpeg", "png", "gif"]


def init(config):
    global anthropic
    api_key = config.get_env_required("ANTHROPIC_API_KEY")
    from anthropic import Anthropic  # fmt: skip

    anthropic = Anthropic(
        api_key=api_key,
        max_retries=5,
    )


def get_client() -> "Anthropic | None":
    return anthropic


class ToolAnthropic(TypedDict):
    name: str
    description: str
    input_schema: dict


class MessagePart(TypedDict, total=False):
    type: Required[Literal["text", "image_url"]]
    text: str
    image_url: str
    cache_control: dict[str, str]


def chat(messages: list[Message], model: str, tools: list[ToolSpec] | None) -> str:
    assert anthropic, "LLM not initialized"
    messages, system_messages = _transform_system_messages(messages)

    messages_dicts = _handle_files(msgs2dicts(messages))

    tools_dict = [_spec2tool(tool) for tool in tools] if tools else None

    response = anthropic.beta.prompt_caching.messages.create(
        model=model,
        messages=messages_dicts,  # type: ignore
        system=system_messages,  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
        tools=tools_dict if tools_dict else NOT_GIVEN,
    )
    content = response.content
    assert content
    assert len(content) == 1
    return content[0].text  # type: ignore


def stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Generator[str, None, None]:
    assert anthropic, "LLM not initialized"
    messages, system_messages = _transform_system_messages(messages)

    messages_dicts = _handle_files(msgs2dicts(messages))

    tools_dict = [_spec2tool(tool) for tool in tools] if tools else None

    with anthropic.beta.prompt_caching.messages.stream(
        model=model,
        messages=messages_dicts,  # type: ignore
        system=system_messages,  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
        tools=tools_dict if tools_dict else NOT_GIVEN,
    ) as stream:
        yield from stream.text_stream


def _handle_files(message_dicts: list[dict]) -> list[dict]:
    return [_process_file(message_dict) for message_dict in message_dicts]


def _process_file(message_dict: dict) -> dict:
    message_content = message_dict["content"]

    # combines a content message with a list of files
    content: list[dict[str, Any]] = (
        message_content
        if isinstance(message_content, list)
        else [{"type": "text", "text": message_content}]
    )

    for f in message_dict.pop("files", []):
        f = Path(f)
        ext = f.suffix[1:]
        if ext not in ALLOWED_FILE_EXTS:
            logger.warning("Unsupported file type: %s", ext)
            continue
        if ext == "jpg":
            ext = "jpeg"
        media_type = f"image/{ext}"

        content.append(
            {
                "type": "text",
                "text": f"![{f.name}]({f.name}):",
            }
        )

        # read file
        data_bytes = f.read_bytes()
        data = base64.b64encode(data_bytes).decode("utf-8")

        # check that the file is not too large
        # anthropic limit is 5MB, seems to measure the base64-encoded size instead of raw bytes
        # TODO: use compression to reduce file size
        # print(f"{len(data)=}")
        if len(data) > 5 * 1_024 * 1_024:
            content.append(
                {
                    "type": "text",
                    "text": "Image size exceeds 5MB. Please upload a smaller image.",
                }
            )
            continue

        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            }
        )

    message_dict["content"] = content
    return message_dict


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
                files=message.files,  # type: ignore
            )

    # find consecutive user role messages and merge them together
    messages_new: list[Message] = []
    while messages:
        message = messages.pop(0)
        if messages_new and messages_new[-1].role == "user" and message.role == "user":
            messages_new[-1] = Message(
                "user",
                content=f"{messages_new[-1].content}\n\n{message.content}",
                files=messages_new[-1].files + message.files,  # type: ignore
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


def parameters2dict(parameters: list[Parameter]) -> dict[str, object]:
    required = []
    properties = {}

    for param in parameters:
        if param.required:
            required.append(param.name)
        properties[param.name] = {"type": param.type, "description": param.description}

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _spec2tool(spec: ToolSpec) -> "PromptCachingBetaToolParam":
    name = spec.name
    if spec.block_types:
        name = spec.block_types[0]

    # TODO: are input_schema and parameters the same? (both JSON Schema?)
    return {
        "name": name,
        "description": spec.get_instructions("tool"),
        "input_schema": parameters2dict(spec.parameters),
    }
