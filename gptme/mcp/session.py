"""MCP session management for gptme."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from gptme.mcp.client import MCPClient
from gptme.mcp.config import MCPConfig
from gptme.mcp.resource import MCPResourceManager
from gptme.mcp.tools import MCPToolRegistry

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