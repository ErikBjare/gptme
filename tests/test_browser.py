import pytest

playwright = pytest.importorskip("playwright")

# noreorder
from gptme.tools.browser import load_page, search  # fmt: skip


@pytest.mark.slow
def test_browser():
    content = load_page("https://superuserlabs.org")
    print(content)


@pytest.mark.slow
def test_search_duckduckgo():
    content = search("test", "duckduckgo")
    print(content)
    assert "Results:" in content


@pytest.mark.slow
def test_search_google():
    content = search("test", "google")
    print(content)
    assert "Results:" in content
