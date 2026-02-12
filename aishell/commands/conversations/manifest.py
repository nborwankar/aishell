"""Manifest utilities for tracking exported conversations.

Each provider maintains its own manifest.json in its conversations/ directory.
"""

import json
import os
from datetime import datetime, timezone


def load_manifest(manifest_path):
    """Load manifest from disk, returning empty structure if not found."""
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            return json.load(f)
    return {"exported_at": None, "conversations": []}


def save_manifest(manifest, manifest_path, conversations_dir):
    """Save manifest to disk, creating directory if needed."""
    os.makedirs(conversations_dir, exist_ok=True)
    manifest["exported_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def already_exported(source_id, raw_dir):
    """Check if a conversation has already been exported (raw file exists)."""
    return os.path.exists(os.path.join(raw_dir, f"{source_id}.json"))
