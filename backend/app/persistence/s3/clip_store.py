"""ClipStore — S3 put / signed_url / get_bytes / delete with SSE-AES256."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.core.errors import DependencyUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)


def _s3_client() -> BaseClient:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **kwargs)


class ClipStore:
    """Stores audio/video clips under clips/{house_id}/{yyyy}/{mm}/{dd}/evt-{id}.ext."""

    def __init__(self, client: BaseClient | None = None) -> None:
        self._client = client or _s3_client()
        self._settings = get_settings()

    def _key(
        self,
        house_id: int,
        event_id: int,
        content_type: str,
        captured_at: datetime,
    ) -> str:
        ext = "mp4" if "mp4" in content_type or content_type.endswith("mp4") else "wav"
        return (
            f"clips/{house_id}/"
            f"{captured_at.year:04d}/{captured_at.month:02d}/{captured_at.day:02d}/"
            f"evt-{event_id}.{ext}"
        )

    def put(
        self,
        house_id: int,
        event_id: int,
        data: bytes,
        content_type: str,
        captured_at: datetime,
        source_filename: str | None = None,
    ) -> str:
        key = self._key(house_id, event_id, content_type, captured_at)
        extra: dict[str, Any] = {}
        if source_filename:
            # S3 user metadata must be ASCII; keep the device's original name for the
            # classifier (the key itself is the fixed evt-{id} format).
            extra["Metadata"] = {
                "source-filename": source_filename.encode("ascii", "replace").decode()[:200]
            }
        try:
            self._client.put_object(
                Bucket=self._settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
                **extra,
            )
        except (ClientError, BotoCoreError) as exc:
            log.error("s3_put_failed", key=key, error=str(exc))
            raise DependencyUnavailableError(
                "S3 storage unavailable",
                details={"error": "storage_unavailable"},
            ) from exc
        return key

    def signed_url(self, key: str, ttl: int | None = None) -> str:
        ttl = ttl if ttl is not None else self._settings.signed_url_ttl_sec
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._settings.s3_bucket, "Key": key},
                ExpiresIn=ttl,
            )
        except (ClientError, BotoCoreError) as exc:
            raise DependencyUnavailableError("Could not sign clip URL") from exc

    def get_clip(self, key: str) -> tuple[bytes, str | None]:
        """Clip bytes plus the device's original filename, if ingest recorded one."""
        try:
            obj = self._client.get_object(Bucket=self._settings.s3_bucket, Key=key)
            filename = (obj.get("Metadata") or {}).get("source-filename")
            return obj["Body"].read(), filename
        except (ClientError, BotoCoreError) as exc:
            raise DependencyUnavailableError("Could not fetch clip") from exc

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self._client.get_object(Bucket=self._settings.s3_bucket, Key=key)
            return obj["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            raise DependencyUnavailableError("Could not fetch clip") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._settings.s3_bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            log.warning("s3_delete_failed", key=key, error=str(exc))
