from gptme.prompts import get_prompt
from gptme.message import len_tokens


def test_get_prompt():
    prompt = get_prompt("full")
    assert 1200 < len_tokens(prompt.content) < 2000

    prompt = get_prompt("short")
    assert 700 < len_tokens(prompt.content) < 900

    prompt = get_prompt("Hello world!")
    assert prompt.content == "Hello world!"
