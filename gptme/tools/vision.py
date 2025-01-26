"""
Tools for viewing images, giving the assistant vision.

Requires a model which supports vision, such as GPT-4o, Anthropic, and Llama 3.2.
"""

import tempfile
from pathlib import Path

from PIL import Image

from ..message import Message
from .base import ToolSpec


def view_image(image_path: Path | str) -> Message:
    """View an image. Large images (>1MB) will be automatically scaled down."""
    if isinstance(image_path, str):
        image_path = Path(image_path)

    if not image_path.exists():
        return Message("system", f"Image not found at {image_path}")

    file_size = image_path.stat().st_size
    MAX_SIZE = 1024 * 1024  # 1MB in bytes

    if file_size > MAX_SIZE:
        # Load and scale down the image
        with Image.open(image_path) as img:
            # Calculate scaling factor to get file size roughly under 1MB
            # This is an approximation as compression ratios vary
            scale_factor = (MAX_SIZE / file_size) ** 0.5
            new_size = tuple(int(dim * scale_factor) for dim in img.size)

            # Create a scaled version
            scaled_img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convert RGBA to RGB if needed
            if scaled_img.mode == "RGBA":
                scaled_img = scaled_img.convert("RGB")

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                scaled_img.save(tmp.name, "JPEG", quality=85)
                scaled_path = Path(tmp.name)

            return Message(
                "system",
                f"Viewing scaled image ({new_size[0]}x{new_size[1]}) from {image_path}",
                files=[scaled_path],
            )

    return Message("system", f"Viewing image at {image_path}", files=[image_path])


instructions = """
Use the `view_image` Python function with `ipython` tool to view an image file.
""".strip()

tool = ToolSpec(
    name="vision",
    desc="Viewing images",
    functions=[view_image],
)
