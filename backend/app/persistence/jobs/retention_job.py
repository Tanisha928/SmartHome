"""RetentionJob — apply retention_policy to S3 lifecycle, Mongo TTL, backup_status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.persistence.mongo.client import ensure_indexes
from app.persistence.pg.models import BackupStatus
from app.persistence.repositories.retention_repo import RetentionRepository

log = get_logger(__name__)


class RetentionJob:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.retention = RetentionRepository(db)
        self.settings = get_settings()

    def run(self) -> dict[str, Any]:
        policy = self.retention.get()
        lifecycle_ok = self._apply_s3_lifecycle(
            policy.clip_expire_days, policy.clip_ia_transition_days
        )
        try:
            ensure_indexes()
            mongo_ok = True
        except Exception as exc:
            log.warning("retention_mongo_ttl_failed", error=str(exc))
            mongo_ok = False
        backups = self._record_backup_status()
        return {
            "clip_expire_days": policy.clip_expire_days,
            "clip_ia_transition_days": policy.clip_ia_transition_days,
            "telemetry_ttl_days": policy.telemetry_ttl_days,
            "lifecycle_ok": lifecycle_ok,
            "mongo_ok": mongo_ok,
            "backups": backups,
        }

    def _s3(self):  # type: ignore[no-untyped-def]
        kwargs: dict[str, Any] = {
            "region_name": self.settings.aws_region,
            "aws_access_key_id": self.settings.aws_access_key_id,
            "aws_secret_access_key": self.settings.aws_secret_access_key,
        }
        if self.settings.aws_endpoint_url:
            kwargs["endpoint_url"] = self.settings.aws_endpoint_url
        return boto3.client("s3", **kwargs)

    def _apply_s3_lifecycle(self, expire_days: int, ia_days: int | None) -> bool:
        rules: list[dict[str, Any]] = [
            {
                "ID": "clip-expire",
                "Filter": {"Prefix": "clips/"},
                "Status": "Enabled",
                "Expiration": {"Days": expire_days},
            }
        ]
        if ia_days is not None:
            rules[0]["Transitions"] = [{"Days": ia_days, "StorageClass": "STANDARD_IA"}]
        try:
            self._s3().put_bucket_lifecycle_configuration(
                Bucket=self.settings.s3_bucket,
                LifecycleConfiguration={"Rules": rules},
            )
            return True
        except (ClientError, BotoCoreError) as exc:
            log.warning("s3_lifecycle_failed", error=str(exc))
            return False

    def _record_backup_status(self) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        # Dev: mock RDS snapshot check; record weekly mongo dump location
        rows = [
            BackupStatus(
                kind="rds_snapshot",
                taken_at=now,
                status="ok" if self.settings.env == "dev" else "checked",
                location="mock://rds-snapshot",
            ),
            BackupStatus(
                kind="mongo_dump",
                taken_at=now,
                status="ok",
                location=f"s3://{self.settings.s3_bucket}/backups/mongo/{now.date().isoformat()}.archive",
            ),
        ]
        for row in rows:
            self.db.add(row)
        self.db.flush()
        return [
            {
                "kind": r.kind,
                "status": r.status,
                "location": r.location,
                "taken_at": r.taken_at.isoformat() + "Z",
            }
            for r in rows
        ]
