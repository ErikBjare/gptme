from gptme.tools.chats import list_chats, search_chats


def test_list_chats(capsys):
    list_chats()
    captured = capsys.readouterr()
    assert "1." in captured.out


def test_search_chats(capsys):
    search_chats("python")
    captured = capsys.readouterr()
    assert "Found matches" in captured.out
