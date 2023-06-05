"""
GPTMe
=====

This is a long-living AI language model called GPTMe, it is designed to be a helpful companion.

It should be able to help the user in various ways, such as:

 - Writing code
 - Using the shell
 - Assisting with technical tasks
 - Writing prose (such as email, code docs, etc.)
 - Acting as an executive assistant

The agent should be able to learn from the user and adapt to their needs.
The agent should always output information using GitHub Flavored Markdown.
THe agent should always output code and commands in markdown code blocks with the appropriate language tag.

Since the agent is long-living, it should be able to remember things that the user has told it,
to do so, it needs to be able to store and query past conversations in a database.
"""
# The above docstring is the first message that the agent will see.

from typing import Literal, Generator
from datetime import datetime
import logging
import os
import sys
import shutil
import readline  # noqa: F401
import itertools
from pathlib import Path

from termcolor import colored  # type: ignore
import openai
import click


from .constants import role_color
from .tools import (
    _execute_linecmd,
    _execute_codeblock,
    _execute_save,
    _execute_shell,
    _execute_python,
)
from .util import msgs2dicts
from .message import Message
from .logmanager import LogManager
from .prompts import initial_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


LLMChoice = Literal["openai", "llama"]

readline.add_history("What is love?")
readline.add_history("Have you heard about an open-source app called ActivityWatch?")
readline.add_history(
    "Explain the 'Attention is All You Need' paper in the style of Andrej Karpathy."
)


def get_logfile(logdir: str) -> str:
    logdir = logdir + "/"
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir + datetime.now().strftime("%Y-%m-%d") + ".log"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def execute_msg(msg: Message) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    for line in msg.content.splitlines():
        yield from _execute_linecmd(line)

    # get all markdown code blocks
    # we support blocks beginning with ```python and ```bash
    codeblocks = [codeblock for codeblock in msg.content.split("```")[1::2]]
    for codeblock in codeblocks:
        yield from _execute_codeblock(codeblock)

    yield from _execute_save(msg.content)


Actions = Literal["continue", "summarize", "load", "shell", "exit", "help", "undo"]

action_descriptions: dict[Actions, str] = {
    "continue": "Continue",
    "undo": "Undo the last action",
    "summarize": "Summarize the conversation so far",
    "load": "Load a file",
    "shell": "Execute a shell command",
    "exit": "Exit the program",
    "help": "Show this help message",
}


def handle_cmd(cmd: str, logmanager: LogManager) -> Generator[Message, None, None]:
    """Handles a command."""
    cmd = cmd.lstrip(".")
    name, *args = cmd.split(" ")
    match name:
        case "bash" | "sh" | "shell":
            yield from _execute_shell(" ".join(args))
        case "python" | "py":
            yield from _execute_python(" ".join(args))
        case "continue":
            raise NotImplementedError
        case "summarize":
            raise NotImplementedError
        case "undo":
            logmanager.undo()
        case "load":
            filename = args[0] if args else input("Filename: ")
            with open(filename) as f:
                contents = f.read()
            yield Message("system", f"# filename: {filename}\n\n{contents}")
        case "exit":
            sys.exit(0)
        case _:
            print("Available commands:")
            for cmd, desc in action_descriptions.items():
                print(f"  {cmd}: {desc}")


@click.group()
def cli():
    pass


script_path = Path(os.path.realpath(__file__))


