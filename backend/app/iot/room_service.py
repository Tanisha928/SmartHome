"""RoomService — POST/GET/PATCH /api/rooms (PLAN 6.1, S1)."""

from __future__ import annotations

from typing import Any

from app.core.deps import Claims
from app.core.errors import ConflictError, ForbiddenError
from app.iot.errors import DuplicateLabelError
from app.persistence.repositories.room_repo import RoomRepository

ROOM_TYPES = ("kitchen", "living", "bedroom", "bath", "other")


def ensure_house_access(claims: Claims, house_id: int) -> None:
    """Admins may act on any house; owners only on houses in their token."""
    if claims.role == "admin":
        return
    if house_id not in claims.house_ids:
        raise ForbiddenError("House out of scope")


def serialize_room(room: Any) -> dict[str, Any]:
    return {
        "room_id": room.room_id,
        "house_id": room.house_id,
        "room_type": room.room_type,
        "label": room.label,
    }


class RoomService:
    def __init__(self, db: Any) -> None:
        self.rooms = RoomRepository(db)

    def create(
        self, claims: Claims, *, house_id: int, room_type: str, label: str
    ) -> dict[str, Any]:
        ensure_house_access(claims, house_id)
        try:
            room = self.rooms.create(house_id=house_id, room_type=room_type, label=label.strip())
        except ConflictError as exc:
            raise DuplicateLabelError("A room with this label already exists in the house") from exc
        return serialize_room(room)

    def list(self, claims: Claims, house_id: int | None) -> list[dict[str, Any]]:
        if house_id is not None:
            ensure_house_access(claims, house_id)
        return [serialize_room(r) for r in self.rooms.list(house_id, claims)]

    def update(
        self, claims: Claims, room_id: int, *, label: str | None, room_type: str | None
    ) -> dict[str, Any]:
        room = self.rooms.get(room_id, claims)  # 404/403
        if label is not None and label.strip() != room.label:
            siblings = self.rooms.list(room.house_id, claims)
            if any(r.label == label.strip() and r.room_id != room_id for r in siblings):
                raise DuplicateLabelError("A room with this label already exists in the house")
        room = self.rooms.update(
            room_id, label=label.strip() if label else None, room_type=room_type
        )
        return serialize_room(room)
