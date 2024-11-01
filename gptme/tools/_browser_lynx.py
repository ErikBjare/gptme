"""
Browser tool by calling lynx --dump
"""

import subprocess


def read_url(url, cookies: dict | None = None) -> str:
    # TODO: create and set LYNX_CFG to use custom lynx config file (needed to save cookies, which I need to debug how cookies should be read)
    if cookies:
        # save them to file to be read by lynx
        with open("cookies.txt", "w") as f:
            for k, v in cookies.items():
                f.write(f"{k}\t{v}\n")
    return subprocess.run(
        ["lynx", "--dump", url, "--display_charset=utf-8"], stdout=subprocess.PIPE
    ).stdout.decode("utf-8")


def search(query, engine="google"):
    if engine == "google":
        # TODO: needs a CONSENT cookie
        return read_url(f"https://www.google.com/search?q={query}")
    elif engine == "duckduckgo":
        return read_url(f"https://duckduckgo.com/?q={query}")
    raise ValueError(f"Unknown search engine: {engine}")


def test_read_url():
    print(read_url("https://gptme.org/"))
    print(read_url("https://github.com/ErikBjare/gptme/issues/205"))


def test_search():
    print(search("Python", "google"))
    print(search("Python", "duckduckgo"))
