"""
Tool for computer interaction through X11 or macOS native commands, including screen capture, keyboard, and mouse control.

The computer tool provides direct interaction with the desktop environment.
Similar to Anthropic's computer use demo, but integrated with gptme's architecture.

.. rubric:: Features

- Keyboard input simulation
- Mouse control (movement, clicks, dragging)
- Screen capture with automatic scaling
- Cursor position tracking

.. rubric:: Installation

On Linux, requires X11 and xdotool::

    # On Debian/Ubuntu
    sudo apt install xdotool

    # On Arch Linux
    sudo pacman -S xdotool

On macOS, uses native ``screencapture`` and external tool `cliclicker`::

    brew install cliclicker

You need to give your terminal both screen recording and accessibility permissions in System Preferences.

.. rubric:: Configuration

The tool uses these environment variables:

- DISPLAY: X11 display to use (default: ":1", Linux only)
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
import platform
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

# Platform detection
IS_MACOS = platform.system() == "Darwin"


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
    if IS_MACOS:
        raise RuntimeError("xdotool is not supported on macOS")

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


def _macos_type(text: str) -> None:
    """
    Type text using cliclick on macOS.

    Security:
        - Uses cliclick for reliable input
        - Text is properly escaped
    """
    safe_text = shlex.quote(text)
    try:
        subprocess.run(["cliclick", "t:" + safe_text], check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "cliclick not found. Install with: brew install cliclick"
        ) from None


def _ensure_cliclick() -> None:
    """Ensure cliclick is installed, raise helpful error if not."""
    if not shutil.which("cliclick"):
        raise RuntimeError("cliclick not found. Install with: brew install cliclick")


def _macos_key(key_sequence: str) -> None:
    """
    Send key sequence using cliclick on macOS.

    Maps common key names to cliclick key codes.
    Uses cliclick's key down/up commands for modifiers and key press for regular keys.

    Security:
        - Input is properly escaped
        - Uses cliclick's built-in key system
    """
    _ensure_cliclick()

    # Map common key names to cliclick key codes
    key_map = {
        "Return": "return",
        "Control_L": "ctrl",
        "Alt_L": "alt",
        "Super_L": "cmd",
        "Shift_L": "shift",
        # Add more mappings as needed
    }

    keys = key_sequence.split("+")
    modifiers = []
    main_key = None

    for key in keys:
        if key in key_map:
            if key in ["Control_L", "Alt_L", "Super_L", "Shift_L"]:
                modifiers.append(key_map[key])
            else:
                main_key = key_map[key]
        else:
            # For regular characters, use key press
            main_key = key.lower()

    commands = []
    if modifiers:
        # Press modifiers
        commands.append(f"kd:{','.join(modifiers)}")

    if main_key:
        if len(main_key) == 1:
            # For single characters, use type
            commands.append(f"t:{main_key}")
        else:
            # For special keys, use key press
            commands.append(f"kp:{main_key}")

    if modifiers:
        # Release modifiers
        commands.append(f"ku:{','.join(modifiers)}")

    try:
        for cmd in commands:
            subprocess.run(
                ["cliclick", cmd], check=True, capture_output=True, text=True
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to send key sequence: {e.stderr}") from e


def _macos_mouse_move(x: int, y: int) -> None:
    """
    Move mouse using cliclick on macOS.

    Security:
        - Coordinates are validated as integers
        - Uses cliclick for reliable input
    """
    try:
        subprocess.run(["cliclick", f"m:{x},{y}"], check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "cliclick not found. Install with: brew install cliclick"
        ) from None


def _macos_click(button: int) -> None:
    """
    Click mouse button using cliclick on macOS.

    Security:
        - Button number is validated as integer
        - Only allows valid button numbers
        - Uses cliclick for reliable input
    """
    _ensure_cliclick()

    if button not in (1, 2, 3):
        raise ValueError("Invalid button number")

    # Get current position
    try:
        result = subprocess.run(
            ["cliclick", "p"], check=True, capture_output=True, text=True
        )
        pos = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get cursor position: {e.stderr}") from e

    # Map buttons to cliclick commands
    button_map = {1: "c", 2: "m", 3: "rc"}
    cmd = f"{button_map[button]}:{pos}"

    try:
        result = subprocess.run(
            ["cliclick", cmd], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to click: {e.stderr}") from e


def computer(
    action: Action, text: str | None = None, coordinate: tuple[int, int] | None = None
) -> Message | None:
    """
    Perform computer interactions in X11 or macOS environments.

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

        if IS_MACOS:
            if action == "mouse_move":
                _macos_mouse_move(x, y)
            else:  # left_click_drag
                _macos_mouse_move(x, y)
                _macos_click(1)
                _macos_mouse_move(x, y)
                _macos_click(1)
        else:
            if action == "mouse_move":
                _run_xdotool(f"mousemove --sync {x} {y}", display)
            else:  # left_click_drag
                _run_xdotool(f"mousedown 1 mousemove --sync {x} {y} mouseup 1", display)

        print(f"Moved mouse to {x},{y}")
        return None
    elif action in ("key", "type"):
        if not text:
            raise ValueError(f"text is required for {action}")

        if IS_MACOS:
            if action == "key":
                _macos_key(text)
                print(f"Sent key sequence: {text}")
            else:  # type
                for chunk in _chunks(text, TYPING_GROUP_SIZE):
                    _macos_type(chunk)
                print(f"Typed text: {text}")
        else:
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
    elif action == "double_click":
        if IS_MACOS:
            # Get current position and double-click using cliclick's dc command
            try:
                result = subprocess.run(
                    ["cliclick", "p"], check=True, capture_output=True, text=True
                )
                pos = result.stdout.strip()
                subprocess.run(
                    ["cliclick", f"dc:{pos}"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to double-click: {e.stderr}") from e
        else:
            _run_xdotool("click --repeat 2 --delay 100 1", display)
        print("Performed double_click")
        return None
    elif action in ("left_click", "right_click", "middle_click"):
        click_map = {
            "left_click": 1,
            "right_click": 3,
            "middle_click": 2,
        }

        if IS_MACOS:
            button = click_map[action]
            _macos_click(button)
        else:
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
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "screenshot.png"

        if IS_MACOS:
            # Use native macOS screencapture
            subprocess.run(["screencapture", "-x", str(path)], check=True)
        elif shutil.which("gnome-screenshot"):
            subprocess.run(["gnome-screenshot", "-f", str(path)], check=True)
        else:
            path = _screenshot(path)  # Use existing screenshot function

        # Scale if needed
        if path.exists():
            x, y = _scale_coordinates(
                _ScalingSource.COMPUTER, width, height, width, height
            )
            subprocess.run(
                ["convert", str(path), "-resize", f"{x}x{y}!", str(path)],
                check=True,
            )
            return view_image(path)
        else:
            print("Error: Screenshot failed")
        return None
    elif action == "cursor_position":
        if IS_MACOS:
            try:
                output = subprocess.run(
                    ["cliclick", "p"], capture_output=True, text=True, check=True
                ).stdout.strip()
                # cliclick outputs format: "x,y"
                x, y = map(int, output.split(","))
            except FileNotFoundError:
                raise RuntimeError(
                    "cliclick not found. Install with: brew install cliclick"
                ) from None
            except (subprocess.CalledProcessError, ValueError) as e:
                raise RuntimeError(f"Failed to get cursor position: {e}") from e
        else:
            output = _run_xdotool("getmouselocation --shell", display)
            x = int(output.split("X=")[1].split("\n")[0])
            y = int(output.split("Y=")[1].split("\n")[0])

        x, y = _scale_coordinates(_ScalingSource.COMPUTER, x, y, width, height)
        print(f"Cursor position: X={x},Y={y}")
        return None
    raise ValueError(f"Invalid action: {action}")


instructions = """
You can interact with the computer through the `computer` Python function.
Works on both Linux (X11) and macOS.

Available actions:
- key: Send key sequence (e.g., "Return", "Control_L+c")
- type: Type text with realistic delays
- mouse_move: Move mouse to coordinates
- left_click, right_click, middle_click, double_click: Mouse clicks
- left_click_drag: Click and drag to coordinates
- screenshot: Take and view a screenshot
- cursor_position: Get current mouse position

Note: Key names are automatically mapped between platforms.
Common modifiers like Control_L, Alt_L, Super_L work on both platforms.
"""


def examples(tool_format):
    return f"""
User: Take a screenshot of the desktop
Assistant: I'll capture the screen using the screenshot tool.
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

User: Get the current mouse position
Assistant: I'll get the cursor position.
{ToolUse("ipython", [], 'computer("cursor_position")').to_output(tool_format)}
System: Cursor position: X=512,Y=384

User: Double-click at current position
Assistant: I'll perform a double-click.
{ToolUse("ipython", [], 'computer("double_click")').to_output(tool_format)}
System: Performed double_click
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
