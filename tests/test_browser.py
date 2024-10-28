import pytest

# TODO: we should also test lynx backend
playwright = pytest.importorskip("playwright")

# noreorder
from gptme.tools.browser import read_url, search  # fmt: skip

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

    # check that link to activitywatch is present
    assert "https://activitywatch.net/" in s
