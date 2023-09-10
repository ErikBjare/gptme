from pathlib import Path

# Prompts
ROLE_COLOR = {
    "user": "bright_green",
    "assistant": "bright_cyan",
    "system": "grey42",
}

# colors wrapped in \001 and \002 to inform readline about non-printable characters
PROMPT_USER = (
    f"\001[bold {ROLE_COLOR['user']}]\002User\001[/bold {ROLE_COLOR['user']}]\002"
)
PROMPT_ASSISTANT = f"[bold {ROLE_COLOR['user']}]Assistant[/bold {ROLE_COLOR['user']}]"

# Config
CONFIG_PATH = Path("~/.config/gptme").expanduser()
HISTORY_FILE = CONFIG_PATH / "history"

# Data
DATADIR = Path("~/.local/share/gptme").expanduser()
LOGSDIR = DATADIR / "logs"

# create all paths
for path in [CONFIG_PATH, DATADIR, LOGSDIR]:
    path.mkdir(parents=True, exist_ok=True)
