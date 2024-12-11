import base64
import logging
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..config import Config
from ..constants import TEMPERATURE, TOP_P
from ..message import Message, msgs2dicts
from ..tools.base import Parameter, ToolSpec
from .models import Provider, get_model

if TYPE_CHECKING:
    # noreorder
    from openai import OpenAI  # fmt: skip
    from openai.types.chat import ChatCompletionToolParam  # fmt: skip

openai: "OpenAI | None" = None
logger = logging.getLogger(__name__)


# Shows in rankings on openrouter.ai
openrouter_headers = {
    "HTTP-Referer": "https://github.com/ErikBjare/gptme",
    "X-Title": "gptme",
}


ALLOWED_FILE_EXTS = ["jpg", "jpeg", "png", "gif"]


def init(provider: Provider, config: Config):
    global openai
    from openai import AzureOpenAI, OpenAI  # fmt: skip

    if provider == "openai":
        api_key = config.get_env_required("OPENAI_API_KEY")
        openai = OpenAI(api_key=api_key)
    elif provider == "azure":
        api_key = config.get_env_required("AZURE_OPENAI_API_KEY")
        azure_endpoint = config.get_env_required("AZURE_OPENAI_ENDPOINT")
        openai = AzureOpenAI(
            api_key=api_key,
            api_version="2023-07-01-preview",
            azure_endpoint=azure_endpoint,
        )
    elif provider == "openrouter":
        api_key = config.get_env_required("OPENROUTER_API_KEY")
        openai = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    elif provider == "gemini":
        api_key = config.get_env_required("GEMINI_API_KEY")
        openai = OpenAI(
            api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta"
        )
    elif provider == "xai":
        api_key = config.get_env_required("XAI_API_KEY")
        openai = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    elif provider == "groq":
        api_key = config.get_env_required("GROQ_API_KEY")
        openai = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    elif provider == "deepseek":
        api_key = config.get_env_required("DEEPSEEK_API_KEY")
        openai = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    elif provider == "local":
        # OPENAI_API_BASE renamed to OPENAI_BASE_URL: https://github.com/openai/openai-python/issues/745
        api_base = config.get_env("OPENAI_API_BASE")
        api_base = api_base or config.get_env("OPENAI_BASE_URL")
        if not api_base:
            raise KeyError("Missing environment variable OPENAI_BASE_URL")
        api_key = config.get_env("OPENAI_API_KEY") or "ollama"
        openai = OpenAI(api_key=api_key, base_url=api_base)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    assert openai, "Provider not initialized"


def get_provider() -> Provider | None:
    # used when checking for provider-specific capabilities
    if not openai:
        return None
    if "openai.com" in str(openai.base_url):
        return "openai"
    if "openrouter.ai" in str(openai.base_url):
        return "openrouter"
    if "groq.com" in str(openai.base_url):
        return "groq"
    if "x.ai" in str(openai.base_url):
        return "xai"
    if "deepseek.com" in str(openai.base_url):
        return "deepseek"
    return "local"


def get_client() -> "OpenAI | None":
    return openai


def _prep_o1(msgs: list[Message]) -> Generator[Message, None, None]:
    # prepare messages for OpenAI O1, which doesn't support the system role
    # and requires the first message to be from the user
    for msg in msgs:
        if msg.role == "system":
            msg = msg.replace(
                role="user", content=f"<system>\n{msg.content}\n</system>"
            )
        yield msg


def chat(messages: list[Message], model: str, tools: list[ToolSpec] | None) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    assert openai, "LLM not initialized"

    is_o1 = model.startswith("o1")
    if is_o1:
        messages = list(_prep_o1(messages))

    messages_dicts = handle_files(msgs2dicts(messages))
    _transform_msgs_for_special_provider(messages_dicts)

    from openai import NOT_GIVEN  # fmt: skip

    tools_dict = [_spec2tool(tool) for tool in tools] if tools else None

    response = openai.chat.completions.create(
        model=model,
        messages=messages_dicts,  # type: ignore
        temperature=TEMPERATURE if not is_o1 else NOT_GIVEN,
        top_p=TOP_P if not is_o1 else NOT_GIVEN,
        tools=tools_dict if tools_dict else NOT_GIVEN,
        extra_headers=(
            openrouter_headers if "openrouter.ai" in str(openai.base_url) else {}
        ),
    )
    content = response.choices[0].message.content
    assert content
    return content


