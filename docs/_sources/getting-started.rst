Getting Started
===============

This guide will help you get started with gptme.

Installation
------------

To install gptme, we recommend using ``pipx``:

.. code-block:: bash

    pipx install gptme

If pipx is not installed, you can install it using pip:

.. code-block:: bash

    pip install --user pipx

.. note::

   Windows is not directly supported, but you can run gptme using WSL or Docker.

Usage
-----

To start your first chat, simply run:

.. code-block:: bash

    gptme

It will then start an interactive chat session where you can talk with the AI assistant.

If you haven't set a :doc:`LLM provider <providers>` API key in the environment or :doc:`configuration <config>`, you will be prompted for one which will be saved in the configuration file.

For detailed usage instructions and examples, see :doc:`usage`.

Next Steps
----------

- Read the :doc:`usage` guide for detailed usage instructions and examples
- Learn about available :doc:`tools`
- Explore different :doc:`providers`
- Set up the :doc:`server` for web access

Support
-------

For any issues, please visit our `issue tracker <https://github.com/ErikBjare/gptme/issues>`_.
