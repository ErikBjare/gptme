import logging
import os
import shutil
import sys

import openai
from rich import print

from .config import get_config
from .constants import PROMPT_ASSISTANT
from .message import Message
from .util import msgs2dicts

# Optimized for code
# Discussion here: https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api-a-few-tips-and-tricks-on-controlling-the-creativity-deterministic-output-of-prompt-responses/172683
# TODO: make these configurable
temperature = 0
top_p = 0.1

logger = logging.getLogger(__name__)


def init_llm(llm: str):
    # set up API_KEY (if openai) and API_BASE (if local)
    config = get_config()

    if llm == "openai":
        if "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"]
        elif api_key := config["env"].get("OPENAI_API_KEY", None):
            pass
        else:
            print("Error: OPENAI_API_KEY not set in env or config, see README.")
            sys.exit(1)
        openai.api_key = api_key
    elif llm in ["local", "llama"]:
        openai.api_base = "http://localhost:8000/v1"
    else:
        print(f"Error: Unknown LLM: {llm}")
        sys.exit(1)


def reply(messages: list[Message], model: str, stream: bool = False) -> Message:
    if stream:
        return _reply_stream(messages, model)
    else:
        print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
        response = _chat_complete(messages, model)
        print(" " * shutil.get_terminal_size().columns, end="\r")
        return Message("assistant", response)


def _chat_complete(messages: list[Message], model: str) -> str:
    # This will generate code and such, so we need appropriate temperature and top_p params
    # top_p controls diversity, temperature controls randomness
    response = openai.ChatCompletion.create(  # type: ignore
        model=model,
        messages=msgs2dicts(messages),
        temperature=temperature,
        top_p=top_p,
    )
    return response.choices[0].message.content


def _reply_stream(messages: list[Message], model: str) -> Message:
    print(f"{PROMPT_ASSISTANT}: Thinking...", end="\r")
    response = openai.ChatCompletion.create(  # type: ignore
        model=model,
        messages=msgs2dicts(messages),
        temperature=temperature,
        top_p=top_p,
        stream=True,
        # the llama-cpp-python server needs this explicitly set, otherwise unreliable results
        max_tokens=1000 if model not in ["gpt-3.5-turbo", "gpt-4"] else None,
    )

    def deltas_to_str(deltas: list[dict]):
        return "".join([d.get("content", "") for d in deltas])

    def print_clear():
        print(" " * shutil.get_terminal_size().columns, end="\r")

    deltas: list[dict] = []
    print_clear()
    print(f"{PROMPT_ASSISTANT}: ", end="")
    stop_reason = None
    try:
        for chunk in response:
            delta = chunk["choices"][0]["delta"]
            deltas.append(delta)
            delta_str = deltas_to_str(deltas)
            stop_reason = chunk["choices"][0]["finish_reason"]
            print(deltas_to_str([delta]), end="")
            # need to flush stdout to get the print to show up
            sys.stdout.flush()
            # pause inference on finished code-block, letting user run the command before continuing
            codeblock_started = "```" in delta_str[:-3]
            codeblock_finished = "```" in delta_str[-5:]
            if codeblock_started and codeblock_finished:
                # if closing a code block, wait for user to run command
                break
    except KeyboardInterrupt:
        return Message("assistant", deltas_to_str(deltas) + "... ^C Interrupted")
    finally:
        print_clear()
    logger.debug(f"Stop reason: {stop_reason}")
    return Message("assistant", deltas_to_str(deltas))
