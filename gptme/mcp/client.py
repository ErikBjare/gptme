"""Model Context Protocol client for gptme."""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP client that manages connections to MCP servers using the standard MCP protocol.
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize an MCP client with a configuration path.

        Args:
            config_path: Path to the MCP configuration file. If None, uses 'mcp.json' in current directory.
        """
        self.config_path = Path(config_path) if config_path else Path("mcp.json")
        self.config = None
        self.sessions = {}  # Server connections
        self.background_tasks = {}  # Background tasks for each server
        self.tools_cache = {}  # Cache for tools from each server
        self.initialized = False
        self.connection_timeout = 20  # seconds

    async def initialize(self) -> bool:
        """
        Initialize the MCP client by loading configuration and connecting to servers.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        try:
            # Load configuration
            if not self.config_path.exists():
                logger.error(f"MCP configuration file not found at {self.config_path}")
                return False

            with open(self.config_path) as f:
                self.config = json.load(f)

            # Handle both configuration formats:
            # 1. New format: {"servers": [{"name": "server1", "type": "stdio", ...}, ...]}
            # 2. Old format: {"mcpServers": {"server1": {"command": "...", ...}, ...}}

            # Check for new format
            if "servers" in self.config:
                logger.info("Using 'servers' array configuration format")
                # Already in the expected format
                pass
            # Check for old format
            elif "mcpServers" in self.config:
                logger.info("Converting 'mcpServers' format to 'servers' array format")
                # Convert old format to new format
                servers_config = []
                for name, config in self.config["mcpServers"].items():
                    server_config = config.copy()
                    server_config["name"] = name
                    server_config["type"] = "stdio"
                    servers_config.append(server_config)

                # Update config with new format
                self.config["servers"] = servers_config
            else:
                logger.error("No MCP servers defined in configuration (missing 'servers' or 'mcpServers')")
                return False

            # Initialize all enabled servers
            await self._connect_all_servers()
            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    async def _connect_all_servers(self, *, timeout: float = 60.0) -> None:
        """
        Connect to all configured MCP servers with timeout.

        Args:
            timeout: Timeout for connecting in seconds
        """
        logger.info("Connecting to all MCP servers")

        # Clear existing state
        self.sessions = {}
        self.tools_cache = {}

        # Get server configurations
        try:
            servers_config = self.config.get("servers", [])
            if not servers_config:
                logger.warning("No MCP servers configured")
                return

            logger.info(f"Found {len(servers_config)} MCP servers in configuration")

            # Start background tasks for each server
            for server_config in servers_config:
                server_name = server_config.get("name", "unnamed")
                server_type = server_config.get("type", "stdio")

                if server_type == "stdio":
                    # Extract stdio-specific configuration
                    command = server_config.get("command", "npx")
                    args = server_config.get("args", [])

                    # Merge environment variables
                    env = os.environ.copy()
                    env.update(server_config.get("env", {}))

                    logger.info(f"Starting MCP stdio server {server_name}: {command} {' '.join(args)}")

                    try:
                        # Create server parameters
                        server_params = StdioServerParameters(command=command, args=args, env=env)

                        # Start the server in the background
                        task = asyncio.create_task(self._run_server_in_background(server_name, server_params))

                        # Store the task
                        self.background_tasks[server_name] = task

                        logger.info(f"Started background task for server {server_name}")
                    except Exception as e:
                        logger.error(f"Failed to start server {server_name}: {e}")
                else:
                    logger.error(f"Unsupported server type: {server_type}")

            # Wait briefly for initialization, but not for the complete timeout
            # This gives servers a chance to start up and register tools
            if self.background_tasks:
                init_time = min(10.0, timeout / 2)
                logger.info(f"Waiting {init_time:.1f} seconds for servers to initialize...")
                await asyncio.sleep(init_time)

                # Check for any quick failures
                failed_tasks = []
                for server_name, task in self.background_tasks.items():
                    if task.done() and not task.cancelled():
                        try:
                            task.result()  # This will raise the exception if there was one
                        except Exception as e:
                            logger.error(f"Server {server_name} failed to start: {e}")
                            failed_tasks.append(server_name)

                # Remove failed tasks
                for server_name in failed_tasks:
                    del self.background_tasks[server_name]

                if not self.background_tasks:
                    logger.error("All MCP servers failed to start")
                else:
                    logger.info(f"{len(self.background_tasks)} MCP servers started successfully")
                    # Set initialized flag
                    self.initialized = True
            else:
                logger.warning("No MCP servers were started")
        except Exception as e:
            logger.error(f"Failed to connect to MCP servers: {e}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Reset state
            self.close()
            raise

    async def _run_server_in_background(self, server_name: str, server_params: Any) -> None:
        """
        Run an MCP server in the background.

        Args:
            server_name: Name of the server
            server_params: Server parameters
        """
        try:
            logger.info(f"Starting server {server_name} in background")

            # Get the server client based on type
            if isinstance(server_params, StdioServerParameters):
                server_client = stdio_client
            else:
                logger.error(f"Unsupported server parameters type: {type(server_params)}")
                return

            # Connect to the server
            try:
                logger.debug(f"Connecting to server {server_name} with params: {server_params}")
                async with server_client(server_params) as (read_stream, write_stream):
                    logger.info(f"Connected to server {server_name}")

                    # Create a session
                    try:
                        # Create session with standard initialization
                        session = ClientSession(read_stream, write_stream)

                        # Add a timeout to initialize
                        try:
                            await asyncio.wait_for(session.initialize(), timeout=30.0)

                            logger.info(f"Initialized session for {server_name}")

                            # Store the session
                            self.sessions[server_name] = session
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout initializing session for {server_name}")
                            raise  # Re-raise to be caught by outer exception handler
                        except Exception as e:
                            logger.error(f"Error during session initialization: {e}")
                            raise  # Re-raise to be caught by outer exception handler

                        # Cache tools
                        try:
                            # Add some debugging output
                            logger.debug(f"Requesting tools list from {server_name}")

                            # Use timeout to avoid hanging
                            tools_result = await asyncio.wait_for(session.list_tools(), timeout=10.0)

                            # Log what was received
                            logger.debug(f"Received tools result from {server_name}: {tools_result}")

                            if hasattr(tools_result, "tools"):
                                self.tools_cache[server_name] = tools_result.tools
                                logger.info(f"Cached {len(tools_result.tools)} tools from {server_name}")
                                # List tool names for debugging
                                tool_names = [t.name for t in tools_result.tools]
                                logger.debug(f"Tool names: {tool_names}")
                            else:
                                logger.warning(f"No tools attribute in result from {server_name}")
                                logger.debug(f"Result attributes: {dir(tools_result)}")
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout while listing tools from {server_name}")
                        except Exception as e:
                            logger.error(f"Failed to list tools from {server_name}: {e}")
                            import traceback

                            logger.debug(f"Traceback: {traceback.format_exc()}")

                        # Server is running and initialized
                        logger.info(f"Server {server_name} is now running")

                        # Keep the session alive
                        try:
                            while True:
                                # Periodically ping to keep connection alive
                                await asyncio.sleep(30)
                                logger.debug(f"Pinging server {server_name}")
                                # We won't actually ping for now since it might not be implemented
                                # on all servers
                        except asyncio.CancelledError:
                            logger.info(f"Background task for {server_name} was cancelled")
                            raise
                        except Exception as e:
                            logger.error(f"Error in background task for {server_name}: {e}")
                            import traceback

                            logger.debug(f"Traceback: {traceback.format_exc()}")
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout initializing session for {server_name}")
                        raise  # Re-raise to be caught by outer exception handler
                    except Exception as e:
                        logger.error(f"Failed to initialize session for {server_name}: {e}")
                        import traceback

                        logger.debug(f"Traceback: {traceback.format_exc()}")
            except Exception as e:
                logger.error(f"Failed to connect to server {server_name}: {e}")
                import traceback

                logger.debug(f"Traceback: {traceback.format_exc()}")
        except asyncio.CancelledError:
            logger.info(f"Background task for {server_name} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in background task for {server_name}: {e}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")
        finally:
            logger.info(f"Background task for {server_name} is ending")

    async def close(self) -> None:
        """
        Close all MCP server connections.
        """
        logger.info("Closing all MCP connections")

        # Cancel all keep-alive futures to trigger cleanup
        keep_alive_futures = getattr(self, "_keep_alive_futures", {})
        for server_name, future in keep_alive_futures.items():
            if not future.done():
                future.cancel()

        # Wait for all background tasks to complete
        if self.background_tasks:
            tasks = list(self.background_tasks.values())
            if tasks:
                logger.info(f"Waiting for {len(tasks)} background tasks to complete")
                try:
                    # Wait with a timeout
                    done, pending = await asyncio.wait(tasks, timeout=5)

                    # Cancel any remaining tasks
                    for task in pending:
                        task.cancel()

                    # Wait again briefly for cancelled tasks
                    if pending:
                        await asyncio.wait(pending, timeout=2)
                except Exception as e:
                    logger.error(f"Error waiting for background tasks: {e}")

        # Clear all collections
        self.sessions.clear()
        self.background_tasks.clear()
        self.tools_cache.clear()
        self._keep_alive_futures = {}
        self.initialized = False

        logger.info("All MCP connections closed")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all tools from all connected MCP servers.

        Returns:
            List of tool specifications
        """
        logger.info("Listing all tools from connected MCP servers")

        tools = []

        # Wait for background tasks to complete initialization if they're still running
        pending_tasks = [task for task in self.background_tasks.values() if not task.done() and not task.cancelled()]

        if pending_tasks:
            logger.info(f"Waiting for {len(pending_tasks)} servers to complete initialization...")
            try:
                # Wait for a short time for initialization to complete
                # but don't block forever
                done, pending = await asyncio.wait(pending_tasks, timeout=5.0, return_when=asyncio.ALL_COMPLETED)

                if pending:
                    logger.warning(f"{len(pending)} servers are still initializing")
            except Exception as e:
                logger.error(f"Error waiting for server initialization: {e}")

        # Check the tools cache first
        if self.tools_cache:
            logger.info(f"Found tools in cache for {list(self.tools_cache.keys())} servers")
            for server_name, server_tools in self.tools_cache.items():
                for tool in server_tools:
                    try:
                        # Add server_name to the tool info
                        tool_info = {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": getattr(tool, "inputSchema", {}),
                            "server_name": server_name,
                        }
                        tools.append(tool_info)
                        logger.debug(f"Added tool from cache: {tool.name} from {server_name}")
                    except Exception as e:
                        logger.error(f"Error processing cached tool: {e}")
        else:
            logger.warning("No tools found in cache, will attempt direct discovery")

        # If there are no tools in the cache, or we want to refresh,
        # check each active session
        if not tools and self.sessions:
            logger.info(f"Attempting direct tool discovery from {len(self.sessions)} active sessions")
            for server_name, session in self.sessions.items():
                try:
                    logger.debug(f"Requesting tools from server: {server_name}")
                    # Add timeout to avoid hanging
                    tools_result = await asyncio.wait_for(session.list_tools(), timeout=10.0)

                    # Log the raw response for debugging
                    logger.debug(f"Raw tools result: {tools_result}")

                    # Extract tools from the result
                    if hasattr(tools_result, "tools") and tools_result.tools:
                        server_tools = tools_result.tools
                        logger.info(f"Found {len(server_tools)} tools from server {server_name}")

                        # Cache these tools for future use
                        self.tools_cache[server_name] = server_tools

                        # Add to our results
                        for tool in server_tools:
                            tool_info = {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": getattr(tool, "inputSchema", {}),
                                "server_name": server_name,
                            }
                            tools.append(tool_info)
                            logger.debug(f"Added tool from direct discovery: {tool.name} from {server_name}")
                    else:
                        logger.warning(f"No tools found in result from server {server_name}")
                        # Log the result structure for debugging
                        logger.debug(f"Result attributes: {dir(tools_result)}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout requesting tools from server {server_name}")
                except Exception as e:
                    logger.error(f"Error requesting tools from server {server_name}: {e}")
                    import traceback

                    logger.debug(f"Traceback: {traceback.format_exc()}")

        if not tools:
            # As a last resort, check if any tasks have completed and examine their results
            logger.warning("No tools found through normal methods, checking task results")
            for server_name, task in self.background_tasks.items():
                if task.done() and not task.cancelled():
                    try:
                        # Try to extract any useful information from the completed task
                        result = task.result()
                        logger.debug(f"Task result for {server_name}: {result}")

                        # Look for tools in the result
                        if isinstance(result, dict) and "tools" in result:
                            server_tools = result["tools"]
                            logger.info(f"Found {len(server_tools)} tools in task result for {server_name}")
                            for tool in server_tools:
                                tool_info = {
                                    "name": tool.get("name", "unknown"),
                                    "description": tool.get("description", "No description"),
                                    "inputSchema": tool.get("inputSchema", {}),
                                    "server_name": server_name,
                                }
                                tools.append(tool_info)
                    except Exception as e:
                        logger.error(f"Error extracting tools from task result for {server_name}: {e}")

        logger.info(f"Total tools found: {len(tools)}")
        return tools

    def _tool_to_dict(self, tool, server_name: str) -> Dict[str, Any]:
        """
        Convert a tool object to a dictionary with server information.

        Args:
            tool: Tool object from MCP.
            server_name: Name of the server providing the tool.

        Returns:
            Dictionary representation of the tool.
        """
        return {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.inputSchema,
            "server_name": server_name,
        }

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
        if server_name not in self.sessions:
            raise Exception(f"Server {server_name} not connected")

        try:
            # Call the tool on the specified server
            session = self.sessions[server_name]
            result = await session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            raise Exception(f"Failed to call tool {tool_name} on {server_name}: {e}")

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
