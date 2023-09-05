GPTMe
=====

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)

An interactive CLI to interact with LLMs in a Chat-style interface, with additional capabilities like executing commands on the local machine.

## Features

 - Directly execute suggested shell commands on the local machine.
   - Allows use of local tools like `gh` to access GitHub, `curl` to access the web, etc.
   - Also spins up a Python REPL to run Python code interactively.
   - Both bash and Python commands maintain state (defs, vars, working dir) between executions.
 - Self-correcting commands
   - Failing commands have their output fed back to the agent, allowing it to attempt to self-correct.
 - Support for OpenAI's GPT-4 and **any model that runs in llama.cpp**
   - Thanks to llama-cpp-server!
 - Handles long contexts through summarization, truncation, and pinning.
   - (wip, not very well developed)

### Demo (TODO)

Steps:

1. Create a new dir 'gptme-test-fib' and git init
2. Write a fibonacci function in Python to fib.py, commit
3. Create a repo and push to GitHub

(I will be creating a screencast of this soon, but it works today!)

### Getting started

Install dependencies:
```sh
poetry install  # or: pip install .
```

(optional) To run local models, you need to start llama-cpp-server:
```sh
MODEL=~/ML/WizardCoder-Python-34B-V1.0-GGUF/wizardcoder-python-34b-v1.0.Q5_K_M.gguf
poetry run python -m llama_cpp.server --model $MODEL
```

Then you can interact with it using:
```sh
gptme --llm llama
```

### Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [COMMAND]

  GPTMe, a chat-CLI for LLMs enabling them to execute commands and code.

Options:
  -v, --verbose TEXT
  --name TEXT           Folder name for conversation, defaults to today's date
  --llm [openai|llama]  LLM to use.
  --stream              Stream responses
  --prompt TEXT         System prompt. Can be 'full', 'short', or something
                        custom.
  --help                Show this message and exit.
```
