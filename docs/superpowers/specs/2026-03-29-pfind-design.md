# pfind — Project Finder (Inverted Index)

**Date**: 2026-03-29
**Status**: Design approved
**Location**: `aishell pfind` subcommand + `~/Projects/pfind/` data directory

---

## Problem

106+ projects across `~/Projects/` in nested directories (`dirs/github/`, `index/`, etc.). Projects move during consolidation. Finding a project by name requires remembering its current path.

## Solution

An inverted index mapping leaf directory names to absolute paths, searchable via `aishell pfind`, rebuilt on demand.

## Data Layout

```
~/Projects/pfind/
├── invindex.json       # leaf dirname → [absolute paths]
├── config.json         # scan roots, excludes, metadata
```

### invindex.json

```json
{
  "_meta": {
    "last_rebuild": "2026-03-29T14:30:00",
    "entry_count": 106,
    "roots_scanned": ["/Users/nitin/Projects"]
  },
  "aishell": ["/Users/nitin/Projects/dirs/github/aishell"],
  "strictRAG": ["/Users/nitin/Projects/dirs/github/kb/strictRAG"],
  "docs": [
    "/Users/nitin/Projects/docs",
    "/Users/nitin/Projects/dirs/github/mm/MetaMuttMaster/metamutt/backend/docs"
  ]
}
```

- Keys: leaf directory names (case-preserved)
- Values: list of absolute paths (multiple when leaf name collides)
- `_meta`: rebuild timestamp, stats, roots that were scanned

### config.json

```json
{
  "roots": ["/Users/nitin/Projects"],
  "exclude_dirs": ["node_modules", ".git", "__pycache__", "_archive", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache", "site-packages"],
  "project_markers": [".git", "CLAUDE.md", "README.md", "setup.py", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]
}
```

## CLI Interface

Command lives in aishell as a subcommand:

```
aishell pfind <query>             # Search (exact → substring → fuzzy)
aishell pfind --rebuild           # Rescan all roots, rebuild invindex.json
aishell pfind --add-root <path>   # Add a scan root to config.json
aishell pfind --roots             # Show configured roots
aishell pfind --stats             # Entry count, last rebuild time
```

### Output

One path per line, composable with shell:

```bash
$ aishell pfind aishell
/Users/nitin/Projects/dirs/github/aishell

$ aishell pfind strict
/Users/nitin/Projects/dirs/github/kb/strictRAG

$ cd $(aishell pfind aishell)     # Jump to project
```

When multiple matches:
```bash
$ aishell pfind docs
docs → /Users/nitin/Projects/docs
docs → /Users/nitin/Projects/dirs/github/mm/MetaMuttMaster/metamutt/backend/docs
```

When no results from exact/substring, fuzzy fallback:
```bash
$ aishell pfind strct
Did you mean?
  strictRAG → /Users/nitin/Projects/dirs/github/kb/strictRAG
```

## Scan Logic

```
                    ┌─────────────────────────┐
                    │   For each root in       │
                    │   config.roots           │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Walk directory tree     │
                    │   (os.walk / iterdir)     │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Skip if dir name in     │
                    │   exclude_dirs            │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Contains a project      │──── No ──→ descend into children
                    │   marker?                 │
                    └────────────┬─────────────┘
                                 │ Yes
                    ┌────────────▼─────────────┐
                    │   Resolve symlinks        │
                    │   (avoid duplicate paths) │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Add leaf_name → path    │
                    │   to invindex             │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Do NOT descend further  │
                    │   (project is atomic)     │
                    └───────────────────────────┘
```

Key rules:
1. A directory is a "project" if it contains any file/dir from `project_markers`
2. Once a project is identified, don't descend into its children (prevents indexing subdirs as separate projects)
3. Resolve symlinks before storing to deduplicate (index/ symlinks → dirs/ real paths)
4. Exclude list prevents descending into dependency/cache directories

## Search Logic

Three tiers, tried in order:

1. **Exact match** (case-insensitive): key.lower() == query.lower()
2. **Substring match** (case-insensitive): query.lower() in key.lower()
3. **Fuzzy fallback** (multi-signal scoring): if tiers 1-2 return nothing, score all keys using three signals:
   - **Subsequence**: query chars appear in order in name (catches typos/missing vowels: "strct" → "strictRAG")
   - **Token overlap**: split name on `-`, `_`, camelCase boundaries; match query tokens to name tokens by prefix ("mlx man" → "mlx-manopt")
   - **Prefix bonus**: query matching start of name or start of any token scores higher
   - Top 5 results with combined score > 0.15 are returned

## Implementation

- **Single file**: `aishell/commands/pfind.py`
- **Zero external deps**: stdlib only (`json`, `os`, `pathlib`, `difflib`)
- **Click subcommand**: registered in aishell's CLI group
- **Data dir**: `~/Projects/pfind/` created on first `--rebuild` if absent
- **Config bootstrapped**: default config.json written on first run with `~/Projects` as sole root

## Edge Cases

- **Symlink dedup**: `~/Projects/index/agents/aishell` → `~/Projects/dirs/github/aishell`. After resolving, both map to same real path. Store only the resolved path.
- **Name collisions**: Multiple projects named `docs` get all paths listed under that key.
- **Stale index**: If a project was moved/deleted, path in index won't exist. `pfind` prints the path but could warn `[stale]` if path doesn't exist at query time.
- **First run**: If invindex.json doesn't exist, prompt user to run `--rebuild`.
