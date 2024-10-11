from gptme.tools.patch import Patch, apply

example_patch = """
<<<<<<< ORIGINAL
original lines
=======
modified lines
>>>>>>> UPDATED
"""


def test_apply_simple():
    codeblock = example_patch
    content = """original lines"""
    result = apply(codeblock, content)
    assert result == """modified lines"""


def test_apply_function():
    content = """
def hello():
    print("hello")

if __name__ == "__main__":
    hello()
"""

    codeblock = """
<<<<<<< ORIGINAL
def hello():
    print("hello")
=======
def hello(name="world"):
    print(f"hello {name}")
>>>>>>> UPDATED
"""

    result = apply(codeblock, content)
    assert result.startswith(
        """
def hello(name="world"):
    print(f"hello {name}")
"""
    )


def test_clear_file():
    # only remove code in patch
    content = """
def hello():
    print("hello")

if __name__ == "__main__":
    hello()
"""

    # NOTE: test fails if UPDATED block doesn't have an empty line
    codeblock = """
<<<<<<< ORIGINAL
def hello():
    print("hello")
=======

>>>>>>> UPDATED
"""
    print(content)
    result = apply(codeblock, content)
    newline = "\n"
    newline_escape = "\\n"
    assert result.startswith(
        "\n\n"
    ), f"result: {result.replace(newline, newline_escape)}"


def test_apply_empty_lines():
    # a test where it replaces a empty line with 3 empty lines
    # checks that whitespace is preserved
    content = """
def hello():
    print("hello")

if __name__ == "__main__":
    hello()
"""
    codeblock = """
<<<<<<< ORIGINAL



=======




>>>>>>> UPDATED
"""
    result = apply(codeblock, content)
    assert "\n\n\n" in result


def test_apply_multiple():
    # tests multiple patches in a single codeblock, with placeholders in patches
    # checks that whitespace is preserved
    content = """
def hello():
    print("hello")

if __name__ == "__main__":
    hello()
"""
    codeblock = """
<<<<<<< ORIGINAL
def hello():
=======
def hello_world():
>>>>>>> UPDATED

<<<<<<< ORIGINAL
    hello()
=======
    hello_world()
>>>>>>> UPDATED
"""
    result = apply(codeblock, content)
    assert "    hello_world()" in result


def test_apply_with_placeholders():
    # tests multiple patches in a single codeblock, with placeholders in patches
    # checks that whitespace is preserved
    content = """
def hello():
    print("hello")
"""
    codeblock = """
<<<<<<< ORIGINAL
def hello():
    # ...
=======
def hello_world():
    # ...
>>>>>>> UPDATED
"""
    result = apply(codeblock, content)
    assert "hello_world()" in result


def test_patch_minimal():
    p = Patch(
        """1
2
3
""",
        """1
0
3
""",
    )
    assert (
        p.diff_minimal()
        == """ 1
-2
+0
 3"""
    )
    assert p.diff_minimal(strip_context=True) == "-2\n+0"
