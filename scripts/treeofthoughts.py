"""
Tree-branching conversations for gptme with branch evaluation/prediction.

The idea is to evaluate if we are on the right track by checking if the current branch is "good"/making progress, and otherwise backtracking to the last good branch and trying a different prompt/approach.
"""

import sys
from typing import Literal

from gptme.chat import step as _step
from gptme.init import init
from gptme.logmanager import Log
from gptme.message import Message
from gptme.prompts import get_prompt
from lxml import etree

EvalAction = Literal["continue", "undo", "done"]


def step(log: Log) -> Log:
    # Steps the conversation forward
    for msg in _step(log, no_confirm=True):
        log = log.append(msg)
    return log


def recommendation(log: Log) -> EvalAction:
    # Returns a LLM-guided recommendation for the next action
    # Can be: undo (backtrack), restart, continue,
    system_msg = Message(
        "system",
        """
We are evaluating the agent in the following conversation to determine the next action.

Please evaluate the current state of the conversation,
if the agent is making progress or if we should undo,
and then recommend the next action within <action></action> tags.

For example:
<action>continue</action> to let the agent continue (making progress)
<action>undo</action> to backtrack until last user prompt (made a mistake)
<action>done</action> if the agent has completed the task (e.g. answered the question)
""",
    )
    log_xml = "Here is the conversation to evaluate:\n"
    for msg in log:
        log_xml += msg.to_xml() + "\n"
    log = Log(
        [system_msg]
        + [Message("system", log_xml)]
        + [Message("user", "evaluate the agent")]
    )
    log = step(log)  # TODO: use faster model for this
    parser = etree.HTMLParser()
    tree = etree.fromstring(log[-1].content, parser)
    return tree.xpath("//action")[0].text


print("Init...")
init(
    model="openai/gpt-4o",
    interactive=False,
    tool_allowlist=["python", "shell", "save", "patch"],
)

# Set up the conversation
prompt = sys.argv[1] if len(sys.argv) > 1 else "What is fib(10)?"
prompts = [Message("user", prompt)]
initial_msgs = [get_prompt("full", interactive=False)]
log = Log(initial_msgs + prompts)

while True:
    # Step it forward
    print("Stepping...")
    log = step(log)
    print("Done with step")

    # Evaluate the conversation
    action = recommendation(log)
    print(f"Recommendation: {action}")

    # Take the recommended action
    if action == "continue":
        continue
    elif action == "undo":
        log = log.pop()
    elif action == "done":
        break
    else:
        raise ValueError(f"Invalid action: {action}")

# Print the final conversation
log.print()
