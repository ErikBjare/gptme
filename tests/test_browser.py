import pytest

playwright = pytest.importorskip("playwright")

# noreorder
from gptme.tools.browser import load_page, read_url, search  # fmt: skip

# noreorder
from playwright.sync_api import expect  # fmt: skip


@pytest.mark.slow
def test_browser():
    page = load_page("https://superuserlabs.org")
    expect(page.get_by_role("main")).to_contain_text("Erik Bjäreholt")


# FIXME: Broken
# @pytest.mark.slow
# def test_search_duckduckgo():
#     results = search("test", "duckduckgo")
#     print(results)
#     assert "```results" in results


@pytest.mark.slow
def test_search_google():
    results = search("test", "google")
    print(results)
    assert "1." in results


@pytest.mark.slow
def test_read_url_with_links():
    s = read_url("https://superuserlabs.org")

    # check that "Erik Bjäreholt" is present
    assert "Erik Bjäreholt" in s

    # check that markdown link to activitywatch is present
    assert "(https://activitywatch.net/)" in s
