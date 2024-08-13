from datetime import datetime

from gptme.util import (
    epoch_to_age,
    extract_codeblocks,
    generate_name,
    is_generated_name,
    transform_examples_to_chat_directives,
)


def test_generate_name():
    name = generate_name()
    assert is_generated_name(name)


def test_epoch_to_age():
    epoch_today = datetime.now().timestamp()
    assert epoch_to_age(epoch_today) == "just now"
    epoch_yesterday = epoch_today - 24 * 60 * 60
    assert epoch_to_age(epoch_yesterday) == "yesterday"


def test_transform_examples_to_chat_directives():
    src = """
# Example
> User: Hello
> Bot: Hi
"""
    expected = """
Example

.. chat::

   User: Hello
   Bot: Hi
"""

    assert transform_examples_to_chat_directives(src, strict=True) == expected


def test_transform_examples_to_chat_directives_tricky():
    src = """
> User: hello
> Assistant: lol
> Assistant: lol
> Assistant: lol
""".strip()

    expected = """

.. chat::

   User: hello
   Assistant: lol
   Assistant: lol
   Assistant: lol"""

    assert transform_examples_to_chat_directives(src, strict=True) == expected


def test_extract_codeblocks_basic():
    markdown = """
Some text
```python
def hello():
    print("Hello, World!")
```
More text
"""
    assert extract_codeblocks(markdown) == [
        ("python", 'def hello():\n    print("Hello, World!")')
    ]


def test_extract_codeblocks_multiple():
    markdown = """
```java
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, Java!");
    }
}
```
Some text
```python
def greet(name):
    return f"Hello, {name}!"
```
"""
    assert extract_codeblocks(markdown) == [
        (
            "java",
            'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, Java!");\n    }\n}',
        ),
        ("python", 'def greet(name):\n    return f"Hello, {name}!"'),
    ]


def test_extract_codeblocks_nested():
    markdown = """
```python
def print_readme():
    print('''Usage:
```javascript
callme()
```
''')
```
"""
    assert extract_codeblocks(markdown) == [
        (
            "python",
            "def print_readme():\n    print('''Usage:\n```javascript\ncallme()\n```\n''')",
        )
    ]


def test_extract_codeblocks_empty():
    assert extract_codeblocks("") == []


def test_extract_codeblocks_text_only():
    assert extract_codeblocks("Just some regular text\nwithout any code blocks.") == []


def test_extract_codeblocks_no_language():
    markdown = """
```
def hello():
    print("Hello, World!")
```
"""
    assert extract_codeblocks(markdown) == [
        ("", 'def hello():\n    print("Hello, World!")')
    ]
