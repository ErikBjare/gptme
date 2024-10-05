Providers
=========

We support several LLM providers, including OpenAI, Anthropic, Azure, and any OpenAI-compatible server (e.g. `ollama`, `llama-cpp-python`).

To select a provider and model, run `gptme` with the `--model` flag set to `<provider>/<model>`, for example:

```sh
gptme --model openai/gpt-4o "hello"
gptme --model anthropic "hello"  # if model part unspecified, will fall back to the provider default
gptme --model openrouter/meta-llama/llama-3.1-70b-instruct "hello"
gptme --model local/ollama "hello"
```

On first startup, if `--model` is not set, and no API keys are set in the config or environment it will be prompted for. It will then auto-detect the provider, and save the key in the configuration file.

## OpenAI

To use OpenAI, set your API key:

```sh
export OPENAI_API_KEY="your-api-key"
```

## Anthropic

To use Anthropic, set your API key:

```sh
export ANTHROPIC_API_KEY="your-api-key"
```

## OpenRouter

To use OpenRouter, set your API key:

```sh
export OPENROUTER_API_KEY="your-api-key"
```

## Local

There are several ways to run local LLM models in a way that exposes a OpenAI API-compatible server, here we will cover:

### ollama + litellm

Here's how to use `ollama`, with the `litellm` proxy to provide the API-compatible server.

You first need to install `ollama` and `litellm`.

```sh
ollama pull mistral
ollama serve
litellm --model ollama/mistral
export OPENAI_API_BASE="http://localhost:8000"
```
