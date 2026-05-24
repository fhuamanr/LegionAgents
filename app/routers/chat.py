"""AI workspace chat APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

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


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> Response:
    await service.delete_conversation(conversation_id)
    return Response(status_code=204)


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


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    request: ChatMessageCreateRequest,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        service.stream_message(conversation_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}/events", response_model=ChatEventListResponse)
async def get_chat_events(
    conversation_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> ChatEventListResponse:
    return await service.events(conversation_id)


@router.get("/conversations/{conversation_id}/messages/{message_id}")
async def get_chat_message(
    conversation_id: UUID,
    message_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> dict:
    return await service.message(conversation_id, message_id)


@router.post("/conversations/{conversation_id}/messages/{message_id}/retry")
async def retry_chat_message(
    conversation_id: UUID,
    message_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> dict:
    try:
        return await service.retry_message(conversation_id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/messages/{message_id}/cancel")
async def cancel_chat_message(
    conversation_id: UUID,
    message_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> dict:
    return await service.cancel_message(conversation_id, message_id)
