import logging
from collections.abc import Generator
from typing import TYPE_CHECKING

from gptme.config import Provider
from gptme.llm import LLMAPIConfig

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


def init(llm_cfg: LLMAPIConfig):
    global openai
    from openai import AzureOpenAI, OpenAI  # fmt: skip

    # FIXME: refactor to merge same constructors
    if llm_cfg.provider == Provider.OPENAI:
        base_url = llm_cfg.endpoint or "https://api.openai.com/v1"
        openai = OpenAI(api_key=llm_cfg.token, base_url=str(base_url))
    elif llm_cfg.provider == Provider.AZURE_OPENAI:
        openai = AzureOpenAI(
            api_key=llm_cfg.token,
            api_version="2023-07-01-preview",
            azure_endpoint=str(llm_cfg.endpoint),
        )
    elif llm_cfg.provider == Provider.OPENROUTER:
        openai = OpenAI(api_key=llm_cfg.token, base_url="https://openrouter.ai/api/v1")
    elif llm_cfg.provider == Provider.LOCAL:
        openai = OpenAI(api_key=llm_cfg.token, base_url=str(llm_cfg.endpoint))
    else:
        raise ValueError(f"Unknown LLM: {llm_cfg.provider.value}")

    assert openai, "LLM not initialized"


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
        messages=msgs2dicts(messages, openai=True),  # type: ignore
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
        messages=msgs2dicts(_prep_o1(messages), openai=True),  # type: ignore
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
