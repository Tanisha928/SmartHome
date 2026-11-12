"""Cross-process event bus over PostgreSQL LISTEN/NOTIFY (PLAN 8.8).

The API, model workers and sweepers are separate processes (and in production, separate
instances). Any of them publishes `alert.*` / `device.*` events here; every API instance runs
`listen()` and fans events out to its own WebSocket clients.

`publish()` issues NOTIFY on the caller's session, so the event is delivered only when that
transaction commits — "publish after commit" for free, and nothing is sent on rollback.
On non-PostgreSQL sessions (SQLite unit tests) events go to an optional in-process handler.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import psycopg
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

CHANNEL = "app_events"
MAX_PAYLOAD_BYTES = 7900  # PostgreSQL NOTIFY payload limit is 8000 bytes

LocalHandler = Callable[[dict[str, Any]], None]
_local_handler: LocalHandler | None = None


def set_local_handler(handler: LocalHandler | None) -> None:
    """Receive events published on non-PostgreSQL sessions (tests, single-process tools)."""
    global _local_handler
    _local_handler = handler


def publish(db: Session, event: dict[str, Any]) -> None:
    """Queue `event` for delivery when `db`'s transaction commits. Never raises."""
    try:
        payload = json.dumps(event, default=str, separators=(",", ":"))
        if len(payload.encode()) > MAX_PAYLOAD_BYTES:
            log.warning("event_too_large_dropped", type=event.get("type"), size=len(payload))
            return
        if db.get_bind().dialect.name == "postgresql":
            db.execute(select(func.pg_notify(CHANNEL, payload)))
        elif _local_handler is not None:
            _local_handler(json.loads(payload))
    except Exception as exc:
        log.warning("event_publish_failed", type=event.get("type"), error=str(exc))


def _dsn() -> str:
    url = get_settings().database_url
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def is_postgres() -> bool:
    return get_settings().database_url.startswith("postgresql")


async def listen(handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
    """Forward every event on CHANNEL to `handler` until cancelled; reconnects with backoff."""
    backoff = 1.0
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(_dsn(), autocommit=True) as conn:
                await conn.execute(f"LISTEN {CHANNEL}")
                log.info("event_bus_listening", channel=CHANNEL)
                backoff = 1.0
                async for notify in conn.notifies():
                    try:
                        await handler(json.loads(notify.payload))
                    except Exception as exc:
                        log.warning("event_handler_failed", error=str(exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("event_bus_disconnected", error=str(exc), retry_in=backoff)
            await asyncio.sleep(backoff)
            backoff = min(30.0, backoff * 2)
