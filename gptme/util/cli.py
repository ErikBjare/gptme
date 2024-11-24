"""
CLI for gptme utility commands.
"""

import glob
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import git
from rich import print as rich_print
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ..dirs import get_logs_dir
from ..logmanager import LogManager
from ..message import Message
from ..tools.chats import list_chats
from . import console

logger = logging.getLogger(__name__)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output.")
def main(verbose: bool = False):
    """Utility commands for gptme."""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.group()
def chats():
    """Commands for managing chat logs."""
    pass


@chats.command("ls")
@click.option("-n", "--limit", default=20, help="Maximum number of chats to show.")
@click.option(
    "--summarize", is_flag=True, help="Generate LLM-based summaries for chats"
)
def chats_list(limit: int, summarize: bool):
    """List conversation logs."""
    if summarize:
        from gptme.init import init  # fmt: skip

        # This isn't the best way to initialize the model for summarization, but it works for now
        init("openai/gpt-4o", interactive=False, tool_allowlist=[])
    list_chats(max_results=limit, include_summary=summarize)


@chats.command("read")
@click.argument("name")
def chats_read(name: str):
    """Read a specific chat log."""

    logdir = Path(get_logs_dir()) / name
    if not logdir.exists():
        print(f"Chat '{name}' not found")
        return

    log = LogManager.load(logdir)
    for msg in log.log:
        if isinstance(msg, Message):
            print(f"{msg.role}: {msg.content}")


@main.group()
def tokens():
    """Commands for token counting."""
    pass


@tokens.command("count")
@click.argument("text", required=False)
@click.option("-m", "--model", default="gpt-4", help="Model to use for token counting.")
@click.option(
    "-f", "--file", type=click.Path(exists=True), help="File to count tokens in."
)
def tokens_count(text: str | None, model: str, file: str | None):
    """Count tokens in text or file."""
    import tiktoken  # fmt: skip

    # Get text from file if specified
    if file:
        with open(file) as f:
            text = f.read()
    elif not text and not sys.stdin.isatty():
        text = sys.stdin.read()

    if not text:
        print("Error: No text provided. Use --file or pipe text to stdin.")
        return

    # Validate model
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"Error: Model '{model}' not supported by tiktoken.")
        print("Supported models include: gpt-4, gpt-3.5-turbo, text-davinci-003")
        sys.exit(1)

    # Count tokens
    tokens = enc.encode(text)
    print(f"Token count ({model}): {len(tokens)}")


@main.group()
def context():
    """Commands for context generation."""
    pass


@context.command("generate")
@click.argument("path", type=click.Path(exists=True))
def context_generate(path: str):
    """Index a file or directory for context retrieval."""
    from ..tools.rag import init, rag_index  # fmt: skip

    # Initialize RAG
    init()

    # Index the file/directory
    n_docs = rag_index(path)
    print(f"Indexed {n_docs} documents")


@main.group()
def prompts():
    """Commands for generating prompts/contexts."""
    pass


