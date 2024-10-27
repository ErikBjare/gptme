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

   .. code-block:: bash

       # Run with computer use support (requires Docker)
       docker run -p 5000:5000 -p 8080:8080 -p 6080:6080 ghcr.io/erikbjare/gptme:latest-server

   The computer use interface provides:

   - Combined chat and desktop view at http://localhost:8080
   - Desktop-only view at http://localhost:6080/vnc.html
   - Chat-only view at http://localhost:5000

   Features:

   - Split view with chat on the left, desktop on the right
   - Toggle for view-only/interactive desktop mode
   - Fullscreen support
   - Automatic screen scaling for optimal LLM vision

   Requirements:

   - Docker for running the server with X11 support
   - Browser with WebSocket support for VNC
   - Network ports 5000 (API), 8080 (combined view), and 6080 (VNC) available

.. warning::

   The computer use interface is experimental and has serious security implications.
   Please use with caution and consider the security considerations below.

Security Considerations
-----------------------

When using the computer use interface:

1. Network Security
   - The server exposes VNC and web interfaces
   - Consider using SSH tunneling for remote access
   - Restrict access to trusted networks/users
   - Use firewall rules to limit port access

2. Container Security
   - Run with minimal privileges
   - Mount only necessary directories
   - Consider using a separate network namespace
   - Regularly update base images and dependencies

3. Usage Guidelines
   - Start in view-only mode by default
   - Require explicit user action to enable interaction
   - Monitor and audit computer use sessions
   - Implement timeouts for inactive sessions

4. Data Protection
   - Don't expose sensitive information in the desktop environment
   - Be cautious with browser automation and credentials
   - Consider using ephemeral containers
   - Regular cleanup of session data

Please also see Anthropic's documentation on `computer use <https://docs.anthropic.com/en/docs/build-with-claude/computer-use>`_ for additional guidance.
