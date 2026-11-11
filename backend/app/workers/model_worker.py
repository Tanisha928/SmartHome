"""SQS model worker: fetch a clip, classify it, and apply alert policy."""

from __future__ import annotations

import json
import logging
import signal
from collections.abc import Callable
from typing import Any

import boto3
from botocore.client import BaseClient

from app.alerts.policy_engine import PolicyEngine
from app.alerts.threshold_resolver import ThresholdResolver
from app.core.config import get_settings
from app.ml.classifier import Classifier, MockClassifier, Prediction
from app.ml.preprocess import prepare_clip
from app.persistence.pg.session import SessionLocal
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.repositories.inference_log_repo import InferenceLogRepository
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
    ) -> None:
        self.queue = queue
        self.queue_url = queue_url
        self.clip_store = clip_store
        self.classifier = classifier
        self.policy_engine = policy_engine
        self.max_clip_bytes = max_clip_bytes
        self.running = True

    def stop(self, *_args: object) -> None:
        self.running = False

    def process_message(self, message: dict[str, Any]) -> Any:
        body = json.loads(str(message["Body"]))
        clip = prepare_clip(
            self.clip_store.get_bytes(str(body["s3_key"])),
            max_bytes=self.max_clip_bytes,
        )
        predictions = self.classifier.classify(clip, filename=str(body["s3_key"]))
        result = {
            "event_id": int(body["event_id"]),
            "house_id": int(body["house_id"]),
            "device_id": int(body["device_id"]),
            "s3_key": str(body["s3_key"]),
            "correlation_id": body.get("correlation_id"),
            "predictions": [_prediction_dict(prediction) for prediction in predictions],
        }
        return self.policy_engine.handle(result)

    def run_once(self) -> int:
        response = self.queue.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=120,
        )
        messages = response.get("Messages", [])
        for message in messages:
            try:
                result = self.process_message(message)
                self.queue.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=str(message["ReceiptHandle"]),
                )
                log.info("inference_message_processed", extra={"result": result})
            except Exception:
                log.exception("inference_message_failed")
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
    engine = PolicyEngine(
        event_repository=events,
        device_repository=DeviceRepository(db),
        alert_repository=alerts,
        inference_log_repository=InferenceLogRepository(),
        threshold_resolver=ThresholdResolver(default=settings.default_threshold),
    )
    classifier: Classifier = MockClassifier()
    if settings.classifier != "mock":
        log.warning("unsupported_classifier_falling_back_to_mock", classifier=settings.classifier)
    worker = ModelWorker(
        queue=_sqs_client(),
        queue_url=settings.sqs_queue_url,
        clip_store=ClipStore(),
        classifier=classifier,
        policy_engine=engine,
        max_clip_bytes=settings.max_clip_mb * 1024 * 1024,
    )
    return worker, db


def main() -> None:
    worker, db = _build_worker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)

    def finish_cycle() -> None:
        db.commit()

    try:
        worker.run(on_cycle=finish_cycle)
    finally:
        db.close()


if __name__ == "__main__":
    main()
