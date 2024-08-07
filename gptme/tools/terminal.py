"""
The assistant can execute terminal commands in a tmux session for interactive applications.
It also provides tools for inspecting pane contents and sending input.

Example:

.. chat::

    User: Start the dev server
    Assistant: Certainly! To start the dev server we should use the terminal tool to run it in a tmux session:
    ```terminal
    new_session npm run dev
    ```

    System: Created new tmux session with ID 0 and started 'npm run dev'

    User: Can you show me the current content of the pane?
    Assistant: Of course! Let's inspect the pane content:
    ```terminal
    inspect_pane 0
    ```

    System: Pane content:
    ```
    Server is running on localhost:5600
    ```

    User: Can you stop the dev server?
    Assistant: Certainly! I'll send 'Ctrl+C' to the pane to stop the server:
    ```terminal
    send_keys 0 C+c
    ```

    System: Sent 'q' to pane 0

The user can also run terminal commands with the /terminal command:

.. chat::

    User: /terminal new_session htop
    System: Created new tmux session with ID 1 and started 'htop'

"""

import logging
import subprocess
from time import sleep
from collections.abc import Generator

from ..message import Message
from ..util import ask_execute, print_preview
from .base import ToolSpec

logger = logging.getLogger(__name__)

"""
session: gpt_0
window: gpt_0:0
pane: gpt_0:0.0
"""


def get_sessions() -> list[str]:
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
        f"Created new tmux session with ID {session_id} and started '{command}'.\nOutput:\n```\n{output}\n```",
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
        "system", f"Sent '{keys}' to pane `{pane_id}`\nOutput:\n```\n{output}\n```"
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

    parts = cmd.split(maxsplit=1)
    if len(parts) == 1:
        yield Message("system", "Invalid command. Please provide arguments.")

    command, _args = parts[0], parts[1]

    if command == "new_session":
        yield new_session(_args)
    elif command == "send_keys":
        pane_id, keys = _args.split(maxsplit=1)
        yield send_keys(pane_id, keys)
    elif command == "inspect_pane":
        yield inspect_pane(_args)
    elif command == "kill_session":
        yield kill_session(_args)
    elif command == "list_sessions":
        yield list_sessions()
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
> User: Start the dev server
> Assistant: Certainly! To start the dev server we should use the terminal tool to run it in a tmux session:
```terminal
new_session 'npm run dev'
```

> User: Create a new vue project with typescript
> Assistant: Sure! Let's create a new vue project in a tmux session:
```terminal
new_session 'npm create vue@latest'
```
> System: Created new tmux session with ID 0 and started 'npm create vue@latest'
Output:
```
> npx
> create-vue

Vue.js - The Progressive JavaScript Framework

? Project name: › vue-project
```
> Assistant: vue-project is a placeholder we can fill in. What would you like to name your project?
> User: Lets go with 'test-project'
> Assistant:
```terminal
send_keys 0 test-project Enter
> System: Sent 'test-project Enter' to pane 0
> User: Show the content of the pane
> Assistant:
```terminal
inspect_pane 0
```
> System:
```
> npx
> create-vue

Vue.js - The Progressive JavaScript Framework

✔ Project name: … test-project
? Add TypeScript? › No / Yes
```
> Assistant: The project name has been set, now we select TypeScript as requested.
```terminal
send_keys 0 Right Enter
```
> System: Sent 'Right Enter' to pane 0

> User: I changed my mind
> Assistant: No problem! Let's kill the session and start over:
```terminal
list_sessions
```
> System: Active tmux sessions: [0]
> Assistant:
```terminal
kill_session 0
```
> System: Killed tmux session with ID 0
"""

tool = ToolSpec(
    name="terminal",
    desc="Executes terminal commands in a tmux session for interactive applications.",
    instructions=instructions,
    examples=examples,
    execute=execute_terminal,
    block_types=["terminal"],
)
