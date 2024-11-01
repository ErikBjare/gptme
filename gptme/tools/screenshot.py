"""
A simple screenshot tool, using `screencapture` on macOS and `scrot` on Linux.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from .base import ToolSpec


def _screenshot(path: Path) -> Path:
    path = Path(path).resolve()

    if os.name == "posix":
        if os.uname().sysname == "Darwin":  # macOS
            subprocess.run(["screencapture", str(path)], check=True)
        else:  # Linux
            # TODO: add support for specifying window/fullscreen?
            subprocess.run(["scrot", "--overwrite", str(path)], check=True)  # --focused
    else:
        raise NotImplementedError(
            "Screenshot functionality is only available on macOS and Linux."
        )

    return path


def screenshot(path: Path | None = None) -> Path:
    """
    Take a screenshot and save it to a file.
    """
    if path is None:
        # TODO: store in log folder or tmp?
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(f"screenshot_{timestamp}.png")

    return _screenshot(path)


tool = ToolSpec(
    name="screenshot",
    desc="Take a screenshot",
    instructions="Use this tool to capture a screenshot. You can optionally specify a filename.",
    functions=[screenshot],
)
