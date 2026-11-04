"""Houses API — POST/GET /api/houses with owner linking and SNS topic per house."""

from __future__ import annotations

import secrets
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.core.deps import Claims, get_db, require_role, require_user
from app.core.logging import get_logger
from app.core.security import hash_password
from app.persistence.repositories.house_repo import HouseRepository
from app.persistence.repositories.user_repo import UserRepository

router = APIRouter(tags=["houses"])
log = get_logger(__name__)


class HouseCreate(BaseModel):
    address_line: str
    city: str | None = None
    state: str | None = None
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = Field(default="America/Los_Angeles")
    owner_email: EmailStr | None = None


def _sns_client():  # type: ignore[no-untyped-def]
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sns", **kwargs)


def create_house_sns_topic(house_id: int) -> str | None:
    settings = get_settings()
    name = f"{settings.sns_topic_prefix}{house_id}"
    try:
        resp = _sns_client().create_topic(Name=name)
        return str(resp.get("TopicArn"))
    except (ClientError, BotoCoreError) as exc:
        log.warning("sns_topic_create_failed", house_id=house_id, error=str(exc))
        return None


def _serialize_house(house: Any, rooms: list[Any] | None = None, devices: list[Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "house_id": house.house_id,
        "address_line": house.address_line,
        "city": house.city,
        "state": house.state,
        "postal_code": house.postal_code,
        "latitude": float(house.latitude) if house.latitude is not None else None,
        "longitude": float(house.longitude) if house.longitude is not None else None,
        "timezone": house.timezone,
        "status": house.status,
    }
    if rooms is not None:
        payload["rooms"] = [
            {"room_id": r.room_id, "room_type": r.room_type, "label": r.label} for r in rooms
        ]
    if devices is not None:
        payload["devices"] = [
            {
                "device_id": d.device_id,
                "room_id": d.room_id,
                "label": d.label,
                "status": d.status,
                "conn_state": d.conn_state,
            }
            for d in devices
        ]
    return payload


@router.post("/api/houses", status_code=201)
def create_house(
    body: HouseCreate,
    claims: Claims = Depends(require_role("admin")),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    houses = HouseRepository(db)
    users = UserRepository(db)
    house = houses.create(**body.model_dump(exclude={"owner_email"}))

    owner_info: dict[str, Any] | None = None
    if body.owner_email:
        owner = users.get_by_email(body.owner_email)
        temp_password = None
        if owner is None:
            temp_password = secrets.token_urlsafe(12)
            owner = users.create(
                email=body.owner_email,
                password_hash=hash_password(temp_password),
                full_name=body.owner_email.split("@")[0],
                role="owner",
                must_reset=True,
            )
            log.info(
                "owner_created_with_temp_password",
                email=body.owner_email,
                temp_password=temp_password,
            )
        houses.link_user(owner.user_id, house.house_id, "owner")
        owner_info = {"user_id": owner.user_id, "email": owner.email, "must_reset": owner.must_reset}
        if temp_password and get_settings().env == "dev":
            owner_info["temp_password"] = temp_password

    topic_arn = create_house_sns_topic(house.house_id)
    return {**_serialize_house(house), "owner": owner_info, "sns_topic_arn": topic_arn}


@router.get("/api/houses")
def list_houses(
    page: int = 1,
    page_size: int = 25,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    result = HouseRepository(db).list(claims, page=page, page_size=page_size)
    return {
        "items": [_serialize_house(h) for h in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get("/api/houses/{house_id}")
def get_house(
    house_id: int,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    repo = HouseRepository(db)
    house = repo.get(house_id, claims)
    rooms, devices = repo.rooms_and_devices(house_id)
    return _serialize_house(house, rooms, devices)
