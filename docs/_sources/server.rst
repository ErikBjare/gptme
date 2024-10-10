Server
======

.. note::
   The server and web UI is still in development and does not have all the features of the CLI.
   It does not support streaming, doesn't ask for confirmation before executing, lacks the ability to interrupt responses and tool calls, etc.

gptme has a minimal REST API with very minimalistic web UI.

It can be started by running the following command:

.. code-block:: bash

    gptme-server

Web UI
------

.. code-block:: bash

    gptme-server

This should let you view your chats in a web browser and make basic requests.

You can then access the web UI by visiting http://localhost:5000 in your browser.

For more usage, see :ref:`the CLI documentation <cli:gptme-server>`.
