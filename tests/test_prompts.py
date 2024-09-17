from gptme.message import len_tokens
from gptme.prompts import get_prompt


def test_get_prompt():
    prompt = get_prompt("full")
    # TODO: lower this significantly by selectively removing examples from the full prompt
    assert 500 < len_tokens(prompt.content) < 5000

    prompt = get_prompt("short")
    assert 500 < len_tokens(prompt.content) < 2000

    prompt = get_prompt("Hello world!")
    assert prompt.content == "Hello world!"
