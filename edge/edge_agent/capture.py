"""Capture sources. v1 ships `FileCapture`: clips dropped into an inbox directory are moved
into the spool and recorded in the outbox. Real microphone capture is future work."""

from __future__ import annotations

import logging
import shutil
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from edge_agent.outbox import Outbox

CLIP_SUFFIXES = (".wav", ".mp4")
log = logging.getLogger("edge.capture")


class Capture(Protocol):
    def poll(self) -> list[int]: ...


def utc_iso(now: datetime | None = None) -> str:
    """Millisecond ISO-8601 UTC with Z. Sorts lexically in capture order."""
    value = now or datetime.now(UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def wav_duration(path: Path) -> float | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wf:
            return round(wf.getnframes() / float(wf.getframerate()), 3)
    except (wave.Error, EOFError, OSError):
        return None


def record_clip(
    outbox: Outbox,
    device_id: int,
    source: Path,
    spool_dir: Path,
    *,
    captured_at: str | None = None,
    move: bool = True,
    extra: dict[str, str] | None = None,
) -> int:
    """Place a clip in the spool and enqueue it. Returns the outbox local_id."""
    spool_dir.mkdir(parents=True, exist_ok=True)
    ts = captured_at or utc_iso()
    safe_ts = ts.replace(":", "").replace("-", "").replace(".", "")
    dest = spool_dir / f"{source.stem}-{safe_ts}{source.suffix.lower()}"
    if move:
        shutil.move(str(source), dest)
    else:
        shutil.copyfile(source, dest)
    payload: dict[str, object] = {"source": source.name, **(extra or {})}
    duration = wav_duration(dest)
    if duration:
        payload["duration_sec"] = duration
    return outbox.enqueue(device_id, dest, ts, payload)


class FileCapture:
    """Watch `inbox` for new clip files and enqueue them."""

    def __init__(self, outbox: Outbox, device_id: int, inbox: Path, spool_dir: Path) -> None:
        self.outbox = outbox
        self.device_id = device_id
        self.inbox = inbox
        self.spool_dir = spool_dir
        self.inbox.mkdir(parents=True, exist_ok=True)
        self._last: datetime | None = None

    def _pending(self) -> list[Path]:
        files = [
            p for p in self.inbox.iterdir() if p.is_file() and p.suffix.lower() in CLIP_SUFFIXES
        ]
        return sorted(files, key=lambda p: (p.stat().st_mtime, p.name))

    def _next_timestamp(self) -> str:
        """Strictly increasing ms timestamps: clips found in one poll must not collide
        (the server dedupes on (device_id, captured_at))."""
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        if self._last is not None and now <= self._last:
            now = self._last + timedelta(milliseconds=1)
        self._last = now
        return utc_iso(now)

    def poll(self) -> list[int]:
        ids = []
        for path in self._pending():
            ids.append(
                record_clip(
                    self.outbox,
                    self.device_id,
                    path,
                    self.spool_dir,
                    captured_at=self._next_timestamp(),
                )
            )
            log.info("captured %s", path.name)
        return ids

    def discard(self) -> int:
        """Capture is disabled: drop anything that arrived instead of queueing it for later."""
        dropped = 0
        for path in self._pending():
            path.unlink(missing_ok=True)
            dropped += 1
        if dropped:
            log.info("capture disabled; dropped %d new clip(s)", dropped)
        return dropped
