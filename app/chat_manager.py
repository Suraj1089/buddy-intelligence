import json
from typing import Dict, List, Any
from uuid import UUID

from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # user_id -> WebSocket
        self.active_user_connections: Dict[UUID, WebSocket] = {}
        # admin_id -> WebSocket
        self.active_admin_connections: Dict[UUID, WebSocket] = {}

    async def connect_user(self, user_id: UUID, websocket: WebSocket):
        await websocket.accept()
        self.active_user_connections[user_id] = websocket

    def disconnect_user(self, user_id: UUID):
        if user_id in self.active_user_connections:
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
                # Handle disconnected clients gracefully if needed
                pass

    async def send_to_user(self, user_id: UUID, message: Any):
        if user_id in self.active_user_connections:
            await self.active_user_connections[user_id].send_json(message)

manager = ConnectionManager()
