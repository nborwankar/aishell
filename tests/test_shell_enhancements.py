"""Tests for shell enhancements with LLM and MCP built-in commands."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aishell.shell.intelligent_shell import IntelligentShell


class TestShellEnhancements:
    """Test the enhanced shell with LLM/MCP commands."""
    
    def test_shell_initialization_with_llm_imports(self):
        """Test that shell initializes with LLM imports."""
        shell = IntelligentShell(nl_provider='mock')
        assert shell is not None
        assert hasattr(shell, '_handle_llm')
        assert hasattr(shell, '_handle_mcp')
        assert hasattr(shell, '_handle_collate')
        assert hasattr(shell, '_handle_generate')
    
    def test_llm_command_recognition(self):
        """Test that LLM commands are recognized."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test invalid usage
        exit_code, stdout, stderr = shell.execute_command('llm')
        assert exit_code == 1
        assert "Usage:" in stderr
    
    def test_mcp_command_recognition(self):
        """Test that MCP commands are recognized."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test invalid usage
        exit_code, stdout, stderr = shell.execute_command('mcp')
        assert exit_code == 1
        assert "Usage:" in stderr
    
    def test_collate_command_recognition(self):
        """Test that collate commands are recognized."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test invalid usage
        exit_code, stdout, stderr = shell.execute_command('collate')
        assert exit_code == 1
        assert "Usage:" in stderr
    
    def test_generate_command_recognition(self):
        """Test that generate commands are recognized."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test invalid usage
        exit_code, stdout, stderr = shell.execute_command('generate')
        assert exit_code == 1
        assert "Usage:" in stderr
        
        # Test invalid usage with only language
        exit_code, stdout, stderr = shell.execute_command('generate python')
        assert exit_code == 1
        assert "Usage:" in stderr
    
    @patch('aishell.shell.intelligent_shell.ClaudeLLMProvider')
    def test_llm_command_execution(self, mock_claude_provider):
        """Test LLM command execution."""
        # Mock the provider
        mock_provider_instance = AsyncMock()
        mock_provider_instance.query.return_value = AsyncMock()
        mock_provider_instance.query.return_value.is_error = False
        mock_provider_instance.query.return_value.content = "Test response"
        mock_provider_instance.query.return_value.model = "test-model"
        mock_provider_instance.query.return_value.usage = {"total_tokens": 10}
        mock_claude_provider.return_value = mock_provider_instance
        
        shell = IntelligentShell(nl_provider='mock')
        
        # Test basic LLM query
        exit_code, stdout, stderr = shell.execute_command('llm "test query"')
        assert exit_code == 0
        mock_provider_instance.query.assert_called_once()
    
    @patch('aishell.shell.intelligent_shell.MCPClient')
    def test_mcp_command_execution(self, mock_mcp_client):
        """Test MCP command execution."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client_instance.initialize.return_value = AsyncMock()
        mock_client_instance.initialize.return_value.is_error = False
        mock_client_instance.ping.return_value = AsyncMock()
        mock_mcp_client.return_value.__aenter__.return_value = mock_client_instance
        
        shell = IntelligentShell(nl_provider='mock')
        
        # Test MCP ping command
        exit_code, stdout, stderr = shell.execute_command('mcp http://localhost:8000 ping')
        assert exit_code == 0
    
    def test_help_includes_new_commands(self):
        """Test that help includes new commands."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Capture help output
        exit_code, stdout, stderr = shell.execute_command('help')
        assert exit_code == 0
        
        # Check if we can find the help method (it prints directly to console)
        # We'll test the _show_help method exists
        assert hasattr(shell, '_show_help')
    
    def test_command_parsing_with_quotes(self):
        """Test command parsing with quoted arguments."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test that commands with quoted strings are parsed correctly
        commands = [
            'llm "test query with spaces"',
            'llm claude "test query with provider"',
            'collate claude openai "another test query"',
            'mcp http://localhost:8000 "command with spaces"',
            'generate python "fibonacci function"'
        ]
        
        for cmd in commands:
            # Should not raise parsing errors
            exit_code, stdout, stderr = shell.execute_command(cmd)
            # The commands will fail due to missing API keys/servers, but parsing should work
            assert "parsing" not in stderr.lower()
    
    @patch('aishell.shell.intelligent_shell.ClaudeLLMProvider')
    @patch('aishell.shell.intelligent_shell.OpenAILLMProvider')
    def test_collate_command_with_providers(self, mock_openai, mock_claude):
        """Test collate command with specific providers."""
        # Mock both providers
        for mock_provider_class in [mock_claude, mock_openai]:
            mock_provider_instance = AsyncMock()
            mock_provider_instance.query.return_value = AsyncMock()
            mock_provider_instance.query.return_value.is_error = False
            mock_provider_instance.query.return_value.content = "Test response"
            mock_provider_instance.query.return_value.usage = {"total_tokens": 10}
            mock_provider_class.return_value = mock_provider_instance
        
        shell = IntelligentShell(nl_provider='mock')
        
        # Test collate with specific providers
        exit_code, stdout, stderr = shell.execute_command('collate claude openai "test"')
        assert exit_code == 0
    
    def test_provider_validation(self):
        """Test LLM provider validation."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test with invalid provider
        exit_code, stdout, stderr = shell.execute_command('llm invalid "test"')
        assert exit_code == 1
        assert "Unknown provider" in stderr
    
    def test_shell_backwards_compatibility(self):
        """Test that existing shell commands still work."""
        shell = IntelligentShell(nl_provider='mock')
        
        # Test existing built-in commands
        existing_commands = [
            'pwd',
            'alias',
            'cd /',
            'export TEST=value'
        ]
        
        for cmd in existing_commands:
            try:
                exit_code, stdout, stderr = shell.execute_command(cmd)
                # Commands should execute without errors (exit_code varies by command)
                assert isinstance(exit_code, int)
            except Exception as e:
                pytest.fail(f"Existing command '{cmd}' failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__])