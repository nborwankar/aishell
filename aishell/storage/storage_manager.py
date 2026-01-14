"""Storage manager for LLM responses."""

import os
import uuid
from typing import Optional, List, Dict, Any
import threading

from .database import Database
from .models import StoredResponse, ResponseMetadata
from .search import SearchQuery, SearchResult


class StorageManager:
    """Manages storage of LLM responses with singleton pattern."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize storage manager.

        Args:
            db_path: Path to SQLite database. If None, uses LLM_RESPONSE_DB
                     from environment or defaults to ~/.aishell/responses.db
        """
        if db_path is None:
            db_path = os.environ.get(
                "LLM_RESPONSE_DB", os.path.expanduser("~/.aishell/responses.db")
            )

        self._db = Database(db_path)
        self._db.initialize()
        self._lock = threading.Lock()

    @property
    def db_path(self) -> str:
        """Get the database path."""
        return str(self._db.db_path)

    def store_response(
        self,
        query: str,
        content: str,
        provider: str,
        model: str,
        session_id: Optional[str] = None,
        is_error: bool = False,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredResponse:
        """Store a single LLM response.

        Returns:
            StoredResponse with assigned ID
        """
        with self._lock:
            conn = self._db.connection
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO responses
                (query, content, provider, model, session_id, is_error, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (query, content, provider, model, session_id, is_error, error_message),
            )

            response_id = cursor.lastrowid

            # Store metadata
            metadata_objects = []
            if metadata:
                for key, value in metadata.items():
                    if value is not None:
                        cursor.execute(
                            """
                            INSERT INTO response_metadata (response_id, key, value)
                            VALUES (?, ?, ?)
                        """,
                            (response_id, key, str(value)),
                        )
                        metadata_objects.append(
                            ResponseMetadata(
                                key=key,
                                value=str(value),
                                response_id=response_id,
                                id=cursor.lastrowid,
                            )
                        )

            conn.commit()

            return StoredResponse(
                id=response_id,
                query=query,
                content=content,
                provider=provider,
                model=model,
                session_id=session_id,
                is_error=is_error,
                error_message=error_message,
                metadata=metadata_objects,
            )

    def store_collation(
        self,
        query: str,
        responses: List[tuple],  # List of (provider_name, LLMResponse)
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[StoredResponse]:
        """Store multiple responses from a collation.

        Args:
            query: The original query
            responses: List of (provider_name, LLMResponse) tuples
            metadata: Shared metadata for all responses

        Returns:
            List of StoredResponse objects with assigned IDs
        """
        session_id = str(uuid.uuid4())
        stored = []

        for provider_name, llm_response in responses:
            # Merge response-specific metadata with shared metadata
            response_meta = dict(metadata) if metadata else {}

            if hasattr(llm_response, "usage") and llm_response.usage:
                response_meta.update(llm_response.usage)

            if hasattr(llm_response, "metadata") and llm_response.metadata:
                response_meta.update(llm_response.metadata)

            # Check for error
            is_error = getattr(llm_response, "is_error", False)
            if not is_error and hasattr(llm_response, "error"):
                is_error = llm_response.error is not None

            stored_response = self.store_response(
                query=query,
                content=llm_response.content if not is_error else "",
                provider=provider_name,
                model=getattr(llm_response, "model", "unknown"),
                session_id=session_id,
                is_error=is_error,
                error_message=llm_response.error if is_error else None,
                metadata=response_meta,
            )
            stored.append(stored_response)

        return stored

    def get_response(self, response_id: int) -> Optional[StoredResponse]:
        """Get a response by ID with its metadata."""
        conn = self._db.connection
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM responses WHERE id = ?", (response_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Get metadata
        cursor.execute(
            "SELECT * FROM response_metadata WHERE response_id = ?", (response_id,)
        )
        metadata_rows = cursor.fetchall()

        return self._row_to_response(row, metadata_rows)

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute a search query."""
        return query.execute(self._db.connection)

    def _row_to_response(self, row, metadata_rows=None) -> StoredResponse:
        """Convert database row to StoredResponse."""
        from datetime import datetime

        metadata = []
        if metadata_rows:
            for m_row in metadata_rows:
                metadata.append(
                    ResponseMetadata(
                        id=m_row["id"],
                        response_id=m_row["response_id"],
                        key=m_row["key"],
                        value=m_row["value"],
                    )
                )

        # Parse created_at
        created_at = row["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = datetime.now()

        return StoredResponse(
            id=row["id"],
            query=row["query"],
            content=row["content"],
            provider=row["provider"],
            model=row["model"],
            created_at=created_at,
            session_id=row["session_id"],
            is_error=bool(row["is_error"]),
            error_message=row["error_message"],
            metadata=metadata,
        )


# Global storage manager instances (keyed by db_path)
_storage_managers: Dict[str, StorageManager] = {}
_storage_lock = threading.Lock()


def get_storage_manager(db_path: Optional[str] = None) -> StorageManager:
    """Get or create a storage manager instance.

    Args:
        db_path: Path to SQLite database. If None, uses LLM_RESPONSE_DB
                 from environment or defaults to ~/.aishell/responses.db

    Returns:
        StorageManager instance for the specified database
    """
    global _storage_managers

    # Resolve the path
    if db_path is None:
        db_path = os.environ.get(
            "LLM_RESPONSE_DB", os.path.expanduser("~/.aishell/responses.db")
        )
    else:
        db_path = os.path.expanduser(db_path)

    db_path = os.path.abspath(db_path)

    with _storage_lock:
        if db_path not in _storage_managers:
            _storage_managers[db_path] = StorageManager(db_path)
        return _storage_managers[db_path]
