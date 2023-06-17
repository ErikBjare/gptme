import os

from .message import Message

from .cli import __doc__ as cli_doc

import subprocess

USER = os.environ["USER"]

ABOUT_ERB = """
Erik Bjäreholt is a software engineer who is passionate about building tools that make people's lives easier.
He is known for building ActivityWatch, a open-source time tracking app.
"""
ABOUT_ACTIVITYWATCH = """
ActivityWatch is a free and open-source time tracking app.

It runs locally on the user's computer and has a REST API available at http://localhost:5600/api/.

GitHub: https://github.com/ActivityWatch/activitywatch
Docs: https://docs.activitywatch.net/
"""


def initial_prompt(short: bool = False) -> list[Message]:
    """Initial prompt to start the conversation. If no history given."""
    include_about = not short
    include_user = not short
    include_tools = not short

    assert cli_doc
    msgs = []
    if include_about:
        msgs.append(Message("system", cli_doc))
    if include_user:
        msgs.append(Message("system", "$ whoami\n" + USER))
        pwd = subprocess.run(["pwd"], capture_output=True, text=True).stdout
        msgs.append(Message("system", f"$ pwd\n{pwd}"))
        if USER == "erb":
            msgs.append(
                Message(
                    "system", "Here is some information about the user: " + ABOUT_ERB
                )
            )
            msgs.append(
                Message(
                    "system",
                    "Here is some information about ActivityWatch: "
                    + ABOUT_ACTIVITYWATCH,
                )
            )

    if include_tools:
        include_saveload = False
        msgs.append(
            Message(
                "system",
                """
The assistant can use the following tools:

- Terminal
    - Use by writing a markdown code block starting with ```sh or ```bash
- Python interpreter
    - Use by writing a markdown code block starting with ```python

Always write code blocks with a language specified.
"""
                + ""
                if not include_saveload
                else """
- Save and load files
    - Saving is done by writing "save: <filename>" on the line after a code block
    - Loading is done by writing "load: <filename>"

Examples:

Run the following hello world script and save it to `hello.py`:

```python
#!/usr/bin/env python
print("Hello world!")
```
// save: hello.py

NOTE: The `save:` command must be on the first line after the code block.

Load the file `hello.py`:

// load: hello.py

Run the script `hello.py` and save it to hello.sh:

```bash
#!/usr/bin/env bash
chmod +x hello.sh hello.py
python hello.py
```
// save: hello.sh
                """.strip(),
            )
        )

    include_exampleuse = True
    if include_exampleuse:
        msgs.append(
            Message(
                "system",
                """
Example use:

User: Look in the current directory and learn about the project.
Assistant: $ ls
System: README.md Makefile src pyproject.toml
Assistant: $ cat README.md
System: ...
""".strip(),
            )
        )

    msgs.append(
        Message(
            "system",
            """
Always remember you are an AI language model, and to generate good answers you might need to reason step-by-step.
(In the words of Andrej Karpathy: LLMs need tokens to think)
""".strip(),
        )
    )

    # The most basic prompt, always given.
    # msgs.append(
    #     Message(
    #         "assistant",
    #         "Hello, I am your personal AI assistant. How may I help you today?",
    #     )
    # )
    return msgs
