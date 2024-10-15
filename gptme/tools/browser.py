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
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import sleep
from typing import Literal

from .base import ToolSpec, ToolUse

has_playwright = importlib.util.find_spec("playwright") is not None

# noreorder
if has_playwright:
    from ._browser_playwright import (  # fmt: skip
        get_browser,
        load_page,
        search_duckduckgo,
        search_google,
    )


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


def has_pdftotext():
    return shutil.which("pdftotext") is not None


def has_browser_tool():
    return has_playwright


def read_url(url: str) -> str:
    """Read the text of a webpage or PDF and return the text in Markdown format."""
    browser = get_browser()
    context = browser.new_context()
    page = context.new_page()

    download_started = False
    download_result: str | Exception | None = None

    def resultwrapper(f):
        nonlocal download_result
        try:
            download_result = f()
        except Exception as e:
            print(f"{e=}")
            download_result = e

    def on_download(download):
        nonlocal download_started, download_result
        download_started = True
        logger.info(f"Download started: {download.suggested_filename}")

        # Wait for the download process to complete and save the downloaded file somewhere
        path = Path(tempfile.mkdtemp()) / download.suggested_filename
        download.save_as(path)

        if path.suffix == ".pdf":
            if not has_pdftotext():
                raise Exception(
                    "pdftotext is not installed. Needed for reading PDF files."
                )

            # Convert PDF to text
            result = subprocess.run(
                ["pdftotext", path, "-"], capture_output=True, text=True
            )
            if result.returncode != 0:
                raise Exception(
                    f"pdftotext returned error code {result.returncode}: {result.stderr}"
                )

            return result.stdout
        else:
            raise Exception(f"Unsupported file extension: {path.suffix}")

    page.on("download", lambda: resultwrapper(on_download))

    try:
        page.goto(url, wait_until="domcontentloaded")
    except Exception as e:
        print("EXCEPT CAUGHT")
        print(f"{e=}")
        # could be download
        sleep(1)
        print(f"{download_started=}")
        if download_started:
            # wait until download_result is set, or timeout after 10 seconds
            s = 0
            while download_result is None and s < 10:
                s += 1
                sleep(1)
                print("...")
            if download_result is not None:
                if isinstance(download_result, Exception):
                    raise download_result from None
                return download_result
            else:
                raise Exception("Download timed out")
        raise

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
