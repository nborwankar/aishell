"""ChatGPT conversation import from data export ZIP and browser-based pull.

Subcommands:
    aishell chatgpt login              # Launch Chrome for ChatGPT sign-in
    aishell chatgpt pull               # Download conversations via API
    aishell chatgpt import <zip_path>  # Parse ChatGPT data export ZIP
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

DATA_DIR = os.path.expanduser("~/.aishell/chatgpt")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
MANIFEST_PATH = os.path.join(CONVERSATIONS_DIR, "manifest.json")

CHATGPT_AUTH_INDICATORS = ["auth0.com", "login.openai.com", "/auth/"]
CHATGPT_API_BASE = "https://chatgpt.com/backend-api"


def _get_access_token(page):
    """Fetch the ChatGPT access token from the session endpoint.

    ChatGPT's backend API requires a Bearer token in the Authorization
    header. The token is obtained from /api/auth/session using the
    browser's session cookies.

    Returns:
        Access token string, or None if unavailable.
    """
    result = page.evaluate(
        """async () => {
        try {
            const resp = await fetch('/api/auth/session', {credentials: 'include'});
            if (!resp.ok) return null;
            const data = await resp.json();
            return data.accessToken || null;
        } catch(e) {
            return null;
        }
    }"""
    )
    return result


# ── Parsing helpers (shared by import and pull) ──────────────────────


def _find_root_id(mapping):
    """Find the root node (parent == null) in a ChatGPT conversation tree."""
    for node_id, node in mapping.items():
        if node.get("parent") is None:
            return node_id
    return None


def _traverse_tree(mapping, root_id):
    """Walk the conversation tree to produce a linear list of turns.

    At each node, follows the last child (the "canonical" path ChatGPT shows).
    Skips null messages and system messages.
    """
    turns = []
    current_id = root_id

    while current_id is not None:
        node = mapping.get(current_id)
        if node is None:
            break

        message = node.get("message")
        if message is not None:
            author_role = message.get("author", {}).get("role", "")
            content = message.get("content", {})
            parts = content.get("parts", [])

            # Skip system messages and empty content
            if author_role in ("user", "assistant") and parts:
                text = "\n".join(
                    str(p) for p in parts if isinstance(p, str) and p.strip()
                )
                if text.strip():
                    timestamp = None
                    create_time = message.get("create_time")
                    if create_time:
                        try:
                            dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
                            timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                        except (ValueError, OSError):
                            pass

                    turns.append(
                        {
                            "role": author_role,
                            "content": text.strip(),
                            "timestamp": timestamp,
                        }
                    )

        # Follow the last child (canonical branch)
        children = node.get("children", [])
        current_id = children[-1] if children else None

    return turns


def _parse_chatgpt_conversation(conv_raw):
    """Parse a single ChatGPT conversation dict into schema turns."""
    mapping = conv_raw.get("mapping", {})
    if not mapping:
        return []

    root_id = _find_root_id(mapping)
    if root_id is None:
        return []

    return _traverse_tree(mapping, root_id)


def extract_chatgpt_meta(raw):
    """Extract metadata from a raw ChatGPT conversation JSON."""
    title = raw.get("title", "Untitled") or "Untitled"

    created_at = None
    create_time = raw.get("create_time")
    if create_time:
        try:
            dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
            created_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            pass

    updated_at = None
    update_time = raw.get("update_time")
    if update_time:
        try:
            dt = datetime.fromtimestamp(update_time, tz=timezone.utc)
            updated_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            pass

    model = raw.get("default_model_slug")

    return {
        "title": title,
        "created_at": created_at,
        "updated_at": updated_at,
        "model": model,
    }


SKILL = {
    "name": "chatgpt",
    "description": "Import or pull ChatGPT conversations via API and ZIP export",
    "capabilities": [
        "Browser login to ChatGPT via Chrome CDP",
        "Pull conversations using internal API (Bearer token auth)",
        "Import from ChatGPT ZIP export files",
    ],
    "examples": [
        "aishell chatgpt login",
        "aishell chatgpt pull",
        "aishell chatgpt pull --max 100 --resume",
        "aishell chatgpt import conversations.zip",
    ],
    "tools": [
        {
            "name": "pull_chatgpt",
            "description": "Download ChatGPT conversations via internal API",
            "parameters": {
                "max_count": {
                    "type": "integer",
                    "default": 200,
                    "description": "Max conversations to pull",
                },
                "resume": {
                    "type": "boolean",
                    "default": False,
                    "description": "Resume interrupted pull",
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

# ── Click command group ──────────────────────────────────────────────


@click.group()
def chatgpt():
    """Import or pull ChatGPT conversations."""
    pass


# ── Login command ────────────────────────────────────────────────────


@chatgpt.command()
def login():
    """Launch Chrome for ChatGPT sign-in.

    Opens Chrome with a persistent profile at ~/chromeuserdata.
    Sign into ChatGPT, then close Chrome when done.
    """
    chrome_login(
        url="https://chatgpt.com",
        message="Sign into ChatGPT, then close Chrome when done.",
        console=console,
    )
    console.print("You can now run [cyan]aishell chatgpt pull[/cyan].")


# ── Pull command ─────────────────────────────────────────────────────


@chatgpt.command()
@click.option(
    "--max", "max_count", type=int, default=0, help="Max conversations (0=all)"
)
@click.option("--resume", is_flag=True, help="Skip already-exported conversations")
@click.option("--dry-run", is_flag=True, help="List conversations without extracting")
@click.option(
    "--delay", type=float, default=2.0, help="Delay between API calls (seconds)"
)
def pull(max_count, resume, dry_run, delay):
    """Download ChatGPT conversations via browser API.

    Connects to Chrome via CDP, calls ChatGPT's internal API using
    the authenticated browser session, and saves each conversation
    to ~/.aishell/chatgpt/.

    Requires: aishell chatgpt login (once)
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

            console.print("[blue]Navigating to chatgpt.com...[/blue]")
            page.goto(
                "https://chatgpt.com",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(3)

            # Auth check
            if not check_auth(page, CHATGPT_AUTH_INDICATORS):
                console.print(
                    "[red]Not logged in! Run 'aishell chatgpt login' first.[/red]"
                )
                page.close()
                browser.close()
                return

            # Get access token (required for ChatGPT backend API)
            console.print("[blue]Fetching access token...[/blue]")
            access_token = _get_access_token(page)
            if not access_token:
                console.print(
                    "[red]Could not obtain access token. "
                    "Try signing in again with 'aishell chatgpt login'.[/red]"
                )
                page.close()
                browser.close()
                return
            auth_headers = {"Authorization": f"Bearer {access_token}"}

            # Fetch conversation list with pagination
            console.print("[blue]Fetching conversation list...[/blue]")
            all_conversations = []
            offset = 0
            limit = 100

            while True:
                url = (
                    f"{CHATGPT_API_BASE}/conversations"
                    f"?offset={offset}&limit={limit}&order=updated"
                )
                try:
                    data = fetch_json(page, url, headers=auth_headers)
                except RuntimeError as e:
                    console.print(f"[red]API error: {e}[/red]")
                    page.close()
                    browser.close()
                    return

                items = data.get("items", [])
                total = data.get("total", 0)
                all_conversations.extend(items)

                console.print(
                    f"  Fetched {len(all_conversations)}/{total} conversations"
                )

                offset += limit
                if offset >= total or not items:
                    break
                time.sleep(1)

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
                    if not already_exported(c.get("id", ""), RAW_DIR)
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
                table = Table(title="ChatGPT Conversations")
                table.add_column("#", style="dim", width=4)
                table.add_column("ID", style="cyan", width=20)
                table.add_column("Status", width=6)
                table.add_column("Title", style="white")

                scan_entries = []
                for i, conv in enumerate(all_conversations, 1):
                    cid = conv.get("id", "")
                    exported = already_exported(cid, RAW_DIR)
                    status = "[green]DONE[/green]" if exported else ""
                    title = conv.get("title", "Untitled") or "Untitled"
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
                source_id = conv_info.get("id", "")
                title = conv_info.get("title", "Untitled") or "Untitled"
                console.print(f"[{i}/{len(all_conversations)}] {title[:60]}...")

                try:
                    # Fetch full conversation detail
                    detail_url = f"{CHATGPT_API_BASE}/conversation/{source_id}"
                    conv_raw = fetch_json(page, detail_url, headers=auth_headers)

                    # Save raw response
                    raw_path = os.path.join(RAW_DIR, f"{source_id}.json")
                    with open(raw_path, "w") as f:
                        json.dump(conv_raw, f, indent=2, ensure_ascii=False)

                    # Parse using existing tree parser
                    turns = _parse_chatgpt_conversation(conv_raw)

                    if not turns:
                        console.print(f"  [yellow]No turns found, skipping[/yellow]")
                        results["skipped"] += 1
                        continue

                    # Get creation time
                    created_at = None
                    create_time = conv_raw.get("create_time")
                    if create_time:
                        try:
                            dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
                            created_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                        except (ValueError, OSError):
                            pass

                    # Convert to schema
                    converted = convert_to_schema(
                        source="chatgpt",
                        source_id=source_id,
                        title=title,
                        turns=turns,
                        model=conv_raw.get("default_model_slug"),
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
            summary = Table(title="ChatGPT Pull Summary")
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


@chatgpt.command(name="import")
@click.argument("zip_path", type=click.Path(exists=True))
def import_zip(zip_path):
    """Import conversations from a ChatGPT data export ZIP.

    ChatGPT exports contain a conversations.json file with tree-structured
    conversation data. This command parses the tree, extracts the canonical
    message path, and saves each conversation as a schema-compliant JSON.

    Examples:
        aishell chatgpt import ~/Downloads/chatgpt-export.zip
    """
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    console.print(f"[blue]Opening ZIP:[/blue] {zip_path}")

    # Find and read conversations.json from the ZIP
    conversations_data = None
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("conversations.json"):
                console.print(f"[blue]Found:[/blue] {name}")
                with zf.open(name) as f:
                    conversations_data = json.load(f)
                break

    if conversations_data is None:
        console.print("[red]No conversations.json found in ZIP.[/red]")
        return

    if not isinstance(conversations_data, list):
        console.print("[red]conversations.json is not a list.[/red]")
        return

    console.print(
        f"[blue]Processing {len(conversations_data)} conversation(s)...[/blue]"
    )

    manifest = load_manifest(MANIFEST_PATH)
    manifest_ids = {c["source_id"] for c in manifest["conversations"]}
    results = {"success": 0, "skipped": 0, "empty": 0}

    for conv_raw in conversations_data:
        title = conv_raw.get("title", "Untitled")
        source_id = conv_raw.get("id", conv_raw.get("conversation_id", ""))

        if not source_id:
            results["skipped"] += 1
            continue

        # Skip if already in manifest
        if source_id in manifest_ids:
            results["skipped"] += 1
            continue

        # Parse tree to linear turns
        turns = _parse_chatgpt_conversation(conv_raw)

        if not turns:
            results["empty"] += 1
            continue

        # Get creation time from first message or conversation metadata
        created_at = None
        create_time = conv_raw.get("create_time")
        if create_time:
            try:
                dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
                created_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, OSError):
                pass

        # Convert to schema
        converted = convert_to_schema(
            source="chatgpt",
            source_id=source_id,
            title=title,
            turns=turns,
            model=conv_raw.get("default_model_slug"),
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
    summary = Table(title="ChatGPT Import Summary")
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
