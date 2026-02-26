# Hybrid Search: Keyword Fallback for Novel Terms

## Context

Pure semantic search fails on coined/novel terms like "flatoon" — the embedding
model has no semantic understanding of these words and maps them to the nearest
known concept ("flat" → FAISS Flat index). The actual "Flatoon Engine Design &
Implementation" conversation (266 chunks in Gemini) never surfaces.

Solution: hybrid search that combines semantic similarity with keyword matching
on `chunk_text` and `conversations_raw.title`. Keyword hits get a synthetic
similarity score and are merged with semantic results, deduplicated.

## Strategy

Use PostgreSQL's built-in `ILIKE` for keyword matching (no need for
`tsvector`/FTS — queries are short phrases, not full-text). Run both queries,
merge results, deduplicate by `(source, source_id, turn_number, chunk_number)`.

```
Query: "flatoon"

1. Semantic search  → top N by cosine similarity     (may miss novel terms)
2. Keyword search   → ILIKE '%flatoon%' on chunk_text + title  (catches exact matches)
3. Merge + dedup    → union, prefer higher score, cap at --limit
```

## Files to Modify

1. **`aishell/commands/conversations/cli.py`** — Rewrite `search` to run both queries and merge results

No schema changes. No changes to `db.py`, `__init__.py`, or `embeddings.py`.

## Step-by-Step

### Step 1: cli.py — Add keyword query

After the semantic query, run a second query that matches on `chunk_text` or
`conversations_raw.title` using `ILIKE`:

```sql
SELECT
    ce.role,
    ce.chunk_text,
    c.title,
    c.source,
    1.0 AS similarity          -- keyword matches get score 1.0
FROM chunk_embeddings ce
JOIN conversations_raw c
    ON ce.source = c.source AND ce.source_id = c.source_id
WHERE (ce.chunk_text ILIKE %s OR c.title ILIKE %s)
  [AND c.source = %s]         -- optional source filter
LIMIT %s
```

The `%s` pattern parameter is `%{query}%` (wrapped in wildcards).

### Step 2: cli.py — Merge and deduplicate results

1. Run semantic query → `semantic_rows`
2. Run keyword query → `keyword_rows`
3. Build dict keyed by `(source, title, chunk_text[:100])` — semantic results first
4. Add keyword results that aren't already present
5. Sort by similarity descending, cap at `--limit`

### Step 3: cli.py — Add "Match" column to results table

Add a column showing match type: `sem` for semantic-only, `kw` for keyword-only,
`both` for results found by both methods. Helps the user understand why a result
appeared.

## What We DON'T Change

- `db.py` — no schema changes
- `__init__.py` — no export changes
- `embeddings.py` — untouched
- Semantic search behavior — identical for known terms
- No new indexes needed (ILIKE on 73K rows is fast enough)

## Verification

1. `aishell conversations search "flatoon"` — should surface Flatoon Engine chunks
2. `aishell conversations search "flatoons"` — same
3. `aishell conversations search "flatoon" --source gemini` — Gemini results appear
4. `aishell conversations search "manifold geometry"` — still works (semantic dominates)
5. `aishell conversations search "FDL"` — keyword catches this acronym
