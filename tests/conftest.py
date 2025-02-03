"""Test configuration and shared fixtures."""

import os
import tempfile
from contextlib import contextmanager

import pytest
from gptme.config import get_config
from gptme.tools import clear_tools, init_tools
from gptme.tools.rag import _has_gptme_rag


def has_api_key() -> bool:
    """Check if any API key is configured."""
    config = get_config()
    # Check for any configured API keys
    return bool(
        config.get_env("OPENAI_API_KEY", "")
        or config.get_env("ANTHROPIC_API_KEY", "")
        or config.get_env("OPENROUTER_API_KEY", "")
        or config.get_env("DEEPSEEK_API_KEY", "")
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_api: mark test as requiring an API key",
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests marked as requiring API key if no key is configured."""
    if not has_api_key():
        # Set environment variables to override LLM provider config
        os.environ["MODEL"] = "local/test"
        os.environ["OPENAI_BASE_URL"] = "http://localhost:666"

        # Skip tests that require an API key if no key is configured
        skip_api = pytest.mark.skip(reason="No API key configured")
        for item in items:
            if "requires_api" in item.keywords:
                item.add_marker(skip_api)


def pytest_sessionstart(session):
    # Download the embedding model before running tests.
    download_model()


def download_model():
    if not _has_gptme_rag():
        return

    try:
        # downloads the model if it doesn't exist
        from chromadb.utils import embedding_functions  # type: ignore # fmt: skip
    except ImportError:
        return

    ef = embedding_functions.DefaultEmbeddingFunction()
    if ef:
        ef._download_model_if_not_exists()  # type: ignore


@pytest.fixture(autouse=True)
def clear_tools_before():
    # Clear all tools and cache to prevent test conflicts
    clear_tools()
    init_tools.cache_clear()


@pytest.fixture
def temp_file():
    @contextmanager
    def _temp_file(content):
        # Create a temporary file with the given content
        temporary_file = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        try:
            temporary_file.write(content)
            temporary_file.flush()
            temporary_file.close()
            yield temporary_file.name  # Yield the path to the temporary file
        finally:
            # Delete the temporary file to ensure cleanup
            if os.path.exists(temporary_file.name):
                os.unlink(temporary_file.name)

    return _temp_file
