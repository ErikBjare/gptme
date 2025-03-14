#!/usr/bin/env python3
"""
Test script for MCP tool registration in GPTme.
This script specifically tests the new fallback mechanisms for tool discovery.
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("mcp-tools-test")

# Make sure gptme module is in path
sys.path.append(str(Path(__file__).parent))

# Import GPTme MCP modules
from gptme.mcp.session import MCPSessionManager

async def test_mcp_tool_registration(config_path: str, timeout: int = 60) -> None:
    """
    Test MCP tool registration with fallback mechanisms.
    
    Args:
        config_path: Path to the MCP config file
        timeout: Overall timeout in seconds
    """
    print(f"=== MCP Tool Registration Test ===")
    print(f"Config: {config_path}")
    print(f"Timeout: {timeout} seconds\n")
    
    # Create the MCP session manager
    print("Creating MCPSessionManager...")
    mcp_manager = MCPSessionManager(config_path=config_path)
    
    try:
        # Initialize the MCP client
        print("\n=== Initializing MCP ===")
        start_time = time.time()
        init_successful = await mcp_manager.initialize(timeout=timeout)
        init_time = time.time() - start_time
        
        if init_successful:
            print(f"✅ MCP initialized successfully in {init_time:.2f}s")
            
            # Get detailed server status
            if hasattr(mcp_manager.client, "get_server_status"):
                print("\n=== Server Status ===")
                try:
                    status = await mcp_manager.client.get_server_status()
                    for server_name, server_status in status.items():
                        print(f"\nServer: {server_name}")
                        print(f"  Connected: {server_status.get('connected', False)}")
                        print(f"  Has list_tools: {server_status.get('has_list_tools', False)}")
                        
                        # Show background task status if available
                        bg_task = server_status.get('background_task')
                        if bg_task:
                            print(f"  Background Task:")
                            print(f"    Done: {bg_task.get('done', False)}")
                            print(f"    Cancelled: {bg_task.get('cancelled', False)}")
                            if bg_task.get('exception'):
                                print(f"    Exception: {bg_task.get('exception')}")
                except Exception as e:
                    print(f"❌ Error getting server status: {e}")
            
            # Test tool registration
            print(f"\n=== Testing Tool Registration ===")
            start_time = time.time()
            try:
                print("Registering tools with fallback mechanism...")
                tools = await mcp_manager.register_tools()
                reg_time = time.time() - start_time
                
                if tools:
                    print(f"✅ Successfully registered {len(tools)} tools in {reg_time:.2f}s")
                    
                    # Show some example tools
                    print("\nExample registered tools:")
                    for i, tool in enumerate(tools[:5], 1):  # Show first 5 tools
                        tool_name = tool.get("function", {}).get("name", "unnamed")
                        tool_desc = tool.get("function", {}).get("description", "No description")
                        # Truncate description
                        if len(tool_desc) > 100:
                            tool_desc = tool_desc[:97] + "..."
                        print(f"{i}. {tool_name}: {tool_desc}")
                    
                    if len(tools) > 5:
                        print(f"... and {len(tools) - 5} more tools")
                else:
                    print(f"❌ No tools registered in {reg_time:.2f}s")
            except Exception as e:
                reg_time = time.time() - start_time
                print(f"❌ Error registering tools in {reg_time:.2f}s: {e}")
                import traceback
                print(f"Detailed error:\n{traceback.format_exc()}")
        else:
            print(f"❌ Failed to initialize MCP in {init_time:.2f}s")
    except Exception as e:
        print(f"❌ Error running MCP tool test: {e}")
        import traceback
        print(f"Detailed error:\n{traceback.format_exc()}")
    finally:
        # Clean up
        print("\n=== Cleaning Up ===")
        try:
            await mcp_manager.close()
            print("MCP connections closed")
        except Exception as e:
            print(f"Error closing MCP connections: {e}")
        
        print("\n=== Test Complete ===")

def main():
    """
    Parse arguments and run the MCP tool registration test.
    """
    parser = argparse.ArgumentParser(description="Test MCP tool registration in GPTme")
    parser.add_argument(
        "--config", 
        type=str, 
        required=True,
        help="Path to MCP config file"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Maximum time to wait for initialization in seconds (default: 60)"
    )
    
    args = parser.parse_args()
    
    # Run the test
    asyncio.run(test_mcp_tool_registration(args.config, args.timeout))

if __name__ == "__main__":
    main()
