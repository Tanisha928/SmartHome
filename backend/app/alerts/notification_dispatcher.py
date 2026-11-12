"""SNS notification delivery with bounded retries and delivery-row updates."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.core.config import get_settings
from app.persistence.notifications.sns import create_sns_client


class NotificationDispatcher:
    def __init__(
        self,
        repository: Any,
        *,
        publisher: Callable[[dict[str, Any]], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        retry_delays: tuple[int, ...] | None = None,
    ) -> None:
        self.repository = repository
        self.publisher = publisher or self._publish_sns
        self.sleep = sleep
        self.retry_delays = retry_delays or tuple(get_settings().sns_retry_delays)

    def dispatch(self, alert: Any, recipients: list[dict[str, Any]]) -> bool:
        rows = self.repository.create_pending(int(alert.alert_id), recipients)
        return self._deliver_rows(alert, rows)

    def resend_failed(self, alert: Any) -> bool:
        rows = [
            row
            for row in self.repository.list_for_alert(int(alert.alert_id))
            if row.status == "failed"
        ]
        return self._deliver_rows(alert, rows)

    def _deliver_rows(self, alert: Any, rows: list[Any]) -> bool:
        accepted = False
        for row in rows:
            attempts = 0
            delays = (0, *self.retry_delays)
            for delay in delays:
                if delay:
                    self.sleep(delay)
                attempts += 1
                try:
                    self.publisher(
                        {
                            "alert": alert,
                            "notification": row,
                            "attempt": attempts,
                        }
                    )
                    self.repository.mark_sent(int(row.notification_id))
                    accepted = True
                    break
                except Exception as exc:
                    if attempts == len(delays):
                        self.repository.mark_failed(int(row.notification_id), str(exc))
        return accepted

    def _publish_sns(self, message: dict[str, Any]) -> None:
        settings = get_settings()
        alert = message["alert"]
        row = message["notification"]
        client_kwargs: dict[str, Any] = {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url
        client = create_sns_client(client_kwargs)
        if row.channel == "sms":
            if not getattr(row, "recipient_label", None):
                raise ValueError("SMS recipient has no phone number")
            client.publish(PhoneNumber=row.recipient_label, Message=self._message(alert))
        else:
            topic = client.create_topic(Name=f"{settings.sns_topic_prefix}{int(alert.house_id)}")
            client.publish(
                TopicArn=str(topic["TopicArn"]),
                Subject=f"Smart Home {alert.severity} alert",
                Message=self._message(alert),
            )

    @staticmethod
    def _message(alert: Any) -> str:
        return f"{alert.severity.upper()} {alert.sound_type} alert for house {alert.house_id}"
