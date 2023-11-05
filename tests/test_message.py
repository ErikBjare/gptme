from gptme.message import (
    Message,
    msg_to_toml,
    msgs_to_toml,
    toml_to_msg,
    toml_to_msgs,
)


def test_toml():
    msg = Message(
        "system",
        '''Hello world!
"""Difficult to handle string"""
''',
    )
    t = msg_to_toml(msg)
    print(t)
    m = toml_to_msg(t)
    print(m)
    assert msg.content == m.content
    assert msg.role == m.role
    assert msg.timestamp.date() == m.timestamp.date()
    assert msg.timestamp.timetuple() == m.timestamp.timetuple()

    msg2 = Message("user", "Hello computer!")
    ts = msgs_to_toml([msg, msg2])
    print(ts)
    ms = toml_to_msgs(ts)
    print(ms)
    assert len(ms) == 2
    assert ms[0].role == msg.role
    assert ms[0].timestamp.timetuple() == msg.timestamp.timetuple()
    assert ms[0].content == msg.content
    assert ms[1].content == msg2.content


def test_get_codeblocks():
    # single codeblock only
    msg = Message(
        "system",
        """```python
def test():
    print("Hello world!")
```""",
    )
    codeblocks = msg.get_codeblocks()
    assert len(codeblocks) == 1

    # multiple codeblocks and leading/trailing text
    msg = Message(
        "system",
        """Hello world!
```bash
echo "Hello world!"
```
```python
print("Hello world!")
```
That's all folks!
""",
    )
    codeblocks = msg.get_codeblocks()
    assert len(codeblocks) == 2
