import base64
import logging
from collections.abc import Generator
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypedDict,
    cast,
)

from ..constants import TEMPERATURE, TOP_P
from ..message import Message, msgs2dicts
from ..tools.base import Parameter, ToolSpec

if TYPE_CHECKING:
    # noreorder
    import anthropic.types  # fmt: skip
    from anthropic import Anthropic  # fmt: skip

logger = logging.getLogger(__name__)

_anthropic: "Anthropic | None" = None

ALLOWED_FILE_EXTS = ["jpg", "jpeg", "png", "gif"]


def init(config):
    global _anthropic
    api_key = config.get_env_required("ANTHROPIC_API_KEY")
    from anthropic import Anthropic  # fmt: skip

    _anthropic = Anthropic(
        api_key=api_key,
        max_retries=5,
    )


def get_client() -> "Anthropic | None":
    return _anthropic


class CacheControl(TypedDict):
    type: Literal["ephemeral"]


def chat(messages: list[Message], model: str, tools: list[ToolSpec] | None) -> str:
    from anthropic import NOT_GIVEN  # fmt: skip

    assert _anthropic, "LLM not initialized"
    messages_dicts, system_messages, tools_dict = _prepare_messages_for_api(
        messages, tools
    )

    response = _anthropic.messages.create(
        model=model,
        messages=messages_dicts,
        system=system_messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
        tools=tools_dict if tools_dict else NOT_GIVEN,
    )
    content = response.content
    logger.debug(response.usage)
    assert content
    assert len(content) == 1
    return content[0].text  # type: ignore


def stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Generator[str, None, None]:
    import anthropic.types  # fmt: skip
    from anthropic import NOT_GIVEN  # fmt: skip

    assert _anthropic, "LLM not initialized"
    messages_dicts, system_messages, tools_dict = _prepare_messages_for_api(
        messages, tools
    )

    with _anthropic.messages.stream(
        model=model,
        messages=messages_dicts,
        system=system_messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=4096,
        tools=tools_dict if tools_dict else NOT_GIVEN,
    ) as stream:
        for chunk in stream:
            match chunk.type:
                case "content_block_start":
                    chunk = cast(anthropic.types.RawContentBlockStartEvent, chunk)
                    block = chunk.content_block
                    if isinstance(block, anthropic.types.ToolUseBlock):
                        tool_use = block
                        yield f"\n@{tool_use.name}: "
                    elif isinstance(block, anthropic.types.TextBlock):
                        if block.text:
                            logger.warning("unexpected text block: %s", block.text)
                    else:
                        print(f"Unknown block type: {block}")
                case "content_block_delta":
                    chunk = cast(anthropic.types.RawContentBlockDeltaEvent, chunk)
                    delta = chunk.delta
                    if isinstance(delta, anthropic.types.TextDelta):
                        yield delta.text
                    elif isinstance(delta, anthropic.types.InputJSONDelta):
                        yield delta.partial_json
                    else:
                        logger.warning("Unknown delta type: %s", delta)
                case "content_block_stop":
                    pass
                case "text":
                    # full text message
                    pass
                case "message_start":
                    chunk = cast(
                        anthropic.types.MessageStartEvent,
                        chunk,
                    )
                    logger.debug(chunk.message.usage)
                case "message_delta":
                    chunk = cast(anthropic.types.MessageDeltaEvent, chunk)
                    logger.debug(chunk.usage)
                case "message_stop":
                    pass
                case _:
                    # print(f"Unknown chunk type: {chunk.type}")
                    pass


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
        f = Path(f).expanduser()
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
) -> tuple[list[Message], list["anthropic.types.TextBlockParam"]]:
    """Transform system messages into Anthropic's expected format.

    This function:
    1. Extracts the first system message as the main system prompt
    2. Transforms subsequent system messages into <system> tags in user messages
    3. Merges consecutive user messages
    4. Applies cache control to optimize performance

    Note: Anthropic allows up to 4 cache breakpoints in a conversation.
    We use this to cache:
    1. The system prompt (if long enough)
    2. Earlier messages in multi-turn conversations

    Returns:
        tuple[list[Message], list[TextBlockParam]]: Transformed messages and system messages
    """
    assert messages[0].role == "system"
    system_prompt = messages[0].content
    messages = messages.copy()
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
    system_messages: list[anthropic.types.TextBlockParam] = [
        {
            "type": "text",
            "text": system_prompt,
        }
    ]

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


def _spec2tool(
    spec: ToolSpec,
) -> "anthropic.types.ToolParam":
    name = spec.name
    if spec.block_types:
        name = spec.block_types[0]

    # TODO: are input_schema and parameters the same? (both JSON Schema?)
    return {
        "name": name,
        "description": spec.get_instructions("tool"),
        "input_schema": parameters2dict(spec.parameters),
    }


def _prepare_messages_for_api(
    messages: list[Message], tools: list[ToolSpec] | None
) -> tuple[
    list["anthropic.types.MessageParam"],
    list["anthropic.types.TextBlockParam"],
    list["anthropic.types.ToolParam"] | None,
]:
    """Prepare messages for the Anthropic API.

    This function:
    1. Transforms system messages
    2. Handles file attachments
    3. Applies cache control
    4. Prepares tools

    Args:
        messages: List of messages to prepare
        tools: List of tool specifications

    Returns:
        tuple containing:
        - Prepared message dictionaries
        - System messages
        - Tool dictionaries (if tools provided)
    """
    # noreorder
    import anthropic.types  # fmt: skip

    # Transform system messages
    messages, system_messages = _transform_system_messages(messages)

    # Handle files and convert to dicts
    messages_dicts = _handle_files(msgs2dicts(messages))

    # Apply cache control to optimize performance
    messages_dicts_new: list[anthropic.types.MessageParam] = []
    for msg in messages_dicts:
        content_parts: list[
            anthropic.types.TextBlockParam
            | anthropic.types.ImageBlockParam
            | anthropic.types.ToolUseBlockParam
            | anthropic.types.ToolResultBlockParam
        ] = []
        raw_content = (
            msg["content"]
            if isinstance(msg["content"], list)
            else [{"type": "text", "text": msg["content"]}]
        )

        for part in raw_content:
            if isinstance(part, dict):
                content_parts.append(part)  # type: ignore
            else:
                content_parts.append({"type": "text", "text": str(part)})

        messages_dicts_new.append({"role": msg["role"], "content": content_parts})

    # set for the first system message (static between sessions)
    system_messages[0]["cache_control"] = {"type": "ephemeral"}

    # set cache points at the two last user messages, as suggested in Anthropic docs:
    # > The conversation history (previous messages) is included in the messages array.
    # > The final turn is marked with cache-control, for continuing in followups.
    # > The second-to-last user message is marked for caching with the cache_control parameter, so that this checkpoint can read from the previous cache.
    # https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching#continuing-a-multi-turn-conversation
    for msgp in [msg for msg in messages_dicts_new if msg["role"] == "user"][-2:]:
        assert isinstance(msgp["content"], list)
        msgp["content"][-1]["cache_control"] = {"type": "ephemeral"}  # type: ignore

    # Prepare tools
    tools_dict = [_spec2tool(tool) for tool in tools] if tools else None

    return messages_dicts_new, system_messages, tools_dict
