"""Conversation persistence repositories."""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from core.contracts.chat import ChatConversation, ChatMessage, WorkspaceAttachment
from core.persistence import PostgresJsonDocumentStore


class ChatConversationRepository(ABC):
    """Conversation persistence boundary."""

    @abstractmethod
    async def save(self, conversation: ChatConversation) -> ChatConversation:
        """Save a conversation."""

    @abstractmethod
    async def get(self, conversation_id: UUID) -> ChatConversation:
        """Get a conversation."""

    @abstractmethod
    async def list(self) -> tuple[ChatConversation, ...]:
        """List conversations."""

    @abstractmethod
    async def add_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        """Add a message."""

    @abstractmethod
    async def add_attachment(self, conversation_id: UUID, attachment: WorkspaceAttachment) -> ChatConversation:
        """Add an attachment."""

    @abstractmethod
    async def delete(self, conversation_id: UUID) -> None:
        """Delete a conversation."""

    @abstractmethod
    async def update_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        """Update one message within a conversation."""


class InMemoryChatConversationRepository(ChatConversationRepository):
    """In-memory conversation persistence."""

    def __init__(self) -> None:
        self._conversations: dict[UUID, ChatConversation] = {}

    async def save(self, conversation: ChatConversation) -> ChatConversation:
        updated = conversation.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._conversations[updated.id] = updated
        return updated

    async def get(self, conversation_id: UUID) -> ChatConversation:
        return self._conversations[conversation_id]

    async def list(self) -> tuple[ChatConversation, ...]:
        return tuple(sorted(self._conversations.values(), key=lambda item: item.updated_at, reverse=True))

    async def add_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        conversation = await self.get(conversation_id)
        return await self.save(conversation.model_copy(update={"messages": conversation.messages + (message,)}))

    async def add_attachment(self, conversation_id: UUID, attachment: WorkspaceAttachment) -> ChatConversation:
        conversation = await self.get(conversation_id)
        return await self.save(conversation.model_copy(update={"attachments": conversation.attachments + (attachment,)}))

    async def delete(self, conversation_id: UUID) -> None:
        self._conversations.pop(conversation_id, None)

    async def update_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        conversation = await self.get(conversation_id)
        updated_messages = tuple(item if item.id != message.id else message for item in conversation.messages)
        return await self.save(conversation.model_copy(update={"messages": updated_messages}))


class FileChatConversationRepository(InMemoryChatConversationRepository):
    """JSON-file-backed conversation persistence."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._storage_path = (storage_path or Path.cwd() / "outputs" / "chat" / "conversations.json").resolve()
        super().__init__()
        self._load()

    async def save(self, conversation: ChatConversation) -> ChatConversation:
        saved = await super().save(conversation)
        self._persist()
        return saved

    async def delete(self, conversation_id: UUID) -> None:
        await super().delete(conversation_id)
        self._persist()

    async def update_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        updated = await super().update_message(conversation_id, message)
        self._persist()
        return updated

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._conversations = {
            UUID(item["id"]): ChatConversation.model_validate(item)
            for item in payload.get("conversations", [])
        }

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"conversations": [item.model_dump(mode="json") for item in self._conversations.values()]}
        self._storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class PostgresChatConversationRepository(ChatConversationRepository):
    """PostgreSQL-backed workspace chat persistence."""

    _bucket = "chat_conversations"

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store

    async def save(self, conversation: ChatConversation) -> ChatConversation:
        updated = conversation.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        await self._store.upsert(
            bucket=self._bucket,
            document_id=updated.id,
            key=updated.updated_at.isoformat(),
            payload=updated.model_dump(mode="json"),
        )
        return updated

    async def get(self, conversation_id: UUID) -> ChatConversation:
        return ChatConversation.model_validate(
            await self._store.get(bucket=self._bucket, document_id=conversation_id)
        )

    async def list(self) -> tuple[ChatConversation, ...]:
        items = tuple(
            ChatConversation.model_validate(payload)
            for payload in await self._store.list(bucket=self._bucket)
        )
        return tuple(sorted(items, key=lambda item: item.updated_at, reverse=True))

    async def add_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        conversation = await self.get(conversation_id)
        return await self.save(conversation.model_copy(update={"messages": conversation.messages + (message,)}))

    async def add_attachment(self, conversation_id: UUID, attachment: WorkspaceAttachment) -> ChatConversation:
        conversation = await self.get(conversation_id)
        return await self.save(conversation.model_copy(update={"attachments": conversation.attachments + (attachment,)}))

    async def delete(self, conversation_id: UUID) -> None:
        await self._store.delete(bucket=self._bucket, document_id=conversation_id)

    async def update_message(self, conversation_id: UUID, message: ChatMessage) -> ChatConversation:
        conversation = await self.get(conversation_id)
        updated_messages = tuple(item if item.id != message.id else message for item in conversation.messages)
        return await self.save(conversation.model_copy(update={"messages": updated_messages}))
