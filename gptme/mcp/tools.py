"""Integration of MCP tools with gptme's tool system."""

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from gptme.message import Message
from gptme.tools.base import Parameter, ToolSpec

logger = logging.getLogger(__name__)


class ToolResult:
    """Result of a tool execution."""

    def __init__(self, success: bool, output: str):
        """Initialize tool result.

        Args:
            success: Whether the execution was successful
            output: Output content from the tool execution
        """
        self.success = success
        self.output = output


class BaseTool:
    """Base class for tools in gptme."""

    def __init__(self, name: str, description: str, function: Callable, parameters: Dict[str, Dict[str, Any]]):
        """Initialize a base tool.

        Args:
            name: Tool name
            description: Tool description
            function: Function to execute
            parameters: Parameter definitions
        """
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters


class MCPToolAdapter:
    """Adapter to convert MCP tool to a function."""

    def __init__(
        self,
        name: str,
        description: str,
        server_name: str,
        input_schema: Dict[str, Any],
        client: Any,
    ):
        """
        Initialize an adapter for an MCP tool.

        Args:
            name: Name of the tool
            description: Description of the tool
            server_name: Name of the server providing the tool
            input_schema: JSON schema for the tool input
            client: MCPClient instance to use for tool calls
        """
        self.name = name
        self.description = description
        self.server_name = server_name
        self.input_schema = input_schema
        self.client = client

    async def __call__(self, **kwargs: Any) -> Any:
        """
        Call the tool on the MCP server.

        Args:
            **kwargs: Arguments to pass to the tool

        Returns:
            Result of the tool call
        """
        if not self.client:
            raise ValueError(f"No MCP client available to call tool {self.name}")

        result = await self.client.call_tool(self.server_name, self.name, kwargs)
        return result


