"""Agent loop: capture → outbox, send cycle every SEND_CYCLE_SEC, heartbeat every HEARTBEAT_SEC."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import httpx

from edge_agent.capture import Capture, FileCapture
from edge_agent.config import EdgeConfig
from edge_agent.config_sync import ConfigSync
from edge_agent.device_auth import DeviceAuth
from edge_agent.outbox import Outbox
from edge_agent.sender import CycleResult, Sender
from edge_agent.state import AgentState

log = logging.getLogger("edge.agent")

Tick = Callable[["Agent"], None]


class Agent:
    def __init__(
        self,
        cfg: EdgeConfig,
        *,
        client: httpx.Client | None = None,
        capture: Capture | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.cfg = cfg
        self._clock = clock
        self.client = client or httpx.Client(timeout=30.0)
        self.outbox = Outbox(cfg.outbox_db, clock=clock)
        self.state = AgentState(started_at=clock())
        self.auth = DeviceAuth(self.client, cfg, clock=clock)
        self.sender = Sender(self.outbox, self.client, self.auth, cfg, self.state, clock=clock)
        self.sync = ConfigSync(self.outbox, self.client, self.auth, cfg, self.state, clock=clock)
        self.capture: Capture = capture or FileCapture(
            self.outbox, cfg.device_id, cfg.clip_dir / "inbox", cfg.spool_dir
        )
        self._next_heartbeat = 0.0
        self._next_send = 0.0

    def tick(self) -> CycleResult | None:
        """One scheduler step. Safe to call in a tight loop; does work only when due."""
        now = self._clock()
        if self.state.restart_requested:
            self._restart()
        if now >= self._next_heartbeat:
            self.sync.heartbeat()
            self._next_heartbeat = now + self.cfg.heartbeat_sec
        if self.state.capture_enabled:
            self.capture.poll()
        else:
            discard = getattr(self.capture, "discard", None)
            if discard is not None:
                discard()
        if now >= self._next_send:
            self._next_send = now + self.cfg.send_cycle_sec
            result = self.sender.send_cycle()
            if result.sent or result.duplicates or result.errors:
                log.info(
                    "send cycle sent=%d dup=%d retry=%d depth=%d",
                    result.sent,
                    result.duplicates,
                    result.retried,
                    self.outbox.depth(),
                )
            return result
        return None

    def run(self, stop: threading.Event | None = None, *, on_tick: Tick | None = None) -> None:
        stop = stop or threading.Event()
        log.info("edge agent started device=%s api=%s", self.cfg.device_id, self.cfg.api_base)
        while not stop.is_set():
            try:
                self.tick()
                if on_tick:
                    on_tick(self)
            except Exception:
                log.exception("agent tick failed")
            if self.state.auth_failed:
                break  # a bad key never fixes itself; exit so the operator sees it
            stop.wait(0.5)
        self.outbox.close()

    def _restart(self) -> None:
        """`reboot` command: reset runtime state and force an immediate heartbeat/config sync."""
        log.info("restart requested; resetting agent loop")
        self.state.restart_requested = False
        self.state.started_at = self._clock()
        self.state.config_version = 0
        self.state.stopped = False
        self.auth.invalidate()
        self._next_heartbeat = 0.0
        self._next_send = 0.0
