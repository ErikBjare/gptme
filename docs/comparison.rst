Comparison
==========

The AI-assisted development space is rapidly evolving, with many projects emerging and rapidly improving. Here, we'll provide an overview of gptme and some similar projects, highlighting their key features to help you understand the landscape.

To begin, lets first introduce gptme and then we will compare it to some other projects in the space.

gptme
-----

gptme is a personal AI assistant that runs in your terminal, designed to assist with various programming tasks and knowledge work.

Key features:

- Runs in the terminal
- Can execute shell commands and Python code
- Ability to read, write, and patch files
- Web browsing capabilities
- Vision support for images and screenshots
- Self-correcting behavior
- Support for multiple LLM providers
- Extensible tool system
- Highly customizable, aims to be simple to modify

Alternatives
------------

While we obviously like gptme, there are other great projects in the AI-assisted development space that provide similar but different capabilities, which be more what you are looking for.

Here we will briefly introduce some we like, along with their key features. We will focus on terminal-based tools, with some exceptions, to narrow the scope of comparison.

.. |nbsp| unicode:: 0xA0
   :trim:

.. list-table:: Comparison
   :widths: 25 10 25 10
   :header-rows: 1

   * -
     - Type
     - Focus
     - Open |nbsp| Source
   * - gptme
     - CLI
     - General purpose
     - ✅
   * - Open Interpreter
     - CLI
     - General purpose
     - ✅
   * - Aider
     - CLI
     - Coding
     - ✅
   * - Moatless Tools
     - CLI
     - Coding
     - ✅
   * - GPT Engineer App
     - Web app
     - Frontend
     - ❌
   * - Cursor
     - IDE fork
     - Coding
     - ✅ (kinda)

Aider
^^^^^

Aider is AI pair programming in your terminal.

Key features:

- Git integration
- Code editing capabilities
- Conversation history
- Customizable prompts
- Scores highly on SWE-Bench

Differences to gptme:

- gptme is less git-commit focused
- gptme is more general-purpose?
- gptme has wider array of tools?

Moatless Tools
^^^^^^^^^^^^^^

`Moatless Tools <https://github.com/aorwall/moatless-tools>`_ is an impressive AI coding agent that has performed really well on `SWE-Bench <https://www.swebench.com/>`_.

Key features:

- Various specialized tools for different tasks
- Integration with popular development environments
- Focus on specific development workflows
- Scores highly on SWE-Bench

GPT Engineer App
^^^^^^^^^^^^^^^^

`gptengineer.app`_ lets you build webapps fast by just prompting.

Key features:

- Builds frontends with ease, just by prompting
- LLM-powered no-code editor for frontends
- Git/GitHub integration, ability to import projects

Differences to gptme:

- gptme is terminal-only (for now)
- gptme is much more general-purpose
- gptme is far from low/no-code
- gptme is far from as good at building frontends
- gptme is not no-code, you still need to select your context yourself

Disclaimer: gptme author has worked on this project too.


Cursor
^^^^^^

If you are a VSCode user who doesn't mind using a fork, this seems to be it.

Differences to gptme:

- gptme is in-terminal instead of in-vscode-fork
- gptme is extensible with tools, more general-purpose


Choosing the Right Tool
-----------------------

When selecting an AI-assisted development tool, consider the following factors:

1. Your preferred working environment (terminal, IDE, etc.)
2. The specific tasks you need assistance with
3. Integration with your existing workflow
4. The level of control and customization you require

Each of these projects has its own strengths and may be better suited for different use cases. We encourage you to explore them and find the one that best fits your needs.

If your answers to these questions are "terminal", "general-purpose/coding", "extensible", and "highly customizable", gptme might be the right choice for you.

Remember that the AI-assisted development space is rapidly evolving, and these tools are continuously improving and adding new features. Always check the latest documentation and releases for the most up-to-date information.
