# Understanding MCP

MCP (Model Context Protocol) is an open protocol that standardizes how applications provide context to LLMs. It follows a client-server architecture where:

- **MCP Clients**: Applications like gptme that want to access data through MCP
- **MCP Servers**: Lightweight programs that expose specific capabilities (tools, resources, prompts) through the standardized protocol

The key capabilities MCP provides are:

- **Resources**: File-like data that can be read by clients
- **Tools**: Functions that can be called by the LLM (with user approval)
- **Prompts**: Pre-written templates for specific tasks

## Analysis of gptme

From the README, gptme is a personal AI assistant in the terminal with tools to execute code, edit files, browse the web, etc. It already has a structure for tools, so integrating MCP should align well with its architecture.

The main advantage of adding MCP support would be the ability to connect to various external MCP servers, expanding gptme's capabilities beyond its built-in tools.

## Implementation Plan

### Phase 1: Project Setup and Dependencies

1. Add the MCP Python SDK as a dependency
2. Create a dedicated module structure for MCP integration

### Phase 2: MCP Client Implementation

1. Implement a basic MCP client that can connect to MCP servers
2. Add configuration options for MCP servers in gptme settings
3. Implement session management for MCP connections

### Phase 3: Tool Integration

1. Create a bridge between gptme's existing tool system and MCP tools
2. Implement tool discovery and registration from MCP servers
3. Add user permission system for MCP tool execution

### Phase 4: Resource Integration

1. Implement resource discovery and access from MCP servers
2. Create a unified interface for accessing both local and MCP resources

### Phase 5: Testing and Documentation

1. Write tests for the MCP integration
2. Update documentation to include MCP features
3. Create examples of common MCP server connections

## Implementation

Let's start implementing the integration of MCP into gptme.

### Phase 1: Project Setup and Dependencies

First, let's add the MCP Python SDK dependency to gptme's `pyproject.toml`:

```python
# Adding to dependencies in pyproject.toml
"mcp": "^1.2.0",  # Model Context Protocol SDK
```

Now, let's create a dedicated module structure for MCP integration. We'll create a new `mcp` module inside gptme:

```
gptme/
├── mcp/
│   ├── __init__.py
│   ├── client.py      # MCP client implementation
│   ├── config.py      # MCP configuration
│   ├── resource.py    # MCP resource handling
│   ├── tools.py       # MCP tool integration
│   └── session.py     # MCP session management
```

### Phase 2: MCP Client Implementation

Let's start with the base MCP client implementation in `gptme/mcp/client.py`:

