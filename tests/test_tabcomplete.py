import os
import sys

from gptme.tabcomplete import _matches


def test_matches():
    # echo cwd
    print(os.getcwd())

    # dirs
    assert ".git/" in _matches("")
    assert _matches(".githu") == [".github/"]
    assert _matches(".github") == [".github/"]
    assert set(_matches(".github/")) == {".github/workflows/", ".github/actions/"}

    # files
    assert _matches("README") == ["README.md"]
    assert _matches("./README") == ["README.md"]
    assert _matches("../gptme/README") == ["../gptme/README.md"]
    if sys.platform != "win32":
        assert "/etc/passwd" in _matches("/etc/pass")

    # commands
    assert _matches("/hel") == ["/help"]
