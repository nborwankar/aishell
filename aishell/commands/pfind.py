"""pfind — Project Finder via inverted index.

Scans configured directory roots for projects (identified by marker files),
builds a leaf-name → absolute-paths inverted index, and provides
exact/substring/fuzzy search.

Data lives at ~/Projects/pfind/ (configurable):
  - invindex.json: the inverted index
  - config.json: roots, excludes, markers
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

DEFAULT_DATA_DIR = Path.home() / "Projects" / "pfind"

DEFAULT_EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "_archive",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "site-packages",
    ".eggs",
    "build",
    "dist",
    ".nox",
}

DEFAULT_PROJECT_MARKERS = {
    ".git",
    "CLAUDE.md",
    "README.md",
    "setup.py",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
}


def _tokenize(name: str) -> list[str]:
    """Split a project name into lowercase tokens on -, _, and camelCase boundaries.

    Examples:
        "hypHNSW"        → ["hyp", "hnsw"]
        "mlx-manopt"     → ["mlx", "manopt"]
        "strictRAG"      → ["strict", "rag"]
        "IdeaSearch-fit" → ["idea", "search", "fit"]
    """
    # Insert boundary before runs of uppercase followed by lowercase (camelCase)
    # and between lowercase/digit and uppercase
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    # Split run of uppercase: "HNSW" stays together, but "RAGfoo" → "RA Gfoo"
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    # Split on hyphens, underscores, spaces
    parts = re.split(r"[-_ ]+", spaced)
    return [p.lower() for p in parts if p]


def _is_subsequence(needle: str, haystack: str) -> bool:
    """Check if needle chars appear in order in haystack."""
    it = iter(haystack)
    return all(c in it for c in needle)


def _fuzzy_score(query: str, name: str) -> float:
    """Score a query against a project name (both already lowercased).

    Returns 0.0 for no match, higher is better (max ~1.0).

    Signals combined:
      1. Subsequence match — query chars appear in order in name
      2. Token overlap — query tokens match name tokens (prefix or full)
      3. Prefix bonus — query matches the start of the name
      4. Length-normalized char overlap — handles short queries well
    """
    score = 0.0

    # Signal 1: subsequence (e.g. "strct" in "strictrag")
    if _is_subsequence(query, name):
        # Ratio of query length to name length rewards tighter matches
        score += 0.4 * (len(query) / len(name))

    # Signal 2: token overlap
    q_tokens = _tokenize(query)
    n_tokens = _tokenize(name)
    if q_tokens and n_tokens:
        matched = 0
        for qt in q_tokens:
            for nt in n_tokens:
                if nt.startswith(qt) or qt.startswith(nt):
                    matched += 1
                    break
        token_ratio = matched / len(q_tokens)
        score += 0.4 * token_ratio

    # Signal 3: prefix bonus
    if name.startswith(query):
        score += 0.2
    elif any(nt.startswith(query) for nt in n_tokens):
        score += 0.1

    # Minimum threshold to count as a match
    if score < 0.15:
        return 0.0
    return score


class ProjectIndex:
    """Builds and queries a project-name inverted index."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.index_path = self.data_dir / "invindex.json"
        self.config_path = self.data_dir / "config.json"

    def build(
        self,
        roots: list[str],
        exclude_dirs: list[str] | None = None,
        markers: set[str] | None = None,
    ) -> dict[str, list[str]]:
        """Scan roots and return inverted index: leaf_name → [abs_paths]."""
        excludes = (
            set(exclude_dirs) if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
        )
        markers = markers or DEFAULT_PROJECT_MARKERS
        index: dict[str, list[str]] = {}
        seen_real: set[str] = set()

        for root in roots:
            self._scan_dir(Path(root), index, excludes, markers, seen_real)

        return index

    def _scan_dir(
        self,
        directory: Path,
        index: dict[str, list[str]],
        excludes: set[str],
        markers: set[str],
        seen_real: set[str],
    ) -> None:
        """Recursively scan a directory for projects."""
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            logger.debug("Permission denied: %s", directory)
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name in excludes:
                continue
            if entry.name.startswith(".") and entry.name != ".git":
                continue

            # Check if this dir is a project
            if self._is_project(entry, markers):
                real = str(entry.resolve())
                if real not in seen_real:
                    seen_real.add(real)
                    name = entry.name
                    index.setdefault(name, []).append(real)
                # Don't descend into projects
                continue

            # Not a project — descend
            self._scan_dir(entry, index, excludes, markers, seen_real)

    def _is_project(self, directory: Path, markers: set[str]) -> bool:
        """Check if directory contains any project marker."""
        try:
            contents = {e.name for e in directory.iterdir()}
        except PermissionError:
            return False
        return bool(contents & markers)

    def save(self, index: dict[str, list[str]], roots: list[str]) -> None:
        """Write invindex.json to data_dir."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "_meta": {
                "last_rebuild": datetime.now(timezone.utc).isoformat(),
                "entry_count": len(index),
                "roots_scanned": roots,
            },
            **dict(sorted(index.items())),
        }
        self.index_path.write_text(json.dumps(payload, indent=2) + "\n")
        logger.info("Wrote %d entries to %s", len(index), self.index_path)

    def load(self) -> dict[str, list[str]]:
        """Load invindex.json. Returns empty dict if missing."""
        if not self.index_path.exists():
            return {}
        data = json.loads(self.index_path.read_text())
        data.pop("_meta", None)
        return data

    def load_meta(self) -> dict:
        """Load just the _meta block from invindex.json."""
        if not self.index_path.exists():
            return {}
        data = json.loads(self.index_path.read_text())
        return data.get("_meta", {})

    def search(
        self, query: str, index: dict[str, list[str]] | None = None
    ) -> list[tuple[str, list[str], str]]:
        """Search index for query. Returns [(name, [paths], match_type), ...]."""
        if index is None:
            index = self.load()
        if not index:
            return []

        q = query.lower()
        results: list[tuple[str, list[str], str]] = []

        # Tier 1: exact match (case-insensitive)
        for name, paths in index.items():
            if name.lower() == q:
                results.append((name, paths, "exact"))

        if results:
            return results

        # Tier 2: substring match
        for name, paths in index.items():
            if q in name.lower():
                results.append((name, paths, "substring"))

        if results:
            return sorted(results, key=lambda r: r[0].lower())

        # Tier 3: fuzzy match (multi-signal scoring)
        scored = []
        for name, paths in index.items():
            score = _fuzzy_score(q, name.lower())
            if score > 0.0:
                scored.append((name, paths, "fuzzy", score))

        scored.sort(key=lambda r: r[3], reverse=True)
        return [(name, paths, "fuzzy") for name, paths, _, _ in scored[:5]]

    def save_config(self, roots: list[str]) -> None:
        """Write config.json."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "roots": roots,
            "exclude_dirs": sorted(DEFAULT_EXCLUDE_DIRS),
            "project_markers": sorted(DEFAULT_PROJECT_MARKERS),
        }
        self.config_path.write_text(json.dumps(config, indent=2) + "\n")

    def load_config(self) -> dict:
        """Load config.json. Returns defaults if missing."""
        if not self.config_path.exists():
            return {
                "roots": [str(Path.home() / "Projects")],
                "exclude_dirs": sorted(DEFAULT_EXCLUDE_DIRS),
                "project_markers": sorted(DEFAULT_PROJECT_MARKERS),
            }
        return json.loads(self.config_path.read_text())


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------

