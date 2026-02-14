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
    Conversation,
)
from aishell.mcp import MCPClient, MCPMessage, NLToMCPTranslator
from aishell.utils import get_transcript_manager, load_env_on_startup

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="aishell")
@click.pass_context
def main(ctx):
    """AIShell - An intelligent command line tool."""
    ctx.ensure_object(dict)

    # Load environment variables on startup
    load_env_on_startup(verbose=False)


@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", "-l", default=10, help="Number of results to return")
@click.option(
    "--engine",
    "-e",
    default="hackernews",
    type=click.Choice(["google", "duckduckgo", "hackernews"]),
    help="Search engine to use",
)
@click.option(
    "--show-browser",
    "-s",
    is_flag=True,
    help="Show browser window (disable headless mode)",
)
def search(query, limit, engine, show_browser):
    """Web search from the command line using Playwright and headless Chrome."""
    query_str = " ".join(query)
    headless = not show_browser

    # Run the async search function
    asyncio.run(
        perform_web_search(query_str, limit=limit, engine=engine, headless=headless)
    )


@main.command()
@click.argument("pattern", required=True)
@click.option("--path", "-p", default=".", help="Path to search in")
@click.option("--content", "-c", help="Search for content within files")
@click.option(
    "--type", "-t", help="File type filter (image, video, audio, text, code, etc.)"
)
@click.option("--size", "-s", help='Size filter (e.g., ">1MB", "<500KB")')
@click.option(
    "--date", "-d", help='Date filter (e.g., "today", "last week", "yesterday")'
)
@click.option("--limit", "-l", default=100, help="Maximum number of results")
@click.option(
    "--no-spotlight", is_flag=True, help="Disable Spotlight and use find instead"
)
@click.option("--tree", is_flag=True, help="Display results in tree format")
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
        use_spotlight=not no_spotlight,
    )

    if tree:
        from aishell.search.file_search import create_tree_view

        tree_view = create_tree_view(results, path)
        console.print(tree_view)
    else:
        display_results(results, show_content=bool(content))


@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", "-l", default=20, help="Maximum number of results")
def spotlight(query, limit):
    """Quick Spotlight search for any query.

    Uses macOS Spotlight to search for files, content, and metadata.

    Examples:
        aishell spotlight python tutorial
        aishell spotlight "machine learning"
        aishell spotlight kind:image
    """
    searcher = MacOSFileSearcher()
    query_str = " ".join(query)

    console.print(f"[blue]Spotlight search:[/blue] {query_str}")

    results = searcher.quick_search(query_str, max_results=limit)
    display_results(results, show_content=False)


@main.command()
@click.option("--no-history", is_flag=True, help="Disable command history")
@click.option("--config", type=click.Path(), help="Path to configuration file")
@click.option(
    "--nl-provider",
    type=click.Choice(["claude", "ollama", "mock", "none"]),
    default="claude",
    help="Natural language provider",
)
@click.option(
    "--ollama-model",
    default="llama2",
    help="Ollama model to use (if using ollama provider)",
)
@click.option(
    "--anthropic-api-key",
    envvar="ANTHROPIC_API_KEY",
    help="Anthropic API key for Claude",
)
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
    if nl_provider == "ollama":
        nl_kwargs["model"] = ollama_model
    elif nl_provider == "claude" and anthropic_api_key:
        nl_kwargs["api_key"] = anthropic_api_key

    # Create shell instance
    if nl_provider == "none":
        shell = IntelligentShell(nl_provider="mock", nl_converter_kwargs=None)
        shell.nl_converter = None  # Disable NL conversion
    else:
        shell = IntelligentShell(nl_provider=nl_provider, nl_converter_kwargs=nl_kwargs)

    if no_history:
        shell.history = None

    shell.run()


