import logging
from collections.abc import Generator
from typing import TYPE_CHECKING

from .config import Config
from .constants import TEMPERATURE, TOP_P
from .message import Message, msgs2dicts
from .models import Provider

if TYPE_CHECKING:
    from openai import OpenAI


openai: "OpenAI | None" = None
logger = logging.getLogger(__name__)


# Shows in rankings on openrouter.ai
openrouter_headers = {
    "HTTP-Referer": "https://github.com/ErikBjare/gptme",
    "X-Title": "gptme",
}


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


def chat(messages: list[Message], model: str) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    assert openai, "LLM not initialized"
    is_o1 = model.startswith("o1")
    if is_o1:
        messages = list(_prep_o1(messages))

    # noreorder
    from openai._types import NOT_GIVEN  # fmt: skip

    response = openai.chat.completions.create(
        model=model,
        messages=msgs2dicts(messages, provider=get_provider()),  # type: ignore
        temperature=TEMPERATURE if not is_o1 else NOT_GIVEN,
        top_p=TOP_P if not is_o1 else NOT_GIVEN,
        extra_headers=(
            openrouter_headers if "openrouter.ai" in str(openai.base_url) else {}
        ),
    )
    content = response.choices[0].message.content
    assert content
    return content


def stream(messages: list[Message], model: str) -> Generator[str, None, None]:
    assert openai, "LLM not initialized"
    stop_reason = None
    for chunk in openai.chat.completions.create(
        model=model,
        messages=msgs2dicts(_prep_o1(messages), provider=get_provider()),  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        stream=True,
        # the llama-cpp-python server needs this explicitly set, otherwise unreliable results
        # TODO: make this better
        # max_tokens=(
        #     (1000 if not model.startswith("gpt-") else 4096)
        # ),
        extra_headers=(
            openrouter_headers if "openrouter.ai" in str(openai.base_url) else {}
        ),
    ):
        if not chunk.choices:  # type: ignore
            # Got a chunk with no choices, Azure always sends one of these at the start
            continue
        stop_reason = chunk.choices[0].finish_reason  # type: ignore
        content = chunk.choices[0].delta.content  # type: ignore
        if content:
            yield content
    logger.debug(f"Stop reason: {stop_reason}")
