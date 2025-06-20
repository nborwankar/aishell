import click
from rich.console import Console

from aishell import __version__

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
def search(query, limit):
    """Web search from the command line."""
    query_str = ' '.join(query)
    console.print(f"[blue]Searching for:[/blue] {query_str}")
    console.print(f"[yellow]Web search functionality coming soon...[/yellow]")


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