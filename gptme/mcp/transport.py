"""
Transport implementations for Model Context Protocol (MCP).

Supports stdio and SSE transports.
"""

import sys
import json
import asyncio
from typing import Any, cast
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .types import McpError, ErrorCode


@dataclass
class JsonRpcMessage:
    """Base class for JSON-RPC messages"""

    jsonrpc: str = "2.0"


@dataclass
class JsonRpcRequest(JsonRpcMessage):
    """JSON-RPC request message"""

    params: dict[str, Any] | None = field(default=None)
    method: str = field(default="")
    id: str | None = field(default=None)


@dataclass
class JsonRpcResponse(JsonRpcMessage):
    """JSON-RPC response message"""

    error: dict[str, Any] | None = field(default=None)
    id: str = field(default="")
    result: Any | None = field(default=None)


@dataclass
class JsonRpcNotification(JsonRpcMessage):
    """JSON-RPC notification message (no response expected)"""

    params: dict[str, Any] | None = field(default=None)
    method: str = field(default="")


class Transport(ABC):
    """Abstract base class for MCP transports"""

    @abstractmethod
    async def start(self) -> None:
        """Start the transport"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport"""
        pass

    @abstractmethod
    async def send(self, message: JsonRpcMessage) -> None:
        """Send a message"""
        pass

    @abstractmethod
    def receive(self) -> AsyncIterator[JsonRpcMessage]:
        """Get message iterator"""
        pass


class StdioTransport(Transport):
    """Transport implementation using stdin/stdout"""

    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False

    async def start(self) -> None:
        """Start the transport with proper stream initialization"""
        loop = asyncio.get_event_loop()

        # Initialize reader
        self._reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

        # Initialize writer with a proper protocol
        class WriterProtocol(asyncio.BaseProtocol):
            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                pass

            def connection_lost(self, exc: Exception | None) -> None:
                pass

        transport, protocol = await loop.connect_write_pipe(
            WriterProtocol, sys.stdout.buffer
        )
        self._writer = asyncio.StreamWriter(
            transport, cast(asyncio.BaseProtocol, protocol), self._reader, loop
        )

        self._running = True

    async def stop(self) -> None:
        """Stop the transport"""
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    async def send(self, message: JsonRpcMessage) -> None:
        """Send a message through the transport"""
        if not self._running or not self._writer:
            raise McpError(ErrorCode.INTERNAL_ERROR, "Transport not started")

        data = json.dumps(message.__dict__)
        self._writer.write(f"{data}\n".encode())
        await self._writer.drain()

    def receive(self) -> AsyncIterator[JsonRpcMessage]:
        """Get message iterator"""
        if not self._running or not self._reader:
            raise McpError(ErrorCode.INTERNAL_ERROR, "Transport not started")

        reader = self._reader  # Capture for async closure

        async def message_iterator() -> AsyncIterator[JsonRpcMessage]:
            while self._running:
                try:
                    line = await reader.readline()
                    if not line:  # EOF
                        break

                    data = json.loads(line.decode())

                    # Determine message type
                    if "method" in data:
                        if "id" in data:
                            yield JsonRpcRequest(**data)
                        else:
                            yield JsonRpcNotification(**data)
                    else:
                        yield JsonRpcResponse(**data)

                except json.JSONDecodeError as e:
                    raise McpError(
                        ErrorCode.PARSE_ERROR, f"Invalid JSON: {str(e)}"
                    ) from e
                except Exception as e:
                    raise McpError(
                        ErrorCode.INTERNAL_ERROR, f"Transport error: {str(e)}"
                    ) from e

        return message_iterator()


# TODO: Implement SSETransport class for HTTP/SSE transport
class SSETransport(Transport):
    """Transport implementation using Server-Sent Events"""

    pass
