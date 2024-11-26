"""
Server implementation for Model Context Protocol (MCP).

This module provides the base MCP server functionality that can be used
to expose gptme's tools and resources through the MCP protocol.
"""

import logging
from typing import Any, TypeVar
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, asdict

from .types import InitializationOptions, ServerInfo, McpError, ErrorCode
from .transport import Transport, JsonRpcRequest, JsonRpcResponse, JsonRpcNotification

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RequestContext:
    """Context for handling requests"""

    request_id: str
    method: str
    params: dict[str, Any]


class Server:
    """MCP server implementation"""

    def __init__(
        self,
        info: ServerInfo,
        options: InitializationOptions,
    ):
        self.info = info
        self.options = options
        self.transport: Transport | None = None

        # Request handlers
        self._handlers: dict[str, Callable[[RequestContext], Awaitable[Any]]] = {}

        # Setup default handlers
        self._setup_default_handlers()

    def _setup_default_handlers(self) -> None:
        """Setup default protocol handlers"""

        # Initialize
        self.register_handler("initialize", self._handle_initialize)

        # Resources
        self.register_handler("resources/list", self._handle_list_resources)
        self.register_handler("resources/read", self._handle_read_resource)

        # Tools
        self.register_handler("tools/list", self._handle_list_tools)
        self.register_handler("tools/call", self._handle_call_tool)

        # Prompts
        self.register_handler("prompts/list", self._handle_list_prompts)
        self.register_handler("prompts/get", self._handle_get_prompt)

    def register_handler(
        self, method: str, handler: Callable[[RequestContext], Awaitable[Any]]
    ) -> None:
        """Register a request handler"""
        self._handlers[method] = handler

    async def start(self, transport: Transport) -> None:
        """Start the server with the given transport"""
        self.transport = transport
        await transport.start()

        try:
            async for message in transport.receive():
                if isinstance(message, JsonRpcRequest):
                    await self._handle_request(message)
                elif isinstance(message, JsonRpcNotification):
                    await self._handle_notification(message)
        except Exception:
            logger.exception("Error in message loop")
            raise
        finally:
            await transport.stop()

    async def _handle_request(self, request: JsonRpcRequest) -> None:
        """Handle an incoming request"""
        if not self.transport:
            raise McpError(ErrorCode.INTERNAL_ERROR, "Transport not initialized")

        # Ensure we have a request ID
        if request.id is None:
            raise McpError(ErrorCode.INVALID_REQUEST, "Missing request ID")

        try:
            handler = self._handlers.get(request.method)
            if not handler:
                raise McpError(
                    ErrorCode.METHOD_NOT_FOUND, f"Method not found: {request.method}"
                )

            context = RequestContext(
                request_id=request.id,  # We know it's not None now
                method=request.method,
                params=request.params or {},
            )

            result = await handler(context)
            response = JsonRpcResponse(id=request.id, result=result)
            await self.transport.send(response)

        except McpError as e:
            error_response = JsonRpcResponse(
                id=request.id,
                error={"code": e.code.value, "message": e.message, "data": e.data},
            )
            await self.transport.send(error_response)

        except Exception as e:
            logger.exception("Error handling request")
            error_response = JsonRpcResponse(
                id=request.id,
                error={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": f"Internal error: {str(e)}",
                },
            )
            await self.transport.send(error_response)

    async def _handle_notification(self, notification: JsonRpcNotification) -> None:
        """Handle an incoming notification"""
        # Most notifications can be ignored, but log for debugging
        logger.debug("Received notification: %s", notification.method)

    # Default handlers

    async def _handle_initialize(self, context: RequestContext) -> dict[str, Any]:
        """Handle initialize request"""
        return {
            "serverInfo": asdict(self.info),
            "capabilities": self.options.capabilities,
        }

    async def _handle_list_resources(self, context: RequestContext) -> dict[str, Any]:
        """Handle resources/list request"""
        # Subclasses should override this
        return {"resources": [], "resourceTemplates": []}

    async def _handle_read_resource(self, context: RequestContext) -> dict[str, Any]:
        """Handle resources/read request"""
        # Subclasses should override this
        raise McpError(ErrorCode.METHOD_NOT_FOUND, "Resource reading not implemented")

    async def _handle_list_tools(self, context: RequestContext) -> dict[str, Any]:
        """Handle tools/list request"""
        # Subclasses should override this
        return {"tools": []}

    async def _handle_call_tool(self, context: RequestContext) -> dict[str, Any]:
        """Handle tools/call request"""
        # Subclasses should override this
        raise McpError(ErrorCode.METHOD_NOT_FOUND, "Tool execution not implemented")

    async def _handle_list_prompts(self, context: RequestContext) -> dict[str, Any]:
        """Handle prompts/list request"""
        # Subclasses should override this
        return {"prompts": []}

    async def _handle_get_prompt(self, context: RequestContext) -> dict[str, Any]:
        """Handle prompts/get request"""
        # Subclasses should override this
        raise McpError(ErrorCode.METHOD_NOT_FOUND, "Prompt templates not implemented")
