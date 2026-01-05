import json
from typing import Dict, List, Any
from uuid import UUID

from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # user_id -> List[WebSocket]
        self.active_user_connections: Dict[UUID, List[WebSocket]] = {}
        # admin_id -> WebSocket
        self.active_admin_connections: Dict[UUID, WebSocket] = {}

    async def connect_user(self, user_id: UUID, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_user_connections:
            self.active_user_connections[user_id] = []
        self.active_user_connections[user_id].append(websocket)

    def disconnect_user(self, user_id: UUID, websocket: WebSocket):
        if user_id in self.active_user_connections:
            if websocket in self.active_user_connections[user_id]:
                self.active_user_connections[user_id].remove(websocket)
            if not self.active_user_connections[user_id]:
                del self.active_user_connections[user_id]

    async def connect_admin(self, admin_id: UUID, websocket: WebSocket):
        await websocket.accept()
        self.active_admin_connections[admin_id] = websocket

    def disconnect_admin(self, admin_id: UUID):
        if admin_id in self.active_admin_connections:
            del self.active_admin_connections[admin_id]

    async def send_personal_message(self, message: Any, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_admins(self, message: Any):
        for connection in self.active_admin_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def send_to_user(self, user_id: UUID, message: Any):
        if user_id in self.active_user_connections:
            for connection in self.active_user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()
