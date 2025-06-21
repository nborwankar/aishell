import asyncio
import click
from rich.console import Console

from aishell import __version__
from aishell.search.web_search import perform_web_search
from aishell.shell.intelligent_shell import IntelligentShell

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
def find(pattern, path, content):
    """Search for files in the filesystem."""
    console.print(f"[blue]Finding files matching:[/blue] {pattern}")
    if content:
        console.print(f"[blue]With content:[/blue] {content}")
    console.print(f"[yellow]File search functionality coming soon...[/yellow]")


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