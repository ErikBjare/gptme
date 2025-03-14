#!/usr/bin/env python3
"""
Simple test script for MCP tool discovery in GPTme.
This script tests our simplified approach based on Goose's implementation.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("simple-mcp-test")

# Make sure gptme module is in path
sys.path.append(str(Path(__file__).parent))

# Import GPTme MCP modules
from gptme.mcp.client import MCPClient
from gptme.mcp.session import MCPSessionManager
from gptme.mcp.tools import MCPToolRegistry

async def test_simple_mcp_discovery(config_path: str) -> None:
    """
    Test the simplified MCP tool discovery.
    
    Args:
        config_path: Path to the MCP config file
    """
    print(f"=== Simple MCP Tool Discovery Test ===")
    print(f"Config: {config_path}")
    
    # Create tool registry
    registry = MCPToolRegistry()
    
    print("\n=== Initializing MCP Session Manager ===")
    start_time = time.time()
    try:
        # Initialize session manager
        session_manager = MCPSessionManager(config_path=config_path)
        
        # Initialize MCP
        print("Initializing MCP client...")
        init_successful = await session_manager.initialize(timeout=30)
        init_time = time.time() - start_time
        
        if init_successful:
            print(f"✅ MCP initialized successfully in {init_time:.2f}s")
            
            # Test tool registration
            print(f"\n=== Testing Tool Registration ===")
            reg_start_time = time.time()
            
            print("Registering tools with simplified method...")
            tools = await session_manager.register_tools()
            reg_time = time.time() - reg_start_time
            
            if tools:
                print(f"✅ Successfully registered {len(tools)} tools in {reg_time:.2f}s")
                
                # Group tools by server
                tools_by_server = {}
                for tool in tools:
                    server = tool.get("function", {}).get("description", "").split("\n")[0]
                    if "from the" in server:
                        server = server.split("from the ")[1].split(" MCP")[0]
                    else:
                        server = "unknown"
                        
                    if server not in tools_by_server:
                        tools_by_server[server] = []
                    tools_by_server[server].append(tool)
                
                # Show tools by server
                print("\nTools by server:")
                for server, server_tools in tools_by_server.items():
                    print(f"  - {server}: {len(server_tools)} tools")
                    # Show first few tools from each server
                    for i, tool in enumerate(server_tools[:3], 1):
                        name = tool.get("function", {}).get("name", "unnamed")
                        print(f"    {i}. {name}")
                    if len(server_tools) > 3:
                        print(f"    ... and {len(server_tools) - 3} more")
            else:
                print(f"❌ No tools registered in {reg_time:.2f}s")
        else:
            print(f"❌ Failed to initialize MCP in {init_time:.2f}s")
    
    except Exception as e:
        print(f"❌ Error running MCP test: {e}")
        import traceback
        print(f"Detailed error:\n{traceback.format_exc()}")
    
    finally:
        # Clean up
        try:
            if 'session_manager' in locals():
                print("\n=== Cleaning Up ===")
                await session_manager.close()
                print("MCP connections closed")
        except Exception as e:
            print(f"Error closing MCP connections: {e}")
        
        print(f"\n=== Test Completed in {time.time() - start_time:.2f}s ===")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test simplified MCP tool discovery")
    parser.add_argument(
        "--config", 
        type=str, 
        default="./mcp-config.json",
        help="Path to MCP config file (default: ./mcp-config.json)"
    )
    
    args = parser.parse_args()
    
    # Run the test
    asyncio.run(test_simple_mcp_discovery(args.config))
