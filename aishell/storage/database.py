"""Database connection and schema management."""

import sqlite3
from pathlib import Path
import threading

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS error_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS response_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    start_id INTEGER,
    parent_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_responses_provider ON responses(provider);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);
CREATE INDEX IF NOT EXISTS idx_responses_session_id ON responses(session_id);
CREATE INDEX IF NOT EXISTS idx_error_responses_provider ON error_responses(provider);
CREATE INDEX IF NOT EXISTS idx_error_responses_created_at ON error_responses(created_at);
CREATE INDEX IF NOT EXISTS idx_error_responses_session_id ON error_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_metadata_response_id ON response_metadata(response_id);
CREATE INDEX IF NOT EXISTS idx_metadata_key ON response_metadata(key);
CREATE INDEX IF NOT EXISTS idx_conv_conversation_id ON conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_provider ON conversations(provider);
CREATE INDEX IF NOT EXISTS idx_conv_start_id ON conversations(start_id);
CREATE INDEX IF NOT EXISTS idx_conv_parent_id ON conversations(parent_id);
"""


class Database:
    """Thread-safe SQLite database wrapper."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the current thread's connection."""
        return self._get_connection()

    def initialize(self) -> None:
        """Initialize database schema."""
        with self._init_lock:
            if self._initialized:
                return

            # Create parent directories
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = self._get_connection()

            # Check current schema version
            current_version = 0
            try:
                cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
                row = cursor.fetchone()
                if row:
                    current_version = row[0]
            except sqlite3.OperationalError:
                # Table doesn't exist yet
                pass

            # Run migrations if needed
            if current_version < SCHEMA_VERSION:
                self._migrate(conn, current_version)

            conn.executescript(SCHEMA_SQL)

            # Set schema version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()
            self._initialized = True

    def _migrate(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Run migrations from from_version to current SCHEMA_VERSION."""
        if from_version == 1:
            # Migration v1 -> v2: Create error_responses table and migrate errors
            # Only run this if upgrading from v1 (has old schema with is_error column)

            # Check if old responses table exists with is_error column
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(responses)")
            columns = {row[1] for row in cursor.fetchall()}

            if "is_error" in columns:
                # Create error_responses table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS error_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        error_message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_id TEXT
                    )
                """
                )

                # Move existing errors to error_responses table
                conn.execute(
                    """
                    INSERT INTO error_responses (query, provider, model, error_message, created_at, session_id)
                    SELECT query, provider, model,
                           COALESCE(error_message, content), created_at, session_id
                    FROM responses
                    WHERE is_error = 1
                """
                )

                # Delete errors from responses table
                conn.execute("DELETE FROM responses WHERE is_error = 1")

                # Remove is_error and error_message columns by recreating table
                # SQLite doesn't support DROP COLUMN in older versions
                conn.execute(
                    """
                    CREATE TABLE responses_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        content TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_id TEXT
                    )
                """
                )
                conn.execute(
                    """
                    INSERT INTO responses_new (id, query, content, provider, model, created_at, session_id)
                    SELECT id, query, content, provider, model, created_at, session_id
                    FROM responses
                """
                )
                conn.execute("DROP TABLE responses")
                conn.execute("ALTER TABLE responses_new RENAME TO responses")

                conn.commit()

        # Migration v2 -> v3: Add conversations table
        # No migration needed - table will be created by SCHEMA_SQL

    def close(self) -> None:
        """Close the current thread's connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
