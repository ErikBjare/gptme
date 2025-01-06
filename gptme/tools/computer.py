"""
Tool for computer interaction through X11, including screen capture, keyboard, and mouse control.

The computer tool provides direct interaction with the desktop environment through X11.
Similar to Anthropic's computer use demo, but integrated with gptme's architecture.

.. rubric:: Features

- Keyboard input simulation
- Mouse control (movement, clicks, dragging)
- Screen capture with automatic scaling
- Cursor position tracking

.. rubric:: Installation

Requires X11 and xdotool::

    # On Debian/Ubuntu
    sudo apt install xdotool

    # On Arch Linux
    sudo pacman -S xdotool

.. rubric:: Configuration

The tool uses these environment variables:

- DISPLAY: X11 display to use (default: ":1")
- WIDTH: Screen width (default: 1024)
- HEIGHT: Screen height (default: 768)

.. rubric:: Usage

The tool supports these actions:

Keyboard:
    - key: Send key sequence (e.g., "Return", "Control_L+c")
    - type: Type text with realistic delays

Mouse:
    - mouse_move: Move mouse to coordinates
    - left_click: Click left mouse button
    - right_click: Click right mouse button
    - middle_click: Click middle mouse button
    - double_click: Double click left mouse button
    - left_click_drag: Click and drag to coordinates

Screen:
    - screenshot: Take and view a screenshot
    - cursor_position: Get current mouse position

The tool automatically handles screen resolution scaling to ensure optimal performance
with LLM vision capabilities.
"""

import os
import shlex
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Literal, TypedDict

from ..message import Message
from .base import ToolSpec, ToolUse
from .screenshot import _screenshot
from .vision import view_image

# Constants from Anthropic's implementation
TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50
OUTPUT_DIR = "/tmp/outputs"

Action = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "screenshot",
    "cursor_position",
]


class _Resolution(TypedDict):
    width: int
    height: int


# Recommended maximum resolutions for LLM vision
MAX_SCALING_TARGETS: dict[str, _Resolution] = {
    "XGA": _Resolution(width=1024, height=768),  # 4:3
    "WXGA": _Resolution(width=1280, height=800),  # 16:10
    "FWXGA": _Resolution(width=1366, height=768),  # ~16:9
}


class _ScalingSource(Enum):
    COMPUTER = "computer"
    API = "api"


def _chunks(s: str, chunk_size: int) -> list[str]:
    """Split string into chunks for typing simulation."""
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


def _scale_coordinates(
    source: _ScalingSource, x: int, y: int, current_width: int, current_height: int
) -> tuple[int, int]:
    """Scale coordinates to/from recommended resolutions."""
    ratio = current_width / current_height
    target_dimension = None

    for dimension in MAX_SCALING_TARGETS.values():
        if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
            if dimension["width"] < current_width:
                target_dimension = dimension
                break

    if target_dimension is None:
        return x, y

    x_scaling_factor = target_dimension["width"] / current_width
    y_scaling_factor = target_dimension["height"] / current_height

    if source == _ScalingSource.API:
        if x > current_width or y > current_height:
            raise ValueError(f"Coordinates {x}, {y} are out of bounds")
        # Scale up
        return round(x / x_scaling_factor), round(y / y_scaling_factor)
    # Scale down
    return round(x * x_scaling_factor), round(y * y_scaling_factor)


def _run_xdotool(cmd: str, display: str | None = None) -> str:
    """Run an xdotool command with optional display setting and wait for completion."""
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    try:
        result = subprocess.run(
            f"xdotool {cmd}",
            shell=True,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"xdotool command failed: {e.stderr}") from e


