"""
Model Context Protocol (MCP) integration for gptme.

This module provides MCP server implementation that exposes gptme's tools
and capabilities through the standardized Model Context Protocol.
"""

import logging
import asyncio
from pathlib import Path
from typing import Any

from .types import (
    ServerInfo,
    InitializationOptions,
    Tool,
    McpError,
    ErrorCode,
)
from .server import Server, RequestContext
from .transport import StdioTransport

from ..tools import get_tool
from ..tools.base import ToolSpec as GptmeTool

logger = logging.getLogger(__name__)


class GptmeMcpServer(Server):
    """MCP server implementation for gptme"""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace
        self.tools: dict[str, GptmeTool] = {}

        # Initialize tools one by one
        for tool_name in ["shell", "python", "browser", "vision"]:
            if tool := get_tool(tool_name):
                self.tools[tool_name] = tool

        info = ServerInfo(
            name="gptme",
            version="0.1.0",  # TODO: Get from package version
        )

        options = InitializationOptions(
            capabilities={
                "tools": {},  # Enable tools capability
                "resources": {},  # Enable resources capability
            }
        )

        super().__init__(info, options)

    def _tool_to_mcp(self, tool: GptmeTool) -> Tool:
        """Convert a gptme tool to MCP tool format"""
        return Tool(
            name=tool.name,
            description=tool.__doc__ or "",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"}
                },
            },
        )

    async def _handle_list_tools(self, context: RequestContext) -> dict[str, Any]:
        """Handle tools/list request"""
        mcp_tools = [self._tool_to_mcp(tool) for tool in self.tools.values()]
        return {"tools": mcp_tools}

    async def _handle_call_tool(self, context: RequestContext) -> dict[str, Any]:
        """Handle tools/call request"""
        name = context.params.get("name")
        if not name:
            raise McpError(ErrorCode.INVALID_PARAMS, "Tool name required")

        tool = self.tools.get(name)
        if not tool:
            raise McpError(ErrorCode.INVALID_PARAMS, f"Tool not found: {name}")

        args = context.params.get("arguments", {})
        command = args.get("command")
        if not command:
            raise McpError(ErrorCode.INVALID_PARAMS, "Command required")

        try:
            # Check if tool is executable
            if tool.execute is None:
                return {
                    "content": {"type": "text", "text": "Tool not executable"},
                    "isError": True,
                }

            # Execute tool and handle both Message and Generator[Message] returns
            result = tool.execute(command, [], lambda _: True)
            if result is None:
                return {
                    "content": {"type": "text", "text": "No output"},
                    "isError": True,
                }

            messages = [result] if not hasattr(result, "__iter__") else list(result)
            if not messages:
                return {
                    "content": {"type": "text", "text": "No output"},
                    "isError": True,
                }

            first_msg = messages[0]
            return {
                "content": {
                    "type": "text",
                    "text": first_msg.content,
                }
            }
        except Exception as e:
            logger.exception("Error executing tool")
            return {
                "content": {"type": "text", "text": f"Error: {str(e)}"},
                "isError": True,
            }


async def run_server(workspace: Path | None = None) -> None:
    """Run the gptme MCP server"""
    server = GptmeMcpServer(workspace)
    transport = StdioTransport()

    try:
        await server.start(transport)
    except Exception:
        logger.exception("Server error")
        raise


def main() -> None:
    """Main entry point for running the MCP server"""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
