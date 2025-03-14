"""Configuration for Model Context Protocol in gptme."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class MCPConfig:
    """Configuration for MCP servers."""
    
    DEFAULT_CONFIG_PATHS = [
        "~/.config/gptme/mcp_servers.json",
        "~/.gptme/mcp_servers.json",
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize MCP configuration.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.servers = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load MCP server configuration from file."""
        # Try specified path first
        if self.config_path:
            expanded_path = os.path.expanduser(self.config_path)
            if os.path.exists(expanded_path):
                self._load_from_file(expanded_path)
                return
                
        # Try default paths
        for path_str in self.DEFAULT_CONFIG_PATHS:
            path = Path(os.path.expanduser(path_str))
            if path.exists():
                self._load_from_file(str(path))
                return
    
    def _load_from_file(self, file_path: str) -> None:
        """Load configuration from a specific file.
        
        Args:
            file_path: Path to the configuration file
        """
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
                
            if "mcpServers" in config_data:
                self.servers = config_data["mcpServers"]
            else:
                self.servers = config_data
        except Exception as e:
            print(f"Error loading MCP configuration from {file_path}: {e}")
            self.servers = {}
    
    def get_server_config(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            Server configuration or None if not found
        """
        return self.servers.get(server_id)
    
    def get_all_servers(self) -> Dict[str, Any]:
        """Get all server configurations.
        
        Returns:
            Dictionary of all server configurations
        """
        return self.servers 