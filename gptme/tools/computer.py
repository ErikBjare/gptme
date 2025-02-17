"""
Tool for computer interaction for X11 or macOS environments, including screen capture, keyboard, and mouse control.

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

import logging
import os
import platform
import shlex
import shutil
import subprocess
from enum import Enum
from typing import Literal, TypedDict

from ..message import Message
from .base import ToolSpec, ToolUse
from .screenshot import screenshot
from .vision import view_image

logger = logging.getLogger(__name__)


# Platform detection
IS_MACOS = platform.system() == "Darwin"


# Constants from Anthropic's implementation
TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50

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


def _get_display_resolution() -> tuple[int, int]:
    """Get the physical display resolution."""
    try:
        if IS_MACOS:
            output = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"], text=True
            )
            for line in output.splitlines():
                if "Resolution" in line:
                    # Parse "Resolution: 2560 x 1664 Retina"
                    parts = line.split(":")[-1].split("x")
                    width = int(parts[0].strip())
                    height = int(parts[1].split()[0].strip())
                    return width, height
        else:
            output = subprocess.check_output(["xrandr"], text=True)
            for line in output.splitlines():
                if "*" in line:  # Current resolution has an asterisk
                    # Parse "2560x1440" from the line
                    resolution = line.split()[0]
                    width, height = map(int, resolution.split("x"))
                    return width, height
    except (subprocess.CalledProcessError, ValueError, IndexError) as e:
        raise RuntimeError(f"Failed to get display resolution: {e}") from e
    raise RuntimeError("Failed to get display resolution")


def _scale_coordinates(
    source: _ScalingSource, x: int, y: int, api_width: int, api_height: int
) -> tuple[int, int]:
    """Scale coordinates between API space and actual screen resolution."""
    # Get the actual physical resolution
    physical_width, physical_height = _get_display_resolution()

    # Account for macOS display scaling factor
    if IS_MACOS:
        # macOS display scaling factor
        # TODO: retrieve somehow? we could move mouse to the bottom right and then get the position
        # (but it's hacky and confusing to users)
        display_scale = 2560 / 1709

        physical_width = int(physical_width / display_scale)
        physical_height = int(physical_height / display_scale)
        logger.info(
            f"Adjusted physical resolution: {physical_width}x{physical_height} (scale: {display_scale})"
        )

    if source == _ScalingSource.API:
        if x > api_width or y > api_height:
            raise ValueError(f"Coordinates {x}, {y} are out of bounds")

        # Scale up from API coordinates to physical screen coordinates
        x_scale = physical_width / api_width
        y_scale = physical_height / api_height
        scaled_x = round(x * x_scale)
        scaled_y = round(y * y_scale)
        logger.info(f"Scaling from API ({x},{y}) to physical ({scaled_x},{scaled_y})")
        logger.info(f"Scale factors: x={x_scale:.3f}, y={y_scale:.3f}")
        return scaled_x, scaled_y
    else:  # _ScalingSource.COMPUTER
        # Scale down from physical screen coordinates to API coordinates
        x_scale = api_width / physical_width
        y_scale = api_height / physical_height
        return round(x * x_scale), round(y * y_scale)


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
        logger.info(f"Moving mouse to {x},{y}")
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
    # Default API space resolution
    # Get actual display resolution and calculate aspect ratio
    display_width, display_height = _get_display_resolution()
    display_ratio = display_width / display_height
    logger.info(
        f"Physical display resolution: {display_width}x{display_height} (ratio: {display_ratio:.3f})"
    )

    # Choose default resolution based on display ratio
    default_resolution = None
    closest_ratio_diff = float("inf")
    for name, res in MAX_SCALING_TARGETS.items():
        ratio = res["width"] / res["height"]
        ratio_diff = abs(ratio - display_ratio)
        if ratio_diff < closest_ratio_diff:
            closest_ratio_diff = ratio_diff
            default_resolution = res
            logger.info(
                f"Selected {name} as closest match: {res['width']}x{res['height']} (ratio diff: {ratio_diff:.3f})"
            )

    # Use environment variables if set, otherwise use chosen defaults
    # Fallback to XGA (4:3) if no resolution matched (shouldn't happen)
    if default_resolution is None:
        default_resolution = MAX_SCALING_TARGETS["XGA"]
        logger.info("Fallback to XGA resolution")

    width = int(os.getenv("WIDTH", str(default_resolution["width"])))
    height = int(os.getenv("HEIGHT", str(default_resolution["height"])))
    logger.info(f"Using API space resolution: {width}x{height}")

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

        # Show the API space coordinates in the output, not the physical ones
        print(f"Moved mouse to {coordinate[0]},{coordinate[1]}")
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
        path = screenshot()  # Use existing screenshot function

        # Scale if needed
        # TODO: also scale in screenshot tool for these situations
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
