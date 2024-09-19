from gptme.tools.patch import apply, apply_unified_diff, is_unified_diff

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


def test_is_unified_diff():
    unified_diff = """
@@ -1,3 +1,3 @@
 def hello():
-    print("hello")
+    print("hello world")
"""
    assert is_unified_diff(unified_diff)
    assert not is_unified_diff(example_patch)


def test_apply_unified_diff_simple():
    content = 'def hello():\n    print("hello")\n'
    unified_diff = """
@@ -1,2 +1,2 @@
 def hello():
-    print("hello")
+    print("hello world")
"""
    result = apply_unified_diff(unified_diff, content)
    assert 'print("hello world")' in result


def test_apply_unified_diff_multiple_hunks():
    content = (
        'def hello():\n    print("hello")\n\ndef goodbye():\n    print("goodbye")\n'
    )
    unified_diff = """
@@ -1,2 +1,2 @@
 def hello():
-    print("hello")
+    print("hello world")
@@ -4,2 +4,2 @@
 def goodbye():
-    print("goodbye")
+    print("farewell")
"""
    result = apply_unified_diff(unified_diff, content)
    assert 'print("hello world")' in result
    assert 'print("farewell")' in result


def test_apply_unified_diff_add_lines():
    content = """
def hello():
    print("hello")
"""
    unified_diff = """
@@ -1,2 +1,4 @@
 def hello():
     print("hello")
+    print("world")
+    return None
"""
    result = apply_unified_diff(unified_diff, content)
    assert 'print("world")' in result
    assert "return None" in result


def test_apply_unified_diff_remove_lines():
    content = 'def hello():\n    print("hello")\n    print("world")\n    return None\n'
    unified_diff = """
@@ -1,4 +1,2 @@
 def hello():
     print("hello")
-    print("world")
-    return None
"""
    result = apply_unified_diff(unified_diff, content)
    assert 'print("world")' not in result
    assert "return None" not in result
