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
        """Get all available tools from MCP servers."""
        if not self.initialized:
            logger.warning("Getting tools from uninitialized MCP session manager")
            return []

        return await self.client.list_tools()

    async def get_resources(self) -> List[Dict[str, Any]]:
        """Get all available MCP resources.

        Returns:
            List of available resources
        """
        return await self.resource_manager.list_resources()
