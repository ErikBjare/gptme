import logging
from dataclasses import dataclass
from typing import TypedDict

from typing_extensions import NotRequired

from gptme.config import Provider

from .llm_openai_models import OPENAI_MODELS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelMeta:
    provider: str
    model: str
    context: int
    max_output: int | None = None

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


# available providers
PROVIDERS = ["openai", "anthropic", "azure", "openrouter", "local"]

# default model
DEFAULT_MODEL: ModelMeta | None = None

# known models metadata
# TODO: can we get this from the API?
MODELS: dict[str, dict[str, _ModelDictMeta]] = {
    "openai": OPENAI_MODELS,
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


def set_default_model(model: str, provider: Provider) -> None:
    modelmeta = get_model(model, provider)
    assert modelmeta
    global DEFAULT_MODEL
    DEFAULT_MODEL = modelmeta


def get_model(model: str | None = None, provider: Provider | None = None) -> ModelMeta:
    if model is None:
        assert DEFAULT_MODEL, "Default model not set, set it with set_default_model()"
        return DEFAULT_MODEL

    if provider and not model:
        model = get_recommended_model(provider)

    logger.debug("provider: %s, model: %s", provider, model)
    # TODO: convert to ModelMeta from LLMAPIConfig
    if provider in [x for x in Provider]:
        if provider not in MODELS or model not in MODELS[provider]:
            if provider not in (Provider.OPENROUTER, Provider.LOCAL):
                logger.warning( f"Unknown model {model} from {provider}, using fallback metadata")
            return ModelMeta(provider=provider.value, model=model, context=128_000)
    else:
        # try to find model in all providers
        all_models = [model for prov in MODELS.values() for model in prov.values()]
        logger.debug("all_models: %s", all_models)
        if model not in all_models:
            logger.warning(f"Unknown model {model}, using fallback metadata")
            return ModelMeta(provider="unknown", model=model, context=128_000)

    return ModelMeta(
        provider=provider.value,
        model=model,
        **MODELS[provider][model],
    )


def get_recommended_model(provider: Provider) -> str:  # pragma: no cover
    if provider == Provider.OPENAI:
        return "gpt-4o"
    elif provider == Provider.OPENROUTER:
        return "meta-llama/llama-3.1-405b-instruct"
    elif provider ==Provider.ANTHROPIC:
        return "claude-3-5-sonnet-20240620"
    else:
        raise ValueError(f"Unknown provider {provider}")


def get_summary_model(provider: str) -> str:  # pragma: no cover
    if provider == "openai":
        return "gpt-4o-mini"
    elif provider == "openrouter":
        return "meta-llama/llama-3.1-8b-instruct"
    elif provider == "anthropic":
        return "claude-3-haiku-20240307"
    else:
        raise ValueError(f"Unknown provider {provider}")
