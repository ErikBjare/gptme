Web UI
======

.. note::
   The web UI is still in development and does not have all the features of the CLI.
   It does not support streaming, doesn't ask for confirmation before executing, lacks the ability to interrupt generations, etc.

gptme has a very minimalistic web UI, it can be started by running the following command:

.. code-block:: bash

    gptme-server

You can then access the web UI by visiting http://localhost:5000 in your browser.


.. click:: gptme.server.cli:main
   :prog: gptme-server
   :nested: full
