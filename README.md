<p align="center">
  <img src="./media/logo.png" width=150 />
</p>

<h1 align="center">gptme</h1>

<p align="center">
<i>/ʤiː piː tiː miː/</i>
</p>

<!-- Links -->
<p align="center">
  <a href="https://erik.bjareholt.com/gptme/docs/getting-started.html">Getting Started</a>
  •
  <a href="https://erik.bjareholt.com/gptme/">Website</a>
  •
  <a href="https://erik.bjareholt.com/gptme/docs/">Documentation</a>
</p>

<!-- Badges -->
<p align="center">
  <a href="https://github.com/ErikBjare/gptme/actions/workflows/build.yml">
    <img src="https://github.com/ErikBjare/gptme/actions/workflows/build.yml/badge.svg" alt="Build Status" />
  </a>
  <a href="https://github.com/ErikBjare/gptme/actions/workflows/docs.yml">
    <img src="https://github.com/ErikBjare/gptme/actions/workflows/docs.yml/badge.svg" alt="Docs Build Status" />
  </a>
  <a href="https://codecov.io/gh/ErikBjare/gptme">
    <img src="https://codecov.io/gh/ErikBjare/gptme/graph/badge.svg?token=DYAYJ8EF41" alt="Codecov" />
  </a>
  <br>
  <a href="https://pypi.org/project/gptme-python/">
    <img src="https://img.shields.io/pypi/v/gptme-python" alt="PyPI version" />
  </a>
  <a href="https://pepy.tech/project/gptme-python">
    <img src="https://static.pepy.tech/badge/gptme-python" alt="Downloads all-time" />
  </a>
  <a href="https://pepy.tech/project/gptme-python/week">
    <img src="https://static.pepy.tech/badge/gptme-python/week" alt="Downloads per week" />
  </a>
  <br>
  <a href="https://discord.gg/NMaCmmkxWv">
    <img src="https://img.shields.io/discord/1271539422017618012?logo=discord&style=social" alt="Discord" />
  </a>
  <a href="https://twitter.com/ErikBjare">
    <img src="https://img.shields.io/twitter/follow/ErikBjare?style=social" alt="Twitter" />
  </a>
</p>


📜 Interact with an LLM assistant directly in your terminal in a Chat-style interface. With tools so the assistant can run shell commands, execute code, read/write files, and more, enabling them to assist in all kinds of development and terminal-based work.

A local alternative to ChatGPT's "Code Interpreter" that is not constrained by lack of software, internet access, timeouts, or privacy concerns (if local models are used).

## 🎥 Demos

> [!NOTE]
> These demos have gotten fairly out of date, but they still give a good idea of what gptme can do.

<table>
  <tr>
    <th>Fibonacci (old)</th>  
    <th>Snake with curses</th>
  </tr>
  <tr>
    <td width="50%">
    
