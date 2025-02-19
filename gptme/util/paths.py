"""Utilities for handling paths and URLs in messages."""

import logging
import re
import urllib.parse
from pathlib import Path

from ..tools import has_tool
from ..tools.browser import read_url

logger = logging.getLogger(__name__)

# Constants for regex patterns
CODE_BLOCK_PATTERN = r"```[\s\S]*?```"
BACKTICK_PATTERN = r"`([^`]+)`"
PUNCTUATION_PATTERN = r"[?.!,]+$"


def find_potential_paths(content: str) -> list[str]:
    """
    Find potential file paths and URLs in a message content.

    Looks for paths and URLs both inside and outside backticks,
    excluding content within code blocks. Handles:
    - Absolute paths (/path/to/file)
    - Home paths (~/path/to/file)
    - Relative paths (./path/to/file)
    - URLs (http://example.com)
    - Local files in current directory

    Args:
        content: The message content to search

    Returns:
        List of potential paths/URLs found in the message
    """
    # Remove code blocks
    content_no_codeblocks = re.sub(CODE_BLOCK_PATTERN, "", content)

    # Get current directory files for relative path matching
    cwd_files = {f.name for f in Path.cwd().iterdir()}  # Use set for O(1) lookup

    def clean_word(word: str) -> str:
        """Remove trailing punctuation and whitespace."""
        return re.sub(PUNCTUATION_PATTERN, "", word.strip())

    def is_path_like(word: str) -> bool:
        """Check if a word looks like a path or URL."""
        # Path prefixes that indicate a file path
        path_prefixes = {"/", "~/", "./"}
        word_start = word.split("/", 1)[0]

        return (
            any(word.startswith(prefix) for prefix in path_prefixes)
            or word.startswith("http")
            or "/" in word
            or word_start in cwd_files
        )

    paths = set()  # Use set to avoid duplicates

    # Find backtick-wrapped paths
    for match in re.finditer(BACKTICK_PATTERN, content_no_codeblocks):
        word = clean_word(match.group(1))
        if is_path_like(word):
            paths.add(word)

    # Find non-backtick-wrapped paths
    content_no_backticks = re.sub(BACKTICK_PATTERN, "", content_no_codeblocks)
    for word in re.split(r"\s+", content_no_backticks):
        word = clean_word(word)
        if word and is_path_like(word):
            paths.add(word)

    return list(paths)


def is_url(text: str) -> bool:
    """Check if text is a URL."""
    try:
        p = urllib.parse.urlparse(text)
        return bool(p.scheme and p.netloc)
    except ValueError:
        return False


def resolve_path(path: str, workspace: Path | None) -> Path | None:
    """Resolve and validate a file path."""
    try:
        file_path = Path(path).expanduser()
        if not file_path.exists() or not file_path.is_file():
            return None

        # Make path relative to workspace if needed
        if workspace and not file_path.is_absolute():
            file_path = file_path.absolute().relative_to(workspace)

        return file_path
    except (OSError, ValueError) as e:
        logger.debug(f"Failed to resolve path {path}: {e}")
        return None


def read_text_file(path: Path) -> str | None:
    """Try to read a file as text."""
    try:
        return path.read_text()
    except UnicodeDecodeError:
        return None


def process_url(url: str) -> str:
    """Process a URL and return its contents if available."""
    if not has_tool("browser"):
        logger.warning("Browser tool not available, skipping URL read")
        return ""

    try:
        content = read_url(url)
        return f"\n\n```{url}\n{content}\n```"
    except Exception as e:
        logger.warning(f"Failed to read URL {url}: {e}")
        return ""
