"""
You can use the tmux tool to run long-lived and/or interactive applications in a tmux session. Requires tmux to be installed.

This tool is suitable to run long-running commands or interactive applications that require user input.
Examples of such commands: ``npm run dev``, ``python3 server.py``, ``python3 train.py``, etc.
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
    # cmd = ["tmux", "new-session", "-d", "-s", session_id, command]
    cmd = ["tmux", "new-session", "-d", "-s", session_id, "bash"]
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

    cmd = ["tmux", "send-keys", "-t", session_id, command, "Enter"]
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
        f"tmux send-keys -t {pane_id} {keys}",
        shell=True,
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


def execute_tmux(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """Executes a command in tmux and returns the output."""
    assert not args
    cmd = code.strip()

    if ask:
        print_preview(f"Command: {cmd}", "bash")
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
You can use the tmux tool to run long-lived and/or interactive applications in a tmux session.

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
Assistant: Certainly! To start the dev server we should use tmux:
```tmux
new_session 'npm run dev'
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

User: Stop the dev server
Assistant: I'll send 'Ctrl+C' to the pane to stop the server:
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

#### Create vue project
User: Create a new vue project with typescript and pinia named fancy-project
Assistant: Sure! Let's create a new vue project with TypeScript and Pinia named fancy-project:
```bash
npm init vue@latest fancy-project --yes -- --typescript --pinia
```
System:
```output
> npx
> create-vue

Vue.js - The Progressive JavaScript Framework

Scaffolding project in ./fancy-project...
```

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
    name="tmux",
    desc="Executes shell commands in a tmux session",
    instructions=instructions,
    # we want to skip the last two examples in prompting
    examples="####".join(examples.split("####")[:-2]),
    execute=execute_tmux,
    block_types=["tmux"],
    available=shutil.which("tmux") is not None,
)
