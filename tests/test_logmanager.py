from gptme.logmanager import LogManager, Message


def test_branch():
    log = LogManager()

    # add message to main branch
    log.append(Message("assistant", "hello"))
    assert log.log[-1].content == "hello"

    # switch branch
    log.branch("dev")
    log.append(Message("assistant", "world"))
    assert log.log[-1].content == "world"
    assert log.log[-2].content == "hello"
    assert log.diff("main") == "+ Assistant: world"

    # switch back
    log.branch("main")
    assert log.log[-1].content == "hello"

    # check diff
    assert log.diff("dev") == "- Assistant: world"

    # undo and check no diff
    log.undo()
    assert log.diff("dev") == "- Assistant: hello\n- Assistant: world"

    d = log.to_dict(branches=True)
    assert "main" in d["branches"]
    assert "dev" in d["branches"]
