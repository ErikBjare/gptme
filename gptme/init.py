import atexit
import logging
import readline
from typing import Any, cast

from dotenv import load_dotenv
from rich.prompt import Prompt

from .config import LLMAPIConfig, Provider, config_path, load_config, set_config_value
from .dirs import get_readline_history_file
from .llm import init_llm
from .models import get_recommended_model, set_default_model
from .tabcomplete import register_tabcomplete
from .tools import init_tools
from .util import console

logger = logging.getLogger(__name__)
_init_done = False

# if config not set, use prompt to create the init-object
# else create from config or env var


def create_from_config(override_model: str | None = None) -> LLMAPIConfig | None:
    config = load_config()
    try:
        raw_model = config.get_env("API_MODEL")
        endpoint = config.get_env("API_ENDPOINT")
        api_key = config.get_env_required("API_KEY")
        provider = config.get_env_required("API_PROVIDER")
        return LLMAPIConfig(
            endpoint=cast(Any, endpoint),
            token=api_key,
            provider=Provider(provider),
            model=override_model if override_model else raw_model,
        )
    except KeyError as e:
        logger.debug(f"Load llm config from config file error, {e}")
        return None

def create_from_prompt(override_model: str | None = None) -> LLMAPIConfig:
    """Interactively ask user for API key"""
    console.print("""You can get one at:
     - OpenAI: https://platform.openai.com/account/api-keys
     - Anthropic: https://console.anthropic.com/settings/keys
     - OpenRouter: https://openrouter.ai/settings/keys
     - or other providers that support openapi format api.
     """)
    provider = _prompt_api_provider()
    api_key = _prompt_api_key()
    endpoint = _prompt_api_endpoint(provider)
    model = _prompt_api_model()

    return LLMAPIConfig(endpoint=cast(Any, endpoint), token=api_key, provider=Provider(provider), model=override_model if override_model else model)

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
    #  if not model:
        #  model = config.get_env("MODEL")

    if (llm_cfg := create_from_config(model)) is None:
        console.print(f"No correct config found in config file {config_path} or environment variables. Please provide it in the config file or environment variables.")
        console.print("or input in below.")
        llm_cfg = create_from_prompt(model)
        llm_cfg.save_to_config()
    logger.debug("current LLMConfig: %s", llm_cfg)

    init_llm(llm_cfg)

    if not llm_cfg.model:
        llm_cfg.model = get_recommended_model(llm_cfg.provider)
        console.log(
            f"No model specified in config file ({config_path}) or env var (MODEL), using recommended model for provider: {model}"
        )
    set_default_model(llm_cfg.model, llm_cfg.provider)

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


def _prompt_api_key() -> str:  # pragma: no cover
    return input("Your OpenAI, Anthropic, or OpenRouter API key: ").strip()


def _prompt_api_endpoint(provider: Provider) -> str | None:  # pragma: no cover
    """Interactively ask user for API endpoint"""
    val = input(f"Custom API endpoint set for [{provider.value}] (leave blank if using official api):").strip()
    return val if val else None

def _prompt_api_provider() -> Provider:  # pragma: no cover
    """Interactively ask user for llm provider"""
    val= Prompt.ask("LLM Provider", choices=[x.value for x in Provider], default=Provider.OPENAI.value).strip()
    return Provider(val)

def _prompt_api_model() -> str | None:  # pragma: no cover
    """Interactively ask user for llm model"""
    val = input("LLM Model (leave blank if using recommended model):").strip()
    return val if val else None


def ask_for_api_key() -> tuple[str, str, str]:  # pragma: no cover
    """Interactively ask user for API key"""
    console.print("No API key set for OpenAI, Anthropic, or OpenRouter.")
    console.print("""You can get one at:
     - OpenAI: https://platform.openai.com/account/api-keys
     - Anthropic: https://console.anthropic.com/settings/keys
     - OpenRouter: https://openrouter.ai/settings/keys
     """)
    # Save to config
    api_key, provider, env_var = _prompt_api_key()
        
    set_config_value(f"env.{env_var}", api_key)
    console.print(f"API key saved to config at {config_path}")
    console.print(f"Successfully set up {provider} API key.")

    api_endpoint, key = _prompt_api_endpoint(provider)
    set_config_value(f"env.{key}", api_endpoint)

    return provider + "/", api_key, api_endpoint
