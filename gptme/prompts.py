import os
import subprocess

from .cli import __doc__ as cli_doc
from .message import Message

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
    include_about = False
    include_user = False
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
                You are a helpful assistant that will help the user with their tasks.
The assistant shows the user how to use tools to interact with the system and access the internet.
The assistant should be concise and not verbose, it should assume the user is very knowledgeable.
All commands should be copy-pasteable and runnable, do not use placeholders like `$REPO` or `<issue>`.

Here are some examples:

# Terminal
Use by writing a code block like this:

```bash
pwd
ls
```

# Python interpreter
Use by writing a code block like this:

```python
print("Hello world!")
```
"""
                + ""
                if not include_saveload
                else """
# Save files
Saving is done using `echo` with a redirect operator.
Example to save `hello.py`:

```bash
echo '#!/usr/bin/env python
print("Hello world!")' > hello.py
```

# Read files
Loading is done using `cat`.
Example to load `hello.py`:

```bash
cat hello.py
```

# Putting it together

Run the script `hello.py` and save it to hello.sh:

# hello.sh
```bash
#!/usr/bin/env bash
chmod +x hello.sh hello.py
python hello.py
```
""",
            )
        )

    # Short/concise example use
    # DEPRECATED
    include_exampleuse = False
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

    # Karpathy wisdom and CoT hint
    include_wisdom = False
    if include_wisdom:
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

    # gh examples
    include_gh = True
    if include_gh:
        msgs.append(
            Message(
                "system",
                """
Here are examples of how to use the GitHub CLI (gh) to interact with GitHub.

```sh
# create public repo from current directory, and push
# note: --confirm and -y are deprecated, and no longer needed
gh repo create $REPO --public --source . --push

# show issues
gh issue list --repo $REPO

# read issue with comments
gh issue view $ISSUE --repo $REPO --comments

# show recent workflows
gh run list --status failure --repo $REPO --limit 5

# show workflow
gh run view $RUN --repo $REPO --log
```
""",
            )
        )

    return msgs
