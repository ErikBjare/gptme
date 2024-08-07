import logging
from dataclasses import dataclass
from typing import Optional, TypedDict

from typing_extensions import NotRequired

logger = logging.getLogger(__name__)


@dataclass
class ModelMeta:
    provider: str
    model: str
    context: int
    max_output: Optional[int] = None

    # price in USD per 1M tokens
    # if price is not set, it is assumed to be 0
    price_input: float = 0
    price_output: float = 0


class _ModelDictMeta(TypedDict):
    context: int
    max_output: NotRequired[int]

    # price in USD per 1M tokens
    price_input: NotRequired[float]
    price_output: NotRequired[float]


# default model
DEFAULT_MODEL: str | None = None

# known models metadata
# TODO: can we get this from the API?
MODELS: dict[str, dict[str, _ModelDictMeta]] = {
    "openai": {
        # gpt-3.5
        "gpt-3.5-turbo": {
            "context": 4097,
            "price_input": 1,
            "price_output": 2,
        },
        "gpt-3.5-turbo-16k": {
            "context": 16385,
        },
        "gpt-3.5-turbo-1106": {
            "context": 16385,
        },
        # gpt-4
        "gpt-4": {
            "context": 8193,
            "price_input": 30,
            "price_output": 60,
        },
        "gpt-4-32k": {
            "context": 32769,
            "price_input": 60,
            "price_output": 120,
        },
        # gpt-4-turbo
        # https://openai.com/blog/new-models-and-developer-products-announced-at-devday
        "gpt-4-1106-preview": {
            "context": 128_000,
        },
        "gpt-4-vision-preview": {
            "context": 128_000,
        },
        "gpt-4-turbo": {
            "context": 128_000,
            "price_input": 10,
            "price_output": 30,
        },
        "gpt-4o": {
            "context": 128_000,
            "price_input": 5,
            "price_output": 15,
        },
        "gpt-4o-2024-08-06": {
            "context": 128_000,
            "price_input": 2.5,
            "price_output": 10,
        },
        "gpt-4o-mini": {
            "context": 128_000,
            "price_input": 0.15,
            "price_output": 0.6,
        },
    },
    "anthropic": {
        "claude-3-opus-20240229": {
            "context": 200_000,
            "max_output": 4096,
            "price_input": 15,
            "price_output": 75,
        },
        "claude-3-5-sonnet-20240620": {
            "context": 200_000,
            "max_output": 4096,
            "price_input": 3,
            "price_output": 15,
        },
        "claude-3-haiku-20240307": {
            "context": 200_000,
            "max_output": 4096,
            "price_input": 0.25,
            "price_output": 1.25,
        },
    },
    "local": {
        # 8B
        "llama3": {
            "context": 8193,
        },
    },
}


def set_default_model(model: str) -> None:
    assert get_model(model)
    global DEFAULT_MODEL
    DEFAULT_MODEL = model


def get_model(model: str | None = None) -> ModelMeta:
    if model is None:
        assert DEFAULT_MODEL, "Default model not set, set it with set_default_model()"
        model = DEFAULT_MODEL

    if "/" in model:
        provider, model = model.split("/")
        if provider not in MODELS or model not in MODELS[provider]:
            logger.warning(
                f"Model {provider}/{model} not found, using fallback model metadata"
            )
            return ModelMeta(provider=provider, model=model, context=4000)
    else:
        # try to find model in all providers
        for provider in MODELS:
            if model in MODELS[provider]:
                break
        else:
            logger.warning(f"Model {model} not found, using fallback model metadata")
            return ModelMeta(provider="unknown", model=model, context=4000)

    return ModelMeta(
        provider=provider,
        model=model,
        **MODELS[provider][model],
    )
