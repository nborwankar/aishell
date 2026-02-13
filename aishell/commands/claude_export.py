"""Claude conversation import from data export ZIP and browser-based pull.

Subcommands:
    aishell claude login              # Launch Chrome for Claude sign-in
    aishell claude pull               # Download conversations via API
    aishell claude import <zip_path>  # Parse Claude data export ZIP
"""

import json
import logging
import os
import time
import zipfile
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from .conversations.schema import slugify, convert_to_schema
from .conversations.manifest import load_manifest, save_manifest, already_exported
from .conversations.browser import (
    chrome_launch,
    chrome_login,
    check_auth,
    fetch_json,
)

console = Console()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.expanduser("~/.aishell/claude")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
MANIFEST_PATH = os.path.join(CONVERSATIONS_DIR, "manifest.json")

CLAUDE_AUTH_INDICATORS = ["login", "accounts.google.com", "/oauth/"]
CLAUDE_API_BASE = "https://claude.ai/api"


# ── Parsing helpers (shared by import and pull) ──────────────────────


def _parse_claude_conversation(conv_raw):
    """Parse a single Claude conversation dict into schema turns.

    Claude exports have a linear `chat_messages` array with:
    - sender: "human" or "assistant"
    - text: message content
    - created_at: ISO 8601 timestamp
    """
    messages = conv_raw.get("chat_messages", [])
    turns = []

    for msg in messages:
        sender = msg.get("sender", "")
        text = msg.get("text", "")

        if not text or not text.strip():
            continue

        # Map Claude roles to universal roles
        if sender == "human":
            role = "user"
        elif sender == "assistant":
            role = "assistant"
        else:
            continue

        timestamp = msg.get("created_at")

        turns.append(
            {
                "role": role,
                "content": text.strip(),
                "timestamp": timestamp,
            }
        )

    return turns


def extract_claude_meta(raw):
    """Extract metadata from a raw Claude conversation JSON."""
    title = raw.get("name", raw.get("title", "Untitled")) or "Untitled"
    created_at = raw.get("created_at")
    updated_at = raw.get("updated_at")
    model = raw.get("model")

    return {
        "title": title,
        "created_at": created_at,
        "updated_at": updated_at,
        "model": model,
    }


def _extract_org_id(page):
    """Extract Claude organization ID from the API.

    Claude requires an org_id for all conversation API calls.
    Tries the /api/organizations endpoint first, then falls back
    to URL parsing.

    Returns:
        Organization UUID string, or None if extraction fails.
    """
    # Strategy 1: API endpoint
    try:
        orgs = fetch_json(page, f"{CLAUDE_API_BASE}/organizations")
        if isinstance(orgs, list) and orgs:
            org_id = orgs[0].get("uuid", orgs[0].get("id", ""))
            if org_id:
                logger.info(f"Got org_id from API: {org_id}")
                return org_id
    except RuntimeError as e:
        logger.debug(f"Organizations API failed: {e}")

    # Strategy 2: Parse from page URL (claude.ai/chat/ pattern)
    current_url = page.url
    # Some Claude URLs embed org info; this is a fallback
    import re

    match = re.search(r"/organizations/([a-f0-9-]+)", current_url)
    if match:
        org_id = match.group(1)
        logger.info(f"Got org_id from URL: {org_id}")
        return org_id

    return None


# ── Click command group ──────────────────────────────────────────────


@click.group(name="claude")
def claude_export():
    """Import or pull Claude conversations."""
    pass


# ── Login command ────────────────────────────────────────────────────


@claude_export.command()
def login():
    """Launch Chrome for Claude sign-in.

    Opens Chrome with a persistent profile at ~/chromeuserdata.
    Sign into Claude, then close Chrome when done.
    """
    chrome_login(
        url="https://claude.ai",
        message="Sign into Claude, then close Chrome when done.",
        console=console,
    )
    console.print("You can now run [cyan]aishell claude pull[/cyan].")


# ── Pull command ─────────────────────────────────────────────────────


