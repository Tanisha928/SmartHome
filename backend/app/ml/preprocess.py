"""Minimal clip preprocessing boundary for the first worker implementation."""

from __future__ import annotations


def prepare_clip(clip: bytes, *, max_bytes: int = 25 * 1024 * 1024) -> bytes:
    if not clip:
        raise ValueError("Clip is empty")
    if len(clip) > max_bytes:
        raise ValueError("Clip is too large")
    return clip


def clip_features(clip: bytes) -> dict[str, float | int]:
    """Basic audio features for the inference log (PLAN 9): duration, RMS, peak dBFS.

    16-bit PCM WAV only (what the edge agent records); other formats report size only.
    """
    import io
    import math
    import struct
    import wave

    features: dict[str, float | int] = {"size_bytes": len(clip)}
    try:
        with wave.open(io.BytesIO(clip), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            rate, width = wav.getframerate(), wav.getsampwidth()
            features["duration_sec"] = round(wav.getnframes() / float(rate), 3) if rate else 0.0
            features["sample_rate"] = rate
    except (wave.Error, EOFError):
        return features
    if width != 2 or not frames:
        return features
    samples = struct.unpack(f"<{len(frames) // 2}h", frames[: len(frames) // 2 * 2])
    peak = max(abs(s) for s in samples) or 1
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    features["rms"] = round(rms / 32768.0, 4)
    features["peak_db"] = round(20 * math.log10(peak / 32768.0), 2)
    return features
