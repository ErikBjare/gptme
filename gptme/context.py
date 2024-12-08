import json
import logging
import os
import shutil
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path

from .message import Message

logger = logging.getLogger(__name__)


def file_to_display_path(f: Path, workspace: Path | None = None) -> Path:
    """
    Determine how to display the path:
    - If file and pwd is in workspace, show path relative to pwd
    - Otherwise, show absolute path
    """
    cwd = Path.cwd()
    if workspace and workspace in f.parents and workspace in [cwd, *cwd.parents]:
        # NOTE: walk_up only available in Python 3.12+
        try:
            return f.relative_to(cwd)
        except ValueError:
            # If relative_to fails, try to find a common parent
            for parent in cwd.parents:
                try:
                    if workspace in parent.parents or workspace == parent:
                        return f.relative_to(parent)
                except ValueError:
                    continue
            return f.absolute()
    elif Path.home() in f.parents:
        return Path("~") / f.relative_to(os.path.expanduser("~"))
    return f


def textfile_as_codeblock(path: Path) -> str | None:
    """Include file content as a codeblock."""
    try:
        if path.exists() and path.is_file():
            try:
                return f"```{path}\n{path.read_text()}\n```"
            except UnicodeDecodeError:
                return None
    except OSError:
        return None
    return None


def append_file_content(msg: Message, workspace: Path | None = None) -> Message:
    """Append file content to a message."""
    files = [file_to_display_path(f, workspace) for f in msg.files]
    text_files = {f: content for f in files if (content := textfile_as_codeblock(f))}
    return replace(
        msg,
        content=msg.content + "\n\n".join(text_files.values()),
        files=[f for f in files if f not in text_files],
    )


def git_branch() -> str | None:
    """Get the current git branch name."""
    if shutil.which("git"):
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            if branch.returncode == 0:
                return branch.stdout.strip()
        except subprocess.CalledProcessError:
            logger.error("Failed to get git branch")
            return None
    return None


def gh_pr_status() -> str | None:
    """Get GitHub PR status if available."""
    branch = git_branch()
    if shutil.which("gh") and branch and branch not in ["main", "master"]:
        try:
            p = subprocess.run(
                ["gh", "pr", "view", "--json", "number,title,url,body,comments"],
                capture_output=True,
                text=True,
                check=True,
            )
            p_diff = subprocess.run(
                ["gh", "pr", "diff"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get PR info: {e}")
            return None

        pr = json.loads(p.stdout)
        return f"""Pull Request #{pr["number"]}: {pr["title"]} ({branch})
{pr["url"]}

{pr["body"]}

<diff>
{p_diff.stdout}
</diff>

<comments>
{pr["comments"]}
</comments>
"""

    return None


def git_status() -> str | None:
    """Get git status if in a repository."""
    try:
        git_status = subprocess.run(
            ["git", "status", "-vv"], capture_output=True, text=True, check=True
        )
        if git_status.returncode == 0:
            logger.debug("Including git status in context")
            return f"```git status -vv\n{git_status.stdout}```"
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("Not in a git repository or git not available")
    return None


def gather_fresh_context(msgs: list[Message], workspace: Path | None) -> Message:
    """Gather fresh context from files and git status."""

    # Get files mentioned in conversation
    workspace_abs = workspace.resolve() if workspace else None
    files: Counter[Path] = Counter()
    for msg in msgs:
        for f in msg.files:
            # If path is relative and we have a workspace, make it absolute relative to workspace
            if not f.is_absolute() and workspace_abs:
                f = (workspace_abs / f).resolve()
            else:
                f = f.resolve()
            files[f] += 1
    logger.info(
        f"Files mentioned in conversation (workspace: {workspace_abs}): {dict(files)}"
    )

    # Sort by mentions and recency
    def file_score(f: Path) -> tuple[int, float]:
        try:
            mtime = f.stat().st_mtime
            return (files[f], mtime)
        except FileNotFoundError:
            return (files[f], 0)

    mentioned_files = sorted(files.keys(), key=file_score, reverse=True)
    sections = []

    if git_status_output := git_status():
        sections.append(git_status_output)

    if pr_status_output := gh_pr_status():
        sections.append(pr_status_output)

    # Read contents of most relevant files
    for f in mentioned_files[:10]:  # Limit to top 10 files
        if f.exists():
            logger.info(f"Including fresh content from: {f}")
            try:
                with open(f) as file:
                    content = file.read()
            except UnicodeDecodeError:
                logger.debug(f"Skipping binary file: {f}")
                content = "<binary file>"
            display_path = file_to_display_path(f, workspace)
            logger.info(f"Reading file: {display_path}")
            sections.append(f"```{display_path}\n{content}\n```")
        else:
            logger.info(f"File not found: {f}")

    cwd = Path.cwd()
    return Message(
        "system",
        f"""# Context
Working directory: {cwd}

This context message is inserted right before your last message.
It contains the current state of relevant files and git status at the time of processing.
The file contents shown in this context message are the source of truth.
Any file contents shown elsewhere in the conversation history may be outdated.
This context message will be removed and replaced with fresh context in the next message.

"""
        + "\n\n".join(sections),
    )
