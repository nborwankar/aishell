# JSONB Migration Plan — Unified Conversation Storage

**Status**: Design phase (not yet implemented)
**Created**: 2026-02-12
**Context**: After successfully pulling 1,764 conversations across 3 providers (Gemini 33, ChatGPT 811, Claude 920), the current file-based + separate DB table design should evolve to a single PostgreSQL JSONB-based store.

## Motivation

Currently the system has redundant storage layers:
- `raw/*.json` — full API responses on disk
- `conversations/*.json` — schema-compliant JSONs on disk
- `manifest.json` — tracking metadata on disk
- PostgreSQL `conversations` + `turns` tables — for search

This plan consolidates everything into PostgreSQL with JSONB columns, making PG the single source of truth.

## Schema Design

### Core Table

```sql
CREATE TABLE conversations_raw (
    source      TEXT NOT NULL CHECK (source IN ('gemini', 'chatgpt', 'claude')),
    source_id   TEXT NOT NULL,
    title       TEXT,
    raw_data    JSONB NOT NULL,         -- full API response (archival)
    turns       JSONB NOT NULL,         -- pre-linearized by Python (queryable)
    model       TEXT,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,            -- from API's update_time (change detection)
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (source, source_id)
);
```

### Why Two JSONB Columns

- **`raw_data`**: Exact API response. ChatGPT's is a tree (`mapping` with `parent`/`children`), Claude's is linear (`chat_messages`), Gemini's is DOM extraction (`turns` with `strategy`). All different shapes. Preserved for archival and future analysis.
- **`turns`**: Pre-linearized by Python parsers (the existing `_parse_chatgpt_conversation`, `_parse_claude_conversation`, `_convert_raw`). Always the same uniform shape regardless of provider:

```json
[
  {"role": "user", "content": "...", "timestamp": "..."},
  {"role": "assistant", "content": "...", "timestamp": "..."}
]
```

Python handles the hard work (ChatGPT tree traversal, Gemini text cleanup, Claude role mapping) once at insert time. SQL gets a clean uniform array.

### Why Not Flatten ChatGPT Trees in SQL

ChatGPT's `mapping` is a tree where you follow `children[-1]` at each node. A recursive CTE could do this:

```sql
WITH RECURSIVE path AS (
    SELECT ... find root where parent IS NULL ...
    UNION ALL
    SELECT ... follow children[-1] ...
)
```

But it's fragile, slow across 811 conversations, and duplicates logic already in Python. Pre-linearizing in Python is simpler and faster.

## Unified View

```sql
CREATE VIEW unified_turns AS
SELECT
    c.source,
    c.source_id,
    c.title,
    c.model,
    t.ord AS turn_number,
    t.turn->>'role' AS role,
    t.turn->>'content' AS content,
    t.turn->>'timestamp' AS timestamp
FROM conversations_raw c,
     jsonb_array_elements(c.turns) WITH ORDINALITY AS t(turn, ord);
```

No UNION needed — `turns` is already uniform. Per-source views for convenience:

```sql
CREATE VIEW chatgpt_turns AS SELECT * FROM unified_turns WHERE source = 'chatgpt';
CREATE VIEW claude_turns  AS SELECT * FROM unified_turns WHERE source = 'claude';
CREATE VIEW gemini_turns  AS SELECT * FROM unified_turns WHERE source = 'gemini';
```

## Embeddings Table

```sql
CREATE TABLE turn_embeddings (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    turn_number  INT NOT NULL,
    content_hash TEXT NOT NULL,       -- SHA-256 of content, for incremental re-embedding
    embedding    vector(768),         -- nomic-embed-text-v1.5
    PRIMARY KEY (source, source_id, turn_number),
    FOREIGN KEY (source, source_id) REFERENCES conversations_raw
);

CREATE INDEX idx_turn_embeddings_hnsw
    ON turn_embeddings USING hnsw (embedding vector_cosine_ops);
```

The `content_hash` enables incremental updates — if a turn's content hasn't changed after a re-pull, skip re-embedding.

## Incremental Update Logic

### Per-Conversation Decision

```
for each conversation from API list:
    if (source, source_id) not in conversations_raw:
        → INSERT raw_data + turns (NEW)
    elif api.update_time > conversations_raw.updated_at:
        → UPDATE raw_data + turns (CHANGED)
        → DELETE from turn_embeddings WHERE content_hash differs
        → Re-embed only changed turns
    else:
        → skip (UNCHANGED)
```

