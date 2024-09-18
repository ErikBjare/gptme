from typing import TypedDict
from typing_extensions import NotRequired


class _ModelDictMeta(TypedDict):
    context: int
    max_output: NotRequired[int]
    price_input: NotRequired[float]
    price_output: NotRequired[float]


OPENAI_MODELS: dict[str, _ModelDictMeta] = {
    # GPT-4o
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
    "gpt-4o-2024-05-13": {
        "context": 128_000,
        "price_input": 5,
        "price_output": 15,
    },
    # GPT-4o mini
    "gpt-4o-mini": {
        "context": 128_000,
        "price_input": 0.15,
        "price_output": 0.6,
    },
    "gpt-4o-mini-2024-07-18": {
        "context": 128_000,
        "price_input": 0.15,
        "price_output": 0.6,
    },
    # OpenAI o1-preview
    "o1-preview": {
        "context": 128_000,
        "price_input": 15,
        "price_output": 60,
    },
    "o1-preview-2024-09-12": {
        "context": 128_000,
        "price_input": 15,
        "price_output": 60,
    },
    # OpenAI o1-mini
    "o1-mini": {
        "context": 128_000,
        "price_input": 3,
        "price_output": 12,
    },
    "o1-mini-2024-09-12": {
        "context": 128_000,
        "price_input": 3,
        "price_output": 12,
    },
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "context": 128_000,
        "price_input": 10,
        "price_output": 30,
    },
    "gpt-4-turbo-2024-04-09": {
        "context": 128_000,
        "price_input": 10,
        "price_output": 30,
    },
    "gpt-4-0125-preview": {
        "context": 128_000,
        "price_input": 10,
        "price_output": 30,
    },
    "gpt-4-1106-preview": {
        "context": 128_000,
        "price_input": 10,
        "price_output": 30,
    },
    "gpt-4-vision-preview": {
        "context": 128_000,
        "price_input": 10,
        "price_output": 30,
    },
    # GPT-4
    "gpt-4": {
        "context": 8192,
        "price_input": 30,
        "price_output": 60,
    },
    "gpt-4-32k": {
        "context": 32768,
        "price_input": 60,
        "price_output": 120,
    },
    # GPT-3.5 Turbo
    "gpt-3.5-turbo-0125": {
        "context": 16385,
        "price_input": 0.5,
        "price_output": 1.5,
    },
    "gpt-3.5-turbo": {
        "context": 16385,
        "price_input": 0.5,
        "price_output": 1.5,
    },
    "gpt-3.5-turbo-instruct": {
        "context": 4096,
        "price_input": 1.5,
        "price_output": 2,
    },
    # Deprecated models (kept for reference)
    "gpt-3.5-turbo-1106": {
        "context": 16385,
        "price_input": 1,
        "price_output": 2,
    },
    "gpt-3.5-turbo-0613": {
        "context": 4096,
        "price_input": 1.5,
        "price_output": 2,
    },
    "gpt-3.5-turbo-16k-0613": {
        "context": 16385,
        "price_input": 3,
        "price_output": 4,
    },
    "gpt-3.5-turbo-0301": {
        "context": 4096,
        "price_input": 1.5,
        "price_output": 2,
    },
    # Other models
    "davinci-002": {
        "context": 4096,  # Assuming default context size
        "price_input": 2,
        "price_output": 2,
    },
    "babbage-002": {
        "context": 4096,  # Assuming default context size
        "price_input": 0.4,
        "price_output": 0.4,
    },
}
