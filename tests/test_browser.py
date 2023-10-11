import pytest

try:
    # noreorder
    import playwright  # fmt: skip # noqa: F401
except ImportError:
    pytest.skip("playwright not installed", allow_module_level=True)

# noreorder
from gptme.tools.browser import load_page, search  # fmt: skip


@pytest.mark.slow
def test_browser():
    content = load_page("https://www.google.com/ncr?hl=en")
    print(content)


@pytest.mark.slow
def test_search():
    content = search("test")
    print(content)
