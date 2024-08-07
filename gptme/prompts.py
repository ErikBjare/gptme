import logging
import os
import subprocess
from collections.abc import Generator, Iterable
from typing import Literal

from .config import get_config
from .message import Message
from .tools import init_tools, loaded_tools

PromptType = Literal["full", "short"]


def get_prompt(prompt: PromptType | str = "full") -> Message:
    """Get the initial system prompt."""
    msgs: Iterable
    if prompt == "full":
        msgs = prompt_full()
    elif prompt == "short":
        msgs = prompt_short()
    else:
        msgs = [Message("system", prompt)]

    # combine all the system prompt messages into one,
    # also hide them and pin them to the top
    msg = join_messages(msgs)
    msg.hide = True
    msg.pinned = True
    return msg


def join_messages(msgs: Iterable[Message]) -> Message:
    return Message("system", "\n\n".join(m.content for m in msgs))


def prompt_full() -> Generator[Message, None, None]:
    """Full prompt to start the conversation."""
    yield from prompt_gptme()
    yield from prompt_tools()
    yield from prompt_user()
    yield from prompt_project()


def prompt_short() -> Generator[Message, None, None]:
    """Short prompt to start the conversation."""
    yield from prompt_gptme()
    yield from prompt_tools(examples=False)
    yield from prompt_user()
    yield from prompt_project()


def prompt_gptme() -> Generator[Message, None, None]:
    yield Message(
        "system",
        """
You are gptme, an AI assistant CLI tool powered by large language models.
You can run code and execute terminal commands on their local machine.
You should show the user how to write code, interact with the system, and access the internet.
The user can execute the suggested commands so that you see their output.
All code should be copy-pasteable or saved, and runnable as-is. Do not use placeholders like `$REPO` unless they have been set.
When the output of a command is of interest, end the code block so that the user can execute it before continuing.

Do not suggest the user open a browser or editor, instead show them how to do it in the shell or Python REPL.
If clarification is needed, ask the user.
""".strip(),
    )


def prompt_user() -> Generator[Message, None, None]:
    config_prompt = get_config().prompt
    if about_user := config_prompt.get("about_user", None):
        response_preference = config_prompt.get("response_preference", None)
        yield Message(
            "system",
            f"""# About user\n\n{about_user}"""
            + (
                f"\n\n## Here is the user's response preferences:\n\n{response_preference}"
                if response_preference
                else ""
            ),
        )
    else:
        logging.warning("No about_user in config.yaml")


def prompt_project() -> Generator[Message, None, None]:
    config_prompt = get_config().prompt
    # detect from git root folder name
    projectdir = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    ).stdout.strip()
    project = os.path.basename(projectdir)
    config_projects = config_prompt.get("project", {})
    if project in config_projects:
        project_prompt = config_projects[project]
        yield Message(
            "system",
            f"Here is information about the current project {project}: {project_prompt}",
        )


def prompt_tools(examples=True) -> Generator[Message, None, None]:
    init_tools()
    assert loaded_tools, "No tools loaded"
    prompt = "# Tools"
    for tool in loaded_tools:
        prompt += f"\n\n## {tool.name}"
        if tool.desc:
            prompt += f"\n\n{tool.desc}"
        if tool.instructions:
            prompt += f"\n\n{tool.instructions}"
        if tool.examples and examples:
            prompt += f"\n\n### Examples\n\n{tool.examples}"

    yield Message("system", prompt.strip() + "\n\n")
