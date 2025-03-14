"""Integration of MCP resources with gptme."""
import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

class MCPResourceManager:
    """Manager for MCP resources in gptme."""
    
    def __init__(self, mcp_client):
        """Initialize MCP resource manager.
        
        Args:
            mcp_client: MCP client instance
        """
        self.mcp_client = mcp_client
        
    async def list_resources(self, server_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available resources from MCP servers.
        
        Args:
            server_id: Optional server identifier to filter resources
            
        Returns:
            List of available resources
        """
        resources = []
        
        if server_id:
            if server_id not in self.mcp_client.sessions:
                return []
                
            session = self.mcp_client.sessions[server_id]["session"]
            try:
                result = await session.list_resources()
                resources = [{
                    "server_id": server_id,
                    "uri": res.uri,
                    "name": res.name,
                    "description": res.description,
                    "mime_type": res.mimeType
                } for res in result.resources]
            except Exception as e:
                logger.error(f"Failed to list resources from server {server_id}: {e}")
        else:
            # List resources from all servers
            for sid in self.mcp_client.sessions:
                server_resources = await self.list_resources(sid)
                resources.extend(server_resources)
                
        return resources
    
    async def read_resource(self, server_id: str, uri: str) -> Tuple[bool, str, Optional[Union[str, bytes]]]:
        """Read a resource from an MCP server.
        
        Args:
            server_id: Server identifier
            uri: Resource URI
            
        Returns:
            Tuple of (success, content_type, content) where content is either text or binary
        """
        if server_id not in self.mcp_client.sessions:
            return False, "error", f"Server {server_id} not connected"
            
        session = self.mcp_client.sessions[server_id]["session"]
        
        try:
            result = await session.read_resource(uri)
            
            for content in result.contents:
                if "text" in content:
                    return True, "text", content.text
                elif "blob" in content:
                    # Decode base64 binary data
                    binary_data = base64.b64decode(content.blob)
                    return True, "binary", binary_data
                    
            return False, "error", "No content found in resource"
            
        except Exception as e:
            error_msg = f"Failed to read resource {uri} from server {server_id}: {e}"
            logger.error(error_msg)
            return False, "error", error_msg
    
    async def save_resource(self, server_id: str, uri: str, path: Union[str, Path]) -> bool:
        """Save a resource to the local filesystem.
        
        Args:
            server_id: Server identifier
            uri: Resource URI
            path: Local filesystem path to save to
            
        Returns:
            True if successful, False otherwise
        """
        success, content_type, content = await self.read_resource(server_id, uri)
        
        if not success:
            logger.error(f"Failed to read resource: {content}")
            return False
            
        path = Path(path)
        
        try:
            if content_type == "text":
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
            elif content_type == "binary":
                with open(path, 'wb') as f:
                    f.write(content)
            else:
                logger.error(f"Unknown content type: {content_type}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Failed to save resource to {path}: {e}")
            return False 