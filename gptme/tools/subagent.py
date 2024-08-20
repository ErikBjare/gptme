"""
A subagent tool for gptme

Lets gptme break down a task into smaller parts, and delegate them to subagents.
"""

import json
import logging
import re
import threading
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

from ..message import Message
from ..util import transform_examples_to_chat_directives
from .base import ToolSpec
from .python import register_function

if TYPE_CHECKING:
    # noreorder
    from ..logmanager import LogManager  # fmt: skip

logger = logging.getLogger(__name__)

Status = Literal["running", "success", "failure"]

_subagents = []


@dataclass
class ReturnType:
    status: Status
    result: str | None = None


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

    def status(self) -> ReturnType:
        if self.thread.is_alive():
            return ReturnType("running")
        # check if the last message contains the return JSON
        msg = self.get_log().log[-1].content.strip()
        json_response = _extract_json(msg)
        if not json_response:
            print(f"FAILED to find JSON in message: {msg}")
            return ReturnType("failure")
        elif not json_response.strip().startswith("{"):
            print(f"FAILED to parse JSON: {json_response}")
            return ReturnType("failure")
        else:
            return ReturnType(**json.loads(json_response))  # type: ignore


def _extract_json_re(s: str) -> str:
    return re.sub(
        r"(?s).+?(```json)?\n([{](.+?)+?[}])\n(```)?",
        r"\2",
        s,
    ).strip()


def _extract_json(s: str) -> str:
    first_brace = s.find("{")
    last_brace = s.rfind("}")
    return s[first_brace : last_brace + 1]


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
        return_prompt = """When done with the task, please end with a JSON response on the format:

```json
{
    result: 'A description of the task result/outcome',
    status: 'success' | 'failure',
}
```"""
        initial_msgs[0].content += "\n\n" + return_prompt

        chat(
            prompt_msgs,
            initial_msgs,
            name=name,
            model=None,
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
def subagent_status(agent_id: str) -> dict:
    """Returns the status of a subagent."""
    for subagent in _subagents:
        if subagent.agent_id == agent_id:
            return asdict(subagent.status())
    raise ValueError(f"Subagent with ID {agent_id} not found.")


@register_function
def subagent_wait(agent_id: str) -> dict:
    """Waits for a subagent to finish. Timeout is 1 minute."""
    subagent = None
    for subagent in _subagents:
        if subagent.agent_id == agent_id:
            break

    if subagent is None:
        raise ValueError(f"Subagent with ID {agent_id} not found.")

    print("Waiting for the subagent to finish...")
    subagent.thread.join(timeout=60)
    status = subagent.status()
    return asdict(status)


examples = """
User: compute fib 69 using a subagent
Assistant: Starting a subagent to compute the 69th Fibonacci number.
```ipython
subagent("compute the 69th Fibonacci number", "fib-69")
```
System: Subagent started successfully.
Assistant: Now we need to wait for the subagent to finish the task.
```ipython
subagent_wait("fib-69")
```
"""

__doc__ += transform_examples_to_chat_directives(examples)


tool = ToolSpec(
    name="subagent",
    desc="A tool to create subagents",
    examples=examples,
    functions=[subagent, subagent_status, subagent_wait],
)
