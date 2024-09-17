import logging
import os
import subprocess
from collections.abc import Generator, Iterable
from typing import Literal

from .config import get_config
from .message import Message
from .tools import init_tools, loaded_tools

PromptType = Literal["full", "short"]


def get_prompt(prompt: PromptType | str = "full", interactive: bool = True) -> Message:
    """Get the initial system prompt."""
    msgs: Iterable
    if prompt == "full":
        msgs = prompt_full(interactive)
    elif prompt == "short":
        msgs = prompt_short(interactive)
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


def prompt_full(interactive: bool) -> Generator[Message, None, None]:
    """Full prompt to start the conversation."""
    yield from prompt_gptme(interactive)
    yield from prompt_tools()
    yield from prompt_user()
    yield from prompt_project()


def prompt_short(interactive: bool) -> Generator[Message, None, None]:
    """Short prompt to start the conversation."""
    yield from prompt_gptme(interactive)
    yield from prompt_tools(examples=False)
    yield from prompt_user()
    yield from prompt_project()


def prompt_gptme(interactive: bool) -> Generator[Message, None, None]:
    base_prompt = """
You are gptme, a general-purpose AI assistant powered by LLMs.
You are designed to help users with programming tasks, such as writing code, debugging, and learning new concepts.
You can run code, execute terminal commands, and access the filesystem on the local machine.
You will help the user with writing code, either from scratch or in existing projects.

You should learn about the context needed to provide the best help, such as exploring a potential project in the current working directory and reading the code.
Think step by step when solving a problem.

Do not use placeholders like `$REPO` unless they have been set.
When the output of a command is of interest, end the code block so that it can be executed before continuing.

Do not suggest opening a browser or editor, instead do it using available tools, such as the shell or with Python.
""".strip()

    interactive_prompt = """
You are in interactive mode. The user is available to provide feedback.
You should show the user how you can use your tools to write code, interact with the terminal, and access the internet.
The user can execute the suggested commands so that you see their output.
If clarification is needed, ask the user.
""".strip()

    non_interactive_prompt = """
You are in non-interactive mode. The user is not available to provide feedback.
All code blocks you suggest will be automatically executed.
Do not provide examples or ask for permission before running commands.
Proceed directly with the most appropriate actions to complete the task.
""".strip()

    full_prompt = (
        base_prompt
        + "\n\n"
        + (interactive_prompt if interactive else non_interactive_prompt)
    )
    yield Message("system", full_prompt)


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
