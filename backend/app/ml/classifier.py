"""Classifier interfaces and the configurable supplied-model adapter."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings


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
    """Adapter for a supplied model exposed as a Python ``module:callable``.

    The supplied callable receives raw clip bytes and the source filename. It may
    return ``Prediction`` objects, dictionaries containing ``label`` and
    ``confidence``, or ``(label, confidence)`` tuples. Keeping this normalization
    here lets the policy engine remain independent of the model framework.
    """

    def __init__(
        self,
        model: object,
        *,
        model_name: str = "supplied-model",
        model_version: str = "unknown",
    ) -> None:
        self.model = model
        self.model_name = model_name
        self.model_version = model_version

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ModelClassifier:
        settings = settings or get_settings()
        if not settings.model_entrypoint:
            raise RuntimeError(
                "MODEL_ENTRYPOINT is required when CLASSIFIER=model; "
                "expected module:callable"
            )
        model = cls._load_entrypoint(settings.model_entrypoint)
        return cls(
            model,
            model_name=settings.model_name,
            model_version=settings.model_version,
        )

    @staticmethod
    def _load_entrypoint(entrypoint: str) -> object:
        module_name, separator, attribute_path = entrypoint.partition(":")
        if not separator or not module_name or not attribute_path:
            raise ValueError("MODEL_ENTRYPOINT must use the module:callable format")
        value: object = import_module(module_name)
        for attribute in attribute_path.split("."):
            value = getattr(value, attribute)
        if isinstance(value, type):
            value = value()
        if not callable(value) and not callable(getattr(value, "classify", None)):
            raise TypeError(
                "MODEL_ENTRYPOINT must resolve to a callable or classify-capable object"
            )
        return value

    def classify(self, clip: bytes, *, filename: str = "") -> list[Prediction]:
        classify = getattr(self.model, "classify", None)
        raw = (
            classify(clip, filename=filename)
            if callable(classify)
            else self.model(clip, filename=filename)  # type: ignore[operator]
        )
        return self._normalize(raw)

    @staticmethod
    def _normalize(raw: Any) -> list[Prediction]:
        if isinstance(raw, dict) and "predictions" in raw:
            raw = raw["predictions"]
        elif isinstance(raw, dict):
            raw = [raw]
        elif isinstance(raw, Prediction):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            raise TypeError("Model output must be a prediction or a list of predictions")

        predictions: list[Prediction] = []
        for item in raw:
            if isinstance(item, Prediction):
                prediction = item
            elif isinstance(item, dict):
                prediction = Prediction(
                    label=str(item["label"]), confidence=float(item["confidence"])
                )
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                prediction = Prediction(label=str(item[0]), confidence=float(item[1]))
            else:
                raise TypeError("Each model prediction must contain label and confidence")
            if not 0 <= prediction.confidence <= 1:
                raise ValueError("Model confidence must be between 0 and 1")
            predictions.append(prediction)
        return predictions