@cli.command()
@click.argument("command", default=None, required=False)
@click.option(
    "--logs",
    default=script_path.parent.parent / "logs",
    help="Folder where conversation logs are stored",
)
@click.option("--llm", default="openai", help="LLM to use")
@click.option(
    "--stream",
    is_flag=True,
    default=True,
    help="Wether to use streaming (only supported for openai atm)",
)
@click.option(
    "--prompt",
    default="short",
    help="Can be 'short', 'full', or a custom prompt",
)
def main(command: str | None, logs: str, llm: LLMChoice, stream: bool, prompt: str):
    """
    GPTMe, a CLI interface for LLMs.
    """
    openai.api_key = os.environ["OPENAI_API_KEY"]
    openai.api_base = "http://localhost:8000/v1"

    if prompt in ["full", "short"]:
        promptmsgs = initial_prompt(short=prompt == "short")
    else:
        promptmsgs = [Message("system", prompt)]

    print(f"Using logdir {logs}")
    logfile = get_logfile(logs)
    logmanager = LogManager.load(logfile, initial_msgs=promptmsgs)
    logmanager.print()
    print("--- ^^^ past messages ^^^ ---")

    log = logmanager.log

    # if last message was from assistant, try to run tools again
    if log[-1].role == "assistant":
        for m in execute_msg(log[-1]):
            logmanager.append(m)

    command_triggered = False

    while True:
        # if non-interactive command given on cli, exit
        if command_triggered:
            print("Command triggered, exiting")
            break

        # If last message was a response, ask for input.
        # If last message was from the user (such as from crash/edited log),
        # then skip asking for input and generate response
        last_msg = log[-1] if log else None
        if not last_msg or (
            (last_msg.role in ["system", "assistant"])
            or (log[-1].role == "user" and log[-1].content.startswith("."))
        ):
            inquiry = prompt_user(command)
            if command:
                command = None
                command_triggered = True

            if not inquiry:
                print("Continue 1 (rare!)")
                continue
            logmanager.append(Message("user", inquiry))

        assert log[-1].role == "user"
        inquiry = log[-1].content
        # if message starts with ., treat as command
        # when command has been run,
        if inquiry.startswith("."):
            for msg in handle_cmd(inquiry, logmanager):
                logmanager.append(msg)
            if command:
                command_triggered = True
                print("Continue 2")
            continue

        # if large context, try to reduce/summarize
        # print response
        try:
            msg_response = reply(logmanager.prepare_messages(), stream)

            # log response and run tools
            if msg_response:
                for msg in itertools.chain([msg_response], execute_msg(msg_response)):
                    logmanager.append(msg)
        except KeyboardInterrupt:
            print("Interrupted")


def prompt_user(value=None) -> str:
    return prompt_input(colored("User", role_color["user"]) + ": ", value)


def prompt_input(prompt: str, value=None) -> str:
    if value:
        print(prompt + value)
    else:
        value = input(prompt)
    return value


def reply(messages: list[Message], stream: bool = False) -> Message:
    if stream:
        return reply_stream(messages)
    else:
        prefix = colored("Assistant", "green", attrs=["bold"])
        print(f"{prefix}: Thinking...", end="\r")
        response = _chat_complete(messages)
        print(" " * shutil.get_terminal_size().columns, end="\r")
        return Message("assistant", response)


def _chat_complete(messages: list[Message]) -> str:
    response = openai.ChatCompletion.create(  # type: ignore
        model="gpt-3.5-turbo",
        messages=msgs2dicts(messages),
        temperature=0,
    )
    return response.choices[0].message.content


def reply_stream(messages: list[Message]) -> Message:
    prefix = colored("Assistant", "green", attrs=["bold"])
    print(f"{prefix}: Thinking...", end="\r")
    response = openai.ChatCompletion.create(  # type: ignore
        model="gpt-3.5-turbo",
        messages=msgs2dicts(messages),
        temperature=0,
        stream=True,
        max_tokens=1000,
    )

    def deltas_to_str(deltas: list[dict]):
        return "".join([d.get("content", "") for d in deltas])

    def print_clear():
        print(" " * shutil.get_terminal_size().columns, end="\r")

    deltas: list[dict] = []
    print_clear()
    print(f"{prefix}: ", end="")
    stop_reason = None
    for chunk in response:
        delta = chunk["choices"][0]["delta"]
        deltas.append(delta)
        stop_reason = chunk["choices"][0]["finish_reason"]
        print(deltas_to_str([delta]), end="")
        # need to flush stdout to get the print to show up
        sys.stdout.flush()
    print_clear()
    verbose = True
    if verbose:
        print(f" - Stop reason: {stop_reason}")
    return Message("assistant", deltas_to_str(deltas))


if __name__ == "__main__":
    main()