def computer(
    action: Action, text: str | None = None, coordinate: tuple[int, int] | None = None
) -> Message | None:
    """
    Perform computer interactions through X11.

    Args:
        action: The type of action to perform
        text: Text to type or key sequence to send
        coordinate: X,Y coordinates for mouse actions
    """
    display = os.getenv("DISPLAY", ":1")
    width = int(os.getenv("WIDTH", "1024"))
    height = int(os.getenv("HEIGHT", "768"))

    if action in ("mouse_move", "left_click_drag"):
        if not coordinate:
            raise ValueError(f"coordinate is required for {action}")
        x, y = _scale_coordinates(
            _ScalingSource.API, coordinate[0], coordinate[1], width, height
        )

        if action == "mouse_move":
            _run_xdotool(f"mousemove --sync {x} {y}", display)
        else:  # left_click_drag
            _run_xdotool(f"mousedown 1 mousemove --sync {x} {y} mouseup 1", display)

        print(f"Moved mouse to {x},{y}")
        return None
    elif action in ("key", "type"):
        if not text:
            raise ValueError(f"text is required for {action}")

        if action == "key":
            _run_xdotool(f"key -- {text}", display)
            print(f"Sent key sequence: {text}")
        else:  # type
            for chunk in _chunks(text, TYPING_GROUP_SIZE):
                _run_xdotool(
                    f"type --delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}",
                    display,
                )
            print(f"Typed text: {text}")
        return None
    elif action in ("left_click", "right_click", "middle_click", "double_click"):
        click_arg = {
            "left_click": "1",
            "right_click": "3",
            "middle_click": "2",
            "double_click": "--repeat 2 --delay 500 1",
        }[action]
        _run_xdotool(f"click {click_arg}", display)
        print(f"Performed {action}")
        return None
    elif action == "screenshot":
        # Use X11-specific screenshot if available, fall back to native
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "screenshot.png"

        if shutil.which("gnome-screenshot"):
            # FIXME: incorrect call to xdotool
            _run_xdotool(f"gnome-screenshot -f {path} -p", display)
        elif os.name == "posix":
            path = _screenshot(path)  # Use existing screenshot function
        else:
            raise NotImplementedError("Screenshot not supported on this platform")

        # Scale if needed
        if path.exists():
            x, y = _scale_coordinates(
                _ScalingSource.COMPUTER, width, height, width, height
            )
            subprocess.run(
                f"convert {path} -resize {x}x{y}! {path}", shell=True, check=True
            )
            return view_image(path)
        else:
            print("Error: Screenshot failed")
        return None
    elif action == "cursor_position":
        output = _run_xdotool("getmouselocation --shell", display)
        x = int(output.split("X=")[1].split("\n")[0])
        y = int(output.split("Y=")[1].split("\n")[0])
        x, y = _scale_coordinates(_ScalingSource.COMPUTER, x, y, width, height)
        print(f"Cursor position: X={x},Y={y}")
        return None
    raise ValueError(f"Invalid action: {action}")


instructions = """
You can interact with the computer through X11 with the `computer` Python function.
Available actions:
- key: Send key sequence (e.g., "Return", "Control_L+c")
- type: Type text with realistic delays
- mouse_move: Move mouse to coordinates
- left_click, right_click, middle_click, double_click: Mouse clicks
- left_click_drag: Click and drag to coordinates
- screenshot: Take and view a screenshot
- cursor_position: Get current mouse position
"""


def examples(tool_format):
    return f"""
User: Take a screenshot of the desktop
Assistant: I'll capture the current screen.
{ToolUse("ipython", [], 'computer("screenshot")').to_output(tool_format)}
System: Viewing image...

User: Type "Hello, World!" into the active window
Assistant: I'll type the text with realistic delays.
{ToolUse("ipython", [], 'computer("type", text="Hello, World!")').to_output(tool_format)}
System: Typed text: Hello, World!

User: Move the mouse to coordinates (100, 200) and click
Assistant: I'll move the mouse and perform a left click.
{ToolUse("ipython", [], 'computer("mouse_move", coordinate=(100, 200))').to_output(tool_format)}
System: Moved mouse to 100,200
{ToolUse("ipython", [], 'computer("left_click")').to_output(tool_format)}
System: Performed left_click

User: Press Ctrl+C
Assistant: I'll send the Control+C key sequence.
{ToolUse("ipython", [], 'computer("key", text="Control_L+c")').to_output(tool_format)}
System: Sent key sequence: Control_L+c
"""


tool = ToolSpec(
    name="computer",
    desc="Control the computer through X11 (keyboard, mouse, screen)",
    instructions=instructions,
    examples=examples,
    functions=[computer],
    disabled_by_default=True,
)

__doc__ = tool.get_doc(__doc__)
