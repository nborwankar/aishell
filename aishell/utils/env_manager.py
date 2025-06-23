"""Environment variable management for aishell."""

import os
from pathlib import Path
from typing import Dict, Optional, List
import threading
from rich.console import Console

console = Console()


class EnvManager:
    """Manages environment variables and .env file loading."""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file).resolve()
        self._lock = threading.Lock()
        self._loaded_vars: Dict[str, str] = {}
        
    def load_env(self, verbose: bool = True) -> bool:
        """Load environment variables from .env file."""
        with self._lock:
            if not self.env_file.exists():
                if verbose:
                    console.print(f"[yellow]No .env file found at {self.env_file}[/yellow]")
                    console.print("[dim]Create .env from .env.example to configure API keys[/dim]")
                return False
            
            try:
                loaded_count = 0
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        
                        # Parse KEY=VALUE format
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Remove quotes if present
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            
                            # Set environment variable
                            os.environ[key] = value
                            self._loaded_vars[key] = value
                            loaded_count += 1
                        else:
                            if verbose:
                                console.print(f"[yellow]Warning: Invalid line {line_num} in .env file: {line}[/yellow]")
                
                if verbose:
                    console.print(f"[green]Loaded {loaded_count} environment variables from {self.env_file.name}[/green]")
                
                return True
                
            except Exception as e:
                if verbose:
                    console.print(f"[red]Error loading .env file: {e}[/red]")
                return False
    
    def reload_env(self, verbose: bool = True) -> bool:
        """Reload environment variables from .env file."""
        if verbose:
            console.print("[blue]Reloading environment variables...[/blue]")
        
        # Store old values for comparison
        old_vars = dict(self._loaded_vars)
        
        # Load new values
        success = self.load_env(verbose=False)
        
        if success and verbose:
            # Show what changed
            new_vars = set(self._loaded_vars.keys())
            old_vars_set = set(old_vars.keys())
            
            added = new_vars - old_vars_set
            removed = old_vars_set - new_vars
            modified = []
            
            for key in new_vars & old_vars_set:
                if self._loaded_vars[key] != old_vars.get(key):
                    modified.append(key)
            
            if added:
                console.print(f"[green]Added variables: {', '.join(sorted(added))}[/green]")
            if removed:
                console.print(f"[yellow]Removed variables: {', '.join(sorted(removed))}[/yellow]")
            if modified:
                console.print(f"[blue]Modified variables: {', '.join(sorted(modified))}[/blue]")
            
            if not (added or removed or modified):
                console.print("[dim]No changes detected[/dim]")
        
        return success
    
    def show_env(self, filter_pattern: Optional[str] = None) -> None:
        """Show loaded environment variables."""
        if not self._loaded_vars:
            console.print("[yellow]No environment variables loaded from .env file[/yellow]")
            return
        
        from rich.table import Table
        
        table = Table(title="Environment Variables", show_header=True)
        table.add_column("Variable", style="cyan", width=25)
        table.add_column("Value", style="white", no_wrap=False)
        
        for key, value in sorted(self._loaded_vars.items()):
            if filter_pattern and filter_pattern.lower() not in key.lower():
                continue
            
            # Mask sensitive values
            display_value = value
            sensitive_keys = ['key', 'token', 'secret', 'password', 'auth']
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if len(value) > 8:
                    display_value = value[:4] + "..." + value[-4:]
                else:
                    display_value = "***"
            
            table.add_row(key, display_value)
        
        console.print(table)
    
    def get_var(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get an environment variable value."""
        return os.environ.get(key, default)
    
    def set_var(self, key: str, value: str) -> None:
        """Set an environment variable (runtime only, not persisted)."""
        os.environ[key] = value
        console.print(f"[green]Set {key} = {value}[/green]")
        console.print("[dim]Note: This change is not persisted to .env file[/dim]")
    
    def get_llm_config(self, provider: str) -> Dict[str, Optional[str]]:
        """Get LLM configuration for a specific provider."""
        configs = {
            'claude': {
                'api_key': self.get_var('ANTHROPIC_API_KEY'),
                'model': self.get_var('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022'),
                'temperature': self.get_var('DEFAULT_TEMPERATURE', '0.7'),
                'max_tokens': self.get_var('DEFAULT_MAX_TOKENS', '4096')
            },
            'openai': {
                'api_key': self.get_var('OPENAI_API_KEY'),
                'base_url': self.get_var('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                'model': self.get_var('OPENAI_MODEL', 'gpt-4o-mini'),
                'temperature': self.get_var('DEFAULT_TEMPERATURE', '0.7'),
                'max_tokens': self.get_var('DEFAULT_MAX_TOKENS', '4096')
            },
            'gemini': {
                'api_key': self.get_var('GOOGLE_API_KEY'),
                'model': self.get_var('GEMINI_MODEL', 'gemini-1.5-flash'),
                'temperature': self.get_var('DEFAULT_TEMPERATURE', '0.7'),
                'max_tokens': self.get_var('DEFAULT_MAX_TOKENS', '4096')
            },
            'ollama': {
                'base_url': self.get_var('OLLAMA_URL', 'http://localhost:11434'),
                'model': self.get_var('OLLAMA_MODEL', 'llama3.2'),
                'temperature': self.get_var('DEFAULT_TEMPERATURE', '0.7'),
                'max_tokens': self.get_var('DEFAULT_MAX_TOKENS', '4096')
            }
        }
        
        return configs.get(provider, {})
    
    def get_mcp_servers(self) -> Dict[str, str]:
        """Get configured MCP servers from environment."""
        servers = {}
        
        # Get all environment variables that start with MCP_
        for key, value in self._loaded_vars.items():
            if key.startswith('MCP_') and key.endswith('_SERVER') and value:
                # Convert MCP_POSTGRES_SERVER to 'postgres'
                server_name = key[4:-7].lower()  # Remove 'MCP_' prefix and '_SERVER' suffix
                servers[server_name] = value
        
        return servers
    
    def list_available_mcp_servers(self) -> List[str]:
        """List all available MCP server types from .env.example."""
        available_servers = [
            'postgres', 'sqlite', 'mysql',       # Database servers
            'github', 'gitlab',                  # Version control
            'jira', 'atlassian',                # Atlassian tools
            'filesystem', 'fetch', 'memory',     # File/web servers
            'docker', 'kubernetes',              # Development tools
            'aws', 'gcp',                       # Cloud services
            'custom_1', 'custom_2'              # Custom servers
        ]
        return available_servers


# Global environment manager instance
_env_manager = None


def get_env_manager() -> EnvManager:
    """Get or create the global environment manager instance."""
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvManager()
    return _env_manager


def load_env_on_startup(verbose: bool = True) -> bool:
    """Load environment variables on startup."""
    env_manager = get_env_manager()
    return env_manager.load_env(verbose=verbose)