from gptme.tools.shell import _shorten_stdout


def test_shorten_stdout_timestamp():
    s = """2021-09-02T08:48:43.123Z
2021-09-02T08:48:43.123Z
"""
    assert _shorten_stdout(s) == "\n\n"


def test_shorten_stdout_common_prefix():
    s = """foo 1
foo 2
foo 3
foo 4
foo 5"""
    assert _shorten_stdout(s) == "1\n2\n3\n4\n5"


def test_shorten_stdout_indent():
    # check that indentation is preserved
    s = """
l1 without indent
    l2 with indent
""".strip()
    assert _shorten_stdout(s) == s


def test_shorten_stdout_blanklines():
    s = """l1

l2"""
    assert _shorten_stdout(s) == s
