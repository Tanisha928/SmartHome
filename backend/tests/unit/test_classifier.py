from __future__ import annotations

import pytest

from app.ml.classifier import ModelClassifier, Prediction


def test_model_classifier_normalizes_dict_predictions() -> None:
    classifier = ModelClassifier(
        lambda _clip, *, filename: {"predictions": [{"label": filename, "confidence": 0.91}]}
    )

    assert classifier.classify(b"audio", filename="glass_break.wav") == [
        Prediction(label="glass_break.wav", confidence=0.91)
    ]


def test_model_classifier_supports_classify_objects() -> None:
    class SuppliedModel:
        def classify(self, _clip: bytes, *, filename: str = "") -> list[tuple[str, float]]:
            return [(filename, 0.88)]

    classifier = ModelClassifier(SuppliedModel())

    assert classifier.classify(b"audio", filename="fall.wav") == [
        Prediction(label="fall.wav", confidence=0.88)
    ]


def test_model_classifier_rejects_missing_entrypoint() -> None:
    with pytest.raises(ValueError, match="module:callable"):
        ModelClassifier._load_entrypoint("not-an-entrypoint")


def test_model_classifier_rejects_invalid_confidence() -> None:
    classifier = ModelClassifier(lambda _clip, *, filename: [(filename, 1.1)])

    with pytest.raises(ValueError, match="between 0 and 1"):
        classifier.classify(b"audio", filename="fall.wav")
