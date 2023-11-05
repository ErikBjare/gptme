import pytest

playwright = pytest.importorskip("playwright")
expect = playwright.sync_api.expect

# noreorder
from gptme.tools.browser import load_page, search  # fmt: skip


@pytest.mark.slow
def test_browser():
    page = load_page("https://superuserlabs.org")
    expect(page.get_by_role("main")).to_contain_text("Erik Bjäreholt")


@pytest.mark.slow
def test_search_duckduckgo():
    results = search("test", "duckduckgo")
    print(results)
    assert "Results:" in results


@pytest.mark.slow
def test_search_google():
    results = search("test", "google")
    print(results)
    assert "Results:" in results
