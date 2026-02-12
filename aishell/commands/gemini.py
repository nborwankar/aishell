"""Gemini conversation export, storage, and semantic search.

Subcommands:
    aishell gemini login       # Launch Chrome for Google sign-in
    aishell gemini pull        # Download all conversations
    aishell gemini load        # Load into PostgreSQL with embeddings
    aishell gemini search "q"  # Semantic search across conversations
"""

import hashlib
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

console = Console()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────

DATA_DIR = os.path.expanduser("~/.aishell/gemini")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
MANIFEST_PATH = os.path.join(CONVERSATIONS_DIR, "manifest.json")

CHROME_USER_DATA_DIR = os.path.expanduser("~/chromeuserdata")
CHROME_DEBUG_PORT = 9222
DB_NAME = "conversation_export"
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
RATE_LIMIT_DELAY = 5.0

# Role normalization: provider-specific → universal
ROLE_MAP = {
    "model": "assistant",
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "human": "user",
}

# Lazy-loaded embedding model
_model = None


# ── Chrome helpers ────────────────────────────────────────────────────


def _is_debug_port_open(port=CHROME_DEBUG_PORT):
    """Check if Chrome's CDP port is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _chrome_quit():
    """Gracefully quit Chrome via AppleScript."""
    subprocess.run(
        ["osascript", "-e", 'tell application "Google Chrome" to quit'],
        capture_output=True,
    )
    for _ in range(10):
        time.sleep(1)
        check = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
        if check.returncode != 0:
            break
    time.sleep(1)


def _chrome_launch(port=CHROME_DEBUG_PORT):
    """Launch Chrome with remote debugging. Returns Popen or None if reusing."""
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    if _is_debug_port_open(port):
        logger.info(f"Chrome debug port {port} already open, reusing")
        return None

    # Quit Chrome if running without debug port
    result = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
    if result.returncode == 0:
        logger.info("Chrome running without debug port — quitting it gracefully...")
        _chrome_quit()

    proc = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"Chrome launched (pid={proc.pid}), waiting for debug port...")

    for _ in range(15):
        time.sleep(1)
        if _is_debug_port_open(port):
            logger.info(f"Debug port {port} ready")
            return proc

    logger.warning(f"Debug port {port} not responding after 15s, proceeding anyway")
    return proc


# ── Extraction helpers ────────────────────────────────────────────────


def _enumerate_conversations(page):
    """Find all conversation links in the Gemini sidebar."""
    return page.evaluate(
        """() => {
        const links = document.querySelectorAll('a[href*="/app/"]');
        const results = [];
        const seen = new Set();
        for (const a of links) {
            const href = a.getAttribute('href') || '';
            const match = href.match(/\\/app\\/([a-f0-9]{10,})/);
            if (match && !seen.has(match[1])) {
                seen.add(match[1]);
                results.push({
                    source_id: match[1],
                    title: a.innerText.trim().substring(0, 200),
                    href: href
                });
            }
        }
        return results;
    }"""
    )


def _scroll_to_load_all(page, container_selector="main", max_scrolls=10):
    """Scroll to trigger lazy-loading of full conversation content."""
    for _ in range(max_scrolls):
        prev_height = page.evaluate(
            f"""() => {{
            const el = document.querySelector('{container_selector}')
                       || document.querySelector('[role="main"]')
                       || document.documentElement;
            const h = el.scrollHeight;
            el.scrollTop = el.scrollHeight;
            return h;
        }}"""
        )
        time.sleep(1)
        new_height = page.evaluate(
            f"""() => {{
            const el = document.querySelector('{container_selector}')
                       || document.querySelector('[role="main"]')
                       || document.documentElement;
            return el.scrollHeight;
        }}"""
        )
        if new_height == prev_height:
            break

    page.evaluate(
        f"""() => {{
        const el = document.querySelector('{container_selector}')
                   || document.querySelector('[role="main"]')
                   || document.documentElement;
        el.scrollTop = 0;
    }}"""
    )
    time.sleep(0.5)


def _extract_conversation(page):
    """Extract conversation turns from the current Gemini page."""
    return page.evaluate(
        """() => {
        const turns = [];

        // Strategy 1: <user-query> / <model-response> web components
        const uq = document.querySelectorAll('user-query');
        const mr = document.querySelectorAll('model-response');
        if (uq.length > 0 || mr.length > 0) {
            const all = [...document.querySelectorAll('user-query, model-response')];
            for (let i = 0; i < all.length; i++) {
                const el = all[i];
                const isUser = el.tagName.toLowerCase() === 'user-query';
                turns.push({
                    role: isUser ? 'user' : 'model',
                    index: i,
                    text: el.innerText.trim()
                });
            }
            return { strategy: 'web-components', count: turns.length, turns };
        }

        // Strategy 2: conversation-turn elements
        const ct = document.querySelectorAll('conversation-turn, .conversation-turn');
        if (ct.length > 0) {
            for (let i = 0; i < ct.length; i++) {
                turns.push({ role: 'unknown', index: i, text: ct[i].innerText.trim() });
            }
            return { strategy: 'conversation-turn', count: turns.length, turns };
        }

        // Strategy 3: data-message-id attributes
        const dm = document.querySelectorAll('[data-message-id]');
        if (dm.length > 0) {
            for (let i = 0; i < dm.length; i++) {
                turns.push({
                    role: dm[i].getAttribute('data-role') || 'unknown',
                    index: i,
                    text: dm[i].innerText.trim()
                });
            }
            return { strategy: 'data-message-id', count: turns.length, turns };
        }

        // Strategy 4: fallback to main content
        const main = document.querySelector('main') || document.querySelector('[role="main"]');
        if (main) {
            turns.push({ role: 'full_page', index: 0, text: main.innerText.trim() });
            return { strategy: 'fallback-main', count: 1, turns };
        }
        return { strategy: 'none', count: 0, turns: [] };
    }"""
    )


# ── Conversion helpers ────────────────────────────────────────────────


def _slugify(text, max_len=60):
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len]


def _generate_conv_id(source, source_id):
    """Generate a stable, platform-agnostic conversation ID."""
    raw = f"{source}:{source_id}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"conv_{digest}"


def _clean_turn_text(text, role):
    """Remove 'You said\\n' / 'Gemini said\\n' prefixes from DOM scraping."""
    if role == "user" and text.startswith("You said\n"):
        return text[len("You said\n") :].strip()
    if role == "assistant" and text.startswith("Gemini said\n"):
        return text[len("Gemini said\n") :].strip()
    return text.strip()


def _convert_raw(raw_data, title, source_id=None, source_url=None, model=None):
    """Convert raw extraction data to schema-compliant format."""
    raw_turns = raw_data.get("turns", [])

    turns = []
    for i, raw_turn in enumerate(raw_turns):
        raw_role = raw_turn.get("role", "unknown")
        role = ROLE_MAP.get(raw_role, raw_role)
        content = _clean_turn_text(raw_turn.get("text", ""), role)
        turns.append(
            {
                "turn_number": i + 1,
                "role": role,
                "content": content,
                "timestamp": None,
                "attachments": [],
                "metadata": {},
            }
        )

    user_turns = sum(1 for t in turns if t["role"] == "user")
    assistant_turns = sum(1 for t in turns if t["role"] == "assistant")
    total_chars = sum(len(t["content"]) for t in turns)

    if source_url is None and source_id:
        source_url = f"https://gemini.google.com/app/{source_id}"

    effective_source_id = source_id or hashlib.sha256(title.encode()).hexdigest()[:16]
    conv_id = _generate_conv_id("gemini", effective_source_id)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "schema_version": "1.0",
        "conversation": {
            "id": conv_id,
            "title": title,
            "source": "gemini",
            "source_id": source_id,
            "source_url": source_url,
            "model": model,
            "created_at": None,
            "exported_at": now_iso,
            "tags": [],
            "metadata": {
                "extraction_strategy": raw_data.get("strategy", "unknown"),
                "raw_turn_count": raw_data.get("count", len(raw_turns)),
            },
        },
        "turns": turns,
        "statistics": {
            "turn_count": len(turns),
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "total_chars": total_chars,
        },
    }


# ── Manifest helpers ──────────────────────────────────────────────────


def _load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"exported_at": None, "conversations": []}


def _save_manifest(manifest):
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    manifest["exported_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _already_exported(source_id):
    return os.path.exists(os.path.join(RAW_DIR, f"{source_id}.json"))


# ── Embedding helpers ─────────────────────────────────────────────────


def _get_model():
    """Load nomic-embed-text-v1.5 on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading {EMBEDDING_MODEL}...")
        _model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
        logger.info(f"Model loaded (dim={_model.get_sentence_embedding_dimension()})")
    return _model


