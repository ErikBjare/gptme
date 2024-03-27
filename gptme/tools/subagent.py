"""
A subagent tool for gptme

Lets gptme break down a task into smaller parts, and delegate them to subagents.
"""

import json
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

from ..message import Message
from .base import ToolSpec
from .python import register_function

if TYPE_CHECKING:
    # noreorder
    from ..logmanager import LogManager  # fmt: skip

Status = Literal["running", "success", "failure"]

_subagents = []


class ReturnType(TypedDict):
    description: str
    result: Literal["success", "failure"]


@dataclass
class Subagent:
    prompt: str
    agent_id: str
    thread: threading.Thread

    def get_log(self) -> "LogManager":
        # noreorder
        from gptme.cli import get_logfile  # fmt: skip

        from ..logmanager import LogManager  # fmt: skip

        name = f"subagent-{self.agent_id}"
        logfile = get_logfile(name, interactive=False)
        return LogManager.load(logfile)

    def status(self) -> tuple[Status, ReturnType | None]:
        # check if the last message contains the return JSON
        last_msg = self.get_log().log[-1]
        if last_msg.content.startswith("{"):
            print("Subagent has returned a JSON response:")
            print(last_msg.content)
            result = ReturnType(**json.loads(last_msg.content))  # type: ignore
            return result["result"], result
        else:
            return "running", None


@register_function
def subagent(prompt: str, agent_id: str):
    """Runs a subagent and returns the resulting JSON output."""
    # noreorder
    from gptme import chat  # fmt: skip

    from ..prompts import get_prompt  # fmt: skip

    name = f"subagent-{agent_id}"

    def run_subagent():
        prompt_msgs = [Message("user", prompt)]
        initial_msgs = [get_prompt()]

        # add the return prompt
        return_prompt = """When done with the task, please return a JSON response of this format:
{
    description: 'A description of the task result',
    result: 'success' | 'failure',
}"""
        initial_msgs[0].content += "\n\n" + return_prompt

        chat(
            prompt_msgs,
            initial_msgs,
            name=name,
            llm="openai",
            model="gpt-4-1106-preview",
            stream=False,
            no_confirm=True,
            interactive=False,
            show_hidden=False,
        )

    # start a thread with a subagent
    t = threading.Thread(
        target=run_subagent,
        daemon=True,
    )
    t.start()
    _subagents.append(Subagent(prompt, agent_id, t))


@register_function
def subagent_status(agent_id: str):
    """Returns the status of a subagent."""
    for subagent in _subagents:
        if subagent.agent_id == agent_id:
            return subagent.status()
    raise ValueError(f"Subagent with ID {agent_id} not found.")


tool = ToolSpec(
    name="subagent",
    desc="A tool to create subagents",
    examples="",  # TODO
    functions=[subagent, subagent_status],
)
