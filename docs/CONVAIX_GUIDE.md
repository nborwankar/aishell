# convaix — Getting Started Guide

**convaix** stores, searches, and shares your AI conversations. It pulls
conversations from ChatGPT, Claude, and Gemini into a local SQLite database
with vector search, so you can find anything you've ever discussed with an LLM.

---

## What convaix Does

You have hundreds (maybe thousands) of AI conversations scattered across
ChatGPT, Claude, and Gemini. Some contain valuable code, ideas, research
directions, and decisions. But they're locked in separate provider UIs with
weak search.

convaix fixes this:

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│  ChatGPT │  │  Claude   │  │  Gemini  │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │ pull        │ pull        │ pull
     └──────┬──────┘──────┬──────┘
            │             │
            ▼             ▼
     ┌────────────────────────────┐
     │  convaix                   │
     │                            │
     │  SQLite + sqlite-vec       │
     │  One DB, all providers     │
     │  Semantic + keyword search │
     │  Offline, private, local   │
     └────────────────────────────┘
```

**One search across everything.** Type a query, get results from all three
providers ranked by relevance. Semantic search understands meaning ("that
conversation about caching strategies") and keyword search catches exact
terms, acronyms, and coined words.

---

## Installation

### 1. Install convaix

```bash
pip install convaix[all]
```

This installs convaix with all optional dependencies: embedding model support,
provider browser automation, and the full search stack.

For a minimal install (core + search only, no provider pulling):

```bash
pip install convaix
```

### 2. Install sqlite-vec

convaix uses [sqlite-vec](https://github.com/asg017/sqlite-vec) for vector
similarity search. It ships as a Python package and loads as a SQLite
extension — no separate server, no PostgreSQL, no Docker.

```bash
pip install sqlite-vec
```

Verify it works:

```bash
python -c "import sqlite_vec; print('sqlite-vec OK')"
```

### 3. Install browser support (for pulling conversations)

convaix uses Playwright to automate Chrome for downloading conversations from
provider websites. This is only needed for the `pull` command.

```bash
python -m playwright install chromium
```

### 4. Verify installation

```bash
convaix --help
```

You should see the available commands: `pull`, `load`, `search`, `list`, etc.

---

## Downloading Your Conversations

### Step 1: Log in to a provider

convaix opens a Chrome browser window so you can sign in normally. It saves
the session cookies for subsequent pulls.

```bash
convaix login chatgpt
```

A browser window opens. Sign in to ChatGPT as you normally would. Once you
reach the main chat page, close the browser — convaix has captured the
session.

Repeat for other providers:

```bash
convaix login claude
convaix login gemini
```

### Step 2: Pull conversations

Download all your conversations from a provider:

```bash
convaix pull chatgpt
```

```
Fetching conversation list... 811 conversations
Downloading: [####################################] 811/811
Saved to: ~/.convaix/chatgpt/raw/
```

convaix downloads the raw API responses and saves them locally. This only
needs to happen once per provider — subsequent pulls only download new
conversations.

Pull from all providers:

```bash
convaix pull chatgpt
convaix pull claude
convaix pull gemini
```

### What gets downloaded

Each conversation is saved as a raw JSON file in `~/.convaix/<provider>/raw/`.
These are your permanent local copies. convaix never modifies or deletes them.

```
~/.convaix/
├── chatgpt/
│   └── raw/           # 811 raw API response JSONs
├── claude/
│   └── raw/           # 920 raw API response JSONs
└── gemini/
    └── raw/           # 33 raw DOM extraction JSONs
```

---

## Loading into the Database

Once downloaded, load conversations into the search database:

```bash
convaix load
```

```
Loading 1764 conversations...
  chatgpt: 811 conversations, 30120 chunks embedded
  claude:  920 conversations, 41832 chunks embedded
  gemini:   33 conversations,  1205 chunks embedded

Total: 1764 conversations, 73157 chunks
Database: ~/.convaix/convaix.db (148 MB)
```

This does three things:

1. **Parses** each raw JSON into a standard format (handles ChatGPT tree
   structures, Claude linear messages, Gemini DOM extractions)
2. **Chunks** each conversation into paragraphs for fine-grained search
3. **Embeds** each chunk using the nomic-embed-text-v1.5 model for semantic
   similarity search

Loading from a single provider:

```bash
convaix load --provider chatgpt
```

Skip embeddings for a faster load (keyword search still works):

```bash
convaix load --skip-embeddings
```

### The database

Everything lives in a single SQLite file:

```
~/.convaix/convaix.db
```

No PostgreSQL. No Docker. No server process. The file is portable — copy it
to another machine and search works immediately.

---

## Searching Your Conversations

### Basic search

```bash
convaix search "manifold embeddings"
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Title                           ┃ Source  ┃ Role    ┃ Match ┃ Score ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ Riemannian Manifold Embeddings  │ claude  │ assist. │ sem   │ 0.92  │
│ Hyperbolic HNSW Implementation  │ chatgpt │ user    │ both  │ 0.87  │
│ Sphere vs Euclidean Comparison  │ claude  │ assist. │ sem   │ 0.84  │
│ PyManopt Optimization Setup     │ chatgpt │ assist. │ kw    │ 0.71  │
│ ...                             │         │         │       │       │
└─────────────────────────────────┴─────────┴─────────┴───────┴───────┘
```

The `Match` column tells you how the result was found:
- **sem** — semantic similarity (the embedding understood the meaning)
- **kw** — keyword match (exact text match on the query terms)
- **both** — matched on both semantic and keyword

### Filter by provider

```bash
convaix search "caching strategies" --source chatgpt
```

### Conversation-level search

Instead of individual chunks, see which conversations mention a topic and
how many hits each has:

```bash
convaix search "WASM components" --conversations
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━┓
┃ Title                               ┃ Source  ┃ Hits ┃ Turns ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━┩
│ Server-Side WASM Components         │ chatgpt │ 47   │ 81    │
│ Industrial Software Assembly        │ chatgpt │ 12   │ 35    │
│ Component Catalog Design            │ claude  │ 8    │ 22    │
└─────────────────────────────────────┴─────────┴──────┴───────┘
```

### Limit results

```bash
convaix search "python async" --limit 5
```

### How search works

convaix uses **hybrid search** — two strategies combined:

```
Query: "flatoon"
                    ┌─────────────────────┐
                    │  Semantic Search     │
                    │  (embedding cosine)  │──→ No results
                    │  "flatoon" has no    │    (unknown word)
                    │  meaningful embedding│
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │  Keyword Search      │
                    │  (LIKE on text)      │──→ Found! "flatoon"
                    │  Exact string match  │    appears in 2 chunks
                    └─────────────────────┘
```

Semantic search understands meaning but fails on novel terms, acronyms, and
invented words. Keyword search catches exact terms but misses paraphrases.
Together they cover both cases.

---

## Browsing Conversations

List all conversations:

```bash
convaix list
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ Title                           ┃ Source  ┃ Turns ┃ Date       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ Riemannian Manifold Embeddings  │ claude  │ 42    │ 2026-02-18 │
│ Server-Side WASM Components     │ chatgpt │ 81    │ 2026-02-15 │
│ Hyperbolic HNSW V2 Pipeline     │ claude  │ 65    │ 2026-02-10 │
│ ...                             │         │       │            │
└─────────────────────────────────┴─────────┴───────┴────────────┘
  1764 conversations (chatgpt: 811, claude: 920, gemini: 33)
```

View the version history of a conversation (multiple snapshots):

```bash
convaix history conv_abc123
```

Export a conversation back to JSON:

```bash
convaix export cx_8f3a2b1c
```

---

## Data Model at a Glance

```
                ┌─────────────┐
                │  Snapshot    │  Immutable. Once published, never changes.
                │             │  Re-exporting a conversation creates a NEW
                │  convaix_id │  snapshot — both coexist.
                │  conv_id    │
                │  title      │
                │  source     │
                │  raw JSON   │
                └──────┬──────┘
                       │ has many
                       ▼
                ┌─────────────┐
                │  Chunk      │  Paragraph-level text fragments.
                │             │  Each chunk is embedded for
                │  chunk_text │  semantic search.
                │  role       │
                │  embedding  │
                └─────────────┘
```

**Immutability** is the core principle. AI conversations are snapshots in time.
If you re-pull a conversation that grew by 10 turns, you get a new snapshot.
The old one stays exactly as it was. This means:

- No data loss from re-imports
- Every snapshot is independently searchable
- You can compare versions of the same conversation
- Sharing a snapshot is safe — the recipient gets exactly what you sent

---

## Quick Reference

```bash
# First-time setup
convaix login chatgpt          # Sign in via browser
convaix login claude
convaix login gemini

# Download conversations
convaix pull chatgpt           # Downloads raw JSONs
convaix pull claude
convaix pull gemini

# Load into search database
convaix load                   # Parse, chunk, embed → convaix.db

# Search
convaix search "query"                    # Hybrid search
convaix search "query" -s chatgpt         # Filter by provider
convaix search "query" -c                 # Conversation-level
convaix search "query" -l 5               # Limit results

# Browse
convaix list                              # All conversations
convaix history <conv_id>                 # Version history

# Re-import after parser updates
convaix import chatgpt                    # Re-parse from local raw files
```

---

## File Locations

| Path | Contents |
|------|----------|
| `~/.convaix/convaix.db` | SQLite database (conversations + embeddings) |
| `~/.convaix/config.toml` | Settings (embedding model, remotes) |
| `~/.convaix/chatgpt/raw/` | Raw ChatGPT API response JSONs |
| `~/.convaix/claude/raw/` | Raw Claude API response JSONs |
| `~/.convaix/gemini/raw/` | Raw Gemini DOM extraction JSONs |

Everything is local. No cloud services, no accounts, no telemetry. Your
conversations stay on your machine.
