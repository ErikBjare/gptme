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
