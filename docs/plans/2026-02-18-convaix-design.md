# convaix — AI Conversation Exchange

**Date**: 2026-02-18
**Status**: Design approved, implementation pending

## Vision

convaix is a standalone tool for storing, searching, and sharing AI conversations. It provides a standard format, local search (SQLite + sqlite-vec), and a P2P exchange layer starting with git-based shared repos and evolving toward serverless gossip.

aishell becomes a thin client of convaix — its conversation features delegate entirely to convaix APIs.

## Architecture

```
┌──────────────────────────────────────┐
│  aishell (thin client)               │
│                                      │
│  Shell, web search, NL conversion,   │
│  MCP, TUI browser                    │
│                                      │
│  pip install aishell                  │
│  depends on convaix                  │
└──────────────┬───────────────────────┘
               │ depends on
               ▼
┌──────────────────────────────────────┐
│  convaix                             │
│                                      │
│  Core:      schema, db, search,      │
│             chunking, embeddings     │
│                                      │
│  Providers: chatgpt, claude, gemini  │
│             (pull, import, browser)  │
│                                      │
│  Exchange:  git sharing, publish,    │
│             sync, discussions        │
│                                      │
│  pip install convaix                 │
│  pip install convaix[providers]      │
└──────────────────────────────────────┘
```

## Core Concepts

### Immutability

AI conversations in convaix are **immutable snapshots**. Once published, a snapshot never changes.

If the same LLM conversation is re-exported with more turns, it becomes a **new snapshot** with a new `convaix_id`. Both coexist — neither replaces the other.

### Identity Model

| Field | Purpose | Mutable? |
|-------|---------|----------|
| `convaix_id` | UUIDv4 assigned at publish time. The definitive, globally unique identity of a snapshot. | Never |
| `conv_id` | Provider-derived hash (`source + source_id`). Groups snapshots of the same LLM conversation lineage. | Never |
| `published_at` | When this snapshot was published to convaix. | Never |

```
┌─────────────────────────────────────────────────┐
│  conv_id: conv_abc123      (lineage — from LLM) │
│                                                  │
│  ┌───────────────────┐  ┌───────────────────┐    │
│  │ convaix_id: cx_001│  │ convaix_id: cx_002│    │
│  │ published: T1     │  │ published: T2     │    │
│  │ 20 turns          │  │ 35 turns          │    │
│  │ immutable         │  │ immutable         │    │
│  └───────────────────┘  └───────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Human Discussions

Humans can have conversations **about** AI conversation snapshots. These are separate entities that reference snapshots by `convaix_id`. They never merge back into the AI conversation. A discussion can reference multiple snapshots (e.g., comparing two versions).

```
AI Snapshot cx_001 (immutable)
       │
       │ referenced by
       ▼
Human Discussion dx_abc
  "This approach to manifold embeddings is wrong because..."
  (separate entity, parallel to the AI conversation)
