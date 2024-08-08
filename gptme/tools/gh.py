import shutil

from gptme.tools.base import ToolSpec


def has_gh_tool() -> bool:
    return shutil.which("gh") is not None


# Note: this isn't actually a tool, it only serves prompting purposes
tool = ToolSpec(
    name="gh",
    available=has_gh_tool(),
    desc="Interact with GitHub",
    instructions="",
    examples="""Here are examples of how to use the GitHub CLI (gh) to interact with GitHub.

> User: create a public repo from the current directory, and push
Note: --confirm and -y are deprecated, and no longer needed
```sh
REPO=$(basename $(pwd))
gh repo create $REPO --public --source . --push
```

> User: show issues
```sh
gh issue list --repo $REPO
```

> User: read issue with comments
```sh
gh issue view $ISSUE --repo $REPO --comments
```

> User: show recent workflows
```sh
gh run list --status failure --repo $REPO --limit 5
```

> User: show workflow
```sh
gh run view $RUN --repo $REPO --log
```
    """,
)
