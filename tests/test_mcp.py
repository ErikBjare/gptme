"""Unit tests for the MCP integration."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gptme.mcp.client import MCPClient
from gptme.mcp.config import MCPConfig
from gptme.mcp.resource import MCPResourceManager
from gptme.mcp.session import MCPSessionManager
from gptme.mcp.tools import MCPToolAdapter, MCPToolRegistry


@pytest.fixture
def mock_config():
    """Create a temporary config file with mock MCP server configuration."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "mcpServers": {
                    "test_server": {
                        "command": "echo",
                        "args": ["test"],
                        "env": {"TEST": "value"},
                    }
                }
            },
            f,
        )
    yield f.name
    os.unlink(f.name)


class TestMCPConfig:
    """Test the MCP configuration class."""

    def test_load_from_file(self, mock_config):
        """Test loading configuration from a file."""
        config = MCPConfig(mock_config)
        assert "test_server" in config.get_all_servers()
        assert config.get_server_config("test_server")["command"] == "echo"

    def test_get_server_config(self, mock_config):
        """Test getting a specific server config."""
        config = MCPConfig(mock_config)
        server_config = config.get_server_config("test_server")
        assert server_config is not None
        assert server_config["command"] == "echo"
        assert server_config["args"] == ["test"]
        assert server_config["env"] == {"TEST": "value"}

    def test_get_nonexistent_server(self, mock_config):
        """Test getting a nonexistent server config."""
        config = MCPConfig(mock_config)
        server_config = config.get_server_config("nonexistent")
        assert server_config is None


@pytest.mark.asyncio
class TestMCPClient:
    """Test the MCP client class."""

    async def test_connect_server(self):
        """Test connecting to an MCP server."""
        client = MCPClient()
        
        # Mock the stdio_client and ClientSession
        with patch("mcp.client.stdio.stdio_client", new_callable=AsyncMock) as mock_stdio, \
             patch("mcp.ClientSession", new_callable=AsyncMock) as mock_session:
            
            # Set up mocks
            mock_stdio.return_value = (MagicMock(), MagicMock())
            mock_session_instance = mock_session.return_value
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
            mock_session_instance.list_resources = AsyncMock(return_value=MagicMock(resources=[]))
            
            # Test connecting
            result = await client.connect_server("test", {"command": "test_cmd", "args": []})
            assert result is True
            
            # Verify mocks were called
            mock_stdio.assert_called_once()
            mock_session_instance.initialize.assert_called_once()
            mock_session_instance.list_tools.assert_called_once()
            mock_session_instance.list_resources.assert_called_once()

    async def test_call_tool(self):
        """Test calling a tool on an MCP server."""
        client = MCPClient()
        
        # Set up mock session
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=MagicMock())
        
        # Add mock session to client
        client.sessions = {
            "test_server": {
                "session": mock_session,
                "config": {},
            }
        }
        
        # Test calling tool
        await client.call_tool("test_server", "test_tool", {"arg": "value"})
        mock_session.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
        
        # Test calling tool on nonexistent server
        with pytest.raises(ValueError):
            await client.call_tool("nonexistent", "test_tool", {})


@pytest.mark.asyncio
class TestMCPToolRegistry:
    """Test the MCP tool registry."""

    async def test_register_tools(self):
        """Test registering MCP tools."""
        # Create mock client
        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            {
                "server_id": "test",
                "name": "test_tool",
                "description": "Test tool",
                "schema": {
                    "properties": {
                        "arg1": {
                            "type": "string",
                            "description": "Argument 1"
                        }
                    },
                    "required": ["arg1"]
                }
            }
        ])
        
        # Create registry
        registry = MCPToolRegistry(mock_client)
        
        # Register tools
        tools = await registry.register_all_tools()
        
        # Check results
        assert len(tools) == 1
        assert tools[0].name == "mcp_test_test_tool"
        assert tools[0].desc == "Test tool"
        
        # Test getting a tool
        tool = registry.get_tool("test", "test_tool")
        assert tool is not None
        assert tool.name == "mcp_test_test_tool"


@pytest.mark.asyncio
class TestMCPSessionManager:
    """Test the MCP session manager."""

    async def test_initialize(self, mock_config):
        """Test initializing the MCP session manager."""
        # Create mock client
        with patch("gptme.mcp.session.MCPClient") as mock_client_class, \
             patch("gptme.mcp.session.MCPToolRegistry") as mock_registry_class:
            
            # Set up mocks
            mock_client = mock_client_class.return_value
            mock_client.connect_server = AsyncMock(return_value=True)
            
            mock_registry = mock_registry_class.return_value
            mock_registry.register_all_tools = AsyncMock(return_value=[])
            
            # Create manager
            manager = MCPSessionManager(mock_config)
            
            # Initialize
            result = await manager.initialize()
            
            # Check results
            assert result is True
            mock_client.connect_server.assert_called_once()
            mock_registry.register_all_tools.assert_called_once()
            
            # Test shutdown
            await manager.shutdown()
            mock_client.disconnect_all.assert_called_once() 