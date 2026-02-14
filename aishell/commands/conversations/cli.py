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

SKILL = {
    "name": "conversations",
    "description": "Load, browse, and search exported LLM conversations",
    "capabilities": [
        "Hybrid search (semantic + keyword) across all conversations",
        "Conversation-level keyword search with hit counts (-c flag)",
        "Interactive TUI browser with source filtering",
        "Load raw exports from Gemini, ChatGPT, Claude into PostgreSQL",
    ],
    "examples": [
        'aisearch "manifold geometry"',
        'aisearch "flatoon" -c',
        'aisearch "FDL" -s gemini -l 5',
        "aishell conversations browse",
        "aishell conversations browse -s gemini",
        "aishell conversations load",
        "aishell conversations load --provider chatgpt",
    ],
    "tools": [
        {
            "name": "search_conversations",
            "description": "Hybrid semantic + keyword search across exported LLM conversations",
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Search query",
                },
                "source": {
                    "type": "string",
                    "enum": ["gemini", "chatgpt", "claude"],
                    "description": "Filter by provider",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Max results",
                },
                "conversations": {
                    "type": "boolean",
                    "default": False,
                    "description": "Conversation-level search (-c flag)",
                },
            },
        },
        {
            "name": "browse_conversations",
            "description": "Launch interactive TUI for browsing conversations",
            "parameters": {
                "source": {
                    "type": "string",
                    "enum": ["gemini", "chatgpt", "claude"],
                    "description": "Pre-filter by provider",
                },
            },
        },
    ],
}

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
@click.option(
    "--source",
    "-s",
    type=click.Choice(list(RAW_PROVIDERS.keys())),
    help="Pre-filter by provider source",
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def browse(source, db):
    """Interactive TUI for browsing and searching conversations.

    Two-panel interface: conversation list (left) + turn viewer (right).
    Type / to search, 1/2/3 to filter by provider, q to quit.

    Examples:
        aishell conversations browse
        aishell conversations browse -s gemini
    """
    from .tui import ConversationBrowser

    app = ConversationBrowser(db_name=db, source_filter=source)
    app.run()


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
@click.option(
    "--conversations",
    "-c",
    "conv_mode",
    is_flag=True,
    help="List conversations containing the term (not individual chunks)",
)
def search(query, limit, source, db, conv_mode):
    """Hybrid search across all exported conversations.

    Combines semantic similarity (nomic-embed-text-v1.5) with keyword
    matching (ILIKE on chunk_text and title). Keyword fallback catches
    novel terms, acronyms, and coined words that embeddings miss.

    Use -c to list conversations containing a term instead of chunks.

    Examples:
        aisearch "manifold geometry"
        aisearch "flatoon" -s gemini
        aisearch "FDL" -c
    """
    import psycopg2

    query_str = " ".join(query)
    console.print(f"[blue]Searching for:[/blue] {query_str}")
    if source:
        console.print(f"[blue]Source filter:[/blue] {source}")

    # --- Conversation-level mode (-c flag) ---
    if conv_mode:
        from .db import search_conversations_by_keyword

        conn = psycopg2.connect(dbname=db)
        try:
            rows = search_conversations_by_keyword(
                conn, query_str, source=source, limit=limit
            )
        finally:
            conn.close()

        if not rows:
            console.print("[yellow]No conversations found.[/yellow]")
            return

        console.print(f'[dim]Conversations containing "{query_str}": {len(rows)}[/dim]')
        table = Table(title=f'Conversations: "{query_str}"', show_lines=True)
        table.add_column("#", style="dim", no_wrap=True)
        table.add_column("Title", style="blue", ratio=2)
        table.add_column("Src", style="magenta", no_wrap=True)
        table.add_column("Hits", style="green", no_wrap=True)
        table.add_column("Turns", style="cyan", no_wrap=True)

        for i, (title, src, source_id, hits, turn_count) in enumerate(rows, 1):
            table.add_row(str(i), title or "Untitled", src, str(hits), str(turn_count))

        console.print(table)
        return

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
            # --- Semantic search ---
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
            semantic_rows = cur.fetchall()

            # --- Keyword search (ILIKE on chunk_text and title) ---
            kw_pattern = f"%{query_str}%"
            if source:
                cur.execute(
                    """
                    SELECT
                        ce.role,
                        ce.chunk_text,
                        c.title,
                        c.source,
                        1.0 AS similarity
                    FROM chunk_embeddings ce
                    JOIN conversations_raw c
                        ON ce.source = c.source AND ce.source_id = c.source_id
                    WHERE (ce.chunk_text ILIKE %s OR c.title ILIKE %s)
                      AND c.source = %s
                    LIMIT %s
                    """,
                    (kw_pattern, kw_pattern, source, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        ce.role,
                        ce.chunk_text,
                        c.title,
                        c.source,
                        1.0 AS similarity
                    FROM chunk_embeddings ce
                    JOIN conversations_raw c
                        ON ce.source = c.source AND ce.source_id = c.source_id
                    WHERE ce.chunk_text ILIKE %s OR c.title ILIKE %s
                    LIMIT %s
                    """,
                    (kw_pattern, kw_pattern, limit),
                )
            keyword_rows = cur.fetchall()
    finally:
        conn.close()

    # --- Merge and deduplicate ---
    # Key: (source, title, chunk_text[:100]) — unique enough to dedup
    # Value: (role, chunk_text, title, source, similarity, match_type)
    merged = {}
    sem_keys = set()

    for role, content, title, src, similarity in semantic_rows:
        key = (src, title, content[:100])
        merged[key] = (role, content, title, src, similarity, "sem")
        sem_keys.add(key)

    for role, content, title, src, similarity in keyword_rows:
        key = (src, title, content[:100])
        if key in sem_keys:
            # Already present from semantic — upgrade to "both", keep higher score
            existing = merged[key]
            best_sim = max(existing[4], similarity)
            merged[key] = (role, content, title, src, best_sim, "both")
        elif key not in merged:
            merged[key] = (role, content, title, src, similarity, "kw")

    # Sort by similarity descending, cap at limit
    results = sorted(merged.values(), key=lambda r: r[4], reverse=True)[:limit]

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    n_sem = sum(1 for r in results if r[5] == "sem")
    n_kw = sum(1 for r in results if r[5] == "kw")
    n_both = sum(1 for r in results if r[5] == "both")
    console.print(
        f"[dim]Results: {len(results)} total "
        f"({n_sem} semantic, {n_kw} keyword, {n_both} both)[/dim]"
    )

    table = Table(title=f'Search: "{query_str}"', show_lines=True)
    table.add_column("Sim", style="green", no_wrap=True)
    table.add_column("Match", style="yellow", no_wrap=True)
    table.add_column("Src", style="magenta", no_wrap=True)
    table.add_column("Role", style="cyan", no_wrap=True)
    table.add_column("Conversation", style="blue", max_width=30)
    table.add_column("Content", style="white", ratio=2)

    for role, content, title, src, similarity, match_type in results:
        preview = content[:300] + "..." if len(content) > 300 else content
        table.add_row(f"{similarity:.3f}", match_type, src, role, title[:30], preview)

    console.print(table)
