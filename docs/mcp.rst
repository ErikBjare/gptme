MCP Support
==========

gptme can run as a Model Context Protocol (MCP) server, allowing other applications to use its capabilities through a standardized protocol.

What is MCP?
-----------

The `Model Context Protocol <https://modelcontextprotocol.io/>`_ (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. It provides a standardized way for applications to:

- Access resources (files, data)
- Execute tools (commands, operations)
- Use prompt templates
- Request LLM completions

Running as MCP Server
-------------------

To run gptme as an MCP server::

    gptme-mcp-server [OPTIONS]

Options:
  -w, --workspace PATH  Path to workspace directory
  -v, --verbose        Enable verbose logging
  --help              Show this message and exit

The server will start and listen on stdin/stdout using the MCP protocol.

Integration with Claude Desktop
----------------------------

To use gptme with Claude Desktop:

1. Install gptme with MCP support::

    pipx install gptme

2. Add to Claude Desktop config (``~/Library/Application Support/Claude/claude_desktop_config.json``)::

    {
      "mcpServers": {
        "gptme": {
          "command": "gptme-mcp-server",
          "args": ["--workspace", "/path/to/workspace"]
        }
      }
    }

3. Restart Claude Desktop

Now Claude can use all of gptme's capabilities through the MCP protocol.

Available Capabilities
-------------------

The gptme MCP server exposes:

- **Tools**: All gptme tools (shell, python, browser, etc.)
- **Resources**: Access to workspace files and data
- **Prompts**: Common prompt templates (coming soon)

Implementation Details
-------------------

The MCP implementation in gptme follows the protocol specification for:

- JSON-RPC message format
- Capability negotiation
- Resource and tool discovery
- Error handling
- Progress reporting

For developers interested in the implementation details, see:

- ``gptme/mcp/types.py`` - Core protocol types
- ``gptme/mcp/transport.py`` - Transport layer (stdio)
- ``gptme/mcp/server.py`` - Server implementation
- ``gptme/mcp/__init__.py`` - gptme integration

Security Considerations
--------------------

The MCP server inherits gptme's security model:

- Tools run with user permissions
- Resource access limited to workspace
- Human approval required for sensitive operations
- No remote code execution without approval

Future Plans
----------

Planned improvements to MCP support:

- Support for prompt templates
- Enhanced resource capabilities
- Better progress reporting
- Additional transport options
- More granular permissions
