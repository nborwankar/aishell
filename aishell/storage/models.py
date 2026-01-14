"""Data models for storage."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class ResponseMetadata:
    """Metadata for a stored response."""

    key: str
    value: str
    response_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class StoredResponse:
    """A stored LLM response with metadata."""

    query: str
    content: str
    provider: str
    model: str
    created_at: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    is_error: bool = False
    error_message: Optional[str] = None
    id: Optional[int] = None
    metadata: List[ResponseMetadata] = field(default_factory=list)

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value by key."""
        for m in self.metadata:
            if m.key == key:
                return m.value
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "query": self.query,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "session_id": self.session_id,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "metadata": {m.key: m.value for m in self.metadata},
        }