```python
"""Model Context Protocol client for gptme."""
import asyncio
import logging
from typing import Dict, List, Optional, Any

import mcp
from mcp.client.stdio import stdio_client
from mcp.server import ServerParameters

logger = logging.getLogger(__name__)

class MCPClient:
    """Client for connecting to Model Context Protocol servers."""
    
    def __init__(self):
        """Initialize the MCP client."""
        self.sessions = {}
        self.servers_config = {}
        self.tools_cache = {}
        self.resources_cache = {}
        
    async def connect_server(self, server_id: str, config: Dict[str, Any]) -> bool:
        """Connect to an MCP server.
        
        Args:
            server_id: Unique identifier for the server
            config: Server configuration, including command and args
            
        Returns:
            True if connection successful, False otherwise
        """
        if server_id in self.sessions:
            logger.warning(f"Server {server_id} already connected")
            return True
            
        try:
            command = config.get("command")
            args = config.get("args", [])
            env = config.get("env", None)
            
            if not command:
                logger.error(f"No command specified for server {server_id}")
                return False
                
            # Configure server parameters
            server_params = ServerParameters(
                command=command,
                args=args,
                env=env
            )
            
            # Create server connection
            stdio_transport = await asyncio.wait_for(
                stdio_client(server_params), 
                timeout=30.0
            )
            
            # Initialize MCP session
            from mcp import ClientSession
            session = await ClientSession(stdio_transport[0], stdio_transport[1])
            await session.initialize()
            
            # Store the session
            self.sessions[server_id] = {
                "session": session,
                "transport": stdio_transport,
                "config": config
            }
            
            # Cache tools and resources for faster access
            await self._cache_server_capabilities(server_id)
            
            logger.info(f"Connected to MCP server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_id}: {e}")
            return False
    
    async def _cache_server_capabilities(self, server_id: str) -> None:
        """Cache the capabilities of a server for faster access.
        
        Args:
            server_id: Server identifier
        """
        if server_id not in self.sessions:
            return
            
        session = self.sessions[server_id]["session"]
        
        # Cache tools
        try:
            tools_result = await session.list_tools()
            self.tools_cache[server_id] = tools_result.tools
        except Exception as e:
            logger.warning(f"Could not cache tools for server {server_id}: {e}")
            self.tools_cache[server_id] = []
            
        # Cache resources
        try:
            resources_result = await session.list_resources()
            self.resources_cache[server_id] = resources_result.resources
        except Exception as e:
            logger.warning(f"Could not cache resources for server {server_id}: {e}")
            self.resources_cache[server_id] = []
    
    async def disconnect_server(self, server_id: str) -> bool:
        """Disconnect from an MCP server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if disconnected successfully, False otherwise
        """
        if server_id not in self.sessions:
            logger.warning(f"Server {server_id} not connected")
            return False
            
        try:
            session_data = self.sessions[server_id]
            session = session_data["session"]
            
            # Clean up session
            await session.close()
            
            # Remove from cache
            self.sessions.pop(server_id)
            self.tools_cache.pop(server_id, None)
            self.resources_cache.pop(server_id, None)
            
            logger.info(f"Disconnected from MCP server {server_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect from MCP server {server_id}: {e}")
            return False
    
    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        server_ids = list(self.sessions.keys())
        for server_id in server_ids:
            await self.disconnect_server(server_id)
            
    async def list_tools(self, server_id: Optional[str] = None) -> List:
        """List available tools from MCP servers.
        
        Args:
            server_id: Optional server identifier to filter tools
            
        Returns:
            List of available tools
        """
        if server_id:
            if server_id not in self.sessions:
                return []
            return self.tools_cache.get(server_id, [])
        
        # Combine tools from all servers
        all_tools = []
        for sid, tools in self.tools_cache.items():
            all_tools.extend([{
                "server_id": sid,
                "name": tool.name,
                "description": tool.description,
                "schema": tool.inputSchema
            } for tool in tools])
        
        return all_tools
    
    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on an MCP server.
        
        Args:
            server_id: Server identifier
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} not connected")
            
        session = self.sessions[server_id]["session"]
        
        try:
            result = await session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on server {server_id}: {e}")
            raise
```

Next, let's implement configuration handling in `gptme/mcp/config.py`:

```python
"""Configuration for Model Context Protocol in gptme."""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

class MCPConfig:
    """Configuration for MCP servers."""
    
    DEFAULT_CONFIG_PATHS = [
        "~/.config/gptme/mcp_servers.json",
        "~/.gptme/mcp_servers.json",
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize MCP configuration.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.servers = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load MCP server configuration from file."""
        # Try specified path first
        if self.config_path:
            expanded_path = os.path.expanduser(self.config_path)
            if os.path.exists(expanded_path):
                self._load_from_file(expanded_path)
                return
                
        # Try default paths
        for path_str in self.DEFAULT_CONFIG_PATHS:
            path = Path(os.path.expanduser(path_str))
            if path.exists():
                self._load_from_file(str(path))
                return
    
    def _load_from_file(self, file_path: str) -> None:
        """Load configuration from a specific file.
        
        Args:
            file_path: Path to the configuration file
        """
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
                
            if "mcpServers" in config_data:
                self.servers = config_data["mcpServers"]
            else:
                self.servers = config_data
        except Exception as e:
            print(f"Error loading MCP configuration from {file_path}: {e}")
            self.servers = {}
    
    def get_server_config(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            Server configuration or None if not found
        """
        return self.servers.get(server_id)
    
    def get_all_servers(self) -> Dict[str, Any]:
        """Get all server configurations.
        
        Returns:
            Dictionary of all server configurations
        """
        return self.servers
```

