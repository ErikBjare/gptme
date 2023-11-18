from datetime import datetime

from gptme.tools import get_codeblocks, is_supported_codeblock
from gptme.util import epoch_to_age, generate_name, is_generated_name


def test_generate_name():
    name = generate_name()
    assert is_generated_name(name)


def test_epoch_to_age():
    epoch_today = datetime.now().timestamp()
    assert epoch_to_age(epoch_today) == "just now"
    epoch_yesterday = epoch_today - 24 * 60 * 60
    assert epoch_to_age(epoch_yesterday) == "yesterday"


def test_is_supported_codeblock():
    block_plain = """```
some plaintext
```
"""
    # clean unsupported block
    assert not is_supported_codeblock(block_plain)

    block_python = """```python
print("hello world")
```
"""
    # clean supported block
    assert is_supported_codeblock(block_python)

    # has preamble
    s = f"""bla bla\n{block_python}"""
    assert is_supported_codeblock(s)

    # last block is plain/unsupported
    s = f"""{block_python}\n{block_plain}"""
    assert not is_supported_codeblock(s)


def test_get_codeblocks():
    s = """```python
print("hello world")
```
"""

    codeblocks = list(get_codeblocks(s))
    assert len(codeblocks) == 1
    assert (
        codeblocks[0]
        == """python
print("hello world")"""
    )

    # test a codeblock which contains triple backticks
    s = """```python
print("hello ``` world")
```
"""

    codeblocks = list(get_codeblocks(s))
    assert len(codeblocks) == 1
    assert (
        codeblocks[0]
        == """python
print("hello ``` world")"""
    )
