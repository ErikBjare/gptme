from gptme.logmanager import LogManager, Message


def test_get_last_code_block():
    # tests that the last code block is indeed returned, with the correct formatting
    log = LogManager()
    log.append(
        Message(
            "assistant",
            """
```python
print('hello')
```

```python
print('world')
```
""",
        )
    )
    assert log.get_last_code_block(content=True) == "print('world')\n"
