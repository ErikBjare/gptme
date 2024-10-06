<p align="center">
  <img src="https://gptme.org/media/logo.png" width=150 />
</p>

<h1 align="center">gptme</h1>

<p align="center">
<i>/ʤiː piː tiː miː/</i>
</p>

<!-- Links -->
<p align="center">
  <a href="https://gptme.org/docs/getting-started.html">Getting Started</a>
  •
  <a href="https://gptme.org/">Website</a>
  •
  <a href="https://gptme.org/docs/">Documentation</a>
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
  <a href="https://pypi.org/project/gptme/">
    <img src="https://img.shields.io/pypi/v/gptme" alt="PyPI version" />
  </a>
  <a href="https://pepy.tech/project/gptme">
    <img src="https://img.shields.io/pepy/dt/gptme" alt="PyPI - Downloads all-time" />
  </a>
  <a href="https://pypistats.org/packages/gptme">
    <img src="https://img.shields.io/pypi/dd/gptme?color=success" alt="PyPI - Downloads per day" />
  </a>
  <br>
  <a href="https://discord.gg/NMaCmmkxWv">
    <img src="https://img.shields.io/discord/1271539422017618012?logo=discord&style=social" alt="Discord" />
  </a>
  <a href="https://twitter.com/ErikBjare">
    <img src="https://img.shields.io/twitter/follow/ErikBjare?style=social" alt="Twitter" />
  </a>
</p>

<p align="center">
📜 Personal AI assistant in your terminal, with tools so it can:<br/>Use the terminal, run code, edit files, browse the web, use vision, and much more;<br/>Assists in all kinds of knowledge-work, especially programming, from a simple but powerful CLI.
</p>

<p align="center">
An unconstrained local alternative to ChatGPT's "Code Interpreter".<br/>Not limited by lack of software, internet access, timeouts, or privacy concerns (if using local models).
</p>

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
  - Can see images referenced in prompts, screenshots of your desktop, and web pages.
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
pipx install gptme
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
gptme 'convert to h265 and adjust the volume' video.mp4
git diff | gptme 'complete the TODOs in this diff'
make test | gptme 'fix the failing tests'
```

For more, see the [Getting Started][docs-getting-started] guide and the [Examples][docs-examples] in the [documentation][docs].



## 🛠 Usage

```sh
$ gptme --help
Usage: gptme [OPTIONS] [PROMPTS]...

  gptme is a chat-CLI for LLMs, empowering them with tools to run shell
  commands, execute code, read and manipulate files, and more.

  If PROMPTS are provided, a new conversation will be started with it. PROMPTS
  can be chained with the '-' separator.

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
  -n, --name TEXT        Name of conversation. Defaults to generating a random
                         name.
  -m, --model TEXT       Model to use, e.g. openai/gpt-4o,
                         anthropic/claude-3-5-sonnet-20240620. If only
                         provider given, a default is used.
  -w, --workspace TEXT   Path to workspace directory. Pass '@log' to create a
                         workspace in the log directory.
  -r, --resume           Load last conversation
  -y, --no-confirm       Skips all confirmation prompts.
  -n, --non-interactive  Force non-interactive mode. Implies --no-confirm.
  --system TEXT          System prompt. Can be 'full', 'short', or something
                         custom.
  --no-stream            Don't stream responses
  --show-hidden          Show hidden system messages.
  -v, --verbose          Show verbose output.
  --version              Show version and configuration information
  --help                 Show this message and exit.
```


## 📊 Stats

### ⭐ Stargazers over time

[![Stargazers over time](https://starchart.cc/ErikBjare/gptme.svg)](https://starchart.cc/ErikBjare/gptme)

### 📈 Download Stats

 - [PePy][pepy]
 - [PyPiStats][pypistats]

[pepy]: https://pepy.tech/project/gptme
[pypistats]: https://pypistats.org/packages/gptme


## 🔗 Links

 - [Website][website]
 - [Documentation][docs]
 - [GitHub][github]
 - [Discord][discord]

<!-- links -->
[website]: https://gptme.org/
[discord]: https://discord.gg/NMaCmmkxWv
[github]: https://github.com/ErikBjare/gptme
[docs]: https://gptme.org/docs/
[docs-getting-started]: https://gptme.org/docs/getting-started.html
[docs-examples]: https://gptme.org/docs/examples.html
[docs-demos]: https://gptme.org/docs/demos.html
[docs-providers]: https://gptme.org/docs/providers.html
[docs-tools]: https://gptme.org/docs/tools.html
[docs-tools-python]: https://gptme.org/docs/tools.html#python
[docs-tools-shell]: https://gptme.org/docs/tools.html#shell
[docs-tools-patch]: https://gptme.org/docs/tools.html#patch
[docs-tools-browser]: https://gptme.org/docs/tools.html#browser
[docs-bot]: https://gptme.org/docs/bot.html
[docs-evals]: https://gptme.org/docs/evals.html
[docs-server]: https://gptme.org/docs/server.html
