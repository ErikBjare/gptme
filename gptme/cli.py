"""
This is a long-living agent that is designed to be a companion to the user.

It should be able to help the user in various ways, such as:

 - Acting as an executive assistant
 - Answering questions
 - Helping strategize
 - Giving advice
 - Writing code
 - Writing prose (such as email, code docs, etc.)
 - Providing companionship

The agent should be able to learn from the user and adapt to their needs.
The agent should try to always output information using markdown formatting, preferably using GitHub Flavored Markdown.

Since the agent is long-living, it should be able to remember things that the user has told it,
to do so, it needs to be able to store and query past conversations in a database.
"""

from typing import Literal, Generator
from datetime import datetime
import logging
import os
import sys
import shutil
import itertools
from pathlib import Path

from termcolor import colored
import openai
import click

import typing

from .constants import role_color
from .tools import _execute_linecmd, _execute_codeblock, _execute_save, _execute_shell, _execute_python
from .util import msgs2dicts
from .message import Message
from .logmanager import LogManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
            for cmd in typing.get_args(Actions):
                desc = action_descriptions.get(cmd, default="missing description")
                print(f"  {cmd}: {desc}")


@click.group()
def cli():
    pass

script_path = Path(os.path.realpath(__file__))

@cli.command()
@click.argument("command" , default=None, required=False)
@click.option(
    "--logs", default=script_path.parent.parent / "logs", help="Folder where conversation logs are stored"
)
def main(command: str | None, logs: str):
    """Main interactivity loop."""
    openai.api_key = os.environ["OPENAI_API_KEY"]

    logfile = get_logfile(logs)
    logmanager = LogManager.load(logfile)
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
            break

        # If last message was a response, ask for input.
        # If last message was from the user (such as from crash/edited log), 
        # then skip asking for input and generate response
        if log[-1].role in ["system", "assistant"]:
            prompt = colored("User", role_color["user"]) + ": "
            if command:
                print(prompt + command)
                inquiry = command
                command = None
                command_triggered = True
            else:
                inquiry = input(prompt)
    
            if not inquiry:
                continue
            logmanager.append(Message("user", inquiry))

        assert log[-1].role == "user"
        inquiry = log[-1].content
        # if message starts with ., treat as command
        # when command has been run, 
        if inquiry.startswith("."):
            for msg in handle_cmd(inquiry, logmanager):
                logmanager.append(msg)
            continue

        # if large context, try to reduce/summarize
        # print response
        msg_response = reply(logmanager.prepare_messages())

        # log response and run tools
        for msg in itertools.chain([msg_response], execute_msg(msg_response)):
            logmanager.append(msg)


def reply(messages: list[Message]) -> Message:
    # print in-progress indicator
    print(colored("Assistant", "green", attrs=["bold"]) + ": Thinking...", end="\r")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=msgs2dicts(messages),
        temperature=0,
    )
    print(" " * shutil.get_terminal_size().columns, end="\r")
    return Message("assistant", response.choices[0].message.content)


if __name__ == "__main__":
    main()
