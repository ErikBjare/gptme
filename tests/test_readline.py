import os
import sys
from pathlib import Path

from gptme.readline import _matches

project_root = Path(__file__).parent.parent


def test_matches():
    # make sure we are in the right directory
    os.chdir(project_root)
    print(os.getcwd())

    # dirs
    assert ".git/" in _matches("")
    assert _matches(".githu") == [".github/"]
    assert _matches(".github") == [".github/"]
    assert set(_matches(".github/")) == {
        ".github/workflows/",
        ".github/actions/",
        ".github/codecov.yml",
    }

    # files
    assert _matches("README") == ["README.md"]
    assert _matches("./README") == ["README.md"]
    assert _matches("../gptme/README") == ["../gptme/README.md"]
    if sys.platform != "win32":
        assert "/etc/passwd" in _matches("/etc/pass")

    # commands
    assert _matches("/hel") == ["/help"]
