"""
Server for gptme.
"""

from .api import create_app
from .cli import main

__all__ = ["main", "create_app"]
