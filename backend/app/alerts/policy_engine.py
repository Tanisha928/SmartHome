"""Convert classifier output into auditable alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.alerts.catalog import get_rule, select_catalog_prediction
from app.alerts.duplicate_detector import DuplicateDetector
from app.alerts.notification_dispatcher import NotificationDispatcher
from app.alerts.recipient_resolver import RecipientResolver
from app.alerts.severity_mapper import SeverityMapper
from app.alerts.threshold_resolver import ThresholdResolver


@dataclass(frozen=True)
class PolicyResult:
    event_id: int
    decision: str
    alert_id: int | None = None


class PolicyEngine:
    """Dependency-injected policy pipeline; repositories own persistence."""

    def __init__(
        self,
        *,
        event_repository: Any,
        device_repository: Any,
        alert_repository: Any,
        inference_log_repository: Any,
        threshold_resolver: ThresholdResolver,
        publisher: Callable[[str, Any], None] | None = None,
        duplicate_detector: DuplicateDetector | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
        recipient_resolver: RecipientResolver | None = None,
        recipient_provider: Callable[[Any], tuple[list[Any], list[Any]]] | None = None,
    ) -> None:
        self.events = event_repository
        self.devices = device_repository
        self.alerts = alert_repository
        self.logs = inference_log_repository
        self.thresholds = threshold_resolver
        self.publisher = publisher
        self.duplicates = duplicate_detector or DuplicateDetector(alert_repository)
        self.notifications = notification_dispatcher
        self.recipients = recipient_resolver
        self.recipient_provider = recipient_provider

    def handle(self, result: dict[str, Any]) -> PolicyResult:
        event_id = int(result["event_id"])
        event = self.events.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        if event.processing_state == "scored":
            return PolicyResult(event_id, event.decision or "already_scored")

        common_log = {
            "event_id": event_id,
            "house_id": event.house_id,
            "device_id": event.device_id,
            "s3_key": result.get("s3_key"),
            "predictions": result.get("predictions", []),
            "correlation_id": result.get(
                "correlation_id", getattr(event, "correlation_id", None)
            ),
            "policy": {},
        }

        prediction = select_catalog_prediction(result.get("predictions", []))
        if prediction is None:
            return self._finish(event, "unknown_label", common_log)

        sound_type = str(prediction.get("label", prediction.get("sound_type")))
        confidence = float(prediction.get("confidence", 0.0))
        rule = get_rule(sound_type)
        threshold = self.thresholds.resolve(event.device_id, event.house_id, sound_type)
        common_log["policy"] = {"threshold": threshold}
        if confidence < threshold:
            return self._finish(event, "below_threshold", common_log)

        device = self.devices.get_raw(event.device_id)
        if device is None:
            raise ValueError(f"Device {event.device_id} not found")
        room_id = int(device.room_id)
        duplicate = self.duplicates.find_recent(sound_type, room_id)
        if duplicate is not None:
            self.duplicates.suppress(duplicate)
            return self._finish(event, "duplicate_suppressed", common_log)

        severity = SeverityMapper.map(rule.category, sound_type, confidence)
        alert = self.alerts.create_with_history_and_mark_event_scored(
            event_id=event_id,
            house_id=event.house_id,
            room_id=room_id,
            device_id=event.device_id,
            alert_category=rule.category,
            sound_type=sound_type,
            confidence=confidence,
            severity=severity,
            decision="alert_created",
        )
        common_log["policy"] = {
            "threshold": threshold,
            "decision": "alert_created",
            "alert_id": alert.alert_id,
        }
        self.logs.write(common_log)
        if self.publisher is not None:
            self.publisher("alert.created", alert)
        if (
            self.notifications is not None
            and self.recipients is not None
            and self.recipient_provider is not None
        ):
            users, preferences = self.recipient_provider(alert)
            recipients = self.recipients.resolve(alert, users, preferences)
            if self.notifications.dispatch(alert, recipients):
                alert = self.alerts.transition(
                    int(alert.alert_id), "new", "notified", None, "notifications accepted"
                )
                if self.publisher is not None:
                    self.publisher("alert.updated", alert)
        return PolicyResult(event_id, "alert_created", int(alert.alert_id))

    def _finish(self, event: Any, decision: str, log_doc: dict[str, Any]) -> PolicyResult:
        self.events.mark_scored(int(event.event_id), decision)
        log_doc = dict(log_doc)
        log_doc["policy"] = {**log_doc.get("policy", {}), "decision": decision}
        self.logs.write(log_doc)
        return PolicyResult(int(event.event_id), decision)
