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
from core.chat import ChatWorkflowIntentParser, WorkspaceChatService
from core.contracts.chat import (
    ChatAttachmentUpload,
    ChatMessageRequest,
    WorkspaceAttachment,
    WorkspaceAttachmentKind,
)
from core.streaming import ExecutionEvent


class WorkspaceChatApplicationService:
    """FastAPI adapter for workspace chat."""

    def __init__(
        self,
        execution_service: ExecutionService,
        chat_service: WorkspaceChatService | None = None,
        intent_parser: ChatWorkflowIntentParser | None = None,
    ) -> None:
        self._execution_service = execution_service
        self._chat = chat_service or WorkspaceChatService()
        self._intent_parser = intent_parser or ChatWorkflowIntentParser()

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
        conversation = await self._chat.get_conversation(conversation_id)
        attachments = self._select_attachments(conversation.attachments, request.attachment_ids)
        intent = await self._intent_parser.parse(request.content, attachments)
        should_resume = request.resume_workflow or intent.resume_requested
        should_trigger = request.trigger_workflow or intent.should_trigger_workflow

        if should_resume:
            workflow_id = self._workflow_id_for_resume(request.metadata, conversation.messages)
            if workflow_id is not None:
                workflow_response = await self._execution_service.recover_workflow(
                    workflow_id,
                    metadata={"resumed_from_chat": True, "conversation_id": str(conversation_id)},
                    progress_hook=self._chat_progress_hook(conversation_id),
                )
                workflow = workflow_response.model_dump(mode="json")
                await self._chat.emit_progress(
                    conversation_id,
                    {
                        "workflow_id": str(workflow_response.workflow_id),
                        "status": workflow_response.status.value,
                        "resumed": True,
                    },
                )
        elif should_trigger:
            workflow_response = await self._execution_service.trigger_workflow(
                TriggerWorkflowRequest(
                    task=intent.normalized_task,
                    thread_id=str(conversation_id),
                    metadata={
                        "source": "workspace_chat",
                        "conversation_id": str(conversation_id),
                        "attachment_ids": [str(item) for item in request.attachment_ids],
                        "workflow_type": intent.workflow_type.value,
                        "intent": intent.model_dump(mode="json"),
                        "repository_references": list(intent.repository_references),
                        "progress_hook": self._chat_progress_hook(conversation_id),
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
                trigger_workflow=should_trigger,
                resume_workflow=should_resume,
                metadata={
                    **request.metadata,
                    "intent": intent.model_dump(mode="json"),
                    "workflow_id": str(workflow_id) if workflow_id else None,
                },
            ),
            workflow_id=workflow_id,
        )
        if should_trigger or should_resume:
            await self._chat.add_assistant_message(
                conversation_id,
                self._assistant_response(should_resume, workflow_id),
                workflow_id=workflow_id,
            )
        return ChatMessageResponse(
            message=message.model_dump(mode="json"),
            workflow=workflow,
            intent=intent.model_dump(mode="json"),
        )

    async def events(self, conversation_id: UUID) -> ChatEventListResponse:
        events = await self._chat.event_bus.history(conversation_id)
        return ChatEventListResponse(events=tuple(event.model_dump(mode="json") for event in events))

    def _select_attachments(
        self,
        attachments: tuple[WorkspaceAttachment, ...],
        attachment_ids: tuple[UUID, ...],
    ) -> tuple[WorkspaceAttachment, ...]:
        if not attachment_ids:
            return tuple()
        requested = set(attachment_ids)
        return tuple(attachment for attachment in attachments if attachment.id in requested)

    def _chat_progress_hook(self, conversation_id: UUID):
        async def publish(event: ExecutionEvent) -> None:
            await self._chat.emit_progress(
                conversation_id,
                {
                    "workflow_id": str(event.workflow_id) if event.workflow_id else None,
                    "execution_id": str(event.execution_id) if event.execution_id else None,
                    "agent_name": event.agent_name,
                    "event_type": event.type.value,
                    "message": event.message,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                },
            )

        return publish

    def _workflow_id_for_resume(self, metadata: dict, messages: tuple) -> UUID | None:
        raw_workflow_id = metadata.get("workflow_id")
        if raw_workflow_id:
            return UUID(str(raw_workflow_id))
        for message in reversed(messages):
            if message.workflow_id is not None:
                return message.workflow_id
            raw = message.metadata.get("workflow_id")
            if raw:
                return UUID(str(raw))
        return None

    def _assistant_response(self, resumed: bool, workflow_id: UUID | None) -> str:
        if resumed:
            return "Workflow resumed. Live execution updates are streaming in this conversation."
        if workflow_id is None:
            return "I parsed the instruction, but no executable workflow was started."
        return "Workflow triggered. Live execution updates are streaming in this conversation."
