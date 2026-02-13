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

from .db import DB_NAME, ensure_database, load_raw_conversation, embed_and_store_chunks
from .embeddings import get_model

console = Console()
logger = logging.getLogger(__name__)

# Provider raw data directories under ~/.aishell/
RAW_PROVIDERS = {
    "gemini": os.path.expanduser("~/.aishell/gemini/raw"),
    "chatgpt": os.path.expanduser("~/.aishell/chatgpt/raw"),
    "claude": os.path.expanduser("~/.aishell/claude/raw"),
}


@click.group(name="conversations")
def conversations():
    """Load and search exported conversations from all providers."""
    pass


@conversations.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(list(RAW_PROVIDERS.keys())),
    help="Load only from a specific provider",
)
@click.option(
    "--skip-embeddings", is_flag=True, help="Load without generating embeddings"
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def load(provider, skip_embeddings, db):
    """Load raw conversations into PostgreSQL with JSONB storage.

    Scans all provider raw directories (or one if --provider given) for
    raw JSON files and loads them into the conversations_raw table.
    Auto-creates database, pgvector extension, and tables on first run.
    Skips conversations already in the database.

    Examples:
        aishell conversations load
        aishell conversations load --provider gemini
        aishell conversations load --skip-embeddings
    """
    import glob as globmod
    import psycopg2

    from ..chatgpt import _parse_chatgpt_conversation, extract_chatgpt_meta
    from ..claude_export import _parse_claude_conversation, extract_claude_meta
    from ..gemini import _parse_gemini_conversation, extract_gemini_meta

    PROVIDER_HANDLERS = {
        "chatgpt": (extract_chatgpt_meta, _parse_chatgpt_conversation),
        "claude": (extract_claude_meta, _parse_claude_conversation),
        "gemini": (extract_gemini_meta, _parse_gemini_conversation),
    }

    console.print(f"[blue]Ensuring database '{db}' exists...[/blue]")
    ensure_database(db)

    # Load Gemini manifest for title lookup (raw files lack titles)
    gemini_titles = {}
    gemini_manifest_path = os.path.expanduser(
        "~/.aishell/gemini/conversations/manifest.json"
    )
    if os.path.exists(gemini_manifest_path):
        with open(gemini_manifest_path) as f:
            gm = json.load(f)
        gemini_titles = {
            c["source_id"]: c["title"] for c in gm.get("conversations", [])
        }

    # Determine which provider dirs to scan
    if provider:
        dirs_to_scan = {provider: RAW_PROVIDERS[provider]}
    else:
        dirs_to_scan = RAW_PROVIDERS

    # Gather raw JSON files from all relevant dirs
    all_files = []
    for prov_name, prov_dir in dirs_to_scan.items():
        if not os.path.isdir(prov_dir):
            continue
        files = sorted(globmod.glob(os.path.join(prov_dir, "*.json")))
        for f in files:
            all_files.append((prov_name, f))

    if not all_files:
        console.print("[yellow]No raw conversation files found.[/yellow]")
        if provider:
            console.print(f"[dim]Directory checked: {RAW_PROVIDERS[provider]}[/dim]")
        else:
            console.print("[dim]Directories checked:[/dim]")
            for name, d in RAW_PROVIDERS.items():
                exists = (
                    "[green]exists[/green]"
                    if os.path.isdir(d)
                    else "[dim]not found[/dim]"
                )
                console.print(f"  {name}: {d} ({exists})")
        return

    console.print(
        f"[blue]Loading {len(all_files)} raw conversation(s) into {db}...[/blue]"
    )

    conn = psycopg2.connect(dbname=db)
    loaded = 0
    skipped = 0
    embedded = 0

    import gc

    try:
        for prov_name, filepath in all_files:
            source_id = os.path.splitext(os.path.basename(filepath))[0]
            basename = os.path.basename(filepath)

            with open(filepath) as f:
                raw_data = json.load(f)

            extract_meta, parse_conv = PROVIDER_HANDLERS[prov_name]
            meta = extract_meta(raw_data)
            turns = parse_conv(raw_data)

            if not turns:
                del raw_data
                skipped += 1
                continue

            # Resolve title: meta → gemini manifest → fallback
            title = meta["title"]
            if not title and prov_name == "gemini":
                title = gemini_titles.get(source_id)
            if not title:
                title = f"Untitled ({source_id[:12]})"

            # Convert turns to JSONB-ready format
            jsonb_turns = [
                {
                    "role": t["role"],
                    "content": t["content"],
                    "timestamp": t.get("timestamp"),
                }
                for t in turns
            ]
            del turns  # free parsed turns (jsonb_turns is the copy we keep)

            if load_raw_conversation(
                conn,
                source=prov_name,
                source_id=source_id,
                title=title,
                raw_data=raw_data,
                turns=jsonb_turns,
                model=meta.get("model"),
                created_at=meta.get("created_at"),
                updated_at=meta.get("updated_at"),
            ):
                console.print(
                    f"  [green]Loaded[/green]: [{prov_name}] {basename} "
                    f"({len(jsonb_turns)} turns)"
                )
                loaded += 1
            else:
                skipped += 1

            del raw_data  # free large JSON immediately after DB insert

            # Embed chunks (content_hash dedup skips already-embedded chunks)
            if not skip_embeddings:
                n = embed_and_store_chunks(
                    conn, prov_name, source_id, title, jsonb_turns
                )
                embedded += n

            del jsonb_turns, meta
            gc.collect()

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
    if not skip_embeddings:
        summary.add_row("Chunks embedded", str(embedded))
    summary.add_row("Total files", str(loaded + skipped))
    console.print(summary)


@conversations.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", "-l", type=int, default=10, help="Max results")
@click.option(
    "--source",
    "-s",
    type=click.Choice(list(RAW_PROVIDERS.keys())),
    help="Filter by provider source",
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def search(query, limit, source, db):
    """Semantic search across all exported conversations.

    Uses nomic-embed-text-v1.5 to embed the query and find
    the most similar turns via cosine similarity (JSONB storage).

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

    # Embed query with search_query: prefix (MLX model, normalized in registry)
    model = get_model()
    query_embedding = model.encode(
        [f"search_query: {query_str}"],
        show_progress=False,
    ).tolist()[0]
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    conn = psycopg2.connect(dbname=db)
    try:
        with conn.cursor() as cur:
            if source:
                cur.execute(
                    """
                    SELECT
                        ce.role,
                        ce.chunk_text,
                        c.title,
                        c.source,
                        1 - (ce.embedding <=> %s::vector) AS similarity
                    FROM chunk_embeddings ce
                    JOIN conversations_raw c
                        ON ce.source = c.source AND ce.source_id = c.source_id
                    WHERE ce.embedding IS NOT NULL
                      AND c.source = %s
                    ORDER BY ce.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, source, emb_str, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        ce.role,
                        ce.chunk_text,
                        c.title,
                        c.source,
                        1 - (ce.embedding <=> %s::vector) AS similarity
                    FROM chunk_embeddings ce
                    JOIN conversations_raw c
                        ON ce.source = c.source AND ce.source_id = c.source_id
                    WHERE ce.embedding IS NOT NULL
                    ORDER BY ce.embedding <=> %s::vector
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

    table = Table(title=f'Search: "{query_str}"', show_lines=True)
    table.add_column("Sim", style="green", no_wrap=True)
    table.add_column("Src", style="magenta", no_wrap=True)
    table.add_column("Role", style="cyan", no_wrap=True)
    table.add_column("Conversation", style="blue", max_width=30)
    table.add_column("Content", style="white", ratio=2)

    for role, content, title, src, similarity in rows:
        preview = content[:300] + "..." if len(content) > 300 else content
        table.add_row(f"{similarity:.3f}", src, role, title[:30], preview)

    console.print(table)
