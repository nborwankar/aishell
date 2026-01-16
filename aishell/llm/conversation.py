"""Multi-turn conversation management for LLM providers."""

import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from ..storage import get_storage_manager, ConversationMessage


@dataclass
class Message:
    """A message in a conversation."""

    role: str  # 'user', 'assistant', 'system'
    content: str


class Conversation:
    """Manages multi-turn conversations with persistence.

    Supports:
    - Adding user and assistant messages
    - Persisting to database with threading
    - Loading existing conversations
    - Converting to API-ready format
    """

    def __init__(
        self,
        provider: str,
        model: str,
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize a conversation.

        Args:
            provider: LLM provider name (e.g., 'openai', 'claude')
            model: Model name
            conversation_id: Existing conversation ID to continue, or None for new
            system_prompt: Optional system prompt to prepend to conversations
        """
        self.provider = provider
        self.model = model
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.system_prompt = system_prompt
        self.messages: List[Message] = []
        self._storage = get_storage_manager()

        # Add system prompt as first message if provided
        if system_prompt and not conversation_id:
            self.messages.append(Message(role="system", content=system_prompt))

    def add_user_message(self, content: str) -> ConversationMessage:
        """Add a user message to the conversation.

        Args:
            content: The user's message

        Returns:
            The persisted ConversationMessage
        """
        self.messages.append(Message(role="user", content=content))
        return self._storage.add_message(
            conversation_id=self.conversation_id,
            provider=self.provider,
            model=self.model,
            role="user",
            content=content,
        )

    def add_assistant_message(self, content: str) -> ConversationMessage:
        """Add an assistant response to the conversation.

        Args:
            content: The assistant's response

        Returns:
            The persisted ConversationMessage
        """
        self.messages.append(Message(role="assistant", content=content))
        return self._storage.add_message(
            conversation_id=self.conversation_id,
            provider=self.provider,
            model=self.model,
            role="assistant",
            content=content,
        )

    def add_system_message(self, content: str) -> ConversationMessage:
        """Add a system message to the conversation.

        Args:
            content: The system message

        Returns:
            The persisted ConversationMessage
        """
        self.messages.append(Message(role="system", content=content))
        return self._storage.add_message(
            conversation_id=self.conversation_id,
            provider=self.provider,
            model=self.model,
            role="system",
            content=content,
        )

    def get_messages(self) -> List[Message]:
        """Get all messages in the conversation.

        Returns:
            List of Message objects
        """
        return self.messages.copy()

    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """Get messages in API-ready format.

        Returns:
            List of dicts with 'role' and 'content' keys
            (compatible with OpenAI, Claude, etc.)
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def get_history(self) -> List[ConversationMessage]:
        """Get the full conversation history from database.

        Returns:
            List of ConversationMessage objects in chronological order
        """
        return self._storage.get_conversation_history(self.conversation_id)

    def clear(self) -> None:
        """Clear in-memory messages (does not affect database)."""
        self.messages = []
        if self.system_prompt:
            self.messages.append(Message(role="system", content=self.system_prompt))

    @classmethod
    def load(cls, conversation_id: str) -> "Conversation":
        """Load an existing conversation from database.

        Args:
            conversation_id: UUID of the conversation to load

        Returns:
            Conversation instance with loaded messages

        Raises:
            ValueError: If conversation not found
        """
        storage = get_storage_manager()
        history = storage.get_conversation_history(conversation_id)

        if not history:
            raise ValueError(f"Conversation not found: {conversation_id}")

        # Get provider and model from first message
        first_msg = history[0]
        conv = cls(
            provider=first_msg.provider,
            model=first_msg.model,
            conversation_id=conversation_id,
        )

        # Load all messages
        for msg in history:
            conv.messages.append(Message(role=msg.role, content=msg.content))

        return conv

    @classmethod
    def list_recent(
        cls, provider: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent conversations.

        Args:
            provider: Filter by provider (optional)
            limit: Maximum number of conversations

        Returns:
            List of conversation summaries
        """
        storage = get_storage_manager()
        return storage.list_conversations(provider=provider, limit=limit)

    def __len__(self) -> int:
        """Return the number of messages in the conversation."""
        return len(self.messages)

    def __repr__(self) -> str:
        return (
            f"Conversation(id={self.conversation_id[:8]}..., "
            f"provider={self.provider}, "
            f"messages={len(self.messages)})"
        )
