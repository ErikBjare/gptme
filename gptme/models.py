import logging
from dataclasses import dataclass
from typing import TypedDict

from typing_extensions import NotRequired

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


def set_default_model(model: str) -> None:
    modelmeta = get_model(model)
    assert modelmeta
    global DEFAULT_MODEL
    DEFAULT_MODEL = modelmeta


def get_model(model: str | None = None) -> ModelMeta:
    if model is None:
        assert DEFAULT_MODEL, "Default model not set, set it with set_default_model()"
        return DEFAULT_MODEL

    # if only provider is given, get recommended model
    if model in PROVIDERS:
        provider = model
        model = get_recommended_model(provider)
        return get_model(f"{provider}/{model}")

    if any(f"{provider}/" in model for provider in PROVIDERS):
        provider, model = model.split("/", 1)
        if provider not in MODELS or model not in MODELS[provider]:
            if provider not in ["openrouter", "local"]:
                logger.warning(
                    f"Unknown model {model} from {provider}, using fallback metadata"
                )
            return ModelMeta(provider=provider, model=model, context=128_000)
    else:
        # try to find model in all providers
        for provider in MODELS:
            if model in MODELS[provider]:
                break
        else:
            logger.warning(f"Unknown model {model}, using fallback metadata")
            return ModelMeta(provider="unknown", model=model, context=128_000)

    return ModelMeta(
        provider=provider,
        model=model,
        **MODELS[provider][model],
    )


def get_recommended_model(provider: str) -> str:  # pragma: no cover
    if provider == "openai":
        return "gpt-4o"
    elif provider == "openrouter":
        return "meta-llama/llama-3.1-405b-instruct"
    elif provider == "anthropic":
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
