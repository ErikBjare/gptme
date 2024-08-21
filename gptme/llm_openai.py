import logging
from collections.abc import Generator
from typing import TYPE_CHECKING

from .constants import TEMPERATURE, TOP_P
from .message import Message, msgs2dicts

if TYPE_CHECKING:
    from openai import OpenAI

openai: "OpenAI | None" = None
logger = logging.getLogger(__name__)


# Shows in rankings on openrouter.ai
openrouter_headers = {
    "HTTP-Referer": "https://github.com/ErikBjare/gptme",
    "X-Title": "gptme",
}


def init(llm: str, config):
    global openai
    from openai import AzureOpenAI, OpenAI  # fmt: skip

    if llm == "openai":
        api_key = config.get_env_required("OPENAI_API_KEY")
        openai = OpenAI(api_key=api_key)
    elif llm == "azure":
        api_key = config.get_env_required("AZURE_OPENAI_API_KEY")
        azure_endpoint = config.get_env_required("AZURE_OPENAI_ENDPOINT")
        openai = AzureOpenAI(
            api_key=api_key,
            api_version="2023-07-01-preview",
            azure_endpoint=azure_endpoint,
        )
    elif llm == "openrouter":
        api_key = config.get_env_required("OPENROUTER_API_KEY")
        openai = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    elif llm == "local":
        api_base = config.get_env_required("OPENAI_API_BASE")
        api_key = config.get_env("OPENAI_API_KEY") or "ollama"
        openai = OpenAI(api_key=api_key, base_url=api_base)
    else:
        raise ValueError(f"Unknown LLM: {llm}")

    assert openai, "LLM not initialized"


def get_client() -> "OpenAI | None":
    return openai


def chat(messages: list[Message], model: str) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    assert openai, "LLM not initialized"
    response = openai.chat.completions.create(
        model=model,
        messages=msgs2dicts(messages, openai=True),  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
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
        messages=msgs2dicts(messages, openai=True),  # type: ignore
        temperature=TEMPERATURE,
        top_p=TOP_P,
        stream=True,
        # the llama-cpp-python server needs this explicitly set, otherwise unreliable results
        # TODO: make this better
        max_tokens=1000 if not model.startswith("gpt-") else 4096,
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