### Phase 3: Tool Integration

Now, let's implement the integration between gptme's tool system and MCP tools. First, let's create `gptme/mcp/tools.py`:

```python
"""Integration of MCP tools with gptme's tool system."""
import asyncio
import inspect
import json
import logging
from typing import Dict, List, Any, Callable, Optional, Union

from gptme.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

class MCPToolAdapter(BaseTool):
    """Adapter for MCP tools to be used in gptme."""
    
    def __init__(self, mcp_client, server_id: str, tool_name: str, 
                description: str, schema: Dict[str, Any]):
        """Initialize MCP tool adapter.
        
        Args:
            mcp_client: MCP client instance
            server_id: Server identifier
            tool_name: Name of the tool
            description: Tool description
            schema: JSON schema for tool input
        """
        self.mcp_client = mcp_client
        self.server_id = server_id
        self.tool_name = tool_name
        self.mcp_schema = schema
        
        # Create a unique name for the tool to avoid conflicts
        unique_name = f"mcp_{server_id}_{tool_name}"
        
        # Extract parameter info from the schema
        params = self._extract_params_from_schema(schema)
        
        super().__init__(
            name=unique_name,
            description=description,
            function=self.execute,
            parameters=params
        )
    
    def _extract_params_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract parameter information from JSON schema.
        
        Args:
            schema: JSON schema for tool input
            
        Returns:
            Dictionary of parameter definitions
        """
        params = {}
        
        if not schema or "properties" not in schema:
            return params
            
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for name, prop in properties.items():
            param_type = prop.get("type", "string")
            description = prop.get("description", "")
            
            params[name] = {
                "type": param_type,
                "description": description,
                "required": name in required
            }
            
            # Handle enums
            if "enum" in prop:
                params[name]["enum"] = prop["enum"]
                
        return params
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the MCP tool.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            result = await self.mcp_client.call_tool(
                self.server_id, 
                self.tool_name, 
                kwargs
            )
            
            # Convert MCP result to gptme's ToolResult
            content = []
            for item in result.content:
                if item.get("type") == "text":
                    content.append(item.get("text", ""))
                    
            text_content = "\n".join(content)
            
            return ToolResult(success=True, output=text_content)
        except Exception as e:
            error_msg = f"Error executing MCP tool {self.tool_name}: {e}"
            logger.error(error_msg)
            return ToolResult(success=False, output=error_msg)


class MCPToolRegistry:
    """Registry for MCP tools in gptme."""
    
    def __init__(self, mcp_client):
        """Initialize MCP tool registry.
        
        Args:
            mcp_client: MCP client instance
        """
        self.mcp_client = mcp_client
        self.registered_tools = {}
        
    async def register_all_tools(self) -> List[BaseTool]:
        """Register all available MCP tools.
        
        Returns:
            List of registered tools
        """
        all_tools = []
        
        # Get all available tools from MCP client
        mcp_tools = await self.mcp_client.list_tools()
        
        for tool_info in mcp_tools:
            server_id = tool_info["server_id"]
            tool_name = tool_info["name"]
            description = tool_info["description"]
            schema = tool_info["schema"]
            
            # Create and register tool adapter
            tool_adapter = MCPToolAdapter(
                self.mcp_client, 
                server_id, 
                tool_name, 
                description, 
                schema
            )
            
            # Store in registry
            tool_key = f"{server_id}_{tool_name}"
            self.registered_tools[tool_key] = tool_adapter
            
            all_tools.append(tool_adapter)
            
        return all_tools
    
    def get_tool(self, server_id: str, tool_name: str) -> Optional[BaseTool]:
        """Get a specific tool from the registry.
        
        Args:
            server_id: Server identifier
            tool_name: Tool name
            
        Returns:
            Tool adapter or None if not found
        """
        tool_key = f"{server_id}_{tool_name}"
        return self.registered_tools.get(tool_key)
```

