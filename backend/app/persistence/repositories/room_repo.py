"""RoomRepository — full implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.persistence.pg.models import Room
from app.persistence.repositories.base import BaseRepository


class RoomRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, room_id: int, claims: Claims) -> Room:
        stmt = select(Room).where(Room.room_id == room_id)
        stmt = self.apply_scope(stmt, claims, Room.house_id, action="get_room", resource=f"room:{room_id}")
        room = self.db.scalars(stmt).first()
        if room is None:
            if self.db.get(Room, room_id) is None:
                raise NotFoundError("Room not found")
            raise ForbiddenError("Room out of scope")
        return room

    def list(self, house_id: int | None, claims: Claims) -> list[Room]:
        stmt = select(Room)
        if house_id is not None:
            stmt = stmt.where(Room.house_id == house_id)
        stmt = self.apply_scope(stmt, claims, Room.house_id, action="list_rooms", resource="rooms")
        return list(self.db.scalars(stmt.order_by(Room.room_id)).all())

    def create(self, **fields: Any) -> Room:
        existing = self.db.scalars(
            select(Room).where(Room.house_id == fields["house_id"], Room.label == fields["label"])
        ).first()
        if existing:
            raise ConflictError("Duplicate room label", details={"error": "duplicate_label"})
        room = Room(house_id=fields["house_id"], room_type=fields["room_type"], label=fields["label"])
        self.db.add(room)
        self.db.flush()
        return room

    def update(self, room_id: int, **fields: Any) -> Room:
        room = self.db.get(Room, room_id)
        if room is None:
            raise NotFoundError("Room not found")
        if "label" in fields and fields["label"] is not None:
            room.label = fields["label"]
        if "room_type" in fields and fields["room_type"] is not None:
            room.room_type = fields["room_type"]
        self.db.flush()
        return room
