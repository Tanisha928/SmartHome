"""ClipStore key layout and put/delete with a fake S3 client."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.errors import DependencyUnavailableError
from app.persistence.s3.clip_store import ClipStore


class FakeS3:
    def __init__(self, *, fail_put: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_put = fail_put
        self.last_put_kwargs: dict[str, Any] | None = None

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        if self.fail_put:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "503", "Message": "down"}}, "PutObject")
        self.last_put_kwargs = kwargs
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def generate_presigned_url(self, _op: str, Params: dict[str, str], ExpiresIn: int) -> str:
        return f"https://example.test/{Params['Key']}?ttl={ExpiresIn}"

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        class Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": Body(self.objects[Key])}

    def delete_object(self, Bucket: str, Key: str) -> dict[str, str]:
        self.objects.pop(Key, None)
        return {}


def test_put_key_layout_and_sse() -> None:
    fake = FakeS3()
    store = ClipStore(client=fake)  # type: ignore[arg-type]
    captured = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    key = store.put(3, 99, b"RIFF....", "audio/wav", captured)
    assert key == "clips/3/2026/10/25/evt-99.wav"
    assert fake.last_put_kwargs is not None
    assert fake.last_put_kwargs["ServerSideEncryption"] == "AES256"


def test_put_failure_raises_503() -> None:
    store = ClipStore(client=FakeS3(fail_put=True))  # type: ignore[arg-type]
    with pytest.raises(DependencyUnavailableError) as exc:
        store.put(1, 1, b"x", "audio/wav", datetime.now(UTC))
    assert exc.value.status_code == 503


def test_signed_url_and_roundtrip() -> None:
    fake = FakeS3()
    store = ClipStore(client=fake)  # type: ignore[arg-type]
    key = store.put(1, 2, b"data", "audio/wav", datetime(2026, 1, 2, tzinfo=UTC))
    assert store.get_bytes(key) == b"data"
    assert "evt-2.wav" in store.signed_url(key)
    store.delete(key)
    assert key not in fake.objects