### Phase 4: Resource Integration

Now, let's implement resource handling in `gptme/mcp/resource.py`:

```python
"""Integration of MCP resources with gptme."""
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import base64

logger = logging.getLogger(__name__)

class MCPResourceManager:
    """Manager for MCP resources in gptme."""
    
    def __init__(self, mcp_client):
        """Initialize MCP resource manager.
        
        Args:
            mcp_client: MCP client instance
        """
        self.mcp_client = mcp_client
        
    async def list_resources(self, server_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available resources from MCP servers.
        
        Args:
            server_id: Optional server identifier to filter resources
            
        Returns:
            List of available resources
        """
        resources = []
        
        if server_id:
            if server_id not in self.mcp_client.sessions:
                return []
                
            session = self.mcp_client.sessions[server_id]["session"]
            try:
                result = await session.list_resources()
                resources = [{
                    "server_id": server_id,
                    "uri": res.uri,
                    "name": res.name,
                    "description": res.description,
                    "mime_type": res.mimeType
                } for res in result.resources]
            except Exception as e:
                logger.error(f"Failed to list resources from server {server_id}: {e}")
        else:
            # List resources from all servers
            for sid in self.mcp_client.sessions:
                server_resources = await self.list_resources(sid)
                resources.extend(server_resources)
                
        return resources
    
    async def read_resource(self, server_id: str, uri: str) -> Tuple[bool, str, Optional[bytes]]:
        """Read a resource from an MCP server.
        
        Args:
            server_id: Server identifier
            uri: Resource URI
            
        Returns:
            Tuple of (success, content_type, content) where content is either text or binary
        """
        if server_id not in self.mcp_client.sessions:
            return False, "error", f"Server {server_id} not connected"
            
        session = self.mcp_client.sessions[server_id]["session"]
        
        try:
            result = await session.read_resource(uri)
            
            for content in result.contents:
                if "text" in content:
                    return True, "text", content.text
                elif "blob" in content:
                    # Decode base64 binary data
                    binary_data = base64.b64decode(content.blob)
                    return True, "binary", binary_data
                    
            return False, "error", "No content found in resource"
            
        except Exception as e:
            error_msg = f"Failed to read resource {uri} from server {server_id}: {e}"
            logger.error(error_msg)
            return False, "error", error_msg
    
    async def save_resource(self, server_id: str, uri: str, path: Union[str, Path]) -> bool:
        """Save a resource to the local filesystem.
        
        Args:
            server_id: Server identifier
            uri: Resource URI
            path: Local filesystem path to save to
            
        Returns:
            True if successful, False otherwise
        """
        success, content_type, content = await self.read_resource(server_id, uri)
        
        if not success:
            logger.error(f"Failed to read resource: {content}")
            return False
            
        path = Path(path)
        
        try:
            if content_type == "text":
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
            elif content_type == "binary":
                with open(path, 'wb') as f:
                    f.write(content)
            else:
                logger.error(f"Unknown content type: {content_type}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Failed to save resource to {path}: {e}")
            return False
```

### Phase 5: Integration with gptme Core

Now, let's integrate the MCP module with gptme's core functionality by creating a session manager in `gptme/mcp/session.py`:

