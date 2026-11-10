"""Fake Smart Home API (httpx.MockTransport) + a controllable clock for edge tests."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

from edge_agent.config import EdgeConfig
from edge_agent.config_sync import ConfigSync
from edge_agent.device_auth import DeviceAuth
from edge_agent.outbox import Outbox
from edge_agent.sender import Sender
from edge_agent.simulator import write_tone_wav
from edge_agent.state import AgentState


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class FakeApi:
    """Mimics the ingest dedupe contract: (device_id, captured_at) is unique."""

    down: bool = False
    lose_responses: int = 0  # store the clip, then drop the connection N times
    ingest_status: int | None = None  # force a status code
    ingest_error: str = ""
    stored: list[tuple[int, str]] = field(default_factory=list)
    uploads: int = 0
    token_calls: int = 0
    expire_tokens: bool = False
    pending_commands: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] | None = None
    acks: list[dict[str, Any]] = field(default_factory=list)
    heartbeats: list[dict[str, Any]] = field(default_factory=list)
    correlation_ids: list[str] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/api/auth/device-token":
            self.token_calls += 1
            body = json.loads(request.content)
            if body["api_key"] != "dk_good":
                return httpx.Response(401, json={"error": "invalid_key", "message": "bad"})
            return httpx.Response(
                200, json={"access_token": f"tok{self.token_calls}", "expires_in": 900}
            )
        if self.expire_tokens and request.headers.get("Authorization") == "Bearer tok1":
            return httpx.Response(401, json={"error": "unauthorized", "message": "expired"})
        if path == "/api/ingest/events":
            return self._ingest(request)
        if path.endswith("/heartbeat"):
            self.heartbeats.append(json.loads(request.content))
            body: dict[str, Any] = {"commands": self.pending_commands}
            self.pending_commands = []
            if self.config is not None:
                body["config"] = self.config
            return httpx.Response(200, json=body)
        if path.endswith("/command-ack"):
            self.acks.append(json.loads(request.content))
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(404, json={"error": "not_found", "message": path})

    def _ingest(self, request: httpx.Request) -> httpx.Response:
        self.uploads += 1
        self.correlation_ids.append(request.headers.get("X-Correlation-Id", ""))
        if self.ingest_status is not None:
            return httpx.Response(
                self.ingest_status, json={"error": self.ingest_error, "message": "forced"}
            )
        text = request.content.decode("latin-1")
        captured_at = text.split('name="captured_at"\r\n\r\n', 1)[1].split("\r\n", 1)[0]
        device_id = int(text.split('name="device_id"\r\n\r\n', 1)[1].split("\r\n", 1)[0])
        key = (device_id, captured_at)
        duplicate = key in self.stored
        if not duplicate:
            self.stored.append(key)
        if self.lose_responses > 0:
            self.lose_responses -= 1
            raise httpx.ReadError("connection reset after upload", request=request)
        return httpx.Response(
            200 if duplicate else 202, json={"event_id": len(self.stored), "duplicate": duplicate}
        )


@dataclass
class Rig:
    api: FakeApi
    clock: Clock
    cfg: EdgeConfig
    outbox: Outbox
    state: AgentState
    auth: DeviceAuth
    sender: Sender
    sync: ConfigSync
    tmp: Path
    wav: Path
    seq: int = 0

    def capture(self, n: int = 1) -> list[int]:
        from edge_agent.capture import record_clip

        ids = []
        for _ in range(n):
            self.seq += 1
            stamp = f"2026-11-10T12:{self.seq // 60:02d}:{self.seq % 60:02d}.000Z"
            ids.append(
                record_clip(
                    self.outbox,
                    self.cfg.device_id,
                    self.wav,
                    self.cfg.spool_dir,
                    captured_at=stamp,
                    move=False,
                )
            )
        return ids


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    api = FakeApi()
    clock = Clock()
    cfg = EdgeConfig(
        api_base="http://api.test",
        device_id=7,
        api_key="dk_good",
        house_id=3,
        outbox_db=tmp_path / "outbox.sqlite",
        clip_dir=tmp_path / "clips",
    )
    client = httpx.Client(transport=httpx.MockTransport(api.handler))
    outbox = Outbox(cfg.outbox_db, clock=clock)
    state = AgentState(started_at=clock())
    auth = DeviceAuth(client, cfg, clock=clock)
    sender = Sender(outbox, client, auth, cfg, state, clock=clock, rng=random.Random(1))
    sync = ConfigSync(outbox, client, auth, cfg, state, clock=clock)
    wav = write_tone_wav(tmp_path / "glass_break.wav", freq_hz=440.0, seconds=0.1)
    return Rig(api, clock, cfg, outbox, state, auth, sender, sync, tmp_path, wav)
