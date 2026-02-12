"""ChatGPT conversation import from data export ZIP.

Subcommands:
    aishell chatgpt import <zip_path>  # Parse ChatGPT data export ZIP
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

DATA_DIR = os.path.expanduser("~/.aishell/chatgpt")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
MANIFEST_PATH = os.path.join(CONVERSATIONS_DIR, "manifest.json")


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
                        from datetime import datetime, timezone

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


@click.group()
def chatgpt():
    """Import ChatGPT conversations from data export ZIP."""
    pass


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
            from datetime import datetime, timezone

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
