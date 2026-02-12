"""Unified CLI for conversation loading and semantic search.

Provides the `conversations` Click group with `load` and `search`
subcommands that operate across all providers (Gemini, ChatGPT, Claude).
"""

import json
import logging
import os

import click
from rich.console import Console
from rich.table import Table

from .db import DB_NAME, ensure_database, load_conversation
from .embeddings import get_model

console = Console()
logger = logging.getLogger(__name__)

# Provider data directories under ~/.aishell/
PROVIDERS = {
    "gemini": os.path.expanduser("~/.aishell/gemini/conversations"),
    "chatgpt": os.path.expanduser("~/.aishell/chatgpt/conversations"),
    "claude": os.path.expanduser("~/.aishell/claude/conversations"),
}


@click.group(name="conversations")
def conversations():
    """Load and search exported conversations from all providers."""
    pass


@conversations.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(list(PROVIDERS.keys())),
    help="Load only from a specific provider",
)
@click.option(
    "--skip-embeddings", is_flag=True, help="Load without generating embeddings"
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def load(provider, skip_embeddings, db):
    """Load conversations into PostgreSQL with embeddings.

    Scans all provider directories (or one if --provider given) for
    conversation JSON files and loads them into the shared database.
    Auto-creates database, pgvector extension, and tables on first run.
    Skips conversations already in the database.

    Examples:
        aishell conversations load
        aishell conversations load --provider gemini
        aishell conversations load --skip-embeddings
    """
    import glob as globmod
    import psycopg2

    console.print(f"[blue]Ensuring database '{db}' exists...[/blue]")
    ensure_database(db)

    # Determine which provider dirs to scan
    if provider:
        dirs_to_scan = {provider: PROVIDERS[provider]}
    else:
        dirs_to_scan = PROVIDERS

    # Gather conversation files from all relevant dirs
    all_files = []
    for prov_name, prov_dir in dirs_to_scan.items():
        if not os.path.isdir(prov_dir):
            continue
        files = sorted(globmod.glob(os.path.join(prov_dir, "*.json")))
        files = [f for f in files if not f.endswith("manifest.json")]
        for f in files:
            all_files.append((prov_name, f))

    if not all_files:
        console.print("[yellow]No conversation files found.[/yellow]")
        if provider:
            console.print(f"[dim]Directory checked: {PROVIDERS[provider]}[/dim]")
        else:
            console.print("[dim]Directories checked:[/dim]")
            for name, d in PROVIDERS.items():
                exists = (
                    "[green]exists[/green]"
                    if os.path.isdir(d)
                    else "[dim]not found[/dim]"
                )
                console.print(f"  {name}: {d} ({exists})")
        return

    console.print(f"[blue]Loading {len(all_files)} conversation(s) into {db}...[/blue]")

    conn = psycopg2.connect(dbname=db)
    loaded = 0
    skipped = 0

    try:
        for prov_name, filepath in all_files:
            basename = os.path.basename(filepath)
            with open(filepath) as f:
                data = json.load(f)

            if load_conversation(conn, data, skip_embeddings=skip_embeddings):
                stats = data["statistics"]
                console.print(
                    f"  [green]Loaded[/green]: [{prov_name}] {basename} "
                    f"({stats['turn_count']} turns, {stats['total_chars']:,} chars)"
                )
                loaded += 1
            else:
                console.print(
                    f"  [dim]Skipped[/dim]: [{prov_name}] {basename} (already loaded)"
                )
                skipped += 1

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        conn.rollback()
        raise
    finally:
        conn.close()

    console.print()
    summary = Table(title="Load Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", style="green")
    summary.add_row("Loaded", str(loaded))
    summary.add_row("Skipped", str(skipped))
    summary.add_row("Total", str(loaded + skipped))
    console.print(summary)


@conversations.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", "-l", type=int, default=10, help="Max results")
@click.option(
    "--source",
    "-s",
    type=click.Choice(list(PROVIDERS.keys())),
    help="Filter by provider source",
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def search(query, limit, source, db):
    """Semantic search across all exported conversations.

    Uses nomic-embed-text-v1.5 to embed the query and find
    the most similar turns via cosine similarity.

    Examples:
        aishell conversations search "manifold geometry"
        aishell conversations search "Lyapunov stability" --limit 5
        aishell conversations search "embeddings" --source gemini
    """
    import psycopg2

    query_str = " ".join(query)
    console.print(f"[blue]Searching for:[/blue] {query_str}")
    if source:
        console.print(f"[blue]Source filter:[/blue] {source}")

    # Embed query with search_query: prefix
    model = get_model()
    query_embedding = model.encode(
        [f"search_query: {query_str}"],
        show_progress_bar=False,
        normalize_embeddings=True,
    ).tolist()[0]
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    conn = psycopg2.connect(dbname=db)
    try:
        with conn.cursor() as cur:
            if source:
                cur.execute(
                    """
                    SELECT
                        t.role,
                        t.content,
                        c.title,
                        c.source,
                        1 - (t.embedding <=> %s::vector) AS similarity
                    FROM turns t
                    JOIN conversations c ON t.conversation_id = c.id
                    WHERE t.embedding IS NOT NULL
                      AND c.source = %s
                    ORDER BY t.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, source, emb_str, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        t.role,
                        t.content,
                        c.title,
                        c.source,
                        1 - (t.embedding <=> %s::vector) AS similarity
                    FROM turns t
                    JOIN conversations c ON t.conversation_id = c.id
                    WHERE t.embedding IS NOT NULL
                    ORDER BY t.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, emb_str, limit),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f'Search: "{query_str}"')
    table.add_column("Sim", style="green", width=6)
    table.add_column("Source", style="magenta", width=8)
    table.add_column("Role", style="cyan", width=10)
    table.add_column("Conversation", style="blue", width=30)
    table.add_column("Content", style="white", width=60, no_wrap=False)

    for role, content, title, src, similarity in rows:
        preview = content[:200] + "..." if len(content) > 200 else content
        table.add_row(f"{similarity:.3f}", src, role, title[:30], preview)

    console.print(table)
