"""
Tools for viewing images, giving the assistant vision.

Requires a model which supports vision, such as GPT-4o, Anthropic, and Llama 3.2.
"""

from pathlib import Path

from ..message import Message
from .base import ToolSpec


def view_image(image_path: Path | str) -> Message:
    """View an image."""
    if isinstance(image_path, str):
        image_path = Path(image_path)
    if not image_path.exists():
        return Message("system", f"Image not found at {image_path}")
    return Message("system", f"Viewing image at {image_path}", files=[image_path])


tool = ToolSpec(
    name="vision",
    desc="Tools for viewing images",
    functions=[view_image],
)
