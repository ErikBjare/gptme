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
    assert log.get_last_code_block(content=True) == "print('world')"


def test_branch():
    log = LogManager()

    # add message to main branch
    log.append(Message("assistant", "hello"))
    assert log.log[-1].content == "hello"

    # switch branch
    log.branch("dev")
    log.append(Message("assistant", "world"))
    assert log.log[-2].content == "hello"
    assert log.log[-1].content == "world"
    assert log.diff("main") == "+ Assistant: world"

    # switch back
    log.branch("main")
    assert log.log[-1].content == "hello"

    # check diff
    assert log.diff("dev") == "- Assistant: world"

    # undo and check no diff
    log.undo()
    assert log.diff("dev") == "- Assistant: hello\n- Assistant: world"
