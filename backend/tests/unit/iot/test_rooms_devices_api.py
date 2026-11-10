"""S1–S3: rooms and device registration/update/remove/rotate (PLAN 6.1, Phase 3 acceptance)."""

from __future__ import annotations

from tests.unit.iot.conftest import IotEnv


def test_room_create_list_and_duplicate_label(iot: IotEnv) -> None:
    c = iot.client
    resp = c.post(
        "/api/rooms",
        headers=iot.owner_a,
        json={"house_id": iot.house_a, "room_type": "bedroom", "label": "Bedroom 1"},
    )
    assert resp.status_code == 201
    dup = c.post(
        "/api/rooms",
        headers=iot.admin,
        json={"house_id": iot.house_a, "room_type": "bedroom", "label": "Bedroom 1"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"] == "duplicate_label"

    listed = c.get(f"/api/rooms?house_id={iot.house_a}", headers=iot.owner_a).json()
    assert {r["label"] for r in listed["items"]} == {"Living", "Bedroom 1"}


def test_room_scope(iot: IotEnv) -> None:
    c = iot.client
    resp = c.post(
        "/api/rooms",
        headers=iot.owner_a,
        json={"house_id": iot.house_b, "room_type": "bath", "label": "Sneaky"},
    )
    assert resp.status_code == 403
    assert c.get(f"/api/rooms?house_id={iot.house_b}", headers=iot.owner_a).status_code == 403
    mine = c.get("/api/rooms", headers=iot.owner_a).json()["items"]
    assert all(r["house_id"] == iot.house_a for r in mine)
    assert (
        c.patch(f"/api/rooms/{iot.room_b}", headers=iot.owner_a, json={"label": "x"}).status_code
        == 403
    )


def test_room_rename_conflict(iot: IotEnv) -> None:
    c = iot.client
    c.post(
        "/api/rooms",
        headers=iot.admin,
        json={"house_id": iot.house_a, "room_type": "other", "label": "Office"},
    )
    resp = c.patch(f"/api/rooms/{iot.room_a}", headers=iot.admin, json={"label": "Office"})
    assert resp.status_code == 409
    ok = c.patch(f"/api/rooms/{iot.room_a}", headers=iot.admin, json={"label": "Lounge"})
    assert ok.status_code == 200 and ok.json()["label"] == "Lounge"


def test_register_device_returns_key_once_and_starts_offline(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-1")
    assert dev["api_key"].startswith("dk_")
    assert dev["conn_state"] == "offline"
    assert dev["house_id"] == iot.house_a

    got = iot.client.get(f"/api/devices/{dev['device_id']}", headers=iot.admin).json()
    assert "api_key" not in got
    assert got["api_key_prefix"] == dev["api_key"][:10]


def test_duplicate_serial_409(iot: IotEnv) -> None:
    iot.register(iot.admin, room_id=iot.room_a, serial="SN-DUP")
    resp = iot.client.post(
        "/api/devices",
        headers=iot.admin,
        json={"room_id": iot.room_b, "device_type": "camera", "serial_no": "SN-DUP"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "duplicate_serial"


def test_owner_registers_only_in_own_house(iot: IotEnv) -> None:
    iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-OA")
    resp = iot.client.post(
        "/api/devices",
        headers=iot.owner_a,
        json={"room_id": iot.room_b, "device_type": "audio", "serial_no": "SN-X"},
    )
    assert resp.status_code == 403


def test_list_devices_scoped_and_owner_hides_admin_fields(iot: IotEnv) -> None:
    iot.register(iot.admin, room_id=iot.room_a, serial="SN-A")
    iot.register(iot.admin, room_id=iot.room_b, serial="SN-B")
    owner_list = iot.client.get("/api/devices", headers=iot.owner_a).json()
    assert [d["serial_no"] for d in owner_list["items"]] == ["SN-A"]
    assert "api_key_prefix" not in owner_list["items"][0]
    assert "threshold" not in owner_list["items"][0]

    admin_list = iot.client.get("/api/devices?connectivity=offline", headers=iot.admin).json()
    assert admin_list["total"] == 2
    assert (
        iot.client.get(f"/api/devices?house_id={iot.house_b}", headers=iot.owner_a).status_code
        == 403
    )


def test_threshold_range_and_admin_only(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-T")
    url = f"/api/devices/{dev['device_id']}"
    assert iot.client.patch(url, headers=iot.admin, json={"threshold": 0.49}).status_code == 422
    assert iot.client.patch(url, headers=iot.admin, json={"threshold": 1.0}).status_code == 422
    ok = iot.client.patch(url, headers=iot.admin, json={"threshold": 0.85})
    assert ok.status_code == 200
    assert ok.json()["threshold"] == 0.85
    assert ok.json()["config_version"] == 2
    assert iot.client.patch(url, headers=iot.owner_a, json={"threshold": 0.9}).status_code == 403
    assert iot.client.patch(url, headers=iot.owner_a, json={"label": "x"}).status_code == 403


def test_owner_status_toggle_enqueues_command_and_publishes(iot: IotEnv) -> None:
    dev = iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-S")
    iot.published.clear()
    url = f"/api/devices/{dev['device_id']}"
    resp = iot.client.patch(url, headers=iot.owner_a, json={"status": "disabled"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"
    assert iot.published and iot.published[-1]["type"] == "device.updated"
    assert iot.published[-1]["device"]["status"] == "disabled"
    # the disable command is already pending, so issuing it explicitly conflicts
    again = iot.client.post(f"{url}/command", headers=iot.owner_a, json={"command": "disable"})
    assert again.status_code == 409
    assert again.json()["error"] == "command_pending"
    # someone else's owner cannot toggle it
    assert iot.client.patch(url, headers=iot.owner_b, json={"status": "enabled"}).status_code == 403


def test_owner_cannot_reboot(iot: IotEnv) -> None:
    dev = iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-R")
    url = f"/api/devices/{dev['device_id']}/command"
    assert iot.client.post(url, headers=iot.owner_a, json={"command": "reboot"}).status_code == 403
    resp = iot.client.post(url, headers=iot.admin, json={"command": "reboot"})
    assert resp.status_code == 202
    assert resp.json()["command_id"]


def test_soft_remove_hides_device_and_revokes_key(iot: IotEnv) -> None:
    dev = iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-RM")
    url = f"/api/devices/{dev['device_id']}"
    assert iot.client.delete(url, headers=iot.owner_a).status_code == 204
    assert iot.client.get(url, headers=iot.admin).status_code == 404
    assert iot.client.get("/api/devices", headers=iot.owner_a).json()["total"] == 0
    token = iot.client.post(
        "/api/auth/device-token", json={"device_id": dev["device_id"], "api_key": dev["api_key"]}
    )
    assert token.status_code == 401
