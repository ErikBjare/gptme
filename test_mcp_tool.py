import logging
from collections.abc import Generator

import gptme.tools as tools
from gptme.message import Message
from gptme.tools.base import ToolSpec

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Make sure tools are initialized
tools.clear_tools()
tools.init_tools()

# Get and verify MCP tool
mcp_tool: ToolSpec | None = tools.get_tool("mcp")
print("Available tools:", [t.name for t in tools.get_tools()])

if not mcp_tool:
    print("ERROR: MCP tool not loaded")
    exit(1)

print("Tool loaded:", mcp_tool.name)


def confirm_callback(msg: str) -> bool:
    """Callback for confirming actions."""
    return True


def run_command(cmd: str) -> bool:
    print(f"\nTesting: {cmd}")
    success = True
    got_response = False
    try:
        # We know mcp_tool is not None here
        assert mcp_tool
        assert mcp_tool.execute
        # Explicitly type the generator
        messages: Generator[Message, None, None] | Message = mcp_tool.execute(
            cmd, None, None, confirm_callback
        )
        assert isinstance(messages, Generator)
        # Iterate through the generator
        for msg in messages:
            got_response = True
            print(f"Response: {msg.content}")
            if "Error" in msg.content or "Failed" in msg.content:
                logger.error(f"Command failed: {msg.content}")
                success = False
        if not got_response:
            logger.error("No response received from command")
            success = False
        return success
    except Exception as e:
        logger.error(f"Command failed with exception: {e}")
        return False


success = True
try:
    # Test server connection and operations
    logger.info("Connecting to server...")
    if not run_command("connect test_mcp_server.py"):
        raise Exception("Failed to connect to server")

    logger.info("Listing tools...")
    if not run_command("tools mcp_server_0"):
        raise Exception("Failed to list tools")

    logger.info("Testing hello tool...")
    if not run_command('call mcp_server_0 hello {"name": "World"}'):
        raise Exception("Failed to call hello tool")

except Exception as e:
    logger.error(f"Test failed: {e}")
    success = False
finally:
    # Cleanup
    logger.info("Cleaning up...")
    run_command("disconnect mcp_server_0")

if success:
    print("\nAll tests passed!")
else:
    print("\nTests failed!")
    exit(1)
