"""S4–S6: device-token, heartbeat, command delivery/ack, key rotation."""

from __future__ import annotations

from tests.unit.iot.conftest import IotEnv


def test_device_token_bad_key_401(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-K")
    resp = iot.client.post(
        "/api/auth/device-token", json={"device_id": dev["device_id"], "api_key": "dk_wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_key"
    unknown = iot.client.post("/api/auth/device-token", json={"device_id": 999, "api_key": "x"})
    assert unknown.status_code == 401


def test_device_token_rate_limited(iot: IotEnv) -> None:
    for _ in range(30):
        iot.client.post("/api/auth/device-token", json={"device_id": 42, "api_key": "x"})
    resp = iot.client.post("/api/auth/device-token", json={"device_id": 42, "api_key": "x"})
    assert resp.status_code == 429


def test_rotate_key_revokes_old_key(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-ROT")
    iot.device_headers(dev["device_id"], dev["api_key"])
    assert (
        iot.client.post(
            f"/api/devices/{dev['device_id']}/rotate-key", headers=iot.owner_a
        ).status_code
        == 403
    )
    rotated = iot.client.post(f"/api/devices/{dev['device_id']}/rotate-key", headers=iot.admin)
    assert rotated.status_code == 200
    new_key = rotated.json()["api_key"]
    assert new_key != dev["api_key"]
    old = iot.client.post(
        "/api/auth/device-token", json={"device_id": dev["device_id"], "api_key": dev["api_key"]}
    )
    assert old.status_code == 401
    iot.device_headers(dev["device_id"], new_key)


def test_first_heartbeat_goes_online_returns_config_and_writes_telemetry(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-HB")
    headers = iot.device_headers(dev["device_id"], dev["api_key"])
    iot.published.clear()
    resp = iot.heartbeat(dev["device_id"], headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["commands"] == []
    assert body["config"] == {"capture_enabled": True, "threshold": None, "version": 1}
    assert iot.telemetry[-1]["device_id"] == dev["device_id"]
    assert iot.telemetry[-1]["buffer_depth"] == 0
    assert iot.published[-1]["device"]["conn_state"] == "online"

    got = iot.client.get(f"/api/devices/{dev['device_id']}", headers=iot.admin).json()
    assert got["conn_state"] == "online"
    assert got["wifi_rssi"] == -55
    assert got["last_heartbeat"].endswith("Z")

    # same version on the next beat → no config block
    again = iot.heartbeat(dev["device_id"], headers, config_version=1).json()
    assert "config" not in again


def test_heartbeat_device_mismatch_403(iot: IotEnv) -> None:
    d1 = iot.register(iot.admin, room_id=iot.room_a, serial="SN-M1")
    d2 = iot.register(iot.admin, room_id=iot.room_a, serial="SN-M2")
    headers = iot.device_headers(d1["device_id"], d1["api_key"])
    resp = iot.heartbeat(d2["device_id"], headers)
    assert resp.status_code == 403
    assert resp.json()["error"] == "device_mismatch"


def test_heartbeat_requires_device_token(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-U")
    assert iot.heartbeat(dev["device_id"], iot.admin).status_code == 403


def test_disable_delivers_command_config_and_ack(iot: IotEnv) -> None:
    dev = iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-CMD")
    headers = iot.device_headers(dev["device_id"], dev["api_key"])
    iot.heartbeat(dev["device_id"], headers)
    iot.client.patch(
        f"/api/devices/{dev['device_id']}", headers=iot.owner_a, json={"status": "disabled"}
    )
    body = iot.heartbeat(dev["device_id"], headers, config_version=1).json()
    assert [c["command"] for c in body["commands"]] == ["disable"]
    assert body["config"]["capture_enabled"] is False
    assert body["config"]["version"] == 2

    # delivered commands are not re-sent
    assert iot.heartbeat(dev["device_id"], headers, config_version=2).json()["commands"] == []

    cmd_id = body["commands"][0]["command_id"]
    ack = iot.client.post(
        f"/api/devices/{dev['device_id']}/command-ack",
        headers=headers,
        json={"command_id": cmd_id, "result": "ok"},
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "completed"

    # disabled devices still heartbeat: online/disabled
    got = iot.client.get(f"/api/devices/{dev['device_id']}", headers=iot.owner_a).json()
    assert (got["conn_state"], got["status"]) == ("online", "disabled")


def test_ack_failed_result_and_foreign_command(iot: IotEnv) -> None:
    d1 = iot.register(iot.admin, room_id=iot.room_a, serial="SN-F1")
    d2 = iot.register(iot.admin, room_id=iot.room_a, serial="SN-F2")
    cmd = iot.client.post(
        f"/api/devices/{d1['device_id']}/command", headers=iot.admin, json={"command": "reboot"}
    ).json()
    h1 = iot.device_headers(d1["device_id"], d1["api_key"])
    h2 = iot.device_headers(d2["device_id"], d2["api_key"])
    foreign = iot.client.post(
        f"/api/devices/{d2['device_id']}/command-ack",
        headers=h2,
        json={"command_id": cmd["command_id"], "result": "ok"},
    )
    assert foreign.status_code == 404
    failed = iot.client.post(
        f"/api/devices/{d1['device_id']}/command-ack",
        headers=h1,
        json={"command_id": cmd["command_id"], "result": "failed: mic busy"},
    )
    assert failed.json()["status"] == "failed"


def test_removed_device_heartbeat_rejected(iot: IotEnv) -> None:
    dev = iot.register(iot.admin, room_id=iot.room_a, serial="SN-GONE")
    headers = iot.device_headers(dev["device_id"], dev["api_key"])
    iot.client.delete(f"/api/devices/{dev['device_id']}", headers=iot.admin)
    resp = iot.heartbeat(dev["device_id"], headers)
    assert resp.status_code == 403
    assert resp.json()["error"] == "device_removed"