@claude_export.command()
@click.option(
    "--max", "max_count", type=int, default=0, help="Max conversations (0=all)"
)
@click.option("--resume", is_flag=True, help="Skip already-exported conversations")
@click.option("--dry-run", is_flag=True, help="List conversations without extracting")
@click.option(
    "--delay", type=float, default=2.0, help="Delay between API calls (seconds)"
)
def pull(max_count, resume, dry_run, delay):
    """Download Claude conversations via browser API.

    Connects to Chrome via CDP, calls Claude's internal API using
    the authenticated browser session, and saves each conversation
    to ~/.aishell/claude/.

    Requires: aishell claude login (once)
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

            console.print("[blue]Navigating to claude.ai...[/blue]")
            page.goto(
                "https://claude.ai",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(3)

            # Auth check
            if not check_auth(page, CLAUDE_AUTH_INDICATORS):
                console.print(
                    "[red]Not logged in! Run 'aishell claude login' first.[/red]"
                )
                page.close()
                browser.close()
                return

            # Extract org_id (required for Claude API calls)
            console.print("[blue]Extracting organization ID...[/blue]")
            org_id = _extract_org_id(page)
            if not org_id:
                console.print(
                    "[red]Could not determine Claude organization ID.[/red]\n"
                    "[dim]Try navigating to claude.ai in Chrome first.[/dim]"
                )
                page.close()
                browser.close()
                return
            console.print(f"  Organization: [cyan]{org_id}[/cyan]")

            # Fetch conversation list
            console.print("[blue]Fetching conversation list...[/blue]")
            list_url = f"{CLAUDE_API_BASE}/organizations/{org_id}/chat_conversations"
            try:
                all_conversations = fetch_json(page, list_url)
            except RuntimeError as e:
                console.print(f"[red]API error: {e}[/red]")
                page.close()
                browser.close()
                return

            if not isinstance(all_conversations, list):
                # Some API versions wrap in an object
                all_conversations = all_conversations.get(
                    "conversations",
                    all_conversations.get("items", []),
                )

            console.print(
                f"Found [green]{len(all_conversations)}[/green] conversations"
            )

            if not all_conversations:
                console.print("[yellow]No conversations found.[/yellow]")
                page.close()
                browser.close()
                return

            # Filter already-exported if resuming
            if resume:
                before = len(all_conversations)
                all_conversations = [
                    c
                    for c in all_conversations
                    if not already_exported(c.get("uuid", c.get("id", "")), RAW_DIR)
                ]
                skipped = before - len(all_conversations)
                if skipped:
                    console.print(
                        f"[dim]Resuming: skipping {skipped} already-exported[/dim]"
                    )

            # Apply max limit
            if max_count > 0:
                all_conversations = all_conversations[:max_count]

            # Dry run: list, save scan, and exit
            if dry_run:
                table = Table(title="Claude Conversations")
                table.add_column("#", style="dim", width=4)
                table.add_column("ID", style="cyan", width=20)
                table.add_column("Status", width=6)
                table.add_column("Title", style="white")

                scan_entries = []
                for i, conv in enumerate(all_conversations, 1):
                    cid = conv.get("uuid", conv.get("id", ""))
                    exported = already_exported(cid, RAW_DIR)
                    status = "[green]DONE[/green]" if exported else ""
                    title = (
                        conv.get("name", conv.get("title", "Untitled")) or "Untitled"
                    )
                    table.add_row(str(i), cid[:20], status, title[:60])
                    scan_entries.append(
                        {
                            "source_id": cid,
                            "title": title,
                            "exported": exported,
                        }
                    )

                already_count = sum(1 for e in scan_entries if e["exported"])
                new_count = len(scan_entries) - already_count

                console.print(table)
                console.print(
                    f"\nTotal: {len(all_conversations)} conversations "
                    f"({already_count} exported, {new_count} new)"
                )

                scan_path = os.path.join(DATA_DIR, "scan.json")
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

            # Fetch each conversation detail
            manifest = load_manifest(MANIFEST_PATH)
            manifest_ids = {c["source_id"] for c in manifest["conversations"]}
            results = {"success": 0, "failed": 0, "skipped": 0}

            for i, conv_info in enumerate(all_conversations, 1):
                source_id = conv_info.get("uuid", conv_info.get("id", ""))
                title = (
                    conv_info.get("name", conv_info.get("title", "Untitled"))
                    or "Untitled"
                )
                console.print(f"[{i}/{len(all_conversations)}] {title[:60]}...")

                try:
                    # Fetch full conversation detail
                    detail_url = (
                        f"{CLAUDE_API_BASE}/organizations/{org_id}"
                        f"/chat_conversations/{source_id}"
                    )
                    conv_raw = fetch_json(page, detail_url)

                    # Save raw response
                    raw_path = os.path.join(RAW_DIR, f"{source_id}.json")
                    with open(raw_path, "w") as f:
                        json.dump(conv_raw, f, indent=2, ensure_ascii=False)

                    # Parse using existing linear parser
                    turns = _parse_claude_conversation(conv_raw)

                    if not turns:
                        console.print(f"  [yellow]No turns found, skipping[/yellow]")
                        results["skipped"] += 1
                        continue

                    # Get creation time and model from conversation metadata
                    created_at = conv_raw.get("created_at")
                    model = conv_raw.get("model")

                    # Convert to schema
                    converted = convert_to_schema(
                        source="claude",
                        source_id=source_id,
                        title=title,
                        turns=turns,
                        model=model,
                        created_at=created_at,
                    )

                    # Save with collision handling
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
                if i < len(all_conversations):
                    time.sleep(delay)

            # Save manifest
            save_manifest(manifest, MANIFEST_PATH, CONVERSATIONS_DIR)

            # Summary
            total = results["success"] + results["failed"] + results["skipped"]
            console.print()
            summary = Table(title="Claude Pull Summary")
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


# ── Import command (from ZIP) ────────────────────────────────────────


@claude_export.command(name="import")
@click.argument("zip_path", type=click.Path(exists=True))
def import_zip(zip_path):
    """Import conversations from a Claude data export ZIP.

    Claude exports contain JSON files with linear chat_messages arrays.
    This command handles both a single conversations.json and individual
    conversation JSON files within the ZIP.

    Examples:
        aishell claude import ~/Downloads/claude-export.zip
    """
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    console.print(f"[blue]Opening ZIP:[/blue] {zip_path}")

    conversations_raw = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Strategy 1: Look for conversations.json (array of conversations)
        for name in zf.namelist():
            if name.endswith("conversations.json"):
                console.print(f"[blue]Found:[/blue] {name}")
                with zf.open(name) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    conversations_raw = data
                break

        # Strategy 2: Look for individual JSON files if no conversations.json
        if not conversations_raw:
            for name in zf.namelist():
                if name.endswith(".json") and not name.startswith("__"):
                    try:
                        with zf.open(name) as f:
                            data = json.load(f)
                        # Check if it looks like a conversation
                        if isinstance(data, dict) and "chat_messages" in data:
                            conversations_raw.append(data)
                            console.print(f"[blue]Found conversation:[/blue] {name}")
                    except (json.JSONDecodeError, KeyError):
                        continue

    if not conversations_raw:
        console.print("[red]No conversation data found in ZIP.[/red]")
        return

    console.print(
        f"[blue]Processing {len(conversations_raw)} conversation(s)...[/blue]"
    )

    manifest = load_manifest(MANIFEST_PATH)
    manifest_ids = {c["source_id"] for c in manifest["conversations"]}
    results = {"success": 0, "skipped": 0, "empty": 0}

    for conv_raw in conversations_raw:
        title = conv_raw.get("name", conv_raw.get("title", "Untitled"))
        source_id = conv_raw.get("uuid", conv_raw.get("id", ""))

        if not source_id:
            results["skipped"] += 1
            continue

        # Skip if already in manifest
        if source_id in manifest_ids:
            results["skipped"] += 1
            continue

        # Parse linear messages
        turns = _parse_claude_conversation(conv_raw)

        if not turns:
            results["empty"] += 1
            continue

        # Get creation time from conversation metadata
        created_at = conv_raw.get("created_at")

        # Get model from conversation metadata
        model = conv_raw.get("model")

        # Convert to schema
        converted = convert_to_schema(
            source="claude",
            source_id=source_id,
            title=title,
            turns=turns,
            model=model,
            created_at=created_at,
        )

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
    summary = Table(title="Claude Import Summary")
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
