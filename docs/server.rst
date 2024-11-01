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

The server provides two interfaces:

1. Basic Chat Interface

   .. code-block:: bash

       gptme-server

   Access the basic chat interface at http://localhost:5000

   For more usage, see :ref:`the CLI documentation <cli:gptme-server>`.

2. Computer Use Interface

   Requires Docker.

   .. code-block:: bash

       # Clone the repository
       git clone https://github.com/ErikBjare/gptme.git
       cd gptme
       # Build container
       make build-docker-computer
       # Run container
       docker run -v ~/.config/gptme:/home/computeruse/.config/gptme -p 5000:5000 -p 6080:6080 -p 8080:8080 gptme-computer:latest

   The computer use interface provides:

   - Combined view at http://localhost:8080/computer
   - Chat view at http://localhost:8080
   - Desktop view at http://localhost:6080/vnc.html

   Features:

   - Split view with chat on the left, desktop on the right
   - Toggle for view-only/interactive desktop mode
   - Fullscreen support
   - Automatic screen scaling for optimal LLM vision

   Requirements:

   - Docker for running the server with X11 support
   - Browser with WebSocket support for VNC
   - Network ports 6080 (VNC) and 8080 (web UI) available

.. include:: computer-use-warning.rst
