import logging
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Test")

logger = logging.getLogger("mcp")


# Add a simple tool
@mcp.tool()
def hello(name: str) -> str:
    """Say hello to someone"""
    return f"Hello, {name}!"


if __name__ == "__main__":
    logger.warning("Starting MCP server")
    mcp.run()
