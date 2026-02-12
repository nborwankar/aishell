"""Claude conversation import from data export ZIP.

Subcommands:
    aishell claude-export import <zip_path>  # Parse Claude data export ZIP
"""

import json
import logging
import os
import zipfile

import click
from rich.console import Console
from rich.table import Table

from .conversations.schema import slugify, convert_to_schema
from .conversations.manifest import load_manifest, save_manifest

console = Console()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.expanduser("~/.aishell/claude")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
MANIFEST_PATH = os.path.join(CONVERSATIONS_DIR, "manifest.json")


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


@click.group(name="claude")
def claude_export():
    """Import Claude conversations from data export ZIP."""
    pass


@claude_export.command(name="import")
@click.argument("zip_path", type=click.Path(exists=True))
def import_zip(zip_path):
    """Import conversations from a Claude data export ZIP.

    Claude exports contain JSON files with linear chat_messages arrays.
    This command handles both a single conversations.json and individual
    conversation JSON files within the ZIP.

    Examples:
        aishell claude-export import ~/Downloads/claude-export.zip
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
