"""Pydantic Settings — all configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="dev", alias="ENV")
    database_url: str = Field(
        default="postgresql+psycopg://smart:smart@localhost:5432/smarthome",
        alias="DATABASE_URL",
    )
    mongo_url: str = Field(default="mongodb://localhost:27017", alias="MONGO_URL")
    mongo_db: str = Field(default="smarthome", alias="MONGO_DB")

    aws_region: str = Field(default="us-west-2", alias="AWS_REGION")
    aws_endpoint_url: str | None = Field(default=None, alias="AWS_ENDPOINT_URL")
    aws_access_key_id: str = Field(default="test", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="test", alias="AWS_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(default="smarthome-clips", alias="S3_BUCKET")
    sqs_queue_url: str = Field(default="", alias="SQS_QUEUE_URL")
    sqs_dlq_url: str = Field(default="", alias="SQS_DLQ_URL")
    sns_topic_prefix: str = Field(default="house-", alias="SNS_TOPIC_PREFIX")

    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")
    access_token_min: int = Field(default=30, alias="ACCESS_TOKEN_MIN")
    refresh_token_days: int = Field(default=7, alias="REFRESH_TOKEN_DAYS")
    device_token_min: int = Field(default=15, alias="DEVICE_TOKEN_MIN")

    max_clip_mb: int = Field(default=25, alias="MAX_CLIP_MB")
    signed_url_ttl_sec: int = Field(default=300, alias="SIGNED_URL_TTL_SEC")
    offline_after_min: int = Field(default=10, alias="OFFLINE_AFTER_MIN")
    cmd_expire_min: int = Field(default=60, alias="CMD_EXPIRE_MIN")
    dup_window_sec: int = Field(default=60, alias="DUP_WINDOW_SEC")
    escalate_after_min: int = Field(default=5, alias="ESCALATE_AFTER_MIN")
    default_threshold: float = Field(default=0.80, alias="DEFAULT_THRESHOLD")
    sns_retry_seconds: str = Field(default="5,15,45", alias="SNS_RETRY_SECONDS")
    classifier: str = Field(default="mock", alias="CLASSIFIER")
    internal_api_enabled: bool = Field(default=True, alias="INTERNAL_API_ENABLED")
    internal_api_key: str = Field(default="dev-internal", alias="INTERNAL_API_KEY")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    telemetry_ttl_days: int = Field(default=30, alias="TELEMETRY_TTL_DAYS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sns_retry_delays(self) -> list[int]:
        return [int(x.strip()) for x in self.sns_retry_seconds.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
