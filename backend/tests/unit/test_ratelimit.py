"""In-memory rate limiter enforces window and raises 429 AppError."""

from __future__ import annotations

import pytest

from app.core.errors import RateLimitError
from app.core.ratelimit import InMemoryRateLimiter


def test_rate_limiter_blocks_after_max() -> None:
    limiter = InMemoryRateLimiter(max_calls=3, window_seconds=60)
    limiter.check("a")
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(RateLimitError) as exc:
        limiter.check("a")
    assert exc.value.status_code == 429
