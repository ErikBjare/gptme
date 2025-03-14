#!/usr/bin/env python3
"""
Test script for MCP functionality in GPTme.
This script verifies that MCP servers can be started and accessed properly.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("mcp-test")

# Make sure gptme module is in path
sys.path.append(str(Path(__file__).parent))

# Import GPTme MCP modules
from gptme.mcp.session import MCPSessionManager

async def test_mcp(config_path: str, timeout: int = 60) -> None:
    """
    Test MCP functionality by initializing the MCPSessionManager
    and listing available tools.
    
    Args:
        config_path: Path to the MCP config file
        timeout: Maximum time to wait for initialization in seconds
    """
    print(f"Testing MCP with config: {config_path}")
    print(f"Timeout: {timeout} seconds")
    
    # Create the MCP session manager
    mcp_manager = MCPSessionManager(config_path=config_path)
    
    try:
        # Initialize the MCP client
        print("Initializing MCP...")
        init_successful = await mcp_manager.initialize(timeout=timeout)
        
        if init_successful:
            print("✅ MCP initialized successfully")
            
            # Try to get tools with improved retry logic
            print("Fetching MCP tools (with retries)...")
            tools = await mcp_manager.register_tools()
            
            if tools:
                print(f"✅ Successfully registered {len(tools)} tools from MCP servers")
                
                # Display tool details
                for i, tool in enumerate(tools, 1):
                    print(f"  {i}. {tool.get('function', {}).get('name', 'Unnamed tool')}")
                    print(f"     Description: {tool.get('function', {}).get('description', 'No description')[:100]}...")
            else:
                print("❌ No tools registered. Waiting longer to see if tools become available...")
                
                # Wait a bit longer and try direct tool listing as a fallback
                print("Attempting direct tool discovery...")
                await asyncio.sleep(5)
                
                raw_tools = await mcp_manager.get_tools()
                if raw_tools:
                    print(f"✅ Found {len(raw_tools)} raw tools through direct discovery")
                    for i, tool in enumerate(raw_tools, 1):
                        name = tool.get("name", "unknown")
                        server = tool.get("server_name", "unknown")
                        print(f"  {i}. {name} (from {server})")
                else:
                    print("❌ Still no tools found through direct discovery")
                    
                    # Check servers status
                    if hasattr(mcp_manager.client, "sessions") and mcp_manager.client.sessions:
                        print(f"Connected to {len(mcp_manager.client.sessions)} servers:")
                        for server_name in mcp_manager.client.sessions:
                            print(f"  - {server_name}")
                    else:
                        print("❌ No active server sessions found")
        else:
            print("❌ Failed to initialize MCP")
    except Exception as e:
        print(f"❌ Error testing MCP: {e}")
        import traceback
        print(f"Detailed error: {traceback.format_exc()}")
    finally:
        # Clean up
        print("Closing MCP connections...")
        try:
            await mcp_manager.close()
            print("MCP shutdown complete")
        except Exception as e:
            print(f"Error during MCP shutdown: {e}")

def main():
    """
    Parse arguments and run the MCP test.
    """
    parser = argparse.ArgumentParser(description="Test MCP functionality in GPTme")
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
    
    # Run the async test with proper event loop cleanup
    try:
        asyncio.run(test_mcp(args.config, args.timeout))
    except KeyboardInterrupt:
        print("\nTest interrupted by user. Cleaning up...")
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()
