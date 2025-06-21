"""Tests for MCP discovery functionality."""

import pytest
from unittest.mock import Mock, patch

from aishell.utils.mcp_discovery import MCPCapabilityManager, get_mcp_capability_manager


class TestMCPCapabilityManager:
    """Test MCP capability management."""
    
    def test_init(self):
        """Test MCPCapabilityManager initialization."""
        manager = MCPCapabilityManager()
        assert manager.server_capabilities is not None
        assert 'postgres' in manager.server_capabilities
        assert 'github' in manager.server_capabilities
        assert 'jira' in manager.server_capabilities
    
    def test_get_server_capabilities(self):
        """Test getting capabilities for a specific server."""
        manager = MCPCapabilityManager()
        
        # Test valid server
        postgres_caps = manager.get_server_capabilities('postgres')
        assert postgres_caps is not None
        assert 'description' in postgres_caps
        assert 'capabilities' in postgres_caps
        assert 'example_commands' in postgres_caps
        assert 'PostgreSQL database access' in postgres_caps['description']
        
        # Test invalid server
        invalid_caps = manager.get_server_capabilities('nonexistent')
        assert invalid_caps is None
    
    @patch('aishell.utils.mcp_discovery.get_env_manager')
    def test_get_available_servers(self, mock_get_env_manager):
        """Test getting available MCP servers from environment."""
        mock_env_manager = Mock()
        mock_env_manager.get_mcp_servers.return_value = {
            'postgres': 'npx @modelcontextprotocol/server-postgres',
            'github': 'npx @modelcontextprotocol/server-github'
        }
        mock_get_env_manager.return_value = mock_env_manager
        
        manager = MCPCapabilityManager()
        servers = manager.get_available_servers()
        
        assert servers == {
            'postgres': 'npx @modelcontextprotocol/server-postgres',
            'github': 'npx @modelcontextprotocol/server-github'
        }
        mock_env_manager.get_mcp_servers.assert_called_once()
    
    @patch('aishell.utils.mcp_discovery.get_env_manager')
    def test_generate_mcp_context_prompt_no_servers(self, mock_get_env_manager):
        """Test generating context prompt with no servers configured."""
        mock_env_manager = Mock()
        mock_env_manager.get_mcp_servers.return_value = {}
        mock_get_env_manager.return_value = mock_env_manager
        
        manager = MCPCapabilityManager()
        context = manager.generate_mcp_context_prompt()
        
        assert context == "No MCP servers are currently configured."
    
    @patch('aishell.utils.mcp_discovery.get_env_manager')
    def test_generate_mcp_context_prompt_with_servers(self, mock_get_env_manager):
        """Test generating context prompt with configured servers."""
        mock_env_manager = Mock()
        mock_env_manager.get_mcp_servers.return_value = {
            'postgres': 'npx @modelcontextprotocol/server-postgres',
            'github': 'npx @modelcontextprotocol/server-github'
        }
        mock_get_env_manager.return_value = mock_env_manager
        
        manager = MCPCapabilityManager()
        context = manager.generate_mcp_context_prompt()
        
        assert "AVAILABLE MCP TOOLS AND CAPABILITIES:" in context
        assert "POSTGRES" in context
        assert "GITHUB" in context
        assert "PostgreSQL database access" in context
        assert "GitHub repository and API management" in context
        assert "mcp postgres" in context
        assert "mcp github" in context
        assert "USAGE INSTRUCTIONS:" in context
    
    @patch('aishell.utils.mcp_discovery.get_env_manager')
    def test_get_capability_summary(self, mock_get_env_manager):
        """Test getting capability summary."""
        mock_env_manager = Mock()
        mock_env_manager.get_mcp_servers.return_value = {
            'postgres': 'npx @modelcontextprotocol/server-postgres',
            'github': 'npx @modelcontextprotocol/server-github'
        }
        mock_get_env_manager.return_value = mock_env_manager
        
        manager = MCPCapabilityManager()
        summary = manager.get_capability_summary()
        
        assert 'postgres' in summary
        assert 'github' in summary
        assert isinstance(summary['postgres'], list)
        assert isinstance(summary['github'], list)
        assert len(summary['postgres']) > 0
        assert len(summary['github']) > 0


def test_get_mcp_capability_manager():
    """Test the global MCP capability manager singleton."""
    manager1 = get_mcp_capability_manager()
    manager2 = get_mcp_capability_manager()
    
    assert manager1 is manager2  # Should be the same instance
    assert isinstance(manager1, MCPCapabilityManager)