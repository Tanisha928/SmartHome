"""Durable SQLite outbox (SDD 4.1.3, PLAN 6.3, S10).

Every captured clip is recorded here before any network call, so clips survive restarts and
outages and are replayed oldest-first. The server deduplicates on (device_id, captured_at),
so re-sending an item whose response was lost is safe.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    local_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL,
    clip_path       TEXT    NOT NULL,
    captured_at     TEXT    NOT NULL,
    payload_json    TEXT    NOT NULL DEFAULT '{}',
    state           TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending', 'sent', 'discarded', 'quarantined')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    next_attempt_at REAL    NOT NULL DEFAULT 0,
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    created_at      REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_outbox_state_captured ON outbox (state, captured_at, local_id);
"""


@dataclass(frozen=True)
class OutboxItem:
    local_id: int
    device_id: int
    clip_path: Path
    captured_at: str
    payload: dict[str, Any]
    state: str
    attempts: int
    last_error: str | None
    next_attempt_at: float


class Outbox:
    def __init__(self, db_path: Path | str, *, clock: Any = time.time) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- writes ----------------------------------------------------------------------------

    def enqueue(
        self,
        device_id: int,
        clip_path: Path,
        captured_at: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        size = clip_path.stat().st_size if clip_path.exists() else 0
        cur = self._conn.execute(
            "INSERT INTO outbox (device_id, clip_path, captured_at, payload_json, size_bytes,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                device_id,
                str(clip_path),
                captured_at,
                json.dumps(payload or {}),
                size,
                self._clock(),
            ),
        )
        return int(cur.lastrowid or 0)

    def mark_sent(self, item: OutboxItem) -> None:
        self._set_state(item.local_id, "sent", None)
        _unlink(item.clip_path)

    def record_retry(self, item: OutboxItem, backoff_sec: float, error: str) -> None:
        self._conn.execute(
            "UPDATE outbox SET attempts = attempts + 1, last_error = ?, next_attempt_at = ?"
            " WHERE local_id = ?",
            (error[:500], self._clock() + backoff_sec, item.local_id),
        )

    def discard(self, item: OutboxItem, reason: str = "discarded") -> None:
        self._set_state(item.local_id, "discarded", reason)
        _unlink(item.clip_path)

    def quarantine(self, item: OutboxItem, error: str) -> None:
        """Keep the clip on disk for inspection, but never send it again."""
        self._set_state(item.local_id, "quarantined", error)

    def discard_unsent(self, reason: str = "capture_disabled") -> int:
        rows = self._conn.execute(
            "SELECT local_id, clip_path FROM outbox WHERE state = 'pending'"
        ).fetchall()
        for row in rows:
            _unlink(Path(row["clip_path"]))
        self._conn.execute(
            "UPDATE outbox SET state = 'discarded', last_error = ? WHERE state = 'pending'",
            (reason,),
        )
        return len(rows)

    def prune(self, cap_bytes: int) -> int:
        """Keep the buffer under `cap_bytes`.

        First drops bookkeeping rows for already-sent clips; if pending clips alone still exceed
        the cap, the oldest pending clips are discarded (the device would otherwise fill its disk).
        Returns the number of pending clips dropped.
        """
        self._conn.execute("DELETE FROM outbox WHERE state = 'sent'")
        dropped = 0
        while self.buffer_bytes() > cap_bytes:
            oldest = self.oldest_unsent(1, ignore_backoff=True)
            if not oldest:
                break
            self.discard(oldest[0], "buffer_cap_exceeded")
            dropped += 1
        return dropped

    def _set_state(self, local_id: int, state: str, error: str | None) -> None:
        self._conn.execute(
            "UPDATE outbox SET state = ?, last_error = ? WHERE local_id = ?",
            (state, error, local_id),
        )

    # -- reads -----------------------------------------------------------------------------

    def oldest_unsent(self, limit: int, *, ignore_backoff: bool = False) -> list[OutboxItem]:
        sql = "SELECT * FROM outbox WHERE state = 'pending'"
        args: list[Any] = []
        if not ignore_backoff:
            sql += " AND next_attempt_at <= ?"
            args.append(self._clock())
        sql += " ORDER BY captured_at, local_id LIMIT ?"
        args.append(limit)
        return [_row_to_item(r) for r in self._conn.execute(sql, args).fetchall()]

    def depth(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM outbox WHERE state = 'pending'").fetchone()
        return int(row[0])

    def buffer_bytes(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM outbox WHERE state = 'pending'"
        ).fetchone()
        return int(row[0])

    def counts(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT state, COUNT(*) FROM outbox GROUP BY state").fetchall()
        return {str(r[0]): int(r[1]) for r in rows}

    def get(self, local_id: int) -> OutboxItem | None:
        row = self._conn.execute("SELECT * FROM outbox WHERE local_id = ?", (local_id,)).fetchone()
        return _row_to_item(row) if row else None


def _row_to_item(row: sqlite3.Row) -> OutboxItem:
    return OutboxItem(
        local_id=int(row["local_id"]),
        device_id=int(row["device_id"]),
        clip_path=Path(row["clip_path"]),
        captured_at=str(row["captured_at"]),
        payload=json.loads(row["payload_json"] or "{}"),
        state=str(row["state"]),
        attempts=int(row["attempts"]),
        last_error=row["last_error"],
        next_attempt_at=float(row["next_attempt_at"]),
    )


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
