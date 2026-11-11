"""Minimal clip preprocessing boundary for the first worker implementation."""

from __future__ import annotations


def prepare_clip(clip: bytes, *, max_bytes: int = 25 * 1024 * 1024) -> bytes:
    if not clip:
        raise ValueError("Clip is empty")
    if len(clip) > max_bytes:
        raise ValueError("Clip is too large")
    return clip
