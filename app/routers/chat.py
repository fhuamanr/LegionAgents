"""AI workspace chat APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_chat_service
from app.schemas import (
    ChatAttachmentResponse,
    ChatAttachmentUploadRequest,
    ChatConversationCreateRequest,
    ChatConversationListResponse,
    ChatConversationResponse,
    ChatEventListResponse,
    ChatMessageCreateRequest,
    ChatMessageResponse,
)
from app.services.chat_service import WorkspaceChatApplicationService

router = APIRouter(prefix="/workspace/chat", tags=["workspace-chat"])


@router.post("/conversations", response_model=ChatConversationResponse, status_code=201)
async def create_conversation(
    request: ChatConversationCreateRequest,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatConversationResponse:
    return await service.create_conversation(request)


@router.get("/conversations", response_model=ChatConversationListResponse)
async def list_conversations(
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatConversationListResponse:
    return await service.list_conversations()


@router.get("/conversations/{conversation_id}", response_model=ChatConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatConversationResponse:
    return await service.get_conversation(conversation_id)


@router.post("/conversations/{conversation_id}/attachments", response_model=ChatAttachmentResponse, status_code=201)
async def upload_attachment(
    conversation_id: UUID,
    request: ChatAttachmentUploadRequest,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatAttachmentResponse:
    return await service.upload_attachment(conversation_id, request)


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, status_code=201)
async def create_message(
    conversation_id: UUID,
    request: ChatMessageCreateRequest,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatMessageResponse:
    return await service.create_message(conversation_id, request)


@router.get("/conversations/{conversation_id}/events", response_model=ChatEventListResponse)
async def get_chat_events(
    conversation_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatEventListResponse:
    return await service.events(conversation_id)
