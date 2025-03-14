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

async def test_mcp(config_path: str) -> None:
    """
    Test MCP functionality by initializing the MCPSessionManager
    and listing available tools.
    
    Args:
        config_path: Path to the MCP config file
    """
    print(f"Testing MCP with config: {config_path}")
    
    # Create the MCP session manager
    mcp_manager = MCPSessionManager(config_path=config_path)
    
    try:
        # Initialize the MCP client
        print("Initializing MCP...")
        init_successful = await mcp_manager.initialize(timeout=30)
        
        if init_successful:
            print("✅ MCP initialized successfully")
            
            # Try to get tools
            print("Fetching MCP tools...")
            tools = await mcp_manager.get_tools()
            
            if tools:
                print(f"✅ Found {len(tools)} tools from MCP servers")
                
                # Display tool names
                for tool in tools:
                    print(f"  - {tool.get('name', 'Unnamed tool')}: {tool.get('description', 'No description')}")
            else:
                print("❌ No tools found. MCP servers might still be starting up.")
            
            # Since we're running as a test, wait for a moment to see if more tools become available
            print("Waiting for 5 seconds to see if more tools become available...")
            await asyncio.sleep(5)
            
            # Try again
            tools = await mcp_manager.get_tools()
            if tools:
                print(f"✅ Now found {len(tools)} tools from MCP servers")
            else:
                print("❌ Still no tools found")
                
        else:
            print("❌ Failed to initialize MCP")
    except Exception as e:
        print(f"❌ Error testing MCP: {e}")
    finally:
        # Clean up
        print("Closing MCP connections...")
        await mcp_manager.close()
        print("MCP test complete")

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
    
    args = parser.parse_args()
    
    # Run the async test
    asyncio.run(test_mcp(args.config))

if __name__ == "__main__":
    main()
