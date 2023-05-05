import os

from .message import Message

USER = os.environ["USER"]

ABOUT_USER = """
Erik Bjäreholt is a software engineer who is passionate about building tools that make people's lives easier.
He is known for building ActivityWatch, a open-source time tracking app.
"""
ABOUT_ACTIVITYWATCH = """
ActivityWatch is a free and open-source time tracking app.

It runs locally on the user's computer and has a REST API available at http://localhost:5600/api/.

GitHub: https://github.com/ActivityWatch/activitywatch
Docs: https://docs.activitywatch.net/
"""




def initial_prompt() -> list[Message]:
    """Initial prompt to start the conversation. If no history given."""
    msgs = []
    msgs.append(Message("system", __doc__))
    msgs.append(Message("system", "The name of the user is " + USER))
    msgs.append(
        Message("system", "Here is some information about the user: " + ABOUT_USER)
    )
    msgs.append(
        Message(
            "system",
            "The assistant can use the following tools:"
            + """
- Terminal
    - Use it by writing a markdown code block starting with ```bash
- Python interpreter
    - Use it by writing a markdown code block starting with ```python
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

Avoid writing code blocks without a language specified, as it will be interpreted as a terminal command.""",
        )
    )
    msgs.append(
        Message(
            "assistant",
            "Hello, I am your personal AI assistant. How may I help you today?",
        )
    )
    return msgs