def stream(
    messages: list[Message], model: str, tools: list[ToolSpec] | None
) -> Generator[str, None, None]:
    assert openai, "LLM not initialized"
    stop_reason = None

    is_o1 = model.startswith("o1")
    if is_o1:
        messages = list(_prep_o1(messages))

    messages_dicts = handle_files(msgs2dicts(messages))
    _transform_msgs_for_special_provider(messages_dicts)

    from openai import NOT_GIVEN  # fmt: skip

    tools_dict = [_spec2tool(tool) for tool in tools] if tools else None

    for chunk_raw in openai.chat.completions.create(
        model=model,
        messages=messages_dicts,  # type: ignore
        temperature=TEMPERATURE if not is_o1 else NOT_GIVEN,
        top_p=TOP_P if not is_o1 else NOT_GIVEN,
        stream=True,
        tools=tools_dict if tools_dict else NOT_GIVEN,
        # the llama-cpp-python server needs this explicitly set, otherwise unreliable results
        # TODO: make this better
        # max_tokens=(
        #     (1000 if not model.startswith("gpt-") else 4096)
        # ),
        extra_headers=(
            openrouter_headers if "openrouter.ai" in str(openai.base_url) else {}
        ),
    ):
        from openai.types.chat import ChatCompletionChunk  # fmt: skip
        from openai.types.chat.chat_completion_chunk import (  # fmt: skip
            ChoiceDeltaToolCall,
            ChoiceDeltaToolCallFunction,
        )

        # Cast the chunk to the correct type
        chunk = cast(ChatCompletionChunk, chunk_raw)

        if not chunk.choices:
            # Got a chunk with no choices, Azure always sends one of these at the start
            continue

        choice = chunk.choices[0]
        stop_reason = choice.finish_reason
        delta = choice.delta

        if delta.content is not None:
            yield delta.content

        # Handle tool calls
        if delta.tool_calls:
            for tool_call in delta.tool_calls:
                if isinstance(tool_call, ChoiceDeltaToolCall) and tool_call.function:
                    func = tool_call.function
                    if isinstance(func, ChoiceDeltaToolCallFunction):
                        if func.name:
                            yield f"\n@{func.name}: "
                        if func.arguments:
                            yield func.arguments

    logger.debug(f"Stop reason: {stop_reason}")


def handle_files(msgs: list[dict]) -> list[dict]:
    return [_process_file(msg) for msg in msgs]


def _process_file(msg: dict) -> dict:
    message_content = msg["content"]
    model = get_model()
    if model.provider == "deepseek":
        # deepseek does not support files
        return msg

    # combines a content message with a list of files
    content: list[dict[str, Any]] = (
        message_content
        if isinstance(message_content, list)
        else [{"type": "text", "text": message_content}]
    )

    has_images = False

    for f in msg.get("files", []):
        f = Path(f)
        ext = f.suffix[1:]
        if ext not in ALLOWED_FILE_EXTS:
            logger.warning("Unsupported file type: %s", ext)
            continue
        if not model.supports_vision:
            logger.warning("Model does not support vision")
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
        # openai limit is 20MB
        # TODO: use compression to reduce file size
        # TODO: check that the limit is measured with the base64 for openai
        # print(f"{len(data)=}")
        if len(data) > 20 * 1_024 * 1_024:
            content.append(
                {
                    "type": "text",
                    "text": "Image size exceeds 20MB. Please upload a smaller image.",
                }
            )
            continue

        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{data}"},
            }
        )
        has_images = True

    msg["content"] = content

    if msg["role"] == "system" and has_images:
        # Images must come from user with openai
        msg["role"] = "user"

    return msg


def _transform_msgs_for_special_provider(messages_dicts: list[dict]):
    if get_provider() == "groq":
        # groq needs message.content to be a string
        messages_dicts = [
            {**msg, "content": msg["content"][0]["text"]} for msg in messages_dicts
        ]


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


def _spec2tool(spec: ToolSpec) -> "ChatCompletionToolParam":
    name = spec.name
    if spec.block_types:
        name = spec.block_types[0]

    description = spec.get_instructions("tool")
    if len(description) > 1024:
        logger.warning(
            "Description for tool `%s` is too long ( %d > 1024 chars). Truncating...",
            spec.name,
            len(description),
        )
        description = description[:1024]

    provider = get_provider()
    if provider in ["openai", "azure", "openrouter", "local"]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters2dict(spec.parameters),
                # "strict": False,  # not supported by OpenRouter
            },
        }
    else:
        raise ValueError("Provider doesn't support tools API")
