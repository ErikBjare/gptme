"""
Utilities for asking user confirmation and handling editable/copiable content.
"""

import logging
import sys
import termios

from rich import print
from rich.console import Console
from rich.syntax import Syntax

from . import print_bell
from .clipboard import copy, set_copytext
from .useredit import edit_text_with_editor

logger = logging.getLogger(__name__)
console = Console(log_path=False)

# Global state
override_auto = False
copiable = False
editable = False

# Editable text state
_editable_text = None
_editable_ext = None


def set_copiable():
    """Mark content as copiable."""
    global copiable
    copiable = True


def clear_copiable():
    """Clear copiable state."""
    global copiable
    copiable = False


def set_editable_text(text: str, ext: str | None = None):
    """Set the text that can be edited and optionally its file extension."""
    global _editable_text, _editable_ext, editable
    _editable_text = text
    _editable_ext = ext
    editable = True


def get_editable_text() -> str:
    """Get the current editable text."""
    global _editable_text
    if _editable_text is None:
        raise RuntimeError("No editable text set")
    return _editable_text


def get_editable_ext() -> str | None:
    """Get the file extension for the editable text."""
    global _editable_ext
    return _editable_ext


def set_edited_text(text: str):
    """Update the editable text after editing."""
    global _editable_text
    _editable_text = text


def clear_editable_text():
    """Clear the editable text and extension."""
    global _editable_text, _editable_ext, editable
    _editable_text = None
    _editable_ext = None
    editable = False


def ask_execute(question="Execute code?", default=True) -> bool:
    """Ask user for confirmation before executing code.

    Args:
        question: The question to ask
        default: The default answer if user just presses enter

    Returns:
        bool: True if user confirms execution, False otherwise
    """
    global override_auto, copiable, editable

    if override_auto:
        return True

    print_bell()  # Ring the bell just before asking for input
    termios.tcflush(sys.stdin, termios.TCIFLUSH)  # flush stdin

    # Build choice string with available options
    choicestr = f"[{'Y' if default else 'y'}/{'n' if default else 'N'}"
    if copiable:
        choicestr += "/c"
    if editable:
        choicestr += "/e"
    choicestr += "/?"
    choicestr += "]"

    answer = (
        console.input(
            f"[bold bright_yellow on red] {question} {choicestr} [/] ",
        )
        .lower()
        .strip()
    )

    if not override_auto:
        if copiable and answer == "c":
            if copy():
                print("Copied to clipboard.")
                return False
            clear_copiable()
        elif editable and answer == "e":
            edited = edit_text_with_editor(get_editable_text(), ext=get_editable_ext())
            if edited != get_editable_text():
                set_edited_text(edited)
                print("Content updated.")
                return ask_execute("Execute with changes?", default)
            return False

    # secret option to stop asking for the rest of the session
    if answer == "auto":
        return (override_auto := True)

    # secret option to ask for help
    if answer in ["help", "h", "?"]:
        lines = [
            "Options:",
            " y - execute the code",
            " n - do not execute the code",
        ]
        if copiable:
            lines.append(" c - copy the code to the clipboard")
        if editable:
            lines.append(" e - edit the code before executing")
        lines.extend(
            [
                " auto - stop asking for the rest of the session",
                f"Default is '{'y' if default else 'n'}' if answer is empty.",
            ]
        )
        helptext = "\n".join(lines)
        print(helptext)
        return ask_execute(question, default)

    return answer in (["y", "yes"] + [""] if default else [])


def print_preview(code: str, lang: str, copy: bool = False):  # pragma: no cover
    print()
    print("[bold white]Preview[/bold white]")

    if copy:
        set_copiable()
        set_copytext(code)

    # NOTE: we can set background_color="default" to remove background
    print(Syntax(code.strip("\n"), lang))
    print()
