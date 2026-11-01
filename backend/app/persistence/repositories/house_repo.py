"""HouseRepository — full implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Claims
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.persistence.pg.models import Device, House, Room, UserHouse
from app.persistence.repositories.base import BaseRepository


def _page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size


class HouseRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, house_id: int, claims: Claims) -> House:
        stmt = select(House).where(House.house_id == house_id).options(
            selectinload(House.rooms),
            selectinload(House.devices),
            selectinload(House.users),
        )
        stmt = self.apply_scope(stmt, claims, House.house_id, action="get_house", resource=f"house:{house_id}")
        house = self.db.scalars(stmt).first()
        if house is None:
            # distinguish 403 vs 404 for owners
            exists = self.db.get(House, house_id)
            if exists is None:
                raise NotFoundError("House not found")
            raise ForbiddenError("House out of scope")
        return house

    def list(self, claims: Claims, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        page, page_size = _page(page, page_size)
        stmt = select(House)
        stmt = self.apply_scope(stmt, claims, House.house_id, action="list_houses", resource="houses")
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.scalars(stmt.order_by(House.house_id).offset((page - 1) * page_size).limit(page_size)).all()
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def create(self, **fields: Any) -> House:
        existing = self.find_by_address(fields.get("address_line") or "", fields.get("postal_code") or "")
        if existing is not None:
            raise ConflictError("Duplicate house address", details={"error": "duplicate_address"})
        house = House(
            address_line=fields.get("address_line"),
            city=fields.get("city"),
            state=fields.get("state"),
            postal_code=fields.get("postal_code"),
            latitude=fields.get("latitude"),
            longitude=fields.get("longitude"),
            timezone=fields["timezone"],
            status=fields.get("status", "active"),
        )
        self.db.add(house)
        self.db.flush()
        return house

    def link_user(self, user_id: int, house_id: int, relation: str = "owner") -> UserHouse:
        link = UserHouse(user_id=user_id, house_id=house_id, relation=relation)
        self.db.merge(link)
        self.db.flush()
        return link

    def find_by_address(self, address_line: str, postal_code: str) -> House | None:
        stmt = select(House).where(
            House.address_line == address_line, House.postal_code == postal_code
        )
        return self.db.scalars(stmt).first()

    def set_status(self, house_id: int, status: str) -> House:
        house = self.db.get(House, house_id)
        if house is None:
            raise NotFoundError("House not found")
        house.status = status
        self.db.flush()
        return house

    def rooms_and_devices(self, house_id: int) -> tuple[list[Room], list[Device]]:
        rooms = list(self.db.scalars(select(Room).where(Room.house_id == house_id)).all())
        devices = list(
            self.db.scalars(
                select(Device).where(Device.house_id == house_id, Device.removed_at.is_(None))
            ).all()
        )
        return rooms, devices
