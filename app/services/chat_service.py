"""Workspace chat application service."""

from pathlib import Path
from uuid import UUID

from app.schemas import (
    ChatAttachmentResponse,
    ChatAttachmentUploadRequest,
    ChatConversationCreateRequest,
    ChatConversationListResponse,
    ChatConversationResponse,
    ChatEventListResponse,
    ChatMessageCreateRequest,
    ChatMessageResponse,
    TriggerWorkflowRequest,
)
from app.services.execution_service import ExecutionService
from core.chat import WorkspaceChatService
from core.contracts.chat import ChatAttachmentUpload, ChatMessageRequest, WorkspaceAttachmentKind


class WorkspaceChatApplicationService:
    """FastAPI adapter for workspace chat."""

    def __init__(
        self,
        execution_service: ExecutionService,
        chat_service: WorkspaceChatService | None = None,
    ) -> None:
        self._execution_service = execution_service
        self._chat = chat_service or WorkspaceChatService()

    @property
    def event_bus(self):
        return self._chat.event_bus

    async def create_conversation(self, request: ChatConversationCreateRequest) -> ChatConversationResponse:
        conversation = await self._chat.create_conversation(title=request.title, created_by=request.created_by)
        return ChatConversationResponse(conversation=conversation.model_dump(mode="json"))

    async def list_conversations(self) -> ChatConversationListResponse:
        conversations = await self._chat.list_conversations()
        return ChatConversationListResponse(conversations=tuple(item.model_dump(mode="json") for item in conversations))

    async def get_conversation(self, conversation_id: UUID) -> ChatConversationResponse:
        conversation = await self._chat.get_conversation(conversation_id)
        return ChatConversationResponse(conversation=conversation.model_dump(mode="json"))

    async def upload_attachment(
        self,
        conversation_id: UUID,
        request: ChatAttachmentUploadRequest,
    ) -> ChatAttachmentResponse:
        attachment = await self._chat.upload_attachment(
            conversation_id,
            ChatAttachmentUpload(
                kind=WorkspaceAttachmentKind(request.kind),
                name=request.name,
                content=request.content,
                uri=request.uri,
                path=Path(request.path) if request.path else None,
                content_type=request.content_type,
                metadata=request.metadata,
            ),
        )
        return ChatAttachmentResponse(attachment=attachment.model_dump(mode="json"))

    async def create_message(
        self,
        conversation_id: UUID,
        request: ChatMessageCreateRequest,
    ) -> ChatMessageResponse:
        workflow = None
        workflow_id = None
        if request.trigger_workflow:
            workflow_response = await self._execution_service.trigger_workflow(
                TriggerWorkflowRequest(
                    task=request.content,
                    thread_id=str(conversation_id),
                    metadata={
                        "source": "workspace_chat",
                        "conversation_id": str(conversation_id),
                        "attachment_ids": [str(item) for item in request.attachment_ids],
                    },
                )
            )
            workflow = workflow_response.model_dump(mode="json")
            workflow_id = workflow_response.workflow_id
            await self._chat.emit_workflow_triggered(conversation_id, workflow_response.workflow_id)
            await self._chat.emit_progress(
                conversation_id,
                {"workflow_id": str(workflow_response.workflow_id), "status": workflow_response.status.value},
            )

        message = await self._chat.add_message(
            conversation_id,
            ChatMessageRequest(
                content=request.content,
                attachment_ids=request.attachment_ids,
                trigger_workflow=request.trigger_workflow,
                metadata=request.metadata,
            ),
            workflow_id=workflow_id,
        )
        if request.trigger_workflow:
            await self._chat.add_assistant_message(
                conversation_id,
                "Workflow triggered. I will stream execution progress here as agents run.",
                workflow_id=workflow_id,
            )
        return ChatMessageResponse(message=message.model_dump(mode="json"), workflow=workflow)

    async def events(self, conversation_id: UUID) -> ChatEventListResponse:
        events = await self._chat.event_bus.history(conversation_id)
        return ChatEventListResponse(events=tuple(event.model_dump(mode="json") for event in events))
