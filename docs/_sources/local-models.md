Local Models
============

This is a guide to setting up a local model for use with gptme.

## Setup

There are several ways to run local LLM models in a way that exposes a OpenAI API-compatible server, here we will cover two:

### ollama + litellm

Here's how to use `ollama`, with the `litellm` proxy to provide the API-compatible server.

You first need to install `ollama` and `litellm`.

```sh
ollama pull mistral
ollama serve
litellm --model ollama/mistral
export OPENAI_API_BASE="http://localhost:8000"
```

### llama-cpp-python

Here's how to use `llama-cpp-python`.

You first need to install and run the [llama-cpp-python][llama-cpp-python] server. To ensure you get the most out of your hardware, make sure you build it with [the appropriate hardware acceleration][hwaccel]. For macOS, you can find detailed instructions [here][metal].

```sh
MODEL=~/ML/wizardcoder-python-13b-v1.0.Q4_K_M.gguf
poetry run python -m llama_cpp.server --model $MODEL --n_gpu_layers 1  # Use `--n_gpu_layer 1` if you have a M1/M2 chip
export OPENAI_API_BASE="http://localhost:8000/v1"
```

## Usage

```sh
gptme --llm local "say hello!"
```


## How well does it work?

I've had mixed results. They are not nearly as good as GPT-4, and often struggles with the tools laid out in the system prompt. However I haven't tested with models larger than 7B/13B.

I'm hoping future models, trained better for tool-use and interactive coding (where outputs are fed back), can remedy this, even at 7B/13B model sizes. Perhaps we can fine-tune a model on (GPT-4) conversation logs to create a purpose-fit model that knows how to use the tools.

[llama-cpp-python]: https://github.com/abetlen/llama-cpp-python
[hwaccel]: https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration
[metal]: https://github.com/abetlen/llama-cpp-python/blob/main/docs/install/macos.md
