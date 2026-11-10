"""Upload loop (component design 2.3, S11).

Per cycle: if capture is disabled, drop unsent clips. Otherwise upload the oldest batch in
order. 200/202 → sent; `device_disabled` → discard; any other 403 → quarantine and stop;
other failures → exponential backoff (max 300 s, jittered) and end the cycle so ordering holds.
"""

from __future__ import annotations

import logging
import mimetypes
import random
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from edge_agent.config import EdgeConfig
from edge_agent.device_auth import DeviceAuth, DeviceAuthError
from edge_agent.outbox import Outbox, OutboxItem
from edge_agent.state import AgentState

log = logging.getLogger("edge.sender")


def correlation_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"c-{stamp}-{secrets.token_hex(6)}"


def backoff_seconds(attempts: int, cap: float, rng: random.Random) -> float:
    """2^attempts seconds, capped, with 20% downward jitter to avoid thundering herds."""
    base = min(cap, float(2 ** min(attempts, 16)))
    return base * rng.uniform(0.8, 1.0)


@dataclass
class CycleResult:
    sent: int = 0
    duplicates: int = 0
    discarded: int = 0
    quarantined: int = 0
    retried: int = 0
    errors: list[str] = field(default_factory=list)


class Sender:
    def __init__(
        self,
        outbox: Outbox,
        client: httpx.Client,
        auth: DeviceAuth,
        cfg: EdgeConfig,
        state: AgentState,
        *,
        clock: Callable[[], float] = time.time,
        rng: random.Random | None = None,
    ) -> None:
        self.outbox = outbox
        self.client = client
        self.auth = auth
        self.cfg = cfg
        self.state = state
        self._clock = clock
        self._rng = rng or random.Random()

    def send_cycle(self) -> CycleResult:
        result = CycleResult()
        if self.state.stopped:
            return result
        if not self.state.capture_enabled:
            result.discarded = self.outbox.discard_unsent("capture_disabled")
            return result

        for item in self.outbox.oldest_unsent(self.cfg.batch_size, ignore_backoff=True):
            if item.next_attempt_at > self._clock():
                break  # oldest clip is backing off; newer clips must not overtake it
            outcome = self._send_one(item)
            if outcome == "sent":
                result.sent += 1
            elif outcome == "duplicate":
                result.duplicates += 1
            elif outcome == "disabled":
                result.discarded += 1 + self.outbox.discard_unsent("device_disabled")
                break
            elif outcome == "discarded":
                result.discarded += 1
            elif outcome == "quarantined":
                result.quarantined += 1
            elif outcome == "stop":
                result.quarantined += 1
                self.state.stopped = True
                log.error("upload forbidden; agent stopped until credentials are fixed")
                break
            else:  # retry: keep oldest-first ordering by not sending newer clips this cycle
                result.retried += 1
                result.errors.append(outcome)
                break
        self.outbox.prune(self.cfg.buffer_cap_bytes)
        return result

    # returns: sent | duplicate | discarded | disabled | quarantined | stop | <retry error>
    def _send_one(self, item: OutboxItem) -> str:
        if self._clock() < self.state.offline_until:
            return self._retry(item, "network unavailable (simulated)")
        if not item.clip_path.exists():
            self.outbox.discard(item, "clip file missing")
            return "discarded"
        try:
            resp = self._post(item)
            if resp.status_code == 401:
                self.auth.invalidate()
                resp = self._post(item)
        except DeviceAuthError as exc:
            self.outbox.quarantine(item, str(exc))
            return "stop"
        except httpx.HTTPError as exc:
            return self._retry(item, f"{type(exc).__name__}: {exc}")

        if resp.status_code in (200, 202):
            self.outbox.mark_sent(item)
            duplicate = bool(_json(resp).get("duplicate"))
            return "duplicate" if duplicate else "sent"
        body = _json(resp)
        code = str(body.get("error") or "")
        details = body.get("details")
        detail_code = str(details.get("error") or "") if isinstance(details, dict) else ""
        if resp.status_code == 403 and "device_disabled" in (code, detail_code):
            self.outbox.discard(item, "device_disabled")
            self.state.capture_enabled = False
            return "disabled"
        if resp.status_code == 403:
            self.outbox.quarantine(item, f"403 {code or detail_code}")
            return "stop"
        if resp.status_code in (400, 404, 413, 415, 422):
            # The server will never accept this clip; keep it for inspection.
            self.outbox.quarantine(item, f"{resp.status_code} {code}")
            return "quarantined"
        return self._retry(item, f"HTTP {resp.status_code} {code}")

    def _post(self, item: OutboxItem) -> httpx.Response:
        content_type = mimetypes.guess_type(item.clip_path.name)[0] or "audio/wav"
        data = {
            "house_id": str(self.cfg.house_id),
            "device_id": str(self.cfg.device_id),
            "captured_at": item.captured_at,
        }
        if item.payload.get("duration_sec"):
            data["duration_sec"] = str(item.payload["duration_sec"])
        headers = {**self.auth.headers(), "X-Correlation-Id": correlation_id()}
        with item.clip_path.open("rb") as fh:
            return self.client.post(
                f"{self.cfg.api_base}/api/ingest/events",
                data=data,
                files={"clip": (item.clip_path.name, fh, content_type)},
                headers=headers,
            )

    def _retry(self, item: OutboxItem, error: str) -> str:
        delay = backoff_seconds(item.attempts, self.cfg.max_backoff_sec, self._rng)
        self.outbox.record_retry(item, delay, error)
        log.warning("upload failed (%s); retry in %.1fs", error, delay)
        return error


def _json(resp: httpx.Response) -> dict[str, object]:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}
