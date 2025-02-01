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


class MCPTool:
    """Tool for interacting with MCP servers."""

    def __init__(self):
        self._servers: dict[str, anyio.Event] = {}  # server_name -> stop_event
        self._sessions: dict[str, tuple[ClientSession, AsyncExitStack]] = {}
        self._lock = anyio.Lock()

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
                    "arguments": [
                        Parameter(
                            name=arg.name,
                            description=arg.description or "",
                            required=arg.required or False,
                            type="string",  # Default to string type
                        )
                        for arg in (tool.arguments or [])
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
                    "uri_template": resource.uriTemplate,
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
        self, server_name: str, resource_uri: str
    ) -> tuple[str, str]:
        """Read a resource from an MCP server."""
        return await self._run_shielded(
            server_name,
            "read resource",
            lambda session: session.read_resource(resource_uri),
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
                {"role": msg.role, "content": msg.content.text}
                for msg in result.messages
            ]

        return await self._run_shielded(server_name, "get prompt", _get_prompt)

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
        result_queue = anyio.create_memory_object_stream[Message](max_buffer_size=10)
        send_stream, receive_stream = result_queue

        async def async_execute(command: str) -> None:
            logger.info("Executing command: %s", command)
            try:
                cmd = command.split(maxsplit=3)  # Split into max 4 parts
                if not cmd:
                    await send_stream.send(
                        Message("assistant", "Please specify an MCP command")
                    )
                    return

                logger.info("Processing command: %s", cmd[0])
                match cmd[0]:
                    case "disconnect":
                        if len(cmd) < 2:
                            result_queue.put(
                                Message("assistant", "Please specify server name")
                            )
                            return
                        server_name = cmd[1]
                        await self.cleanup(server_name)
                        result_queue.put(
                            Message(
                                "assistant",
                                f"Disconnected from MCP server: {server_name}",
                            )
                        )

                    case "connect":
                        if len(cmd) < 2:
                            result_queue.put(
                                Message("assistant", "Please specify server path")
                            )
                            return
                        try:
                            name = cmd[2] if len(cmd) > 2 else None
                            server_name = await self.connect_server(cmd[1], name)
                            result_queue.put(
                                Message(
                                    "assistant",
                                    f"Connected to MCP server: {server_name}",
                                )
                            )
                        except Exception as e:
                            result_queue.put(
                                Message(
                                    "assistant",
                                    f"Failed to connect to server: {str(e)}",
                                )
                            )

                    case "tools" | "resources" | "prompts" as list_cmd:
                        if len(cmd) < 2:
                            result_queue.put(
                                Message(
                                    "assistant",
                                    f"Please specify server name for {list_cmd}",
                                )
                            )
                            return

                        items = await getattr(self, f"list_{list_cmd}")(cmd[1])
                        if not items:
                            result_queue.put(
                                Message("assistant", f"No {list_cmd} available")
                            )
                            return

                        # Format output based on type
                        if list_cmd == "tools":
                            items_str = "Available tools:\n" + "\n".join(
                                f"- {t['name']}: {t['description']}\n  Arguments: {t['arguments']}"
                                for t in items
                            )
                        elif list_cmd == "resources":
                            items_str = "Available resources:\n" + "\n".join(
                                f"- {r['uri_template']}: {r['description']}"
                                for r in items
                            )
                        else:  # prompts
                            items_str = "Available prompts:\n" + "\n".join(
                                f"- {p['name']}: {p['description']}\n  Arguments: {p['arguments']}"
                                for p in items
                            )

                        result_queue.put(Message("assistant", items_str))

                    case "call":
                        if len(cmd) < 4:
                            result_queue.put(
                                Message(
                                    "assistant",
                                    "Usage: call <server> <tool> <args>",
                                )
                            )
                            return
                        server_name, tool_name = cmd[1:3]
                        args = parse_args(cmd[3])
                        result = await self.call_tool(server_name, tool_name, args)
                        result_queue.put(Message("assistant", f"Tool result: {result}"))

                    case "read":
                        if len(cmd) < 3:
                            result_queue.put(
                                Message(
                                    "assistant",
                                    "Usage: read <server> <resource_uri>",
                                )
                            )
                            return
                        content, mime_type = await self.read_resource(cmd[1], cmd[2])
                        result_queue.put(
                            Message(
                                "assistant",
                                f"Resource content ({mime_type}):\n{content}",
                            )
                        )

                    case "prompt":
                        if len(cmd) < 4:
                            result_queue.put(
                                Message(
                                    "assistant",
                                    "Usage: prompt <server> <name> <args>",
                                )
                            )
                            return
                        server_name, prompt_name = cmd[1:3]
                        args = parse_args(cmd[3])
                        messages = await self.get_prompt(server_name, prompt_name, args)
                        result_queue.put(
                            Message(
                                "assistant",
                                "Prompt messages:\n"
                                + "\n".join(
                                    f"{m['role']}: {m['content']}" for m in messages
                                ),
                            )
                        )

                    case _:
                        result_queue.put(
                            Message("assistant", f"Unknown MCP command: {cmd[0]}")
                        )

            except Exception as e:
                logger.exception("Error executing MCP command")
                result_queue.put(
                    Message("assistant", f"Error executing MCP command: {str(e)}")
                )

        async def run_with_session():
            try:
                await async_execute(code)
            except Exception as e:
                logger.exception("Error in async execution")
                result_queue.put(Message("assistant", f"Error: {str(e)}"))

        try:
            logger.info("Starting async execution...")
            # Create a new event loop for async execution
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the async code and wait for it to complete
            loop.run_until_complete(run_with_session())
            loop.close()

            logger.info("Async execution completed")

            # Yield all messages from the queue
            logger.info("Processing result queue...")
            while not result_queue.empty():
                msg = result_queue.get_nowait()
                logger.info("Yielding message: %s", msg)
                yield msg
            logger.info("Queue processing complete")

            # Only cleanup on explicit disconnect
            if code and code.startswith("disconnect "):
                cmd = code.split(maxsplit=2)
                if len(cmd) >= 2:
                    server_name = cmd[1]
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.cleanup(server_name))
                        loop.close()
                    except Exception as e:
                        logger.warning("Error during cleanup: %s", e)
        except Exception as e:
            logger.exception("Error in execution")
            yield Message("assistant", f"Error: {str(e)}")


# Create and expose the tool instance
tool = ToolSpec(
    name="mcp",
    desc="Model Context Protocol client for interacting with MCP servers",
    block_types=["mcp"],
    parameters=[
        Parameter(
            "command",
            type="string",
            description="MCP command to execute",
            required=True,
        ),
    ],
    execute=MCPTool().execute,
)