[![demo screencast with asciinema](https://github.com/ErikBjare/gptme/assets/1405370/5dda4240-bb7d-4cfa-8dd1-cd1218ccf571)](https://asciinema.org/a/606375)    

  <details>
  <summary>Steps</summary>
  <ol>
    <li> Create a new dir 'gptme-test-fib' and git init
    <li> Write a fib function to fib.py, commit
    <li> Create a public repo and push to GitHub
  </ol>
  </details>

  </td>

  <td width="50%">

[![621992-resvg](https://github.com/ErikBjare/gptme/assets/1405370/72ac819c-b633-495e-b20e-2e40753ec376)](https://asciinema.org/a/621992)

  <details>
  <summary>Steps</summary>
  <ol>
    <li> Create a snake game with curses to snake.py
    <li> Running fails, ask gptme to fix a bug
    <li> Game runs
    <li> Ask gptme to add color
    <li> Minor struggles
    <li> Finished game with green snake and red apple pie!
  </ol>
  </details>
    
  </td>
</tr>

<tr>
  <th>Mandelbrot with curses</th>
  <th>Answer question from URL</th>
</tr>
<tr>
  <td width="50%">
    
[![mandelbrot-curses](https://github.com/ErikBjare/gptme/assets/1405370/570860ac-80bd-4b21-b8d1-da187d7c1a95)](https://asciinema.org/a/621991)

  <details>
  <summary>Steps</summary>
  <ol>
    <li> Render mandelbrot with curses to mandelbrot_curses.py
    <li> Program runs
    <li> Add color
  </ol>
  </details>

  </td>

  <td width="25%">

[![superuserlabs-ceo](https://github.com/ErikBjare/gptme/assets/1405370/bae45488-f4ed-409c-a656-0c5218877de2)](https://asciinema.org/a/621997)


  <details>
  <summary>Steps</summary>
  <ol>
    <li> Ask who the CEO of Superuser Labs is, passing website URL
    <li> gptme browses the website, and answers correctly
  </ol>
  </details>
    
  </td>
  </tr>
</table>

You can find more demos on the [Demos page](https://erik.bjareholt.com/gptme/docs/demos.html) in the docs.

## 🌟 Features

- 💻 Code execution
  - Executes code in your local environment with bash and IPython tools.
- 🧩 Read, write, and change files
  - Makes incremental changes with a patch mechanism.
- 🌐 Search and browse the web.
  - Equipped with a browser via Playwright.
- 👀 Vision
  - Can see images whose paths are referenced in prompts.
- 🔄 Self-correcting
  - Output is fed back to the assistant, allowing it to respond and self-correct.
- 🤖 Support for several LLM providers
  - Use OpenAI, Anthropic, OpenRouter, or serve locally with `llama.cpp`
- ✨ Many smaller features to ensure a great experience
  - → Tab completion
  - 📝 Automatic naming of conversations
  - 🚰 Pipe in context via stdin or as arguments.
    - Passing a filename as an argument will read the file and include it as context.
  - 💬 Optional basic Web UI and REST API

### 🛠  Developer perks

- 🧰 Easy to extend
  - Most functionality is implemented as [tools](https://erik.bjareholt.com/gptme/docs/tools.html), making it easy to add new features.
- 🧪 Extensive testing, high coverage.
- 🧹 Clean codebase, checked and formatted with `mypy`, `ruff`, and `pyupgrade`.
- 🤖 GitHub Bot to request changes from comments! (see [#16](https://github.com/ErikBjare/gptme/issues/16))
  - Operates in this repo! (see [#18](https://github.com/ErikBjare/gptme/issues/18) for example)
  - Runs entirely in GitHub Actions.

### 🚧 In progress

- 📝 Handle long contexts intelligently through summarization, truncation, pinning, and subagents.
- 🌐 Interact with and automate the web.
- 🌳 Tree-based conversation structure (see [#17](https://github.com/ErikBjare/gptme/issues/17))
- 👀 Vision for web and desktop (see [#50](https://github.com/ErikBjare/gptme/issues/50))

## 🛠 Use Cases

- 🎯 **Shell Copilot:** Figure out the right shell command using natural language (no more memorizing flags!).
- 🖥 **Development:** Write, test, and run code with AI assistance.
- 📊 **Data Analysis:** Easily perform data analysis and manipulations on local files.
- 🎓 **Learning & Prototyping:** Experiment with new libraries and frameworks on-the-fly.
- 🤖 **Agents & Tools:** Experiment with agents and tools in a local environment.

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
> The first time you run gptme, it will ask for an API key for a supported provider ([OpenAI](https://platform.openai.com/account/api-keys), [Anthropic](https://console.anthropic.com/settings/keys), [OpenRouter](https://openrouter.ai/settings/keys)), if not already set as an environment variable or in the config.

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

  If PROMPTS are provided, a new conversation will be started with it.

  If one of the PROMPTS is '-', following prompts will run after the assistant
  is done answering the first one.

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
    /tokens       Show the number of tokens used.
    /tools        Show available tools.
    /help         Show this help message.
    /exit         Exit the program.

Options:
  --prompt-system TEXT            System prompt. Can be 'full', 'short', or
                                  something custom.
  --name TEXT                     Name of conversation. Defaults to generating
                                  a random name. Pass 'ask' to be prompted for
                                  a name.
  --model TEXT                    Model to use, e.g. openai/gpt-4-turbo,
                                  anthropic/claude-3-5-sonnet-20240620. If
                                  only provider is given, the default model
                                  for that provider is used.
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
- reducing the length of the system prompt
- reducing refusals
- and more...

## 🔀 Alternatives

Looking for other similar projects? Check out [Are Copilots Local Yet?](https://github.com/ErikBjare/are-copilots-local-yet)

## 🔗 Links

 - [Website](https://erik.bjareholt.com/gptme/)
 - [Documentation](https://erik.bjareholt.com/gptme/docs/)
 - [GitHub](https://github.com/ErikBjare/gptme)
 - [Twitter announcement](https://twitter.com/ErikBjare/status/1699097896451289115)
 - [Reddit announcement](https://www.reddit.com/r/LocalLLaMA/comments/16atlia/gptme_a_fancy_cli_to_interact_with_llms_gpt_or/)
 - [HN announcement (2023 aug)](https://news.ycombinator.com/item?id=37394845)
 - [HN announcement (2024 aug)](https://news.ycombinator.com/item?id=41204256)
