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
            "metadata": {m.key: m.value for m in self.metadata},
        }


@dataclass
class StoredError:
    """A stored LLM error response."""

    query: str
    provider: str
    model: str
    error_message: str
    created_at: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "query": self.query,
            "provider": self.provider,
            "model": self.model,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "session_id": self.session_id,
        }


@dataclass
class ConversationMessage:
    """A message in a multi-turn conversation."""

    conversation_id: str
    provider: str
    model: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    start_id: Optional[int] = None  # ID of first message in thread
    parent_id: Optional[int] = None  # Previous message ID
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "provider": self.provider,
            "model": self.model,
            "role": self.role,
            "content": self.content,
            "start_id": self.start_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
