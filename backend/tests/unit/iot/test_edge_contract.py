"""Contract check: the real edge agent against the real API (in-process, S3/SQS stubbed).

Skipped unless the edge package is installed (`pip install -e ../edge`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.unit.iot.conftest import IotEnv

edge_agent = pytest.importorskip("edge_agent")

from edge_agent.agent import Agent  # noqa: E402
from edge_agent.config import EdgeConfig  # noqa: E402
from edge_agent.simulator import Simulator, write_tone_wav  # noqa: E402


class FakeClipStore:
    objects: dict[str, bytes] = {}
    names: dict[str, str | None] = {}

    def put(
        self,
        house_id: int,
        event_id: int,
        data: bytes,
        content_type: str,
        captured_at: Any,
        source_filename: str | None = None,
    ) -> str:
        key = f"clips/{house_id}/evt-{event_id}.wav"
        self.objects[key] = data
        self.names[key] = source_filename
        return key

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakePublisher:
    messages: list[dict[str, Any]] = []

    def publish_inference_event(self, **body: Any) -> str:
        self.messages.append(body)
        return f"m-{len(self.messages)}"


@pytest.fixture
def agent(
    iot: IotEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Agent, dict[str, Any]]:
    FakeClipStore.objects = {}
    FakeClipStore.names = {}
    FakePublisher.messages = []
    monkeypatch.setattr("app.persistence.ingest.service.ClipStore", FakeClipStore)
    monkeypatch.setattr("app.persistence.ingest.service.QueuePublisher", FakePublisher)
    dev = iot.register(iot.owner_a, room_id=iot.room_a, serial="SN-EDGE")
    cfg = EdgeConfig(
        api_base="",  # TestClient resolves relative URLs against http://testserver
        device_id=dev["device_id"],
        api_key=dev["api_key"],
        house_id=iot.house_a,
        outbox_db=tmp_path / "outbox.sqlite",
        clip_dir=tmp_path / "clips",
    )
    return Agent(cfg, client=iot.client), dev


def _sim(agent: Agent, tmp_path: Path) -> Simulator:
    wav = write_tone_wav(tmp_path / "glass_break.wav", freq_hz=4000.0, seconds=0.2)
    return Simulator(agent.outbox, agent.cfg.device_id, agent.cfg.spool_dir, wav, room="Living")


def test_simulated_clip_reaches_ingest_and_device_goes_online(
    iot: IotEnv, agent: tuple[Agent, dict[str, Any]], tmp_path: Path
) -> None:
    a, dev = agent
    _sim(a, tmp_path).emit(3)
    result = a.tick()
    assert result is not None and result.sent == 3, result
    assert len(FakePublisher.messages) == 3
    assert all(m["device_id"] == dev["device_id"] for m in FakePublisher.messages)
    assert a.outbox.depth() == 0

    got = iot.client.get(f"/api/devices/{dev['device_id']}", headers=iot.owner_a).json()
    assert got["conn_state"] == "online"
    assert a.state.config_version == 1


def test_resend_is_deduplicated_by_server(
    iot: IotEnv, agent: tuple[Agent, dict[str, Any]], tmp_path: Path
) -> None:
    a, _ = agent
    _sim(a, tmp_path).emit(1)
    item = a.outbox.oldest_unsent(1)[0]
    first = a.sender._post(item)
    second = a.sender._post(item)
    assert first.status_code == 202
    assert second.status_code == 200 and second.json()["duplicate"] is True
    assert len(FakeClipStore.objects) == 1


def test_owner_disable_stops_uploads_within_one_heartbeat(
    iot: IotEnv, agent: tuple[Agent, dict[str, Any]], tmp_path: Path
) -> None:
    a, dev = agent
    a.tick()  # first heartbeat
    iot.client.patch(
        f"/api/devices/{dev['device_id']}", headers=iot.owner_a, json={"status": "disabled"}
    )
    sim = _sim(a, tmp_path)
    sim.emit(2)
    a.sync.heartbeat()  # next heartbeat delivers the disable command + config
    assert a.state.capture_enabled is False
    assert a.outbox.depth() == 0
    assert a.sender.send_cycle().sent == 0
    assert FakePublisher.messages == []

    # the ack reached the API
    from app.persistence.pg.models import DeviceCommand

    db = iot.Session()
    try:
        cmds = db.query(DeviceCommand).filter(DeviceCommand.device_id == dev["device_id"]).all()
        assert [(c.command, c.status) for c in cmds] == [("disable", "completed")]
    finally:
        db.close()


def test_ingest_rejects_disabled_device_and_agent_discards(
    iot: IotEnv, agent: tuple[Agent, dict[str, Any]], tmp_path: Path
) -> None:
    a, dev = agent
    _sim(a, tmp_path).emit(2)
    # disabled server-side, but the agent has not heard yet (no heartbeat in between)
    iot.client.patch(
        f"/api/devices/{dev['device_id']}", headers=iot.admin, json={"status": "disabled"}
    )
    result = a.sender.send_cycle()
    assert result.discarded == 2 and a.state.capture_enabled is False
