import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class ModelDict(TypedDict):
    provider: str
    model: str
    context: int


class _ModelDictMeta(TypedDict):
    context: int


# default model
DEFAULT_MODEL: str | None = None

# known models metadata
# TODO: can we get this from the API?
MODELS: dict[str, dict[str, _ModelDictMeta]] = {
    "openai": {
        "gpt-4": {
            "context": 8193,
        },
        "gpt-3.5-turbo": {
            "context": 4097,
        },
        "gpt-3.5-turbo-16k": {
            "context": 16385,
        },
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


def get_model(model: str | None = None) -> ModelDict:
    if model is None:
        assert DEFAULT_MODEL, "Default model not set, set it with set_default_model()"
        model = DEFAULT_MODEL

    if "/" in model:
        provider, model = model.split("/")
        if provider not in MODELS or model not in MODELS[provider]:
            logger.warning(
                f"Model {provider}/{model} not found, using fallback model metadata"
            )
            return ModelDict(provider=provider, model=model, context=4000)
    else:
        # try to find model in all providers
        for provider in MODELS:
            if model in MODELS[provider]:
                break
        else:
            logger.warning(f"Model {model} not found, using fallback model metadata")
            return ModelDict(provider="unknown", model=model, context=4000)

    return ModelDict(provider=provider, model=model, **MODELS[provider][model])
