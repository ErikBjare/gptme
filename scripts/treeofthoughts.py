"""
Tree-branching conversations for gptme with branch evaluation/prediction.

The idea is to evaluate if we are on the right track by checking if the current branch is "good"/making progress, and otherwise backtracking to the last good branch and trying a different prompt/approach.

The goal is to have a more autonomous agent which can self-supervise and make several branching attempts to find the right path to the solution.
"""

import subprocess
import sys
from typing import Literal

from gptme.chat import step as _step
from gptme.init import init
from gptme.logmanager import Log
from gptme.message import Message
from gptme.prompts import get_prompt
from lxml import etree

EvalAction = Literal["continue", "undo", "done"]


def project_files() -> list[str]:
    # Returns a list of files in the project
    p = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return p.stdout.splitlines()


def changed_files() -> list[str]:
    # Returns a list of changed files in the project
    p = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True
    )
    return p.stdout.splitlines()


def unstaged_files() -> list[str]:
    # Returns a list of unstaged files in the project
    p = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True)
    return p.stdout.splitlines()


def context_from_files(files: list[str]) -> str:
    # Returns the context from the files
    context = ""
    for f in files:
        context += f"```{f}\n"
        with open(f) as file:
            try:
                context += file.read()
            except UnicodeDecodeError:
                context += "<binary file>"
        context += "\n```\n"
    return context


def step(log: Log) -> Log:
    # Steps the conversation forward
    for msg in _step(log, no_confirm=True):
        log = log.append(msg)
    return log


def recommendation(log: Log) -> EvalAction:
    # Returns a LLM-guided recommendation for the next action
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
    log = step(log)
    parser = etree.HTMLParser()
    tree = etree.fromstring(log[-1].content, parser)
    return tree.xpath("//action")[0].text


def lint_format(log: Log) -> Log:
    # Lint, format, and fix the conversation by calling "make format"
    p = subprocess.run(["make", "format"], capture_output=True, text=True)
    if p.returncode == 0:
        return log

    changed_files = [f for f in unstaged_files() if f in p.stdout or f in p.stderr]
    files_str = f"""Files:
{context_from_files(changed_files)}
"""

    system_msg = Message(
        "system",
        f"""
Linting and formatting the code with "make format"...

stdout:
{p.stdout}

stderr:
{p.stderr}

{files_str}
""".strip(),
    )
    log = log.append(system_msg)
    return log


def typecheck(log: Log) -> Log:
    # Typecheck the code by calling "make typecheck"
    p = subprocess.run(["make", "typecheck"], capture_output=True, text=True)
    if p.returncode == 0:
        return log

    system_msg = Message(
        "system",
        f"""
Typechecking the code with "make typecheck"...

stdout:
{p.stdout}

stderr:
{p.stderr}
""",
    )
    log = log.append(system_msg)
    return log


context_header = "Context:\n\n"


def gather_context() -> Message:
    # Dynamically gather context from changed files
    files = changed_files()
    return Message("system", context_header + context_from_files(files))


def update_context(log: Log) -> Log:
    # remove the last context message
    msgs = [msg for msg in log if not msg.content.startswith(context_header)]
    return Log(msgs + [gather_context()])


def main():
    print("Initializing the autonomous agent...")
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

    # Main loop for autonomous operation
    while True:
        # Gather and update context
        log = update_context(log)
        print("Context updated.")

        # Step the conversation forward
        log = step(log)
        print("Conversation stepped forward.")

        # Check for changes in the project files
        if (
            subprocess.run(
                ["git", "diff", "--exit-code"], capture_output=True
            ).returncode
            != 0
        ):
            print("Changes detected, performing lint and typecheck.")
            log = lint_format(log)
            log = typecheck(log)

        # Get recommendation for next action
        action = recommendation(log)
        print(f"Recommended action: {action}")

        # Execute the recommended action
        if action == "continue":
            continue
        elif action == "undo":
            log = log.pop()
            print("Undoing last step.")
        elif action == "done":
            print("Task completed successfully.")
            break
        else:
            print(f"Unexpected action: {action}")
            break

    print("Exiting")


if __name__ == "__main__":
    main()
