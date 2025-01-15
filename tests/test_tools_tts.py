from gptme.tools.tts import re_thinking, re_tool_use, split_text


def test_split_text_single_sentence():
    assert split_text("Hello, world!") == ["Hello, world!"]


def test_split_text_multiple_sentences():
    assert split_text("Hello, world! I'm Bob") == ["Hello, world!", "I'm Bob"]


def test_split_text_decimals():
    # Don't split on periods in numbers with decimals
    # Note: For TTS purposes, having a period at the end is acceptable
    result = split_text("0.5x")
    assert result == ["0.5x"]


def test_split_text_numbers_before_punctuation():
    assert split_text("The dog was 12. The cat was 3.") == [
        "The dog was 12.",
        "The cat was 3.",
    ]


def test_split_text_paragraphs():
    assert split_text(
        """
Text without punctuation

Another paragraph
"""
    ) == ["Text without punctuation", "", "Another paragraph"]


def test_split_text_lists():
    assert split_text(
        """
- Test
- Test2
"""
    ) == ["- Test", "- Test2"]

    # Markdown list (numbered)
    # Also tests punctuation in list items, which shouldn't cause extra pauses (unlike paragraphs)
    assert split_text(
        """
1. Test.
2. Test2
"""
    ) == ["1. Test.", "2. Test2"]

    # We can strip trailing punctuation from list items
    assert [
        part.strip()
        for part in split_text(
            """
1. Test.
2. Test2.
"""
        )
    ] == ["1. Test", "2. Test2"]

    # Replace asterisk lists with dashes
    assert split_text(
        """
* Test
* Test2
"""
    ) == ["- Test", "- Test2"]


def test_clean_for_speech():
    # test underlying regexes

    # complete
    assert re_thinking.search("<thinking>thinking</thinking>")
    assert re_tool_use.search("```tool\ncontents\n```")

    # with arg
    assert re_tool_use.search("```save test.txt\ncontents\n```")

    # incomplete
    assert re_thinking.search("\n<thinking>thinking")
    assert re_tool_use.search("```savefile.txt\ncontents")
