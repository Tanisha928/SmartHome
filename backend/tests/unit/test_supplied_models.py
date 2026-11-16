from __future__ import annotations

from app.ml.supplied_models import ACCIDENT_LABELS


def test_accident_model_maps_only_glass_break_to_alert_catalog() -> None:
    assert ACCIDENT_LABELS[0] == "glass_break"
    assert ACCIDENT_LABELS[1] == "animal"
    assert ACCIDENT_LABELS[2] == "animal"
