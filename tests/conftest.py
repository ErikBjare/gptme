"""Test configuration and shared fixtures."""

from gptme.tools.rag import _HAS_RAG


def pytest_sessionstart(session):
    # Download the embedding model before running tests.
    download_model()


def download_model():
    if not _HAS_RAG:
        return

    # downloads the model if it doesn't exist
    from chromadb.utils import embedding_functions  # fmt: skip

    ef = embedding_functions.DefaultEmbeddingFunction()
    if ef:
        ef._download_model_if_not_exists()  # type: ignore
