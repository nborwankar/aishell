# Paragraph-Level Chunking Migration

## Context

The aishell embedding system currently embeds entire turns as single units.
Long assistant responses (covering multiple topics across paragraphs) get
mashed into one vector, making search imprecise. Paragraphs are natural
semantic units — splitting on `\n\n` gives better search granularity with
minimal truncation (most paragraphs are well under 2048 tokens).

Additionally, embedding each paragraph with a context prefix
`[conversation_title] role: paragraph_text` helps the embedding model
disambiguate content that would be ambiguous in isolation.

```
BEFORE (turn-level):                    AFTER (paragraph-level):

Turn 2 (assistant, 4 paragraphs)       Turn 2, chunk 1 → embedding
    → 1 embedding (first 2048 tokens)   Turn 2, chunk 2 → embedding
                                        Turn 2, chunk 3 → embedding
                                        Turn 2, chunk 4 → embedding
```

## Files to Modify

1. **`aishell/commands/conversations/db.py`** — New schema, chunking function, rewrite embed function
2. **`aishell/commands/conversations/cli.py`** — Update load call + rewrite search SQL
3. **`aishell/commands/conversations/__init__.py`** — Update exports

**No changes**: `embeddings.py` (embed_texts already handles `search_document:` prefix)

## Step-by-Step

### Step 1: db.py — Add `SCHEMA_V3_SQL`

Drop old `turn_embeddings`, create new `chunk_embeddings`:

```sql
DROP TABLE IF EXISTS turn_embeddings;

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    turn_number  INT NOT NULL,
    chunk_number INT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    chunk_text   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding    vector(768),
    PRIMARY KEY (source, source_id, turn_number, chunk_number),
    FOREIGN KEY (source, source_id) REFERENCES conversations_raw
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_hnsw
    ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);
```

Key columns:
- `chunk_number` — 1-indexed within each turn
- `role` — denormalized from JSONB turn (avoids joins in search)
- `chunk_text` — raw paragraph text (for display, NO context prefix)
- `content_hash` — SHA-256 of raw paragraph (not prefixed version)

Update `ensure_database()` to run `SCHEMA_V3_SQL` after V2.

### Step 2: db.py — Add `split_turn_into_chunks()`

```python
def split_turn_into_chunks(content, min_chars=50):
    """Split on \n\n, merge short paragraphs (<min_chars) into previous."""
```

- Split on `\n\n`
- Merge paragraphs shorter than 50 chars into previous (avoids embedding "Sure!" etc.)
- Returns list of paragraph strings (single-element list if no splits)

### Step 3: db.py — Replace `embed_and_store_turns()` with `embed_and_store_chunks()`

New signature adds `title`:

```python
def embed_and_store_chunks(conn, source, source_id, title, turns, skip_embeddings=False):
```

Logic:
1. For each turn, split into paragraphs via `split_turn_into_chunks()`
2. For each paragraph, compute `content_hash = sha256(raw_paragraph)`
3. Check existing hashes in `chunk_embeddings` — skip unchanged
4. Build context-prefixed text: `[{title}] {role}: {paragraph}`
5. Call `embed_texts()` (which adds `search_document:` prefix)
6. UPSERT into `chunk_embeddings` with raw paragraph as `chunk_text`

Remove old `embed_and_store_turns()` (table is dropped anyway).

### Step 4: cli.py — Update `load` command

- Change import: `embed_and_store_chunks` instead of `embed_and_store_turns`
- Pass `title` to the new function: `embed_and_store_chunks(conn, prov_name, source_id, title, jsonb_turns)`
- Change summary label: "Chunks embedded" instead of "Turns embedded"

### Step 5: cli.py — Rewrite `search` SQL

Replace LATERAL join with direct query on `chunk_embeddings`:

```sql
SELECT
    ce.role,
    ce.chunk_text,
    c.title,
    c.source,
    1 - (ce.embedding <=> %s::vector) AS similarity
FROM chunk_embeddings ce
JOIN conversations_raw c
    ON ce.source = c.source AND ce.source_id = c.source_id
WHERE ce.embedding IS NOT NULL
ORDER BY ce.embedding <=> %s::vector
LIMIT %s
```

Performance win: eliminates the LATERAL + `jsonb_array_elements()` per result row.

Add source filter variant with `AND c.source = %s`.

### Step 6: __init__.py — Update exports

- Replace `embed_and_store_turns` with `embed_and_store_chunks`
- Add `split_turn_into_chunks`
- Add `SCHEMA_V3_SQL`

## Data Flow

```
                    load command (cli.py)
                            │
                ┌───────────┴───────────┐
                │  For each conversation │
                │  title, turns[]       │
                └───────────┬───────────┘
                            │
           embed_and_store_chunks(conn, source, source_id, title, turns)
                            │
                ┌───────────┴───────────┐
                │  For each turn:       │
                │    split on \n\n      │
                │    merge <50 chars    │
                │    → paragraphs[]     │
                └───────────┬───────────┘
                            │
                ┌───────────┴───────────┐
                │  For each paragraph:  │
                │    hash = sha256(raw) │
                │    text = "[title]    │
                │      role: raw_para"  │
                └───────────┬───────────┘
                            │
                ┌───────────┴───────────┐
                │  embed_texts([...])   │
                │  adds "search_document:" │
                │  → vectors[]         │
                └───────────┬───────────┘
                            │
                ┌───────────┴───────────┐
                │  UPSERT into         │
                │  chunk_embeddings:    │
                │    chunk_text = raw   │
                │    embedding = vector │
                └───────────────────────┘


                    search command
                            │
                ┌───────────┴───────────┐
                │  model.encode(        │
                │    "search_query: Q") │
                │  (NO context prefix)  │
                └───────────┬───────────┘
                            │
                ┌───────────┴───────────┐
                │  SELECT chunk_text,   │
                │    role, title, source │
                │  FROM chunk_embeddings│
                │  JOIN conversations_raw│
                │  ORDER BY cosine dist │
                └───────────────────────┘
```

## What We DON'T Change

- `conversations_raw` table — untouched
- `embeddings.py` — `embed_texts()` already handles `search_document:` prefix
- Search query embedding — stays `search_query: {query}` (no context prefix on queries)
- `unified_turns` view — still useful for non-search queries
- Old `SCHEMA_V2_SQL` — kept in code for reference

## Verification

1. `aishell conversations load` — re-embeds all conversations as paragraph chunks
2. `psql conversation_export -c "SELECT count(*) FROM chunk_embeddings"` — expect >11,623 (more chunks than turns)
3. `psql conversation_export -c "SELECT source, count(*) FROM chunk_embeddings GROUP BY source"` — verify per-provider
4. `aishell conversations search "manifold geometry"` — returns paragraph-level results
5. Check memory stays stable (~2 GB, no leak)