```

## Schema: v1.0 + Extension Mechanism

Core schema is the existing aishell v1.0 format, unchanged. P2P metadata lives in an `x-convaix` extension namespace.

```json
{
  "schema_version": "1.0",
  "conversation": {
    "id": "conv_a1b2c3d4e5f6",
    "title": "Riemannian Manifold Embeddings",
    "source": "claude",
    "source_id": "provider-uuid",
    "source_url": "https://...",
    "model": "claude-3-opus",
    "created_at": "2026-02-18T10:00:00Z",
    "exported_at": "2026-02-18T12:00:00Z",
    "tags": ["research", "embeddings"],
    "metadata": {}
  },
  "turns": [
    {
      "turn_number": 1,
      "role": "user",
      "content": "message text",
      "timestamp": "2026-02-18T10:00:01Z",
      "attachments": [],
      "metadata": {}
    }
  ],
  "statistics": {
    "turn_count": 42,
    "user_turns": 21,
    "assistant_turns": 21,
    "total_chars": 85000
  },

  "x-convaix": {
    "convaix_id": "cx_8f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "version": "0.1",
    "conv_id": "conv_a1b2c3d4e5f6",
    "author": {
      "handle": "nborwankar",
      "key_id": null
    },
    "published_at": "2026-02-18T14:00:00Z",
    "parent_refs": [],
    "annotations": [],
    "signature": null
  }
}
```

**Extension rules:**
- All P2P metadata lives under `"x-convaix"` — never in the core schema
- `x-convaix` is optional — a file without it is still valid schema v1.0
- `parent_refs` lists `convaix_id`s this conversation builds on (research threading)
- `author`, `signature`, `key_id` present but null until crypto is layered in
- Any tool that reads schema v1.0 ignores unknown top-level keys — full backward compatibility

## Storage Layer: SQLite3 + sqlite-vec

```
┌─────────────────────────────────────────────────────┐
│  convaix.db (SQLite3)                               │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  snapshots                                  │     │
│  │                                             │     │
│  │  convaix_id TEXT PK  (UUIDv4, definitive)   │     │
│  │  conv_id TEXT        (lineage, from LLM)    │     │
│  │  title TEXT                                 │     │
│  │  source TEXT                                │     │
│  │  source_id TEXT                             │     │
│  │  model TEXT                                 │     │
│  │  created_at TEXT     (LLM conversation time)│     │
│  │  published_at TEXT   (convaix publish time)  │     │
│  │  author TEXT                                │     │
│  │  tags JSON                                  │     │
│  │  raw JSON            (full v1.0 + x-convaix)│     │
│  │  turn_count INTEGER                         │     │
│  │  total_chars INTEGER                        │     │
│  │                                             │     │
│  │  INDEX(conv_id)                             │     │
│  │  INDEX(author)                              │     │
│  │  INDEX(source)                              │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  chunks                                     │     │
│  │                                             │     │
│  │  id INTEGER PK AUTOINCREMENT                │     │
│  │  convaix_id TEXT FK → snapshots.convaix_id  │     │
│  │  turn_number INTEGER                        │     │
│  │  chunk_number INTEGER                       │     │
│  │  role TEXT                                  │     │
│  │  chunk_text TEXT                            │     │
│  │  content_hash TEXT                          │     │
│  │                                             │     │
│  │  UNIQUE(convaix_id, turn_number,            │     │
│  │         chunk_number)                       │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  chunks_vec (sqlite-vec virtual table)      │     │
│  │                                             │     │
│  │  rowid → chunks.id                          │     │
│  │  embedding FLOAT[768]                       │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  discussions                                │     │
│  │                                             │     │
│  │  discussion_id TEXT PK (UUIDv4)             │     │
│  │  title TEXT                                 │     │
│  │  created_at TEXT                            │     │
│  │  created_by TEXT                            │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  discussion_refs                            │     │
│  │                                             │     │
│  │  discussion_id TEXT FK → discussions        │     │
│  │  convaix_id TEXT FK → snapshots             │     │
│  │  PK(discussion_id, convaix_id)              │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  discussion_messages                        │     │
│  │                                             │     │
│  │  id INTEGER PK AUTOINCREMENT                │     │
│  │  discussion_id TEXT FK → discussions        │     │
│  │  author TEXT                                │     │
│  │  content TEXT                               │     │
│  │  created_at TEXT                            │     │
│  └─────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

**Key design choices:**
- `snapshots` replaces the old `conversations_raw` table — name reflects immutability
- All FKs reference `convaix_id`, not `conv_id`
- `raw` column stores the full JSON blob (v1.0 + x-convaix)
- sqlite-vec virtual table for vector search, joined by rowid
- Brute-force KNN sufficient for <100K chunks — no HNSW index needed initially
- Hybrid search: semantic (sqlite-vec cosine) + keyword (LIKE on chunk_text and title)

## Git Exchange Model

Phase 1 transport. Shared repos for collaborative research teams.

### Shared Repo Layout

```
team-ml/
├── .convaix/
│   └── repo.toml             # Repo metadata (name, description)
├── manifest.json              # Index of all snapshots + discussions
├── conversations/
│   ├── cx_8f3a2b1c-riemannian-embeddings.json
│   ├── cx_d4e5f6a7-riemannian-embeddings.json
│   └── cx_1a2b3c4d-hyperbolic-hnsw.json
└── discussions/
    └── dx_9f8e7d6c-manifold-choice-debate.json
```

**File naming:** `cx_{convaix_id_prefix}-{slugified-title}.json`

### manifest.json

```json
{
  "repo": "team-ml",
  "description": "ML research conversations",
  "snapshots": [
    {
      "convaix_id": "cx_8f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
      "conv_id": "conv_abc123",
      "title": "Riemannian Embeddings",
      "source": "claude",
      "author": "nborwankar",
      "published_at": "2026-02-18T14:00:00Z",
      "file": "conversations/cx_8f3a2b1c-riemannian-embeddings.json",
      "turn_count": 20
    }
  ],
  "discussions": [
    {
      "discussion_id": "dx_9f8e7d6c-1a2b-3c4d-5e6f-7a8b9c0d1e2f",
      "title": "Manifold choice debate",
      "references": ["cx_8f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c"],
      "file": "discussions/dx_9f8e7d6c-manifold-choice-debate.json"
    }
  ]
}
```

