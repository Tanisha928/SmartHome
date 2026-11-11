"""Classifier interfaces used by the model worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float


class Classifier(Protocol):
    def classify(self, clip: bytes, *, filename: str = "") -> list[Prediction]: ...


class MockClassifier:
    """Deterministic classifier for local development and integration tests."""

    LABELS = {
        "glass_break": "glass_break",
        "smoke_fire_alarm": "smoke_fire_alarm",
        "distress": "distress",
        "fall": "fall",
    }

    def classify(self, clip: bytes, *, filename: str = "") -> list[Prediction]:
        del clip
        stem = Path(filename).stem.lower()
        label = next((value for key, value in self.LABELS.items() if key in stem), "animal")
        return [Prediction(label=label, confidence=0.95)]


class ModelClassifier:
    """Adapter placeholder for the real supplied model."""

    def __init__(self, model: object | None = None) -> None:
        self.model = model

    def classify(self, clip: bytes, *, filename: str = "") -> list[Prediction]:
        raise NotImplementedError("Provide the project model through ModelClassifier")
