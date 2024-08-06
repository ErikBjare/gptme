from gptme.tools.patch import apply

example_patch = """
```patch filename.py
<<<<<<< ORIGINAL
original lines
=======
modified lines
>>>>>>> UPDATED
```
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
```patch test.py
<<<<<<< ORIGINAL
def hello():
    print("hello")
=======
def hello(name="world"):
    print(f"hello {name}")
>>>>>>> UPDATED
```
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
```patch test.py
<<<<<<< ORIGINAL
def hello():
    print("hello")
=======

>>>>>>> UPDATED
```
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
```patch test.py
<<<<<<< ORIGINAL

=======


>>>>>>> UPDATED
```
"""
    result = apply(codeblock, content)
    assert "\n\n\n" in result
