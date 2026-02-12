"""Database utilities for conversation storage.

Handles PostgreSQL + pgvector provisioning and conversation loading.
"""

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

    # Create extension and tables
    conn = psycopg2.connect(dbname=db_name)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        for statement in SCHEMA_SQL.split(";"):
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
