"""Authenticated, house-scoped WebSocket endpoint for alert updates."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.alerts.event_publisher import alert_hub
from app.core.deps import claims_from_payload
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token

router = APIRouter(tags=["alerts"])


def _protocol_token(websocket: WebSocket) -> str:
    values = [value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(values) != 2 or values[0] != "bearer" or not values[1]:
        raise UnauthorizedError("WebSocket bearer subprotocol required")
    return values[1]


@router.websocket("/ws/alerts")
async def alerts_socket(websocket: WebSocket, house_id: int | None = None) -> None:
    try:
        claims = claims_from_payload(decode_token(_protocol_token(websocket)))
        if claims.type != "user":
            raise ForbiddenError("User token required")
        if house_id is None:
            if claims.role == "admin":
                raise ForbiddenError("Admin WebSocket requires house_id")
            if len(claims.house_ids) != 1:
                raise ForbiddenError("House selection required")
            selected_house = claims.house_ids[0]
        else:
            selected_house = house_id
            if claims.role != "admin" and selected_house not in claims.house_ids:
                raise ForbiddenError("House out of scope")
        await websocket.accept(subprotocol="bearer")
    except Exception:
        await websocket.close(code=1008)
        return

    await alert_hub.connect(selected_house, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=25)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        alert_hub.disconnect(selected_house, websocket)
