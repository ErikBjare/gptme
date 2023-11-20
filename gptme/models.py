import logging
from dataclasses import dataclass
from typing import TypedDict

from typing_extensions import NotRequired

logger = logging.getLogger(__name__)


@dataclass
class ModelMeta:
    provider: str
    model: str
    context: int

    # price in USD per 1k tokens
    # if price is not set, it is assumed to be 0
    price_input: float = 0
    price_output: float = 0


class _ModelDictMeta(TypedDict):
    context: int

    # price in USD per 1k tokens
    price_input: NotRequired[float]
    price_output: NotRequired[float]


# default model
DEFAULT_MODEL: str | None = None

# known models metadata
# TODO: can we get this from the API?
MODELS: dict[str, dict[str, _ModelDictMeta]] = {
    "openai": {
        "gpt-4": {
            "context": 8193,
            # 0.03 USD per 1k input tokens
            # 0.06 USD per 1k output tokens
            "price_input": 0.03,
            "price_output": 0.06,
        },
        "gpt-3.5-turbo": {
            "context": 4097,
            # 0.001 USD per 1k input tokens
            # 0.002 USD per 1k output tokens
            "price_input": 0.001,
            "price_output": 0.002,
        },
        "gpt-3.5-turbo-16k": {
            "context": 16385,
        },
        # gpt-4-turbo
        # https://openai.com/blog/new-models-and-developer-products-announced-at-devday
        "gpt-4-1106-preview": {
            "context": 128_000,
        },
        "gpt-4-vision-preview": {
            "context": 128_000,
        },
        "gpt-3.5-turbo-1106": {
            "context": 16385,
        },
    }
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
