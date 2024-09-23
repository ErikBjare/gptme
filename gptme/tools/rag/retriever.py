import faiss
import numpy as np
import logging
import time
import sys
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from gptme.dirs import get_cache_dir

logging.basicConfig(level=logging.INFO)

data_dir = get_cache_dir() / "rag"

def load_index_and_metadata() -> Tuple[faiss.Index, List[Tuple[str, str, int, int]]]:
    start_time = time.time()
    index = faiss.read_index(str(data_dir / "code_index.faiss"))
    metadata = np.load(str(data_dir / "code_metadata.npy"), allow_pickle=True)
    logging.info(f"Index and metadata loaded in {time.time() - start_time:.2f} seconds.")
    return index, metadata.tolist()

def retrieve_relevant_chunks(query: str, index: faiss.Index, metadata: List[Tuple[str, str, int, int]], model: SentenceTransformer, top_k: int = 5) -> List[Tuple[str, str, int, int, float]]:
    start_time = time.time()
    query_embedding = model.encode([query])
    logging.info(f"Query embedding created in {time.time() - start_time:.2f} seconds.")
    
    start_time = time.time()
    distances, indices = index.search(query_embedding.astype('float32'), top_k)
    logging.info(f"Index search completed in {time.time() - start_time:.2f} seconds.")
    
    relevant_chunks = [(metadata[idx][0], metadata[idx][1], metadata[idx][2], metadata[idx][3], distances[0][i]) for i, idx in enumerate(indices[0])]
    return relevant_chunks

def format_chunk(chunk: Tuple[str, str, int, int, float]) -> str:
    file_path, code, start_line, end_line, distance = chunk
    return f"File: {file_path} (Lines {start_line}-{end_line}, Distance: {distance:.4f})\n{code}\n{'='*80}"

def main():
    if len(sys.argv) < 2:
        logging.error("Please provide a query as a command-line argument.")
        sys.exit(1)
    
    query = sys.argv[1]
    logging.info(f"Query received: {query}")
    
    logging.info("Loading model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    logging.info("Model loaded.")
    
    logging.info("Loading index and metadata...")
    index, metadata = load_index_and_metadata()
    
    logging.info("Retrieving relevant chunks...")
    relevant_chunks = retrieve_relevant_chunks(query, index, metadata, model)
    logging.info("Relevant chunks retrieved.")
    
    for chunk in relevant_chunks:
        print(format_chunk(chunk))

if __name__ == '__main__':
    main()
