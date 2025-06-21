import asyncio
import click
from rich.console import Console

from aishell import __version__
from aishell.search.web_search import perform_web_search
from aishell.shell.intelligent_shell import IntelligentShell
from aishell.search.file_search import MacOSFileSearcher, display_results

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


if __name__ == '__main__':
    main()