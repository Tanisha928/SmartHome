"""Simple in-memory rate limiter (no Redis) for login and device-token."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitError


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by arbitrary strings (e.g. ip:email)."""

    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_calls:
                raise RateLimitError(
                    "Too many attempts; try again later",
                    details={"retry_after_sec": int(self.window_seconds)},
                )
            q.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


# Login: 5 failures / 15 minutes per IP+email
login_limiter = InMemoryRateLimiter(max_calls=5, window_seconds=15 * 60)

# Device token: 30 / minute per device_id
device_token_limiter = InMemoryRateLimiter(max_calls=30, window_seconds=60)