def _embed_texts(texts):
    """Generate embeddings with search_document: prefix."""
    model = _get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(
        prefixed, show_progress_bar=False, normalize_embeddings=True
    )
    return embeddings.tolist()


# ── Database helpers ──────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('gemini', 'chatgpt', 'claude')),
    source_id       TEXT,
    source_url      TEXT,
    model           TEXT,
    created_at      TIMESTAMPTZ,
    exported_at     TIMESTAMPTZ NOT NULL,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    turn_count      INT NOT NULL DEFAULT 0,
    user_turns      INT NOT NULL DEFAULT 0,
    assistant_turns INT NOT NULL DEFAULT 0,
    total_chars     INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    id              SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_number     INT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    timestamp       TIMESTAMPTZ,
    attachments     JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    embedding       vector(768),
    UNIQUE (conversation_id, turn_number)
);

CREATE INDEX IF NOT EXISTS idx_turns_embedding
    ON turns USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_turns_conversation_id
    ON turns (conversation_id);
CREATE INDEX IF NOT EXISTS idx_turns_role
    ON turns (role);
CREATE INDEX IF NOT EXISTS idx_conversations_source
    ON conversations (source);
"""


def _ensure_database(db_name):
    """Create database, extension, and tables if they don't exist."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Check if database exists, create if not
    conn = psycopg2.connect(dbname="postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            logger.info(f"Creating database '{db_name}'...")
            cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()

    # Create extension and tables
    conn = psycopg2.connect(dbname=db_name)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        for statement in SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)
    conn.close()
    logger.info("Database schema verified")