@prompts.command("git")
@click.option("--branch", help="Specific branch to analyze")
@click.option("--since", help="Show changes since this date/ref")
@click.option(
    "--max-files", type=int, default=10, help="Maximum number of files to include"
)
@click.option(
    "--show-diff/--no-diff",
    default=True,
    help="Show diffs of staged and unstaged changes",
)
def prompts_git(
    branch: str | None,
    since: str | None,
    max_files: int,
    show_diff: bool,
):
    """Generate a prompt about the current git repository."""

    logger = logging.getLogger(__name__)
    print("## Git")

    def format_section(title: str, items: list[str]) -> list[str]:
        """Format a section with title and items."""
        if not items:
            return []

        result = [f"\n### {title}"]

        for item in items:
            item_prefix = "- "
            result.append(f"{item_prefix}{item}")
        return result

    def get_diff_output(repo: git.Repo, staged: bool = False) -> str:
        """Get formatted diff output."""
        if staged:
            diff_obj = repo.index.diff(repo.head.commit)
            diff_str = repo.git.diff("--cached")
        else:
            diff_obj = repo.index.diff(None)
            diff_str = repo.git.diff()

        if not diff_str.strip():
            return ""

        [d.a_path for d in diff_obj]
        title = "Staged changes" if staged else "Unstaged changes"

        output = [f"### {title}", "\n```diff"]

        output.extend([diff_str, "```"])
        return "\n".join(output)

    try:
        repo = git.Repo(".", search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        logger.error("Not a git repository")
        return

    sections = []

    # Basic repo info
    if repo.remotes:
        origin = repo.remotes.origin
        sections.extend([f"Repository: {origin.url}"])

    try:
        branch_name = repo.active_branch.name
        sections.append(f"Current branch: {branch_name}")
    except TypeError:
        # Handle detached HEAD state
        sections.append(f"HEAD is detached at {repo.head.commit.hexsha[:7]}")
        branch_name = None

    # Recent commits
    commits = list(repo.iter_commits(branch or branch_name, max_count=5))
    if commits:
        commit_items = []
        for commit in commits:
            date = commit.committed_datetime.strftime("%Y-%m-%d %H:%M")
            commit_items.append(f"{commit.hexsha[:7]} ({date}) {commit.summary}")
        sections.extend(format_section("Recent commits", commit_items))

    # Changed files
    try:
        if since:
            diff = repo.git.diff(since, name_only=True).split("\n")
        else:
            diff = [item.a_path for item in repo.index.diff(None)]

        if diff and diff[0]:
            shown_files = diff[:max_files]
            sections.extend(format_section("Changed files", shown_files))
            if len(diff) > max_files:
                sections.append(f"... and {len(diff) - max_files} more changed files")
    except git.GitCommandError as e:
        logger.error(f"Error getting changed files: {e}")

    # Untracked files
    try:
        untracked = repo.untracked_files
        if untracked:
            shown_files = untracked[:max_files]
            sections.extend(format_section("Untracked files", shown_files))
            if len(untracked) > max_files:
                sections.append(
                    f"... and {len(untracked) - max_files} more untracked files"
                )
    except Exception as e:
        logger.error(f"Error getting untracked files: {e}")

    # Add stats
    try:
        stats = repo.git.shortlog("--summary", "--numbered", "--email").split("\n")
        if stats and stats[0]:
            sections.extend(["\nContributors:"] + [f"• {s.strip()}" for s in stats[:3]])
            if len(stats) > 3:
                sections.append(f"... and {len(stats) - 3} more contributors")
    except git.GitCommandError:
        pass  # Skip if stats unavailable

    # Add diffs if requested
    if show_diff:
        # Add staged changes
        staged_diff = get_diff_output(repo, staged=True)
        if staged_diff:
            sections.extend(["", staged_diff])

        # Add unstaged changes
        unstaged_diff = get_diff_output(repo, staged=False)
        if unstaged_diff:
            sections.extend(["", unstaged_diff])

    print("\n".join(sections))


@prompts.command("journal")
@click.option("--days", type=int, default=7, help="Number of days to look back")
@click.option(
    "--path",
    type=click.Path(exists=True),
    help="Journal directory path (optional)",
)
def prompts_journal(days: int, path: str | None, silent_fail: bool = True):
    """Generate a prompt from journal entries."""

    logger = logging.getLogger(__name__)

    # Common journal locations to try
    locations = [
        path,  # User-specified path first
        os.path.expanduser("~/journal"),
        os.path.expanduser("~/Documents/journal"),
        os.path.expanduser("~/notes"),
        os.path.expanduser("~/Documents/notes"),
    ]

    journal_dir = None
    for loc in locations:
        if loc and os.path.exists(loc):
            journal_dir = loc
            if loc != path:  # Only log if we're using a default location
                logger.info(f"Using journal directory: {loc}")
            break

    if not journal_dir:
        locations_str = "\n  ".join(
            [loc for loc in locations[1:] if loc]
        )  # Skip None from path
        if not silent_fail:
            print(f"No journal directory found. Tried:\n  {locations_str}")
            print("\nPlease specify a path with --path")
        return False

    # Get dates for the last N days
    dates = [
        (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)
    ]

    entries = []
    for date in dates:
        # Look for files matching the date pattern
        pattern = os.path.join(journal_dir, f"*{date}*.md")
        files = glob.glob(pattern)

        for file in files:
            with open(file) as f:
                content = f.read()
                entries.append(f"\n# {date}\n{content}")

    if entries:
        print(f"Journal entries from the last {days} days:\n")
        print("\n".join(entries))
    else:
        print(f"No journal entries found for the last {days} days")


def get_file_type(path: str) -> str:
    """Get file type from extension."""
    ext = os.path.splitext(path)[1].lower()
    if not ext:
        return "no extension"
    return ext[1:]  # Remove the dot


def list_files(path: str, excludes: list[str]) -> list[tuple[str, int]]:
    """List all files with their sizes, respecting excludes."""
    result = []
    for root, dirs, files in os.walk(path):
        # Skip excluded directories
        dirs[:] = [
            d
            for d in dirs
            if not any(
                os.path.join(root, d).startswith(os.path.join(path, e))
                for e in excludes
            )
        ]

        for file in files:
            file_path = os.path.join(root, file)
            # Skip excluded files
            if any(file_path.startswith(os.path.join(path, e)) for e in excludes):
                continue
            try:
                size = os.path.getsize(file_path)
                rel_path = os.path.relpath(file_path, path)
                result.append((rel_path, size))
            except OSError:
                continue
    return result


def walk_directory(
    directory: Path,
    tree: Tree,
    excludes: list[str] | None = None,
    max_depth: int | None = None,
    depth: int = 1,
    show_size: bool = True,
    icons: bool = False,
) -> None:
    """Recursively build a Tree with directory contents."""
    if excludes is None:
        excludes = []

    if max_depth is not None and depth > max_depth:
        return

    try:
        # Sort dirs first then by filename
        paths = sorted(
            Path(directory).iterdir(),
            key=lambda path: (path.is_file(), path.name.lower()),
        )

        for path in paths:
            # Skip excluded paths with fnmatch
            if any(path.match(e) for e in excludes):
                continue

            try:
                if path.is_dir():
                    style = "dim" if path.name.startswith("__") else ""
                    branch = tree.add(
                        f"[bold magenta]{':open_file_folder: ' if icons else ''}[link file://{path}]{escape(path.name)}/",
                        style=style,
                        guide_style=style,
                    )
                    walk_directory(
                        path, branch, excludes, max_depth, depth + 1, show_size
                    )
                else:
                    text_filename = Text(path.name, "green")
                    text_filename.highlight_regex(r"\..*$", "bold red")
                    text_filename.stylize(f"link file://{path}")

                    if show_size:
                        file_size = path.stat().st_size
                        text_filename.append(f" ({decimal(file_size)})", "blue")

                    # Choose icon based on file type
                    icon = "🐍 " if path.suffix == ".py" else "📄 "
                    tree.add((Text(icon if icons else "")) + text_filename)
            except OSError as e:
                tree.add(f"[red]{path.name} [Error: {e}]")

    except PermissionError:
        tree.add("[red][Permission denied]")
    except OSError as e:
        tree.add(f"[red][Error: {e}]")


def print_tree(
    path: str,
    excludes: list[str] | None = None,
    max_depth: int | None = None,
    show_size: bool = False,
    icons: bool = False,
) -> None:
    """Print directory structure as a rich tree.

    Args:
        path: Path to print tree for
        excludes: List of patterns to exclude
        max_depth: Maximum depth to traverse
        show_size: Whether to show file sizes
    """

    abs_path = os.path.abspath(path)
    tree = Tree(
        f":open_file_folder: [link file://{abs_path}]{abs_path}" if icons else abs_path,
        guide_style="bold bright_blue",
    )
    walk_directory(Path(path), tree, excludes, max_depth, show_size=show_size)
    rich_print(tree)


def show_file_contents(file_path: str) -> None:
    """Show contents of a file."""
    try:
        with open(file_path) as f:
            content = f.read().strip()
            if content:
                console.print(f"```{file_path}\n{content}\n```")
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")


def read_gitignore(path: str) -> list[str]:
    """Read .gitignore file and return list of patterns."""
    gitignore_path = os.path.join(path, ".gitignore")
    ignores = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            ignores += [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    # check global gitignore
    global_gitignore_path = os.path.expanduser("~/.config/git/ignore")
    if os.path.exists(global_gitignore_path):
        with open(global_gitignore_path) as f:
            ignores += [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    return ignores


@prompts.command("workspace")
@click.option(
    "--path", type=click.Path(exists=True), default=".", help="Workspace path"
)
@click.option("--max-depth", type=int, default=1, help="Maximum depth to show in tree")
def prompts_workspace(path: str, max_depth: int):
    """Generate a prompt about the current workspace directory structure.

    Shows the directory structure as a tree and provides statistics about file types
    and sizes. Can optionally show contents of important files like README and
    configuration files.

    Respects .gitignore if present. Useful for giving an AI assistant context about
    the project structure.
    """
    # Build excludes list from .gitignore
    excludes = read_gitignore(path) + [".git"]

    print("## Workspace structure\n\n```tree")
    print_tree(path, excludes=excludes, max_depth=max_depth)
    print("```")


@main.group()
def tools():
    """Tool-related utilities."""
    pass


@tools.command("list")
@click.option(
    "--available/--all", default=True, help="Show only available tools or all tools"
)
@click.option("--langtags", is_flag=True, help="Show language tags for code execution")
def tools_list(available: bool, langtags: bool):
    """List available tools."""
    from ..commands import _gen_help  # fmt: skip
    from ..tools import init_tools, loaded_tools  # fmt: skip

    # Initialize tools
    init_tools()

    if langtags:
        # Show language tags using existing help generator
        for line in _gen_help(incl_langtags=True):
            if line.startswith("Supported langtags:"):
                print("\nSupported language tags:")
                continue
            if line.startswith("  - "):
                print(line)
        return

    print("Available tools:")
    for tool in loaded_tools:
        if not available or tool.available:
            status = "✓" if tool.available else "✗"
            print(
                f"""
{status} {tool.name}
   {tool.desc}"""
            )


@tools.command("info")
@click.argument("tool_name")
def tools_info(tool_name: str):
    """Show detailed information about a tool."""
    from ..tools import get_tool, init_tools, loaded_tools  # fmt: skip

    # Initialize tools
    init_tools()

    tool = get_tool(tool_name)
    if not tool:
        print(f"Tool '{tool_name}' not found. Available tools:")
        for t in loaded_tools:
            print(f"- {t.name}")
        sys.exit(1)

    print(f"Tool: {tool.name}")
    print(f"Description: {tool.desc}")
    print(f"Available: {'Yes' if tool.available else 'No'}")
    print("\nInstructions:")
    print(tool.instructions)
    if tool.examples:
        print("\nExamples:")
        print(tool.examples)


@tools.command("call")
@click.argument("tool_name")
@click.argument("function_name")
@click.option(
    "--arg",
    "-a",
    multiple=True,
    help="Arguments to pass to the function. Format: key=value",
)
def tools_call(tool_name: str, function_name: str, arg: list[str]):
    """Call a tool with the given arguments."""
    from ..tools import get_tool, init_tools, loaded_tools  # fmt: skip

    # Initialize tools
    init_tools()

    tool = get_tool(tool_name)
    if not tool:
        print(f"Tool '{tool_name}' not found. Available tools:")
        for t in loaded_tools:
            print(f"- {t.name}")
        sys.exit(1)

    function = (
        [f for f in tool.functions if f.__name__ == function_name] or None
        if tool.functions
        else None
    )
    if not function:
        print(f"Function '{function_name}' not found in tool '{tool_name}'.")
        if tool.functions:
            print("Available functions:")
            for f in tool.functions:
                print(f"- {f.__name__}")
        else:
            print("No functions available for this tool.")
        sys.exit(1)
    else:
        # Parse arguments into a dictionary, ensuring proper typing
        kwargs = {}
        for arg_str in arg:
            key, value = arg_str.split("=", 1)
            kwargs[key] = value
        return_val = function[0](**kwargs)
        print(return_val)


if __name__ == "__main__":
    main()
