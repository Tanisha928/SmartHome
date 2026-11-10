"""Capture sources. v1 ships `FileCapture`: clips dropped into an inbox directory are moved
into the spool and recorded in the outbox. Real microphone capture is future work."""

from __future__ import annotations

import shutil
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from edge_agent.outbox import Outbox

CLIP_SUFFIXES = (".wav", ".mp4")


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

    def poll(self) -> list[int]:
        ids = []
        for path in sorted(self.inbox.iterdir(), key=lambda p: p.stat().st_mtime):
            if path.is_file() and path.suffix.lower() in CLIP_SUFFIXES:
                ids.append(record_clip(self.outbox, self.device_id, path, self.spool_dir))
        return ids
