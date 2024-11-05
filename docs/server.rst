Server
======

.. note::
   The server and web UI is still in development and does not have all the features of the CLI.
   It does not support streaming, doesn't ask for confirmation before executing, lacks the ability to interrupt responses and tool calls, etc.

gptme has a minimal REST API with very minimalistic web UI.

It can be started by running the following command:

.. code-block:: bash

    gptme-server

For more CLI usage, see :ref:`the CLI documentation <cli:gptme-server>`.

There are a few different interfaces available:

Web UI
------

A basic chat interface with minimal dependencies that is bundled with the server.

Simply start the server to access the interface at http://localhost:5000

Fancy Web UI
------------

A modern, feature-rich web interface for gptme is available as a separate project `gptme-webui <https://github.com/ErikBjare/gptme-webui>`_. It is mainly built with `gptengineer.app <https://gptengineer.app>`_.

To use gptme-webui, see the `gptme-webui README <https://github.com/ErikBjare/gptme-webui>`_.

Features:

- Modern React-based interface with shadcn/ui
- Streaming of responses
- Mobile-friendly design
- Dark mode support
- Offline/exports support


Computer Use Interface
----------------------

.. include:: computer-use-warning.rst

The computer use interface provides a split view with a chat on the left and a desktop on the right.

Requires Docker.

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/ErikBjare/gptme.git
   cd gptme
   # Build container
   make build-docker-computer
   # Run container
   docker run -v ~/.config/gptme:/home/computeruse/.config/gptme -p 6080:6080 -p 8080:8080 gptme-computer:latest

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
- Network ports 6080 (VNC) and 8080 (web UI) available
