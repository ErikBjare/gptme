"""Model Context Protocol client for gptme."""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..config import Config

# Import the official MCP SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client that manages connections to MCP servers using the standard MCP protocol."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize an MCP client with a configuration path.

        Args:
            config_path: Path to the MCP configuration file. If None, uses 'mcp.json' in current directory.
        """
        self.config_path = Path(config_path) if config_path else Path("mcp.json")
        self.config = None
        self.sessions = {}  # Server connections using official SDK
        self.background_tasks = {}  # Background tasks for each server
        self.tools_cache = {}  # Cache for tools from each server
        self.tools_cache_timestamp = 0
        self.tools_cache_ttl = 60  # 1 minute
        self.initialized = False
        self.connection_timeout = 20  # seconds

    async def initialize(self) -> bool:
        """
        Initialize the MCP client by loading configuration and connecting to servers.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        if self.initialized:
            return True

        # Load configuration
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load MCP configuration from {self.config_path}: {e}")
            return False

        # Handle both "mcpServers" format and "servers" array format
        if "mcpServers" in self.config and not self.config.get("servers"):
            # Convert mcpServers format to servers array format
            logger.info("Converting 'mcpServers' format to 'servers' array format")
            servers = []
            for name, server_config in self.config["mcpServers"].items():
                # Extract command and combine with args
                command_parts = [server_config.get("command", "")]
                if "args" in server_config:
                    command_parts.extend(server_config["args"])
                
                # Create server entry
                server_entry = {
                    "name": name,
                    "command": " ".join(command_parts),
                    "config": {}  # Any server-specific config can go here
                }
                servers.append(server_entry)
            
            self.config["servers"] = servers

        # Connect to MCP servers
        logger.info("Connecting to all MCP servers")
        servers = self.config.get("servers", [])
        if not servers:
            logger.warning("No MCP servers configured")
            return False

        logger.info(f"Found {len(servers)} MCP servers in configuration")

        # Start MCP servers with a connection timeout
        success = await self._connect_all_servers(timeout=self.connection_timeout)
        self.initialized = success
        return success

    async def _connect_all_servers(self, *, timeout: float = 60.0) -> bool:
        """
        Connect to all configured MCP servers with timeout.

        Args:
            timeout: Timeout for connecting in seconds
        """
        servers = self.config.get("servers", [])
        if not servers:
            return False

        # Start each server in the background
        for server in servers:
            server_name = server.get("name", "")
            command = server.get("command", "")
            config = server.get("config", {})

            if not server_name or not command:
                logger.warning(f"Skipping invalid server configuration: {server}")
                continue

            # Start the server
            logger.info(f"Starting MCP stdio server {server_name}: {command}")
            
            # Create server parameters for the official SDK
            command_parts = command.split()
            if not command_parts:
                logger.warning(f"Invalid command for server {server_name}")
                continue
                
            # Extract executable and arguments
            executable = command_parts[0]
            args = command_parts[1:]
            
            # Create server parameters with shell=True to properly handle the complex command
            server_params = StdioServerParameters(
                command=executable,
                args=args,
                env=os.environ.copy(),
                shell=False  # Running without shell for better control
            )
            
            # Start the server in the background
            task = asyncio.create_task(
                self._run_server_in_background(server_name, server_params)
            )
            self.background_tasks[server_name] = task
            logger.info(f"Started background task for server {server_name}")

        # Wait for servers to start
        if servers:
            logger.info(f"Waiting {timeout} seconds to check for immediate startup failures...")
            # Wait a bit to check for immediate startup failures
            await asyncio.sleep(min(5.0, timeout / 3))

        # Check how many servers are connected
        connected_servers = len(self.sessions)
        total_servers = len(servers)
        logger.info(f"Connected to {connected_servers}/{total_servers} MCP servers")

        # Consider initialization successful if any servers connected
        return connected_servers > 0

    async def _run_server_in_background(self, server_name: str, server_params: StdioServerParameters):
        """
        Run an MCP server in the background using the official SDK.

        Args:
            server_name: Name of the server
            server_params: Server parameters for the official SDK
        """
        logger.info(f"Starting server {server_name} in background")
        
        try:
            # Connect to the server using the official SDK
            async with stdio_client(server_params) as (read, write):
                # Create a ClientSession
                async with ClientSession(read, write) as session:
                    # Initialize the connection
                    await session.initialize()
                    logger.info(f"Successfully initialized server {server_name}")
                    
                    # Store the session for later use
                    self.sessions[server_name] = session
                    
                    # Keep the connection open
                    while True:
                        await asyncio.sleep(5)
                        
                        # Check if the session is still alive - if not, exit the loop
                        if not session.is_connected():
                            logger.warning(f"Server {server_name} disconnected")
                            break
        except Exception as e:
            logger.error(f"Error running server {server_name}: {e}")
        finally:
            # Remove the session if it exists
            if server_name in self.sessions:
                logger.info(f"Removing server {server_name} from sessions")
                del self.sessions[server_name]

    async def close(self):
        """
        Close all MCP server connections.
        """
        logger.info("Closing all MCP connections")

        # Close background tasks
        for server_name, task in self.background_tasks.items():
            if not task.done():
                logger.info(f"Cancelling background task for server {server_name}")
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for {server_name} task to cancel")
                except asyncio.CancelledError:
                    logger.info(f"Task for {server_name} cancelled")
                except Exception as e:
                    logger.error(f"Error cancelling task for {server_name}: {e}")

        # Clear all collections
        self.sessions.clear()
        self.background_tasks.clear()
        self.tools_cache.clear()
        self.initialized = False

        logger.info("All MCP connections closed")

    async def list_tools(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get a list of all available tools from all MCP servers using the official SDK.
        
        Args:
            timeout: Maximum time to wait for tool discovery in seconds
            
        Returns:
            List of discovered tools
        """
        if not self.initialized:
            logger.warning("MCP client not initialized")
            return []
            
        if not timeout:
            timeout = 30.0  # Default timeout
            
        logger.info(f"Discovering tools from MCP servers (timeout: {timeout}s)")
        
        # Simple semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(10)
        
        # List to hold all tools
        all_tools = []
        
        # Function to get tools from a single server with timeout
        async def get_server_tools(server_name: str, session):
            async with semaphore:
                try:
                    # Skip servers that don't support tools/list
                    if not hasattr(session, "list_tools") or not callable(session.list_tools):
                        logger.debug(f"Server {server_name} does not support tool listing")
                        return []
                    
                    # Get tools with timeout
                    logger.debug(f"Getting tools from server {server_name}")
                    tools_result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
                    
                    # Process the tools result
                    # The SDK returns tools in a different format, process accordingly
                    tools = []
                    if hasattr(tools_result, "tools"):
                        # Handle SDK response object
                        tools = tools_result.tools
                    elif isinstance(tools_result, list):
                        # Direct list of tools
                        tools = tools_result
                    
                    # Format tools as needed for our application
                    formatted_tools = []
                    for tool in tools:
                        # Convert to our tool format
                        formatted_tool = self._tool_to_dict(tool, server_name)
                        formatted_tools.append(formatted_tool)
                    
                    logger.info(f"Server {server_name} returned {len(formatted_tools)} tools")
                    return formatted_tools
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout getting tools from server {server_name}")
                    return []
                except Exception as e:
                    logger.error(f"Error getting tools from server {server_name}: {e}")
                    return []
        
        # Create tasks for each server
        tasks = []
        for server_name, session in self.sessions.items():
            tasks.append(get_server_tools(server_name, session))
        
        # Run all tasks concurrently
        if tasks:
            try:
                results = await asyncio.gather(*tasks)
                # Combine all results
                for tools in results:
                    all_tools.extend(tools)
                
                logger.info(f"Discovered {len(all_tools)} tools from {len(tasks)} servers")
            except Exception as e:
                logger.error(f"Error gathering tools: {e}")
        
        return all_tools

    async def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed status information for all MCP servers.
        
        Returns:
            Dictionary of server status information
        """
        status = {}
        
        if not self.initialized:
            return {"overall": "not_initialized", "servers": {}}
        
        for server_name, session in self.sessions.items():
            server_status = {
                "connected": True,
                "has_list_tools": hasattr(session, "list_tools") and callable(session.list_tools),
                "background_task": None
            }
            
            # Check if there's a background task for this server
            if server_name in self.background_tasks:
                task = self.background_tasks[server_name]
                server_status["background_task"] = {
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                    "exception": str(task.exception()) if task.done() and not task.cancelled() and task.exception() else None
                }
            
            # Try to get basic info from the session
            if hasattr(session, "info") and callable(session.info):
                try:
                    # Use a timeout to avoid hanging
                    info = await asyncio.wait_for(session.info(), timeout=2.0)
                    server_status["info"] = info
                except Exception as e:
                    server_status["info_error"] = str(e)
            
            status[server_name] = server_status
        
        # For servers with background tasks but no session, add their status
        for server_name, task in self.background_tasks.items():
            if server_name not in self.sessions:
                if task.done():
                    if task.cancelled():
                        status[server_name] = {
                            "connected": False,
                            "status": "cancelled",
                            "exception": None
                        }
                    else:
                        exception = task.exception()
                        status[server_name] = {
                            "connected": False,
                            "status": "failed",
                            "exception": str(exception) if exception else "Unknown error"
                        }
                else:
                    status[server_name] = {
                        "connected": False,
                        "status": "starting",
                        "exception": None
                    }
        
        return status

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on a specific server.

        Args:
            server_name: Name of the server providing the tool.
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            Result of the tool call.

        Raises:
            Exception: If the server is not connected or the tool call fails.
        """
        if not self.initialized:
            raise Exception("MCP client not initialized")
            
        if server_name not in self.sessions:
            raise Exception(f"Server {server_name} not connected")
            
        session = self.sessions[server_name]
        if not hasattr(session, "call_tool") or not callable(session.call_tool):
            raise Exception(f"Server {server_name} does not support tool calls")
            
        logger.info(f"Calling tool {tool_name} on server {server_name}")
        
        try:
            # Call the tool with a timeout
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=60.0  # Default timeout of 60 seconds
            )
            
            logger.info(f"Tool {tool_name} call completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on server {server_name}: {e}")
            raise

    async def __aenter__(self):
        """
        Async context manager enter method.
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit method.
        """
        logger.info("Exiting MCP client context")
        await self.close()

    def _tool_to_dict(self, tool, server_name: str) -> Dict[str, Any]:
        """
        Convert a tool object to a dictionary with server information.

        Args:
            tool: Tool object from MCP.
            server_name: Name of the server providing the tool.

        Returns:
            Dictionary representation of the tool.
        """
        # Handle different tool formats from different SDK versions
        if isinstance(tool, dict):
            # SDK returns tool as a dictionary
            tool_dict = tool.copy()
        else:
            # SDK returns tool as an object
            tool_dict = {
                "name": getattr(tool, "name", None),
                "description": getattr(tool, "description", None),
                "parameters": getattr(tool, "parameters", None),
            }
        
        # Add server information
        tool_dict["server_name"] = server_name
        
        # Format for OpenAI function calling
        return {
            "type": "function",
            "function": {
                "name": f"mcp{tool_dict.get('name', '')}",
                "description": f"This is a tool from the {server_name} MCP server.\n\n{tool_dict.get('description', '')}",
                "parameters": tool_dict.get("parameters", {})
            },
            "server_name": server_name,
            "original_name": tool_dict.get("name", "")
        }
