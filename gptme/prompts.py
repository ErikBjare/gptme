import os
import shutil

from .cli import __doc__ as cli_doc
from .config import get_config
from .message import Message

USER = os.environ["USER"]

ABOUT_ACTIVITYWATCH = """
ActivityWatch is a free and open-source automated time-tracker that helps you track how you spend your time on your devices.

It runs locally on the user's computer and has a REST API available at http://localhost:5600/api/.

GitHub: https://github.com/ActivityWatch/activitywatch
Docs: https://docs.activitywatch.net/
"""


def initial_prompt(short: bool = False) -> list[Message]:
    """Initial prompt to start the conversation. If no history given."""
    config = get_config()

    include_about = False
    include_user = True
    include_project = False
    include_tools = not short

    assert cli_doc
    msgs = []
    if include_about:
        msgs.append(Message("system", cli_doc))
    if include_user:
        msgs.append(Message("system", "$ whoami\n" + USER))

        # NOTE: this is better to have as a temporary message that's updated with every request, so that the information is up-to-date
        # pwd = subprocess.run(["pwd"], capture_output=True, text=True).stdout
        # msgs.append(Message("system", f"$ pwd\n{pwd}"))

        msgs.append(
            Message(
                "system",
                "Here is some information about the user: "
                + config["prompt"]["about_user"],
            )
        )
    if include_project:
        # TODO: detect from git root folder name
        project = "activitywatch"
        # TODO: enshrine in config
        config["prompt"]["project"] = {
            "activitywatch": ABOUT_ACTIVITYWATCH,
        }
        msgs.append(
            Message(
                "system",
                f"Some information about the current project {project}: "
                + config["prompt"]["project"][project],
            )
        )

    if include_tools:
        msgs.append(
            Message(
                "system",
                """
                You are a helpful assistant that will help the user with their tasks.
The assistant shows the user how to use tools to interact with the system and access the internet.
The assistant should be concise and not verbose, it should assume the user is very knowledgeable.
All commands should be copy-pasteable and runnable, do not use placeholders like `$REPO` or `<issue>`.
Do not suggest the user open a browser or editor, instead show them how to do it in the shell.
When the output of a command is of interest, end the code block so that the user can execute it before continuing.

Here are some examples:

# Terminal
Use by writing a code block like this:

> User: learn about the project
```bash
ls
```
> stdout: README.md
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
Loading is done using `cat`.

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
