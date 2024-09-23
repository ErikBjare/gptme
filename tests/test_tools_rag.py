import os
import tempfile
import pytest
import faiss
import pathspec
from sentence_transformers import SentenceTransformer
from gptme.tools.rag.indexer import (
    load_code_files,
    chunk_code_syntactically,
    chunk_code_line_based,
    create_index,
)
from gptme.tools.rag.retriever import retrieve_relevant_chunks


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def model():
    return SentenceTransformer("all-MiniLM-L6-v2")


def test_load_code_files(temp_dir):
    # Create test files
    os.makedirs(os.path.join(temp_dir, "subdir"))
    with open(os.path.join(temp_dir, "file1.py"), "w") as f:
        f.write("print('Hello, world!')")
    with open(os.path.join(temp_dir, "subdir", "file2.py"), "w") as f:
        f.write("def foo():\n    return 'bar'")
    with open(os.path.join(temp_dir, ".gitignore"), "w") as f:
        f.write("*.pyc\n__pycache__\n")

    # Load code files
    code_files = load_code_files(
        temp_dir,
        pathspec.PathSpec.from_lines(
            "gitwildmatch", open(os.path.join(temp_dir, ".gitignore"))
        ),
    )

    # Check that the correct files are loaded
    assert len(code_files) == 2
    assert "file1.py" in [os.path.basename(cf[0]) for cf in code_files]
    assert "file2.py" in [os.path.basename(cf[0]) for cf in code_files]


def test_chunk_code_syntactically():
    code = """
def foo():
    \"\"\"This is a docstring.\"\"\"
    print('Hello, world!')

class Bar:
    def baz(self):
        pass
"""
    chunks = chunk_code_syntactically(code, "test.py")
    assert len(chunks) == 3
    assert "def foo()" in chunks[0][1]
    assert "class Bar" in chunks[1][1]


def test_chunk_code_line_based():
    code = """
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', () => {
  const count = ref(0)
  const doubleCount = computed(() => count.value * 2)
  function increment() {
    count.value++
  }

  return { count, doubleCount, increment }
})
"""
    chunks = chunk_code_line_based(code, "test.ts", language="typescript")
    assert len(chunks) == 1
    assert "function increment()" in chunks[0][1]


def test_create_index(temp_dir, model):
    # Create test files
    os.makedirs(os.path.join(temp_dir, "subdir"))
    with open(os.path.join(temp_dir, "file1.py"), "w") as f:
        f.write("print('Hello, world!')")
    with open(os.path.join(temp_dir, "subdir", "file2.py"), "w") as f:
        f.write("def foo():\n    return 'bar'")

    # Load code files
    code_files = load_code_files(temp_dir, pathspec.PathSpec([]))

    # Create index
    index, metadata = create_index(code_files, model)

    # Check that the index and metadata are created correctly
    assert isinstance(index, faiss.Index)
    assert len(metadata) == 1


def test_retrieve_relevant_chunks(temp_dir, model):
    # Create test files
    os.makedirs(os.path.join(temp_dir, "subdir"))
    with open(os.path.join(temp_dir, "file1.py"), "w") as f:
        f.write("print('Hello, world!')")
    with open(os.path.join(temp_dir, "subdir", "file2.py"), "w") as f:
        f.write("def foo():\n    return 'bar'")

    # Load code files
    code_files = load_code_files(temp_dir, pathspec.PathSpec([]))

    # Create index
    index, metadata = create_index(code_files, model)

    # Retrieve relevant chunks
    query = "foo"
    relevant_chunks = retrieve_relevant_chunks(query, index, metadata, model)

    # Check that the relevant chunks are retrieved correctly
    assert len(relevant_chunks) > 0
    assert "def foo()" in relevant_chunks[0][1]
