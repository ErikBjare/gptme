from gptme.tools import is_supported_codeblock


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
    s = f"""bla bla\n{block_python}\nbla bla{block_plain}"""
    assert not is_supported_codeblock(s)