### Why Full Turn Replacement for Changed Conversations

ChatGPT conversations are trees. When a user edits message 3, a new branch is created. The canonical path (`children[-1]`) changes, so turn_number N may now be a different message. `ON CONFLICT DO NOTHING` would silently keep stale content.

For changed conversations: replace all turns, then use `content_hash` to avoid re-embedding turns whose content is identical.

## What This Replaces

| Current | JSONB Design |
|---------|-------------|
| `raw/*.json` files | `raw_data` JSONB column |
| `conversations/*.json` files | `turns` JSONB column |
| `manifest.json` | `SELECT source_id, updated_at FROM conversations_raw` |
| `conversations` + `turns` DB tables | Single `conversations_raw` table + views |
| File-based dedup (`already_exported`) | `PRIMARY KEY (source, source_id)` |

## Tradeoffs

- **Pro**: Single source of truth, simpler queries, natural incremental updates
- **Pro**: Raw data queryable via JSONB operators (e.g., find all ChatGPT conversations with branches)
- **Pro**: No file system state to manage or sync
- **Con**: PostgreSQL required for all operations (currently pull works without PG)
- **Con**: Migration from current schema needed
- **Mitigation**: Keep file export as an optional `dump` command for portability

## Migration Path

1. Create new `conversations_raw` table alongside existing tables
2. Bulk-load from existing `raw/*.json` and `conversations/*.json` files
3. Verify row counts match manifest counts
4. Update `pull` commands to write to PG instead of files
5. Update `load` command to read from `conversations_raw` instead of files
6. Update `search` to query `unified_turns` view
7. Keep file-based commands as `export`/`dump` for portability

## Branch Metadata (Future Enhancement)

For conversations with edits/branches, store metadata for discovery:

```json
{
  "branch_count": 3,
  "has_edits": true,
  "canonical_depth": 24,
  "total_nodes": 30
}
```

Query: `WHERE raw_data->'metadata'->>'has_edits' = 'true'`

This lets you find branched conversations without parsing every tree.

---

## Implementation Plan (2026-02-12)

**Status**: In progress

### Architecture Decision: Keep File-Based Interchange

The `conversations/*.json` files remain on disk as the **universal interchange format** — portable, shareable, importable by other tools. The JSONB migration only replaces the PG side.

```
                    ┌─────────────────────────────────┐
                    │         pull (per provider)      │
                    └──────────┬──────────┬────────────┘
                               │          │
                    ┌──────────▼──┐  ┌────▼──────────────┐
                    │ raw/*.json  │  │ conversations/*.json│
                    │ (archival)  │  │ (interchange fmt)   │
                    └──────────┬──┘  └─────────────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   conversations_raw     │
            load    │   (source, source_id)   │
           ──────►  │   raw_data  JSONB       │
                    │   turns     JSONB       │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   turn_embeddings       │
                    │   content_hash + vector │
                    └─────────────────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   unified_turns (view)  │
                    │   search queries here   │
                    └─────────────────────────┘
```

### Loading Strategy

The `load` command reads from **both** file sets per provider:
- `conversations/*.json` — structured metadata (title, source_id, turns, model, dates)
- `raw/{source_id}.json` — archival raw API response

This avoids re-implementing provider-specific parsers in the loader (the parsers already ran at pull time). Gemini's raw files lack title/metadata, so the conversations/ file is the canonical source.

### Files Modified

1. `aishell/commands/conversations/db.py` — SCHEMA_V2_SQL, load_raw_conversation(), embed_and_store_turns()
2. `aishell/commands/conversations/cli.py` — Updated load + search commands
3. `aishell/commands/conversations/__init__.py` — Export new symbols

### Archive

Before migration, raw files archived to `~/.aishell/archive/raw_2026-02-12/` (read-only, 81MB, 1,785 files).

### Steps

1. [ ] Update db.py — new schema + loader functions
2. [ ] Update cli.py load — read from conversations/ + raw/, insert into conversations_raw
3. [ ] Update cli.py search — query turn_embeddings + unified_turns
4. [ ] Update __init__.py — export new symbols
5. [ ] Verify: bulk load 1,764 conversations, check counts, test search
