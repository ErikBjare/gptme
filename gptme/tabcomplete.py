import readline
from functools import lru_cache
from pathlib import Path

from .commands import CMDFIX, COMMANDS


def register_tabcomplete() -> None:
    """Register tab completion for readline."""

    # set up tab completion
    print("Setting up tab completion")
    readline.set_completer(_completer)
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    # https://github.com/python/cpython/issues/102130#issuecomment-1439242363
    if "libedit" in readline.__doc__:  # type: ignore
        print("Found libedit readline")
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        print("Found gnu readline")
        readline.parse_and_bind("tab: complete")


def _completer(text: str, state: int) -> str | None:
    """
    Tab completion for readline.

    Completes /commands and paths in arguments.

    The completer function is called as function(text, state), for state in 0, 1, 2, …, until it returns a non-string value.
    It should return the next possible completion starting with text.
    """
    return _matches(text)[state]


@lru_cache(maxsize=1)
def _matches(text: str) -> list[str]:
    """Returns a list of matches for text to complete."""

    # if text starts with /, complete with commands or files as absolute paths
    if text.startswith("/"):
        # if no text, list all commands
        all_commands = [f"{CMDFIX}{cmd}" for cmd in COMMANDS if cmd != "help"]
        if not text[1:]:
            return all_commands
        # else, filter commands with text
        else:
            matching_files = [str(p) for p in Path("/").glob(text[1:] + "*")]
            return [
                cmd for cmd in all_commands if cmd.startswith(text)
            ] + matching_files

    # if text starts with ., complete with current dir
    elif text.startswith("."):
        if not text[1:]:
            return [str(Path.cwd())]
        else:
            all_files = [str(p) for p in Path.cwd().glob("*")]
            return [f for f in all_files if f.startswith(text)]

    # if text starts with ../, complete with parent dir
    elif text.startswith(".."):
        if not text[2:]:
            return [str(Path.cwd().parent)]
        else:
            return [str(p) for p in Path.cwd().parent.glob(text[2:] + "*")]

    # else, complete with files in current dir
    else:
        if not text:
            return [str(Path.cwd())]
        else:
            return [str(p) for p in Path.cwd().glob(text + "*")]
