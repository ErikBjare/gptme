Usage
=====

This guide covers common usage patterns and examples for gptme.

To start a new chat or select an existing one, run:

.. code-block:: bash

    gptme

This will show you a list of past chats, allowing you to select one or start a new one.

To get inspiration for your first prompt, see the :doc:`examples`.

Features
--------

.. rubric:: Tools

gptme comes with a variety of tools for different tasks:

- :ref:`tools:shell` - Execute shell commands
- :ref:`tools:python` - Run Python code
- :ref:`tools:browser` - Browse and interact with web content
- :ref:`tools:vision` - Process and analyze images

See the :doc:`tools` page for a complete list of available tools.

.. rubric:: Writing Files

You can ask the assistant to create new files or modify existing ones:

.. chat::

   User: create a new file named life.py implementing the game of life

   Assistant: Certainly! I'll create a new file named `life.py` implementing Conway's Game of Life. This implementation will use NumPy for efficient array operations and Matplotlib for visualization. Here's the code:
   ```life.py
   import numpy as np
   import matplotlib.pyplot as plt
   from matplotlib.animation import FuncAnimation
   ...
   ```

   System: Saved to life.py

.. rubric:: Making Changes

You can start chats and request changes directly from the command line. The contents of any mentioned text files will be included as context, and the assistant will generate patches to apply the requested changes:

.. code-block:: bash

   gptme 'make improvements to life.py so that dead cells fade out over time'

.. chat::

   User: make improvements to life.py so that dead cells fade out over time
   ```life.py
   ...
   ```

   Assistant: To make alive cells green and dead cells black in the Game of Life simulation, we need to modify the colormap and how we represent the cell states. Here's the updated `life.py` script with these changes:
   ```patch life.py
   ...
   ```

   System: Patch applied

.. rubric:: Browser Integration

With the :ref:`tools:browser` extras installed, the assistant can process URLs included in the prompt and interact with web content.

Commands
--------

.. TODO: use autodoc from source, like cli reference

During a chat session, you can use these slash-commands for various actions:

- ``/undo`` - Undo the last action
- ``/log`` - Show the conversation log
- ``/tools`` - Show available tools
- ``/edit`` - Edit the conversation in your editor
- ``/rename`` - Rename the conversation
- ``/fork`` - Create a copy of the conversation
- ``/summarize`` - Summarize the conversation
- ``/replay`` - Re-execute codeblocks in the conversation
- ``/help`` - Show help message
- ``/exit`` - Exit the program

Interfaces
----------

Besides the CLI, gptme can be used through:

- :ref:`server:web ui` - A web-based interface
- :doc:`bot` - GitHub bot integration

For more detailed information about specific features, check out:

- :doc:`tools` - Available tools and their usage
- :doc:`providers` - Supported LLM providers
- :doc:`server` - Web UI and API server setup
