"""MCP session management."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .client import MCPClient
from .tools import MCPToolRegistry

logger = logging.getLogger(__name__)


class MCPSessionManager:
    """
    Manager for Model Context Protocol (MCP) sessions and tools.
    Handles the connection to MCP servers and tool registration.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the MCP session manager.

        Args:
            config_path: Optional path to the MCP configuration file.
                         If None, will look for mcp.json in current directory.
        """
        self.config_path = config_path or "mcp.json"
        self.client = MCPClient(config_path=self.config_path)
        self.tool_registry = MCPToolRegistry()
        self.initialized = False

    async def initialize(self, timeout: int = 45) -> bool:
        """
        Initialize MCP connections and register tools.

        Args:
            timeout: Maximum time in seconds to wait for initialization.

        Returns:
            bool: True if initialization successful, False otherwise.
        """
        try:
            # Create a task for initialization
            logger.info(f"Initializing MCP client (timeout: {timeout}s)")

            # Start the client initialization
            init_success = await self.client.initialize()

            if not init_success:
                logger.error("Failed to initialize MCP client")
                return False

            # Set a short timeout to allow servers to start in the background
            # but not block for too long
            await asyncio.sleep(2.0)

            # Check if any servers were successfully started
            if not self.client.sessions:
                logger.warning("No MCP servers were successfully connected")
                # We'll still return True if initialization itself succeeded,
                # even if no servers were connected yet
                
            self.initialized = True
            logger.info("MCP session manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing MCP session manager: {e}")
            import traceback

            logger.debug(f"Detailed error: {traceback.format_exc()}")
            return False

    async def close(self) -> None:
        """
        Close all MCP connections.
        """
        if self.initialized:
            await self.client.close()
            self.initialized = False
            logger.info("MCP session manager closed")

    async def __aenter__(self):
        """
        Async context manager enter.
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        """
        await self.close()

    async def get_tools(self) -> List[Any]:
        """
        Get all available tools from MCP servers.
        
        Implements retry logic with progressive backoff to handle servers
        that are still in the process of initializing.
        
        Returns:
            List of tool declarations
        """
        if not self.initialized:
            logger.warning("Getting tools from uninitialized MCP session manager")
            return []

        # Try to get tools with multiple retries
        max_retries = 3
        tools = []
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"Tool discovery attempt {attempt}/{max_retries}")
            
            # Get tools from the client
            tools = await self.client.list_tools()
            
            if tools:
                logger.info(f"Successfully found {len(tools)} tools on attempt {attempt}")
                return tools
            
            # If this isn't the last attempt and we found no tools, wait and retry
            if attempt < max_retries:
                # Progressive backoff: wait longer with each retry
                wait_time = 2 * attempt  # 2s, 4s, 6s, etc.
                logger.info(f"No tools found, waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        # If we get here, we've exhausted retries
        logger.warning(f"Failed to discover any tools after {max_retries} attempts")
        return []

    async def register_tools(self) -> List[Dict[str, Any]]:
        """
        Register tools from the MCP client.
        
        Returns:
            List of registered function declarations
        """
        if not self.initialized or not self.client:
            logger.warning("MCP client not initialized, cannot register tools")
            return []
        
        logger.info("Starting MCP tool registration process")
        
        # Get tools from the MCP client with fallback mechanism
        try:
            logger.info("Discovering tools from MCP servers...")
            raw_tools = await self.client.get_tools_with_fallback(timeout=60.0)  # Use our new fallback method
            
            if not raw_tools:
                logger.warning("No tools discovered from MCP servers")
                return []
            
            logger.info(f"Successfully discovered {len(raw_tools)} raw tools from MCP servers")
            
            # Group tools by server for better diagnostics
            tools_by_server = {}
            for tool in raw_tools:
                server_name = tool.get("server_name", "unknown")
                if server_name not in tools_by_server:
                    tools_by_server[server_name] = []
                tools_by_server[server_name].append(tool)
            
            # Log tool counts by server
            for server_name, server_tools in tools_by_server.items():
                logger.info(f"Server {server_name} provided {len(server_tools)} tools")
            
            # Convert raw tools to function declarations
            function_declarations = []
            for tool in raw_tools:
                try:
                    name = tool.get("name")
                    description = tool.get("description", "")
                    server_name = tool.get("server_name", "unknown")
                    
                    # Ensure the name is prefixed with the server name for uniqueness
                    # This helps avoid conflicts between tools from different servers
                    if name and not name.startswith(f"mcp{len(function_declarations)}"):
                        # Create a unique prefix for this tool
                        prefix = f"mcp{len(function_declarations)}_"
                        
                        # Format the function declaration
                        func_decl = {
                            "type": "function",
                            "function": {
                                "name": f"{prefix}{name}",
                                "description": f"This is a tool from the {server_name} MCP server.\n{description}",
                                "parameters": tool.get("inputSchema", {})
                            }
                        }
                        
                        # Add mapping for this tool
                        self.tool_registry.add_mapping(
                            function_name=func_decl["function"]["name"],
                            tool_name=name,
                            server_name=server_name
                        )
                        
                        function_declarations.append(func_decl)
                        logger.debug(f"Registered tool: {func_decl['function']['name']} from {server_name}")
                except Exception as e:
                    logger.error(f"Error converting tool to function declaration: {e}")
            
            logger.info(f"Successfully registered {len(function_declarations)} MCP tools")
            return function_declarations
        
        except Exception as e:
            logger.error(f"Error registering MCP tools: {e}")
            import traceback
            logger.error(f"Tool registration traceback: {traceback.format_exc()}")
            return []

    async def get_resources(self) -> List[Dict[str, Any]]:
        """Get all available MCP resources.

        Returns:
            List of available resources
        """
        return await self.resource_manager.list_resources()
