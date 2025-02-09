import json
import logging
import os
import shutil
import subprocess
import time
from collections import Counter
from copy import copy
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from ..config import get_config
from ..message import Message

logger = logging.getLogger(__name__)


def use_fresh_context() -> bool:
    """Check if fresh context mode is enabled.

    Fresh context mode (GPTME_FRESH=true) ensures that file contents shown in the context
    are always up to date by:
    - Adding a context message before each user message
    - Including current git status
    - Including contents of recently modified files
    - Marking outdated file contents in the conversation history
    """
    flag: str = get_config().get_env("GPTME_FRESH", "")  # type: ignore
    return flag.lower() in ("1", "true", "yes")


def use_checks() -> bool:
    """Check if pre-commit checks are enabled.

    Pre-commit checks are enabled when either:
    1. GPTME_CHECK=true is set explicitly, or
    2. A .pre-commit-config.yaml file exists in any parent directory

    Any issues found are included in the context, helping catch and fix code quality
    issues before the user continues the conversation.
    """
    flag: str = get_config().get_env("GPTME_CHECK", "")  # type: ignore
    explicit_enabled = flag.lower() in ("1", "true", "yes")
    explicit_disabled = flag.lower() in ("0", "false", "no")
    if explicit_disabled:
        return False

    # Check for .pre-commit-config.yaml in any parent directory
    has_config = any(
        parent.joinpath(".pre-commit-config.yaml").exists()
        for parent in [Path.cwd(), *Path.cwd().parents]
    )

    if explicit_enabled and not has_config:
        logger.warning(
            "GPTME_CHECK is enabled but no .pre-commit-config.yaml found in any parent directory"
        )

    return explicit_enabled or has_config


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


def md_codeblock(lang: str | Path, content: str) -> str:
    """Wrap content in a markdown codeblock."""
    return f"```{lang}\n{content}\n```"


def textfile_as_codeblock(path: Path) -> str | None:
    """Include file content as a codeblock."""
    try:
        if path.exists() and path.is_file():
            try:
                return md_codeblock(path, path.read_text())
            except UnicodeDecodeError:
                return None
    except OSError:
        return None
    return None


