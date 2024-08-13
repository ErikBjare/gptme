import atexit
import logging
import urllib.parse
from dataclasses import dataclass

from playwright.sync_api import ElementHandle, Page, sync_playwright

_p = None
logger = logging.getLogger(__name__)


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


def search_google(query: str) -> str:
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


def search_duckduckgo(query: str) -> str:
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
    for input_element in inputs:
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
    for el in clickable:
        elements.append(Element.from_element(el))

    return elements


def titleurl_to_list(results: list[tuple[str, str]]) -> str:
    s = "```results"
    for i, (title, url) in enumerate(results):
        s += f"\n{i+1}. {title} ({url})"
    return s + "\n```"


def _list_results_google(page) -> str:
    # fetch the results (elements with .g class)
    results = page.query_selector_all(".g")
    if not results:
        return "Error: something went wrong with the search."

    # list results
    hits = []
    for result in results:
        url = result.query_selector("a").evaluate("el => el.href")
        h3 = result.query_selector("h3")
        if h3:
            title = h3.inner_text()
            result.query_selector("span").inner_text()
            hits.append((title, url))
    return titleurl_to_list(hits)


def _list_results_duckduckgo(page) -> str:
    # fetch the results
    results = page.query_selector(".react-results--main")
    if not results:
        logger.error("Unable to find selector `.react-results--main` in results")
        return "Error: something went wrong with the search."
    results = results.query_selector_all("article")
    if not results:
        return "Error: something went wrong with the search."

    # list results
    hits = []
    for result in results:
        url = result.query_selector("a").evaluate("el => el.href")
        h2 = result.query_selector("h2")
        if h2:
            title = h2.inner_text()
            result.query_selector("span").inner_text()
            hits.append((title, url))
    return titleurl_to_list(hits)
