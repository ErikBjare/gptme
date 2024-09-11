"""
Server for gptme.
"""

from .api import create_app, main

__all__ = ["main", "create_app"]
