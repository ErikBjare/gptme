from ..base import ToolSpec

from .indexer import main as main_indexer
from .retriever import main as main_retriever


def retrieve():
    # TODO: only re-index if necessary
    main_indexer()
    return main_retriever()


tool = ToolSpec(
    name="rag",
    desc="A tool for retrieving code, documents, and other files.",
    functions=[retrieve],
)