### Trust Model (Phase 1)

Git repo access controls. Who has push/pull access defines the trusted group. Crypto (GPG signing, key-based identity) layered in later.

### Conflict Handling

No conflicts possible on conversation files — every publish creates a new uniquely-named file. Manifest.json is append-only (new entries only). Discussion messages are append-only (ordered by timestamp).

## CLI Design: Verb-First

The provider is an argument, not a command group. Extensible via provider registry.

```bash
# Provider operations (verb first, target as argument)
convaix login <provider>
convaix pull <provider>
convaix import <provider> <path>

# Core
convaix load <file-or-dir>
convaix search "query" [-c] [-s source] [-l limit]
convaix list
convaix history <conv_id>
convaix validate <file>
convaix export <convaix_id>

# Exchange
convaix init <path>
convaix publish <convaix_id> --repo <name>
convaix sync <repo>
convaix discuss <convaix_id> --repo <name> --title "..."
```

### Provider Registry

```python
PROVIDERS = {
    "chatgpt": ChatGPTProvider,
    "claude":  ClaudeProvider,
    "gemini":  GeminiProvider,
}
```

Third-party providers can register via entry points:

```toml
[project.entry-points."convaix.providers"]
mistral = "convaix_mistral:MistralProvider"
```

### Python API

```python
import convaix

convaix.pull("chatgpt")
convaix.login("claude")
convaix.load("./conversations/")
convaix.search("manifold embeddings")
convaix.publish("cx_abc123", repo="team-ml")
```

## Package Structure

```
convaix/
├── CLAUDE.md
├── DONE.md
├── README.md
├── pyproject.toml
├── docs/
│   └── plans/
├── src/
│   └── convaix/
│       ├── __init__.py           # Public API (pull, load, search, etc.)
│       ├── cli.py                # Click CLI entry point
│       │
│       ├── # ── Core (always installed) ──
│       ├── schema.py             # v1.0 format + x-convaix extensions
│       ├── validate.py           # JSON schema validation
│       ├── db.py                 # SQLite3 + sqlite-vec
│       ├── chunking.py           # Paragraph splitting
│       ├── embeddings.py         # MLX + nomic-embed-text-v1.5
│       ├── search.py             # Hybrid semantic + keyword
│       │
│       ├── # ── Providers (pip install convaix[providers]) ──
│       ├── providers/
│       │   ├── __init__.py       # PROVIDERS registry
│       │   ├── base.py           # Provider base class
│       │   ├── browser.py        # Chrome CDP, fetch_json, chrome_login
│       │   ├── chatgpt.py        # ChatGPT pull, import
│       │   ├── claude.py         # Claude pull, import
│       │   └── gemini.py         # Gemini pull, import
│       │
│       ├── # ── Exchange (always installed) ──
│       └── exchange/
│           ├── __init__.py
│           ├── git.py            # init, publish, pull, sync
│           ├── manifest.py       # Shared repo manifest management
│           └── discuss.py        # Human discussions
│
└── tests/
```

### pyproject.toml

```toml
[project]
name = "convaix"
description = "AI conversation exchange — store, search, share"

dependencies = [
    "click",
    "rich",
    "sqlite-vec",
    "mlx-embedding-models",
]

[project.optional-dependencies]
providers = [
    "playwright",
    "beautifulsoup4",
    "lxml",
    "requests",
]

[project.scripts]
convaix = "convaix.cli:main"
```

## Data Locations

```
~/.convaix/
├── convaix.db            # SQLite3 + sqlite-vec (local store)
├── config.toml           # Settings (embed model, remotes, etc.)
└── repos/                # Cloned shared repos
    └── team-ml/          # Managed by convaix
```

## aishell Integration

aishell becomes a thin client. Its conversation commands delegate to convaix Python APIs. The TUI browser stays in aishell as a value-add UI that reads from `convaix.db`.

```
aishell/
├── cli.py
├── commands/
│   ├── conversations/
│   │   ├── cli.py        # Thin wrappers → convaix.load(), convaix.search()
│   │   └── tui.py        # TUI browser (reads convaix.db)
│   └── ...
├── search/               # Web/file search (aishell's own)
├── shell/                # Intelligent shell (aishell's own)
└── utils/
```

## Future Roadmap (Not in Scope Now)

1. **Gossip P2P** — replace git with serverless gossip protocol (Scuttlebutt-style)
2. **Crypto layer** — GPG/SSH signing, key-based identity, web-of-trust
3. **Open web publishing** — static site generation, public browsing without authenticity
4. **Entry point providers** — third-party provider plugins via pyproject.toml entry points
