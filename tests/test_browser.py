import pytest

# TODO: we should also test lynx backend
playwright = pytest.importorskip("playwright")

# noreorder
from gptme.tools.browser import read_url, search  # fmt: skip


# FIXME: Broken? ~~Seems to work, for now~~ edit: not anymore
@pytest.mark.skip
@pytest.mark.slow
def test_search_ddg():
    results = search("test", "duckduckgo")
    assert "1." in results, f"{results=}"


# FIXME: Broken, sometimes hits CAPTCHA
@pytest.mark.skip
@pytest.mark.slow
def test_search_google():
    results = search("test", "google")
    assert "1." in results, f"{results=}"


@pytest.mark.slow
def test_read_url_with_links():
    s = read_url("https://superuserlabs.org")

    # check that "Erik Bjäreholt" is present
    assert "Erik Bjäreholt" in s

    # check that link to activitywatch is present
    assert "https://activitywatch.net/" in s


@pytest.mark.slow
def test_read_url_arxiv_html():
    # TODO: test that we can read it in a reasonable amount of tokens
    # url = "https://arxiv.org/html/2410.12361v2"
    pass


@pytest.mark.slow
def test_read_url_arxiv_pdf():
    # TODO: test that we can read it
    # url = "https://arxiv.org/pdf/2410.12361v2"
    pass
