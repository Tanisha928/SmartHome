from __future__ import annotations

import pytest

from app.alerts.alert_state_service import AlertStateService
from app.alerts.catalog import SOUND_CATALOG, select_catalog_prediction
from app.alerts.severity_mapper import SeverityMapper
from app.alerts.threshold_resolver import ThresholdResolver
from app.core.errors import UnprocessableError


@pytest.mark.parametrize("sound_type", SOUND_CATALOG)
def test_catalog_predictions_are_accepted(sound_type: str) -> None:
    prediction = select_catalog_prediction([{"label": sound_type, "confidence": 0.8}])
    assert prediction is not None
    assert prediction["label"] == sound_type


def test_unknown_prediction_is_ignored() -> None:
    assert select_catalog_prediction([{"label": "doorbell", "confidence": 0.99}]) is None


@pytest.mark.parametrize("confidence, expected", [(0.89, "medium"), (0.90, "high")])
def test_safety_severity_boundary(confidence: float, expected: str) -> None:
    assert SeverityMapper.map("safety", "smoke_fire_alarm", confidence) == expected


def test_emergency_is_never_downgraded() -> None:
    assert SeverityMapper.map("emergency", "fall", 0.51) == "critical"


def test_threshold_precedence() -> None:
    resolver = ThresholdResolver(
        device_overrides={(3, "glass_break"): 0.91},
        house_overrides={(7, "glass_break"): 0.87},
        global_overrides={"glass_break": 0.83},
    )
    assert resolver.resolve(3, 7, "glass_break") == 0.91
    assert resolver.resolve(4, 7, "glass_break") == 0.87
    assert resolver.resolve(4, 8, "glass_break") == 0.83
    assert resolver.resolve(4, 8, "fall") == 0.80


class FakeAlertRepository:
    def transition(self, *args: object) -> tuple[object, ...]:
        return args


def test_owner_can_use_owner_actions() -> None:
    service = AlertStateService(FakeAlertRepository())
    assert service.allowed_transitions("owner", "new") == {"escalated", "false_positive"}


def test_owner_cannot_resolve_alert() -> None:
    service = AlertStateService(FakeAlertRepository())
    with pytest.raises(UnprocessableError):
        service.transition(
            1,
            current_state="acknowledged",
            next_state="resolved",
            role="owner",
            actor=2,
        )
