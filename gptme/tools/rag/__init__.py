import faiss
import numpy as np
from gptme.dirs import get_cache_dir
from sentence_transformers import SentenceTransformer

from ..base import ToolSpec
from .indexer import main as main_indexer
from .retriever import retrieve_relevant_chunks

data_dir = get_cache_dir() / "rag"


def retrieve(query: str, top_k: int = 5):
    # TODO: Add a check if the index exists
    main_indexer()

    # Load the model, index, and metadata only once
    model = SentenceTransformer("all-MiniLM-L6-v2")
    index = faiss.read_index(str(data_dir / "code_index.faiss"))
    metadata = np.load(str(data_dir / "code_metadata.npy"), allow_pickle=True).tolist()

    # Retrieve relevant chunks
    relevant_chunks = retrieve_relevant_chunks(query, index, metadata, model, top_k)

    # Format the results
    formatted_results = []
    for chunk in relevant_chunks:
        file_path, code, start_line, end_line, distance = chunk
        formatted_chunk = f"File: {file_path} (Lines {start_line}-{end_line}, Distance: {distance:.4f})\n{code}\n{'='*80}"
        formatted_results.append(formatted_chunk)

    return "\n\n".join(formatted_results)


tool = ToolSpec(
    name="rag",
    desc="A tool for retrieving relevant code snippets from the project.",
    functions=[retrieve],
)
