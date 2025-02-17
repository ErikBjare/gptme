"""
A simple screenshot tool, using `screencapture` on macOS and `scrot` or `gnome-screenshot` on Linux.
"""

import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .base import ToolSpec

OUTPUT_DIR = Path("/tmp/outputs")
IS_MACOS = platform.system() == "Darwin"
IS_WAYLAND = os.environ.get("XDG_SESSION_TYPE") == "wayland"

# TODO: check for this instead of prompting the llm
INSTRUCTIONS = (
    "If all you see is a wallpaper, the user may have to allow screen capture in `System Preferences -> Security & Privacy -> Screen Recording`."
    if IS_MACOS
    else ""
)


def screenshot(path: Path | None = None) -> Path:
    """
    Take a screenshot and save it to a file.
    """

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"screenshot_{timestamp}.png"

    path.parent.mkdir(parents=True, exist_ok=True)
    path = path.resolve()

    if IS_MACOS:
        subprocess.run(["screencapture", str(path)], check=True)
        return path
    elif os.name == "posix":
        # TODO: add support for specifying window/fullscreen?
        if shutil.which("gnome-screenshot"):
            subprocess.run(["gnome-screenshot", "-f", str(path)], check=True)
            return path
        elif not IS_WAYLAND and shutil.which("scrot"):
            subprocess.run(["scrot", "--overwrite", str(path)], check=True)
            return path
        else:
            raise NotImplementedError("No supported screenshot method available")
    else:
        raise NotImplementedError(
            "Screenshot functionality is only available on macOS and Linux."
        )


tool = ToolSpec(
    name="screenshot",
    desc="Take a screenshot",
    instructions=INSTRUCTIONS,
    functions=[screenshot],
)
