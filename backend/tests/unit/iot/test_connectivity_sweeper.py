"""S7: offline after 10 minutes; S6: command expiry after 60 minutes (freezegun).

Only the sweeper runs under frozen time; FastAPI request handling does not cope with
freezegun's FakeDatetime, so HTTP calls happen at real time and we freeze relative to them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from app.iot.connectivity_sweeper import ConnectivitySweeper
from app.persistence.pg.models import Device, DeviceCommand
from tests.unit.iot.conftest import IotEnv


def _online_device(iot: IotEnv, serial: str) -> int:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial=serial)
    headers = iot.device_headers(dev["device_id"], dev["api_key"])
    assert iot.heartbeat(dev["device_id"], headers).status_code == 200
    return int(dev["device_id"])


def _sweep_at(iot: IotEnv, when: datetime) -> int:
    db = iot.Session()
    try:
        with freeze_time(when):
            return ConnectivitySweeper(db).run()
    finally:
        db.close()


def _conn_state(iot: IotEnv, device_id: int) -> str:
    db = iot.Session()
    try:
        device = db.get(Device, device_id)
        assert device is not None
        return device.conn_state
    finally:
        db.close()


def test_stays_online_within_10_minutes(iot: IotEnv) -> None:
    before = datetime.now(UTC)
    device_id = _online_device(iot, "SN-ON")
    assert _sweep_at(iot, before + timedelta(minutes=9, seconds=59)) == 0
    assert _conn_state(iot, device_id) == "online"


def test_goes_offline_after_10_minutes_and_publishes(iot: IotEnv) -> None:
    device_id = _online_device(iot, "SN-OFF")
    after = datetime.now(UTC)
    iot.published.clear()
    assert _sweep_at(iot, after + timedelta(minutes=10, seconds=1)) == 1
    assert _conn_state(iot, device_id) == "offline"
    assert iot.published[-1]["device"]["device_id"] == device_id
    assert iot.published[-1]["device"]["conn_state"] == "offline"
    assert _sweep_at(iot, after + timedelta(minutes=11)) == 0  # idempotent


def test_next_heartbeat_brings_device_back_online(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-BACK")
    headers = iot.device_headers(dev["device_id"], dev["api_key"])
    iot.heartbeat(dev["device_id"], headers)
    _sweep_at(iot, datetime.now(UTC) + timedelta(minutes=11))
    assert _conn_state(iot, dev["device_id"]) == "offline"
    iot.heartbeat(dev["device_id"], headers, config_version=1)
    assert _conn_state(iot, dev["device_id"]) == "online"


def test_disabled_device_not_swept(iot: IotEnv) -> None:
    device_id = _online_device(iot, "SN-DIS")
    iot.client.patch(f"/api/devices/{device_id}", headers=iot.admin, json={"status": "disabled"})
    assert _sweep_at(iot, datetime.now(UTC) + timedelta(minutes=30)) == 0


def test_pending_commands_expire_after_60_minutes(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-EXP")
    url = f"/api/devices/{dev['device_id']}/command"
    cmd_id = iot.client.post(url, headers=iot.admin, json={"command": "reboot"}).json()[
        "command_id"
    ]
    assert iot.client.post(url, headers=iot.admin, json={"command": "reboot"}).status_code == 409

    _sweep_at(iot, datetime.now(UTC) + timedelta(minutes=59))
    db = iot.Session()
    try:
        cmd = db.get(DeviceCommand, cmd_id)
        assert cmd is not None and cmd.status == "pending"
    finally:
        db.close()

    _sweep_at(iot, datetime.now(UTC) + timedelta(minutes=61))
    db = iot.Session()
    try:
        cmd = db.get(DeviceCommand, cmd_id)
        assert cmd is not None and cmd.status == "expired"
    finally:
        db.close()
    # once expired, a new reboot can be queued
    assert iot.client.post(url, headers=iot.admin, json={"command": "reboot"}).status_code == 202
