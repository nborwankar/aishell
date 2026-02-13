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

    # Create extension and tables (v1 + v2)
    conn = psycopg2.connect(dbname=db_name)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        for schema in (SCHEMA_SQL, SCHEMA_V2_SQL):
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


def embed_and_store_turns(conn, source, source_id, turns, skip_embeddings=False):
    """Embed turns and store in turn_embeddings. Uses content_hash to skip unchanged.

    Returns the number of turns embedded.
    """
    if skip_embeddings:
        return 0

    # Build turn data with content hashes (1-indexed to match WITH ORDINALITY)
    turn_data = []
    for i, turn in enumerate(turns):
        content = turn.get("content", "")
        if not content.strip():
            continue
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        turn_data.append((i + 1, content, content_hash))

    if not turn_data:
        return 0

    # Check which turns already have matching hashes
    with conn.cursor() as cur:
        cur.execute(
            """SELECT turn_number, content_hash FROM turn_embeddings
               WHERE source = %s AND source_id = %s""",
            (source, source_id),
        )
        existing = {row[0]: row[1] for row in cur.fetchall()}

    # Find turns needing (re-)embedding
    to_embed = []
    for turn_number, content, content_hash in turn_data:
        if existing.get(turn_number) != content_hash:
            to_embed.append((turn_number, content, content_hash))

    if not to_embed:
        return 0

    # Generate embeddings
    texts = [content for _, content, _ in to_embed]
    embeddings = embed_texts(texts)

    # UPSERT into turn_embeddings
    with conn.cursor() as cur:
        for (turn_number, content, content_hash), emb in zip(to_embed, embeddings):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute(
                """INSERT INTO turn_embeddings
                   (source, source_id, turn_number, content_hash, embedding)
                   VALUES (%s, %s, %s, %s, %s::vector)
                   ON CONFLICT (source, source_id, turn_number) DO UPDATE
                   SET content_hash = EXCLUDED.content_hash,
                       embedding = EXCLUDED.embedding""",
                (source, source_id, turn_number, content_hash, emb_str),
            )
    conn.commit()
    return len(to_embed)
