import asyncio
import click
from rich.console import Console

from aishell import __version__
from aishell.search.web_search import perform_web_search

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
def shell():
    """Start an intelligent shell session."""
    console.print("[green]Starting AIShell interactive mode...[/green]")
    console.print("[yellow]Shell functionality coming soon...[/yellow]")


if __name__ == '__main__':
    main()