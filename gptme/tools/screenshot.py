"""
A simple screenshot tool, using `screencapture` on macOS and `scrot` on Linux.
"""

import os
import subprocess
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from ..message import Message
from .base import ToolSpec


def _screenshot(path: Path) -> Path:
    path = Path(path).resolve()

    if os.name == "posix":
        if os.uname().sysname == "Darwin":  # macOS
            subprocess.run(["screencapture", str(path)], check=True)
        else:  # Linux
            subprocess.run(["scrot", "-s", str(path)], check=True)
    else:
        raise NotImplementedError(
            "Screenshot functionality is only available on macOS and Linux."
        )

    return path


def screenshot(path: Path | None = None) -> Generator[Message, None, None]:
    """
    Take a screenshot and save it to a file.
    """
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(f"screenshot_{timestamp}.png")

    try:
        path = _screenshot(path)
        yield Message("system", f"Screenshot saved to: {path}")
    except NotImplementedError as e:
        yield Message("system", str(e))
    except subprocess.CalledProcessError:
        yield Message("system", "Failed to capture screenshot.")


tool = ToolSpec(
    name="screenshot",
    desc="Take a screenshot",
    instructions="Use this tool to capture a screenshot. You can optionally specify a filename.",
    functions=[screenshot],
)
