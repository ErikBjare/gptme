from typing import Literal

CMDFIX = "/"  # prefix for commands, e.g. /help

Actions = Literal[
    "continue",
    "summarize",
    "log",
    "edit",
    "rename",
    "fork",
    "summarize",
    "context",
    "load",
    "save",
    "shell",
    "python",
    "replay",
    "undo",
    "impersonate",
    "help",
    "exit",
]

action_descriptions: dict[Actions, str] = {
    "continue": "Continue response",
    "undo": "Undo the last action",
    "log": "Show the conversation log",
    "edit": "Edit previous messages",
    "rename": "Rename the conversation",
    "fork": "Create a copy of the conversation with a new name",
    "summarize": "Summarize the conversation so far",
    "load": "Load a file",
    "save": "Save the most recent code block to a file",
    "shell": "Execute a shell command",
    "python": "Execute a Python command",
    "replay": "Re-execute past commands in the conversation (does not store output in log)",
    "impersonate": "Impersonate the assistant",
    "help": "Show this help message",
    "exit": "Exit the program",
}
COMMANDS = list(action_descriptions.keys())
