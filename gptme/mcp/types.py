"""
Core types for Model Context Protocol (MCP) implementation.

Based on: https://modelcontextprotocol.io/
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class ErrorCode(Enum):
    """Standard MCP error codes"""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class McpError(Exception):
    """MCP protocol error"""

    code: ErrorCode
    message: str
    data: Any | None = None


@dataclass
class Resource:
    """MCP resource definition"""

    uri: str
    name: str
    description: str | None = None
    mimeType: str | None = None


@dataclass
class ResourceTemplate:
    """Template for dynamic resources"""

    uriTemplate: str
    name: str
    description: str | None = None
    mimeType: str | None = None


@dataclass
class Tool:
    """MCP tool definition"""

    name: str
    description: str
    inputSchema: dict[str, Any]  # JSON Schema


@dataclass
class PromptArgument:
    """Argument definition for prompt templates"""

    name: str
    description: str | None = None
    required: bool = False


@dataclass
class Prompt:
    """MCP prompt template"""

    name: str
    description: str | None = None
    arguments: list[PromptArgument] | None = None


@dataclass
class TextContent:
    """Text content in messages"""

    text: str
    type: Literal["text"] = "text"


@dataclass
class ImageContent:
    """Image content in messages"""

    data: str  # base64 encoded
    mimeType: str
    type: Literal["image"] = "image"


@dataclass
class EmbeddedResource:
    """Resource content embedded in messages"""

    resource: Resource
    type: Literal["resource"] = "resource"


MessageContent = TextContent | ImageContent | EmbeddedResource


@dataclass
class Message:
    """MCP message"""

    role: str  # Literal["user", "assistant"]
    content: MessageContent


@dataclass
class InitializationOptions:
    """Options for server initialization"""

    capabilities: dict[str, Any]


@dataclass
class ServerInfo:
    """Server identification information"""

    name: str
    version: str
