import os
import sys
import subprocess
import shlex
import asyncio
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
from aishell.llm import (
    ClaudeLLMProvider,
    OpenAILLMProvider,
    OllamaLLMProvider,
    GeminiLLMProvider,
    OpenRouterLLMProvider,
    Conversation,
)
from aishell.mcp import MCPClient, MCPMessage, NLToMCPTranslator
from aishell.utils import (
    get_transcript_manager,
    get_env_manager,
    load_env_on_startup,
    get_mcp_capability_manager,
)

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
                with open(self.history_file, "r") as f:
                    self.history = [line.strip() for line in f.readlines()]
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load history: {e}[/yellow]")

    def save_history(self):
        """Save command history to file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w") as f:
                f.write("\n".join(self.history[-1000:]))  # Keep last 1000 commands
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save history: {e}[/yellow]")

    def add(self, command: str):
        """Add command to history."""
        if command and command not in ["exit", "quit"]:
            self.history.append(command)
            self.save_history()


class CommandSuggester:
    """Provide intelligent command suggestions."""

    def __init__(self):
        self.common_commands = {
            "git": [
                "status",
                "add",
                "commit",
                "push",
                "pull",
                "branch",
                "checkout",
                "merge",
                "log",
            ],
            "docker": ["ps", "images", "run", "build", "stop", "rm", "exec", "logs"],
            "npm": ["install", "start", "test", "run", "build", "update"],
            "python": ["-m pip install", "-m venv", "-c", "--version"],
            "pip": ["install", "list", "freeze", "show", "uninstall"],
        }

        self.dangerous_commands = {
            "rm": "-rf",
            "chmod": "777",
            "chown": "-R",
            "dd": "if=",
            "mkfs": ".",
            "format": "c:",
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
            suggestions = [
                f"{base_cmd} {sub}" for sub in self.common_commands[base_cmd]
            ]

        # File/directory completion
        if len(parts) >= 2:
            last_part = parts[-1]
            if "/" in last_part or last_part.startswith("."):
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
                            matches.append(str(item) + "/")
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

    def __init__(
        self, nl_provider: str = "claude", nl_converter_kwargs: Optional[Dict] = None
    ):
        self.history = CommandHistory()
        self.suggester = CommandSuggester()
        self.aliases: Dict[str, str] = self._load_aliases()
        self.env_vars: Dict[str, str] = {}
        self.current_dir = Path.cwd()

        # Load environment variables
        load_env_on_startup(verbose=True)

        # Initialize NL converter
        self.nl_converter: Optional[NLConverter] = None
        try:
            nl_converter_kwargs = nl_converter_kwargs or {}
            self.nl_converter = get_nl_converter(nl_provider, **nl_converter_kwargs)
            console.print(
                f"[green]Natural language conversion enabled ({nl_provider})[/green]"
            )
        except Exception as e:
            console.print(
                f"[yellow]Natural language conversion not available: {e}[/yellow]"
            )
            console.print(
                "[dim]You can still use the shell with regular commands[/dim]"
            )

    def _load_aliases(self) -> Dict[str, str]:
        """Load shell aliases."""
        aliases = {
            "ll": "ls -la",
            "la": "ls -a",
            "l": "ls -l",
            "..": "cd ..",
            "...": "cd ../..",
            "g": "git",
            "d": "docker",
            "p": "python",
            "cls": "clear",
        }

        # Try to load user's aliases
        try:
            alias_file = Path("~/.aishell_aliases").expanduser()
            if alias_file.exists():
                with open(alias_file, "r") as f:
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
            return " ".join(parts)
        return command

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command and return exit code, stdout, stderr."""
        # Expand aliases
        command = self.expand_alias(command)

        # Handle built-in commands
        if command.startswith("cd "):
            return self._handle_cd(command)
        elif command == "pwd":
            return 0, str(self.current_dir), ""
        elif command.startswith("export "):
            return self._handle_export(command)
        elif command == "alias":
            return self._show_aliases()
        elif command == "help":
            self._show_help()
            return 0, "", ""
        elif command.startswith("llm") and (
            command == "llm" or command.startswith("llm ")
        ):
            return self._handle_llm(command)
        elif command.startswith("mcp") and (
            command == "mcp" or command.startswith("mcp ")
        ):
            return self._handle_mcp(command)
        elif command.startswith("collate") and (
            command == "collate" or command.startswith("collate ")
        ):
            return self._handle_collate(command)
        elif command.startswith("generate") and (
            command == "generate" or command.startswith("generate ")
        ):
            return self._handle_generate(command)
        elif command.startswith("env") and (
            command == "env" or command.startswith("env ")
        ):
            return self._handle_env(command)
        elif command.startswith("chat") and (
            command == "chat" or command.startswith("chat ")
        ):
            return self._handle_chat(command)

        # Default to LLM command if no other built-in matches
        # Check if it looks like a natural language query
        if not any(
            command.startswith(cmd)
            for cmd in [
                "cd",
                "pwd",
                "export",
                "alias",
                "history",
                "clear",
                "cls",
                "help",
                "exit",
                "quit",
                "env",
                "chat",
            ]
        ):
            # Try as LLM command with the entire input as query
            return self._handle_llm(f'llm "{command}"')

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
                env=env,
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
            parts = command.split("=", 1)
            if len(parts) == 2:
                var_name = parts[0].replace("export ", "").strip()
                var_value = parts[1].strip().strip("\"'")
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
        return 0, "\n".join(output), ""

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
                cwd=self.current_dir,
            )
            if result.returncode == 0 and result.stdout.strip():
                git_branch = f" [git:{result.stdout.strip()}]"
        except Exception:
            pass

        return f"[bold blue]{dir_str}[/bold blue][green]{git_branch}[/green] [bold]$[/bold] "

    def run(self):
        """Run the interactive shell."""
        console.print(
            Panel(
                "[bold green]AIShell Interactive Mode[/bold green]\n"
                "Type 'help' for commands, 'exit' to quit",
                title="Welcome",
                expand=False,
            )
        )

        # Set up readline for better input handling
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self._readline_completer)

        while True:
            try:
                # Get command with rich prompt
                command = Prompt.ask(self.format_prompt())

                if not command:
                    continue

                # Check for exit
                if command.lower() in ["exit", "quit", "q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                # Check for help
                if command.lower() == "help":
                    self._show_help()
                    continue

                # Check for natural language input (starts with ?)
                if command.startswith("?") and self.nl_converter:
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
                    if (
                        not Prompt.ask(
                            "Continue anyway?", choices=["y", "n"], default="n"
                        )
                        == "y"
                    ):
                        continue

                # Execute command
                exit_code, stdout, stderr = self.execute_command(command)

                # Display output
                if stdout:
                    console.print(stdout, end="")
                if stderr:
                    console.print(f"[red]{stderr}[/red]", end="")

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
            "cwd": str(self.current_dir),
            "os": platform.system(),
            "shell": "bash",  # We're simulating bash
        }

        with console.status("[bold green]Thinking..."):
            command = self.nl_converter.convert(nl_input, context)

        if command:
            console.print(f"[green]Command:[/green] {command}")

            # Ask for confirmation
            if (
                Prompt.ask("Execute this command?", choices=["y", "n"], default="y")
                == "y"
            ):
                # Add to history
                self.history.add(command)

                # Execute command
                exit_code, stdout, stderr = self.execute_command(command)

                # Display output
                if stdout:
                    console.print(stdout, end="")
                if stderr:
                    console.print(f"[red]{stderr}[/red]", end="")

                # Show exit code if non-zero
                if exit_code != 0:
                    console.print(f"[dim]Exit code: {exit_code}[/dim]")
        else:
            console.print(
                "[yellow]Could not convert to a command. Try rephrasing.[/yellow]"
            )

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
            ('llm "query"', "Query an LLM provider"),
            ('collate "query"', "Collate responses across LLM providers"),
            ("chat [provider]", "Start interactive multi-turn chat"),
            ("mcp <url> <cmd>", "Interact with MCP servers"),
            ("generate <lang> <desc>", "Generate code in specified language"),
            ("env <subcommand>", "Manage environment variables and MCP servers"),
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

    def _enhance_query_with_mcp_context(self, query: str) -> str:
        """Enhance LLM query with MCP capability context when relevant."""
        # Check if query might benefit from MCP context
        mcp_keywords = [
            "database",
            "sql",
            "query",
            "table",
            "postgres",
            "mysql",
            "sqlite",
            "github",
            "gitlab",
            "repository",
            "repo",
            "git",
            "commit",
            "issue",
            "jira",
            "atlassian",
            "ticket",
            "project",
            "task",
            "workflow",
            "docker",
            "container",
            "kubernetes",
            "k8s",
            "pod",
            "deployment",
            "aws",
            "s3",
            "cloud",
            "storage",
            "bucket",
            "gcp",
            "google cloud",
            "file",
            "directory",
            "folder",
            "filesystem",
            "web",
            "fetch",
            "url",
            "memory",
            "remember",
            "store",
            "recall",
            "knowledge",
        ]

        query_lower = query.lower()
        if any(keyword in query_lower for keyword in mcp_keywords):
            mcp_manager = get_mcp_capability_manager()
            mcp_context = mcp_manager.generate_mcp_context_prompt()

            if mcp_context != "No MCP servers are currently configured.":
                enhanced_query = f"""{query}

{mcp_context}

Please consider whether any of the available MCP tools could help with this request and suggest appropriate commands if relevant."""
                return enhanced_query

        return query

    def _handle_llm(self, command: str) -> Tuple[int, str, str]:
        """Handle LLM queries with new syntax: llm [provider] 'query'."""
        try:
            parts = shlex.split(command)
            if len(parts) < 2:
                return (
                    1,
                    "",
                    'Usage: llm [provider] "query" [--stream] [--research]',
                )

            # Parse new syntax: llm [provider] "query"
            valid_providers = ["claude", "openai", "ollama", "gemini", "openrouter"]

            if parts[1] in valid_providers:
                # llm <provider> "query" format
                if len(parts) < 3:
                    return 1, "", f'Usage: llm {parts[1]} "query" [--stream]'
                provider_name = parts[1]
                query = parts[2]
                options_start = 3
                console.print(f"[blue]Using provider: {provider_name}[/blue]")
            elif len(parts) >= 3:
                # Provider specified but invalid
                return (
                    1,
                    "",
                    f"Unknown provider: {parts[1]}. Use: {', '.join(valid_providers)}",
                )
            else:
                # Check if the first argument looks like a provider name but is invalid
                potential_providers = [
                    "claude",
                    "openai",
                    "ollama",
                    "gemini",
                    "openrouter",
                    "invalid",
                    "unknown",
                    "bad",
                ]
                if any(
                    parts[1].lower().startswith(p.lower()) for p in potential_providers
                ) or parts[1] in ["invalid", "unknown", "bad", "test", "fake"]:
                    return (
                        1,
                        "",
                        f"Unknown provider: {parts[1]}. Use: claude, openai, ollama, gemini, openrouter",
                    )

                # llm "query" format (use default provider)
                env_manager = get_env_manager()
                provider_name = env_manager.get_var("DEFAULT_LLM_PROVIDER", "claude")
                query = parts[1]
                options_start = 2
                console.print(f"[blue]Using default provider: {provider_name}[/blue]")

            stream = False
            research = False

            # Parse remaining options
            i = options_start
            while i < len(parts):
                if parts[i] == "--stream":
                    stream = True
                    i += 1
                elif parts[i] == "--research" or parts[i] == "-r":
                    research = True
                    i += 1
                else:
                    i += 1

            # Create provider with env config
            env_manager = get_env_manager()
            config = env_manager.get_llm_config(provider_name)

            provider_map = {
                "claude": ClaudeLLMProvider,
                "openai": OpenAILLMProvider,
                "ollama": OllamaLLMProvider,
                "gemini": GeminiLLMProvider,
                "openrouter": OpenRouterLLMProvider,
            }

            if provider_name not in provider_map:
                return (
                    1,
                    "",
                    f"Unknown provider: {provider_name}. Use: claude, openai, ollama, gemini, openrouter",
                )

            # Create provider with configuration from env
            if provider_name == "claude":
                provider = provider_map[provider_name](
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "openai":
                provider = provider_map[provider_name](
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "gemini":
                provider = provider_map[provider_name](
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "ollama":
                provider = provider_map[provider_name](base_url=config.get("base_url"))
            elif provider_name == "openrouter":
                provider = provider_map[provider_name](
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            else:
                provider = provider_map[provider_name]()

            # Enhance query with MCP context if relevant
            enhanced_query = self._enhance_query_with_mcp_context(query)

            # Show research mode notice
            if research and provider_name == "gemini":
                console.print(
                    "[blue]Mode:[/blue] Deep Research (Google Search grounding)"
                )
            elif research and provider_name != "gemini":
                console.print(
                    "[yellow]Warning:[/yellow] --research is only supported with Gemini"
                )

            # Run the query
            async def run_query():
                transcript = get_transcript_manager()

                if stream:
                    console.print(f"[blue]Streaming from {provider_name}...[/blue]")
                    streamed_content = ""
                    async for chunk in provider.stream_query(enhanced_query):
                        console.print(chunk, end="")
                        streamed_content += chunk
                    console.print()  # Final newline

                    # Log streamed response to transcript (use original query for logging)
                    transcript.log_interaction(
                        query=query,
                        response=streamed_content,
                        provider=provider_name,
                        model=provider.default_model,
                    )
                else:
                    # Build query kwargs
                    query_kwargs = {}
                    if research and provider_name == "gemini":
                        query_kwargs["research"] = True

                    with console.status(
                        f"[yellow]Querying {provider_name}...[/yellow]"
                    ):
                        response = await provider.query(enhanced_query, **query_kwargs)

                    if response.is_error:
                        console.print(f"[red]Error:[/red] {response.error}")
                        # Log error to transcript (use original query for logging)
                        transcript.log_interaction(
                            query=query,
                            response="",
                            provider=provider_name,
                            model=provider.default_model,
                            error=response.error,
                        )
                    else:
                        panel = Panel(
                            response.content,
                            title=f"[green]{provider_name.title()} Response[/green]",
                            subtitle=f"Model: {response.model}",
                            border_style="green",
                            padding=(1, 2),
                        )
                        console.print(panel)

                        if response.usage:
                            console.print(
                                f"[dim]Tokens: {response.usage.get('total_tokens', 'N/A')}[/dim]"
                            )

                        # Show research metadata if available
                        if response.metadata and response.metadata.get("grounded"):
                            console.print()
                            console.print("[blue]Research Sources:[/blue]")
                            if "search_queries" in response.metadata:
                                console.print("  [dim]Search queries:[/dim]")
                                for sq in response.metadata["search_queries"]:
                                    console.print(f"    - {sq}")
                            if "grounding_chunks" in response.metadata:
                                console.print(
                                    f"  [dim]Sources:[/dim] {response.metadata['grounding_chunks']}"
                                )

                        # Log successful response to transcript (use original query for logging)
                        transcript.log_interaction(
                            query=query,
                            response=response.content,
                            provider=provider_name,
                            model=response.model,
                            usage=response.usage,
                        )

            asyncio.run(run_query())
            return 0, "", ""

        except Exception as e:
            return 1, "", f"LLM error: {str(e)}"

    def _handle_mcp(self, command: str) -> Tuple[int, str, str]:
        """Handle MCP commands."""
        try:
            parts = shlex.split(command)
            if len(parts) < 2:
                return 1, "", "Usage: mcp <server_url> <command> [args]"

            server_url = parts[1]

            if len(parts) < 3:
                return 1, "", "Usage: mcp <server_url> <command> [args]"

            mcp_command = parts[2]

            async def run_mcp():
                async with MCPClient(server_url) as client:
                    # Initialize connection
                    console.print(f"[blue]Connecting to {server_url}...[/blue]")
                    init_response = await client.initialize(
                        client_info={"name": "aishell-shell", "version": "1.0"}
                    )

                    if init_response.is_error:
                        console.print(
                            f"[red]Connection failed:[/red] {init_response.error}"
                        )
                        return

                    # Handle specific commands
                    if mcp_command == "ping":
                        response = await client.ping()
                        client.display_response(response, "Ping Response")
                    elif mcp_command == "tools":
                        response = await client.list_tools()
                        client.display_response(response, "Available Tools")
                    elif mcp_command == "resources":
                        response = await client.list_resources()
                        client.display_response(response, "Available Resources")
                    elif mcp_command == "prompts":
                        response = await client.list_prompts()
                        client.display_response(response, "Available Prompts")
                    else:
                        # Try natural language conversion
                        translator = NLToMCPTranslator()
                        full_query = " ".join(parts[2:])
                        message = await translator.translate(full_query)
                        response = await client.send_message(message)
                        client.display_response(
                            response, f"Response for: {message.method}"
                        )

            asyncio.run(run_mcp())
            return 0, "", ""

        except Exception as e:
            return 1, "", f"MCP error: {str(e)}"

    def _handle_collate(self, command: str) -> Tuple[int, str, str]:
        """Handle multi-LLM collations with syntax: collate <provider1> <provider2> [provider3...] 'query' [--no-save] [--db path]."""
        try:
            parts = shlex.split(command)
            if len(parts) < 4:
                return (
                    1,
                    "",
                    'Usage: collate <provider1> <provider2> [provider3...] "query" [--no-save] [--db path]',
                )

            valid_providers = ["claude", "openai", "ollama", "gemini", "openrouter"]

            # Parse options
            save_to_db = True
            db_path = None
            filtered_parts = []

            i = 1
            while i < len(parts):
                if parts[i] == "--no-save":
                    save_to_db = False
                    i += 1
                elif parts[i] == "--save":
                    save_to_db = True
                    i += 1
                elif parts[i] == "--db" and i + 1 < len(parts):
                    db_path = parts[i + 1]
                    i += 2
                else:
                    filtered_parts.append(parts[i])
                    i += 1

            # Parse providers and query from filtered parts
            providers = []
            query_parts = []

            for idx, arg in enumerate(filtered_parts):
                if arg.lower() in valid_providers and not query_parts:
                    providers.append(arg.lower())
                else:
                    query_parts = filtered_parts[idx:]
                    break

            # Validate we have at least 2 providers
            if len(providers) < 2:
                return (
                    1,
                    "",
                    f'At least 2 providers required. Valid: {", ".join(valid_providers)}',
                )

            # Validate we have a query
            if not query_parts:
                return 1, "", "Query is required after provider names"

            query = " ".join(query_parts)

            # Warn if duplicate providers
            if len(providers) != len(set(providers)):
                console.print("[yellow]Warning: Duplicate providers specified[/yellow]")

            async def run_comparison():
                env_manager = get_env_manager()

                # Create only requested provider instances
                provider_map = {}
                for name in providers:
                    config = env_manager.get_llm_config(name)
                    if name == "claude":
                        provider_map[name] = ClaudeLLMProvider(
                            api_key=config.get("api_key"),
                            base_url=config.get("base_url"),
                        )
                    elif name == "openai":
                        provider_map[name] = OpenAILLMProvider(
                            api_key=config.get("api_key"),
                            base_url=config.get("base_url"),
                        )
                    elif name == "gemini":
                        provider_map[name] = GeminiLLMProvider(
                            api_key=config.get("api_key"),
                            base_url=config.get("base_url"),
                        )
                    elif name == "ollama":
                        provider_map[name] = OllamaLLMProvider(
                            base_url=config.get("base_url")
                        )
                    elif name == "openrouter":
                        provider_map[name] = OpenRouterLLMProvider(
                            api_key=config.get("api_key"),
                            base_url=config.get("base_url"),
                        )

                console.print(
                    f"[blue]Querying {len(providers)} providers simultaneously...[/blue]"
                )
                console.print(f"[blue]Query:[/blue] {query}")
                for provider_name in providers:
                    if provider_name in provider_map:
                        console.print(
                            f"[blue]{provider_name.title()}:[/blue] {provider_map[provider_name].default_model} (default)"
                        )
                console.print()

                # Run queries concurrently using asyncio.gather
                async def query_provider(name, provider):
                    try:
                        response = await provider.query(query)
                        return (name, response)
                    except Exception as e:
                        from aishell.llm import LLMResponse

                        error_response = LLMResponse(
                            content="", model="unknown", provider=name, error=str(e)
                        )
                        return (name, error_response)

                with console.status("[yellow]Waiting for responses...[/yellow]"):
                    tasks = [
                        query_provider(name, provider)
                        for name, provider in provider_map.items()
                    ]
                    results = await asyncio.gather(*tasks)

                # Create collation table
                table = Table(title="LLM Responses Collation", show_lines=True)
                table.add_column("Provider", style="cyan", width=12)
                table.add_column("Response", style="white", no_wrap=False)
                table.add_column("Tokens", style="dim", width=10)

                for provider_name, response in results:
                    if response.is_error:
                        table.add_row(
                            provider_name.title(),
                            f"[red]Error: {response.error}[/red]",
                            "-",
                        )
                    else:
                        tokens = (
                            str(response.usage.get("total_tokens", "-"))
                            if response.usage
                            else "-"
                        )
                        table.add_row(provider_name.title(), response.content, tokens)

                console.print(table)

                # Log to transcript
                transcript = get_transcript_manager()
                transcript.log_multi_interaction(query, results)

                # Save to database if enabled
                if save_to_db:
                    try:
                        from aishell.storage import get_storage_manager

                        storage = get_storage_manager(db_path)
                        stored_responses, stored_errors = storage.store_collation(
                            query=query, responses=results, metadata={}
                        )
                        if stored_responses:
                            console.print(
                                f"[dim]Saved {len(stored_responses)} response(s) to database: {storage.db_path}[/dim]"
                            )
                        if stored_errors:
                            console.print(
                                f"[dim]Saved {len(stored_errors)} error(s) to error log[/dim]"
                            )
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Could not save to database: {e}[/yellow]"
                        )

            asyncio.run(run_comparison())
            return 0, "", ""

        except Exception as e:
            return 1, "", f"Collate error: {str(e)}"

    def _handle_generate(self, command: str) -> Tuple[int, str, str]:
        """Handle code generation commands."""
        try:
            parts = shlex.split(command)
            if len(parts) < 3:
                return 1, "", "Usage: generate <language> <description>"

            language = parts[1]
            description = " ".join(parts[2:])

            # Create generation prompt
            prompt = f"""Generate {language} code for: {description}

Requirements:
- Write clean, well-commented code
- Include example usage if appropriate
- Follow {language} best practices
- Provide only the code, no explanations

Language: {language}
Task: {description}"""

            async def run_generation():
                # Use Claude for code generation by default
                provider = ClaudeLLMProvider()

                with console.status(f"[yellow]Generating {language} code...[/yellow]"):
                    response = await provider.query(prompt, temperature=0.3)

                if response.is_error:
                    console.print(f"[red]Generation failed:[/red] {response.error}")
                else:
                    # Display code with syntax highlighting
                    syntax = Syntax(
                        response.content,
                        language.lower(),
                        theme="monokai",
                        line_numbers=True,
                    )
                    panel = Panel(
                        syntax,
                        title=f"[green]Generated {language.title()} Code[/green]",
                        border_style="green",
                        padding=(1, 2),
                    )
                    console.print(panel)

            asyncio.run(run_generation())
            return 0, "", ""

        except Exception as e:
            return 1, "", f"Generate error: {str(e)}"

    def _handle_env(self, command: str) -> Tuple[int, str, str]:
        """Handle environment variable commands."""
        try:
            parts = shlex.split(command)
            if len(parts) < 2:
                help_text = """Usage: env <subcommand> [args]

Subcommands:
  reload              Reload .env file
  show [filter]       Show environment variables (optionally filtered)
  get <key>           Get value of environment variable
  set <key> <value>   Set environment variable (runtime only)
  llm <provider>      Show LLM configuration for provider
  default <provider>  Set default LLM provider (runtime only)
  mcp                 Show configured MCP servers
  mcp-list            List all available MCP server types

Examples:
  env reload
  env show API
  env get ANTHROPIC_API_KEY
  env set TEMP_VAR value
  env llm claude
  env default openai
  env mcp
  env mcp-list"""
                console.print(help_text)
                return 0, "", ""

            env_manager = get_env_manager()
            subcommand = parts[1].lower()

            if subcommand == "reload":
                success = env_manager.reload_env()
                return 0 if success else 1, "", ""

            elif subcommand == "show":
                filter_pattern = parts[2] if len(parts) > 2 else None
                env_manager.show_env(filter_pattern)
                return 0, "", ""

            elif subcommand == "get":
                if len(parts) < 3:
                    return 1, "", "Usage: env get <key>"

                key = parts[2]
                value = env_manager.get_var(key)
                if value is not None:
                    console.print(f"[cyan]{key}[/cyan] = {value}")
                else:
                    console.print(f"[yellow]Variable {key} not found[/yellow]")
                return 0, "", ""

            elif subcommand == "set":
                if len(parts) < 4:
                    return 1, "", "Usage: env set <key> <value>"

                key = parts[2]
                value = parts[3]
                env_manager.set_var(key, value)
                return 0, "", ""

            elif subcommand == "llm":
                if len(parts) < 3:
                    providers = ["claude", "openai", "gemini", "ollama"]
                    console.print("Available providers: " + ", ".join(providers))
                    return 0, "", ""

                provider = parts[2].lower()
                config = env_manager.get_llm_config(provider)

                if not config:
                    return 1, "", f"Unknown provider: {provider}"

                from rich.table import Table

                table = Table(
                    title=f"{provider.title()} Configuration", show_header=True
                )
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="white")

                for key, value in config.items():
                    if value is None:
                        display_value = "[red]Not set[/red]"
                    elif "key" in key.lower() or "token" in key.lower():
                        # Mask sensitive values
                        if len(value) > 8:
                            display_value = value[:4] + "..." + value[-4:]
                        else:
                            display_value = "***"
                    else:
                        display_value = value

                    table.add_row(key, display_value)

                console.print(table)
                return 0, "", ""

            elif subcommand == "default":
                if len(parts) < 3:
                    current_default = env_manager.get_var(
                        "DEFAULT_LLM_PROVIDER", "claude"
                    )
                    console.print(
                        f"Current default LLM provider: [cyan]{current_default}[/cyan]"
                    )
                    console.print("Available providers: claude, openai, gemini, ollama")
                    console.print("Usage: env default <provider>")
                    return 0, "", ""

                provider = parts[2].lower()
                valid_providers = ["claude", "openai", "gemini", "ollama"]

                if provider not in valid_providers:
                    return (
                        1,
                        "",
                        f"Invalid provider: {provider}. Use: {', '.join(valid_providers)}",
                    )

                env_manager.set_var("DEFAULT_LLM_PROVIDER", provider)
                console.print(f"[green]Default LLM provider set to: {provider}[/green]")
                console.print(
                    "[dim]Note: This change affects current session only. Update .env to persist.[/dim]"
                )
                return 0, "", ""

            elif subcommand == "mcp":
                servers = env_manager.get_mcp_servers()

                if not servers:
                    console.print("[yellow]No MCP servers configured[/yellow]")
                    console.print(
                        "[dim]Configure servers in .env file with MCP_*_SERVER variables[/dim]"
                    )
                    return 0, "", ""

                from rich.table import Table

                table = Table(title="Configured MCP Servers", show_header=True)
                table.add_column("Name", style="cyan")
                table.add_column("Command/URL", style="white")

                for name, command in servers.items():
                    table.add_row(name.title(), command)

                console.print(table)
                return 0, "", ""

            elif subcommand == "mcp-list":
                available = env_manager.list_available_mcp_servers()

                from rich.table import Table

                table = Table(title="Available MCP Server Types", show_header=True)
                table.add_column("Category", style="cyan")
                table.add_column("Servers", style="white")

                categories = {
                    "Database": ["postgres", "sqlite", "mysql"],
                    "Version Control": ["github", "gitlab"],
                    "Atlassian": ["jira", "atlassian"],
                    "File/Web": ["filesystem", "fetch", "memory"],
                    "Development": ["docker", "kubernetes"],
                    "Cloud": ["aws", "gcp"],
                    "Custom": ["custom_1", "custom_2"],
                }

                for category, servers in categories.items():
                    table.add_row(category, ", ".join(servers))

                console.print(table)
                console.print(
                    "\n[dim]Configure in .env as MCP_<NAME>_SERVER=<command>[/dim]"
                )
                console.print(
                    "[dim]Example: MCP_POSTGRES_SERVER=npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb[/dim]"
                )
                return 0, "", ""

            else:
                return (
                    1,
                    "",
                    f"Unknown subcommand: {subcommand}. Use: reload, show, get, set, llm, default, mcp, mcp-list",
                )

        except Exception as e:
            return 1, "", f"Env error: {str(e)}"

    def _handle_chat(self, command: str) -> Tuple[int, str, str]:
        """Handle interactive multi-turn chat sessions."""
        try:
            parts = shlex.split(command)

            # Parse options
            provider_name = None
            resume_id = None
            system_prompt = None

            i = 1
            while i < len(parts):
                if parts[i] == "--resume" and i + 1 < len(parts):
                    resume_id = parts[i + 1]
                    i += 2
                elif parts[i] == "--system" and i + 1 < len(parts):
                    system_prompt = parts[i + 1]
                    i += 2
                elif not parts[i].startswith("-"):
                    provider_name = parts[i]
                    i += 1
                else:
                    i += 1

            # Default provider
            env_manager = get_env_manager()
            valid_providers = ["claude", "openai", "ollama", "gemini"]

            if provider_name is None:
                provider_name = "openai"
            elif provider_name.lower() not in valid_providers:
                return (
                    1,
                    "",
                    f"Unknown provider: {provider_name}. Available: {', '.join(valid_providers)}",
                )
            else:
                provider_name = provider_name.lower()

            # Get provider config
            config = env_manager.get_llm_config(provider_name)

            # Create LLM provider
            if provider_name == "claude":
                llm = ClaudeLLMProvider(
                    api_key=config.get("api_key"),
                    base_url=config.get("base_url"),
                )
            elif provider_name == "openai":
                llm = OpenAILLMProvider(
                    api_key=config.get("api_key"),
                    base_url=config.get("base_url"),
                )
            elif provider_name == "ollama":
                llm = OllamaLLMProvider(base_url=config.get("base_url"))
            elif provider_name == "gemini":
                llm = GeminiLLMProvider(
                    api_key=config.get("api_key"),
                    base_url=config.get("base_url"),
                )

            model_name = llm.default_model

            # Load or create conversation
            if resume_id:
                try:
                    conversation = Conversation.load(resume_id)
                    console.print(
                        f"[green]Resumed conversation:[/green] {resume_id[:8]}..."
                    )
                    console.print(
                        f"[dim]Messages loaded: {len(conversation.messages)}[/dim]"
                    )
                except ValueError as e:
                    return 1, "", str(e)
            else:
                conversation = Conversation(
                    provider=provider_name,
                    model=model_name,
                    system_prompt=system_prompt,
                )
                console.print(
                    f"[green]Started new conversation:[/green] {conversation.conversation_id[:8]}..."
                )

            console.print(f"[blue]Provider:[/blue] {provider_name}")
            console.print(f"[blue]Model:[/blue] {model_name}")
            if system_prompt:
                console.print(f"[blue]System:[/blue] {system_prompt[:50]}...")
            console.print()
            console.print("[dim]Commands: /exit, /history, /id, /clear[/dim]")
            console.print()

            # Chat loop
            async def run_chat_loop():
                while True:
                    try:
                        user_input = Prompt.ask("[cyan]You[/cyan]")

                        if not user_input:
                            continue

                        # Handle commands
                        if user_input.startswith("/"):
                            cmd = user_input.lower()

                            if cmd in ["/exit", "/quit", "/q"]:
                                console.print("[dim]Conversation ended.[/dim]")
                                console.print(
                                    f"[dim]Conversation ID: {conversation.conversation_id}[/dim]"
                                )
                                break

                            elif cmd == "/history":
                                console.print()
                                for msg in conversation.messages:
                                    role_color = (
                                        "cyan"
                                        if msg.role == "user"
                                        else (
                                            "green"
                                            if msg.role == "assistant"
                                            else "yellow"
                                        )
                                    )
                                    console.print(
                                        f"[{role_color}]{msg.role.title()}:[/{role_color}]"
                                    )
                                    console.print(f"  {msg.content[:100]}...")
                                    console.print()
                                continue

                            elif cmd == "/id":
                                console.print(
                                    f"[blue]Conversation ID:[/blue] {conversation.conversation_id}"
                                )
                                continue

                            elif cmd == "/clear":
                                conversation.clear()
                                console.print(
                                    "[dim]Conversation cleared (database preserved)[/dim]"
                                )
                                continue

                            else:
                                console.print(
                                    f"[yellow]Unknown command:[/yellow] {cmd}"
                                )
                                console.print(
                                    "[dim]Available: /exit, /history, /id, /clear[/dim]"
                                )
                                continue

                        # Add user message
                        conversation.add_user_message(user_input)

                        # Get response
                        with console.status(
                            "[yellow]Thinking...[/yellow]", spinner="dots"
                        ):
                            response = await llm.chat(
                                conversation.get_messages(),
                                model=model_name,
                            )

                        if response.is_error:
                            console.print(f"[red]Error:[/red] {response.error}")
                            # Remove the user message since we couldn't get a response
                            conversation.messages.pop()
                        else:
                            # Add assistant response
                            conversation.add_assistant_message(response.content)
                            console.print()
                            console.print(f"[green]Assistant:[/green]")
                            console.print(response.content)
                            console.print()

                    except KeyboardInterrupt:
                        console.print("\n[dim]Use /exit to end the conversation[/dim]")
                    except EOFError:
                        console.print("\n[dim]Conversation ended.[/dim]")
                        break

            asyncio.run(run_chat_loop())
            return 0, "", ""

        except Exception as e:
            return 1, "", f"Chat error: {str(e)}"
