"""
You can use the terminal tool to run long-lived and/or interactive applications in a tmux session. Requires tmux to be installed.

This tool is suitable to run long-running commands or interactive applications that require user input.
Examples of such commands: ``npm run dev``, ``npm create vue@latest``, ``python3 server.py``, ``python3 train.py``, etc.
It allows for inspecting pane contents and sending input.
"""

import logging
import shutil
import subprocess
from collections.abc import Generator
from time import sleep

from ..message import Message
from ..util import ask_execute, print_preview, transform_examples_to_chat_directives
from .base import ToolSpec

logger = logging.getLogger(__name__)

# Examples of identifiers:
#   session: gpt_0
#   window: gpt_0:0
#   pane: gpt_0:0.0


def get_sessions() -> list[str]:
    output = subprocess.run(
        ["tmux", "has"],
        capture_output=True,
        text=True,
    )
    if output.returncode != 0:
        return []
    output = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True,
    )
    assert output.returncode == 0
    return [session.split(":")[0] for session in output.stdout.split("\n") if session]


def _capture_pane(pane_id: str) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", pane_id],
        capture_output=True,
        text=True,
    )
    return result.stdout


def new_session(command: str) -> Message:
    _max_session_id = 0
    for session in get_sessions():
        if session.startswith("gptme_"):
            _max_session_id = max(_max_session_id, int(session.split("_")[1]))
    session_id = f"gptme_{_max_session_id + 1}"
    cmd = ["tmux", "new-session", "-d", "-s", session_id, command]
    print(" ".join(cmd))
    result = subprocess.run(
        " ".join(cmd),
        check=True,
        capture_output=True,
        text=True,
        shell=True,
    )
    assert result.returncode == 0
    print(result.stdout, result.stderr)

    # sleep 1s and capture output
    sleep(1)
    output = _capture_pane(f"{session_id}")
    return Message(
        "system",
        f"Running '{command}' in session {session_id}.\n```output\n{output}\n```",
    )


def send_keys(pane_id: str, keys: str) -> Message:
    result = subprocess.run(
        ["tmux", "send-keys", "-t", pane_id, *keys.split(" ")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return Message(
            "system", f"Failed to send keys to tmux pane `{pane_id}`: {result.stderr}"
        )
    sleep(1)
    output = _capture_pane(pane_id)
    return Message(
        "system", f"Sent '{keys}' to pane `{pane_id}`\n```output\n{output}\n```"
    )


def inspect_pane(pane_id: str) -> Message:
    content = _capture_pane(pane_id)
    return Message(
        "system",
        f"""Pane content:
```output
{content}
```""",
    )


def kill_session(session_id: str) -> Message:
    result = subprocess.run(
        ["tmux", "kill-session", "-t", f"gptme_{session_id}"],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return Message(
            "system",
            f"Failed to kill tmux session with ID {session_id}: {result.stderr}",
        )
    return Message("system", f"Killed tmux session with ID {session_id}")


def list_sessions() -> Message:
    sessions = get_sessions()
    return Message("system", f"Active tmux sessions: {sessions}")


def execute_terminal(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """Executes a terminal command and returns the output."""
    assert not args
    cmd = code.strip()

    if ask:
        print_preview(f"Terminal command: {cmd}", "sh")
        confirm = ask_execute()
        print()
        if not confirm:
            yield Message("system", "Command execution cancelled.")
            return

    parts = cmd.split(maxsplit=1)
    command = parts[0]
    if command == "list_sessions":
        yield list_sessions()
        return

    _args = parts[1]
    if command == "new_session":
        yield new_session(_args)
    elif command == "send_keys":
        pane_id, keys = _args.split(maxsplit=1)
        yield send_keys(pane_id, keys)
    elif command == "inspect_pane":
        yield inspect_pane(_args)
    elif command == "kill_session":
        yield kill_session(_args)
    else:
        yield Message("system", f"Unknown command: {command}")


instructions = """
You can use the terminal tool to run long-lived and/or interactive applications in a tmux session.

This tool is suitable to run long-running commands or interactive applications that require user input.
Examples of such commands are: `npm run dev`, `npm create vue@latest`, `python3 server.py`, `python3 train.py`, etc.

Available commands:
- new_session <command>: Start a new tmux session with the given command
- send_keys <session_id> <keys> [<keys>]: Send keys to the specified session
- inspect_pane <session_id>: Show the current content of the specified pane
- kill_session <session_id>: Terminate the specified tmux session
- list_sessions: Show all active tmux sessions
"""
# TODO: implement smart-wait, where we wait for n seconds and then until output is stable

examples = """
#### Managing a dev server
User: Start the dev server
Assistant: Certainly! To start the dev server we should use the terminal tool to run it in a tmux session:
```terminal
new_session npm run dev
```
System: Running `npm run dev` in session 0

User: Can you show me the current content of the pane?
Assistant: Of course! Let's inspect the pane content:
```terminal
inspect_pane 0
```
System:
```output
Server is running on localhost:5600
```

User: Can you stop the dev server?
Assistant: Certainly! I'll send 'Ctrl+C' to the pane to stop the server:
```terminal
send_keys 0 C-c
```
System: Sent 'C-c' to pane 0

#### Get info from ncurses applications
User: start top and give me a summary
System: Running `top` in session 1.
```output
(output from top shown here)
```
Assistant: The load is...

#### Background process
User: Start the dev server
Assistant: Certainly! To start the dev server we should use the terminal tool to run it in a tmux session:
```terminal
new_session 'npm run dev'
```

#### Interactive process
User: Create a new vue project with typescript
Assistant: Sure! Let's create a new vue project in a tmux session:
```terminal
new_session 'npm create vue@latest'
```
System: Running 'npm create vue@latest' in session 0
```output
> npx
> create-vue

Vue.js - The Progressive JavaScript Framework

? Project name: › vue-project
```
Assistant: vue-project is a placeholder we can fill in. What would you like to name your project?
User: fancy-project
Assistant:
```terminal
send_keys 0 fancy-project Enter
```
System: Sent 'fancy-project Enter' to pane 0
Assistant: Lets check that the name was set and move on
```terminal
inspect_pane 0
```
System:
```output
? Project name: › fancy-project
? Add TypeScript? › No / Yes
```
Assistant: The project name has been set, now we choose TypeScript
```terminal
send_keys 0 Right Enter
```
System: Sent 'Right Enter' to pane 0

#### Ending a session
User: I changed my mind
Assistant: No problem! Let's kill the session and start over:
```terminal
list_sessions
```
System: Active tmux sessions [0]
Assistant:
```terminal
kill_session 0
```
System: Killed tmux session with ID 0
"""


new_examples = transform_examples_to_chat_directives(examples)
__doc__ += new_examples


tool = ToolSpec(
    name="terminal",
    desc="Executes shell commands in a tmux session",
    instructions=instructions,
    # we want to skip the last two examples in prompting
    examples="####".join(examples.split("####")[:-2]),
    execute=execute_terminal,
    block_types=["terminal"],
    available=shutil.which("tmux") is not None,
)
