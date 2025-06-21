"""Tests for environment variable management."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from aishell.utils.env_manager import EnvManager


class TestEnvManager:
    """Test the environment variable manager."""
    
    def test_env_manager_initialization(self):
        """Test that env manager initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            manager = EnvManager(str(env_file))
            # Use resolve() to handle symlinks consistently
            assert manager.env_file == env_file.resolve()
    
    def test_load_env_file_not_exists(self):
        """Test loading when .env file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            manager = EnvManager(str(env_file))
            
            result = manager.load_env(verbose=False)
            assert result is False
    
    def test_load_env_file_exists(self):
        """Test loading valid .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            
            # Create test .env file
            with open(env_file, 'w') as f:
                f.write("# Test comment\n")
                f.write("TEST_KEY=test_value\n")
                f.write("QUOTED_KEY=\"quoted value\"\n")
                f.write("SINGLE_QUOTED='single quoted'\n")
                f.write("\n")  # Empty line
                f.write("ANOTHER_KEY=another_value\n")
            
            manager = EnvManager(str(env_file))
            result = manager.load_env(verbose=False)
            
            assert result is True
            assert os.environ.get('TEST_KEY') == 'test_value'
            assert os.environ.get('QUOTED_KEY') == 'quoted value'
            assert os.environ.get('SINGLE_QUOTED') == 'single quoted'
            assert os.environ.get('ANOTHER_KEY') == 'another_value'
    
    def test_reload_env(self):
        """Test reloading environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            
            # Create initial .env file
            with open(env_file, 'w') as f:
                f.write("INITIAL_KEY=initial_value\n")
            
            manager = EnvManager(str(env_file))
            manager.load_env(verbose=False)
            assert os.environ.get('INITIAL_KEY') == 'initial_value'
            
            # Update .env file
            with open(env_file, 'w') as f:
                f.write("INITIAL_KEY=updated_value\n")
                f.write("NEW_KEY=new_value\n")
            
            # Reload
            result = manager.reload_env(verbose=False)
            assert result is True
            assert os.environ.get('INITIAL_KEY') == 'updated_value'
            assert os.environ.get('NEW_KEY') == 'new_value'
    
    def test_get_var(self):
        """Test getting environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            
            with open(env_file, 'w') as f:
                f.write("TEST_VAR=test_value\n")
            
            manager = EnvManager(str(env_file))
            manager.load_env(verbose=False)
            
            assert manager.get_var('TEST_VAR') == 'test_value'
            assert manager.get_var('NONEXISTENT') is None
            assert manager.get_var('NONEXISTENT', 'default') == 'default'
    
    def test_set_var(self):
        """Test setting environment variables."""
        manager = EnvManager()
        
        manager.set_var('RUNTIME_VAR', 'runtime_value')
        assert os.environ.get('RUNTIME_VAR') == 'runtime_value'
    
    def test_get_llm_config(self):
        """Test getting LLM configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            
            with open(env_file, 'w') as f:
                f.write("ANTHROPIC_API_KEY=test_claude_key\n")
                f.write("OPENAI_API_KEY=test_openai_key\n")
                f.write("DEFAULT_TEMPERATURE=0.8\n")
            
            manager = EnvManager(str(env_file))
            manager.load_env(verbose=False)
            
            # Test Claude config
            claude_config = manager.get_llm_config('claude')
            assert claude_config['api_key'] == 'test_claude_key'
            assert claude_config['temperature'] == '0.8'
            
            # Test OpenAI config
            openai_config = manager.get_llm_config('openai')
            assert openai_config['api_key'] == 'test_openai_key'
            assert openai_config['base_url'] == 'https://api.openai.com/v1'
            
            # Test unknown provider
            unknown_config = manager.get_llm_config('unknown')
            assert unknown_config == {}
    
    def test_invalid_env_line(self):
        """Test handling of invalid lines in .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            
            with open(env_file, 'w') as f:
                f.write("VALID_KEY=valid_value\n")
                f.write("INVALID_LINE_NO_EQUALS\n")
                f.write("ANOTHER_VALID=another_value\n")
            
            manager = EnvManager(str(env_file))
            result = manager.load_env(verbose=False)
            
            # Should still succeed despite invalid line
            assert result is True
            assert os.environ.get('VALID_KEY') == 'valid_value'
            assert os.environ.get('ANOTHER_VALID') == 'another_value'


class TestShellEnvCommand:
    """Test the shell env command."""
    
    def test_env_command_help(self):
        """Test env command shows help when no subcommand provided."""
        from aishell.shell.intelligent_shell import IntelligentShell
        
        shell = IntelligentShell(nl_provider='mock')
        exit_code, stdout, stderr = shell.execute_command('env')
        
        assert exit_code == 0
        # Help should be displayed (function prints directly to console)
    
    def test_env_command_invalid_subcommand(self):
        """Test env command with invalid subcommand."""
        from aishell.shell.intelligent_shell import IntelligentShell
        
        shell = IntelligentShell(nl_provider='mock')
        exit_code, stdout, stderr = shell.execute_command('env invalid')
        
        assert exit_code == 1
        assert "Unknown subcommand" in stderr


if __name__ == '__main__':
    pytest.main([__file__])