class MCPToolRegistry:
    """Registry for MCP tools."""

    def __init__(self):
        """Initialize the tool registry."""
        self.tools: Dict[str, MCPToolAdapter] = {}
        self.tool_specs: List[Dict[str, Any]] = []

    async def register_all_tools(self, client: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Register all tools from connected MCP servers.

        Args:
            client: MCPClient instance to use for tool registration. If None,
                   tries to retrieve the client from the session manager.

        Returns:
            List of registered tool specifications
        """
        logger.info("Registering MCP tools")

        # Clear existing tools
        self.tools = {}
        self.tool_specs = []

        if not client:
            logger.error("No MCP client provided, cannot register tools")
            return []

        # Log the client type and attributes for debugging
        logger.debug(f"Client type: {type(client)}")
        logger.debug(f"Client attributes: {dir(client)}")

        # Verify client is initialized
        if not getattr(client, "initialized", False):
            logger.warning("Client is not initialized, tools may not be available")

        # Check if the client's sessions and tools_cache are populated
        if hasattr(client, "sessions"):
            logger.debug(f"Client has {len(client.sessions)} session(s)")

        if hasattr(client, "tools_cache"):
            logger.debug(f"Client has tools cached for {list(client.tools_cache.keys())} servers")
            # Log what's in the cache for debugging
            for server, tools in client.tools_cache.items():
                logger.debug(f"Server {server} has {len(tools)} cached tools")

        try:
            # Get tools from all servers
            logger.info("Requesting tools from client.list_tools()")
            all_tools = await client.list_tools()

            logger.info(f"Received {len(all_tools)} tools from client.list_tools()")

            if not all_tools:
                # If no tools found, check if there might be a direct way to access them
                logger.warning("No MCP tools found from client.list_tools() - trying alternative approaches")

                # Attempt to access tools cache directly if available
                direct_tools = []

                if hasattr(client, "tools_cache"):
                    for server_name, tools in client.tools_cache.items():
                        logger.debug(f"Directly accessing {len(tools)} tools from server {server_name}")
                        for tool in tools:
                            try:
                                tool_info = {
                                    "name": tool.name,
                                    "description": tool.description,
                                    "inputSchema": getattr(tool, "inputSchema", {}),
                                    "server_name": server_name,
                                }
                                direct_tools.append(tool_info)
                            except Exception as e:
                                logger.error(f"Error processing tool from cache: {e}")

                    if direct_tools:
                        logger.info(f"Found {len(direct_tools)} tools directly from cache")
                        all_tools = direct_tools

                if not all_tools:
                    logger.warning("No MCP tools found from any approach")
                    return []

            logger.info(f"Found {len(all_tools)} MCP tools to register")

            # Register each tool
            registered_count = 0
            for tool_info in all_tools:
                try:
                    # Log the raw tool info for debugging
                    logger.debug(f"Processing tool: {tool_info}")

                    # Extract required fields, with fallbacks
                    name = tool_info.get("name", "<unnamed>")
                    description = tool_info.get("description", f"Tool: {name}")

                    # Handle different types of schema representation
                    input_schema = tool_info.get("inputSchema", {})
                    if not isinstance(input_schema, dict):
                        logger.warning(f"Tool {name} has non-dict inputSchema: {type(input_schema)}")
                        # Try to convert to dict if possible
                        if hasattr(input_schema, "__dict__"):
                            input_schema = input_schema.__dict__
                        else:
                            # Default empty schema
                            input_schema = {"type": "object", "properties": {}}

                    server_name = tool_info.get("server_name", "unknown")

                    # Create adapter for the tool
                    adapter = MCPToolAdapter(
                        name=name,
                        description=description,
                        server_name=server_name,
                        input_schema=input_schema,
                        client=client,
                    )

                    # Store adapter
                    self.tools[name] = adapter

                    # Create tool specification
                    tool_spec = {
                        "type": "function",
                        "function": {"name": name, "description": description, "parameters": input_schema},
                    }

                    self.tool_specs.append(tool_spec)
                    registered_count += 1
                    logger.debug(f"Registered MCP tool: {name} from server {server_name}")

                except Exception as e:
                    logger.error(f"Failed to register MCP tool {tool_info.get('name', '<unknown>')}: {e}")
                    import traceback

                    logger.debug(f"Traceback: {traceback.format_exc()}")

            logger.info(f"Successfully registered {registered_count} MCP tools")
            return self.tool_specs

        except Exception as e:
            logger.error(f"Error during tool registration: {e}")
            import traceback
        # Get tools from all servers
        all_tools = await client.list_tools()

        if not all_tools:
            logger.warning("No MCP tools found from any servers")
            return []

        logger.info(f"Found {len(all_tools)} MCP tools to register")

        # Register each tool
        registered_count = 0
        for tool_info in all_tools:
            try:
                name = tool_info["name"]
                description = tool_info["description"]
                input_schema = tool_info["inputSchema"]
                server_name = tool_info["server_name"]

                # Create adapter for the tool
                adapter = MCPToolAdapter(
                    name=name,
                    description=description,
                    server_name=server_name,
                    input_schema=input_schema,
                    client=client,
                )

                # Store adapter
                self.tools[name] = adapter

                # Create tool specification
                tool_spec = {
                    "type": "function",
                    "function": {"name": name, "description": description, "parameters": input_schema},
                }

                self.tool_specs.append(tool_spec)
                registered_count += 1
                logger.debug(f"Registered MCP tool: {name} from server {server_name}")

            except Exception as e:
                logger.error(f"Failed to register MCP tool {tool_info.get('name', '<unknown>')}: {e}")

        logger.info(f"Successfully registered {registered_count} MCP tools")
        return self.tool_specs

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a registered MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result of the tool call

        Raises:
            ValueError: If the tool is not registered
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not registered")

        return await self.tools[tool_name](**arguments)

    def register_tool(self, server_id: str, tool: Any) -> ToolSpec:
        """Register an MCP tool.

        Args:
            server_id: Server identifier
            tool: MCP tool to register

        Returns:
            Registered tool spec
        """
        tool_id = f"{server_id}_{tool.name}"
        if tool_id in self.tools:
            return self.tools[tool_id]

        # Create tool spec from MCP tool
        tool_spec = ToolSpec(
            name=f"{server_id}_{tool.name}",
            desc=tool.description,
            parameters=tool.inputSchema.get("properties", {}),
            required=tool.inputSchema.get("required", []),
        )

        self.tools[tool_id] = tool_spec
        return tool_spec
