"""Mutable runtime state shared by the sender, config sync, and agent loop."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentState:
    capture_enabled: bool = True
    config_version: int = 0
    threshold: float | None = None
    restart_requested: bool = False
    stopped: bool = False  # set after a 403 quarantine: credentials/scope are wrong
    auth_failed: bool = False  # the API rejected our device key; nothing can work until it is fixed
    offline_until: float = 0.0  # simulator: pretend the network is down until this time
    started_at: float = field(default_factory=time.time)

    def uptime_sec(self, now: float | None = None) -> int:
        return max(0, int((now if now is not None else time.time()) - self.started_at))
