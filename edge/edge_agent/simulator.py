"""Simulator: replays a WAV as if captured, on a schedule, with optional bursts/outages (S13).

The clip is named after its sound label (e.g. `glass_break-<ts>.wav`) so the backend's
MockClassifier can pick the label from the filename.
"""

from __future__ import annotations

import math
import struct
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

from edge_agent.capture import record_clip, utc_iso
from edge_agent.outbox import Outbox


class Simulator:
    def __init__(
        self, outbox: Outbox, device_id: int, spool_dir: Path, wav: Path, *, room: str | None
    ) -> None:
        if not wav.exists():
            raise FileNotFoundError(wav)
        self.outbox = outbox
        self.device_id = device_id
        self.spool_dir = spool_dir
        self.wav = wav
        self.room = room
        self.emitted = 0
        self._last: datetime | None = None

    def _next_timestamp(self) -> str:
        """Strictly increasing ms timestamps: the server dedupes on (device_id, captured_at)."""
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)  # wire format is ms
        if self._last is not None and now <= self._last:
            now = self._last + timedelta(milliseconds=1)
        self._last = now
        return utc_iso(now)

    def emit(self, count: int = 1) -> list[int]:
        """Enqueue `count` copies of the WAV with distinct capture timestamps."""
        extra = {"room": self.room} if self.room else None
        ids = []
        for _ in range(count):
            ids.append(
                record_clip(
                    self.outbox,
                    self.device_id,
                    self.wav,
                    self.spool_dir,
                    captured_at=self._next_timestamp(),
                    move=False,
                    extra=extra,
                )
            )
            self.emitted += 1
        return ids


def parse_duration(text: str) -> float:
    """'30s', '2m', '1h', or plain seconds."""
    text = text.strip().lower()
    units = {"s": 1, "m": 60, "h": 3600}
    if text and text[-1] in units:
        return float(text[:-1]) * units[text[-1]]
    return float(text)


def write_tone_wav(
    path: Path, *, freq_hz: float, seconds: float = 1.0, rate: int = 16_000, noise: bool = False
) -> Path:
    """Generate a small mono 16-bit WAV (used for the bundled samples and tests)."""
    import random

    rng = random.Random(int(freq_hz))
    frames = bytearray()
    for i in range(int(seconds * rate)):
        value = 0.4 * math.sin(2 * math.pi * freq_hz * i / rate)
        if noise:
            value = 0.5 * value + 0.5 * rng.uniform(-1, 1)
        frames += struct.pack("<h", int(value * 32767))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(bytes(frames))
    return path


SAMPLES = {
    "glass_break": {"freq_hz": 4200.0, "noise": True},
    "smoke_fire_alarm": {"freq_hz": 3100.0, "noise": False},
    "fall": {"freq_hz": 120.0, "noise": True},
    "distress": {"freq_hz": 880.0, "noise": True},
}


def make_samples(directory: Path) -> list[Path]:
    return [
        write_tone_wav(
            directory / f"{name}.wav", freq_hz=float(spec["freq_hz"]), noise=bool(spec["noise"])
        )
        for name, spec in SAMPLES.items()
    ]
