from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.alerts.alert_state_service import AlertStateService
from app.alerts.api import _check_house_scope
from app.core.deps import Claims
from app.core.errors import ForbiddenError, UnprocessableError


def test_house_scope_rejects_cross_house_access() -> None:
    claims = Claims(sub=10, type="user", role="owner", house_ids=[1])

    _check_house_scope(claims, 1)
    with pytest.raises(ForbiddenError):
        _check_house_scope(claims, 2)


def test_admin_scope_can_select_any_house() -> None:
    _check_house_scope(Claims(sub=1, type="user", role="admin"), 99)


@pytest.mark.parametrize("role", ["owner", "family", "caregiver"])
def test_non_admin_roles_use_owner_safe_transition_rules(role: str) -> None:
    service = AlertStateService(SimpleNamespace())
    assert service.allowed_transitions(role, "new") == {"escalated", "false_positive"}
    with pytest.raises(UnprocessableError):
        service.transition(
            1,
            current_state="new",
            next_state="resolved",
            role=role,
            actor=10,
        )


def test_admin_can_resolve_acknowledged_alert() -> None:
    class Repository:
        def transition(self, *args: object) -> tuple[object, ...]:
            return args

    result = AlertStateService(Repository()).transition(
        7,
        current_state="acknowledged",
        next_state="resolved",
        role="admin",
        actor=1,
    )
    assert result[:3] == (7, "acknowledged", "resolved")
