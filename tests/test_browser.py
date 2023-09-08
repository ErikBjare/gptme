from gptme.tools.browser import load_page, search


def test_browser():
    content = load_page("https://www.google.com/ncr?hl=en")
    print(content)


def test_search():
    content = search("test")
    print(content)
