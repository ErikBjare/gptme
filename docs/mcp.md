# MCP Integration

gptme now supports the Model Context Protocol (MCP), which allows connecting to external MCP servers for expanded capabilities.

## What is MCP?

Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to LLMs. It follows a client-server architecture where:

- **MCP Clients**: Applications like gptme that want to access data through MCP
- **MCP Servers**: Lightweight programs that expose specific capabilities (tools, resources, prompts) through the standardized protocol

The key capabilities MCP provides are:

- **Resources**: File-like data that can be read by clients
- **Tools**: Functions that can be called by the LLM (with user approval)
- **Prompts**: Pre-written templates for specific tasks

## Configuration

Create an MCP server configuration file at one of these locations:
- `~/.config/gptme/mcp_servers.json`
- `~/.gptme/mcp_servers.json`

Example configuration (see a full example at [docs/examples/mcp/mcp_servers.json](examples/mcp/mcp_servers.json)):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
      "env": {
        "CUSTOM_ENV_VAR": "value"
      }
    },
    "browser": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-browser"]
    }
  }
}
```

## Usage

MCP servers provide additional tools that gptme can use. Once configured, these tools will appear in the `/tools` command output with the prefix `mcp_<server_id>_`.

Example:

```
/tools
Available tools:
...
mcp_filesystem_read_file (Read file from allowed directory)
mcp_browser_search (Search the web)
...
```

You can specify which MCP servers to use with:

```
gptme --mcp-servers=filesystem,browser
```

Or specify a custom config file:

```
gptme --mcp-config=~/my_mcp_config.json
```

## Available MCP Servers

Here are some common MCP servers that you can use with gptme:

### Filesystem Server

Access files in a specific directory:

```
npm install -g @modelcontextprotocol/server-filesystem
```

Then configure in your `mcp_servers.json`:

```json
"filesystem": {
  "command": "mcp-filesystem",
  "args": ["/path/to/allowed/dir"]
}
```

### Browser Server

Perform web searches:

```
npm install -g @modelcontextprotocol/server-browser
```

Then configure in your `mcp_servers.json`:

```json
"browser": {
  "command": "mcp-browser"
}
```

## Creating Your Own MCP Server

You can create your own MCP server to extend gptme with custom capabilities. The MCP protocol is standardized and documented at [mcp.ai](https://mcp.ai).

Basic steps to create an MCP server:

1. Implement the MCP server API
2. Expose the tools and resources you want to provide
3. Add the server to your gptme configuration

## Limitations

- MCP integration requires the MCP server to be installed and properly configured
- Performance may be affected when using many MCP servers
- Tools from MCP servers require user approval just like built-in tools

## Troubleshooting

If you're having issues with MCP:

1. Check your configuration file syntax
2. Verify that the MCP server is installed and accessible
3. Run gptme with the `--verbose` flag for more detailed logs
4. Check the server's logs for any errors 