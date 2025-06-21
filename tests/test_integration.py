"""Integration tests for Phase 2 features."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner
import asyncio
import json

from aishell.cli import main
from aishell.llm import LLMResponse
from aishell.mcp import MCPResponse


class TestLLMIntegration:
    """Integration tests for LLM functionality."""
    
    def test_query_command_help(self):
        """Test query command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['query', '--help'])
        
        assert result.exit_code == 0
        assert 'Send a query to an LLM provider' in result.output
        assert '--provider' in result.output
        assert '--stream' in result.output
    
    def test_collate_command_help(self):
        """Test collate command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['collate', '--help'])
        
        assert result.exit_code == 0
        assert 'Send the same query to multiple LLM providers' in result.output
        assert '--providers' in result.output
    
    @patch('aishell.cli.ClaudeLLMProvider')
    def test_query_command_execution(self, mock_claude_provider):
        """Test query command execution."""
        # Mock the provider
        mock_provider_instance = AsyncMock()
        mock_provider_instance.query.return_value = LLMResponse(
            content="Hello! This is a test response.",
            model="claude-3-sonnet",
            provider="claude",
            usage={"total_tokens": 25}
        )
        mock_provider_instance.default_model = "claude-3-sonnet"
        mock_claude_provider.return_value = mock_provider_instance
        
        runner = CliRunner()
        result = runner.invoke(main, [
            'query', 'Hello, how are you?',
            '--provider', 'claude'
        ])
        
        assert result.exit_code == 0
        assert 'Provider: claude' in result.output
        # The actual content assertion might be tricky due to Rich formatting
    
    @patch('aishell.cli.OpenAILLMProvider')
    def test_query_command_with_streaming(self, mock_openai_provider):
        """Test query command with streaming."""
        # Mock the provider for streaming
        mock_provider_instance = AsyncMock()
        
        # Mock the stream_query method directly as an async generator
        async def mock_stream_query(*args, **kwargs):
            for word in ["Hello", " world", "!"]:
                yield word
        
        mock_provider_instance.stream_query = mock_stream_query
        mock_provider_instance.default_model = "gpt-3.5-turbo"
        mock_openai_provider.return_value = mock_provider_instance
        
        runner = CliRunner()
        result = runner.invoke(main, [
            'query', 'Hello',
            '--provider', 'openai',
            '--stream'
        ])
        
        assert result.exit_code == 0
        assert 'Provider: openai' in result.output


class TestMCPIntegration:
    """Integration tests for MCP functionality."""
    
    def test_mcp_command_help(self):
        """Test MCP command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['mcp', '--help'])
        
        assert result.exit_code == 0
        assert 'Interact with MCP' in result.output
        assert '--method' in result.output
        assert '--raw' in result.output
    
    def test_mcp_convert_command_help(self):
        """Test MCP convert command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['mcp-convert', '--help'])
        
        assert result.exit_code == 0
        assert 'Convert natural language queries to MCP messages' in result.output
        assert '--provider' in result.output
        assert '--execute' in result.output
    
    @patch('aishell.cli.MCPClient')
    def test_mcp_command_simple(self, mock_mcp_client):
        """Test simple MCP command."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client_instance.initialize.return_value = MCPResponse(
            result={"status": "ok"},
            id=1
        )
        mock_client_instance.ping.return_value = MCPResponse(
            result={"status": "pong"},
            id=2
        )
        mock_mcp_client.return_value.__aenter__.return_value = mock_client_instance
        
        runner = CliRunner()
        result = runner.invoke(main, [
            'mcp', 'http://localhost:8000', 'ping'
        ])
        
        assert result.exit_code == 0
        assert 'Connecting to MCP server' in result.output
    
    @patch('aishell.cli.MCPClient')
    def test_mcp_command_with_method(self, mock_mcp_client):
        """Test MCP command with method parameter."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client_instance.initialize.return_value = MCPResponse(
            result={"status": "ok"},
            id=1
        )
        mock_client_instance.send_message.return_value = MCPResponse(
            result={"tools": [{"name": "search"}, {"name": "calc"}]},
            id=2
        )
        mock_mcp_client.return_value.__aenter__.return_value = mock_client_instance
        
        runner = CliRunner()
        result = runner.invoke(main, [
            'mcp', 'http://localhost:8000',
            '--method', 'tools/list'
        ])
        
        assert result.exit_code == 0
        assert 'Connecting to MCP server' in result.output
    
    @patch('aishell.cli.NLToMCPTranslator')
    def test_mcp_convert_command(self, mock_translator):
        """Test MCP convert command."""
        # Mock the translator
        mock_translator_instance = MagicMock()
        mock_translator_instance.get_suggestions.return_value = ["list tools", "ping server"]
        
        # Mock async translate method
        async def mock_translate(query):
            from aishell.mcp import MCPMessage, MCPMethod
            return MCPMessage(method=MCPMethod.TOOLS_LIST.value)
        
        mock_translator_instance.translate = mock_translate
        mock_translator.return_value = mock_translator_instance
        
        runner = CliRunner()
        result = runner.invoke(main, [
            'mcp-convert', 'list all available tools'
        ])
        
        assert result.exit_code == 0
        assert 'Query: list all available tools' in result.output


class TestCLIBasics:
    """Test basic CLI functionality for Phase 2."""
    
    def test_main_help_includes_new_commands(self):
        """Test that main help includes new commands."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert 'query' in result.output
        assert 'collate' in result.output
        assert 'mcp' in result.output
        assert 'mcp-convert' in result.output
    
    def test_query_command_requires_query(self):
        """Test that query command requires a query argument."""
        runner = CliRunner()
        result = runner.invoke(main, ['query'])
        
        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'Usage:' in result.output
    
    def test_mcp_command_requires_server_url(self):
        """Test that MCP command requires server URL."""
        runner = CliRunner()
        result = runner.invoke(main, ['mcp'])
        
        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'Usage:' in result.output
    
    def test_mcp_convert_requires_query(self):
        """Test that MCP convert command requires a query."""
        runner = CliRunner()
        result = runner.invoke(main, ['mcp-convert'])
        
        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'Usage:' in result.output


if __name__ == '__main__':
    pytest.main([__file__])