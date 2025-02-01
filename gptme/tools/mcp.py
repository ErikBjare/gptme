"""MCP client tool for gptme."""

import ast
import json
import logging
import asyncio
from collections.abc import Callable, Generator
from contextlib import AsyncExitStack
from typing import Any, TypeAlias

import anyio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from mcp.types import (
    TextContent,
    ImageContent,
    EmbeddedResource,
    AnyUrl,
)
from pydantic import AnyHttpUrl

from ..message import Message
from .base import ConfirmFunc, Parameter, ToolSpec

# Type alias for parameter arguments
ParameterArgs: TypeAlias = dict[str, str | bool | None]


logger = logging.getLogger(__name__)


def parse_args(args_str: str) -> dict[str, Any]:
    """Safely parse arguments from string."""
    try:
        # First try as JSON
        return json.loads(args_str)
    except json.JSONDecodeError:
        try:
            # Then try as Python literal
            return ast.literal_eval(args_str)
        except (SyntaxError, ValueError) as e:
            raise ValueError(
                "Arguments must be valid JSON or Python literal dictionary"
            ) from e


class MCPCommandHandler:
    """Handles MCP commands and manages server connections."""

    def __init__(self):
        self._servers: dict[str, anyio.Event] = {}  # server_name -> stop_event
        self._sessions: dict[str, tuple[ClientSession, AsyncExitStack]] = {}
        self._lock = anyio.Lock()
        self._send_stream: (
            anyio.streams.memory.MemoryObjectSendStream[Message] | None
        ) = None

    async def send_message(self, text: str) -> None:
        """Send a message to the output stream."""
        if self._send_stream:
            await self._send_stream.send(Message("assistant", text))

    async def handle_disconnect(self, args: list[str]) -> None:
        """Handle disconnect command."""
        if len(args) < 1:
            await self.send_message("Please specify server name")
            return
        server_name = args[0]
        await self.cleanup(server_name)
        await self.send_message(f"Disconnected from MCP server: {server_name}")

    async def handle_connect(self, args: list[str]) -> None:
        """Handle connect command."""
        if len(args) < 1:
            await self.send_message("Please specify server path")
            return
        try:
            name = args[1] if len(args) > 1 else None
            server_name = await self.connect_server(args[0], name)
            await self.send_message(f"Connected to MCP server: {server_name}")
        except Exception as e:
            await self.send_message(f"Failed to connect to server: {str(e)}")

    async def handle_list(self, cmd_type: str, args: list[str]) -> None:
        """Handle list commands (tools/resources/prompts)."""
        if len(args) < 1:
            await self.send_message(f"Please specify server name for {cmd_type}")
            return

        items = await getattr(self, f"list_{cmd_type}")(args[0])
        if not items:
            await self.send_message(f"No {cmd_type} available")
            return

        items_str = self._format_list_output(cmd_type, items)
        await self.send_message(items_str)

    def _format_list_output(self, cmd_type: str, items: list[dict[str, Any]]) -> str:
        """Format the output of list commands."""
        if cmd_type == "tools":
            return "Available tools:\n" + "\n".join(
                f"- {t['name']}: {t['description']}\n  Arguments: {t['arguments']}"
                for t in items
            )
        elif cmd_type == "resources":
            return "Available resources:\n" + "\n".join(
                f"- {r['uri_template']}: {r['description']}" for r in items
            )
        else:  # prompts
            return "Available prompts:\n" + "\n".join(
                f"- {p['name']}: {p['description']}\n  Arguments: {p['arguments']}"
                for p in items
            )

    async def handle_call(self, args: list[str]) -> None:
        """Handle tool call command."""
        if len(args) < 3:
            await self.send_message("Usage: call <server> <tool> <args>")
            return
        server_name, tool_name = args[0:2]
        tool_args = parse_args(args[2])
        result = await self.call_tool(server_name, tool_name, tool_args)
        await self.send_message(f"Tool result: {result}")

    async def handle_read(self, args: list[str]) -> None:
        """Handle resource read command."""
        if len(args) < 2:
            await self.send_message("Usage: read <server> <resource_uri>")
            return
        try:
            # Convert string to AnyUrl
            url = AnyHttpUrl(args[1])
            content, mime_type = await self.read_resource(args[0], url)
            await self.send_message(f"Resource content ({mime_type}):\n{content}")
        except ValueError as e:
            await self.send_message(f"Invalid URL: {e}")

    async def handle_prompt(self, args: list[str]) -> None:
        """Handle prompt command."""
        if len(args) < 3:
            await self.send_message("Usage: prompt <server> <name> <args>")
            return
        server_name, prompt_name = args[0:2]
        prompt_args = parse_args(args[2])
        messages = await self.get_prompt(server_name, prompt_name, prompt_args)
        formatted_messages = []
        for m in messages:
            role = m["role"]
            content = m["content"]

            match content:
                case TextContent(text=text):
                    formatted_text = text
                case ImageContent(mimeType=mime_type):
                    formatted_text = f"[Image: {mime_type}]"
                case EmbeddedResource(resource=resource):
                    formatted_text = f"[Resource: {resource.uri}]"
                case _:
                    formatted_text = str(content)

            formatted_messages.append(f"{role}: {formatted_text}")

        await self.send_message("Prompt messages:\n" + "\n".join(formatted_messages))

    async def execute_command(self, command: str) -> None:
        """Execute an MCP command."""
        logger.info("Executing command: %s", command)
        try:
            parts = command.split(maxsplit=3)
            if not parts:
                await self.send_message("Please specify an MCP command")
                return

            cmd, *args = parts
            handlers = {
                "disconnect": self.handle_disconnect,
                "connect": self.handle_connect,
                "tools": lambda args: self.handle_list("tools", args),
                "resources": lambda args: self.handle_list("resources", args),
                "prompts": lambda args: self.handle_list("prompts", args),
                "call": self.handle_call,
                "read": self.handle_read,
                "prompt": self.handle_prompt,
            }

            if cmd in handlers:
                await handlers[cmd](args)
            else:
                await self.send_message(f"Unknown MCP command: {cmd}")

        except Exception as e:
            logger.exception("Error executing MCP command")
            await self.send_message(f"Error executing MCP command: {str(e)}")

    async def _server_loop(
        self,
        server_name: str,
        server_params: StdioServerParameters,
        stop_event: anyio.Event,
        connection_ready: anyio.Event,
    ):
        """Run the server event loop."""
        logger.info(
            "Starting server loop for %s with params: %s", server_name, server_params
        )
        try:
            async with AsyncExitStack() as stack:
                logger.info(
                    "Creating stdio transport with command: %s %s",
                    server_params.command,
                    " ".join(server_params.args),
                )
                try:
                    stdio_transport = await stack.enter_async_context(
                        stdio_client(server_params)
                    )
                    logger.info("Stdio transport created successfully")
                except Exception as e:
                    logger.error("Failed to create stdio transport: %s", e)
                    raise
                read_stream, write_stream = stdio_transport
                logger.info("Creating client session...")
                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                logger.info("Initializing session...")
                await session.initialize()

                logger.info("Session initialized, storing in sessions dict...")
                self._sessions[server_name] = (session, stack)

                # Signal that connection is ready
                connection_ready.set()
                logger.info("Connection ready event set, waiting for stop event...")

                # Keep the server running until stopped
                await stop_event.wait()
                logger.info("Stop event received, server loop completing")
        finally:
            if server_name in self._sessions:
                del self._sessions[server_name]

    async def connect_server(self, server_path: str, name: str | None = None) -> str:
        """Connect to an MCP server."""
        async with self._lock:
            # Validate server name
            server_name = name or f"mcp_server_{len(self._sessions)}"
            if server_name in self._servers:
                raise ValueError(f"Server name '{server_name}' already in use")

            # Create server parameters with safe environment and uv
            server_params = StdioServerParameters(
                command="uv",
                args=["run", "--with", "mcp", server_path],
                env=get_default_environment(),
            )

            try:
                # Create stop event and start server loop
                stop_event = anyio.Event()
                self._servers[server_name] = stop_event

                logger.info("Starting server loop for %s", server_name)

                # Create a nursery for concurrent tasks
                async def connection_monitor():
                    logger.info("Starting connection monitor...")
                    for i in range(50):  # 5 second timeout
                        if server_name in self._sessions:
                            logger.info("Session established after %d attempts", i)
                            return True
                        logger.debug("Waiting... attempt %d", i)
                        await anyio.sleep(0.1)
                    logger.error("Session establishment timed out")
                    return False

                async def setup_connection():
                    logger.info("Setting up connection...")
                    success = False

                    connection_ready = anyio.Event()

                    async def run_server():
                        nonlocal success
                        try:
                            logger.info("Starting server loop task")
                            await self._server_loop(
                                server_name, server_params, stop_event, connection_ready
                            )
                            logger.info("Server loop task completed normally")
                        except Exception as e:
                            logger.error("Server loop failed: %s", e)
                            success = False
                            raise

                    async def monitor():
                        nonlocal success
                        logger.info("Starting monitor task")
                        success = await connection_monitor()
                        if not success:
                            logger.error("Connection monitor failed")
                            # Cancel the server loop if monitor fails
                            stop_event.set()
                        logger.info("Monitor task completed")

                    logger.info("Creating task group")
                    async with anyio.create_task_group() as tg:
                        # Start server first
                        tg.start_soon(run_server)
                        # Then start monitor
                        tg.start_soon(monitor)
                        # Wait for either success or failure
                        await connection_ready.wait()
                    logger.info("Task group completed")

                    logger.info("Connection setup completed with success=%s", success)
                    if not success:
                        raise TimeoutError("Server connection timed out")
                    return success

                success = await setup_connection()
                if success:
                    logger.info("Server %s connected successfully", server_name)
                    return server_name
                else:
                    raise ValueError("Failed to connect to server")

            except Exception as e:
                logger.exception("Failed to connect to MCP server")
                if server_name in self._servers:
                    del self._servers[server_name]
                raise ValueError(f"Failed to connect to MCP server: {str(e)}") from e

    def _get_session(self, server_name: str) -> tuple[ClientSession, AsyncExitStack]:
        """Get a session by name, with error handling."""
        if server_name not in self._sessions:
            raise ValueError(f"Unknown server: {server_name}")
        return self._sessions[server_name]

    async def cleanup(self, server_name: str | None = None) -> None:
        """Clean up server connections."""
        async with self._lock:
            if server_name:
                if server_name in self._servers:
                    # Signal server loop to stop
                    stop_event = self._servers[server_name]
                    stop_event.set()
                    del self._servers[server_name]
            else:
                # Stop all servers
                for stop_event in self._servers.values():
                    stop_event.set()
                self._servers.clear()

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        """List available tools from an MCP server."""

        async def _list_tools(session: ClientSession):
            response = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    # Parse arguments from inputSchema if it's a properties object
                    "arguments": [
                        Parameter(
                            name=prop_name,
                            description=prop.get("description", ""),
                            required=prop_name
                            in (tool.inputSchema.get("required", [])),
                            type=prop.get("type", "string"),
                        )
                        for prop_name, prop in (
                            tool.inputSchema.get("properties", {}) or {}
                        ).items()
                    ],
                }
                for tool in response.tools
            ]

        return await self._run_shielded(server_name, "list tools", _list_tools)

    async def list_resources(self, server_name: str) -> list[dict[str, Any]]:
        """List available resources from an MCP server."""

        async def _list_resources(session: ClientSession):
            response = await session.list_resources()
            return [
                {
                    "uri_template": resource.uri.unicode_string(),
                    "description": resource.description,
                }
                for resource in response.resources
            ]

        return await self._run_shielded(server_name, "list resources", _list_resources)

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """Call a tool on an MCP server."""
        result = await self._run_shielded(
            server_name,
            "call tool",
            lambda session: session.call_tool(tool_name, arguments),
        )
        return result.content

    async def _run_shielded(
        self, server_name: str, operation: str, func: Callable[[ClientSession], Any]
    ) -> Any:
        """Run an operation with task group shielding."""
        session, _ = self._get_session(server_name)
        async with self._lock:
            try:
                with anyio.CancelScope(shield=True):
                    return await func(session)
            except Exception as e:
                logger.exception(f"Failed to {operation}")
                raise ValueError(f"Failed to {operation}: {str(e)}") from e

    async def read_resource(
        self, server_name: str, resource_uri: AnyUrl | str
    ) -> tuple[str, str]:
        """Read a resource from an MCP server."""
        # Convert string to AnyUrl if needed
        uri = AnyUrl(resource_uri) if isinstance(resource_uri, str) else resource_uri
        return await self._run_shielded(
            server_name,
            "read resource",
            lambda session: session.read_resource(uri),
        )

    async def list_prompts(self, server_name: str) -> list[dict[str, Any]]:
        """List available prompts from an MCP server."""

        async def _list_prompts(session: ClientSession):
            response = await session.list_prompts()
            return [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": [
                        Parameter(
                            name=arg.name,
                            description=arg.description or "",
                            required=arg.required or False,
                            type="string",  # Default to string type
                        )
                        for arg in (prompt.arguments or [])
                    ],
                }
                for prompt in response.prompts
            ]

        return await self._run_shielded(server_name, "list prompts", _list_prompts)

    async def get_prompt(
        self, server_name: str, prompt_name: str, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get a prompt from an MCP server."""

        async def _get_prompt(session: ClientSession):
            result = await session.get_prompt(prompt_name, arguments)
            return [
                {
                    "role": msg.role,
                    "content": msg.content,  # Return the full content object
                }
                for msg in result.messages
            ]

        return await self._run_shielded(server_name, "get prompt", _get_prompt)


class MCPTool:
    """Tool for interacting with MCP servers."""

    def __init__(self):
        self._handler = MCPCommandHandler()

    def execute(
        self,
        code: str | None,
        args: list[str] | None,
        kwargs: dict[str, str] | None,
        confirm: ConfirmFunc,
    ) -> Generator[Message, None, None]:
        """Execute an MCP command."""
        if not code:
            yield Message("assistant", "No command provided")
            return

        # Create an async queue for results
        send_stream, receive_stream = anyio.create_memory_object_stream[Message](
            max_buffer_size=10
        )
        self._handler._send_stream = send_stream

        async def run_command():
            try:
                await self._handler.execute_command(code)
            finally:
                await send_stream.aclose()

        try:
            # Create a new event loop for async execution
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the command
            loop.run_until_complete(run_command())
            loop.close()

            # Yield messages from the stream
            while True:
                try:
                    msg = loop.run_until_complete(receive_stream.receive())
                    yield msg
                except anyio.EndOfStream:
                    break

        except Exception as e:
            logger.exception("Error in execution")
            yield Message("assistant", f"Error: {str(e)}")


# Create and expose the tool instance
# Create and expose the tool instance
tool = ToolSpec(
    name="mcp",
    desc="Model Context Protocol client for interacting with MCP servers",
    block_types=["mcp"],
    parameters=[
        Parameter(
            name="command",
            type="string",
            description="MCP command to execute",
            required=True,
        ),
    ],
    execute=MCPTool().execute,
)
