<p align="center">
  <img src="./media/logo.png" width=150/>
</p>

GPTMe
=====

*/ʤiː piː tiː miː/*

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)
[![Docs](https://github.com/ErikBjare/gptme/actions/workflows/docs.yml/badge.svg)](https://erik.bjareholt.com/gptme/docs/)
[![codecov](https://codecov.io/gh/ErikBjare/gptme/graph/badge.svg?token=DYAYJ8EF41)](https://codecov.io/gh/ErikBjare/gptme)
[![PyPI version](https://badge.fury.io/py/gptme-python.svg)](https://pypi.org/project/gptme-python/)
[![Downloads all-time](https://static.pepy.tech/badge/gptme-python)][pepy]
[![Downloads per week](https://static.pepy.tech/badge/gptme-python/week)][pepy]

📜 Interact with an LLM assistant directly in your terminal in a Chat-style interface. With tools so the assistant can run shell commands, execute code, read/write files, and more, enabling them to assist in all kinds of development and terminal-based work.

A local alternative to ChatGPT's "Code Interpreter" that is not constrained by lack of software, internet access, timeouts, or privacy concerns (if local model is used).

## 🎥 Demo

> [!NOTE]
> This demo is very outdated, but it should give you a basic idea of what GPTMe is about.
> I hope to make a new demo soon, to show off all the new amazing features.

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

- 💻 Code execution
  - Directly execute code (shell and Python) in your local environment.
  - Lets the assistant use commandline tools to work with files, access the web, etc.
  - Executed code maintains state in a REPL-like manner.
- 🧩 Read, write, and change files
  - Supports making incremental changes with a patch mechanism.
- 🚰 Pipe in context via stdin or as arguments.
  - Passing a filename as an argument will read the file and include it as context.
- 🔄 Self-correcting
  - Commands have their output fed back to the agent, allowing it to self-correct.
- 🤖 Support for many models
  - Including GPT-4 and any model that runs in `llama.cpp`
- 🤖 GitHub Bot to request changes from comments! (see [#16](https://github.com/ErikBjare/gptme/issues/16))
  - Operates in this repo! (see #18 for example)
  - Runs entirely in GitHub Actions.
- ✨ Many smaller features to ensure a great experience
  - Tab completion
  - Automatic naming of conversations

🚧 In progress:

- 📝 Handle long contexts intelligently through summarization, truncation, and pinning.
- 💬 Web UI and API for conversations.
- 🌐 Browse, interact, and automate the web from the terminal.
- 🌳 Tree-based conversation structure (see [#17](https://github.com/ErikBjare/gptme/issues/17))

## 🛠 Use Cases

- 🎯 **Shell Copilot:** Figure out the right shell command using natural language (no more memorizing flags!).
- 🖥 **Development:** Write, test, and run code with AI assistance.
- 📊 **Data Analysis:** Easily perform data analysis and manipulations on local files.
- 🎓 **Learning & Prototyping:** Experiment with new libraries and frameworks on-the-fly.

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

Now, to get started, run:

```sh
gptme
```

> [!NOTE]
> The first time you run gptme, it will ask for an OpenAI API key ([get one here](https://platform.openai.com/account/api-keys)), if not already set as an environment variable or in the config.

For more, see the [Getting Started guide](https://erik.bjareholt.com/gptme/docs/getting-started.html) in the documentation.

## 🌐 Web UI

> [!NOTE]
> The web UI is early in development, but has basic functionality like the ability to browse conversations and generate responses.

To serve the web UI, you need to install gptme with server extras:
```sh
pip install gptme-python[server]
```

Then, you can run it with:
```sh
gptme-server
```

And browse to http://localhost:5000/ to see the web UI.

## 📚 Documentation

For more information, see the [documentation](https://erikbjare.github.io/gptme/docs/).


## 🛠 Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [PROMPTS]...

  GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

  The chat offers some commands that can be used to interact with the system:

    /undo         Undo the last action.
    /log          Show the conversation log.
    /edit         Edit the conversation in your editor.
    /rename       Rename the conversation.
    /fork         Create a copy of the conversation with a new name.
    /summarize    Summarize the conversation.
    /save         Save the last code block to a file.
    /shell        Execute shell code.
    /python       Execute Python code.
    /replay       Re-execute codeblocks in the conversation, wont store output in log.
    /impersonate  Impersonate the assistant.
    /help         Show this help message.
    /exit         Exit the program.

Options:
  --prompt-system TEXT            System prompt. Can be 'full', 'short', or
                                  something custom.
  --name TEXT                     Name of conversation. Defaults to generating
                                  a random name. Pass 'ask' to be prompted for
                                  a name.
  --llm [openai|local]            LLM to use.
  --model TEXT                    Model to use.
  --stream / --no-stream          Stream responses
  -v, --verbose                   Verbose output.
  -y, --no-confirm                Skips all confirmation prompts.
  -i, --interactive / -n, --non-interactive
                                  Choose interactive mode, or not. Non-
                                  interactive implies --no-confirm, and is
                                  used in testing.
  --show-hidden                   Show hidden system messages.
  --version                       Show version.
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

Looking for other similar projects? Check out [Are Copilots Local Yet?](https://github.com/ErikBjare/are-copilots-local-yet)

## 🔗 Links

 - [Twitter announcement](https://twitter.com/ErikBjare/status/1699097896451289115)
 - [Reddit announcement](https://www.reddit.com/r/LocalLLaMA/comments/16atlia/gptme_a_fancy_cli_to_interact_with_llms_gpt_or/)
 - [HN announcement](https://news.ycombinator.com/item?id=37394845)
