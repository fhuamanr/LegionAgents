"""WebSocket routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.dependencies.container import get_execution_service
from app.dependencies.container import get_chat_service
from app.services.execution_service import ExecutionService
from app.services.chat_service import WorkspaceChatApplicationService
from app.websocket.manager import WebSocketConnectionManager

router = APIRouter(tags=["websocket"])
manager = WebSocketConnectionManager()


@router.websocket("/ws/executions/{workflow_id}")
async def stream_execution(
    websocket: WebSocket,
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> None:
    await manager.connect(workflow_id, websocket)
    try:
        async for event in service.event_bus.subscribe(workflow_id=workflow_id):
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        manager.disconnect(workflow_id, websocket)


@router.websocket("/ws/chat/{conversation_id}")
async def stream_chat(
    websocket: WebSocket,
    conversation_id: UUID,
    service: WorkspaceChatApplicationService = Depends(get_chat_service),
) -> None:
    await websocket.accept()
    try:
        async for event in service.event_bus.subscribe(conversation_id=conversation_id):
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
