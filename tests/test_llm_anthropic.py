from collections.abc import Iterable
from gptme.llm.llm_anthropic import (
    _handle_files,
    _handle_tools,
    _transform_system_messages,
)
from gptme.message import Message, msgs2dicts
from gptme.tools import init_tools


def test_message_conversion():
    messages = [
        Message(role="system", content="Initial Message", pinned=True, hide=True),
        Message(role="system", content="Project prompt", hide=True),
        Message(role="user", content="First user prompt"),
    ]

    messages, system_messages = _transform_system_messages(messages)

    assert system_messages == [{"text": "Initial Message", "type": "text"}]

    messages_dicts: Iterable[dict] = _handle_files(msgs2dicts(messages))

    assert messages_dicts == [
        {
            "content": [
                {
                    "text": "<system>Project prompt</system>\n\nFirst user prompt",
                    "type": "text",
                },
            ],
            "role": "user",
        },
    ]


def test_message_conversion_with_tool():
    init_tools(allowlist=["save"])

    messages = [
        Message(role="system", content="Initial Message", pinned=True, hide=True),
        Message(role="system", content="Project prompt", hide=True),
        Message(role="user", content="First user prompt"),
        Message(
            role="assistant",
            content='<thinking>\nSomething\n</thinking>\n@save(tool_call_id): {"path": "path.txt", "content": "file_content"}',
        ),
        Message(
            role="tool_result", content="Saved to toto.txt", call_id="tool_call_id"
        ),
    ]

    messages, _ = _transform_system_messages(messages)
    messages_dicts: Iterable[dict] = _handle_files(msgs2dicts(messages))
    messages_dicts = list(_handle_tools(messages_dicts))

    assert messages_dicts == [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "<system>Project prompt</system>\n\nFirst user prompt",
                },
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "<thinking>\nSomething\n</thinking>\n",
                },
                {
                    "type": "tool_use",
                    "id": "tool_call_id",
                    "name": "save",
                    "input": {"path": "path.txt", "content": "file_content"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "content": [
                        {
                            "type": "text",
                            "text": "Saved to toto.txt",
                        },
                    ],
                    "tool_use_id": "tool_call_id",
                },
            ],
        },
    ]
