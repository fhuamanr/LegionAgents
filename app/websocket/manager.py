"""WebSocket connection manager."""

from uuid import UUID

from fastapi import WebSocket


class WebSocketConnectionManager:
    """Minimal workflow-scoped WebSocket manager."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = {}

    async def connect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(workflow_id, set()).add(websocket)

    def disconnect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(workflow_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(workflow_id, None)

    async def broadcast_json(self, workflow_id: UUID, payload: dict[str, object]) -> None:
        for websocket in tuple(self._connections.get(workflow_id, set())):
            await websocket.send_json(payload)

