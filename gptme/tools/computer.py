"""
Tool for computer interaction through X11, including screen capture, keyboard, and mouse control.
Similar to Anthropic's computer use demo, but integrated with gptme's architecture.
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


class Resolution(TypedDict):
    width: int
    height: int


# Recommended maximum resolutions for LLM vision
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),  # 4:3
    "WXGA": Resolution(width=1280, height=800),  # 16:10
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9
}


class ScalingSource(Enum):
    COMPUTER = "computer"
    API = "api"


def chunks(s: str, chunk_size: int) -> list[str]:
    """Split string into chunks for typing simulation."""
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


def scale_coordinates(
    source: ScalingSource, x: int, y: int, current_width: int, current_height: int
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

    if source == ScalingSource.API:
        if x > current_width or y > current_height:
            raise ValueError(f"Coordinates {x}, {y} are out of bounds")
        # Scale up
        return round(x / x_scaling_factor), round(y / y_scaling_factor)
    # Scale down
    return round(x * x_scaling_factor), round(y * y_scaling_factor)


def run_xdotool(cmd: str, display: str | None = None) -> str:
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
        x, y = scale_coordinates(
            ScalingSource.API, coordinate[0], coordinate[1], width, height
        )

        if action == "mouse_move":
            run_xdotool(f"mousemove --sync {x} {y}", display)
        else:  # left_click_drag
            run_xdotool(f"mousedown 1 mousemove --sync {x} {y} mouseup 1", display)

        print(f"Moved mouse to {x},{y}")
        return None
    elif action in ("key", "type"):
        if not text:
            raise ValueError(f"text is required for {action}")

        if action == "key":
            run_xdotool(f"key -- {text}", display)
            print(f"Sent key sequence: {text}")
        else:  # type
            for chunk in chunks(text, TYPING_GROUP_SIZE):
                run_xdotool(
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
        run_xdotool(f"click {click_arg}", display)
        print(f"Performed {action}")
        return None
    elif action == "screenshot":
        # Use X11-specific screenshot if available, fall back to native
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "screenshot.png"

        if shutil.which("gnome-screenshot"):
            # FIXME: incorrect call to xdotool
            run_xdotool(f"gnome-screenshot -f {path} -p", display)
        elif os.name == "posix":
            path = _screenshot(path)  # Use existing screenshot function
        else:
            raise NotImplementedError("Screenshot not supported on this platform")

        # Scale if needed
        if path.exists():
            x, y = scale_coordinates(
                ScalingSource.COMPUTER, width, height, width, height
            )
            subprocess.run(
                f"convert {path} -resize {x}x{y}! {path}", shell=True, check=True
            )
            return view_image(path)
        else:
            print("Error: Screenshot failed")
        return None
    elif action == "cursor_position":
        output = run_xdotool("getmouselocation --shell", display)
        x = int(output.split("X=")[1].split("\n")[0])
        y = int(output.split("Y=")[1].split("\n")[0])
        x, y = scale_coordinates(ScalingSource.COMPUTER, x, y, width, height)
        print(f"Cursor position: X={x},Y={y}")
        return None
    raise ValueError(f"Invalid action: {action}")


instructions = """
Use this tool to interact with the computer through X11.
Available actions:
- key: Send key sequence (e.g., "Return", "Control_L+c")
- type: Type text with realistic delays
- mouse_move: Move mouse to coordinates
- left_click, right_click, middle_click, double_click: Mouse clicks
- left_click_drag: Click and drag to coordinates
- screenshot: Take and view a screenshot
- cursor_position: Get current mouse position
"""

examples = f"""
#### View a screenshot
> User: What do you see on the screen?
> Assistant:
{ToolUse("ipython", [], 'computer("screenshot")').to_output()}
> System: Viewing image...
"""

tool = ToolSpec(
    name="computer",
    desc="Control the computer through X11 (keyboard, mouse, screen)",
    instructions=instructions,
    examples=examples,
    functions=[computer],
)
