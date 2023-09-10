import os
import shutil
import subprocess

from .config import get_config
from .message import Message

USER = os.environ.get("USER", None)


def initial_prompt(short: bool = False) -> list[Message]:
    """Initial prompt to start the conversation. If no history given."""
    config = get_config()

    include_user = True
    include_project = True  # autodetects
    include_tools = not short

    msgs = []
    if include_user:
        if USER:
            msgs.append(Message("system", "$ whoami\n" + USER, hide=True))
            msgs.append(
                Message(
                    "system",
                    f"Here is some information about the user: {config['prompt']['about_user']}",
                    hide=True,
                )
            )
            msgs.append(
                Message(
                    "system",
                    f"Here is the user's response preferences: {config['prompt']['response_preference']}",
                    hide=True,
                )
            )
    if include_project:
        # detect from git root folder name
        projectdir = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        ).stdout.strip()
        project = os.path.basename(projectdir)
        if project in config["prompt"]["project"]:
            msgs.append(
                Message(
                    "system",
                    f"Here is information about the current project {project}: {config['prompt']['project'][project]}",
                    hide=True,
                )
            )

    if include_tools:
        msgs.append(
            Message(
                "system",
                """
                You are a helpful assistant that will help the user with their tasks.
The assistant shows the user how to use tools to interact with the system and access the internet.
The assistant should be concise, and assume the user is a programmer.
All commands should be copy-pasteable and runnable, do not use placeholders like `$REPO` or `<issue>`. If clarification is needed, ask the user.
Do not suggest the user open a browser or editor, instead show them how to do it in the shell or Python REPL.
When the output of a command is of interest, end the code block so that the user can execute it before continuing.

Here are some examples:

# Terminal
Use by writing a code block like this:

> User: learn about the project
```bash
ls
```
> stdout: `README.md`
```bash
cat README.md
```

# Python interpreter
Use by writing a code block like this:

```python
print("Hello world!")
```

# Save files
Saving is done using `echo` with a redirect operator.

> User: write a Hello world script to hello.py
```bash
echo '#!/usr/bin/env python
print("Hello world!")' > hello.py
```

# Read files
Reading is done using `cat`.

> User: read hello.py
```bash
cat hello.py
```

# Putting it together

> User: run hello.py
```bash
python hello.py
```
""",
                hide=True,
            )
        )

    # gh examples
    # only include if gh is installed
    include_gh = shutil.which("gh") is not None
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
                hide=True,
            )
        )

    return msgs
