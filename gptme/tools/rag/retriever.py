import faiss
import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from gptme.dirs import get_cache_dir

logging.basicConfig(level=logging.INFO)

data_dir = get_cache_dir() / "rag"


def load_index_and_metadata() -> tuple[faiss.Index, list[tuple[str, str, int, int]]]:
    index = faiss.read_index(str(data_dir / "code_index.faiss"))
    metadata = np.load(str(data_dir / "code_metadata.npy"), allow_pickle=True)
    return index, metadata.tolist()


def retrieve_relevant_chunks(
    query: str,
    index: faiss.Index,
    metadata: list[tuple[str, str, int, int]],
    model: SentenceTransformer,
    top_k: int = 5,
) -> list[tuple[str, str, int, int, float]]:
    query_embedding = model.encode([query])
    distances, indices = index.search(query_embedding.astype("float32"), top_k)
    return [(*metadata[idx], distances[0][i]) for i, idx in enumerate(indices[0])]


def format_chunk(chunk: tuple[str, str, int, int, float]) -> str:
    file_path, code, start_line, end_line, distance = chunk
    return f"File: {file_path} (Lines {start_line}-{end_line}, Distance: {distance:.4f})\n{code}\n{'='*80}"


def retrieve(query: str, top_k: int = 5) -> str:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    index, metadata = load_index_and_metadata()
    relevant_chunks = retrieve_relevant_chunks(query, index, metadata, model, top_k)
    return "\n\n".join(format_chunk(chunk) for chunk in relevant_chunks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Please provide a query as a command-line argument.")
        sys.exit(1)
    print(retrieve(sys.argv[1]))
