"""Core security helpers: password hash, JWT round-trip, device key."""

from __future__ import annotations

from app.core.security import (
    create_access_token,
    create_device_token,
    decode_token,
    generate_device_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("super-secret-1")
    assert verify_password("super-secret-1", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_claims() -> None:
    token, expires_in = create_access_token(subject=42, role="admin", house_ids=[1, 2])
    assert expires_in == 30 * 60
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "user"
    assert payload["role"] == "admin"
    assert payload["house_ids"] == [1, 2]


def test_device_token_claims() -> None:
    token, expires_in = create_device_token(device_id=7, house_id=3)
    assert expires_in == 15 * 60
    payload = decode_token(token)
    assert payload["type"] == "device"
    assert payload["device_id"] == 7
    assert payload["house_id"] == 3


def test_api_key_hash() -> None:
    raw, digest, prefix = generate_device_api_key()
    assert raw.startswith("dk_")
    assert digest == hash_api_key(raw)
    assert prefix == raw[:10]
