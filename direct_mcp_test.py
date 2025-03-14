#!/usr/bin/env python3
"""
Direct, no-frills MCP tool discovery test.
Minimal code to test MCP server connections and tool discovery.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

class DirectMCPTest:
    """Direct, minimalist MCP testing class."""
    
    def __init__(self, config_path: str):
        """Initialize with config path."""
        self.config_path = config_path
        self.log = logging.getLogger("direct-mcp")
        self.processes = {}
        self.session_pipes = {}
        
    async def start_server(self, name: str, command: str, config: Dict):
        """Start a single MCP server process."""
        self.log.info(f"Starting server: {name}")
        
        try:
            # Convert config to JSON string
            config_str = json.dumps(config)
            
            # Create full command
            full_cmd = f"{command} --config '{config_str}'"
            self.log.info(f"Command: {full_cmd}")
            
            # Start the process
            process = await asyncio.create_subprocess_shell(
                full_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.processes[name] = process
            self.log.info(f"Started server {name} (PID: {process.pid})")
            
            # Store the pipes
            self.session_pipes[name] = {
                "stdin": process.stdin,
                "stdout": process.stdout
            }
            
            # Start reading stderr in background to catch errors
            asyncio.create_task(self._read_stderr(name, process.stderr))
            
            return True
        except Exception as e:
            self.log.error(f"Failed to start server {name}: {e}")
            return False
    
    async def _read_stderr(self, name: str, stderr):
        """Read stderr from a process to catch errors."""
        try:
            while True:
                line = await stderr.readline()
                if not line:
                    break
                    
                error_line = line.decode('utf-8', errors='replace').strip()
                if error_line:
                    self.log.warning(f"[{name} stderr] {error_line}")
        except Exception as e:
            self.log.error(f"Error reading stderr from {name}: {e}")
    
    async def initialize_server(self, name: str):
        """Send initialize message to server."""
        self.log.info(f"Initializing server: {name}")
        
        if name not in self.session_pipes:
            self.log.error(f"Server {name} not started")
            return False
        
        try:
            # Create initialize message
            init_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "direct-mcp-test",
                        "version": "0.1.0"
                    }
                }
            }
            
            # Send message
            message = json.dumps(init_msg) + "\n"
            stdin = self.session_pipes[name]["stdin"]
            await stdin.write(message.encode())
            
            # Read response
            stdout = self.session_pipes[name]["stdout"]
            response_line = await stdout.readline()
            
            if not response_line:
                self.log.error(f"No response from {name}")
                return False
                
            response = json.loads(response_line)
            self.log.info(f"Initialize response from {name}: {json.dumps(response)[:100]}...")
            
            if "result" in response:
                self.log.info(f"Successfully initialized {name}")
                return True
            else:
                self.log.error(f"Failed to initialize {name}: {response.get('error')}")
                return False
                
        except Exception as e:
            self.log.error(f"Error initializing {name}: {e}")
            return False
    
    async def list_tools(self, name: str):
        """List tools from a server."""
        self.log.info(f"Listing tools from server: {name}")
        
        if name not in self.session_pipes:
            self.log.error(f"Server {name} not started")
            return []
        
        try:
            # Create tools/list message
            list_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            # Send message
            message = json.dumps(list_msg) + "\n"
            stdin = self.session_pipes[name]["stdin"]
            await stdin.write(message.encode())
            
            # Read response with timeout
            stdout = self.session_pipes[name]["stdout"]
            try:
                response_line = await asyncio.wait_for(stdout.readline(), timeout=5.0)
            except asyncio.TimeoutError:
                self.log.error(f"Timeout waiting for tools/list response from {name}")
                return []
                
            if not response_line:
                self.log.error(f"No response from {name}")
                return []
                
            response = json.loads(response_line)
            
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                self.log.info(f"Got {len(tools)} tools from {name}")
                return tools
            else:
                self.log.error(f"Failed to get tools from {name}: {response.get('error')}")
                return []
                
        except Exception as e:
            self.log.error(f"Error listing tools from {name}: {e}")
            return []
    
    async def cleanup(self):
        """Clean up processes."""
        self.log.info("Cleaning up...")
        
        for name, process in self.processes.items():
            self.log.info(f"Terminating {name}")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.log.warning(f"Killing {name} forcefully")
                process.kill()
            except Exception as e:
                self.log.error(f"Error terminating {name}: {e}")
    
    async def run_test(self):
        """Run the full test."""
        self.log.info("Starting direct MCP test")
        
        try:
            # Load config
            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            # Extract servers from config
            servers = []
            if "mcpServers" in config:
                for name, server_cfg in config["mcpServers"].items():
                    servers.append({
                        "name": name,
                        "command": server_cfg.get("command", ""),
                        "config": server_cfg.get("config", {})
                    })
            elif "servers" in config:
                for server in config["servers"]:
                    servers.append({
                        "name": server.get("name", f"server_{len(servers)}"),
                        "command": server.get("command", ""),
                        "config": server.get("config", {})
                    })
            
            self.log.info(f"Found {len(servers)} servers in config")
            
            # Start and initialize each server
            successful_servers = []
            for server in servers:
                name = server["name"]
                command = server["command"]
                config = server["config"]
                
                self.log.info(f"Processing server: {name}")
                
                # Start the server
                if await self.start_server(name, command, config):
                    # Give it a moment to start up
                    await asyncio.sleep(1.0)
                    
                    # Initialize the server
                    if await self.initialize_server(name):
                        successful_servers.append(name)
            
            self.log.info(f"Successfully initialized {len(successful_servers)} servers")
            
            # List tools from each server
            all_tools = {}
            for name in successful_servers:
                tools = await self.list_tools(name)
                all_tools[name] = tools
            
            # Print summary
            self.log.info("\n===== TOOL DISCOVERY SUMMARY =====")
            total_tools = sum(len(tools) for tools in all_tools.values())
            self.log.info(f"Total tools discovered: {total_tools}")
            
            for name, tools in all_tools.items():
                self.log.info(f"Server {name}: {len(tools)} tools")
                
                # Print a few example tools
                for i, tool in enumerate(tools[:3]):
                    tool_name = tool.get("name", "unnamed")
                    self.log.info(f"  {i+1}. {tool_name}")
                
                if len(tools) > 3:
                    self.log.info(f"  ... and {len(tools) - 3} more")
            
        except Exception as e:
            self.log.error(f"Error in test: {e}")
            import traceback
            self.log.error(traceback.format_exc())
        finally:
            # Clean up
            await self.cleanup()

async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config_path>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Run the test
    tester = DirectMCPTest(config_path)
    await tester.run_test()

if __name__ == "__main__":
    asyncio.run(main())
