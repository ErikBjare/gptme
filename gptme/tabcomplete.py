import logging
import readline
from functools import lru_cache
from pathlib import Path

from .commands import COMMANDS

logger = logging.getLogger(__name__)


def register_tabcomplete() -> None:  # pragma: no cover
    """Register tab completion for readline."""
    logger.debug("Setting up tab completion")
    readline.set_completer(_completer)
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    if "libedit" in readline.__doc__:  # type: ignore
        logger.debug("Found libedit readline")
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        logger.debug("Found gnu readline")
        readline.parse_and_bind("tab: complete")


def _completer(text: str, state: int) -> str | None:  # pragma: no cover
    """Tab completion for readline."""
    return _matches(text)[state]


def _process_completion(p: Path) -> str:
    p = Path(str(p).replace(str(Path.cwd()) + "/", ""))
    p = Path(str(p).replace(str(Path.home()), "~/"))
    if p.expanduser().exists() and p.expanduser().is_dir():
        return str(p) + "/"
    else:
        return str(p)


@lru_cache(maxsize=1)
def _matches(text: str) -> list[str]:
    """Returns a list of matches for text to complete."""
    logger.debug(f"Matching text: {text}")
    current_dir_contents = list(Path.cwd().iterdir())
    logger.debug(f"Current directory contents: {current_dir_contents}")

    if text.startswith("/"):
        all_commands = [f"/{cmd}" for cmd in COMMANDS]
        if not text[1:]:
            return all_commands
        else:
            matching_files = [
                _process_completion(p) for p in Path("/").glob(text[1:] + "*")
            ]
            return [
                cmd for cmd in all_commands if cmd.startswith(text)
            ] + matching_files

    elif text.startswith("../"):
        return [_process_completion(p) for p in Path("..").glob(text[3:] + "*")]

    elif text.startswith("~/"):
        return [_process_completion(p) for p in Path.home().glob(text[2:] + "*")]

    else:
        return [_process_completion(p) for p in Path.cwd().glob(text + "*")]
