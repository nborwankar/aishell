"""MCP client for interacting with Model Context Protocol servers."""

import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel


console = Console()


class MCPMethod(Enum):
    """Standard MCP methods."""
    # Tool-related methods
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # Resource-related methods
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_WRITE = "resources/write"
    
    # Prompt-related methods
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    
    # Server info
    INITIALIZE = "initialize"
    PING = "ping"
    
    # Custom method
    CUSTOM = "custom"


@dataclass
class MCPMessage:
    """MCP message structure."""
    jsonrpc: str = "2.0"
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            data["params"] = self.params
        if self.id is not None:
            data["id"] = self.id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params"),
            id=data.get("id")
        )


@dataclass
class MCPResponse:
    """MCP response structure."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    
    @property
    def is_error(self) -> bool:
        """Check if response is an error."""
        return self.error is not None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPResponse":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            result=data.get("result"),
            error=data.get("error"),
            id=data.get("id")
        )


class MCPClient:
    """Client for interacting with MCP servers."""
    
    def __init__(self, server_url: str, timeout: int = 30):
        """Initialize MCP client.
        
        Args:
            server_url: URL of the MCP server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_id = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    def _get_next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id
    
    async def send_message(self, message: MCPMessage) -> MCPResponse:
        """Send a message to the MCP server.
        
        Args:
            message: MCP message to send
            
        Returns:
            MCP response from the server
        """
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Add ID if not present
        if message.id is None:
            message.id = self._get_next_id()
        
        try:
            async with self._session.post(
                f"{self.server_url}/mcp",
                json=message.to_dict(),
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    return MCPResponse(
                        jsonrpc="2.0",
                        error={
                            "code": response.status,
                            "message": f"HTTP error: {response.status}",
                            "data": await response.text()
                        },
                        id=message.id
                    )
                
                data = await response.json()
                return MCPResponse.from_dict(data)
                
        except aiohttp.ClientError as e:
            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                id=message.id
            )
        except Exception as e:
            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                id=message.id
            )
    
    async def initialize(self, client_info: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Initialize connection with MCP server.
        
        Args:
            client_info: Optional client information
            
        Returns:
            Server initialization response
        """
        params = {
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": True
            }
        }
        
        if client_info:
            params["clientInfo"] = client_info
        
        message = MCPMessage(
            method=MCPMethod.INITIALIZE.value,
            params=params
        )
        
        return await self.send_message(message)
    
    async def ping(self) -> MCPResponse:
        """Ping the MCP server.
        
        Returns:
            Ping response
        """
        message = MCPMessage(method=MCPMethod.PING.value)
        return await self.send_message(message)
    
    async def list_tools(self) -> MCPResponse:
        """List available tools from the server.
        
        Returns:
            List of available tools
        """
        message = MCPMessage(method=MCPMethod.TOOLS_LIST.value)
        return await self.send_message(message)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPResponse:
        """Call a tool on the server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        message = MCPMessage(
            method=MCPMethod.TOOLS_CALL.value,
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )
        return await self.send_message(message)
    
    async def list_resources(self) -> MCPResponse:
        """List available resources from the server.
        
        Returns:
            List of available resources
        """
        message = MCPMessage(method=MCPMethod.RESOURCES_LIST.value)
        return await self.send_message(message)
    
    async def read_resource(self, uri: str) -> MCPResponse:
        """Read a resource from the server.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content
        """
        message = MCPMessage(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": uri}
        )
        return await self.send_message(message)
    
    async def list_prompts(self) -> MCPResponse:
        """List available prompts from the server.
        
        Returns:
            List of available prompts
        """
        message = MCPMessage(method=MCPMethod.PROMPTS_LIST.value)
        return await self.send_message(message)
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Get a prompt from the server.
        
        Args:
            name: Prompt name
            arguments: Optional prompt arguments
            
        Returns:
            Prompt content
        """
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
            
        message = MCPMessage(
            method=MCPMethod.PROMPTS_GET.value,
            params=params
        )
        return await self.send_message(message)
    
    def display_response(self, response: MCPResponse, title: str = "MCP Response"):
        """Display an MCP response nicely formatted.
        
        Args:
            response: MCP response to display
            title: Panel title
        """
        if response.is_error:
            error_content = f"[red]Error Code:[/red] {response.error.get('code', 'Unknown')}\n"
            error_content += f"[red]Message:[/red] {response.error.get('message', 'Unknown error')}"
            
            if 'data' in response.error:
                error_content += f"\n[red]Details:[/red] {response.error['data']}"
            
            panel = Panel(
                error_content,
                title=f"[red]{title} - Error[/red]",
                border_style="red",
                padding=(1, 2)
            )
            console.print(panel)
        else:
            # Format the result based on its type
            if isinstance(response.result, (dict, list)):
                syntax = Syntax(
                    json.dumps(response.result, indent=2),
                    "json",
                    theme="monokai",
                    line_numbers=False
                )
                panel = Panel(
                    syntax,
                    title=f"[green]{title}[/green]",
                    border_style="green",
                    padding=(1, 2)
                )
            else:
                panel = Panel(
                    str(response.result),
                    title=f"[green]{title}[/green]",
                    border_style="green",
                    padding=(1, 2)
                )
            console.print(panel)