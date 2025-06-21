import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from rich.console import Console

console = Console()


class NLConverter(ABC):
    """Abstract base class for natural language to command converters."""
    
    @abstractmethod
    def convert(self, nl_input: str, context: Dict[str, Any]) -> Optional[str]:
        """Convert natural language to shell command."""
        pass


class ClaudeNLConverter(NLConverter):
    """Convert natural language to shell commands using Claude API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set")
        
        # Import here to avoid dependency if not using Claude
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install anthropic: pip install anthropic")
    
    def convert(self, nl_input: str, context: Dict[str, Any]) -> Optional[str]:
        """Convert natural language to shell command using Claude."""
        try:
            # Build context information
            context_info = f"""
Current directory: {context.get('cwd', 'unknown')}
Operating system: {context.get('os', 'unknown')}
Shell: {context.get('shell', 'bash')}
"""
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": f"""Convert this natural language request to a shell command. 
Return ONLY the command, no explanation or markdown.

Context:
{context_info}

Request: {nl_input}

Command:"""
                }]
            )
            
            command = response.content[0].text.strip()
            return command if command else None
            
        except Exception as e:
            console.print(f"[red]Error converting with Claude: {e}[/red]")
            return None


class OllamaNLConverter(NLConverter):
    """Convert natural language to shell commands using Ollama (local LLM)."""
    
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        
        # Import here to avoid dependency if not using Ollama
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("Please install requests: pip install requests")
    
    def convert(self, nl_input: str, context: Dict[str, Any]) -> Optional[str]:
        """Convert natural language to shell command using Ollama."""
        try:
            # Build context information
            context_info = f"""
Current directory: {context.get('cwd', 'unknown')}
Operating system: {context.get('os', 'unknown')}
Shell: {context.get('shell', 'bash')}
"""
            
            prompt = f"""Convert this natural language request to a shell command. 
Return ONLY the command, no explanation or markdown.

Context:
{context_info}

Request: {nl_input}

Command:"""
            
            response = self.requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0,
                    "max_tokens": 200,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                command = result.get("response", "").strip()
                # Extract just the command if the model included explanation
                if '\n' in command:
                    command = command.split('\n')[0]
                return command if command else None
            else:
                console.print(f"[red]Ollama error: {response.status_code}[/red]")
                return None
                
        except Exception as e:
            console.print(f"[red]Error converting with Ollama: {e}[/red]")
            return None


class MockNLConverter(NLConverter):
    """Mock converter for testing without API access."""
    
    def convert(self, nl_input: str, context: Dict[str, Any]) -> Optional[str]:
        """Simple pattern matching for common requests."""
        nl_lower = nl_input.lower()
        
        # Simple pattern matching
        patterns = {
            "list files": "ls -la",
            "show files": "ls",
            "current directory": "pwd",
            "go home": "cd ~",
            "go back": "cd ..",
            "clear screen": "clear",
            "show history": "history",
            "disk usage": "df -h",
            "memory usage": "free -h",
            "running processes": "ps aux",
            "network connections": "netstat -an",
            "find": f"find . -name '*{nl_input.split('find')[-1].strip()}*'" if 'find' in nl_lower else None,
            "search for": f"grep -r '{nl_input.split('search for')[-1].strip()}' ." if 'search for' in nl_lower else None,
            "create directory": f"mkdir {nl_input.split('directory')[-1].strip()}" if 'directory' in nl_lower else None,
            "delete": f"rm {nl_input.split('delete')[-1].strip()}" if 'delete' in nl_lower else None,
        }
        
        for pattern, command in patterns.items():
            if pattern in nl_lower and command:
                return command
        
        return None


def get_nl_converter(provider: str = "claude", **kwargs) -> NLConverter:
    """Factory function to get appropriate NL converter."""
    if provider == "claude":
        return ClaudeNLConverter(**kwargs)
    elif provider == "ollama":
        return OllamaNLConverter(**kwargs)
    elif provider == "mock":
        return MockNLConverter(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")