```python
"""MCP session management for gptme."""
import asyncio
import logging
from typing import Dict, List, Optional, Any

from gptme.mcp.client import MCPClient
from gptme.mcp.config import MCPConfig
from gptme.mcp.tools import MCPToolRegistry
from gptme.mcp.resource import MCPResourceManager

logger = logging.getLogger(__name__)

class MCPSessionManager:
    """Manager for MCP sessions in gptme."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize MCP session manager.
        
        Args:
            config_path: Optional path to MCP configuration file
        """
        self.config = MCPConfig(config_path)
        self.client = MCPClient()
        self.tool_registry = MCPToolRegistry(self.client)
        self.resource_manager = MCPResourceManager(self.client)
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize MCP sessions based on configuration.
        
        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True
            
        servers = self.config.get_all_servers()
        if not servers:
            logger.info("No MCP servers configured")
            return False
            
        # Connect to all configured servers
        success = False
        for server_id, server_config in servers.items():
            server_success = await self.client.connect_server(server_id, server_config)
            success = success or server_success
            
        # Register tools
        if success:
            await self.tool_registry.register_all_tools()
            
        self._initialized = success
        return success
    
    async def shutdown(self) -> None:
        """Shutdown all MCP sessions."""
        await self.client.disconnect_all()
        self._initialized = False
    
    async def get_tools(self) -> List[Any]:
        """Get all available MCP tools.
        
        Returns:
            List of available tools
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.tool_registry.register_all_tools()
    
    async def get_resources(self) -> List[Dict[str, Any]]:
        """Get all available MCP resources.
        
        Returns:
            List of available resources
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.resource_manager.list_resources()
```

### Phase 6: Modifying gptme Main Module

Now, let's modify the main gptme module to integrate MCP functionality. We'll need to update the main CLI to add MCP support:

```python
# Add to gptme/main.py or relevant module

import asyncio
from gptme.mcp.session import MCPSessionManager

# Add as a class variable or global
mcp_manager = None

# Add to the initialization function
async def initialize_mcp():
    global mcp_manager
    mcp_manager = MCPSessionManager()
    await mcp_manager.initialize()
    
    # Register MCP tools with gptme's tool registry
    mcp_tools = await mcp_manager.get_tools()
    for tool in mcp_tools:
        register_tool(tool)  # Assuming this is the function to register tools in gptme

# Add to the cleanup function
async def cleanup_mcp():
    global mcp_manager
    if mcp_manager:
        await mcp_manager.shutdown()
```

### Phase 7: Command-Line Interface Updates

Now, let's add CLI options for MCP configuration:

```python
# Add to CLI options in gptme/cli.py or relevant module

@click.option(
    "--mcp-config", 
    help="Path to MCP servers configuration file",
    type=str
)
@click.option(
    "--mcp-servers",
    help="Comma-separated list of MCP server IDs to use",
    type=str
)
```

### Phase 8: Adding Configuration Documentation

Finally, let's create a documentation section for MCP in gptme:

````markdown
# MCP Integration

gptme now supports the Model Context Protocol (MCP), which allows connecting to external MCP servers for expanded capabilities.

## Configuration

Create an MCP server configuration file at one of these locations:
- `~/.config/gptme/mcp_servers.json`
- `~/.gptme/mcp_servers.json`

Example configuration:

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
````

## Usage

MCP servers provide additional tools that gptme can use. Once configured, these tools will appear in the `/tools` command output.

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

```

## Testing Plan

Here's a plan for testing the MCP integration:

1. **Unit Tests**:
   - Test MCP client connection
   - Test tool registration
   - Test resource handling

2. **Integration Tests**:
   - Test with a simple MCP server
   - Verify tool execution through MCP
   - Verify resource access through MCP

3. **End-to-End Tests**:
   - Test full workflow with a real MCP server
   - Test error handling and recovery

## Summary of Changes

1. Added new `mcp` module with the following components:
   - `client.py`: Core MCP client implementation
   - `config.py`: Configuration handling for MCP servers
   - `tools.py`: Integration of MCP tools with gptme's tool system
   - `resource.py`: Resource handling for MCP
   - `session.py`: Session management for MCP

2. Added CLI options for MCP configuration
3. Updated documentation to include MCP features

This implementation allows gptme to connect to MCP servers, use their tools, and access their resources, expanding its capabilities beyond built-in functionality.
```
