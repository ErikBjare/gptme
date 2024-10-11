import shutil

from . import ToolSpec, ToolUse


def has_gh_tool() -> bool:
    return shutil.which("gh") is not None


instructions = "Interact with GitHub via the GitHub CLI (gh)."

examples = f"""
> User: create a public repo from the current directory, and push. Note that --confirm and -y are deprecated, and no longer needed.
> Assistant:
{ToolUse("shell", [], '''
REPO=$(basename $(pwd))
gh repo create $REPO --public --source . --push
''').to_output()}

> User: show issues
> Assistant:
{ToolUse("shell", [], "gh issue list --repo $REPO").to_output()}

> User: read issue with comments
> Assistant:
{ToolUse("shell", [], "gh issue view $ISSUE --repo $REPO --comments").to_output()}

> User: show recent workflows
> Assistant:
{ToolUse("shell", [], "gh run list --repo $REPO --limit 5").to_output()}

> User: show workflow
> Assistant:
{ToolUse("shell", [], "gh run view $RUN --repo $REPO --log").to_output()}
"""

# Note: this isn't actually a tool, it only serves prompting purposes
tool = ToolSpec(
    name="gh",
    available=has_gh_tool(),
    desc="Interact with GitHub",
    instructions=instructions,
    examples=examples,
)
