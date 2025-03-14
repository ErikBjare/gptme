#!/usr/bin/env python3
"""
Test script for our refactored MCP client that properly uses the official SDK.
This script focuses solely on testing the tool discovery functionality.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("mcp-sdk-test")

# Add the parent directory to sys.path to ensure we can import gptme
sys.path.insert(0, str(Path(__file__).parent))

# Import our refactored MCP client directly
from gptme.mcp.client import MCPClient

async def test_mcp_sdk_integration(config_path: str, timeout: float = 30.0) -> None:
    """
    Test the refactored MCP client with proper SDK integration.
    
    Args:
        config_path: Path to the MCP config file
        timeout: Maximum time to wait for operations in seconds
    """
    print(f"\n=== MCP SDK Integration Test ===")
    print(f"Config: {config_path}")
    print(f"Timeout: {timeout}s")
    
    start_time = time.time()
    
    try:
        # Create the MCP client
        print("\n[1] Creating MCP client...")
        client = MCPClient(config_path=config_path)
        
        # Initialize the client
        print("\n[2] Initializing client...")
        init_start = time.time()
        initialized = await client.initialize()
        init_time = time.time() - init_start
        
        if initialized:
            print(f"✅ Client initialized successfully in {init_time:.2f}s")
            
            # Test tool discovery
            print("\n[3] Testing tool discovery...")
            tools_start = time.time()
            tools = await client.list_tools(timeout=timeout)
            tools_time = time.time() - tools_start
            
            if tools:
                print(f"✅ Successfully discovered {len(tools)} tools in {tools_time:.2f}s")
                
                # Group tools by server
                tools_by_server = {}
                for tool in tools:
                    server_name = tool.get("server_name", "unknown")
                    if server_name not in tools_by_server:
                        tools_by_server[server_name] = []
                    tools_by_server[server_name].append(tool)
                
                # Show tools by server
                print("\nTools by server:")
                for server_name, server_tools in tools_by_server.items():
                    print(f"  - {server_name}: {len(server_tools)} tools")
                    # Show first few tools from each server
                    for i, tool in enumerate(server_tools[:3], 1):
                        name = tool.get("function", {}).get("name", "unnamed")
                        print(f"    {i}. {name}")
                    if len(server_tools) > 3:
                        print(f"    ... and {len(server_tools) - 3} more")
            else:
                print(f"❌ No tools discovered in {tools_time:.2f}s")
        else:
            print(f"❌ Client initialization failed in {init_time:.2f}s")
        
        # Get server status
        print("\n[4] Getting server status...")
        status = await client.get_server_status()
        print(f"Server status: {len(status)} servers")
        for server_name, server_status in status.items():
            # Handle case where server_status might be a string
            if isinstance(server_status, dict):
                connected = server_status.get("connected", False)
                status_info = server_status.get("status", "unknown")
                has_list_tools = server_status.get("has_list_tools", False)
                print(f"  - {server_name}: Connected={connected}, Status={status_info}, Has list_tools={has_list_tools}")
            else:
                # If server_status is a string, just print it
                print(f"  - {server_name}: {server_status}")

    
    except Exception as e:
        print(f"❌ Error during MCP test: {e}")
        import traceback
        print(f"Detailed error:\n{traceback.format_exc()}")
    
    finally:
        # Clean up resources
        if 'client' in locals():
            print("\n[5] Cleaning up...")
            close_start = time.time()
            await client.close()
            close_time = time.time() - close_start
            print(f"✅ Client closed in {close_time:.2f}s")
        
        total_time = time.time() - start_time
        print(f"\n=== Test completed in {total_time:.2f}s ===")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP SDK integration")
    parser.add_argument(
        "--config", 
        type=str, 
        default="./mcp-config.json",
        help="Path to MCP config file (default: ./mcp-config.json)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Maximum time to wait for operations in seconds (default: 30.0)"
    )
    
    args = parser.parse_args()
    
    # Run the test
    asyncio.run(test_mcp_sdk_integration(args.config, args.timeout))
