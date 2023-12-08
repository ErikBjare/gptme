"""
Tools to let the assistant control a browser, including reading webpages and searching.

.. note::

    This is an experimental feature. It needs some work to be more robust and useful.
"""

import atexit
import logging
import re
import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass
from typing import Literal

from playwright.sync_api import ElementHandle, Page, sync_playwright

_p = None
logger = logging.getLogger(__name__)

EngineType = Literal["google", "duckduckgo"]

instructions = """
To browse the web, you can use the `load_url` and `search` commands.
"""

examples = """
> User: find out which is the latest ActivityWatch version from this site https://superuserlabs.org/
> Assistant: ```load_url https://superuserlabs.org/```
> System:
```https://superuserlabs.org/
...
[ActivityWatch](https://activitywatch.net/)
...
```
> Assistant: ```load_url https://activitywatch.net/```
> System:
```https://activitywatch.net/
...
Download latest version v0.12.2
> Assistant: The latest version of ActivityWatch is v0.12.2

> User: who is the founder of ActivityWatch?
> Assistant: ```search who is the founder of ActivityWatch?```
> System:
```Results:
1. [ActivityWatch](https://activitywatch.net/)
...
```
> Assistant: ```load_url https://activitywatch.net/```
> System:
```https://activitywatch.net/
...
The ActivityWatch project was founded by Erik Bjäreholt in 2016.
...
```
""".strip()


def get_browser():
    """
    Return a browser object.
    """
    global _p
    if _p is None:
        logger.info("Starting browser")
        _p = sync_playwright().start()

        atexit.register(_p.stop)
    browser = _p.chromium.launch()
    return browser


def read_url(url: str) -> str:
    """Read the text of a webpage and return the text in Markdown format."""
    page = load_page(url)

    # Get the HTML of the body
    body_html = page.inner_html("body")

    # Convert the HTML to Markdown
    markdown = html_to_markdown(body_html)

    return markdown


def load_page(url: str) -> Page:
    browser = get_browser()

    # set browser language to English such that Google uses English
    coords_sf = {"latitude": 37.773972, "longitude": 13.39}
    context = browser.new_context(
        locale="en-US",
        geolocation=coords_sf,
        permissions=["geolocation"],
    )

    # create a new page
    logger.info(f"Loading page: {url}")
    page = context.new_page()
    page.goto(url)

    return page


def search(query: str, engine: EngineType = "google") -> str:
    """Search for a query on a search engine."""
    logger.info(f"Searching for '{query}' on {engine}")
    if engine == "google":
        return _search_google(query)
    elif engine == "duckduckgo":
        return _search_duckduckgo(query)
    else:
        raise ValueError(f"Unknown search engine: {engine}")


def _search_google(query: str) -> str:
    query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={query}&hl=en"
    page = load_page(url)

    els = _list_clickable_elements(page)
    for el in els:
        # print(f"{el['type']}: {el['text']}")
        if "Accept all" in el.text:
            el.element.click()
            logger.debug("Accepted Google terms")
            break

    # list results
    result_str = _list_results_google(page)

    return result_str


def _search_duckduckgo(query: str) -> str:
    url = f"https://duckduckgo.com/?q={query}"
    page = load_page(url)

    return _list_results_duckduckgo(page)


@dataclass
class Element:
    type: str
    text: str
    name: str
    href: str | None
    element: ElementHandle
    selector: str

    @classmethod
    def from_element(cls, element: ElementHandle):
        return cls(
            type=element.evaluate("el => el.type"),
            text=element.evaluate("el => el.innerText"),
            name=element.evaluate("el => el.name"),
            href=element.evaluate("el => el.href"),
            element=element,
            # FIXME: is this correct?
            selector=element.evaluate("el => el.selector"),
        )


def _list_input_elements(page) -> list[Element]:
    # List all input elements
    elements = []
    inputs = page.query_selector_all("input")
    for i, input_element in enumerate(inputs):
        elements.append(Element.from_element(input_element))
    return elements


def _list_clickable_elements(page, selector=None) -> list[Element]:
    elements = []

    # filter by selector
    if selector:
        selector = f"{selector} button, {selector} a"
    else:
        selector = "button, a"

    # List all clickable buttons
    clickable = page.query_selector_all(selector)
    for i, el in enumerate(clickable):
        # "selector": f"{tag_name}:has-text('{text}')",
        elements.append(Element.from_element(el))

    return elements


def _list_results_google(page) -> str:
    # fetch the results (elements with .g class)
    results = page.query_selector_all(".g")
    if not results:
        return "Error: something went wrong with the search."

    # list results
    s = "Results:"
    for i, result in enumerate(results):
        url = result.query_selector("a").evaluate("el => el.href")
        h3 = result.query_selector("h3")
        if h3:
            title = h3.inner_text()
            result.query_selector("span").inner_text()
            s += f"\n{i+1}. {title} ({url})"
    return s


def _list_results_duckduckgo(page) -> str:
    # fetch the results
    results = page.query_selector(".react-results--main")
    results = results.query_selector_all("article")
    if not results:
        return "Error: something went wrong with the search."

    # list results
    s = "Results:"
    for i, result in enumerate(results):
        url = result.query_selector("a").evaluate("el => el.href")
        h2 = result.query_selector("h2")
        if h2:
            title = h2.inner_text()
            result.query_selector("span").inner_text()
            s += f"\n{i+1}. {title} ({url})"
    return s


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

    return markdown
