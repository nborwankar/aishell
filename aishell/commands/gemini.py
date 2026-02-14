"""Gemini conversation export via Chrome CDP browser automation.

Subcommands:
    aishell gemini login                # Launch Chrome for Google sign-in
    aishell gemini pull                 # Download all conversations
    aishell gemini import [raw_path]    # Re-process raw JSON files
"""

import glob as globmod
import json
import logging
import os
import time
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from .conversations.schema import slugify, convert_to_schema, ROLE_MAP
from .conversations.manifest import load_manifest, save_manifest, already_exported
from .conversations.browser import (
    CHROME_USER_DATA_DIR,
    CHROME_DEBUG_PORT,
    is_debug_port_open,
    chrome_quit,
    chrome_launch,
    chrome_login,
)

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

RATE_LIMIT_DELAY = 5.0


# ── Extraction helpers ────────────────────────────────────────────────


def _expand_sidebar(page):
    """Expand the Gemini sidebar if it's collapsed."""
    expanded = page.evaluate(
        """() => {
        // Try multiple selectors for the sidebar toggle
        const selectors = [
            'button[aria-label*="menu" i]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="navigation" i]',
            'button[aria-label*="open" i][aria-label*="nav" i]',
            'button[data-panel-id]',
            '[role="navigation"] button',
            'mat-icon-button[aria-label]',
        ];
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn) {
                btn.click();
                return {found: true, selector: sel, label: btn.getAttribute('aria-label') || ''};
            }
        }
        // Fallback: look for any button whose aria-label contains "menu"
        const allBtns = document.querySelectorAll('button');
        for (const btn of allBtns) {
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            if (label.includes('menu') || label.includes('sidebar') || label.includes('navigation')) {
                btn.click();
                return {found: true, selector: 'fallback', label: btn.getAttribute('aria-label') || ''};
            }
        }
        return {found: false, selector: null, label: null};
    }"""
    )
    if expanded["found"]:
        logger.info(
            f"Sidebar toggle clicked: {expanded['label']} ({expanded['selector']})"
        )
        time.sleep(2)  # Wait for sidebar animation
    else:
        logger.info("No sidebar toggle found — sidebar may already be expanded")
    return expanded["found"]


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
                const title = a.innerText.trim()
                    || a.getAttribute('aria-label') || ''
                    || a.getAttribute('title') || ''
                    || a.closest('[aria-label]')?.getAttribute('aria-label') || '';
                results.push({
                    source_id: match[1],
                    title: title.substring(0, 200),
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


# ── Gemini-specific conversion ───────────────────────────────────────


def _clean_turn_text(text, role):
    """Remove 'You said\\n' / 'Gemini said\\n' prefixes from DOM scraping."""
    if role == "user" and text.startswith("You said\n"):
        return text[len("You said\n") :].strip()
    if role == "assistant" and text.startswith("Gemini said\n"):
        return text[len("Gemini said\n") :].strip()
    return text.strip()


def _parse_gemini_conversation(raw):
    """Parse raw Gemini extraction data into linearized turns."""
    raw_turns = raw.get("turns", [])
    turns = []
    for raw_turn in raw_turns:
        raw_role = raw_turn.get("role", "unknown")
        role = ROLE_MAP.get(raw_role, raw_role)
        content = _clean_turn_text(raw_turn.get("text", ""), role)
        if content:
            turns.append({"role": role, "content": content, "timestamp": None})
    return turns


def extract_gemini_meta(raw):
    """Extract metadata from a raw Gemini conversation JSON."""
    return {
        "title": None,
        "created_at": None,
        "updated_at": None,
        "model": raw.get("model"),
    }


def _convert_raw(raw_data, title, source_id=None, source_url=None, model=None):
    """Convert raw Gemini extraction data to schema-compliant format."""
    raw_turns = raw_data.get("turns", [])

    turns = []
    for raw_turn in raw_turns:
        raw_role = raw_turn.get("role", "unknown")
        role = ROLE_MAP.get(raw_role, raw_role)
        content = _clean_turn_text(raw_turn.get("text", ""), role)
        turns.append({"role": role, "content": content})

    if source_url is None and source_id:
        source_url = f"https://gemini.google.com/app/{source_id}"

    return convert_to_schema(
        source="gemini",
        source_id=source_id or title,
        title=title,
        turns=turns,
        source_url=source_url,
        model=model,
        extra_metadata={
            "extraction_strategy": raw_data.get("strategy", "unknown"),
            "raw_turn_count": raw_data.get("count", len(raw_turns)),
        },
    )


SKILL = {
    "name": "gemini",
    "description": "Export Gemini conversations via Chrome browser automation",
    "capabilities": [
        "Browser login to Gemini via Chrome CDP",
        "Pull conversations using DOM scraping (4 extraction strategies)",
        "Import from local raw JSON files",
    ],
    "examples": [
        "aishell gemini login",
        "aishell gemini pull",
        "aishell gemini pull --max 50 --dry-run",
        "aishell gemini import",
    ],
    "tools": [
        {
            "name": "pull_gemini",
            "description": "Download Gemini conversations via browser automation",
            "parameters": {
                "max_count": {
                    "type": "integer",
                    "default": 200,
                    "description": "Max conversations to pull",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "Scan only, don't download",
                },
            },
        },
    ],
}

# ── Click command group ───────────────────────────────────────────────


@click.group()
def gemini():
    """Export Gemini conversations via Chrome browser automation."""
    pass


@gemini.command()
def login():
    """Launch Chrome with debug port for Google sign-in.

    Opens Chrome with a persistent profile at ~/chromeuserdata.
    Sign into your Google account, then close Chrome when done.
    """
    chrome_login(
        url="https://accounts.google.com",
        message="Sign into Google, then close Chrome when done.",
        console=console,
    )
    console.print("You can now run [cyan]aishell gemini pull[/cyan].")


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
    chrome_proc = chrome_launch()

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

            # Expand sidebar if collapsed
            _expand_sidebar(page)

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
                    c
                    for c in conversations
                    if not already_exported(c["source_id"], RAW_DIR)
                ]
                skipped = before - len(conversations)
                if skipped:
                    console.print(
                        f"[dim]Resuming: skipping {skipped} already-exported[/dim]"
                    )

            # Apply max limit
            if max_count > 0:
                conversations = conversations[:max_count]

            # Dry run: list, save scan, and exit
            if dry_run:
                table = Table(title="Gemini Conversations")
                table.add_column("#", style="dim", width=4)
                table.add_column("Source ID", style="cyan", width=20)
                table.add_column("Status", width=6)
                table.add_column("Title", style="white")

                scan_entries = []
                for i, conv in enumerate(conversations, 1):
                    exported = already_exported(conv["source_id"], RAW_DIR)
                    status = "[green]DONE[/green]" if exported else ""
                    table.add_row(str(i), conv["source_id"], status, conv["title"][:60])
                    scan_entries.append(
                        {
                            "source_id": conv["source_id"],
                            "title": conv["title"],
                            "exported": exported,
                        }
                    )

                already_count = sum(1 for e in scan_entries if e["exported"])
                new_count = len(scan_entries) - already_count

                console.print(table)
                console.print(
                    f"\nTotal: {len(conversations)} conversations "
                    f"({already_count} exported, {new_count} new)"
                )

                # Save scan results for sizing assessment
                scan_path = os.path.join(DATA_DIR, "scan.json")
                os.makedirs(DATA_DIR, exist_ok=True)
                scan_data = {
                    "scanned_at": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "total": len(scan_entries),
                    "exported": already_count,
                    "new": new_count,
                    "conversations": scan_entries,
                }
                with open(scan_path, "w") as f:
                    json.dump(scan_data, f, indent=2, ensure_ascii=False)
                console.print(f"[dim]Scan saved: {scan_path}[/dim]")

                page.close()
                browser.close()
                return

            # Extract each conversation
            manifest = load_manifest(MANIFEST_PATH)
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
                    slug = slugify(title)
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
            save_manifest(manifest, MANIFEST_PATH, CONVERSATIONS_DIR)

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


# ── Import command (re-process raw JSONs) ────────────────────────────


@gemini.command(name="import")
@click.argument("raw_path", required=False, default=None)
def import_raw(raw_path):
    """Re-process raw Gemini JSON files into schema-compliant conversations.

    Takes raw JSON files previously saved by 'gemini pull' (from the raw/
    directory) and converts them to schema format. Useful for re-importing
    after parser improvements or from a different machine.

    RAW_PATH can be a single .json file, a directory of .json files, or
    omitted to use the default ~/.aishell/gemini/raw/ directory.

    Examples:
        aishell gemini import
        aishell gemini import ~/.aishell/gemini/raw/
        aishell gemini import ~/backup/gemini/17299a597166054b.json
    """
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    # Resolve input files
    if raw_path is None:
        raw_path = RAW_DIR

    raw_path = os.path.expanduser(raw_path)

    if os.path.isfile(raw_path):
        json_files = [raw_path]
    elif os.path.isdir(raw_path):
        json_files = sorted(globmod.glob(os.path.join(raw_path, "*.json")))
    else:
        console.print(f"[red]Path not found: {raw_path}[/red]")
        return

    if not json_files:
        console.print(f"[yellow]No JSON files found in {raw_path}[/yellow]")
        return

    console.print(
        f"[blue]Processing {len(json_files)} raw file(s) from:[/blue] {raw_path}"
    )

    # Load existing manifest for title lookup and dedup
    manifest = load_manifest(MANIFEST_PATH)
    title_lookup = {c["source_id"]: c["title"] for c in manifest["conversations"]}
    manifest_ids = {c["source_id"] for c in manifest["conversations"]}
    results = {"success": 0, "skipped": 0, "empty": 0}

    for filepath in json_files:
        source_id = os.path.splitext(os.path.basename(filepath))[0]

        # Skip if already in manifest
        if source_id in manifest_ids:
            results["skipped"] += 1
            continue

        try:
            with open(filepath) as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"  [red]Error reading {filepath}: {e}[/red]")
            results["empty"] += 1
            continue

        if raw_data.get("count", 0) == 0:
            results["empty"] += 1
            continue

        # Title: from manifest lookup, or derive from source_id
        title = title_lookup.get(source_id, f"Gemini ({source_id})")

        # Convert to schema
        converted = _convert_raw(raw_data, title=title, source_id=source_id)

        # Save with collision handling
        slug = slugify(title)
        conv_path = os.path.join(CONVERSATIONS_DIR, f"{slug}.json")
        if os.path.exists(conv_path):
            slug = f"{slug}-{source_id[:8]}"
            conv_path = os.path.join(CONVERSATIONS_DIR, f"{slug}.json")

        with open(conv_path, "w") as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)

        stats = converted["statistics"]
        console.print(
            f"  [green]OK[/green]: {title[:50]} "
            f"({stats['turn_count']} turns, {stats['total_chars']:,} chars)"
        )

        # Update manifest
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

    # Save manifest
    save_manifest(manifest, MANIFEST_PATH, CONVERSATIONS_DIR)

    # Summary
    console.print()
    summary = Table(title="Gemini Import Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", style="green")
    summary.add_row("Imported", str(results["success"]))
    summary.add_row("Skipped", str(results["skipped"]))
    summary.add_row("Empty", str(results["empty"]))
    summary.add_row(
        "Total", str(results["success"] + results["skipped"] + results["empty"])
    )
    console.print(summary)
    console.print(f"[dim]Data: {CONVERSATIONS_DIR}[/dim]")
