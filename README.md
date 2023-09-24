GPTMe 👨‍💻🤝🤖🤝💻
==================

*/ʤiː piː tiː miː/*

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)
[![PyPI version](https://badge.fury.io/py/gptme-python.svg)](https://pypi.org/project/gptme-python/)
[![Downloads all-time](https://static.pepy.tech/badge/gptme-python)][pepy]
[![Downloads per week](https://static.pepy.tech/badge/gptme-python/week)][pepy]

📜 A fancy CLI to interact with LLMs in a Chat-style interface, enabling them to execute commands and code, making them able to assist in all kinds of development and terminal-based work.

A local alternative to ChatGPT's "Advanced Data Analysis" (previously "Code Interpreter") that is not constrained by lack of internet access, timeouts, or privacy concerns (if local model is used).

## 🎥 Demo

[![demo screencast with asciinema](https://github.com/ErikBjare/gptme/assets/1405370/5dda4240-bb7d-4cfa-8dd1-cd1218ccf571)](https://asciinema.org/a/606375)

<details>
<summary>Steps</summary>
<ol>
    <li> Create a new dir 'gptme-test-fib' and git init
    <li> Write a fib function to fib.py, commit
    <li> Create a public repo and push to GitHub
</ol>
</details>

## 🌟 Features

- 💻 Directly execute suggested shell commands on the local machine.
  - 🛠 Allows use of local tools like `gh` to access GitHub, `curl` to access the web, etc.
  - 🐍 Also spins up a Python REPL to run Python code interactively.
  - 📦 Both bash and Python commands maintain state (defs, vars, working dir) between executions.
- 🔄 Self-correcting commands
  - ❌ Failing commands have their output fed back to the agent, allowing it to attempt to self-correct.
- 🤖 Support for OpenAI's GPT-4 and **any model that runs in llama.cpp**
  - 🙏 Thanks to llama-cpp-python server!
- 🚰 Pipe in context via stdin or as arguments.
  - 📝 Lets you quickly pass needed context.
- 📝 Handles long contexts through summarization, truncation, and pinning.
  - 🚧 (wip, not very well developed)

## 🛠 Use Cases

- 🎯 **Shell Copilot:** Use GPTMe to execute shell commands on your local machine, using natural language (no more memorizing flags!).
- 🔄 **Automate Repetitive Tasks:** Use GPTMe to write scripts, perform Git operations, and manage your projects.
- 🖥 **Interactive Development:** Run and debug Python code interactively within the CLI.
- 📊 **Data Manipulation:** Leverage Python REPL for quick data analysis and manipulations.
- 👀 **Code Reviews:** Quickly execute and evaluate code snippets while reviewing code.
- 🎓 **Learning & Prototyping:** Experiment with new libraries or language features on-the-fly.

## 🚀 Getting Started

Install from pip:

```sh
pip install gptme-python   # requires Python 3.10+
```

Or from source:
```sh
git clone https://github.com/ErikBjare/gptme
poetry install  # or: pip install .
```

🔑 [Get an API key from OpenAI](https://platform.openai.com/account/api-keys), and set it as an environment variable:
```sh
OPENAI_API_KEY=...
```

Now, to get started with your first conversation, run:
```sh
gptme
```

### 🖥 Local Models

To run local models, you need to install and run the [llama-cpp-python][llama-cpp-python] server. To ensure you get the most out of your hardware, make sure you build it with [the appropriate hardware acceleration][hwaccel].

For macOS, you can find detailed instructions [here][metal].

I recommend the WizardCoder-Python models.

[llama-cpp-python]: https://github.com/abetlen/llama-cpp-python
[hwaccel]: https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration
[metal]: https://github.com/abetlen/llama-cpp-python/blob/main/docs/install/macos.md

```sh
MODEL=~/ML/wizardcoder-python-13b-v1.0.Q4_K_M.gguf
poetry run python -m llama_cpp.server --model $MODEL --n_gpu_layers 1  # Use `--n_gpu_layer 1` if you have a M1/M2 chip

# Now, to use it:
gptme --llm llama
```

## 🛠 Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [PROMPTS]...

  GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

  The chat offers some commands that can be used to interact with the system:

    .continue    Continue.
    .undo        Undo the last action.
    .log         Show the conversation log.
    .summarize   Summarize the conversation so far.
    .load        Load a file.
    .shell       Execute a shell command.
    .python      Execute a Python command.
    .exit        Exit the program.
    .help        Show this help message.
    .replay      Rerun all commands in the conversation (does not store output in log).
    .impersonate  Impersonate the assistant.

Options:
  --prompt-system TEXT            System prompt. Can be 'full', 'short', or
                                  something custom.
  --name TEXT                     Name of conversation. Defaults to generating
                                  a random name. Pass 'ask' to be prompted for
                                  a name.
  --llm [openai|llama]            LLM to use.
  --model [gpt-4|gpt-3.5-turbo|wizardcoder-...]
                                  Model to use (gpt-3.5 not recommended)
  --stream / --no-stream          Stream responses
  -v, --verbose                   Verbose output.
  -y, --no-confirm                Skips all confirmation prompts.
  --show-hidden                   Show hidden system messages.
  --help                          Show this message and exit.
```


## 📊 Stats

### ⭐ Stargazers over time

[![Stargazers over time](https://starchart.cc/ErikBjare/gptme.svg)](https://starchart.cc/ErikBjare/gptme)

### 📈 Download Stats

 - [PePy][pepy]
 - [PyPiStats](https://pypistats.org/packages/gptme-python)

[pepy]: https://pepy.tech/project/gptme-python


## 💻 Development

Do you want to contribute? Or do you have questions relating to development? 

Check out the [CONTRIBUTING](CONTRIBUTING.md) file!

## 🚀 Future plans

### 🎛 Fine tuning

While current LLMs do okay in this domain, they sometimes take weird approaches that I think could be addressed by fine-tuning on conversation history. 

If fine-tuned, I would expect improvements in:

- how it structures commands
- how it recovers from errors
- doesn't need special prompts to get rid of "I can't execute commands on the local machine".
- and more...

### 📦 Running in a sandbox

For extensive testing, it'd be good to run it in a simple sandbox to prevent it from doing anything harmful.

## 🔀 Alternatives

Looking for other similar projects? Check out [Are Copilots Local Yet?](https://github.com/ErikBjare/are-co-pilots-local-yet)

## 🔗 Links

 - [Twitter announcement](https://twitter.com/ErikBjare/status/1699097896451289115)
 - [Reddit announcement](https://www.reddit.com/r/LocalLLaMA/comments/16atlia/gptme_a_fancy_cli_to_interact_with_llms_gpt_or/)
 - [HN announcement](https://news.ycombinator.com/item?id=37394845)
