"""
Tools to let the assistant control a browser, including:
 - loading pages
 - reading their contents
 - viewing them through screenshots
 - searching

.. note::

    This is an experimental feature. It needs some work to be more robust and useful.
"""

import importlib.util
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Literal

from .base import ToolSpec

has_playwright = importlib.util.find_spec("playwright") is not None

# noreorder
if has_playwright:
    from ._browser_playwright import (  # fmt: skip
        load_page,
        search_duckduckgo,
        search_google,
    )


logger = logging.getLogger(__name__)

EngineType = Literal["google", "duckduckgo"]

instructions = """
To browse the web, you can use the `read_url`, `search`, and `screenshot_url` functions in Python.
""".strip()

examples = """
### Answer question from URL with browsing
User: find out which is the latest ActivityWatch version from superuserlabs.org
Assistant: Let's browse the site.
```ipython
read_url("https://superuserlabs.org/")
```
System:
```https://superuserlabs.org/
...
[ActivityWatch](https://activitywatch.net/)
...
```
Assistant: Couldn't find the answer on the page. Following link to the ActivityWatch website.
```ipython
read_url("https://activitywatch.net/")
```
System:
```https://activitywatch.net/
...
Download latest version v0.12.2
...
```
Assistant: The latest version of ActivityWatch is v0.12.2

### Searching
User: who is the founder of ActivityWatch?
Assistant: Let's search for that.
```ipython
search("ActivityWatch founder")
```
System:
```results
1. [ActivityWatch](https://activitywatch.net/)
...
```
Assistant: Following link to the ActivityWatch website.
```ipython
read_url("https://activitywatch.net/")
```
System:
```https://activitywatch.net/
...
The ActivityWatch project was founded by Erik Bjäreholt in 2016.
...
```
Assistant: The founder of ActivityWatch is Erik Bjäreholt.

### Take screenshot of page
User: take a screenshot of the ActivityWatch website
Assistant: Certainly! I'll use the browser tool to screenshot the ActivityWatch website.
```ipython
screenshot_url("https://activitywatch.net")
```
System:
```
Screenshot saved to screenshot.png
```
""".strip()


def has_browser_tool():
    return has_playwright


def read_url(url: str) -> str:
    """Read the text of a webpage and return the text in Markdown format."""
    page = load_page(url)

    # Get the HTML of the body
    body_html = page.inner_html("body")

    # Convert the HTML to Markdown
    markdown = html_to_markdown(body_html)

    return markdown


def search(query: str, engine: EngineType = "google") -> str:
    """Search for a query on a search engine."""
    logger.info(f"Searching for '{query}' on {engine}")
    if engine == "google":
        return search_google(query)
    elif engine == "duckduckgo":
        return search_duckduckgo(query)
    else:
        raise ValueError(f"Unknown search engine: {engine}")


def screenshot_url(url: str, filename: str | None = None) -> str:
    """Take a screenshot of a webpage and save it to a file."""
    logger.info(f"Taking screenshot of '{url}' and saving to '{filename}'")
    page = load_page(url)

    if filename is None:
        filename = tempfile.mktemp(suffix=".png")
    else:
        # create the directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Take the screenshot
    page.screenshot(path=filename)

    return f"Screenshot saved to {filename}"


def html_to_markdown(html):
    # check that pandoc is installed
    if not shutil.which("pandoc"):
        raise Exception("Pandoc is not installed. Needed for browsing.")

    p = subprocess.Popen(
        ["pandoc", "-f", "html", "-t", "markdown"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input=html.encode())

    if p.returncode != 0:
        raise Exception(f"Pandoc returned error code {p.returncode}: {stderr.decode()}")

    # Post-process the output to remove :::
    markdown = stdout.decode()
    markdown = "\n".join(
        line for line in markdown.split("\n") if not line.strip().startswith(":::")
    )

    # Post-process the output to remove div tags
    markdown = markdown.replace("<div>", "").replace("</div>", "")

    # replace [\n]{3,} with \n\n
    markdown = re.sub(r"[\n]{3,}", "\n\n", markdown)

    # replace {...} with ''
    markdown = re.sub(r"\{(#|style|target|\.)[^}]*\}", "", markdown)

    # strip inline images, like: data:image/png;base64,...
    re_strip_data = re.compile(r"!\[[^\]]*\]\(data:image[^)]*\)")

    # test cases
    assert re_strip_data.sub("", "![test](data:image/png;base64,123)") == ""
    assert re_strip_data.sub("", "![test](data:image/png;base64,123) test") == " test"

    markdown = re_strip_data.sub("", markdown)

    return markdown


tool = ToolSpec(
    name="browser",
    desc="Browse the web",
    instructions=instructions,
    examples=examples,
    functions=[read_url, search, screenshot_url],
    available=has_browser_tool(),
)
__doc__ = tool.get_doc(__doc__)
