GPTMe
=====

*/ʤiː piː tiː miː/*

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)

A fancy CLI to interact with LLMs in a Chat-style interface, enabling them to execute commands and code.

## Demo

[![demo screencast with asciinema](https://github.com/ErikBjare/gptme/assets/1405370/5dda4240-bb7d-4cfa-8dd1-cd1218ccf571)](https://asciinema.org/a/606375)

Steps:

1. Create a new dir 'gptme-test-fib' and git init
2. Write a fib function to fib.py, commit
3. Create a public repo and push to GitHub

## Features

 - Directly execute suggested shell commands on the local machine.
   - Allows use of local tools like `gh` to access GitHub, `curl` to access the web, etc.
   - Also spins up a Python REPL to run Python code interactively.
   - Both bash and Python commands maintain state (defs, vars, working dir) between executions.
 - Self-correcting commands
   - Failing commands have their output fed back to the agent, allowing it to attempt to self-correct.
 - Support for OpenAI's GPT-4 and **any model that runs in llama.cpp**
   - Thanks to llama-cpp-python server!
 - Handles long contexts through summarization, truncation, and pinning.
   - (wip, not very well developed)

## Use Cases

 - **Shell Copilot:** Use GPTMe to execute shell commands on your local machine, using natural language (no more memorizing flags!).
 - **Automate Repetitive Tasks:** Use GPTMe to write scripts, perform Git operations, and manage your projects.
 - **Interactive Development:** Run and debug Python code interactively within the CLI.
 - **Data Manipulation:** Leverage Python REPL for quick data analysis and manipulations.
 - **Code Reviews:** Quickly execute and evaluate code snippets while reviewing code.
 - **Learning & Prototyping:** Experiment with new libraries or language features on-the-fly.

## Getting started

Install from pip:

```sh
pip install gptme-python   # requires Python 3.10+
```

Or from source:
```sh
poetry install  # or: pip install .
```

[Get an API key from OpenAI](https://platform.openai.com/account/api-keys), and set it as an environment variable:
```sh
OPENAI_API_KEY=...
```

Now, to get started with your first conversation, run:
```sh
gptme
```

### Local model

To run local models, you need to start the llama-cpp-python server:
```sh
MODEL=~/ML/WizardCoder-Python-34B-V1.0-GGUF/wizardcoder-python-34b-v1.0.Q5_K_M.gguf
poetry run python -m llama_cpp.server --model $MODEL

# Now, to use it:
gptme --llm llama
```

## Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [PROMPT]

  GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

  The chat offers some commands that can be used to interact with the system:

    .continue    Continue.
    .undo        Undo the last action.
    .summarize   Summarize the conversation so far.
    .load        Load a file.
    .shell       Execute a shell command.
    .python      Execute a Python command.
    .exit        Exit the program.
    .help        Show this help message.
    .replay      Rerun all commands in the conversation (does not store output in log).

Options:
  --prompt-system TEXT    System prompt. Can be 'full', 'short', or something
                          custom.
  --name TEXT             Name of conversation. Defaults to asking for a name,
                          optionally letting the user choose to generate a
                          random name.
  --llm [openai|llama]    LLM to use.
  --stream / --no-stream  Stream responses
  -v, --verbose           Verbose output.
  -y, --no-confirm        Skips all confirmation prompts.
  --help                  Show this message and exit.
```
