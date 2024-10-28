"""
Tools to let the assistant control a browser, including:
 - loading pages
 - reading their contents
 - viewing them through screenshots
 - searching

.. note::

    This is an experimental feature. It needs some work to be more robust and useful.

To use the browser tool, you need to have the `playwright` Python package installed along with gptme, which you can install with:

.. code-block:: bash

    pipx install gptme[browser]
    gptme '/shell playwright install chromium'
"""

import importlib.util
import logging
import shutil
from pathlib import Path
from typing import Literal

from .base import ToolSpec, ToolUse

has_playwright = lambda: importlib.util.find_spec("playwright") is not None  # noqa
has_lynx = lambda: shutil.which("lynx")  # noqa
browser: Literal["playwright", "lynx"] | None = (
    "playwright" if has_playwright() else ("lynx" if has_lynx() else None)
)

# noreorder
if browser == "playwright":
    from ._browser_playwright import read_url as read_url_playwright  # fmt: skip
    from ._browser_playwright import (
        screenshot_url as screenshot_url_playwright,  # fmt: skip
    )
    from ._browser_playwright import search_duckduckgo, search_google  # fmt: skip
elif browser == "lynx":
    from ._browser_lynx import read_url as read_url_lynx  # fmt: skip
    from ._browser_lynx import search as search_lynx  # fmt: skip

logger = logging.getLogger(__name__)

EngineType = Literal["google", "duckduckgo"]

instructions = """
To browse the web, you can use the `read_url`, `search`, and `screenshot_url` functions in Python.
""".strip()

examples = f"""
### Answer question from URL with browsing
User: find out which is the latest ActivityWatch version from superuserlabs.org
Assistant: Let's browse the site.
{ToolUse("ipython", [], "read_url('https://superuserlabs.org/')").to_output()}
System:
{ToolUse("https://superuserlabs.org/", [], "... [ActivityWatch](https://activitywatch.net/) ...".strip()).to_output()}
Assistant: Couldn't find the answer on the page. Following link to the ActivityWatch website.
{ToolUse("ipython", [], "read_url('https://activitywatch.net/')").to_output()}
System:
{ToolUse("https://activitywatch.net/", [], "... Download latest version v0.12.2 ...".strip()).to_output()}
Assistant: The latest version of ActivityWatch is v0.12.2

### Searching
User: who is the founder of ActivityWatch?
Assistant: Let's search for that.
{ToolUse("ipython", [], "search('ActivityWatch founder')").to_output()}
System:
{ToolUse("results", [], "1. [ActivityWatch](https://activitywatch.net/) ...").to_output()}
Assistant: Following link to the ActivityWatch website.
{ToolUse("ipython", [], "read_url('https://activitywatch.net/')").to_output()}
System:
{ToolUse("https://activitywatch.net/", [], "... The ActivityWatch project was founded by Erik Bjäreholt in 2016. ...".strip()).to_output()}
Assistant: The founder of ActivityWatch is Erik Bjäreholt.

### Take screenshot of page
User: take a screenshot of the ActivityWatch website
Assistant: Certainly! I'll use the browser tool to screenshot the ActivityWatch website.
{ToolUse("ipython", [], "screenshot_url('https://activitywatch.net')").to_output()}
System:
{ToolUse("result", [], "Screenshot saved to screenshot.png").to_output()}
""".strip()


def has_browser_tool():
    return browser is not None


def read_url(url: str) -> str:
    """Read a webpage in a text format."""
    assert browser
    if browser == "playwright":
        return read_url_playwright(url)  # type: ignore
    elif browser == "lynx":
        return read_url_lynx(url)  # type: ignore


def search(query: str, engine: EngineType = "google") -> str:
    """Search for a query on a search engine."""
    logger.info(f"Searching for '{query}' on {engine}")
    if browser == "playwright":
        return search_playwright(query, engine)
    elif browser == "lynx":
        return search_lynx(query, engine)  # type: ignore
    raise ValueError(f"Unknown search engine: {engine}")


def search_playwright(query: str, engine: EngineType = "google") -> str:
    """Search for a query on a search engine using Playwright."""
    if engine == "google":
        return search_google(query)  # type: ignore
    elif engine == "duckduckgo":
        return search_duckduckgo(query)  # type: ignore
    raise ValueError(f"Unknown search engine: {engine}")


def screenshot_url(url: str, path: Path | str | None = None) -> Path:
    """Take a screenshot of a webpage."""
    assert browser
    if browser == "playwright":
        return screenshot_url_playwright(url, path)  # type: ignore
    raise ValueError("Screenshot not supported with lynx backend")


tool = ToolSpec(
    name="browser",
    desc="Browse the web",
    instructions=instructions,
    examples=examples,
    functions=[read_url, search, screenshot_url],
    available=has_browser_tool(),
)
__doc__ = tool.get_doc(__doc__)
