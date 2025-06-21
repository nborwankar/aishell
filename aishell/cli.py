import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from aishell import __version__
from aishell.search.web_search import perform_web_search
from aishell.shell.intelligent_shell import IntelligentShell
from aishell.search.file_search import MacOSFileSearcher, display_results
from aishell.llm import (
    ClaudeLLMProvider,
    OpenAILLMProvider,
    OllamaLLMProvider,
    GeminiLLMProvider,
)
from aishell.mcp import MCPClient, MCPMessage, NLToMCPTranslator
from aishell.utils import get_transcript_manager

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="aishell")
@click.pass_context
def main(ctx):
    """AIShell - An intelligent command line tool."""
    ctx.ensure_object(dict)


@main.command()
@click.argument('query', nargs=-1, required=True)
@click.option('--limit', '-l', default=10, help='Number of results to return')
@click.option('--engine', '-e', default='google', type=click.Choice(['google', 'duckduckgo']), help='Search engine to use')
@click.option('--show-browser', '-s', is_flag=True, help='Show browser window (disable headless mode)')
def search(query, limit, engine, show_browser):
    """Web search from the command line using Playwright and headless Chrome."""
    query_str = ' '.join(query)
    headless = not show_browser
    
    # Run the async search function
    asyncio.run(perform_web_search(query_str, limit=limit, engine=engine, headless=headless))


@main.command()
@click.argument('pattern', required=True)
@click.option('--path', '-p', default='.', help='Path to search in')
@click.option('--content', '-c', help='Search for content within files')
@click.option('--type', '-t', help='File type filter (image, video, audio, text, code, etc.)')
@click.option('--size', '-s', help='Size filter (e.g., ">1MB", "<500KB")')
@click.option('--date', '-d', help='Date filter (e.g., "today", "last week", "yesterday")')
@click.option('--limit', '-l', default=100, help='Maximum number of results')
@click.option('--no-spotlight', is_flag=True, help='Disable Spotlight and use find instead')
@click.option('--tree', is_flag=True, help='Display results in tree format')
def find(pattern, path, content, type, size, date, limit, no_spotlight, tree):
    """Search for files in the filesystem using macOS native tools.
    
    Uses Spotlight (mdfind) by default for fast searching, with fallback to BSD find.
    
    Examples:
        aishell find "*.py"                    # Find all Python files
        aishell find "config" --content "api"  # Find files named 'config' containing 'api'
        aishell find "*" --type image          # Find all images
        aishell find "*" --size ">1MB"         # Find files larger than 1MB
        aishell find "*" --date today          # Find files modified today
    """
    searcher = MacOSFileSearcher()
    
    console.print(f"[blue]Searching for:[/blue] {pattern}")
    if content:
        console.print(f"[blue]With content:[/blue] {content}")
    if type:
        console.print(f"[blue]File type:[/blue] {type}")
    if size:
        console.print(f"[blue]Size filter:[/blue] {size}")
    if date:
        console.print(f"[blue]Date filter:[/blue] {date}")
    
    results = searcher.search_files(
        pattern=pattern,
        path=path,
        content_pattern=content,
        file_type=type,
        size_filter=size,
        date_filter=date,
        max_results=limit,
        use_spotlight=not no_spotlight
    )
    
    if tree:
        from aishell.search.file_search import create_tree_view
        tree_view = create_tree_view(results, path)
        console.print(tree_view)
    else:
        display_results(results, show_content=bool(content))


@main.command()
@click.argument('query', nargs=-1, required=True)
@click.option('--limit', '-l', default=20, help='Maximum number of results')
def spotlight(query, limit):
    """Quick Spotlight search for any query.
    
    Uses macOS Spotlight to search for files, content, and metadata.
    
    Examples:
        aishell spotlight python tutorial
        aishell spotlight "machine learning"
        aishell spotlight kind:image
    """
    searcher = MacOSFileSearcher()
    query_str = ' '.join(query)
    
    console.print(f"[blue]Spotlight search:[/blue] {query_str}")
    
    results = searcher.quick_search(query_str, max_results=limit)
    display_results(results, show_content=False)


