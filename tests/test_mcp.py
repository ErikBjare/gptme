"""Tests for MCP implementation"""

import pytest
from collections.abc import AsyncIterator

from gptme.mcp.types import ServerInfo, InitializationOptions, ErrorCode
from gptme.mcp.transport import (
    Transport,
    JsonRpcMessage,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcNotification,
)
from gptme.mcp.server import Server
from gptme.mcp import GptmeMcpServer


class MockTransport(Transport):
    """Mock transport for testing"""

    def __init__(self):
        self.sent_messages: list[JsonRpcMessage] = []
        self.messages_to_receive: list[JsonRpcMessage] = []
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, message: JsonRpcMessage) -> None:
        self.sent_messages.append(message)

    def receive(self) -> AsyncIterator[JsonRpcMessage]:
        async def message_iterator() -> AsyncIterator[JsonRpcMessage]:
            for message in self.messages_to_receive:
                yield message
            self._running = False

        return message_iterator()


@pytest.fixture
def mock_transport():
    return MockTransport()


@pytest.fixture
def server():
    info = ServerInfo(name="test", version="0.1.0")
    options = InitializationOptions(capabilities={"tools": {}, "resources": {}})
    return Server(info, options)


@pytest.mark.asyncio
async def test_server_initialization(server: Server, mock_transport: MockTransport):
    """Test server initialization"""
    # Setup initialization request
    init_request = JsonRpcRequest(id="1", method="initialize", params={})
    mock_transport.messages_to_receive.append(init_request)

    # Start server
    await server.start(mock_transport)

    # Check response
    assert len(mock_transport.sent_messages) == 1
    response = mock_transport.sent_messages[0]
    assert isinstance(response, JsonRpcResponse)
    assert response.id == "1"
    assert isinstance(response.result, dict)
    server_info = response.result.get("serverInfo", {})
    assert server_info.get("name") == "test"
    assert server_info.get("version") == "0.1.0"
    assert "capabilities" in response.result


@pytest.mark.asyncio
async def test_gptme_server_tools(mock_transport: MockTransport):
    """Test gptme MCP server tool handling"""
    server = GptmeMcpServer()

    # List tools request
    list_tools_request = JsonRpcRequest(id="1", method="tools/list", params={})
    mock_transport.messages_to_receive.append(list_tools_request)

    # Start server
    await server.start(mock_transport)

    # Check response
    assert len(mock_transport.sent_messages) == 1
    response = mock_transport.sent_messages[0]
    assert isinstance(response, JsonRpcResponse)
    assert response.id == "1"
    assert isinstance(response.result, dict)
    tools = response.result.get("tools", [])
    assert isinstance(tools, list)
    assert len(tools) > 0

    # Verify tool format
    tool = tools[0]
    assert isinstance(tool, dict)
    assert "name" in tool
    assert "description" in tool
    assert "inputSchema" in tool


@pytest.mark.asyncio
async def test_error_handling(server: Server, mock_transport: MockTransport):
    """Test error handling"""
    # Invalid method request
    invalid_request = JsonRpcRequest(id="1", method="invalid_method", params={})
    mock_transport.messages_to_receive.append(invalid_request)

    # Start server
    await server.start(mock_transport)

    # Check error response
    assert len(mock_transport.sent_messages) == 1
    response = mock_transport.sent_messages[0]
    assert isinstance(response, JsonRpcResponse)
    assert response.id == "1"
    assert response.error is not None
    assert response.error["code"] == ErrorCode.METHOD_NOT_FOUND.value


@pytest.mark.asyncio
async def test_notification_handling(server: Server, mock_transport: MockTransport):
    """Test notification handling"""
    # Send a notification
    notification = JsonRpcNotification(method="test_notification", params={})
    mock_transport.messages_to_receive.append(notification)

    # Start server
    await server.start(mock_transport)

    # Check that no response was sent
    assert len(mock_transport.sent_messages) == 0
