"""Database connection and schema management."""

import sqlite3
from pathlib import Path
import threading

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    is_error BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS response_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_responses_provider ON responses(provider);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);
CREATE INDEX IF NOT EXISTS idx_responses_session_id ON responses(session_id);
CREATE INDEX IF NOT EXISTS idx_metadata_response_id ON response_metadata(response_id);
CREATE INDEX IF NOT EXISTS idx_metadata_key ON response_metadata(key);
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
            conn.executescript(SCHEMA_SQL)

            # Set schema version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()
            self._initialized = True

    def close(self) -> None:
        """Close the current thread's connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
