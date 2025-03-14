"""Model Context Protocol client for gptme."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import mcp
from mcp.client.stdio import StdioServerParameters, stdio_client

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

            # Add more detailed logging about the server we're starting
            logger.info(f"Starting MCP server '{server_id}' with command: {command}")
            logger.debug(f"Full command with args: {command} {' '.join(args)}")

            # Check if the command exists
            import shutil

            if not shutil.which(command):
                logger.error(f"MCP server command '{command}' not found in PATH. Please install it first.")
                logger.error(f"For npm packages, run: npm install -g {command}")
                logger.error(f"For Python packages, run: pip install {command}")
                return False

            # Configure server parameters with the full command and args
            server_params = StdioServerParameters(
                command=command,
                args=args,  # Use the args array directly from the config
                env=env,
            )

            # Create server connection using async with instead of await
            try:
                # Use asyncio.timeout instead of wait_for for better compatibility
                async with asyncio.timeout(30.0):
                    logger.debug(f"Launching process for server '{server_id}'...")
                    async with stdio_client(server_params) as stdio_transport:
                        logger.debug(f"Process launched for server '{server_id}', initializing session...")
                        # Initialize MCP session
                        from mcp import ClientSession

                        session = ClientSession(stdio_transport[0], stdio_transport[1])
                        await session.initialize()

                        # Store the session
                        self.sessions[server_id] = {"session": session, "transport": stdio_transport, "config": config}

                        # Cache tools and resources for faster access
                        await self._cache_server_capabilities(server_id)

                        logger.info(f"Connected to MCP server {server_id}")
                        return True
            except asyncio.TimeoutError:
                logger.error(f"Timeout connecting to MCP server {server_id}")
                return False
            except FileNotFoundError as e:
                logger.error(f"MCP server executable not found: {e}")
                logger.error(f"Please make sure the MCP server package is installed correctly.")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_id}: {e}")
            # Log more details about the error to help diagnose
            import traceback

            logger.error(f"Detailed error for server {server_id}: {traceback.format_exc()}")
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
            all_tools.extend(
                [
                    {"server_id": sid, "name": tool.name, "description": tool.description, "schema": tool.inputSchema}
                    for tool in tools
                ]
            )

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
