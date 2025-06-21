import os
import sys
import subprocess
import shlex
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import json
import readline
import platform

from rich.console import Console
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from aishell.shell.nl_converter import get_nl_converter, NLConverter

console = Console()


class CommandHistory:
    """Manage command history with persistence."""
    
    def __init__(self, history_file: str = "~/.aishell_history"):
        self.history_file = Path(history_file).expanduser()
        self.history: List[str] = []
        self.load_history()
    
    def load_history(self):
        """Load command history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    self.history = [line.strip() for line in f.readlines()]
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load history: {e}[/yellow]")
    
    def save_history(self):
        """Save command history to file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                f.write('\n'.join(self.history[-1000:]))  # Keep last 1000 commands
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save history: {e}[/yellow]")
    
    def add(self, command: str):
        """Add command to history."""
        if command and command not in ['exit', 'quit']:
            self.history.append(command)
            self.save_history()


class CommandSuggester:
    """Provide intelligent command suggestions."""
    
    def __init__(self):
        self.common_commands = {
            'git': ['status', 'add', 'commit', 'push', 'pull', 'branch', 'checkout', 'merge', 'log'],
            'docker': ['ps', 'images', 'run', 'build', 'stop', 'rm', 'exec', 'logs'],
            'npm': ['install', 'start', 'test', 'run', 'build', 'update'],
            'python': ['-m pip install', '-m venv', '-c', '--version'],
            'pip': ['install', 'list', 'freeze', 'show', 'uninstall'],
        }
        
        self.dangerous_commands = {
            'rm': '-rf',
            'chmod': '777',
            'chown': '-R',
            'dd': 'if=',
            'mkfs': '.',
            'format': 'c:',
        }
    
    def suggest_completion(self, partial_command: str) -> List[str]:
        """Suggest command completions based on partial input."""
        suggestions = []
        parts = partial_command.split()
        
        if not parts:
            return suggestions
        
        base_cmd = parts[0]
        
        # Check for common command patterns
        if base_cmd in self.common_commands and len(parts) == 1:
            suggestions = [f"{base_cmd} {sub}" for sub in self.common_commands[base_cmd]]
        
        # File/directory completion
        if len(parts) >= 2:
            last_part = parts[-1]
            if '/' in last_part or last_part.startswith('.'):
                suggestions.extend(self._complete_path(last_part))
        
        return suggestions[:10]  # Limit suggestions
    
    def _complete_path(self, partial_path: str) -> List[str]:
        """Complete file/directory paths."""
        try:
            path = Path(partial_path)
            parent = path.parent
            prefix = path.name
            
            if parent.exists():
                matches = []
                for item in parent.iterdir():
                    if item.name.startswith(prefix):
                        if item.is_dir():
                            matches.append(str(item) + '/')
                        else:
                            matches.append(str(item))
                return matches
        except Exception:
            pass
        return []
    
    def check_dangerous(self, command: str) -> Optional[str]:
        """Check if command might be dangerous."""
        for cmd, pattern in self.dangerous_commands.items():
            if cmd in command and pattern in command:
                return f"⚠️  Warning: This command contains potentially dangerous patterns ({cmd} {pattern})"
        return None


