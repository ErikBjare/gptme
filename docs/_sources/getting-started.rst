Getting Started
===============

This guide will assist you in beginning your journey with gptme.

Installation
------------

To install gptme, we recommend using pipx:

.. code-block:: bash

    pipx install gptme

If pipx is not installed, you can install it using pip:

.. code-block:: bash

    pip install --user pipx

Usage
-----

To initiate a new chat or select an existing one, execute:

.. code-block:: bash

    gptme

This will show you a list of past chats, allowing you to select one or start a new one.

.. rubric:: Writing a file

You can then interact with the assistant. Lets start by asking it to write code.

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

The assistant will prompt for your confirmation and save the file, as requested.

.. rubric:: Making changes

We can also start chats and request changes directly from the command line. The contents of any mentioned text files will be included as context, and the assistant will generate patches to apply the requested changes:

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

.. note::
    With the :ref:`tools:browser` extras installed, the assistant can also process URLs included in the prompt.

More tools
**********

You can read about all the other tools on the :doc:`tools` page.

Including :ref:`tools:shell`, :ref:`tools:python`, how to set up :ref:`tools:browser`, and use :ref:`tools:vision`.

Interfaces
**********

There are several ways to interact with gptme:

- :doc:`CLI <cli>`
- :ref:`server:web ui`
- :doc:`bot`

Support
-------

For any issues, please visit our `issue tracker <https://github.com/ErikBjare/gptme/issues>`_.