@main.command()
@click.option('--no-history', is_flag=True, help='Disable command history')
@click.option('--config', type=click.Path(), help='Path to configuration file')
@click.option('--nl-provider', type=click.Choice(['claude', 'ollama', 'mock', 'none']), default='claude', help='Natural language provider')
@click.option('--ollama-model', default='llama2', help='Ollama model to use (if using ollama provider)')
@click.option('--anthropic-api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key for Claude')
def shell(no_history, config, nl_provider, ollama_model, anthropic_api_key):
    """Start an intelligent shell session with enhanced features.
    
    Features:
    - Command history and suggestions
    - Aliases and tab completion
    - Git branch awareness
    - Safety warnings for dangerous commands
    - Built-in commands (cd, export, alias)
    - Natural language to command conversion (use ? prefix)
    
    Examples:
        aishell shell                    # Use Claude for NL conversion
        aishell shell --nl-provider ollama  # Use local Ollama
        aishell shell --nl-provider none    # Disable NL conversion
    """
    # Prepare NL converter kwargs
    nl_kwargs = {}
    if nl_provider == 'ollama':
        nl_kwargs['model'] = ollama_model
    elif nl_provider == 'claude' and anthropic_api_key:
        nl_kwargs['api_key'] = anthropic_api_key
    
    # Create shell instance
    if nl_provider == 'none':
        shell = IntelligentShell(nl_provider='mock', nl_converter_kwargs=None)
        shell.nl_converter = None  # Disable NL conversion
    else:
        shell = IntelligentShell(nl_provider=nl_provider, nl_converter_kwargs=nl_kwargs)
    
    if no_history:
        shell.history = None
    
    shell.run()


