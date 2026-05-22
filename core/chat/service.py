"""AI workspace chat service."""

from pathlib import Path
from uuid import UUID

from core.chat.events import ChatEventBus
from core.chat.repository import ChatConversationRepository, FileChatConversationRepository
from core.contracts.chat import (
    ChatAttachmentUpload,
    ChatConversation,
    ChatEvent,
    ChatEventType,
    ChatMessage,
    ChatMessageRequest,
    ChatRole,
    WorkspaceAttachment,
    WorkspaceAttachmentKind,
)


class WorkspaceChatService:
    """Coordinates conversations, uploads, references, streaming events, and workflow triggering."""

    def __init__(
        self,
        repository: ChatConversationRepository | None = None,
        event_bus: ChatEventBus | None = None,
    ) -> None:
        self.repository = repository or FileChatConversationRepository()
        self.event_bus = event_bus or ChatEventBus()

    async def create_conversation(
        self,
        title: str,
        created_by: str = "workspace-user",
    ) -> ChatConversation:
        """Create a conversation."""

        conversation = await self.repository.save(ChatConversation(title=title, created_by=created_by))
        await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation.id,
                type=ChatEventType.MESSAGE_CREATED,
                message="Conversation created.",
                payload={"title": title},
            )
        )
        return conversation

    async def list_conversations(self) -> tuple[ChatConversation, ...]:
        """List conversations."""

        return await self.repository.list()

    async def get_conversation(self, conversation_id: UUID) -> ChatConversation:
        """Get one conversation."""

        return await self.repository.get(conversation_id)

    async def upload_attachment(
        self,
        conversation_id: UUID,
        upload: ChatAttachmentUpload,
    ) -> WorkspaceAttachment:
        """Persist an uploaded input or external reference."""

        content = upload.content
        if upload.path and upload.kind in {WorkspaceAttachmentKind.TEXT, WorkspaceAttachmentKind.MARKDOWN}:
            content = Path(upload.path).read_text(encoding="utf-8")
        attachment = WorkspaceAttachment(
            kind=upload.kind,
            name=upload.name,
            content=content,
            uri=upload.uri,
            path=upload.path,
            content_type=upload.content_type,
            size_bytes=len((content or upload.uri or str(upload.path or "")).encode("utf-8")),
            metadata=upload.metadata,
        )
        await self.repository.add_attachment(conversation_id, attachment)
        await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation_id,
                type=ChatEventType.ATTACHMENT_UPLOADED,
                message=f"Attachment uploaded: {attachment.name}",
                payload=attachment.model_dump(mode="json"),
            )
        )
        return attachment

    async def add_message(
        self,
        conversation_id: UUID,
        request: ChatMessageRequest,
        workflow_id: UUID | None = None,
    ) -> ChatMessage:
        """Add a user chat message."""

        message = ChatMessage(
            conversation_id=conversation_id,
            role=ChatRole.USER,
            content=request.content,
            attachment_ids=request.attachment_ids,
            workflow_id=workflow_id,
            metadata={**request.metadata, "trigger_workflow": request.trigger_workflow},
        )
        await self.repository.add_message(conversation_id, message)
        await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation_id,
                type=ChatEventType.MESSAGE_CREATED,
                message="User message created.",
                payload=message.model_dump(mode="json"),
            )
        )
        return message

    async def add_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        workflow_id: UUID | None = None,
    ) -> ChatMessage:
        """Add an assistant chat message."""

        message = ChatMessage(
            conversation_id=conversation_id,
            role=ChatRole.ASSISTANT,
            content=content,
            workflow_id=workflow_id,
        )
        await self.repository.add_message(conversation_id, message)
        await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation_id,
                type=ChatEventType.MESSAGE_CREATED,
                message="Assistant message created.",
                payload=message.model_dump(mode="json"),
            )
        )
        return message

    async def emit_workflow_triggered(self, conversation_id: UUID, workflow_id: UUID) -> ChatEvent:
        """Emit workflow trigger event."""

        return await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation_id,
                type=ChatEventType.WORKFLOW_TRIGGERED,
                message="Workflow triggered from workspace chat.",
                payload={"workflow_id": str(workflow_id)},
            )
        )

    async def emit_progress(self, conversation_id: UUID, payload: dict) -> ChatEvent:
        """Emit execution progress event."""

        return await self.event_bus.publish(
            ChatEvent(
                conversation_id=conversation_id,
                type=ChatEventType.EXECUTION_PROGRESS,
                message="Workflow execution progress updated.",
                payload=payload,
            )
        )
