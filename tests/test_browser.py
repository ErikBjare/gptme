import pytest
from gptme.tools.browser import load_page, search


@pytest.mark.slow
def test_browser():
    content = load_page("https://www.google.com/ncr?hl=en")
    print(content)


@pytest.mark.slow
def test_search():
    content = search("test")
    print(content)
