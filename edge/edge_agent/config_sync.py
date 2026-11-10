"""Heartbeat + apply server config and commands (S12)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from edge_agent.config import EdgeConfig
from edge_agent.device_auth import DeviceAuth
from edge_agent.outbox import Outbox
from edge_agent.state import AgentState

log = logging.getLogger("edge.config_sync")


class ConfigSync:
    def __init__(
        self,
        outbox: Outbox,
        client: httpx.Client,
        auth: DeviceAuth,
        cfg: EdgeConfig,
        state: AgentState,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.outbox = outbox
        self.client = client
        self.auth = auth
        self.cfg = cfg
        self.state = state
        self._clock = clock

    def heartbeat(self) -> dict[str, Any] | None:
        """Send one heartbeat and apply its response. Returns the response, or None on failure."""
        if self._clock() < self.state.offline_until:
            return None
        body = {
            "wifi_rssi": self.cfg.wifi_rssi,
            "uptime_sec": self.state.uptime_sec(self._clock()),
            "buffer_depth": self.outbox.depth(),
            "config_version": self.state.config_version,
        }
        url = f"{self.cfg.api_base}/api/devices/{self.cfg.device_id}/heartbeat"
        try:
            resp = self.client.post(url, json=body, headers=self.auth.headers())
            if resp.status_code == 401:
                self.auth.invalidate()
                resp = self.client.post(url, json=body, headers=self.auth.headers())
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("heartbeat failed: %s", exc)
            return None
        data: dict[str, Any] = resp.json()
        self.apply(data)
        return data

    def apply(self, data: dict[str, Any]) -> None:
        config = data.get("config")
        if config:
            self.state.config_version = int(config.get("version", self.state.config_version))
            self.state.threshold = config.get("threshold")
            self._set_capture(bool(config.get("capture_enabled", True)))
        for cmd in data.get("commands", []):
            result = self._run_command(str(cmd["command"]))
            self._ack(int(cmd["command_id"]), result)

    def _run_command(self, command: str) -> str:
        if command == "enable":
            self._set_capture(True)
        elif command == "disable":
            self._set_capture(False)
        elif command == "reboot":
            self.state.restart_requested = True
        else:
            return f"failed: unknown command {command}"
        return "ok"

    def _set_capture(self, enabled: bool) -> None:
        if self.state.capture_enabled and not enabled:
            dropped = self.outbox.discard_unsent("capture_disabled")
            log.info("capture disabled; discarded %d unsent clips", dropped)
        self.state.capture_enabled = enabled

    def _ack(self, command_id: int, result: str) -> None:
        try:
            self.client.post(
                f"{self.cfg.api_base}/api/devices/{self.cfg.device_id}/command-ack",
                json={"command_id": command_id, "result": result},
                headers=self.auth.headers(),
            )
        except httpx.HTTPError as exc:
            log.warning("command ack failed for %s: %s", command_id, exc)
