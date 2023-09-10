from pathlib import Path

# Prompts
ROLE_COLOR = {
    "user": "bright_green",
    "assistant": "bright_cyan",
    "system": "grey42",
}
PROMPT_USER = f"[bold {ROLE_COLOR['user']}]User[/bold {ROLE_COLOR['user']}]"
PROMPT_ASSISTANT = f"[bold {ROLE_COLOR['user']}]Assistant[/bold {ROLE_COLOR['user']}]"

# Dirs
CONFIG_PATH = Path("~/.config/gptme").expanduser()
CONFIG_PATH.mkdir(parents=True, exist_ok=True)

LOGSDIR = Path("~/.local/share/gptme/logs").expanduser()
LOGSDIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = CONFIG_PATH / "history"
