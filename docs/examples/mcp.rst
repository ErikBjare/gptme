MCP Examples
===========

This page contains examples of using gptme as a Model Context Protocol (MCP) server.

Claude Desktop Integration
------------------------

Here's how to configure Claude Desktop to use gptme's capabilities through MCP:

1. Install gptme::

    pipx install gptme

2. Create configuration file:

.. literalinclude:: mcp/claude_desktop_config.json
   :language: json
   :caption: claude_desktop_config.json

3. Copy to appropriate location:

   - macOS: ``~/Library/Application Support/Claude/claude_desktop_config.json``
   - Windows: ``%APPDATA%\Claude\claude_desktop_config.json``

4. Replace environment variables:

   - ``${OPENAI_API_KEY}`` with your OpenAI API key
   - ``${ANTHROPIC_API_KEY}`` with your Anthropic API key
   - Adjust the workspace path as needed

5. Restart Claude Desktop

Example Usage
-----------

Once configured, you can ask Claude to use gptme's capabilities:

Code Execution
^^^^^^^^^^^^^

.. code-block:: text

    Can you write a Python script that generates a Mandelbrot set visualization?

File Operations
^^^^^^^^^^^^^^

.. code-block:: text

    Can you read my .gitconfig and suggest improvements?

Web Browsing
^^^^^^^^^^^

.. code-block:: text

    Can you check the ActivityWatch website and tell me what the latest version is?

Security Considerations
---------------------

The MCP server:

- Runs with your user permissions
- Has access to your API keys through environment variables
- Can access files in the configured workspace
- Requires confirmation for sensitive operations

For more details, see the :doc:`../mcp` documentation.
