import atexit
import logging
from functools import lru_cache
from pathlib import Path

from .commands import COMMANDS
from .dirs import get_readline_history_file

# noreorder
try:
    import readline  # fmt: skip
except ImportError:  # pragma: no cover
    raise Exception(
        "Unsupported platform: readline not available.\nIf you are on Windows, use WSL or Docker to run gptme."
    ) from None


logger = logging.getLogger(__name__)
init = False


# default history if none found
# NOTE: there are also good examples in the integration tests
history_examples = [
    "What is love?",
    "Have you heard about an open-source app called ActivityWatch?",
    "Explain 'Attention is All You Need' in the style of Andrej Karpathy.",
    "Explain how public-key cryptography works as if I'm five.",
    "Write a Python script that prints the first 100 prime numbers.",
    "Find all TODOs in the current git project",
]


def add_history(line: str) -> None:  # pragma: no cover
    if not init:
        load_readline_history()

    readline.add_history(line)
    readline.write_history_file(get_readline_history_file())


def load_readline_history() -> None:  # pragma: no cover
    global init
    if init:
        return

    logger.debug("Loading history")
    # enabled by default in CPython, make it explicit
    readline.set_auto_history(True)
    # had some bugs where it grew to gigs, which should be fixed, but still good precaution
    readline.set_history_length(100)
    history_file = get_readline_history_file()
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        for line in history_examples:
            readline.add_history(line)
    except Exception:
        logger.exception("Failed to load history file")

    atexit.register(readline.write_history_file, history_file)
    init = True


def register_tabcomplete() -> None:  # pragma: no cover
    """Register tab completion for readline."""

    # set up tab completion
    logger.debug("Setting up tab completion")
    readline.set_completer(_completer)
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    # https://github.com/python/cpython/issues/102130#issuecomment-1439242363
    if "libedit" in readline.__doc__:  # type: ignore
        logger.debug("Found libedit readline")
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        logger.debug("Found gnu readline")
        readline.parse_and_bind("tab: complete")


def _completer(text: str, state: int) -> str | None:  # pragma: no cover
    """
    Tab completion for readline.

    Completes /commands and paths in arguments.

    The completer function is called as function(text, state), for state in 0, 1, 2, …, until it returns a non-string value.
    It should return the next possible completion starting with text.
    """
    return _matches(text)[state]


def _process_completion(p: Path) -> str:
    # Strip cwd from path
    p = Path(str(p).replace(str(Path.cwd()) + "/", ""))

    # Use ~/ if path is in home dir
    p = Path(str(p).replace(str(Path.home()), "~/"))

    # If path is a directory, add trailing slash
    if p.expanduser().exists() and p.expanduser().is_dir():
        return str(p) + "/"
    else:
        return str(p)


@lru_cache(maxsize=1)
def _matches(text: str) -> list[str]:
    """Returns a list of matches for text to complete."""

    # if text starts with /, complete with commands or files as absolute paths
    if text.startswith("/"):
        # if no text, list all commands
        all_commands = [f"/{cmd}" for cmd in COMMANDS]
        if not text[1:]:
            return all_commands
        # else, filter commands with text
        else:
            matching_files = [
                _process_completion(p) for p in Path("/").glob(text[1:] + "*")
            ]
            return [
                cmd for cmd in all_commands if cmd.startswith(text)
            ] + matching_files

    # if text starts with ../, complete with parent dir
    elif text.startswith("../"):
        return [_process_completion(p) for p in Path("..").glob(text[3:] + "*")]

    # if text starts with ~/, complete with home dir
    elif text.startswith("~/"):
        return [_process_completion(p) for p in Path.home().glob(text[2:] + "*")]

    # else, complete with files in current dir
    else:
        return [_process_completion(p) for p in Path.cwd().glob(text + "*")]
