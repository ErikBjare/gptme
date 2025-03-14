#!/usr/bin/env python3
"""
Diagnostic utility for MCP functionality in GPTme.
This script provides detailed information about MCP server communication and tool registration.
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
logger = logging.getLogger("mcp-diagnostics")

# Make sure gptme module is in path
sys.path.append(str(Path(__file__).parent))

# Import GPTme MCP modules
from gptme.mcp.session import MCPSessionManager
from gptme.mcp.client import MCPClient

async def test_individual_server(client: MCPClient, server_name: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Test a specific MCP server's tool discovery functionality.
    
    Args:
        client: Initialized MCPClient instance
        server_name: Name of the server to test
        timeout: Timeout in seconds for tool discovery
        
    Returns:
        Dictionary with diagnostic information about the server
    """
    results = {
        "server_name": server_name,
        "status": "unknown",
        "connection_status": "unknown",
        "tools_discovered": 0,
        "errors": [],
        "elapsed_time": 0,
        "tools": []
    }
    
    # Check if the server is connected
    if server_name not in client.sessions:
        results["status"] = "failed"
        results["connection_status"] = "not_connected"
        results["errors"].append(f"Server {server_name} is not connected")
        return results
    
    # Get the session for this server
    session = client.sessions[server_name]
    results["connection_status"] = "connected"
    
    # Try to discover tools from this specific server
    start_time = time.time()
    try:
        # Check if the session has list_tools method
        if hasattr(session, "list_tools") and callable(session.list_tools):
            logger.info(f"Testing tool discovery for server {server_name}")
            
            # Try to discover tools with timeout
            tools = await asyncio.wait_for(session.list_tools(), timeout=timeout)
            
            elapsed = time.time() - start_time
            results["elapsed_time"] = elapsed
            
            if tools:
                results["status"] = "success"
                results["tools_discovered"] = len(tools)
                results["tools"] = tools
                logger.info(f"Server {server_name} returned {len(tools)} tools in {elapsed:.2f}s")
            else:
                results["status"] = "no_tools"
                logger.warning(f"Server {server_name} returned no tools in {elapsed:.2f}s")
        else:
            results["status"] = "unsupported"
            results["errors"].append(f"Server {server_name} does not support tool discovery")
            logger.error(f"Server {server_name} does not support tool discovery")
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        results["status"] = "timeout"
        results["elapsed_time"] = elapsed
        results["errors"].append(f"Timeout after {elapsed:.2f}s waiting for tool discovery")
        logger.error(f"Timeout getting tools from server {server_name} after {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start_time
        results["status"] = "error"
        results["elapsed_time"] = elapsed
        results["errors"].append(f"Error: {str(e)}")
        logger.error(f"Error getting tools from server {server_name}: {e}")
    
    return results

async def format_tool_for_display(tool: Dict[str, Any]) -> str:
    """Format a tool for display in the diagnostic output."""
    try:
        name = tool.get("name", "unnamed")
        desc = tool.get("description", "No description")
        schema = tool.get("inputSchema", {})
        
        # Limit description length
        if len(desc) > 100:
            desc = desc[:97] + "..."
        
        # Format schema
        schema_str = json.dumps(schema, indent=2) if schema else "No schema"
        
        return f"- Name: {name}\n  Description: {desc}\n  Schema: {schema_str if len(schema_str) < 200 else schema_str[:197] + '...'}"
    except Exception as e:
        return f"- Error formatting tool: {e}"

async def diagnostic_mcp(config_path: str, timeout: int = 60, per_server_timeout: int = 30) -> None:
    """
    Run comprehensive MCP diagnostics.
    
    Args:
        config_path: Path to the MCP config file
        timeout: Overall timeout for initialization in seconds
        per_server_timeout: Timeout for each individual server test
    """
    print(f"=== MCP Diagnostic Utility ===")
    print(f"Config: {config_path}")
    print(f"Timeout: {timeout} seconds")
    print(f"Per-server timeout: {per_server_timeout} seconds\n")
    
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
            
            # Get the client reference
            client = mcp_manager.client
            
            # Report on connected servers
            connected_servers = list(client.sessions.keys()) if client and hasattr(client, "sessions") else []
            print(f"\n=== Connected Servers ({len(connected_servers)}) ===")
            for i, server_name in enumerate(connected_servers, 1):
                print(f"{i}. {server_name}")
            
            if connected_servers:
                # Test individual servers
                print(f"\n=== Testing Individual Servers ===")
                all_server_results = {}
                
                for server_name in connected_servers:
                    print(f"\nTesting server: {server_name}")
                    server_results = await test_individual_server(
                        client=client, 
                        server_name=server_name,
                        timeout=per_server_timeout
                    )
                    all_server_results[server_name] = server_results
                    
                    # Display basic results
                    status_emoji = "✅" if server_results["status"] == "success" else "❌"
                    print(f"{status_emoji} Status: {server_results['status']}")
                    print(f"  Tools discovered: {server_results['tools_discovered']}")
                    print(f"  Time taken: {server_results['elapsed_time']:.2f}s")
                    
                    if server_results["errors"]:
                        print(f"  Errors:")
                        for error in server_results["errors"]:
                            print(f"    - {error}")
                    
                    # Show tools if any were discovered
                    if server_results["tools"]:
                        print(f"  Tools:")
                        for i, tool in enumerate(server_results["tools"][:5], 1):  # Limit to first 5
                            tool_str = await format_tool_for_display(tool)
                            print(f"  {i}. {tool_str}")
                        
                        if len(server_results["tools"]) > 5:
                            print(f"  ... and {len(server_results['tools']) - 5} more tools")
                
                # Test overall tool registration
                print(f"\n=== Testing Overall Tool Registration ===")
                start_time = time.time()
                try:
                    print("Attempting to register all tools...")
                    tools = await mcp_manager.register_tools()
                    reg_time = time.time() - start_time
                    
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
                        for server, server_tools in tools_by_server.items():
                            print(f"  - {server}: {len(server_tools)} tools")
                    else:
                        print(f"❌ No tools registered in {reg_time:.2f}s")
                except Exception as e:
                    reg_time = time.time() - start_time
                    print(f"❌ Error registering tools in {reg_time:.2f}s: {e}")
            else:
                print("❌ No servers connected")
        else:
            print(f"❌ Failed to initialize MCP in {init_time:.2f}s")
    except Exception as e:
        print(f"❌ Error running MCP diagnostics: {e}")
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
        
        print("\n=== Diagnostics Complete ===")

def main():
    """
    Parse arguments and run the MCP diagnostics.
    """
    parser = argparse.ArgumentParser(description="Diagnostic utility for MCP in GPTme")
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
    parser.add_argument(
        "--server-timeout",
        type=int,
        default=30,
        help="Maximum time to wait for each server test in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    # Run the async diagnostics
    asyncio.run(diagnostic_mcp(args.config, args.timeout, args.server_timeout))

if __name__ == "__main__":
    main()
