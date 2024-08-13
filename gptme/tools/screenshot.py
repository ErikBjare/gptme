"""
A simple screenshot tool, using `screencapture` on macOS and `scrot` on Linux.
"""

import os
import subprocess
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from ..message import Message
from ..util import ask_execute, print_preview
from .base import ToolSpec


def take_screenshot(filename: str | None = None) -> str:
    """
    Take a screenshot and save it to a file.

    :param filename: Optional filename for the screenshot. If not provided, a default name will be used.
    :return: Path to the saved screenshot file.
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

    screenshot_path = Path(filename).resolve()

    if os.name == "posix":
        if os.uname().sysname == "Darwin":  # macOS
            subprocess.run(["screencapture", "-i", str(screenshot_path)], check=True)
        else:  # Linux
            subprocess.run(["scrot", "-s", str(screenshot_path)], check=True)
    else:
        raise NotImplementedError(
            "Screenshot functionality is only available on macOS and Linux."
        )

    return str(screenshot_path)


def execute_screenshot(
    code: str, ask: bool, args: list[str]
) -> Generator[Message, None, None]:
    """Executes a screenshot command and returns the output."""
    assert not args
    filename = (
        code.strip()
        if code.strip()
        else f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )

    if ask:
        print_preview(f"Taking screenshot: {filename or 'default filename'}", "sh")
        confirm = ask_execute()
        print()
        if not confirm:
            yield Message("system", "Screenshot cancelled.")
            return

    try:
        screenshot_path = take_screenshot(filename)
        yield Message("system", f"Screenshot saved to: {screenshot_path}")
    except NotImplementedError as e:
        yield Message("system", str(e))
    except subprocess.CalledProcessError:
        yield Message("system", "Failed to capture screenshot.")


tool = ToolSpec(
    name="screenshot",
    desc="Take a screenshot",
    instructions="Use this tool to capture a screenshot. You can optionally specify a filename.",
    examples="""
User: Take a screenshot
Assistant: Certainly! Let's capture a screenshot using the screenshot tool:
```screenshot
```
Assistant: Screenshot saved to: <path>
""",
    execute=execute_screenshot,
)
