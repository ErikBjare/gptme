from datetime import datetime

from gptme.util import (
    epoch_to_age,
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
