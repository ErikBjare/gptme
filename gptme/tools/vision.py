"""
Tools for viewing images, giving the assistant vision.

Requires a model which supports vision, such as GPT-4o, Anthropic, and Llama 3.2.
"""

from collections.abc import Generator
from pathlib import Path

from ..message import Message
from .base import ToolSpec


def view_image(image_path: Path | str) -> Generator[Message, None, None]:
    """View an image."""
    if isinstance(image_path, str):
        image_path = Path(image_path)
    yield Message("system", f"Viewing image at {image_path}", files=[image_path])


tool = ToolSpec(
    name="vision",
    desc="Tools for viewing images",
    functions=[view_image],
)
