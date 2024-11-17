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