class IntelligentShell:
    """An intelligent shell with enhanced features."""
    
    def __init__(self, nl_provider: str = "claude", nl_converter_kwargs: Optional[Dict] = None):
        self.history = CommandHistory()
        self.suggester = CommandSuggester()
        self.aliases: Dict[str, str] = self._load_aliases()
        self.env_vars: Dict[str, str] = {}
        self.current_dir = Path.cwd()
        
        # Initialize NL converter
        self.nl_converter: Optional[NLConverter] = None
        try:
            nl_converter_kwargs = nl_converter_kwargs or {}
            self.nl_converter = get_nl_converter(nl_provider, **nl_converter_kwargs)
            console.print(f"[green]Natural language conversion enabled ({nl_provider})[/green]")
        except Exception as e:
            console.print(f"[yellow]Natural language conversion not available: {e}[/yellow]")
            console.print("[dim]You can still use the shell with regular commands[/dim]")
        
    def _load_aliases(self) -> Dict[str, str]:
        """Load shell aliases."""
        aliases = {
            'll': 'ls -la',
            'la': 'ls -a',
            'l': 'ls -l',
            '..': 'cd ..',
            '...': 'cd ../..',
            'g': 'git',
            'd': 'docker',
            'p': 'python',
            'cls': 'clear',
        }
        
        # Try to load user's aliases
        try:
            alias_file = Path("~/.aishell_aliases").expanduser()
            if alias_file.exists():
                with open(alias_file, 'r') as f:
                    user_aliases = json.load(f)
                    aliases.update(user_aliases)
        except Exception:
            pass
        
        return aliases
    
    def expand_alias(self, command: str) -> str:
        """Expand command aliases."""
        parts = shlex.split(command)
        if parts and parts[0] in self.aliases:
            parts[0] = self.aliases[parts[0]]
            return ' '.join(parts)
        return command
    
    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command and return exit code, stdout, stderr."""
        # Expand aliases
        command = self.expand_alias(command)
        
        # Handle built-in commands
        if command.startswith('cd '):
            return self._handle_cd(command)
        elif command == 'pwd':
            return 0, str(self.current_dir), ""
        elif command.startswith('export '):
            return self._handle_export(command)
        elif command == 'alias':
            return self._show_aliases()
        
        # Execute external command
        try:
            # Update environment with custom vars
            env = os.environ.copy()
            env.update(self.env_vars)
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.current_dir,
                env=env
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except Exception as e:
            return 1, "", str(e)
    
    def _handle_cd(self, command: str) -> Tuple[int, str, str]:
        """Handle cd command."""
        parts = shlex.split(command)
        if len(parts) == 1:
            # cd with no args goes to home
            new_dir = Path.home()
        else:
            new_dir = Path(parts[1]).expanduser()
        
        try:
            if not new_dir.is_absolute():
                new_dir = self.current_dir / new_dir
            new_dir = new_dir.resolve()
            
            if new_dir.exists() and new_dir.is_dir():
                self.current_dir = new_dir
                os.chdir(new_dir)
                return 0, str(new_dir), ""
            else:
                return 1, "", f"cd: {new_dir}: No such directory"
        except Exception as e:
            return 1, "", str(e)
    
    def _handle_export(self, command: str) -> Tuple[int, str, str]:
        """Handle export command."""
        try:
            parts = command.split('=', 1)
            if len(parts) == 2:
                var_name = parts[0].replace('export ', '').strip()
                var_value = parts[1].strip().strip('"\'')
                self.env_vars[var_name] = var_value
                os.environ[var_name] = var_value
                return 0, f"Exported {var_name}={var_value}", ""
            else:
                return 1, "", "export: Invalid syntax"
        except Exception as e:
            return 1, "", str(e)
    
    def _show_aliases(self) -> Tuple[int, str, str]:
        """Show all aliases."""
        output = []
        for alias, command in sorted(self.aliases.items()):
            output.append(f"{alias}='{command}'")
        return 0, '\n'.join(output), ""
    
    def format_prompt(self) -> str:
        """Format the shell prompt."""
        # Get current directory relative to home
        try:
            rel_path = self.current_dir.relative_to(Path.home())
            dir_str = f"~/{rel_path}"
        except ValueError:
            dir_str = str(self.current_dir)
        
        # Get git branch if in git repo
        git_branch = ""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.current_dir
            )
            if result.returncode == 0 and result.stdout.strip():
                git_branch = f" [git:{result.stdout.strip()}]"
        except Exception:
            pass
        
        return f"[bold blue]{dir_str}[/bold blue][green]{git_branch}[/green] [bold]$[/bold] "
    
    def run(self):
        """Run the interactive shell."""
        console.print(Panel(
            "[bold green]AIShell Interactive Mode[/bold green]\n"
            "Type 'help' for commands, 'exit' to quit",
            title="Welcome",
            expand=False
        ))
        
        # Set up readline for better input handling
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self._readline_completer)
        
        while True:
            try:
                # Get command with rich prompt
                command = Prompt.ask(self.format_prompt())
                
                if not command:
                    continue
                
                # Check for exit
                if command.lower() in ['exit', 'quit', 'q']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                
                # Check for help
                if command.lower() == 'help':
                    self._show_help()
                    continue
                
                # Check for natural language input (starts with ?)
                if command.startswith('?') and self.nl_converter:
                    nl_input = command[1:].strip()
                    if nl_input:
                        self._process_nl_command(nl_input)
                        continue
                
                # Add to history
                self.history.add(command)
                
                # Check for dangerous commands
                warning = self.suggester.check_dangerous(command)
                if warning:
                    console.print(f"[bold red]{warning}[/bold red]")
                    if not Prompt.ask("Continue anyway?", choices=["y", "n"], default="n") == "y":
                        continue
                
                # Execute command
                exit_code, stdout, stderr = self.execute_command(command)
                
                # Display output
                if stdout:
                    console.print(stdout, end='')
                if stderr:
                    console.print(f"[red]{stderr}[/red]", end='')
                
                # Show exit code if non-zero
                if exit_code != 0:
                    console.print(f"[dim]Exit code: {exit_code}[/dim]")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit[/yellow]")
            except EOFError:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    def _readline_completer(self, text: str, state: int) -> Optional[str]:
        """Readline completer for tab completion."""
        if state == 0:
            self.matches = self.suggester.suggest_completion(readline.get_line_buffer())
        
        try:
            return self.matches[state]
        except IndexError:
            return None
    
    def _process_nl_command(self, nl_input: str):
        """Process natural language command."""
        console.print(f"[dim]Converting: {nl_input}[/dim]")
        
        # Get context for conversion
        context = {
            'cwd': str(self.current_dir),
            'os': platform.system(),
            'shell': 'bash',  # We're simulating bash
        }
        
        with console.status("[bold green]Thinking..."):
            command = self.nl_converter.convert(nl_input, context)
        
        if command:
            console.print(f"[green]Command:[/green] {command}")
            
            # Ask for confirmation
            if Prompt.ask("Execute this command?", choices=["y", "n"], default="y") == "y":
                # Add to history
                self.history.add(command)
                
                # Execute command
                exit_code, stdout, stderr = self.execute_command(command)
                
                # Display output
                if stdout:
                    console.print(stdout, end='')
                if stderr:
                    console.print(f"[red]{stderr}[/red]", end='')
                
                # Show exit code if non-zero
                if exit_code != 0:
                    console.print(f"[dim]Exit code: {exit_code}[/dim]")
        else:
            console.print("[yellow]Could not convert to a command. Try rephrasing.[/yellow]")
    
    def _show_help(self):
        """Show help information."""
        help_table = Table(title="AIShell Commands", show_header=True)
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description", style="white")
        
        commands = [
            ("help", "Show this help message"),
            ("exit/quit", "Exit the shell"),
            ("cd <dir>", "Change directory"),
            ("pwd", "Print working directory"),
            ("export VAR=value", "Set environment variable"),
            ("alias", "Show all aliases"),
            ("history", "Show command history"),
            ("clear/cls", "Clear the screen"),
        ]
        
        # Add NL command if available
        if self.nl_converter:
            commands.append(("?<request>", "Convert natural language to command"))
        
        for cmd, desc in commands:
            help_table.add_row(cmd, desc)
        
        console.print(help_table)
        
        # Show NL examples if available
        if self.nl_converter:
            console.print("\n[bold]Natural Language Examples:[/bold]")
            examples = [
                "?list all python files",
                "?show disk usage",
                "?find large files",
                "?check running processes",
                "?create a backup folder",
            ]
            for ex in examples:
                console.print(f"  [cyan]{ex}[/cyan]")
        
        # Show aliases
        console.print("\n[bold]Available Aliases:[/bold]")
        for alias, command in sorted(self.aliases.items())[:10]:
            console.print(f"  [cyan]{alias}[/cyan] → {command}")
        if len(self.aliases) > 10:
            console.print(f"  [dim]... and {len(self.aliases) - 10} more[/dim]")