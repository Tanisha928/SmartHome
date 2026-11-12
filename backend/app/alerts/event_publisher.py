"""In-process WebSocket fan-out hub (one per API instance).

Events reach every instance through the Postgres event bus (`app.persistence.events_bus`);
each instance's listener calls `deliver()`, which pushes to the sockets connected here.
Connections are grouped by house, plus an admin group that receives every house (PLAN 8.8).
Non-admin sockets get an owner-safe copy (no confidence/threshold/model data).
"""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

ADMIN_GROUP = 0  # house ids start at 1
OWNER_HIDDEN_FIELDS = ("confidence", "threshold", "model")


def owner_safe(event: dict[str, Any]) -> dict[str, Any]:
    safe = copy.deepcopy(event)
    for key in ("alert", "device"):
        body = safe.get(key)
        if isinstance(body, dict):
            for field in OWNER_HIDDEN_FIELDS:
                body.pop(field, None)
    return safe


class AlertEventHub:
    def __init__(self) -> None:
        # group id → {socket: is_admin}
        self._connections: dict[int, dict[WebSocket, bool]] = defaultdict(dict)

    async def connect(
        self, house_id: int | None, websocket: WebSocket, *, admin: bool = False
    ) -> None:
        """`house_id=None` (admins only) subscribes to every house."""
        group = ADMIN_GROUP if house_id is None else house_id
        self._connections[group][websocket] = admin

    def disconnect(self, house_id: int | None, websocket: WebSocket) -> None:
        group = ADMIN_GROUP if house_id is None else house_id
        self._connections[group].pop(websocket, None)
        if not self._connections[group]:
            self._connections.pop(group, None)

    async def publish(self, house_id: int, event: dict[str, Any]) -> None:
        safe: dict[str, Any] | None = None
        targets = [
            (house_id, ws, is_admin) for ws, is_admin in self._connections.get(house_id, {}).items()
        ] + [
            (None, ws, is_admin) for ws, is_admin in self._connections.get(ADMIN_GROUP, {}).items()
        ]
        stale: list[tuple[int | None, WebSocket]] = []
        for group, websocket, is_admin in targets:
            if not is_admin and safe is None:
                safe = owner_safe(event)
            try:
                await websocket.send_json(event if is_admin else safe)
            except Exception:
                stale.append((group, websocket))
        for group, websocket in stale:
            self.disconnect(group, websocket)


alert_hub = AlertEventHub()


async def deliver(event: dict[str, Any]) -> None:
    """Event-bus handler: route a bus event to the sockets for its house."""
    house_id = event.get("house_id")
    if house_id is None:
        return
    await alert_hub.publish(int(house_id), event)
