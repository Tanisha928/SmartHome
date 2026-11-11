"""In-process alert event fan-out hub for the MVP deployment."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class AlertEventHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, house_id: int, websocket: WebSocket) -> None:
        self._connections[house_id].add(websocket)

    def disconnect(self, house_id: int, websocket: WebSocket) -> None:
        self._connections[house_id].discard(websocket)
        if not self._connections[house_id]:
            self._connections.pop(house_id, None)

    async def publish(self, house_id: int, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in self._connections.get(house_id, set()):
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(house_id, websocket)


alert_hub = AlertEventHub()