@main.command()
@click.argument('query', nargs=-1, required=True)
@click.option('--provider', '-p', type=click.Choice(['claude', 'openai', 'ollama', 'gemini']), default='claude', help='LLM provider to use')
@click.option('--model', '-m', help='Model to use (provider-specific)')
@click.option('--temperature', '-t', default=0.7, help='Temperature for sampling')
@click.option('--max-tokens', default=None, type=int, help='Maximum tokens to generate')
@click.option('--stream', '-s', is_flag=True, help='Stream the response')
@click.option('--api-key', envvar='LLM_API_KEY', help='API key for the provider')
@click.option('--ollama-url', default='http://localhost:11434', help='Ollama API URL')
@click.option('--openai-url', help='OpenAI-compatible API URL')
def query(query, provider, model, temperature, max_tokens, stream, api_key, ollama_url, openai_url):
    """Send a query to an LLM provider.
    
    Examples:
        aishell query "What is the capital of France?"
        aishell query "Explain quantum computing" --provider openai --model gpt-4
        aishell query "Write a Python function" --provider ollama --stream
        aishell query "Tell me a joke" --provider gemini
    """
    query_str = ' '.join(query)
    
    async def run_query():
        transcript = get_transcript_manager()
        
        # Create the appropriate provider
        if provider == 'claude':
            llm = ClaudeLLMProvider(api_key=api_key)
        elif provider == 'openai':
            llm = OpenAILLMProvider(api_key=api_key, base_url=openai_url)
        elif provider == 'ollama':
            llm = OllamaLLMProvider(base_url=ollama_url)
        elif provider == 'gemini':
            llm = GeminiLLMProvider(api_key=api_key)
        
        console.print(f"[blue]Provider:[/blue] {provider}")
        if model:
            console.print(f"[blue]Model:[/blue] {model}")
        else:
            console.print(f"[blue]Model:[/blue] {llm.default_model} (default)")
        console.print()
        
        if stream:
            # Streaming response
            streamed_content = ""
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                first_chunk = True
                async for chunk in llm.stream_query(
                    query_str,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    if first_chunk:
                        console.print()  # Clear the status
                        first_chunk = False
                    console.print(chunk, end="")
                    streamed_content += chunk
            console.print()  # Final newline
            
            # Log streamed response to transcript
            transcript.log_interaction(
                query=query_str,
                response=streamed_content,
                provider=provider,
                model=model or llm.default_model
            )
        else:
            # Regular response
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                response = await llm.query(
                    query_str,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            if response.is_error:
                console.print(f"[red]Error:[/red] {response.error}")
                # Log error to transcript
                transcript.log_interaction(
                    query=query_str,
                    response=f"ERROR: {response.error}",
                    provider=provider,
                    model=model or "unknown"
                )
            else:
                # Display response in a nice panel
                panel = Panel(
                    response.content,
                    title=f"[green]{response.provider.title()} Response[/green]",
                    subtitle=f"Model: {response.model}",
                    border_style="green",
                    padding=(1, 2)
                )
                console.print(panel)
                
                # Show usage stats if available
                if response.usage:
                    console.print()
                    console.print("[dim]Usage:[/dim]")
                    for key, value in response.usage.items():
                        console.print(f"  [dim]{key}:[/dim] {value}")
                
                # Log successful response to transcript
                transcript.log_interaction(
                    query=query_str,
                    response=response.content,
                    provider=provider,
                    model=response.model,
                    usage=response.usage
                )
    
    asyncio.run(run_query())


@main.command(name='collate')
@click.argument('query', nargs=-1, required=True)
@click.option('--providers', '-p', multiple=True, type=click.Choice(['claude', 'openai', 'ollama', 'gemini']), help='LLM providers to use')
@click.option('--temperature', '-t', default=0.7, help='Temperature for sampling')
@click.option('--max-tokens', default=None, type=int, help='Maximum tokens to generate')
@click.option('--table', '-t', is_flag=True, help='Show results in collation table')
def collate(query, providers, temperature, max_tokens, table):
    """Send the same query to multiple LLM providers simultaneously.
    
    Examples:
        aishell collate "What is 2+2?" -p claude -p openai -p ollama
        aishell collate "Explain DNS" --providers gemini --providers claude --table
    """
    query_str = ' '.join(query)
    
    # Default to all providers if none specified
    if not providers:
        providers = ['claude', 'openai', 'ollama', 'gemini']
    
    async def run_multi_query():
        transcript = get_transcript_manager()
        
        # Create provider instances
        provider_map = {
            'claude': ClaudeLLMProvider(),
            'openai': OpenAILLMProvider(),
            'ollama': OllamaLLMProvider(),
            'gemini': GeminiLLMProvider(),
        }
        
        # Filter to requested providers
        active_providers = {name: provider_map[name] for name in providers}
        
        console.print(f"[blue]Querying {len(active_providers)} providers simultaneously...[/blue]")
        console.print(f"[blue]Query:[/blue] {query_str}")
        console.print()
        
        # Run queries concurrently
        tasks = []
        for name, provider in active_providers.items():
            task = provider.query(
                query_str,
                temperature=temperature,
                max_tokens=max_tokens
            )
            tasks.append((name, task))
        
        # Gather results
        results = []
        with console.status("[yellow]Waiting for responses...[/yellow]", spinner="dots"):
            for name, task in tasks:
                try:
                    response = await task
                    results.append((name, response))
                except Exception as e:
                    # Create error response
                    from aishell.llm import LLMResponse
                    error_response = LLMResponse(
                        content="",
                        model="unknown",
                        provider=name,
                        error=str(e)
                    )
                    results.append((name, error_response))
        
        # Log to transcript
        transcript.log_multi_interaction(query_str, results)
        
        # Display results
        if table:
            # Collation table
            collation_table = Table(title="LLM Responses Collation", show_lines=True)
            collation_table.add_column("Provider", style="cyan", width=12)
            collation_table.add_column("Model", style="blue", width=20)
            collation_table.add_column("Response", style="white", no_wrap=False)
            collation_table.add_column("Tokens", style="dim", width=10)
            
            for name, response in results:
                if response.is_error:
                    collation_table.add_row(
                        name.title(),
                        response.model,
                        f"[red]Error: {response.error}[/red]",
                        "-"
                    )
                else:
                    tokens = "-"
                    if response.usage and 'total_tokens' in response.usage:
                        tokens = str(response.usage['total_tokens'])
                    
                    collation_table.add_row(
                        name.title(),
                        response.model,
                        response.content,
                        tokens
                    )
            
            console.print(collation_table)
        else:
            # Sequential display
            for name, response in results:
                if response.is_error:
                    panel = Panel(
                        f"[red]Error: {response.error}[/red]",
                        title=f"[red]{name.title()} Error[/red]",
                        border_style="red",
                        padding=(1, 2)
                    )
                else:
                    panel = Panel(
                        response.content,
                        title=f"[green]{name.title()} Response[/green]",
                        subtitle=f"Model: {response.model}",
                        border_style="green",
                        padding=(1, 2)
                    )
                console.print(panel)
                console.print()
    
    asyncio.run(run_multi_query())


@main.command()
@click.argument('server_url')
@click.argument('message', nargs=-1)
@click.option('--method', '-m', help='MCP method (e.g., tools/list, resources/read)')
@click.option('--params', '-p', help='JSON parameters for the method')
@click.option('--raw', '-r', is_flag=True, help='Send raw JSON message')
@click.option('--timeout', '-t', default=30, help='Request timeout in seconds')
def mcp(server_url, message, method, params, raw, timeout):
    """Interact with MCP (Model Context Protocol) servers.
    
    Examples:
        # List available tools
        aishell mcp http://localhost:8000 --method tools/list
        
        # Call a tool with parameters
        aishell mcp http://localhost:8000 --method tools/call --params '{"name": "search", "arguments": {"query": "python"}}'
        
        # Send raw JSON message
        aishell mcp http://localhost:8000 --raw '{"jsonrpc": "2.0", "method": "ping"}'
        
        # Simple ping
        aishell mcp http://localhost:8000 ping
    """
    async def run_mcp():
        async with MCPClient(server_url, timeout=timeout) as client:
            # Initialize connection first
            console.print(f"[blue]Connecting to MCP server:[/blue] {server_url}")
            init_response = await client.initialize(
                client_info={"name": "aishell", "version": __version__}
            )
            
            if init_response.is_error:
                client.display_response(init_response, "Initialization Failed")
                return
            
            console.print("[green]✓ Connected successfully[/green]")
            console.print()
            
            # Prepare the message
            if raw and message:
                # Parse raw JSON message
                import json
                try:
                    raw_msg = ' '.join(message)
                    msg_data = json.loads(raw_msg)
                    mcp_message = MCPMessage.from_dict(msg_data)
                except json.JSONDecodeError as e:
                    console.print(f"[red]Invalid JSON:[/red] {e}")
                    return
            elif method:
                # Use specified method and params
                params_dict = None
                if params:
                    try:
                        import json
                        params_dict = json.loads(params)
                    except json.JSONDecodeError as e:
                        console.print(f"[red]Invalid JSON parameters:[/red] {e}")
                        return
                
                mcp_message = MCPMessage(method=method, params=params_dict)
            elif message:
                # Simple command parsing
                cmd = ' '.join(message).lower()
                if cmd == 'ping':
                    response = await client.ping()
                    client.display_response(response, "Ping Response")
                    return
                elif cmd in ['list tools', 'tools']:
                    response = await client.list_tools()
                    client.display_response(response, "Available Tools")
                    return
                elif cmd in ['list resources', 'resources']:
                    response = await client.list_resources()
                    client.display_response(response, "Available Resources")
                    return
                elif cmd in ['list prompts', 'prompts']:
                    response = await client.list_prompts()
                    client.display_response(response, "Available Prompts")
                    return
                else:
                    console.print(f"[yellow]Unknown command:[/yellow] {cmd}")
                    console.print("Try: ping, list tools, list resources, list prompts")
                    return
            else:
                console.print("[red]Error:[/red] No message specified")
                console.print("Use --method, --raw, or provide a simple command")
                return
            
            # Send the message
            response = await client.send_message(mcp_message)
            client.display_response(response, f"Response for: {mcp_message.method}")
    
    asyncio.run(run_mcp())


@main.command(name='mcp-convert')
@click.argument('query', nargs=-1, required=True)
@click.option('--provider', '-p', type=click.Choice(['claude', 'openai']), help='LLM provider for advanced translation')
@click.option('--execute', '-e', is_flag=True, help='Execute the generated MCP message')
@click.option('--server', '-s', help='MCP server URL (required with --execute)')
def mcp_convert(query, provider, execute, server):
    """Convert natural language queries to MCP messages.
    
    Examples:
        # Simple conversion
        aishell mcp-convert "list all available tools"
        
        # With LLM assistance
        aishell mcp-convert "use the search tool to find Python tutorials" --provider claude
        
        # Convert and execute
        aishell mcp-convert "ping the server" --execute --server http://localhost:8000
    """
    query_str = ' '.join(query)
    
    async def run_conversion():
        # Create translator
        llm_provider = None
        if provider == 'claude':
            llm_provider = ClaudeLLMProvider()
        elif provider == 'openai':
            llm_provider = OpenAILLMProvider()
        
        translator = NLToMCPTranslator(llm_provider)
        
        console.print(f"[blue]Query:[/blue] {query_str}")
        console.print()
        
        # Get suggestions if query is short
        if len(query_str) < 20:
            suggestions = translator.get_suggestions(query_str)
            if suggestions:
                console.print("[dim]Suggestions:[/dim]")
                for suggestion in suggestions:
                    console.print(f"  • {suggestion}")
                console.print()
        
        # Translate the query
        with console.status("[yellow]Translating query...[/yellow]", spinner="dots"):
            mcp_message = await translator.translate(query_str)
        
        # Display the generated message
        import json
        syntax = Syntax(
            json.dumps(mcp_message.to_dict(), indent=2),
            "json",
            theme="monokai",
            line_numbers=False
        )
        
        panel = Panel(
            syntax,
            title="[green]Generated MCP Message[/green]",
            border_style="green",
            padding=(1, 2)
        )
        console.print(panel)
        
        # Execute if requested
        if execute:
            if not server:
                console.print("[red]Error:[/red] --server is required with --execute")
                return
            
            console.print()
            console.print(f"[blue]Executing on server:[/blue] {server}")
            
            async with MCPClient(server) as client:
                # Initialize first
                init_response = await client.initialize(
                    client_info={"name": "aishell", "version": __version__}
                )
                
                if init_response.is_error:
                    client.display_response(init_response, "Initialization Failed")
                    return
                
                # Send the message
                response = await client.send_message(mcp_message)
                client.display_response(response, "Execution Result")
    
    asyncio.run(run_conversion())


if __name__ == '__main__':
    main()