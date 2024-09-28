from gptme.tools.chats import list_chats, search_chats


def test_chats(capsys):
    list_chats()
    captured = capsys.readouterr()
    if "No conversations found" in captured.out:
        search_chats("python", system=True)
        captured = capsys.readouterr()
        assert "No results found" in captured.out
    else:
        assert "1." in captured.out
        search_chats("python", system=True)
        captured = capsys.readouterr()
        assert "Found matches" in captured.out