SKILL = {
    "name": "pfind",
    "description": "Find projects by name using an inverted index",
    "capabilities": [
        "Search for projects by name (exact, substring, fuzzy)",
        "Rebuild index by scanning configured project roots",
        "Show index statistics",
    ],
    "examples": [
        "aishell pfind aishell",
        "aishell pfind strict",
        "aishell pfind --rebuild",
        "aishell pfind --stats",
        "cd $(aishell pfind aishell)",
    ],
    "tools": [],
}


@click.command(name="pfind")
@click.argument("query", required=False)
@click.option("--rebuild", is_flag=True, help="Rescan roots and rebuild the index")
@click.option("--stats", is_flag=True, help="Show index statistics")
@click.option("--roots", "show_roots", is_flag=True, help="Show configured scan roots")
@click.option("--add-root", type=click.Path(exists=True), help="Add a scan root")
@click.option(
    "--data-dir",
    type=click.Path(),
    default=None,
    hidden=True,
    help="Override data directory (for testing)",
)
@click.option(
    "--root",
    type=click.Path(exists=True),
    default=None,
    hidden=True,
    help="Override root for --rebuild (for testing)",
)
def pfind(query, rebuild, stats, show_roots, add_root, data_dir, root):
    """Find projects by name.

    \b
    Search:   aishell pfind <query>
    Rebuild:  aishell pfind --rebuild
    Stats:    aishell pfind --stats
    Roots:    aishell pfind --roots
    """
    dd = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    idx = ProjectIndex(data_dir=dd)

    if add_root:
        config = idx.load_config()
        abs_root = str(Path(add_root).resolve())
        if abs_root not in config["roots"]:
            config["roots"].append(abs_root)
            idx.data_dir.mkdir(parents=True, exist_ok=True)
            idx.config_path.write_text(json.dumps(config, indent=2) + "\n")
            console.print(f"Added root: {abs_root}")
        else:
            console.print(f"Root already configured: {abs_root}")
        return

    if show_roots:
        config = idx.load_config()
        console.print("[bold]Configured roots:[/bold]")
        for r in config["roots"]:
            console.print(f"  {r}")
        return

    if rebuild:
        config = idx.load_config()
        roots = [root] if root else config["roots"]
        console.print(f"Scanning {len(roots)} root(s)...")
        index = idx.build(roots, exclude_dirs=config.get("exclude_dirs", []))
        idx.save(index, roots)
        idx.save_config(roots if not root else config["roots"])
        console.print(f"Rebuilt index: {len(index)} projects found.")
        return

    if stats:
        meta = idx.load_meta()
        if not meta:
            console.print("No index found. Run: aishell pfind --rebuild")
            return
        console.print(f"[bold]Projects:[/bold] {meta.get('entry_count', '?')}")
        console.print(f"[bold]Last rebuild:[/bold] {meta.get('last_rebuild', '?')}")
        console.print(f"[bold]Roots:[/bold] {', '.join(meta.get('roots_scanned', []))}")
        return

    if not query:
        console.print(
            "Usage: aishell pfind <query>  |  --rebuild  |  --stats  |  --roots"
        )
        return

    # Search
    index = idx.load()
    if not index:
        console.print("No index found. Run: aishell pfind --rebuild")
        return

    results = idx.search(query, index)

    if not results:
        console.print(f"No projects matching '{query}'")
        return

    for name, paths, match_type in results:
        tag = "" if match_type == "exact" else f"  [dim]({match_type})[/dim]"
        for p in paths:
            stale = "" if os.path.isdir(p) else "  [red][stale][/red]"
            console.print(f"{name} → {p}{stale}{tag}")
