#!/usr/bin/env python

import re
import sys

re_str = r"<details>\s*<summary>(.*?)<\/summary>(.*?)<\/details>"
r = re.compile(re_str, re.DOTALL | re.IGNORECASE | re.MULTILINE)


def shorten_long_details(details: str, limit: int):
    def shorten_block(match):
        summary = match.group(1)
        content = match.group(2)
        if len(content) <= limit:
            return match.group(0)
        return f"<details><summary>{summary}</summary>{content[:limit]}...</details>"

    return r.sub(shorten_block, details)


def test_shorten_long_details():
    details = """<details><summary>Summary</summary>This is a long text that should be shortened.</details>"""
    assert (
        shorten_long_details(details, limit=31)
        == """<details><summary>Summary</summary>This is a long text that should...</details>"""
    )


def test_shorten_long_details_multiple():
    details = """
<details><summary>Summary</summary>This is a short text.</details>
<details><summary>Summary</summary>This is a long text that should be shortened.</details>
"""
    assert (
        shorten_long_details(details, limit=31)
        == """
<details><summary>Summary</summary>This is a short text.</details>
<details><summary>Summary</summary>This is a long text that should...</details>
"""
    )


if __name__ == "__main__":
    details = sys.stdin.read()
    try:
        limit = int(sys.argv[1])
    except (ValueError, IndexError):
        print(f"Usage: {sys.argv[0]} [limit]")
        sys.exit(1)
    print(shorten_long_details(details, limit))
