from __future__ import annotations

from types import SimpleNamespace

from app.alerts.api import _serialize_alert


def test_owner_alert_payload_hides_confidence() -> None:
    alert = SimpleNamespace(
        alert_id=1,
        event_id=2,
        house_id=3,
        room_id=4,
        device_id=5,
        alert_category="security",
        sound_type="glass_break",
        confidence=0.97,
        severity="high",
        state="new",
        suppressed_count=0,
        version=1,
        created_at=None,
        updated_at=None,
    )
    payload = _serialize_alert(alert, owner_view=True)
    assert "confidence" not in payload


def test_admin_alert_payload_includes_confidence() -> None:
    alert = SimpleNamespace(
        alert_id=1,
        event_id=2,
        house_id=3,
        room_id=4,
        device_id=5,
        alert_category="security",
        sound_type="glass_break",
        confidence=0.97,
        severity="high",
        state="new",
        suppressed_count=0,
        version=1,
        created_at=None,
        updated_at=None,
    )
    assert _serialize_alert(alert, owner_view=False)["confidence"] == 0.97
