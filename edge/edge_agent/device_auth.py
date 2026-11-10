"""Exchange the device API key for a short-lived JWT; cache until 60 s before expiry (S11)."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from edge_agent.config import EdgeConfig

REFRESH_MARGIN_SEC = 60


class DeviceAuthError(Exception):
    """The API rejected our key (revoked, rotated, or device removed)."""


class DeviceAuth:
    def __init__(
        self, client: httpx.Client, cfg: EdgeConfig, *, clock: Callable[[], float] = time.time
    ) -> None:
        self.client = client
        self.cfg = cfg
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token is None or self._clock() >= self._expires_at - REFRESH_MARGIN_SEC:
            self._fetch()
        assert self._token is not None
        return self._token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

    def invalidate(self) -> None:
        """Call after a 401 so the next request fetches a fresh token."""
        self._token = None

    def _fetch(self) -> None:
        resp = self.client.post(
            f"{self.cfg.api_base}/api/auth/device-token",
            json={"device_id": self.cfg.device_id, "api_key": self.cfg.api_key},
        )
        if resp.status_code == 401:
            raise DeviceAuthError("device key rejected")
        resp.raise_for_status()
        body = resp.json()
        self._token = str(body["access_token"])
        self._expires_at = self._clock() + float(body.get("expires_in", 900))
