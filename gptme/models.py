from typing import TypedDict


class ModelDict(TypedDict):
    context: int


MODELS: dict[str, dict[str, ModelDict]] = {
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


def get_model(model: str) -> ModelDict:
    if "/" in MODELS:
        provider, model = model.split("/")
    else:
        provider = "openai"
    return MODELS[provider][model]
