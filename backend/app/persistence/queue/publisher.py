"""QueuePublisher — publish inference-event messages to SQS."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _sqs_client() -> BaseClient:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sqs", **kwargs)


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.astimezone().isoformat().replace("+00:00", "Z")


class QueuePublisher:
    """Publishes SQS messages with the exact SDD 4.2.2 body shape."""

    def __init__(self, client: BaseClient | None = None) -> None:
        self._client = client or _sqs_client()
        self._settings = get_settings()

    def publish_inference_event(
        self,
        *,
        event_id: int,
        house_id: int,
        device_id: int,
        s3_key: str,
        captured_at: datetime,
        correlation_id: str,
    ) -> str | None:
        """Return MessageId on success, None on failure (caller keeps event queued)."""
        body = {
            "event_id": event_id,
            "house_id": house_id,
            "device_id": device_id,
            "s3_key": s3_key,
            "captured_at": _iso_z(captured_at),
            "correlation_id": correlation_id,
        }
        try:
            resp = self._client.send_message(
                QueueUrl=self._settings.sqs_queue_url,
                MessageBody=json.dumps(body),
                MessageAttributes={
                    "correlation_id": {
                        "DataType": "String",
                        "StringValue": correlation_id,
                    }
                },
            )
            return str(resp.get("MessageId"))
        except (ClientError, BotoCoreError) as exc:
            log.error("sqs_publish_failed", event_id=event_id, error=str(exc))
            return None

    def get_queue_attributes(self, queue_url: str) -> dict[str, str]:
        try:
            resp = self._client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                ],
            )
            return dict(resp.get("Attributes", {}))
        except (ClientError, BotoCoreError):
            return {}
