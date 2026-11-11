"""Role-aware alert state transitions."""

from __future__ import annotations

from typing import Any

from app.core.errors import UnprocessableError

_ADMIN_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"notified", "acknowledged", "escalated", "false_positive"}),
    "notified": frozenset({"acknowledged", "escalated", "false_positive"}),
    "acknowledged": frozenset({"escalated", "resolved", "false_positive"}),
    "escalated": frozenset({"resolved", "false_positive"}),
    "resolved": frozenset(),
    "false_positive": frozenset(),
}

_OWNER_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"escalated", "false_positive"}),
    "notified": frozenset({"escalated", "false_positive"}),
    "acknowledged": frozenset(),
    "escalated": frozenset(),
    "resolved": frozenset(),
    "false_positive": frozenset(),
}


class AlertStateService:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    @staticmethod
    def allowed_transitions(role: str, current_state: str) -> frozenset[str]:
        if role == "admin":
            return _ADMIN_TRANSITIONS.get(current_state, frozenset())
        if role in {"owner", "family", "caregiver"}:
            return _OWNER_TRANSITIONS.get(current_state, frozenset())
        return frozenset()

    def transition(
        self,
        alert_id: int,
        *,
        current_state: str,
        next_state: str,
        role: str,
        actor: int | None,
        note: str | None = None,
    ) -> Any:
        if next_state not in self.allowed_transitions(role, current_state):
            raise UnprocessableError(
                "Invalid alert state transition",
                details={"from_state": current_state, "to_state": next_state},
            )
        return self.repository.transition(alert_id, current_state, next_state, actor, note)
