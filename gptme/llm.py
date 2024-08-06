import logging
import shutil
import sys
from typing import Generator, Iterator, Tuple

import openai
from anthropic import Anthropic
from openai import AzureOpenAI, OpenAI
from rich import print

from .config import config_path, get_config, set_config_value
from .constants import PROMPT_ASSISTANT
from .message import Message
from .models import MODELS
from .util import len_tokens, msgs2dicts

# Optimized for code
# Discussion here: https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api-a-few-tips-and-tricks-on-controlling-the-creativity-deterministic-output-of-prompt-responses/172683
# TODO: make these configurable
temperature = 0
top_p = 0.1

logger = logging.getLogger(__name__)

oai_client: OpenAI | None = None
anthropic_client: Anthropic | None = None


def init_llm(llm: str, interactive: bool):
    global oai_client, anthropic_client

    # set up API_KEY (if openai) and API_BASE (if local)
    config = get_config()

    # TODO: use llm/model from config if specified and not passed as args
    if llm == "openai":
        if api_key := config.get_env("OPENAI_API_KEY", None):
            pass
        elif interactive:
            api_key = ask_for_api_key()
            # recursively call init_llm to start over with init
            return init_llm(llm, interactive)
        else:
            print("Error: OPENAI_API_KEY not set in env or config, see README.")
            sys.exit(1)
        oai_client = OpenAI(api_key=api_key)
    elif llm == "azure":
        api_key = config.get_env_required("AZURE_OPENAI_API_KEY")
        azure_endpoint = config.get_env_required("AZURE_OPENAI_ENDPOINT")
        oai_client = AzureOpenAI(
            api_key=api_key,
            api_version="2023-07-01-preview",
            azure_endpoint=azure_endpoint,
        )

    elif llm == "anthropic":
        api_key = config.get_env_required("ANTHROPIC_API_KEY")
        anthropic_client = Anthropic(
            api_key=api_key,
        )

    elif llm == "local":
        api_base = config.get_env_required("OPENAI_API_BASE")
        oai_client = OpenAI(api_key="ollama", base_url=api_base)
    else:
        print(f"Error: Unknown LLM: {llm}")
        sys.exit(1)

    # ensure we have initialized the client
    assert oai_client or anthropic_client


def ask_for_api_key():
    """Interactively ask user for API key"""
    print("No API key set for OpenAI.")
    print("You can get one at https://platform.openai.com/account/api-keys\n")
    api_key = input("Your OpenAI API key: ").strip()

    # TODO: test API key
    # Save to config
    set_config_value("env.OPENAI_API_KEY", api_key)
    print(f"API key saved to config at {config_path}")
    return api_key


def reply(messages: list[Message], model: str, stream: bool = False) -> Message:
    if stream:
        return _reply_stream(messages, model)
    else:
        print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
        response = _chat_complete(messages, model)
        print(" " * shutil.get_terminal_size().columns, end="\r")
        print(f"{PROMPT_ASSISTANT}: {response}")
        return Message("assistant", response)


def _chat_complete_openai(messages: list[Message], model: str) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    assert oai_client, "LLM not initialized"
    response = oai_client.chat.completions.create(
        model=model,
        messages=msgs2dicts(messages),  # type: ignore
        temperature=temperature,
        top_p=top_p,
    )
    content = response.choices[0].message.content
    assert content
    return content


def _chat_complete_anthropic(messages: list[Message], model: str) -> str:
    assert anthropic_client, "LLM not initialized"
    messages, system_message = _transform_system_messages_anthropic(messages)
    response = anthropic_client.messages.create(
        model=model,
        messages=msgs2dicts(messages),  # type: ignore
        system=system_message,
        temperature=temperature,
        top_p=top_p,
        max_tokens=4096,
    )
    # TODO: rewrite handling of response to support anthropic API
    content = response.content
    assert content
    assert len(content) == 1
    return content[0].text  # type: ignore


def _chat_complete(messages: list[Message], model: str) -> str:
    if oai_client:
        return _chat_complete_openai(messages, model)
    elif anthropic_client:
        return _chat_complete_anthropic(messages, model)
    else:
        raise ValueError("LLM not initialized")


def _transform_system_messages_anthropic(
    messages: list[Message],
) -> Tuple[list[Message], str]:
    # transform system messages into system kwarg for anthropic
    # for first system message, transform it into a system kwarg
    assert messages[0].role == "system"
    system_prompt = messages[0].content
    messages.pop(0)

    # for any subsequent system messages, transform them into a <system> message
    for i, message in enumerate(messages):
        if message.role == "system":
            messages[i] = Message(
                "user",
                content=f"<system>{message.content}</system>",
            )

    # find consecutive user role messages and merge them into a single <system> message
    messages_new: list[Message] = []
    while messages:
        message = messages.pop(0)
        if messages_new and messages_new[-1].role == "user":
            messages_new[-1] = Message(
                "user",
                content=f"{messages_new[-1].content}\n{message.content}",
            )
        else:
            messages_new.append(message)
    messages = messages_new

    return messages, system_prompt


def _stream(messages: list[Message], model: str) -> Iterator[str]:
    if oai_client:
        return _stream_openai(messages, model)
    elif anthropic_client:
        return _stream_anthropic(messages, model)
    else:
        raise ValueError("LLM not initialized")