@main.command()
@click.argument("provider", required=False)
@click.argument("query", nargs=-1, required=True)
@click.option("--temperature", "-t", default=0.7, help="Temperature for sampling")
@click.option("--max-tokens", default=None, type=int, help="Maximum tokens to generate")
@click.option("--stream", "-s", is_flag=True, help="Stream the response")
@click.option("--api-key", envvar="LLM_API_KEY", help="API key for the provider")
@click.option("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
@click.option("--openai-url", help="OpenAI-compatible API URL")
@click.option(
    "--research",
    "-r",
    is_flag=True,
    help="Enable deep research with Google Search grounding (Gemini only)",
)
def llm(
    provider,
    query,
    temperature,
    max_tokens,
    stream,
    api_key,
    ollama_url,
    openai_url,
    research,
):
    """Send a query to a single LLM provider.

    Examples:
        aishell llm claude "What is the capital of France?"
        aishell llm openai "Explain quantum computing"
        aishell llm "Hello" --stream  # Uses default provider
        aishell llm gemini "Tell me a joke" --temperature 0.9
        aishell llm gemini "Latest AI developments" --research
    """
    query_str = " ".join(query)

    def _enhance_query_with_mcp_context(query_text: str) -> str:
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

        query_lower = query_text.lower()
        if any(keyword in query_lower for keyword in mcp_keywords):
            from aishell.utils import get_mcp_capability_manager

            mcp_manager = get_mcp_capability_manager()
            mcp_context = mcp_manager.generate_mcp_context_prompt()

            if mcp_context != "No MCP servers are currently configured.":
                enhanced_query = f"""{query_text}

{mcp_context}

Please consider whether any of the available MCP tools could help with this request and suggest appropriate commands if relevant."""
                return enhanced_query

        return query_text

    async def run_query():
        transcript = get_transcript_manager()

        # Get default provider if none specified
        from aishell.utils import get_env_manager

        env_manager = get_env_manager()

        if provider is None:
            provider_name = env_manager.get_var("DEFAULT_LLM_PROVIDER", "claude")
            console.print(f"[blue]Using default provider: {provider_name}[/blue]")
        else:
            provider_name = provider

        # Validate provider
        valid_providers = ["claude", "openai", "ollama", "gemini"]
        if provider_name not in valid_providers:
            console.print(
                f"[red]Error: Unknown provider '{provider_name}'. Available providers: {', '.join(valid_providers)}[/red]"
            )
            return

        # Get configuration from environment manager
        env_manager = get_env_manager()
        config = env_manager.get_llm_config(provider_name)

        # Enhance query with MCP context if relevant
        enhanced_query = _enhance_query_with_mcp_context(query_str)

        # Create the appropriate provider with env config
        if provider_name == "claude":
            llm = ClaudeLLMProvider(
                api_key=api_key or config.get("api_key"),
                base_url=config.get("base_url"),
            )
        elif provider_name == "openai":
            llm = OpenAILLMProvider(
                api_key=api_key or config.get("api_key"),
                base_url=openai_url or config.get("base_url"),
            )
        elif provider_name == "ollama":
            llm = OllamaLLMProvider(base_url=ollama_url or config.get("base_url"))
        elif provider_name == "gemini":
            llm = GeminiLLMProvider(
                api_key=api_key or config.get("api_key"),
                base_url=config.get("base_url"),
            )

        console.print(f"[blue]Provider:[/blue] {provider_name}")
        console.print(f"[blue]Model:[/blue] {llm.default_model} (default)")
        if research and provider_name == "gemini":
            console.print("[blue]Mode:[/blue] Deep Research (Google Search grounding)")
        elif research and provider_name != "gemini":
            console.print(
                "[yellow]Warning:[/yellow] --research is only supported with Gemini"
            )
        console.print()

        if stream:
            # Streaming response
            streamed_content = ""
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                first_chunk = True
                async for chunk in llm.stream_query(
                    enhanced_query, temperature=temperature, max_tokens=max_tokens
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
                provider=provider_name,
                model=llm.default_model,
            )
        else:
            # Regular response
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                # Pass research flag to Gemini queries
                query_kwargs = {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if research and provider_name == "gemini":
                    query_kwargs["research"] = True

                response = await llm.query(enhanced_query, **query_kwargs)

            if response.is_error:
                console.print(f"[red]Error:[/red] {response.error}")
                # Log error to transcript
                transcript.log_interaction(
                    query=query_str,
                    response="",
                    provider=provider_name,
                    model=llm.default_model,
                    error=response.error,
                )
            else:
                # Display response in a nice panel
                panel = Panel(
                    response.content,
                    title=f"[green]{response.provider.title()} Response[/green]",
                    subtitle=f"Model: {response.model}",
                    border_style="green",
                    padding=(1, 2),
                )
                console.print(panel)

                # Show usage stats if available
                if response.usage:
                    console.print()
                    console.print("[dim]Usage:[/dim]")
                    for key, value in response.usage.items():
                        console.print(f"  [dim]{key}:[/dim] {value}")

                # Show research/grounding metadata if available
                if response.metadata and response.metadata.get("grounded"):
                    console.print()
                    console.print("[blue]Research Sources:[/blue]")
                    if "search_queries" in response.metadata:
                        console.print("  [dim]Search queries:[/dim]")
                        for sq in response.metadata["search_queries"]:
                            console.print(f"    - {sq}")
                    if "grounding_chunks" in response.metadata:
                        console.print(
                            f"  [dim]Sources used:[/dim] {response.metadata['grounding_chunks']}"
                        )

                # Log successful response to transcript
                transcript.log_interaction(
                    query=query_str,
                    response=response.content,
                    provider=provider_name,
                    model=response.model,
                    usage=response.usage,
                )

    asyncio.run(run_query())


@main.command(name="collate")
@click.argument("args", nargs=-1, required=True)
@click.option("--temperature", "-t", default=0.7, help="Temperature for sampling")
@click.option("--max-tokens", default=None, type=int, help="Maximum tokens to generate")
@click.option("--table", "-T", is_flag=True, help="Show results in collation table")
@click.option(
    "--db", type=click.Path(), help="Override database path for storing responses"
)
@click.option("--save/--no-save", default=True, help="Save responses to database")
def collate(args, temperature, max_tokens, table, db, save):
    """Send the same query to multiple LLM providers simultaneously.

    Accepts 2+ providers followed by the query. The last argument(s) form the query,
    all preceding valid provider names are used as providers.

    Examples:
        aishell collate claude openai "What is 2+2?"
        aishell collate claude openai gemini "Compare these AI models"
        aishell collate gemini ollama "Explain DNS" --table
        aishell collate claude openai gemini "Tell me a joke" --no-save
        aishell collate claude openai "Research query" --db ./research.db
    """
    # Valid providers list
    valid_providers = ["claude", "openai", "ollama", "gemini", "openrouter"]

    # Parse providers and query from args
    providers = []
    query_parts = []

    for i, arg in enumerate(args):
        if arg.lower() in valid_providers and not query_parts:
            providers.append(arg.lower())
        else:
            query_parts = list(args[i:])
            break

    # Validate we have at least 2 providers
    if len(providers) < 2:
        console.print("[red]Error: At least 2 providers required[/red]")
        console.print(f"[dim]Valid providers: {', '.join(valid_providers)}[/dim]")
        console.print(
            '[dim]Usage: aishell collate <provider1> <provider2> [provider3...] "query"[/dim]'
        )
        return

    # Validate we have a query
    if not query_parts:
        console.print("[red]Error: Query is required[/red]")
        console.print(
            '[dim]Usage: aishell collate <provider1> <provider2> [provider3...] "query"[/dim]'
        )
        return

    query_str = " ".join(query_parts)

    # Check for duplicate providers
    if len(providers) != len(set(providers)):
        console.print("[yellow]Warning: Duplicate providers specified[/yellow]")

    async def run_multi_query():
        transcript = get_transcript_manager()

        # Get environment configuration
        from aishell.utils import get_env_manager

        env_manager = get_env_manager()

        # Import OpenRouter if needed
        from aishell.llm import OpenRouterLLMProvider

        # Create provider instances with env config
        provider_map = {}
        for provider_name in providers:
            config = env_manager.get_llm_config(provider_name)
            if provider_name == "claude":
                provider_map[provider_name] = ClaudeLLMProvider(
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "openai":
                provider_map[provider_name] = OpenAILLMProvider(
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "ollama":
                provider_map[provider_name] = OllamaLLMProvider(
                    base_url=config.get("base_url")
                )
            elif provider_name == "gemini":
                provider_map[provider_name] = GeminiLLMProvider(
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )
            elif provider_name == "openrouter":
                provider_map[provider_name] = OpenRouterLLMProvider(
                    api_key=config.get("api_key"), base_url=config.get("base_url")
                )

        console.print(
            f"[blue]Querying {len(provider_map)} providers simultaneously...[/blue]"
        )
        console.print(f"[blue]Query:[/blue] {query_str}")
        for name, provider in provider_map.items():
            console.print(
                f"[blue]{name.title()}:[/blue] {provider.default_model} (default)"
            )
        console.print()

        # Run queries concurrently using asyncio.gather for true parallelism
        async def query_provider(name, provider):
            try:
                response = await provider.query(
                    query_str, temperature=temperature, max_tokens=max_tokens
                )
                return (name, response)
            except Exception as e:
                from aishell.llm import LLMResponse

                error_response = LLMResponse(
                    content="", model="unknown", provider=name, error=str(e)
                )
                return (name, error_response)

        # Gather results in parallel
        with console.status(
            "[yellow]Waiting for responses...[/yellow]", spinner="dots"
        ):
            tasks = [
                query_provider(name, provider)
                for name, provider in provider_map.items()
            ]
            results = await asyncio.gather(*tasks)

        # Log to transcript
        transcript.log_multi_interaction(query_str, results)

        # Save to database if enabled
        if save:
            try:
                from aishell.storage import get_storage_manager

                storage = get_storage_manager(db)
                stored_responses, stored_errors = storage.store_collation(
                    query=query_str,
                    responses=results,
                    metadata={"temperature": temperature, "max_tokens": max_tokens},
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
                        "-",
                    )
                else:
                    tokens = "-"
                    if response.usage and "total_tokens" in response.usage:
                        tokens = str(response.usage["total_tokens"])

                    collation_table.add_row(
                        name.title(), response.model, response.content, tokens
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
                        padding=(1, 2),
                    )
                else:
                    panel = Panel(
                        response.content,
                        title=f"[green]{name.title()} Response[/green]",
                        subtitle=f"Model: {response.model}",
                        border_style="green",
                        padding=(1, 2),
                    )
                console.print(panel)
                console.print()

    asyncio.run(run_multi_query())


@main.command(name="search-responses")
@click.argument("search_text", required=False)
@click.option("--provider", "-p", multiple=True, help="Filter by provider(s)")
@click.option("--model", "-m", multiple=True, help="Filter by model(s)")
@click.option("--session", "-s", help="Filter by session ID")
@click.option("--hours", "-h", type=int, help="Only responses from last N hours")
@click.option("--limit", "-l", default=20, help="Maximum results to return")
@click.option("--offset", "-o", default=0, help="Skip first N results")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--db", type=click.Path(), help="Override database path")
def search_responses(
    search_text,
    provider,
    model,
    session,
    hours,
    limit,
    offset,
    output_json,
    db,
):
    """Search stored LLM responses.

    Examples:
        aishell search-responses "python"
        aishell search-responses --provider claude --hours 24
        aishell search-responses --provider claude --provider openai
        aishell search-responses --session abc123
        aishell search-responses --json > results.json
        aishell search-responses --db ./research.db "kubernetes"
    """
    from aishell.storage import get_storage_manager, SearchQuery
    from datetime import datetime, timedelta

    try:
        storage = get_storage_manager(db)
    except Exception as e:
        console.print(f"[red]Error opening database:[/red] {e}")
        return

    console.print(f"[dim]Database: {storage.db_path}[/dim]")

    # Build search query
    query = SearchQuery(
        query_contains=search_text,
        providers=list(provider) if provider else None,
        models=list(model) if model else None,
        session_id=session,
        from_date=datetime.now() - timedelta(hours=hours) if hours else None,
        limit=limit,
        offset=offset,
    )

    result = storage.search(query)

    if output_json:
        import json

        console.print(json.dumps(result.to_dict(), indent=2, default=str))
        return

    # Display results in table
    if not result.responses:
        console.print("[yellow]No responses found[/yellow]")
        return

    console.print(
        f"[blue]Found {result.total_count} responses (showing {len(result.responses)})[/blue]"
    )
    console.print()

    response_table = Table(title="Stored Responses", show_lines=True)
    response_table.add_column("ID", style="dim", width=6)
    response_table.add_column("Date", style="cyan", width=16)
    response_table.add_column("Provider", style="blue", width=10)
    response_table.add_column("Query", style="white", width=30, no_wrap=True)
    response_table.add_column("Response", style="green", width=40, no_wrap=True)

    for resp in result.responses:
        query_preview = resp.query[:27] + "..." if len(resp.query) > 30 else resp.query
        content_preview = (
            resp.content[:37] + "..." if len(resp.content) > 40 else resp.content
        )

        response_table.add_row(
            str(resp.id),
            resp.created_at.strftime("%Y-%m-%d %H:%M") if resp.created_at else "N/A",
            resp.provider,
            query_preview,
            content_preview,
        )

    console.print(response_table)

    if result.total_count > len(result.responses):
        console.print(f"\n[dim]Use --offset {offset + limit} to see more results[/dim]")


@main.command(name="search-errors")
@click.option("--provider", "-p", help="Filter by provider")
@click.option("--hours", "-h", type=int, help="Only errors from last N hours")
@click.option("--limit", "-l", default=20, help="Maximum results to return")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--db", type=click.Path(), help="Override database path")
def search_errors(provider, hours, limit, output_json, db):
    """Search stored LLM errors.

    Errors are stored separately from successful responses.

    Examples:
        aishell search-errors
        aishell search-errors --provider openai
        aishell search-errors --hours 24
        aishell search-errors --json > errors.json
    """
    from aishell.storage import get_storage_manager

    try:
        storage = get_storage_manager(db)
    except Exception as e:
        console.print(f"[red]Error opening database:[/red] {e}")
        return

    console.print(f"[dim]Database: {storage.db_path}[/dim]")

    errors = storage.get_errors(provider=provider, hours=hours, limit=limit)

    if output_json:
        import json

        console.print(json.dumps([e.to_dict() for e in errors], indent=2, default=str))
        return

    if not errors:
        console.print("[green]No errors found[/green]")
        return

    total_errors = storage.count_errors()
    console.print(
        f"[yellow]Found {total_errors} total errors (showing {len(errors)})[/yellow]"
    )
    console.print()

    error_table = Table(title="Stored Errors", show_lines=True)
    error_table.add_column("ID", style="dim", width=6)
    error_table.add_column("Date", style="cyan", width=16)
    error_table.add_column("Provider", style="blue", width=10)
    error_table.add_column("Query", style="white", width=25, no_wrap=True)
    error_table.add_column("Error", style="red", width=45, no_wrap=True)

    for err in errors:
        query_preview = err.query[:22] + "..." if len(err.query) > 25 else err.query
        error_preview = (
            err.error_message[:42] + "..."
            if len(err.error_message) > 45
            else err.error_message
        )

        error_table.add_row(
            str(err.id),
            err.created_at.strftime("%Y-%m-%d %H:%M") if err.created_at else "N/A",
            err.provider,
            query_preview,
            error_preview,
        )

    console.print(error_table)


@main.command()
@click.argument("provider", required=False, default="openai")
@click.option("--resume", "-r", help="Resume an existing conversation by ID")
@click.option("--system", "-s", help="System prompt for the conversation")
@click.option("--model", "-m", help="Model to use")
@click.option("--temperature", "-t", default=0.7, help="Temperature for sampling")
@click.option("--max-tokens", default=None, type=int, help="Maximum tokens to generate")
def chat(provider, resume, system, model, temperature, max_tokens):
    """Start an interactive multi-turn chat session.

    Conversations are stored in the database with full history.

    Examples:
        aishell chat                    # Start chat with OpenAI (default)
        aishell chat openai             # Start chat with OpenAI
        aishell chat claude             # Start chat with Claude
        aishell chat --resume abc123    # Resume existing conversation
        aishell chat --system "You are a helpful coding assistant"
    """
    from prompt_toolkit import prompt
    from prompt_toolkit.history import InMemoryHistory

    async def run_chat():
        from aishell.utils import get_env_manager

        env_manager = get_env_manager()

        # Determine provider
        provider_name = provider.lower() if provider else "openai"
        valid_providers = ["claude", "openai", "ollama", "gemini"]

        if provider_name not in valid_providers:
            console.print(
                f"[red]Error: Unknown provider '{provider_name}'. "
                f"Available: {', '.join(valid_providers)}[/red]"
            )
            return

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

        model_name = model or llm.default_model

        # Load or create conversation
        if resume:
            try:
                conversation = Conversation.load(resume)
                console.print(f"[green]Resumed conversation:[/green] {resume[:8]}...")
                console.print(
                    f"[dim]Messages loaded: {len(conversation.messages)}[/dim]"
                )
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                return
        else:
            conversation = Conversation(
                provider=provider_name,
                model=model_name,
                system_prompt=system,
            )
            console.print(
                f"[green]Started new conversation:[/green] {conversation.conversation_id[:8]}..."
            )

        console.print(f"[blue]Provider:[/blue] {provider_name}")
        console.print(f"[blue]Model:[/blue] {model_name}")
        if system:
            console.print(f"[blue]System:[/blue] {system[:50]}...")
        console.print()
        console.print("[dim]Commands: /exit, /history, /id, /clear[/dim]")
        console.print()

        # Chat loop
        history = InMemoryHistory()

        while True:
            try:
                user_input = prompt("You: ", history=history).strip()

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
                                else "green" if msg.role == "assistant" else "yellow"
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
                        console.print(f"[yellow]Unknown command:[/yellow] {cmd}")
                        console.print(
                            "[dim]Available: /exit, /history, /id, /clear[/dim]"
                        )
                        continue

                # Add user message
                conversation.add_user_message(user_input)

                # Get response
                with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                    response = await llm.chat(
                        conversation.get_messages(),
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                if response.is_error:
                    console.print(f"[red]Error:[/red] {response.error}")
                    # Remove the user message we just added since we couldn't get a response
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

    asyncio.run(run_chat())


@main.command(name="llm-chats")
@click.option("--provider", "-p", help="Filter by provider")
@click.option("--limit", "-l", default=20, help="Maximum conversations to show")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--db", type=click.Path(), help="Override database path")
def list_conversations(provider, limit, output_json, db):
    """List recent interactive LLM chat sessions.

    Examples:
        aishell llm-chats
        aishell llm-chats --provider openai
        aishell llm-chats --limit 10 --json
    """
    from aishell.storage import get_storage_manager

    try:
        storage = get_storage_manager(db)
    except Exception as e:
        console.print(f"[red]Error opening database:[/red] {e}")
        return

    console.print(f"[dim]Database: {storage.db_path}[/dim]")

    conversations = storage.list_conversations(provider=provider, limit=limit)

    if output_json:
        import json

        console.print(json.dumps(conversations, indent=2, default=str))
        return

    if not conversations:
        console.print("[yellow]No conversations found[/yellow]")
        return

    console.print(f"[blue]Found {len(conversations)} conversation(s)[/blue]")
    console.print()

    conv_table = Table(title="Recent Conversations", show_lines=True)
    conv_table.add_column("ID", style="dim", width=10)
    conv_table.add_column("Provider", style="blue", width=10)
    conv_table.add_column("Model", style="cyan", width=15)
    conv_table.add_column("Messages", style="green", width=8)
    conv_table.add_column("Started", style="dim", width=16)
    conv_table.add_column("Preview", style="white", width=35, no_wrap=True)

    for conv in conversations:
        conv_table.add_row(
            conv["conversation_id"][:8] + "...",
            conv["provider"],
            conv["model"][:15] if len(conv["model"]) > 15 else conv["model"],
            str(conv["message_count"]),
            conv["started_at"][:16] if conv["started_at"] else "N/A",
            conv["preview"],
        )

    console.print(conv_table)


@main.command()
@click.argument("server_url")
@click.argument("message", nargs=-1)
@click.option("--method", "-m", help="MCP method (e.g., tools/list, resources/read)")
@click.option("--params", "-p", help="JSON parameters for the method")
@click.option("--raw", "-r", is_flag=True, help="Send raw JSON message")
@click.option("--timeout", "-t", default=30, help="Request timeout in seconds")
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
                    raw_msg = " ".join(message)
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
                cmd = " ".join(message).lower()
                if cmd == "ping":
                    response = await client.ping()
                    client.display_response(response, "Ping Response")
                    return
                elif cmd in ["list tools", "tools"]:
                    response = await client.list_tools()
                    client.display_response(response, "Available Tools")
                    return
                elif cmd in ["list resources", "resources"]:
                    response = await client.list_resources()
                    client.display_response(response, "Available Resources")
                    return
                elif cmd in ["list prompts", "prompts"]:
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


@main.command(name="mcp-convert")
@click.argument("query", nargs=-1, required=True)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["claude", "openai"]),
    help="LLM provider for advanced translation",
)
@click.option("--execute", "-e", is_flag=True, help="Execute the generated MCP message")
@click.option("--server", "-s", help="MCP server URL (required with --execute)")
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
    query_str = " ".join(query)

    async def run_conversion():
        # Create translator
        llm_provider = None
        if provider == "claude":
            llm_provider = ClaudeLLMProvider()
        elif provider == "openai":
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
            line_numbers=False,
        )

        panel = Panel(
            syntax,
            title="[green]Generated MCP Message[/green]",
            border_style="green",
            padding=(1, 2),
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


@main.command()
@click.argument("url", required=False)
@click.option("--task", "-t", help="Natural language task description (LLM-assisted)")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Use saved configuration file"
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["claude", "openai", "gemini", "ollama", "opus", "haiku"]),
    help="LLM provider for task translation",
)
@click.option(
    "--fallback",
    type=click.Choice(["claude", "openai", "gemini", "ollama", "opus", "haiku"]),
    help="Fallback provider if primary fails",
)
@click.option(
    "--save-config", type=click.Path(), help="Save generated configuration to file"
)
@click.option(
    "--output", "-o", type=click.Path(), help="Output file for extracted data"
)
@click.option(
    "--headless/--no-headless", default=True, help="Run browser in headless mode"
)
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser type",
)
def navigate(
    url, task, config, provider, fallback, save_config, output, headless, browser
):
    """Navigate and scrape websites using LLM-assisted Playwright automation.

    Three modes of operation:

    1. Free-form task (LLM translates to actions):
       aishell navigate https://example.com --task "Extract all product prices"

    2. Configuration-based (reusable patterns):
       aishell navigate --config home_loans.yaml

    3. Task variations with fallback:
       aishell navigate https://example.com --task "Get loan rates" --provider haiku --fallback opus

    Examples:
        # Discovery with Opus
        aishell navigate https://www.icici.bank.in \\
          --task "Extract all home loan products with rates" \\
          --provider opus --save-config home_loans.yaml

        # Weekly execution with Haiku
        aishell navigate --config home_loans.yaml \\
          --provider haiku --fallback opus --output data.json

        # Quick extraction
        aishell navigate https://news.ycombinator.com \\
          --task "Get top 10 story titles and URLs"
    """

    async def run_navigation():
        from pathlib import Path
        from usecases.webscraping import (
            WebNavigator,
            LLMNavigator,
            ScrapingConfig,
            ConfigLibrary,
        )
        from aishell.utils import get_env_manager

        # Validate inputs
        if not url and not config:
            console.print("[red]Error:[/red] Either URL or --config must be provided")
            return

        if config and not Path(config).exists():
            console.print(f"[red]Error:[/red] Configuration file not found: {config}")
            return

        # Get LLM provider if needed
        llm_provider_instance = None
        fallback_provider_instance = None

        if task or (config and provider):
            env_manager = get_env_manager()

            # Map opus/haiku to claude with specific models
            if provider == "opus":
                provider_name = "claude"
                model_override = "claude-opus-4-20250514"
            elif provider == "haiku":
                provider_name = "claude"
                model_override = "claude-3-5-haiku-20241022"
            else:
                provider_name = provider or env_manager.get_var(
                    "DEFAULT_LLM_PROVIDER", "claude"
                )
                model_override = None

            # Create primary provider
            config_dict = env_manager.get_llm_config(provider_name)

            if provider_name == "claude":
                llm_provider_instance = ClaudeLLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "openai":
                llm_provider_instance = OpenAILLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "gemini":
                llm_provider_instance = GeminiLLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "ollama":
                llm_provider_instance = OllamaLLMProvider(
                    base_url=config_dict.get("base_url")
                )

            # Create fallback provider if specified
            if fallback:
                if fallback == "opus":
                    fallback_name = "claude"
                    fallback_model = "claude-opus-4-20250514"
                elif fallback == "haiku":
                    fallback_name = "claude"
                    fallback_model = "claude-3-5-haiku-20241022"
                else:
                    fallback_name = fallback
                    fallback_model = None

                fallback_config = env_manager.get_llm_config(fallback_name)

                if fallback_name == "claude":
                    fallback_provider_instance = ClaudeLLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "openai":
                    fallback_provider_instance = OpenAILLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "gemini":
                    fallback_provider_instance = GeminiLLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "ollama":
                    fallback_provider_instance = OllamaLLMProvider(
                        base_url=fallback_config.get("base_url")
                    )

        # Create navigator
        async with WebNavigator(headless=headless, browser_type=browser) as navigator:

            result = None

            if config:
                # Mode 2: Configuration-based
                console.print(f"[blue]Loading configuration:[/blue] {config}")
                scraping_config = ScrapingConfig.load(Path(config))

                console.print(f"[blue]Task:[/blue] {scraping_config.name}")
                console.print(f"[blue]URL:[/blue] {scraping_config.url}")
                console.print(f"[blue]Actions:[/blue] {len(scraping_config.actions)}")
                console.print()

                with console.status(
                    "[yellow]Executing navigation...[/yellow]", spinner="dots"
                ):
                    result = await navigator.execute_config(scraping_config)

            elif task:
                # Mode 1: Free-form task with LLM
                if not llm_provider_instance:
                    console.print(
                        "[red]Error:[/red] LLM provider required for task-based navigation"
                    )
                    return

                llm_nav = LLMNavigator(
                    llm_provider=llm_provider_instance,
                    navigator=navigator,
                    fallback_provider=fallback_provider_instance,
                    model=model_override,
                    fallback_model=fallback_model if fallback else None,
                )

                console.print(f"[blue]Task:[/blue] {task}")
                console.print(f"[blue]URL:[/blue] {url}")
                console.print(f"[blue]Provider:[/blue] {provider or 'default'}")
                if fallback:
                    console.print(f"[blue]Fallback:[/blue] {fallback}")
                console.print()

                with console.status(
                    "[yellow]Generating navigation plan...[/yellow]", spinner="dots"
                ):
                    save_path = Path(save_config) if save_config else None
                    result = await llm_nav.execute_task(
                        task, url, save_config=save_path
                    )

                if save_config:
                    console.print(
                        f"[green]✓[/green] Configuration saved to: {save_config}"
                    )
                    console.print()

            else:
                console.print(
                    "[red]Error:[/red] Either --task or --config must be provided"
                )
                return

            # Display results
            if result:
                if result.success:
                    console.print("[green]✓ Navigation completed successfully[/green]")
                    console.print(
                        f"[blue]Actions executed:[/blue] {result.actions_executed}"
                    )

                    if result.data:
                        console.print()
                        console.print("[blue]Extracted data:[/blue]")

                        import json

                        data_json = json.dumps(result.data, indent=2)
                        syntax = Syntax(
                            data_json, "json", theme="monokai", line_numbers=False
                        )
                        panel = Panel(
                            syntax,
                            title="[green]Data[/green]",
                            border_style="green",
                            padding=(1, 2),
                        )
                        console.print(panel)

                        # Save to output file if specified
                        if output:
                            output_path = Path(output)
                            output_path.parent.mkdir(parents=True, exist_ok=True)

                            if output_path.suffix == ".json":
                                with open(output_path, "w") as f:
                                    json.dump(result.data, f, indent=2)
                            elif output_path.suffix == ".yaml":
                                import yaml

                                with open(output_path, "w") as f:
                                    yaml.dump(result.data, f)
                            else:
                                # Default to JSON
                                with open(output_path, "w") as f:
                                    json.dump(result.data, f, indent=2)

                            console.print(f"[green]✓[/green] Data saved to: {output}")

                    if result.screenshots:
                        console.print()
                        console.print("[blue]Screenshots:[/blue]")
                        for screenshot in result.screenshots:
                            console.print(f"  • {screenshot}")

                    if result.metadata:
                        console.print()
                        console.print("[dim]Page metadata:[/dim]")
                        console.print(
                            f"  [dim]Title:[/dim] {result.metadata.get('title', 'N/A')}"
                        )

                else:
                    console.print("[red]✗ Navigation failed[/red]")

                if result.errors:
                    console.print()
                    console.print("[red]Errors:[/red]")
                    for error in result.errors:
                        console.print(f"  • {error}")

    asyncio.run(run_navigation())


from aishell.commands import discover_commands

discover_commands(main)


def aisearch_main():
    """Shortcut entry point: aisearch 'query' [flags]

    Delegates directly to `aishell conversations search`.
    """
    from aishell.commands.conversations.cli import search as _search

    _search(standalone_mode=True)


if __name__ == "__main__":
    main()
