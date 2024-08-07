from gptme.prompts import get_prompt
from gptme.util import len_tokens


def test_get_prompt():
    prompt = get_prompt("full")
    assert len_tokens(prompt.content) < 2000

    prompt = get_prompt("short")
    assert len_tokens(prompt.content) < 800

    prompt = get_prompt("Hello world!")
    assert prompt.content == "Hello world!"
