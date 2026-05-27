from fastapi import WebSocket
from typing import Dict, List
import json


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, ws: WebSocket, room: str) -> None:
        await ws.accept()
        self.active.setdefault(room, []).append(ws)

    def disconnect(self, ws: WebSocket, room: str) -> None:
        if room in self.active:
            self.active[room] = [c for c in self.active[room] if c is not ws]

    async def broadcast(self, room: str, data: dict) -> None:
        dead: List[WebSocket] = []
        for ws in self.active.get(room, []):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, room)


# Singleton — import this instance everywhere
manager = ConnectionManager()
