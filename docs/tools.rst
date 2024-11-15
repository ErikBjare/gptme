Tools
=====

Tools available in gptme.

The tools can be grouped into the following categories:

- Execution

  - `Shell`_
  - `Python`_
  - `Tmux`_
  - `Subagent`_

- Files

  - `Read`_
  - `Save`_
  - `Patch`_

- Network

  - `Browser`_

- Vision

  - `Screenshot`_
  - `Vision`_
  - `Computer`_

- Chat management

  - `Chats`_

- Context management

  - `RAG`_

Shell
-----

.. automodule:: gptme.tools.shell
    :members:
    :noindex:

Python
------

.. automodule:: gptme.tools.python
    :members:
    :noindex:

Tmux
----

.. automodule:: gptme.tools.tmux
    :members:
    :noindex:

Subagent
--------

.. automodule:: gptme.tools.subagent
    :members:
    :noindex:

Read
----

.. automodule:: gptme.tools.read
    :members:
    :noindex:

Save
----

.. automodule:: gptme.tools.save
    :members:
    :noindex:

Patch
-----

.. automodule:: gptme.tools.patch
    :members:
    :noindex:

Screenshot
----------

.. automodule:: gptme.tools.screenshot
    :members:
    :noindex:

Browser
-------

.. automodule:: gptme.tools.browser
    :members:
    :noindex:

Vision
------

.. automodule:: gptme.tools.vision
    :members:
    :noindex:

Chats
-----

.. automodule:: gptme.tools.chats
    :members:
    :noindex:

Computer
--------

.. automodule:: gptme.tools.computer
    :members:
    :noindex:

The computer tool provides direct interaction with the desktop environment through X11, allowing for:

- Keyboard input simulation
- Mouse control (movement, clicks, dragging)
- Screen capture with automatic scaling
- Cursor position tracking

To use the computer tool, see the instructions for :doc:`server`.

Example usage::

    # Type text
    computer(action="type", text="Hello, World!")

    # Move mouse and click
    computer(action="mouse_move", coordinate=(100, 100))
    computer(action="left_click")

    # Take screenshot
    computer(action="screenshot")

    # Send keyboard shortcuts
    computer(action="key", text="Control_L+c")

The tool automatically handles screen resolution scaling to ensure optimal performance with LLM vision capabilities.

.. include:: computer-use-warning.rst

RAG
---

.. automodule:: gptme.tools.rag
    :members:
    :noindex:

The RAG (Retrieval-Augmented Generation) tool provides context-aware assistance by indexing and searching project documentation.

Installation
^^^^^^^^^^^

The RAG tool requires the ``gptme-rag`` package. Install it with::

    pip install "gptme[rag]"

Configuration
^^^^^^^^^^^^

Configure RAG in your ``gptme.toml``::

    [rag]
    # Storage configuration
    index_path = "~/.cache/gptme/rag"  # Where to store the index
    collection = "gptme_docs"          # Collection name for documents

    # Context enhancement settings
    max_tokens = 2000                  # Maximum tokens for context window
    auto_context = true               # Enable automatic context enhancement
    min_relevance = 0.5               # Minimum relevance score for including context
    max_results = 5                   # Maximum number of results to consider

    # Cache configuration
    [rag.cache]
    max_embeddings = 10000            # Maximum number of cached embeddings
    max_searches = 1000               # Maximum number of cached search results
    embedding_ttl = 86400             # Embedding cache TTL in seconds (24h)
    search_ttl = 3600                # Search cache TTL in seconds (1h)

Features
^^^^^^^^

1. Manual Search and Indexing
   - Index project documentation with ``rag index``
   - Search indexed documents with ``rag search``
   - Check index status with ``rag status``

2. Automatic Context Enhancement
   - Automatically adds relevant context to user messages
   - Retrieves semantically similar documents
   - Manages token budget to avoid context overflow
   - Preserves conversation flow with hidden context messages

3. Performance Optimization
   - Intelligent caching system for embeddings and search results
   - Configurable cache sizes and TTLs
   - Automatic cache invalidation
   - Memory-efficient storage

Example Usage
^^^^^^^^^^^^

1. Index your project::

    ```rag index ./docs ./src```

2. Search for specific information::

    ```rag search python functions```

3. Automatic Context Enhancement:

   When you ask a question, gptme automatically:
   - Searches for relevant documentation
   - Adds context as hidden system messages
   - Maintains conversation history

   Example conversation with automatic context::

    User: How do I use the patch tool?
    [Hidden context from patch.py docs added automatically]
    Assistant: The patch tool allows you to modify files...

Benefits
^^^^^^^^

- Better informed responses through relevant documentation
- Reduced need for manual context inclusion
- Automatic token management
- Seamless integration with conversation flow

Usage
^^^^^

Index documents::

    ```rag index ./docs```

Search the index::

    ```rag search python functions```

Check index status::

    ```rag status```

The tool automatically handles document processing, embedding generation, and semantic search to provide relevant context for your queries.
