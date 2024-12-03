"""Test configuration and shared fixtures."""

from contextlib import contextmanager
import os
import pytest
import tempfile

from gptme.tools.rag import _HAS_RAG


def pytest_sessionstart(session):
    # Download the embedding model before running tests.
    download_model()


def download_model():
    if not _HAS_RAG:
        return

    # downloads the model if it doesn't exist
    from chromadb.utils import embedding_functions  # type: ignore # fmt: skip

    ef = embedding_functions.DefaultEmbeddingFunction()
    if ef:
        ef._download_model_if_not_exists()  # type: ignore


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
