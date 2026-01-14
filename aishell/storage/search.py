"""Search functionality for stored responses."""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .models import StoredResponse, ResponseMetadata


@dataclass
class SearchResult:
    """Result of a search query."""

    responses: List[StoredResponse]
    total_count: int
    query_params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_count": self.total_count,
            "responses": [r.to_dict() for r in self.responses],
            "query_params": self.query_params,
        }


@dataclass
class SearchQuery:
    """Builder for search queries."""

    # Text search
    query_contains: Optional[str] = None
    content_contains: Optional[str] = None

    # Filters
    providers: Optional[List[str]] = None
    models: Optional[List[str]] = None
    session_id: Optional[str] = None
    include_errors: bool = True

    # Date range
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

    # Pagination
    limit: int = 50
    offset: int = 0

    # Sorting
    order_by: str = "created_at"
    order_desc: bool = True

    def execute(self, conn: sqlite3.Connection) -> SearchResult:
        """Execute the search query."""
        # Build WHERE clause
        conditions = []
        params = []

        if self.query_contains:
            conditions.append("query LIKE ?")
            params.append(f"%{self.query_contains}%")

        if self.content_contains:
            conditions.append("content LIKE ?")
            params.append(f"%{self.content_contains}%")

        if self.providers:
            placeholders = ",".join("?" * len(self.providers))
            conditions.append(f"provider IN ({placeholders})")
            params.extend(self.providers)

        if self.models:
            placeholders = ",".join("?" * len(self.models))
            conditions.append(f"model IN ({placeholders})")
            params.extend(self.models)

        if self.session_id:
            conditions.append("session_id = ?")
            params.append(self.session_id)

        if not self.include_errors:
            conditions.append("is_error = 0")

        if self.from_date:
            conditions.append("created_at >= ?")
            params.append(self.from_date.isoformat())

        if self.to_date:
            conditions.append("created_at <= ?")
            params.append(self.to_date.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM responses WHERE {where_clause}"
        cursor = conn.cursor()
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        # Build ORDER BY
        order_dir = "DESC" if self.order_desc else "ASC"
        valid_columns = ["created_at", "provider", "model", "query"]
        order_col = self.order_by if self.order_by in valid_columns else "created_at"

        # Execute main query
        sql = f"""
            SELECT * FROM responses
            WHERE {where_clause}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        query_params = params + [self.limit, self.offset]

        cursor.execute(sql, query_params)
        rows = cursor.fetchall()

        # Get metadata for each response
        responses = []
        for row in rows:
            cursor.execute(
                "SELECT * FROM response_metadata WHERE response_id = ?", (row["id"],)
            )
            metadata_rows = cursor.fetchall()

            metadata = [
                ResponseMetadata(
                    id=m["id"],
                    response_id=m["response_id"],
                    key=m["key"],
                    value=m["value"],
                )
                for m in metadata_rows
            ]

            # Parse created_at
            created_at = row["created_at"]
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except ValueError:
                    created_at = datetime.now()

            responses.append(
                StoredResponse(
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
            )

        return SearchResult(
            responses=responses,
            total_count=total_count,
            query_params={
                "query_contains": self.query_contains,
                "content_contains": self.content_contains,
                "providers": self.providers,
                "limit": self.limit,
                "offset": self.offset,
            },
        )

    # Convenience factory methods
    @classmethod
    def by_provider(cls, provider: str, limit: int = 50) -> "SearchQuery":
        """Search responses by provider."""
        return cls(providers=[provider], limit=limit)

    @classmethod
    def by_session(cls, session_id: str) -> "SearchQuery":
        """Search responses by session (collation group)."""
        return cls(session_id=session_id, limit=1000)

    @classmethod
    def recent(cls, hours: int = 24, limit: int = 50) -> "SearchQuery":
        """Search recent responses."""
        return cls(from_date=datetime.now() - timedelta(hours=hours), limit=limit)

    @classmethod
    def full_text(cls, text: str, limit: int = 50) -> "SearchQuery":
        """Search in both query and content fields."""
        return cls(query_contains=text, limit=limit)
