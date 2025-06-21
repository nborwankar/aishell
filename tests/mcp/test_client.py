"""Tests for MCP client."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from aishell.mcp.client import MCPClient, MCPMessage, MCPResponse, MCPMethod


class TestMCPMessage:
    """Test MCP message class."""
    
    def test_message_creation(self):
        """Test message creation."""
        message = MCPMessage(
            method="tools/list",
            params={"limit": 10},
            id=1
        )
        
        assert message.jsonrpc == "2.0"
        assert message.method == "tools/list"
        assert message.params == {"limit": 10}
        assert message.id == 1
    
    def test_to_dict(self):
        """Test message serialization."""
        message = MCPMessage(
            method="tools/call",
            params={"name": "search", "arguments": {"query": "test"}}
        )
        
        data = message.to_dict()
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tools/call"
        assert data["params"]["name"] == "search"
    
    def test_from_dict(self):
        """Test message deserialization."""
        data = {
            "jsonrpc": "2.0",
            "method": "ping",
            "id": 42
        }
        
        message = MCPMessage.from_dict(data)
        
        assert message.jsonrpc == "2.0"
        assert message.method == "ping"
        assert message.id == 42
        assert message.params is None


class TestMCPResponse:
    """Test MCP response class."""
    
    def test_success_response(self):
        """Test successful response."""
        response = MCPResponse(
            result={"tools": ["search", "calc"]},
            id=1
        )
        
        assert not response.is_error
        assert response.result["tools"] == ["search", "calc"]
        assert response.id == 1
    
    def test_error_response(self):
        """Test error response."""
        response = MCPResponse(
            error={"code": -32600, "message": "Invalid request"},
            id=1
        )
        
        assert response.is_error
        assert response.error["code"] == -32600
        assert response.error["message"] == "Invalid request"
    
    def test_from_dict(self):
        """Test response deserialization."""
        data = {
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": 123
        }
        
        response = MCPResponse.from_dict(data)
        
        assert response.jsonrpc == "2.0"
        assert response.result["status"] == "ok"
        assert response.id == 123
        assert not response.is_error


class TestMCPClient:
    """Test MCP client."""
    
    def test_initialization(self):
        """Test client initialization."""
        client = MCPClient("http://localhost:8000")
        
        assert client.server_url == "http://localhost:8000"
        assert client._request_id == 0
    
    def test_url_normalization(self):
        """Test URL normalization."""
        client = MCPClient("http://localhost:8000/")
        
        assert client.server_url == "http://localhost:8000"
    
    def test_request_id_generation(self):
        """Test request ID generation."""
        client = MCPClient("http://localhost:8000")
        
        id1 = client._get_next_id()
        id2 = client._get_next_id()
        
        assert id1 == 1
        assert id2 == 2
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with MCPClient("http://localhost:8000") as client:
            assert isinstance(client, MCPClient)
            assert client._session is not None
    
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message sending."""
        client = MCPClient("http://localhost:8000")
        message = MCPMessage(method="tools/list")
        
        # Mock the send_message method to return a successful response
        client.send_message = AsyncMock(return_value=MCPResponse(
            result={"tools": ["search"]},
            id=1
        ))
        
        response = await client.send_message(message)
        
        assert not response.is_error
        assert response.result["tools"] == ["search"]
        assert response.id == 1
    
    @pytest.mark.asyncio
    async def test_send_message_http_error(self):
        """Test HTTP error handling."""
        client = MCPClient("http://localhost:8000")
        message = MCPMessage(method="tools/list")
        
        # Mock the send_message method to return an error response
        client.send_message = AsyncMock(return_value=MCPResponse(
            error={"code": 404, "message": "HTTP error: 404", "data": "Not Found"},
            id=1
        ))
        
        response = await client.send_message(message)
        
        assert response.is_error
        assert response.error["code"] == 404
        assert "HTTP error" in response.error["message"]
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization method."""
        with patch.object(MCPClient, 'send_message') as mock_send:
            mock_send.return_value = MCPResponse(
                result={"protocolVersion": "0.1.0", "capabilities": {}},
                id=1
            )
            
            client = MCPClient("http://localhost:8000")
            response = await client.initialize({"name": "test"})
            
            # Check that send_message was called with correct parameters
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.method == MCPMethod.INITIALIZE.value
            assert message.params["clientInfo"]["name"] == "test"
    
    @pytest.mark.asyncio
    async def test_ping(self):
        """Test ping method."""
        with patch.object(MCPClient, 'send_message') as mock_send:
            mock_send.return_value = MCPResponse(result={"status": "ok"}, id=1)
            
            client = MCPClient("http://localhost:8000")
            response = await client.ping()
            
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.method == MCPMethod.PING.value
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test list tools method."""
        with patch.object(MCPClient, 'send_message') as mock_send:
            mock_send.return_value = MCPResponse(
                result={"tools": [{"name": "search"}]},
                id=1
            )
            
            client = MCPClient("http://localhost:8000")
            response = await client.list_tools()
            
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.method == MCPMethod.TOOLS_LIST.value
    
    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test call tool method."""
        with patch.object(MCPClient, 'send_message') as mock_send:
            mock_send.return_value = MCPResponse(
                result={"content": "Search results"},
                id=1
            )
            
            client = MCPClient("http://localhost:8000")
            response = await client.call_tool("search", {"query": "python"})
            
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.method == MCPMethod.TOOLS_CALL.value
            assert message.params["name"] == "search"
            assert message.params["arguments"]["query"] == "python"
    
    @pytest.mark.asyncio
    async def test_read_resource(self):
        """Test read resource method."""
        with patch.object(MCPClient, 'send_message') as mock_send:
            mock_send.return_value = MCPResponse(
                result={"content": "file content"},
                id=1
            )
            
            client = MCPClient("http://localhost:8000")
            response = await client.read_resource("file://test.txt")
            
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.method == MCPMethod.RESOURCES_READ.value
            assert message.params["uri"] == "file://test.txt"