def _load_conversation(conn, conv_data, skip_embeddings=False):
    """Load a single conversation into the database. Returns True if loaded."""
    import psycopg2
    from psycopg2.extras import execute_values

    conv = conv_data["conversation"]
    turns = conv_data["turns"]
    stats = conv_data["statistics"]

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM conversations WHERE id = %s", (conv["id"],))
        if cur.fetchone():
            return False

        cur.execute(
            """INSERT INTO conversations
               (id, title, source, source_id, source_url, model,
                created_at, exported_at, tags, metadata,
                turn_count, user_turns, assistant_turns, total_chars)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                conv["id"],
                conv["title"],
                conv["source"],
                conv.get("source_id"),
                conv.get("source_url"),
                conv.get("model"),
                conv.get("created_at"),
                conv["exported_at"],
                conv.get("tags", []),
                json.dumps(conv.get("metadata", {})),
                stats["turn_count"],
                stats["user_turns"],
                stats["assistant_turns"],
                stats["total_chars"],
            ),
        )

        contents = [t["content"] for t in turns]
        if skip_embeddings:
            embeddings = [None] * len(turns)
        else:
            embeddings = _embed_texts(contents)

        turn_rows = []
        for turn, emb in zip(turns, embeddings):
            emb_str = None
            if emb is not None:
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            turn_rows.append(
                (
                    conv["id"],
                    turn["turn_number"],
                    turn["role"],
                    turn["content"],
                    turn.get("timestamp"),
                    json.dumps(turn.get("attachments", [])),
                    json.dumps(turn.get("metadata", {})),
                    emb_str,
                )
            )

        execute_values(
            cur,
            """INSERT INTO turns
               (conversation_id, turn_number, role, content,
                timestamp, attachments, metadata, embedding)
               VALUES %s""",
            turn_rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s::vector)",
        )

    conn.commit()
    return True


# ── Click command group ───────────────────────────────────────────────


@click.group()
def gemini():
    """Export and search Gemini conversations."""
    pass


@gemini.command()
def login():
    """Launch Chrome with debug port for Google sign-in.

    Opens Chrome with a persistent profile at ~/chromeuserdata.
    Sign into your Google account, then close Chrome when done.
    """
    console.print("[blue]Launching Chrome for Google sign-in...[/blue]")

    # Quit existing Chrome
    result = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
    if result.returncode == 0:
        console.print("[yellow]Quitting existing Chrome...[/yellow]")
        _chrome_quit()

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    proc = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
            "https://accounts.google.com",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    console.print(f"[green]Chrome launched (pid={proc.pid})[/green]")
    console.print(f"  User data dir: {CHROME_USER_DATA_DIR}")
    console.print(f"  Debug port:    {CHROME_DEBUG_PORT}")
    console.print()
    console.print("Sign into Google, then close Chrome when done.")
    console.print("[dim]Waiting for Chrome to exit...[/dim]")

    proc.wait()
    console.print(
        "[green]Chrome closed. You can now run 'aishell gemini pull'.[/green]"
    )


@gemini.command()
@click.option(
    "--max", "max_count", type=int, default=0, help="Max conversations (0=all)"
)
@click.option("--resume", is_flag=True, help="Skip already-exported conversations")
@click.option("--dry-run", is_flag=True, help="List conversations without extracting")
@click.option(
    "--delay",
    type=float,
    default=RATE_LIMIT_DELAY,
    help="Delay between conversations (seconds)",
)
def pull(max_count, resume, dry_run, delay):
    """Download all Gemini conversations.

    Connects to Chrome via CDP, enumerates sidebar conversations,
    and extracts each one to ~/.aishell/gemini/.
    """
    from playwright.sync_api import sync_playwright

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    console.print("[blue]Launching Chrome with remote debugging...[/blue]")
    chrome_proc = _chrome_launch()

    try:
        with sync_playwright() as p:
            console.print("[blue]Connecting to Chrome via CDP...[/blue]")
            browser = p.chromium.connect_over_cdp(
                "http://127.0.0.1:9222", timeout=15000
            )
            context = browser.contexts[0]
            page = context.new_page()

            console.print("[blue]Navigating to gemini.google.com...[/blue]")
            page.goto(
                "https://gemini.google.com/app",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(5)

            # Auth check
            if "accounts.google" in page.url or "signin" in page.url.lower():
                console.print(
                    "[red]Not logged in! Run 'aishell gemini login' first.[/red]"
                )
                page.close()
                browser.close()
                return

            # Enumerate conversations
            console.print("[blue]Enumerating conversations in sidebar...[/blue]")
            conversations = _enumerate_conversations(page)
            console.print(f"Found [green]{len(conversations)}[/green] conversations")

            if not conversations:
                console.print(
                    "[yellow]No conversations found. Sidebar may not be loaded.[/yellow]"
                )
                page.close()
                browser.close()
                return

            # Filter already-exported if resuming
            if resume:
                before = len(conversations)
                conversations = [
                    c for c in conversations if not _already_exported(c["source_id"])
                ]
                skipped = before - len(conversations)
                if skipped:
                    console.print(
                        f"[dim]Resuming: skipping {skipped} already-exported[/dim]"
                    )

            # Apply max limit
            if max_count > 0:
                conversations = conversations[:max_count]

            # Dry run: list and exit
            if dry_run:
                table = Table(title="Gemini Conversations")
                table.add_column("#", style="dim", width=4)
                table.add_column("Source ID", style="cyan", width=20)
                table.add_column("Status", width=6)
                table.add_column("Title", style="white")

                for i, conv in enumerate(conversations, 1):
                    status = (
                        "[green]DONE[/green]"
                        if _already_exported(conv["source_id"])
                        else ""
                    )
                    table.add_row(str(i), conv["source_id"], status, conv["title"][:60])

                console.print(table)
                console.print(f"\nTotal: {len(conversations)} conversations")
                page.close()
                browser.close()
                return

            # Extract each conversation
            manifest = _load_manifest()
            manifest_ids = {c["source_id"] for c in manifest["conversations"]}
            results = {"success": 0, "failed": 0, "skipped": 0}

            for i, conv_info in enumerate(conversations, 1):
                source_id = conv_info["source_id"]
                title = conv_info["title"] or f"Untitled ({source_id})"
                console.print(f"[{i}/{len(conversations)}] {title[:60]}...")

                try:
                    url = f"https://gemini.google.com/app/{source_id}"
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)

                    _scroll_to_load_all(page)
                    raw_data = _extract_conversation(page)

                    if raw_data["count"] == 0:
                        console.print(f"  [yellow]No turns found, skipping[/yellow]")
                        results["skipped"] += 1
                        continue

                    # Save raw extraction
                    raw_path = os.path.join(RAW_DIR, f"{source_id}.json")
                    with open(raw_path, "w") as f:
                        json.dump(raw_data, f, indent=2, ensure_ascii=False)

                    # Convert to schema format
                    converted = _convert_raw(
                        raw_data, title=title, source_id=source_id, source_url=url
                    )

                    # Save converted (with collision handling)
                    slug = _slugify(title)
                    conv_path = os.path.join(CONVERSATIONS_DIR, f"{slug}.json")
                    if os.path.exists(conv_path) and source_id:
                        slug = f"{slug}-{source_id[:8]}"
                        conv_path = os.path.join(CONVERSATIONS_DIR, f"{slug}.json")

                    with open(conv_path, "w") as f:
                        json.dump(converted, f, indent=2, ensure_ascii=False)

                    stats = converted["statistics"]
                    console.print(
                        f"  [green]OK[/green]: {stats['turn_count']} turns, "
                        f"{stats['total_chars']:,} chars → {slug}.json"
                    )

                    # Update manifest
                    if source_id not in manifest_ids:
                        manifest["conversations"].append(
                            {
                                "source_id": source_id,
                                "title": title,
                                "conv_id": converted["conversation"]["id"],
                                "file": f"{slug}.json",
                                "turn_count": stats["turn_count"],
                                "total_chars": stats["total_chars"],
                                "exported_at": converted["conversation"]["exported_at"],
                            }
                        )
                        manifest_ids.add(source_id)

                    results["success"] += 1

                except Exception as e:
                    console.print(f"  [red]FAILED: {e}[/red]")
                    results["failed"] += 1

                # Rate limiting delay
                if i < len(conversations):
                    time.sleep(delay)

            # Save manifest
            _save_manifest(manifest)

            # Summary
            total = results["success"] + results["failed"] + results["skipped"]
            console.print()
            summary = Table(title="Pull Summary")
            summary.add_column("Metric", style="cyan")
            summary.add_column("Count", style="green")
            summary.add_row("Success", str(results["success"]))
            summary.add_row("Failed", str(results["failed"]))
            summary.add_row("Skipped", str(results["skipped"]))
            summary.add_row("Total", str(total))
            console.print(summary)
            console.print(f"[dim]Data: {DATA_DIR}[/dim]")

            page.close()
            browser.close()

    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        import traceback

        traceback.print_exc()
    finally:
        if chrome_proc:
            console.print("[dim]Done. You can close Chrome when ready.[/dim]")


@gemini.command()
@click.option(
    "--skip-embeddings", is_flag=True, help="Load without generating embeddings"
)
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def load(skip_embeddings, db):
    """Load conversations into PostgreSQL with embeddings.

    Auto-creates database, pgvector extension, and tables on first run.
    Skips conversations already in the database.
    """
    import glob as globmod
    import psycopg2

    # Ensure database and schema exist
    console.print(f"[blue]Ensuring database '{db}' exists...[/blue]")
    _ensure_database(db)

    # Gather conversation files
    files = sorted(globmod.glob(os.path.join(CONVERSATIONS_DIR, "*.json")))
    files = [f for f in files if not f.endswith("manifest.json")]

    if not files:
        console.print(
            "[yellow]No conversation files found in " f"{CONVERSATIONS_DIR}[/yellow]"
        )
        console.print("[dim]Run 'aishell gemini pull' first.[/dim]")
        return

    console.print(f"[blue]Loading {len(files)} conversation(s) into {db}...[/blue]")

    conn = psycopg2.connect(dbname=db)
    loaded = 0
    skipped = 0

    try:
        for filepath in files:
            basename = os.path.basename(filepath)
            with open(filepath) as f:
                data = json.load(f)

            if _load_conversation(conn, data, skip_embeddings=skip_embeddings):
                stats = data["statistics"]
                console.print(
                    f"  [green]Loaded[/green]: {basename} "
                    f"({stats['turn_count']} turns, {stats['total_chars']:,} chars)"
                )
                loaded += 1
            else:
                console.print(f"  [dim]Skipped[/dim]: {basename} (already loaded)")
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


@gemini.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", "-l", type=int, default=10, help="Max results")
@click.option("--db", default=DB_NAME, help=f"Database name (default: {DB_NAME})")
def search(query, limit, db):
    """Semantic search across Gemini conversations.

    Uses nomic-embed-text-v1.5 to embed the query and find
    the most similar turns via cosine similarity.

    Examples:
        aishell gemini search "manifold geometry"
        aishell gemini search "Lyapunov stability" --limit 5
    """
    import psycopg2

    query_str = " ".join(query)
    console.print(f"[blue]Searching for:[/blue] {query_str}")

    # Embed query with search_query: prefix
    model = _get_model()
    query_embedding = model.encode(
        [f"search_query: {query_str}"],
        show_progress_bar=False,
        normalize_embeddings=True,
    ).tolist()[0]
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    conn = psycopg2.connect(dbname=db)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.role,
                    t.content,
                    c.title,
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
    table.add_column("Role", style="cyan", width=10)
    table.add_column("Conversation", style="blue", width=30)
    table.add_column("Content", style="white", width=60, no_wrap=False)

    for role, content, title, similarity in rows:
        preview = content[:200] + "..." if len(content) > 200 else content
        table.add_row(f"{similarity:.3f}", role, title[:30], preview)

    console.print(table)