def append_file_content(
    msg: Message, workspace: Path | None = None, check_modified=False
) -> Message:
    """Append attached text files to a message."""
    files = [file_to_display_path(f, workspace).expanduser() for f in msg.files]
    files_text = {}
    for f in files:
        if not check_modified or f.stat().st_mtime <= datetime.timestamp(msg.timestamp):
            content = textfile_as_codeblock(f)
            if not content:
                # Non-text file, skip
                continue
            files_text[f] = content
        else:
            files_text[f] = md_codeblock(f, "<file was modified after message>")
    return replace(
        msg,
        content=msg.content + "\n\n".join(files_text.values()),
        files=[f for f in files if f not in files_text],
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
        logger.info(f"Getting PR status for branch: {branch}")
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

<body>
{pr["body"]}
</body>

<comments>
{pr["comments"]}
</comments>

<diff>
{p_diff.stdout}
</diff>
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
            return md_codeblock("git status -vv", git_status.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("Not in a git repository or git not available")
    return None


def get_mentioned_files(msgs: list[Message], workspace: Path | None) -> list[Path]:
    """Count files mentioned in messages."""
    workspace_abs = workspace.resolve() if workspace else None
    files: Counter[Path] = Counter()
    for msg in msgs:
        for f in msg.files:
            # If path is relative and we have a workspace, make it absolute relative to workspace
            if workspace_abs and not f.is_absolute():
                f = (workspace_abs / f).resolve()
            else:
                f = f.resolve()
            files[f] += 1

    if files:
        logger.info(f"Files mentioned: {dict(files)}")

    def file_score(f: Path) -> tuple[int, float]:
        # Sort by mentions and recency
        try:
            mtime = f.stat().st_mtime
            return (files[f], mtime)
        except FileNotFoundError:
            return (files[f], 0)

    return sorted(files.keys(), key=file_score, reverse=True)


def gather_fresh_context(
    msgs: list[Message], workspace: Path | None, git=True
) -> Message:
    """Gather fresh context from files and git status."""

    files = get_mentioned_files(msgs, workspace)
    sections = []

    # Add pre-commit check results if there are issues
    if precommit_output := run_precommit_checks():
        sections.append(precommit_output)

    if git and (git_status_output := git_status()):
        sections.append(git_status_output)

    # if pr_status_output := gh_pr_status():
    #     sections.append(pr_status_output)

    # Read contents of most relevant files
    for f in files[:10]:  # Limit to top 10 files
        if f.exists():
            try:
                with open(f) as file:
                    content = file.read()
            except UnicodeDecodeError:
                logger.debug(f"Skipping binary file: {f}")
                content = "<binary file>"
            display_path = file_to_display_path(f, workspace)
            logger.info(f"Read file: {display_path}")
            sections.append(md_codeblock(display_path, content))
        else:
            logger.info(f"File not found: {f}")

    cwd = Path.cwd()
    return Message(
        "system",
        f"""# Context
Working directory: {cwd}

This context message is always inserted before the last user message.
It contains the current state of relevant files and git status at the time of processing.
The file contents shown in this context message are the source of truth.
Any file contents shown elsewhere in the conversation history may be outdated.
This context message will be removed and replaced with fresh context on every new message.

"""
        + "\n\n".join(sections),
    )


def get_changed_files() -> list[Path]:
    """Returns a list of changed files based on git diff."""
    try:
        p = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [Path(f) for f in p.stdout.splitlines()]
    except subprocess.CalledProcessError as e:
        logger.debug(f"Error getting git diff files: {e}")
        return []


def run_precommit_checks() -> str | None:
    """Run pre-commit checks on modified files and return output if there are issues.

    Pre-commit checks will run if either:
    1. GPTME_CHECK=true is set explicitly, or
    2. A .pre-commit-config.yaml file exists in any parent directory
    """
    if not use_checks():
        logger.debug("Pre-commit checks not enabled")
        return None

    # cmd = "pre-commit run --files $(git ls-files -m)"
    cmd = "pre-commit run --all-files"
    start_time = time.monotonic()
    logger.info(f"Running pre-commit checks: {cmd}")
    try:
        subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return None  # No issues found
    except subprocess.CalledProcessError as e:
        logger.error(f"Pre-commit checks failed: {e}")
        output = "Pre-commit checks failed\n\n"

        # Add stdout if present
        if e.stdout.strip():
            output += md_codeblock("stdout", e.stdout.rstrip()) + "\n\n"

        # Add stderr if present
        if e.stderr.strip():
            output += md_codeblock("stderr", e.stderr.rstrip()) + "\n\n"

        # Add guidance about automated fixes
        if "files were modified by this hook" in e.stdout:
            output += "Note: Some issues were automatically fixed by the pre-commit hooks. No manual fixes needed for those changes."
        else:
            output += "Note: The above issues require manual fixes as they were not automatically resolved."

        return output.strip()
    finally:
        logger.info(
            f"Pre-commit checks completed in {time.monotonic() - start_time:.2f}s"
        )


def autocommit() -> Message:
    """
    Auto-commit staged changes.
    """
    # TODO: auto-stage files modified by gptme
    # TODO: add a review step?
    # TODO: generate commit message from diff + conversation history
    # TODO: enable with GPTME_AUTOCOMMIT=true
    return Message("system", "Auto-commit not implemented yet")


def enrich_messages_with_context(
    msgs: list[Message], workspace: Path | None = None
) -> list[Message]:
    """
    Enrich messages with context.
    Embeds file contents where they occur in the conversation.

    If GPTME_FRESH enabled, a context message will be added that includes:
    - git status
    - contents of files modified after their message timestamp
    """
    from ..tools.rag import rag_enhance_messages  # fmt: skip

    # Make a copy of messages to avoid modifying the original
    msgs = copy(msgs)

    # First enhance messages with context, if gptme-rag is available
    msgs = rag_enhance_messages(msgs, workspace)

    msgs = [
        append_file_content(msg, workspace, check_modified=use_fresh_context())
        for msg in msgs
    ]
    if use_fresh_context():
        # insert right before the last user message
        fresh_content_msg = gather_fresh_context(msgs, workspace)
        logger.info(fresh_content_msg.content)
        last_user_idx = next(
            (i for i, msg in enumerate(msgs[::-1]) if msg.role == "user"), None
        )
        msgs.insert(-last_user_idx if last_user_idx else -1, fresh_content_msg)
    else:
        # Legacy mode: file contents already included at the time of message creation
        pass

    return msgs
