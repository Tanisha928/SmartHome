"""HouseRepository skeleton — PLAN 4.4 / houses API."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.errors import ConflictError, NotFoundError
from app.persistence.pg.models import House, UserHouse
from app.persistence.repositories.base import BaseRepository


class HouseRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, house_id: int, claims: Claims) -> House:
        raise NotImplementedError("HouseRepository.get — implement in T6 full pass")

    def list(self, claims: Claims, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        raise NotImplementedError("HouseRepository.list")

    def create(self, **fields: Any) -> House:
        raise NotImplementedError("HouseRepository.create")

    def link_user(self, user_id: int, house_id: int, relation: str = "owner") -> UserHouse:
        raise NotImplementedError("HouseRepository.link_user")

    def find_by_address(self, address_line: str, postal_code: str) -> House | None:
        stmt = select(House).where(
            House.address_line == address_line, House.postal_code == postal_code
        )
        return self.db.scalars(stmt).first()

    def require(self, house_id: int) -> House:
        house = self.db.get(House, house_id)
        if house is None:
            raise NotFoundError("House not found")
        return house

    def raise_duplicate(self) -> None:
        raise ConflictError("Duplicate house address", details={"error": "duplicate_address"})
