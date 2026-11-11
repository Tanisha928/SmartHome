"""Catalog of model labels accepted by the alert policy."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SoundRule:
    sound_type: str
    category: str
    default_severity: str
    downgrade_below: float | None = None
    downgraded_severity: str | None = None


SOUND_CATALOG: dict[str, SoundRule] = {
    "fall": SoundRule("fall", "emergency", "critical"),
    "distress": SoundRule("distress", "emergency", "critical"),
    "gunshot": SoundRule("gunshot", "emergency", "critical"),
    "explosion": SoundRule("explosion", "emergency", "critical"),
    "smoke_fire_alarm": SoundRule(
        "smoke_fire_alarm", "safety", "high", 0.90, "medium"
    ),
    "loud_argument": SoundRule("loud_argument", "safety", "high", 0.90, "medium"),
    "intruder": SoundRule("intruder", "security", "high", 0.90, "medium"),
    "glass_break": SoundRule("glass_break", "security", "high", 0.90, "medium"),
    "unusual_inactivity": SoundRule(
        "unusual_inactivity", "resident", "medium", 0.90, "low"
    ),
    "unusual_room_pattern": SoundRule(
        "unusual_room_pattern", "resident", "medium", 0.90, "low"
    ),
    "animal": SoundRule("animal", "animal", "low"),
}


def select_catalog_prediction(predictions: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-confidence prediction whose label is in the catalog."""

    accepted = [
        prediction
        for prediction in predictions
        if str(prediction.get("label", prediction.get("sound_type", ""))) in SOUND_CATALOG
    ]
    return (
        max(accepted, key=lambda prediction: float(prediction.get("confidence", 0)))
        if accepted
        else None
    )


def get_rule(sound_type: str) -> SoundRule:
    """Return a catalog rule or raise a clear error for an unknown label."""

    try:
        return SOUND_CATALOG[sound_type]
    except KeyError as exc:
        raise ValueError(f"Unknown sound type: {sound_type}") from exc
