import ast
import json
import logging
import os
import subprocess
import textwrap

import faiss
import numpy as np
import pathspec
from gptme.dirs import get_cache_dir
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)

data_dir = get_cache_dir() / "rag"
os.makedirs(data_dir, exist_ok=True)

metadata_file = data_dir / "index_metadata.json"


def get_git_root(path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to find git root: {result.stderr.strip()}")
    return result.stdout.strip()


def load_gitignore_patterns(repo_root: str) -> pathspec.PathSpec:
    gitignore_path = os.path.join(repo_root, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    return pathspec.PathSpec([])


def load_code_files(
    directory: str, ignore_patterns: pathspec.PathSpec
) -> list[tuple[str, str]]:
    code_files = []
    ignored_files_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), directory)
            if ignore_patterns.match_file(file_path):
                ignored_files_count += 1
                continue
            if file.endswith(
                (".py", ".js", ".ts", ".html", ".css")
            ):  # Add more file types as needed
                logging.info(f"Processing file: {file_path}")
                with open(os.path.join(root, file), encoding="utf-8") as f:
                    code_files.append((file_path, f.read()))
    logging.info(f"Total files ignored: {ignored_files_count}")
    return code_files


def chunk_code_syntactically(
    code: str, file_path: str
) -> list[tuple[str, str, int, int]]:
    chunks = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If parsing fails, fall back to simple line-based chunking
        lines = code.split("\n")
        for i in range(0, len(lines), 10):
            chunk = "\n".join(lines[i : i + 10])
            chunks.append((file_path, chunk, i + 1, min(i + 10, len(lines))))
        return chunks

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            start_lineno = node.lineno - 1
            end_lineno = (
                node.end_lineno
                if hasattr(node, "end_lineno")
                else len(code.split("\n"))
            )

            # Include decorators
            if hasattr(node, "decorator_list") and node.decorator_list:
                start_lineno = node.decorator_list[0].lineno - 1

            chunk = code.split("\n")[start_lineno:end_lineno]
            chunk_code = textwrap.dedent("\n".join(chunk))

            chunks.append((file_path, chunk_code, start_lineno + 1, end_lineno))

    return chunks


def chunk_code_line_based(
    code: str, file_path: str, chunk_size: int = 20, language: str = "generic"
) -> list[tuple[str, str, int, int]]:
    chunks = []
    lines = code.split("\n")
    for i in range(0, len(lines), chunk_size):
        chunk = "\n".join(lines[i : i + chunk_size])
        chunks.append((file_path, chunk, i + 1, min(i + chunk_size, len(lines))))
    return chunks


def create_index(
    code_files: list[tuple[str, str]], model: SentenceTransformer
) -> tuple[faiss.Index, list[tuple[str, str, int, int]]]:
    chunks = []
    for file_path, code in code_files:
        logging.info(f"Processing file: {file_path}")
        if file_path.endswith(".py"):
            chunks.extend(chunk_code_syntactically(code, file_path))
        elif file_path.endswith(".ts"):
            logging.info(f"Processing TypeScript file: {file_path}")
            chunks.extend(chunk_code_line_based(code, file_path, language="typescript"))
        else:
            chunks.extend(chunk_code_line_based(code, file_path))
    logging.info(f"Total chunks created: {len(chunks)}")

    texts = [chunk[1] for chunk in chunks]
    batch_size = 64  # Adjust batch size as needed
    embeddings = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    for i in range(total_batches):
        batch_texts = texts[i * batch_size : (i + 1) * batch_size]
        if i % 10 == 0 or i == total_batches - 1:
            logging.info(f"Encoding batch {i + 1}/{total_batches}")
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.append(batch_embeddings)
    embeddings = np.vstack(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))

    return index, chunks


def load_metadata() -> dict[str, float]:
    if metadata_file.exists():
        with open(metadata_file, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_metadata(metadata: dict[str, float]):
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f)


def main():
    logging.info("Loading model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    logging.info("Model loaded.")

    logging.info("Finding Git root...")
    repo_root = get_git_root(".")
    logging.info(f"Git root found: {repo_root}")

    logging.info("Loading .gitignore patterns...")
    ignore_patterns = load_gitignore_patterns(repo_root)
    logging.info(".gitignore patterns loaded.")

    logging.info("Loading code files...")
    code_files = load_code_files(repo_root, ignore_patterns)
    logging.info(f"Total code files loaded: {len(code_files)}")

    logging.info("Loading previous metadata...")
    previous_metadata = load_metadata()

    logging.info("Checking for changes...")
    changed_files = []
    current_metadata = {}
    for file_path, code in code_files:
        current_metadata[file_path] = os.path.getmtime(file_path)
        if (
            file_path not in previous_metadata
            or previous_metadata[file_path] != current_metadata[file_path]
        ):
            changed_files.append((file_path, code))

    if not changed_files:
        logging.info("No changes detected. Exiting.")
        return

    logging.info(f"Files changed: {len(changed_files)}")

    logging.info("Creating index...")
    index, chunks = create_index(changed_files, model)
    logging.info("Index created.")

    logging.info("Saving index and metadata...")
    faiss.write_index(index, str(data_dir / "code_index.faiss"))
    logging.info("Index saved.")

    logging.info("Saving metadata...")
    np.save(str(data_dir / "code_metadata.npy"), chunks)
    save_metadata(current_metadata)
    logging.info("Metadata saved.")


if __name__ == "__main__":
    main()
