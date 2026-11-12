"""Edge configuration from environment variables (or an optional KEY=VALUE file)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class EdgeConfig(BaseModel):
    api_base: str = "http://localhost:8000"
    device_id: int = 0
    api_key: str = ""
    house_id: int = 0
    outbox_db: Path = Path("outbox.sqlite")
    clip_dir: Path = Path("clips")
    heartbeat_sec: float = Field(default=60.0, gt=0)
    send_cycle_sec: float = Field(default=5.0, gt=0)
    buffer_cap_gb: float = Field(default=2.0, gt=0)
    batch_size: int = Field(default=10, ge=1)
    max_backoff_sec: float = Field(default=300.0, gt=0)  # cap on upload retry backoff
    wifi_rssi: int = -55  # reported in heartbeats until a real radio probe exists

    @property
    def buffer_cap_bytes(self) -> int:
        return int(self.buffer_cap_gb * 1024**3)

    @property
    def spool_dir(self) -> Path:
        """Where captured clips live until uploaded."""
        return self.clip_dir / "spool"

    @classmethod
    def load(cls, env_file: Path | None = None) -> EdgeConfig:
        values: dict[str, str] = {}
        if env_file is not None and env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    values[key.strip()] = val.strip()
        values.update({k: v for k, v in os.environ.items() if k in _ENV_KEYS})
        return cls.model_validate({_ENV_KEYS[k]: v for k, v in values.items() if k in _ENV_KEYS})


_ENV_KEYS = {
    "API_BASE": "api_base",
    "DEVICE_ID": "device_id",
    "API_KEY": "api_key",
    "HOUSE_ID": "house_id",
    "OUTBOX_DB": "outbox_db",
    "CLIP_DIR": "clip_dir",
    "HEARTBEAT_SEC": "heartbeat_sec",
    "SEND_CYCLE_SEC": "send_cycle_sec",
    "BUFFER_CAP_GB": "buffer_cap_gb",
    "WIFI_RSSI": "wifi_rssi",
    "MAX_BACKOFF_SEC": "max_backoff_sec",
}
