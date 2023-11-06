Getting started
===============

Here we will help you get started with effectively using gptme.


Installation
------------

We suggest you install it with pipx:

.. code-block:: bash

    pipx install gptme-python

If you don't have pipx, you can install it with pip: ``pip install --user pipx``

Usage
-----

Run the following to start a new chat or choose a previous one:

.. code-block:: bash

    gptme

To fully utilize the assistant, you need to know a little bit about what it can do. 

You can ask the assistant to make changes to files. For example, you can ask it to create a new file:

.. code-block:: text

    User: implement game of life in life.py

The assistant will generate the file, then ask you to confirm the changes.

You can also run a prompt directly from the command line:

.. code-block:: bash

    gptme 'write a snake game with curses to snake.py'

Any text files are in the prompt and exist will be included in the context.

.. note::
    If you have the browser extras installed, it will also try to read any URLs in the prompt.

You can then ask it to make modifications:

.. code-block:: text

    User: make the snake green and the apple red

This will make it generate and apply patches to the file, making the requested changes.

----

Any issues? Report them on the `issue tracker <https://github.com/ErikBjare/gptme/issues>`_.
