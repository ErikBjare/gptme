"""Integration of MCP tools with gptme's tool system."""

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union

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


class MCPToolAdapter(BaseTool):
    """Adapter for MCP tools to be used in gptme."""

    def __init__(self, mcp_client, server_id: str, tool_name: str, description: str, schema: Dict[str, Any]):
        """Initialize MCP tool adapter.

        Args:
            mcp_client: MCP client instance
            server_id: Server identifier
            tool_name: Name of the tool
            description: Tool description
            schema: JSON schema for tool input
        """
        self.mcp_client = mcp_client
        # Store the original server_id with @ prefix if it has one
        self.server_id = server_id
        self.tool_name = tool_name
        self.mcp_schema = schema

        # Create a unique name for the tool that preserves the @ prefix
        unique_name = f"mcp_{server_id}_{tool_name}".replace("@", "at_")

        # Extract parameter info from the schema
        params = self._extract_params_from_schema(schema)

        super().__init__(name=unique_name, description=description, function=self.execute, parameters=params)

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

            params[name] = {"type": param_type, "description": description, "required": name in required}

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
            # Use the original server_id with @ prefix
            result = await self.mcp_client.call_tool(self.server_id, self.tool_name, kwargs)

            # Convert MCP result to gptme's ToolResult
            content = []
            for item in result.content:
                if item.get("type") == "text":
                    content.append(item.get("text", ""))

            text_content = "\n".join(content)

            return ToolResult(success=True, output=text_content)
        except Exception as e:
            error_msg = f"Error executing MCP tool {self.tool_name} on server {self.server_id}: {e}"
            logger.error(error_msg)
            return ToolResult(success=False, output=error_msg)

    def to_toolspec(self) -> ToolSpec:
        """Convert this adapter to a gptme ToolSpec.

        Returns:
            ToolSpec instance
        """
        parameters = []
        for name, param_info in self.parameters.items():
            parameters.append(
                Parameter(
                    name=name,
                    type=param_info["type"],
                    description=param_info.get("description", ""),
                    enum=param_info.get("enum"),
                    required=param_info.get("required", False),
                )
            )

        # Create sync wrapper for the async execute method
        def execute_wrapper(*args, **kwargs):
            # Create event loop or use existing one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run async function
            result = loop.run_until_complete(self.execute(**kwargs))

            # Return a generator that yields a single message
            if result.success:
                yield Message.system(result.output)
            else:
                yield Message.error(result.output)

        # Create the tool spec
        tool_spec = ToolSpec(name=self.name, desc=self.description, parameters=parameters, execute=execute_wrapper)

        return tool_spec


class MCPToolRegistry:
    """Registry for MCP tools in gptme."""

    def __init__(self, mcp_client):
        """Initialize MCP tool registry.

        Args:
            mcp_client: MCP client instance
        """
        self.mcp_client = mcp_client
        self.registered_tools = {}

    async def register_all_tools(self) -> List[ToolSpec]:
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
            tool_adapter = MCPToolAdapter(self.mcp_client, server_id, tool_name, description, schema)

            # Store in registry
            tool_key = f"{server_id}_{tool_name}"
            self.registered_tools[tool_key] = tool_adapter

            # Convert to ToolSpec
            tool_spec = tool_adapter.to_toolspec()
            all_tools.append(tool_spec)

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