def _stream_openai(messages: list[Message], model: str) -> Generator[str, None, None]:
    assert oai_client, "LLM not initialized"
    stop_reason = None
    for chunk in oai_client.chat.completions.create(
        model=model,
        messages=msgs2dicts(messages),  # type: ignore
        temperature=temperature,
        top_p=top_p,
        stream=True,
        # the llama-cpp-python server needs this explicitly set, otherwise unreliable results
        max_tokens=1000 if not model.startswith("gpt-") else None,
    ):
        if not chunk.choices:  # type: ignore
            # Got a chunk with no choices, Azure always sends one of these at the start
            continue
        stop_reason = chunk.choices[0].finish_reason  # type: ignore
        yield chunk.choices[0].delta.content  # type: ignore
    logger.debug(f"Stop reason: {stop_reason}")


def _stream_anthropic(
    messages: list[Message], model: str
) -> Generator[str, None, None]:
    messages, system_prompt = _transform_system_messages_anthropic(messages)
    assert anthropic_client, "LLM not initialized"
    with anthropic_client.messages.stream(
        model=model,
        messages=msgs2dicts(messages),  # type: ignore
        system=system_prompt,
        temperature=temperature,
        top_p=top_p,
        max_tokens=4096,
    ) as stream:
        yield from stream.text_stream


def _reply_stream(messages: list[Message], model: str) -> Message:
    print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")

    def deltas_to_str(deltas: list[str]):
        return "".join([d or "" for d in deltas])

    def print_clear():
        print(" " * shutil.get_terminal_size().columns, end="\r")

    deltas: list[str] = []
    print_clear()
    print(f"{PROMPT_ASSISTANT}: ", end="")
    try:
        for delta in _stream(messages, model):
            if isinstance(delta, tuple):
                print("Got a tuple, expected str")
                continue
            if isinstance(delta, tuple):
                print("Got a Chunk, expected str")
                continue
            deltas.append(delta)
            delta_str = deltas_to_str(deltas)
            print(deltas_to_str([deltas[-1]]), end="")
            # need to flush stdout to get the print to show up
            sys.stdout.flush()

            # pause inference on finished code-block, letting user run the command before continuing
            codeblock_started = "```" in delta_str[:-3]
            codeblock_finished = "\n```\n" in delta_str[-7:]
            if codeblock_started and codeblock_finished:
                # noreorder
                from .tools import is_supported_codeblock  # fmt: skip

                # if closing a code block supported by tools, abort generation to let them run
                if is_supported_codeblock(delta_str):
                    print("\n")
                    break

            # pause inference in finished patch
            patch_started = "```patch" in delta_str[:-3]
            patch_finished = "\n>>>>>>> UPDATED" in delta_str[-30:]
            if patch_started and patch_finished:
                if "```" not in delta_str[-10:]:
                    print("\n```", end="")
                    deltas.append("\n```")
                print("\n")
                break
    except KeyboardInterrupt:
        return Message("assistant", deltas_to_str(deltas) + "... ^C Interrupted")
    finally:
        print_clear()
    return Message("assistant", deltas_to_str(deltas))


def summarize(content: str) -> str:
    """
    Summarizes a long text using a LLM.

    To summarize messages or the conversation log,
    use `gptme.tools.summarize` instead (which wraps this).
    """
    assert oai_client, "LLM not initialized"
    messages = [
        Message(
            "system",
            content="You are ChatGPT, a large language model by OpenAI. You summarize messages.",
        ),
        Message("user", content=f"Summarize this:\n{content}"),
    ]

    # model selection
    model = "gpt-3.5-turbo"
    if len_tokens(messages) > MODELS["openai"][model]["context"]:
        model = "gpt-3.5-turbo-16k"
    if len_tokens(messages) > MODELS["openai"][model]["context"]:
        raise ValueError(
            f"Cannot summarize more than 16385 tokens, got {len_tokens(messages)}"
        )

    try:
        response = oai_client.chat.completions.create(
            model=model,
            messages=msgs2dicts(messages),  # type: ignore
            temperature=0,
            max_tokens=256,
        )
    except openai.APIError:
        logger.error("OpenAI API error, returning empty summary: ", exc_info=True)
        return "error"
    summary = response.choices[0].message.content
    assert summary
    logger.debug(
        f"Summarized long output ({len_tokens(content)} -> {len_tokens(summary)} tokens): "
        + summary
    )
    return summary


def generate_name(msgs: list[Message]) -> str:
    """
    Generates a name for a given text/conversation using a LLM.
    """
    # filter out system messages
    msgs = [m for m in msgs if m.role != "system"]
    msgs = (
        [
            Message(
                "system",
                """
The following is a conversation between a user and an assistant. Which we will generate a name for.

The name should be 2-5 words describing the conversation, separated by dashes. Examples:
 - install-llama
 - implement-game-of-life
 - capitalize-words-in-python
""",
            )
        ]
        + msgs
        + [Message("user", "Now, generate a name for this conversation.")]
    )
    name = _chat_complete(msgs, model="gpt-3.5-turbo").strip()
    return name
