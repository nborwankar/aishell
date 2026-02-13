"""Database utilities for conversation storage.

Handles PostgreSQL + pgvector provisioning and conversation loading.
"""

import hashlib
import json
import logging

from .embeddings import embed_texts

logger = logging.getLogger(__name__)

DB_NAME = "conversation_export"

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('gemini', 'chatgpt', 'claude')),
    source_id       TEXT,
    source_url      TEXT,
    model           TEXT,
    created_at      TIMESTAMPTZ,
    exported_at     TIMESTAMPTZ NOT NULL,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    turn_count      INT NOT NULL DEFAULT 0,
    user_turns      INT NOT NULL DEFAULT 0,
    assistant_turns INT NOT NULL DEFAULT 0,
    total_chars     INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    id              SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_number     INT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    timestamp       TIMESTAMPTZ,
    attachments     JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    embedding       vector(768),
    UNIQUE (conversation_id, turn_number)
);

CREATE INDEX IF NOT EXISTS idx_turns_embedding
    ON turns USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_turns_conversation_id
    ON turns (conversation_id);
CREATE INDEX IF NOT EXISTS idx_turns_role
    ON turns (role);
CREATE INDEX IF NOT EXISTS idx_conversations_source
    ON conversations (source);
"""

SCHEMA_V2_SQL = """
CREATE TABLE IF NOT EXISTS conversations_raw (
    source      TEXT NOT NULL CHECK (source IN ('gemini','chatgpt','claude')),
    source_id   TEXT NOT NULL,
    title       TEXT,
    raw_data    JSONB NOT NULL,
    turns       JSONB NOT NULL,
    model       TEXT,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS turn_embeddings (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    turn_number  INT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding    vector(768),
    PRIMARY KEY (source, source_id, turn_number),
    FOREIGN KEY (source, source_id) REFERENCES conversations_raw
);

CREATE INDEX IF NOT EXISTS idx_turn_embeddings_hnsw
    ON turn_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE VIEW unified_turns AS
SELECT
    c.source, c.source_id, c.title, c.model,
    t.ord AS turn_number,
    t.turn->>'role' AS role,
    t.turn->>'content' AS content,
    t.turn->>'timestamp' AS timestamp
FROM conversations_raw c,
     jsonb_array_elements(c.turns) WITH ORDINALITY AS t(turn, ord);
"""

SCHEMA_V3_SQL = """
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
"""


def list_conversations(conn, source=None, limit=None):
    """Return conversations as list of (source, source_id, title, model, created_at, turn_count).

    Sorted alphabetically by title. Optional source filter and limit.
    """
    with conn.cursor() as cur:
        if source:
            cur.execute(
                """SELECT source, source_id, title, model, created_at,
                          jsonb_array_length(turns) AS turn_count
                   FROM conversations_raw
                   WHERE source = %s
                   ORDER BY title
                   LIMIT %s""",
                (source, limit or 10000),
            )
        else:
            cur.execute(
                """SELECT source, source_id, title, model, created_at,
                          jsonb_array_length(turns) AS turn_count
                   FROM conversations_raw
                   ORDER BY title
                   LIMIT %s""",
                (limit or 10000,),
            )
        return cur.fetchall()


def get_conversation_turns(conn, source, source_id):
    """Return ordered turns for a conversation from JSONB.

    Returns list of (turn_number, role, content) tuples.
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT t.ord AS turn_number,
                      t.turn->>'role' AS role,
                      t.turn->>'content' AS content
               FROM conversations_raw c,
                    jsonb_array_elements(c.turns) WITH ORDINALITY AS t(turn, ord)
               WHERE c.source = %s AND c.source_id = %s
               ORDER BY t.ord""",
            (source, source_id),
        )
        return cur.fetchall()


def search_conversations_by_keyword(conn, query, source=None, limit=20):
    """Return conversations containing keyword, with hit count.

    Returns list of (title, source, source_id, hits, turn_count) tuples,
    sorted by hits descending.
    """
    kw_pattern = f"%{query}%"
    with conn.cursor() as cur:
        if source:
            cur.execute(
                """SELECT c.title, c.source, c.source_id,
                          COUNT(*) AS hits,
                          jsonb_array_length(c.turns) AS turn_count
                   FROM chunk_embeddings ce
                   JOIN conversations_raw c
                       ON ce.source = c.source AND ce.source_id = c.source_id
                   WHERE (ce.chunk_text ILIKE %s OR c.title ILIKE %s)
                     AND c.source = %s
                   GROUP BY c.title, c.source, c.source_id, c.turns
                   ORDER BY hits DESC
                   LIMIT %s""",
                (kw_pattern, kw_pattern, source, limit),
            )
        else:
            cur.execute(
                """SELECT c.title, c.source, c.source_id,
                          COUNT(*) AS hits,
                          jsonb_array_length(c.turns) AS turn_count
                   FROM chunk_embeddings ce
                   JOIN conversations_raw c
                       ON ce.source = c.source AND ce.source_id = c.source_id
                   WHERE ce.chunk_text ILIKE %s OR c.title ILIKE %s
                   GROUP BY c.title, c.source, c.source_id, c.turns
                   ORDER BY hits DESC
                   LIMIT %s""",
                (kw_pattern, kw_pattern, limit),
            )
        return cur.fetchall()


def ensure_database(db_name):
    """Create database, extension, and tables if they don't exist."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Check if database exists, create if not
    conn = psycopg2.connect(dbname="postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            logger.info(f"Creating database '{db_name}'...")
            cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()

    # Create extension and tables (v1 + v2 + v3)
    conn = psycopg2.connect(dbname=db_name)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        for schema in (SCHEMA_SQL, SCHEMA_V2_SQL, SCHEMA_V3_SQL):
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
    conn.close()
    logger.info("Database schema verified")


def load_conversation(conn, conv_data, skip_embeddings=False):
    """Load a single conversation into the database. Returns True if loaded."""
    from psycopg2.extras import execute_values

    conv = conv_data["conversation"]
    turns = conv_data["turns"]
    stats = conv_data["statistics"]

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM conversations WHERE id = %s", (conv["id"],))
        if cur.fetchone():
            return False

        cur.execute(
            """INSERT INTO conversations
               (id, title, source, source_id, source_url, model,
                created_at, exported_at, tags, metadata,
                turn_count, user_turns, assistant_turns, total_chars)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                conv["id"],
                conv["title"],
                conv["source"],
                conv.get("source_id"),
                conv.get("source_url"),
                conv.get("model"),
                conv.get("created_at"),
                conv["exported_at"],
                conv.get("tags", []),
                json.dumps(conv.get("metadata", {})),
                stats["turn_count"],
                stats["user_turns"],
                stats["assistant_turns"],
                stats["total_chars"],
            ),
        )

        contents = [t["content"] for t in turns]
        if skip_embeddings:
            embeddings = [None] * len(turns)
        else:
            embeddings = embed_texts(contents)

        turn_rows = []
        for turn, emb in zip(turns, embeddings):
            emb_str = None
            if emb is not None:
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            turn_rows.append(
                (
                    conv["id"],
                    turn["turn_number"],
                    turn["role"],
                    turn["content"],
                    turn.get("timestamp"),
                    json.dumps(turn.get("attachments", [])),
                    json.dumps(turn.get("metadata", {})),
                    emb_str,
                )
            )

        execute_values(
            cur,
            """INSERT INTO turns
               (conversation_id, turn_number, role, content,
                timestamp, attachments, metadata, embedding)
               VALUES %s""",
            turn_rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s::vector)",
        )

    conn.commit()
    return True


def load_raw_conversation(
    conn,
    source,
    source_id,
    title,
    raw_data,
    turns,
    model=None,
    created_at=None,
    updated_at=None,
):
    """Load a conversation into conversations_raw. Returns True if inserted."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO conversations_raw
               (source, source_id, title, raw_data, turns, model, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (
                source,
                source_id,
                title,
                json.dumps(raw_data),
                json.dumps(turns),
                model,
                created_at,
                updated_at,
            ),
        )
        inserted = cur.rowcount > 0
    conn.commit()
    return inserted


def split_turn_into_chunks(content, min_chars=50):
    """Split on \\n\\n, merge short paragraphs (<min_chars) into previous.

    Returns list of paragraph strings (single-element list if no splits).
    """
    if not content or not content.strip():
        return []

    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    # Merge short paragraphs into previous
    merged = [paragraphs[0]]
    for p in paragraphs[1:]:
        if len(p) < min_chars and merged:
            merged[-1] = merged[-1] + "\n\n" + p
        else:
            merged.append(p)

    return merged


def embed_and_store_chunks(
    conn, source, source_id, title, turns, skip_embeddings=False
):
    """Embed paragraph-level chunks and store in chunk_embeddings.

    Each turn is split into paragraphs. Each paragraph is embedded with a
    context prefix: [{title}] {role}: {paragraph}

    Uses content_hash (of raw paragraph) to skip unchanged chunks.
    Returns the number of chunks embedded.
    """
    if skip_embeddings:
        return 0

    # Build chunk data: (turn_number, chunk_number, role, raw_text, content_hash)
    chunk_data = []
    for i, turn in enumerate(turns):
        content = turn.get("content", "")
        role = turn.get("role", "user")
        turn_number = i + 1  # 1-indexed to match WITH ORDINALITY
        paragraphs = split_turn_into_chunks(content)
        for j, paragraph in enumerate(paragraphs):
            chunk_number = j + 1  # 1-indexed
            content_hash = hashlib.sha256(paragraph.encode()).hexdigest()
            chunk_data.append(
                (turn_number, chunk_number, role, paragraph, content_hash)
            )

    if not chunk_data:
        return 0

    # Check which chunks already have matching hashes
    with conn.cursor() as cur:
        cur.execute(
            """SELECT turn_number, chunk_number, content_hash FROM chunk_embeddings
               WHERE source = %s AND source_id = %s""",
            (source, source_id),
        )
        existing = {(row[0], row[1]): row[2] for row in cur.fetchall()}

    # Find chunks needing (re-)embedding
    to_embed = []
    for turn_number, chunk_number, role, paragraph, content_hash in chunk_data:
        if existing.get((turn_number, chunk_number)) != content_hash:
            to_embed.append((turn_number, chunk_number, role, paragraph, content_hash))

    if not to_embed:
        return 0

    # Build context-prefixed texts for embedding
    prefixed_texts = [
        f"[{title}] {role}: {paragraph}" for _, _, role, paragraph, _ in to_embed
    ]
    embeddings = embed_texts(prefixed_texts)

    # UPSERT into chunk_embeddings (store raw paragraph, not prefixed)
    stored = 0
    with conn.cursor() as cur:
        for (turn_number, chunk_number, role, paragraph, content_hash), emb in zip(
            to_embed, embeddings
        ):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute(
                """INSERT INTO chunk_embeddings
                   (source, source_id, turn_number, chunk_number, role,
                    chunk_text, content_hash, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                   ON CONFLICT (source, source_id, turn_number, chunk_number) DO UPDATE
                   SET role = EXCLUDED.role,
                       chunk_text = EXCLUDED.chunk_text,
                       content_hash = EXCLUDED.content_hash,
                       embedding = EXCLUDED.embedding""",
                (
                    source,
                    source_id,
                    turn_number,
                    chunk_number,
                    role,
                    paragraph,
                    content_hash,
                    emb_str,
                ),
            )
            stored += 1
    conn.commit()
    return stored
