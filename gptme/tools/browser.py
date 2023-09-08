"""
Tools to let LLMs control a browser.
"""

import atexit
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import ElementHandle, Page, sync_playwright

_p = None


def get_browser():
    """
    Return a browser object.
    """
    global _p
    if _p is None:
        _p = sync_playwright().start()

        atexit.register(_p.stop)
    browser = _p.chromium.launch()
    return browser


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
    page = context.new_page()
    page.goto(url)

    return page


def search(query: str, engine: str = "google") -> str:
    """
    Search for a query on a search engine.
    """
    if engine == "google":
        return _search_google(query)
    elif engine == "duckduckgo":
        return _search_duckduckgo(query)
    else:
        raise ValueError(f"Unknown search engine: {engine}")


def _search_google(query: str) -> str:
    """
    Search for a query on Google.
    """
    query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={query}&hl=en"
    page = load_page(url)

    els = _list_clickable_elements(page)
    for el in els:
        print(f"{el['type']}: {el['text']}")
        if "Accept all" in el["text"]:
            el["element"].click()
            print("Accepted terms")
            break

    # list results
    result_str = _list_results_google(page)

    return result_str


def _search_duckduckgo(query: str) -> str:
    url = f"https://duckduckgo.com/?q={query}"
    page = load_page(url)

    el = page.query_selector(".react-results--main")
    if el:
        return el.inner_text()
    else:
        return "Error: no results found"


@dataclass
class Element:
    type: str
    text: str
    name: str
    href: Optional[str]
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
            selector=element.evaluate("el => el.selector"),
        )


def _list_input_elements(page):
    elements = []

    # List all input elements
    inputs = page.query_selector_all("input")
    print("Input Elements:")
    for i, input_element in enumerate(inputs):
        elements.append(Element.from_element(input_element))


def _list_clickable_elements(page, selector=None) -> list[dict]:
    elements = []

    # filter by selector
    if selector:
        selector = f"{selector} button, {selector} a"
    else:
        selector = "button, a"

    # List all clickable buttons
    clickable = page.query_selector_all(selector)
    for i, el in enumerate(clickable):
        tag_name = el.evaluate("el => el.tagName")
        text = el.evaluate("el => el.innerText")
        href = el.evaluate("el => el.href")
        elements.append(
            {
                "type": tag_name,
                "text": text,
                "href": href,
                "element": el,
                "selector": f"{tag_name}:has-text('{text}')",
            }
        )

    return elements


def _list_results_google(page):
    # fetch the results (elements with .g class)
    results = page.query_selector_all(".g")

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
