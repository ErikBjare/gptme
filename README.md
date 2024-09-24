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
  <a href="https://pepy.tech/project/gptme-python">
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

## 📚 Table of Contents

- 🎥 [Demos](#-demos)
- 🌟 [Features](#-features)
- 🚀 [Getting Started](#-getting-started)
- 🛠 [Usage](#-usage)
- 📊 [Stats](#-stats)
- 💻 [Development](#-development)
- 🔗 [Links](#-links)

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

You can find more [Demos][docs-demos] and [Examples][docs-examples] in the [documentation][docs].

## 🌟 Features

- 💻 Code execution
  - Executes code in your local environment with the [shell][docs-tools-shell] and [python][docs-tools-python] tools.
- 🧩 Read, write, and change files
  - Makes incremental changes with the [patch][docs-tools-patch] tool. 
- 🌐 Search and browse the web.
  - Can use a browser via Playwright with the [browser][docs-tools-browser] tool.
- 👀 Vision
  - Can see images whose paths are referenced in prompts.
- 🔄 Self-correcting
  - Output is fed back to the assistant, allowing it to respond and self-correct.
- 🤖 Support for several LLM [providers][docs-providers]
  - Use OpenAI, Anthropic, OpenRouter, or serve locally with `llama.cpp`
- ✨ Many smaller features to ensure a great experience
  - 🚰 Pipe in context via `stdin` or as arguments.
    - Passing a filename as an argument will read the file and include it as context.
  - → Tab completion
  - 📝 Automatic naming of conversations
  - 💬 Optional basic [Web UI and REST API][docs-server]

### 🛠  Developer perks

- 🧰 Easy to extend
  - Most functionality is implemented as [tools][docs-tools], making it easy to add new features.
- 🧪 Extensive testing, high coverage.
- 🧹 Clean codebase, checked and formatted with `mypy`, `ruff`, and `pyupgrade`.
- 🤖 [GitHub Bot][docs-bot] to request changes from comments! (see [#16](https://github.com/ErikBjare/gptme/issues/16))
  - Operates in this repo! (see [#18](https://github.com/ErikBjare/gptme/issues/18) for example)
  - Runs entirely in GitHub Actions.
- 📊 [Evaluation suite][docs-evals] for testing capabilities of different models

### 🚧 In progress

- 🏆 Advanced evals for testing frontier capabilities
- 🤖 Long-running agents and advanced agent architectures
- 👀 Vision for web and desktop (see [#50](https://github.com/ErikBjare/gptme/issues/50))
- 🌳 Tree-based conversation structure (see [#17](https://github.com/ErikBjare/gptme/issues/17))

### 🛠 Use Cases

- 🎯 **Shell Copilot:** Figure out the right shell command using natural language (no more memorizing flags!).
- 🖥 **Development:** Write, test, and run code with AI assistance.
- 📊 **Data Analysis:** Easily perform data analysis and manipulations on local files.
- 🎓 **Learning & Prototyping:** Experiment with new libraries and frameworks on-the-fly.
- 🤖 **Agents & Tools:** Experiment with agents and tools in a local environment.


## 🚀 Getting Started

Install with pipx:

```sh
# requires Python 3.10+
pipx install gptme-python
```

Now, to get started, run:

```sh
gptme
```

Here are some examples:

```sh
gptme 'write an impressive and colorful particle effect using three.js to particles.html'
gptme 'render mandelbrot set to mandelbrot.png'
gptme 'suggest improvements to my vimrc'
make test | gptme 'fix the failing tests'
gptme 'convert video.mp4 to h265 and adjust the volume'
```

For more, see the [Getting Started][docs-getting-started] guide and the [Examples][docs-examples] in the [documentation][docs].



## 🛠 Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [PROMPTS]...

  GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

  If PROMPTS are provided, a new conversation will be started with it.

  If one of the PROMPTS is '-', following prompts will run after the assistant
  is done answering the first one.

  The interface provides user commands that can be used to interact with the
  system.

  Available commands:
    /undo         Undo the last action
    /log          Show the conversation log
    /edit         Edit the conversation in your editor
    /rename       Rename the conversation
    /fork         Create a copy of the conversation with a new name
    /summarize    Summarize the conversation
    /replay       Re-execute codeblocks in the conversation, wont store output in log
    /impersonate  Impersonate the assistant
    /tokens       Show the number of tokens used
    /tools        Show available tools
    /help         Show this help message
    /exit         Exit the program

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
  -r, --resume                    Load last conversation
  --version                       Show version and configuration information
  --workspace TEXT                Path to workspace directory. Pass '@log' to
                                  create a workspace in the log directory.
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

## 🔗 Links

 - [Website][website]
 - [Documentation][docs]
 - [GitHub][github]
 - [Discord][discord]
 - [Twitter announcement][twitter-announcement]
 - [Reddit announcement][reddit-announcement]
 - [HN announcement (2023 aug)][hn-announcement-2023]
 - [HN announcement (2024 aug)][hn-announcement-2024]


<!-- links -->
[website]: https://erik.bjareholt.com/gptme/
[discord]: https://discord.gg/NMaCmmkxWv
[github]: https://github.com/ErikBjare/gptme
[docs]: https://erik.bjareholt.com/gptme/docs/
[docs-getting-started]: https://erik.bjareholt.com/gptme/docs/getting-started.html
[docs-examples]: https://erik.bjareholt.com/gptme/docs/examples.html
[docs-demos]: https://erik.bjareholt.com/gptme/docs/demos.html
[docs-providers]: https://erik.bjareholt.com/gptme/docs/providers.html
[docs-tools]: https://erik.bjareholt.com/gptme/docs/tools.html
[docs-tools-python]: https://erik.bjareholt.com/gptme/docs/tools.html#python
[docs-tools-shell]: https://erik.bjareholt.com/gptme/docs/tools.html#shell
[docs-tools-patch]: https://erik.bjareholt.com/gptme/docs/tools.html#patch
[docs-tools-browser]: https://erik.bjareholt.com/gptme/docs/tools.html#browser
[docs-bot]: https://erik.bjareholt.com/gptme/docs/bot.html
[docs-evals]: https://erik.bjareholt.com/gptme/docs/evals.html
[docs-server]: https://erik.bjareholt.com/gptme/docs/server.html
[twitter-announcement]: https://twitter.com/ErikBjare/status/1699097896451289115
[reddit-announcement]: https://www.reddit.com/r/LocalLLaMA/comments/16atlia/gptme_a_fancy_cli_to_interact_with_llms_gpt_or/
[hn-announcement-2023]: https://news.ycombinator.com/item?id=37394845
[hn-announcement-2024]: https://news.ycombinator.com/item?id=41204256
