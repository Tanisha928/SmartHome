"""S8: house disable/enable cascades to devices in one transaction; partial failure rolls back."""

from __future__ import annotations

from typing import Any

import pytest

from app.iot.command_queue import CommandQueue
from app.persistence.pg.models import Device, House
from tests.unit.iot.conftest import IotEnv


def _states(iot: IotEnv, house_id: int) -> tuple[str, list[str]]:
    db = iot.Session()
    try:
        house = db.get(House, house_id)
        assert house is not None
        devices = db.query(Device).filter(Device.house_id == house_id).order_by(Device.device_id)
        return house.status, [d.status for d in devices]
    finally:
        db.close()


def test_disable_and_enable_house(iot: IotEnv) -> None:
    for n in range(3):
        iot.register(iot.admin, room_id=iot.room_a, serial=f"SN-H{n}")
    other = iot.register(iot.admin, room_id=iot.room_b, serial="SN-OTHER")

    resp = iot.client.post(f"/api/houses/{iot.house_a}/disable", headers=iot.admin)
    assert resp.status_code == 200
    assert resp.json()["devices_updated"] == 3
    assert _states(iot, iot.house_a) == ("disabled", ["disabled"] * 3)
    assert _states(iot, iot.house_b)[1] == ["enabled"]

    pending = iot.client.post(
        f"/api/devices/{other['device_id']}/command", headers=iot.admin, json={"command": "disable"}
    )
    assert pending.status_code == 202  # other house untouched → no pending disable there

    resp = iot.client.post(f"/api/houses/{iot.house_a}/enable", headers=iot.admin)
    assert resp.json()["devices_updated"] == 3
    assert _states(iot, iot.house_a) == ("active", ["enabled"] * 3)


def test_owner_cannot_disable_house(iot: IotEnv) -> None:
    resp = iot.client.post(f"/api/houses/{iot.house_a}/disable", headers=iot.owner_a)
    assert resp.status_code == 403


def test_partial_failure_rolls_back(iot: IotEnv, monkeypatch: pytest.MonkeyPatch) -> None:
    for n in range(3):
        iot.register(iot.admin, room_id=iot.room_a, serial=f"SN-RB{n}")

    calls = {"n": 0}
    original = CommandQueue.issue_if_absent

    def flaky(self: CommandQueue, *args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated failure mid-cascade")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CommandQueue, "issue_if_absent", flaky)
    with pytest.raises(RuntimeError):
        iot.client.post(f"/api/houses/{iot.house_a}/disable", headers=iot.admin)
    assert _states(iot, iot.house_a) == ("active", ["enabled"] * 3)
