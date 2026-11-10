"""IoT Device Manager routes: /api/rooms, /api/devices*, /api/auth/device-token,
/api/houses/{id}/disable|enable (PLAN 6.1)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from app.core.deps import Claims, get_db, require_device, require_role, require_user
from app.iot.device_auth_service import DeviceAuthService
from app.iot.device_service import DeviceService
from app.iot.heartbeat_service import HeartbeatService
from app.iot.room_service import RoomService

router = APIRouter(tags=["iot"])
admin_only = require_role("admin")

RoomType = Literal["kitchen", "living", "bedroom", "bath", "other"]
DeviceType = Literal["audio", "camera"]
DeviceStatus = Literal["enabled", "disabled"]
Connectivity = Literal["online", "offline"]
Command = Literal["enable", "disable", "reboot"]


# -- schemas ----------------------------------------------------------------------------------


class RoomCreate(BaseModel):
    house_id: int
    room_type: RoomType
    label: str = Field(min_length=1, max_length=100)


class RoomPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    room_type: RoomType | None = None


class DeviceCreate(BaseModel):
    room_id: int
    device_type: DeviceType
    serial_no: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=100)


class DevicePatch(BaseModel):
    status: DeviceStatus | None = None
    label: str | None = Field(default=None, max_length=100)
    threshold: float | None = None
    room_id: int | None = None


class CommandCreate(BaseModel):
    command: Command


class DeviceTokenRequest(BaseModel):
    device_id: int
    api_key: str = Field(min_length=1)


class HeartbeatBody(BaseModel):
    wifi_rssi: int
    uptime_sec: int = Field(ge=0)
    buffer_depth: int = Field(ge=0)
    config_version: int


class CommandAck(BaseModel):
    command_id: int
    result: str = Field(max_length=2000)


# -- rooms ------------------------------------------------------------------------------------


@router.post("/api/rooms", status_code=201)
def create_room(
    body: RoomCreate, claims: Claims = Depends(require_user), db: Any = Depends(get_db)
) -> dict[str, Any]:
    return RoomService(db).create(
        claims, house_id=body.house_id, room_type=body.room_type, label=body.label
    )


@router.get("/api/rooms")
def list_rooms(
    house_id: int | None = None,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    items = RoomService(db).list(claims, house_id)
    return {"items": items, "total": len(items)}


@router.patch("/api/rooms/{room_id}")
def patch_room(
    room_id: int,
    body: RoomPatch,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return RoomService(db).update(claims, room_id, label=body.label, room_type=body.room_type)


# -- devices ----------------------------------------------------------------------------------


@router.post("/api/devices", status_code=201)
def create_device(
    body: DeviceCreate, claims: Claims = Depends(require_user), db: Any = Depends(get_db)
) -> dict[str, Any]:
    return DeviceService(db).register(
        claims,
        room_id=body.room_id,
        device_type=body.device_type,
        serial_no=body.serial_no,
        label=body.label,
    )


@router.get("/api/devices")
def list_devices(
    house_id: int | None = None,
    room_id: int | None = None,
    status: DeviceStatus | None = None,
    connectivity: Connectivity | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    filters = {
        "house_id": house_id,
        "room_id": room_id,
        "status": status,
        "connectivity": connectivity,
    }
    return DeviceService(db).list(claims, filters, page, page_size)


@router.get("/api/devices/{device_id}")
def get_device(
    device_id: int, claims: Claims = Depends(require_user), db: Any = Depends(get_db)
) -> dict[str, Any]:
    return DeviceService(db).get(claims, device_id)


@router.patch("/api/devices/{device_id}")
def patch_device(
    device_id: int,
    body: DevicePatch,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return DeviceService(db).update(claims, device_id, body.model_dump(exclude_unset=True))


@router.delete("/api/devices/{device_id}", status_code=204)
def delete_device(
    device_id: int, claims: Claims = Depends(require_user), db: Any = Depends(get_db)
) -> Response:
    DeviceService(db).remove(claims, device_id)
    return Response(status_code=204)


@router.post("/api/devices/{device_id}/rotate-key")
def rotate_key(
    device_id: int,
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return DeviceService(db).rotate_key(claims, device_id)


@router.post("/api/devices/{device_id}/command", status_code=202)
def issue_command(
    device_id: int,
    body: CommandCreate,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return DeviceService(db).issue_command(claims, device_id, body.command)


# -- device-facing (device JWT) ---------------------------------------------------------------


@router.post("/api/auth/device-token")
def device_token(body: DeviceTokenRequest, db: Any = Depends(get_db)) -> dict[str, Any]:
    return DeviceAuthService(db).issue_token(body.device_id, body.api_key)


@router.post("/api/devices/{device_id}/heartbeat")
def heartbeat(
    device_id: int,
    body: HeartbeatBody,
    request: Request,
    claims: Claims = Depends(require_device),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return HeartbeatService(db).handle(
        claims,
        device_id,
        wifi_rssi=body.wifi_rssi,
        uptime_sec=body.uptime_sec,
        buffer_depth=body.buffer_depth,
        config_version=body.config_version,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


@router.post("/api/devices/{device_id}/command-ack")
def command_ack(
    device_id: int,
    body: CommandAck,
    claims: Claims = Depends(require_device),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return HeartbeatService(db).ack(claims, device_id, body.command_id, body.result)


# -- house cascade ----------------------------------------------------------------------------


@router.post("/api/houses/{house_id}/disable")
def disable_house(
    house_id: int,
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return DeviceService(db).set_house_status(claims, house_id, "disabled")


@router.post("/api/houses/{house_id}/enable")
def enable_house(
    house_id: int,
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return DeviceService(db).set_house_status(claims, house_id, "active")
