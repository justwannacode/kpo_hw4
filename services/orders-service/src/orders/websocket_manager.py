from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import DefaultDict, Set
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: DefaultDict[UUID, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, order_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[order_id].add(websocket)

    async def disconnect(self, order_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections.get(order_id, set()):
                self._connections[order_id].remove(websocket)
            if not self._connections.get(order_id):
                self._connections.pop(order_id, None)

    async def broadcast(self, order_id: UUID, message: str) -> None:
        async with self._lock:
            conns = list(self._connections.get(order_id, set()))
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                try:
                    await ws.close()
                except Exception:
                    pass
                await self.disconnect(order_id, ws)
