import atexit
import logging
import readline

from dotenv import load_dotenv

from .dirs import get_readline_history_file
from .llm import init_llm
from .models import set_default_model
from .tabcomplete import register_tabcomplete
from .tools import init_tools

logger = logging.getLogger(__name__)
_init_done = False


def init(llm: str, model: str, interactive: bool):
    global _init_done
    if _init_done:
        logger.warning("init() called twice, ignoring")
        return
    _init_done = True

    # init
    logger.debug("Started")
    load_dotenv()

    # set up API_KEY and API_BASE, needs to be done before loading history to avoid saving API_KEY
    init_llm(llm, interactive)
    set_default_model(model)

    if interactive:  # pragma: no cover
        _load_readline_history()

        # for some reason it bugs out shell tests in CI
        register_tabcomplete()

    init_tools()


def init_logging(verbose):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


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


def _load_readline_history() -> None:
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

    atexit.register(readline.write_history_file, history_file)
