"""SQS model worker: fetch a clip, classify it, and apply alert policy."""

from __future__ import annotations

import json
import logging
import signal
import time
from collections.abc import Callable
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from app.alerts.events import bus_publisher
from app.alerts.live_thresholds import LiveThresholdResolver
from app.alerts.notification_dispatcher import NotificationDispatcher
from app.alerts.policy_engine import PolicyEngine
from app.alerts.recipient_resolver import RecipientResolver
from app.core.config import get_settings
from app.ml.classifier import Classifier, MockClassifier, ModelClassifier, Prediction
from app.ml.preprocess import clip_features, prepare_clip
from app.persistence.pg.session import SessionLocal
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.repositories.inference_log_repo import InferenceLogRepository
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.repositories.prefs_repo import PrefsRepository
from app.persistence.repositories.user_repo import UserRepository
from app.persistence.s3.clip_store import ClipStore

log = logging.getLogger("model_worker")


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


def _prediction_dict(prediction: Prediction) -> dict[str, Any]:
    return {"label": prediction.label, "confidence": prediction.confidence}


class ModelWorker:
    """Testable worker core; successful messages are deleted exactly once."""

    def __init__(
        self,
        *,
        queue: BaseClient,
        queue_url: str,
        clip_store: ClipStore,
        classifier: Classifier,
        policy_engine: PolicyEngine,
        max_clip_bytes: int = 25 * 1024 * 1024,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.queue = queue
        self.queue_url = queue_url
        self.clip_store = clip_store
        self.classifier = classifier
        self.policy_engine = policy_engine
        self.max_clip_bytes = max_clip_bytes
        self.commit = commit or (lambda: None)
        self.rollback = rollback or (lambda: None)
        self.sleep = sleep
        self.running = True
        self._receive_failures = 0

    def stop(self, *_args: object) -> None:
        self.running = False

    def process_message(self, message: dict[str, Any]) -> Any:
        body = json.loads(str(message["Body"]))
        key = str(body["s3_key"])
        source_name: str | None = None
        get_clip = getattr(self.clip_store, "get_clip", None)
        if get_clip is not None:
            raw, source_name = get_clip(key)
        else:
            raw = self.clip_store.get_bytes(key)
        clip = prepare_clip(raw, max_bytes=self.max_clip_bytes)
        # Ingest stores clips as evt-{id}; the device's original name (kept as S3 metadata)
        # is what carries the label for the mock classifier.
        started = time.perf_counter()
        predictions = self.classifier.classify(clip, filename=source_name or key)
        runtime_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {
            "event_id": int(body["event_id"]),
            "house_id": int(body["house_id"]),
            "device_id": int(body["device_id"]),
            "s3_key": str(body["s3_key"]),
            "correlation_id": body.get("correlation_id"),
            "predictions": [_prediction_dict(prediction) for prediction in predictions],
            # FR-19: every inference log records the model version and clip features.
            "model": {
                "name": getattr(self.classifier, "model_name", type(self.classifier).__name__),
                "version": getattr(self.classifier, "model_version", "unknown"),
                "runtime_ms": runtime_ms,
            },
            "features": clip_features(clip),
        }
        return self.policy_engine.handle(result)

    def run_once(self) -> int:
        try:
            response = self.queue.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=120,
            )
            self._receive_failures = 0
        except (ClientError, BotoCoreError) as exc:
            # Queue missing/unreachable (e.g. LocalStack still starting): back off, don't die.
            self._receive_failures += 1
            delay = min(30.0, 2.0 ** min(self._receive_failures, 5))
            log.warning("sqs_receive_failed", extra={"error": str(exc), "retry_in": delay})
            self.sleep(delay)
            return 0
        messages = response.get("Messages", [])
        for message in messages:
            try:
                result = self.process_message(message)
                # Persist first; delete only once the alert/event state is durable. If the
                # commit fails the message stays on the queue and is retried (then DLQ).
                self.commit()
            except Exception:
                self.rollback()
                log.exception("inference_message_failed")
                continue
            try:
                self.queue.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=str(message["ReceiptHandle"]),
                )
            except (ClientError, BotoCoreError):
                # Redelivery is safe: PolicyEngine returns the stored decision for scored events.
                log.exception("sqs_delete_failed")
            log.info("inference_message_processed", extra={"result": result})
        return len(messages)

    def run(self, *, on_cycle: Callable[[], None] | None = None) -> None:
        while self.running:
            self.run_once()
            if on_cycle is not None:
                on_cycle()


def _build_worker() -> tuple[ModelWorker, Any]:
    settings = get_settings()
    db = SessionLocal()
    events = EventRepository(db)
    alerts = AlertRepository(db)
    users = UserRepository(db)
    prefs = PrefsRepository(db)

    def recipient_provider(alert: Any) -> tuple[list[Any], list[Any]]:
        house_users = users.list_for_house(int(alert.house_id))
        house_prefs = [
            pref
            for user in house_users
            for pref in prefs.get_for_user_house(int(user.user_id), int(alert.house_id))
        ]
        return house_users, house_prefs

    engine = PolicyEngine(
        event_repository=events,
        device_repository=DeviceRepository(db),
        alert_repository=alerts,
        inference_log_repository=InferenceLogRepository(),
        threshold_resolver=LiveThresholdResolver(db, default=settings.default_threshold),
        notification_dispatcher=NotificationDispatcher(NotificationRepository(db)),
        publisher=bus_publisher(db),
        recipient_resolver=RecipientResolver(),
        recipient_provider=recipient_provider,
    )
    if settings.classifier == "mock":
        classifier: Classifier = MockClassifier()
    elif settings.classifier == "model":
        classifier = ModelClassifier.from_settings(settings)
        log.info(
            "supplied_model_loaded",
            extra={
                "model_name": classifier.model_name,
                "model_version": classifier.model_version,
            },
        )
    else:
        raise ValueError(f"Unsupported CLASSIFIER value: {settings.classifier}")
    worker = ModelWorker(
        queue=_sqs_client(),
        queue_url=settings.sqs_queue_url,
        clip_store=ClipStore(),
        classifier=classifier,
        policy_engine=engine,
        max_clip_bytes=settings.max_clip_mb * 1024 * 1024,
        commit=db.commit,
        rollback=db.rollback,
    )
    return worker, db


def main() -> None:
    worker, db = _build_worker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)

    try:
        worker.run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
