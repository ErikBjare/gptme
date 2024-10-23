import logging
from typing import cast

from dotenv import load_dotenv

from .config import config_path, load_config, set_config_value
from .llm import init_llm
from .models import (
    PROVIDERS,
    Provider,
    get_recommended_model,
    set_default_model,
)
from .readline import load_readline_history, register_tabcomplete
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
        provider, model = cast(tuple[Provider, str], model.split("/", 1))
    else:
        provider, model = cast(tuple[Provider, str], (model, None))

    # set up API_KEY and API_BASE, needs to be done before loading history to avoid saving API_KEY
    model = model or get_recommended_model(provider)
    console.log(f"Using model: {provider}/{model}")
    init_llm(provider)
    set_default_model(model)

    if interactive:
        load_readline_history()

        # for some reason it bugs out shell tests in CI
        register_tabcomplete()

    init_tools(tool_allowlist)


def init_logging(verbose):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    # set httpx logging to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)


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
