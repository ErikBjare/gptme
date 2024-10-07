import atexit
import logging
import readline

from dotenv import load_dotenv

from .config import config_path, load_config, set_config_value
from .dirs import get_readline_history_file
from .llm import init_llm
from .models import PROVIDERS, get_recommended_model, set_default_model
from .tabcomplete import register_tabcomplete
from .tools import init_tools
from .util import console

logger = logging.getLogger(__name__)
_init_done = False


def init(model: str | None, interactive: bool, tool_allowlist: list[str] | None):
    global _init_done
    if _init_done:
        logger.warning("init() called twice, ignoring")
        return
    _init_done = True

    # init
    logger.debug("Started")
    load_dotenv()

    config = load_config()

    # get from config
    if not model:
        model = config.get_env("MODEL")

    if not model:  # pragma: no cover
        # auto-detect depending on if OPENAI_API_KEY or ANTHROPIC_API_KEY is set
        if config.get_env("OPENAI_API_KEY"):
            console.log("Found OpenAI API key, using OpenAI provider")
            model = "openai"
        elif config.get_env("ANTHROPIC_API_KEY"):
            console.log("Found Anthropic API key, using Anthropic provider")
            model = "anthropic"
        elif config.get_env("OPENROUTER_API_KEY"):
            console.log("Found OpenRouter API key, using OpenRouter provider")
            model = "openrouter"
        # ask user for API key
        elif interactive:
            model, _ = ask_for_api_key()

    # fail
    if not model:
        raise ValueError("No API key found, couldn't auto-detect provider")

    if any(model.startswith(f"{provider}/") for provider in PROVIDERS):
        provider, model = model.split("/", 1)
    else:
        provider, model = model, None

    # set up API_KEY and API_BASE, needs to be done before loading history to avoid saving API_KEY
    init_llm(provider)

    if not model:
        model = get_recommended_model(provider)
        console.log(
            f"No model specified, using recommended model for provider: {model}"
        )
    set_default_model(model)

    if interactive:
        _load_readline_history()

        # for some reason it bugs out shell tests in CI
        register_tabcomplete()

    init_tools(tool_allowlist)


def init_logging(verbose):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    # set httpx logging to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)


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


def _load_readline_history() -> None:  # pragma: no cover
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


def _prompt_api_key() -> tuple[str, str, str]:  # pragma: no cover
    api_key = input("Your OpenAI, Anthropic, or OpenRouter API key: ").strip()
    if api_key.startswith("sk-ant-"):
        return api_key, "anthropic", "ANTHROPIC_API_KEY"
    elif api_key.startswith("sk-or-"):
        return api_key, "openrouter", "OPENROUTER_API_KEY"
    elif api_key.startswith("sk-"):
        return api_key, "openai", "OPENAI_API_KEY"
    else:
        console.print("Invalid API key format. Please try again.")
        return _prompt_api_key()


def ask_for_api_key():  # pragma: no cover
    """Interactively ask user for API key"""
    console.print("No API key set for OpenAI, Anthropic, or OpenRouter.")
    console.print(
        """You can get one at:
 - OpenAI: https://platform.openai.com/account/api-keys
 - Anthropic: https://console.anthropic.com/settings/keys
 - OpenRouter: https://openrouter.ai/settings/keys
 """
    )
    # Save to config
    api_key, provider, env_var = _prompt_api_key()
    set_config_value(f"env.{env_var}", api_key)
    console.print(f"API key saved to config at {config_path}")
    console.print(f"Successfully set up {provider} API key.")
    return provider, api_key
