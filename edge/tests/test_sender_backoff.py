"""S11: upload outcomes, backoff, token refresh, disable/quarantine handling."""

from __future__ import annotations

import random
import re

from edge_agent.sender import backoff_seconds, correlation_id
from tests.conftest import Rig


def test_uploads_oldest_first_and_marks_sent(rig: Rig) -> None:
    rig.capture(3)
    result = rig.sender.send_cycle()
    assert result.sent == 3
    assert rig.outbox.depth() == 0
    assert [k[1] for k in rig.api.stored] == sorted(k[1] for k in rig.api.stored)
    assert all(re.fullmatch(r"c-\d{8}-[0-9a-f]{12}", c) for c in rig.api.correlation_ids)


def test_batch_of_ten_per_cycle(rig: Rig) -> None:
    rig.capture(12)
    assert rig.sender.send_cycle().sent == 10
    assert rig.sender.send_cycle().sent == 2


def test_server_error_backs_off_and_stops_cycle(rig: Rig) -> None:
    rig.capture(3)
    rig.api.ingest_status = 503
    result = rig.sender.send_cycle()
    assert result.retried == 1 and rig.api.uploads == 1  # newer clips wait their turn
    item = rig.outbox.oldest_unsent(1, ignore_backoff=True)[0]
    assert item.attempts == 1
    assert 0 < item.next_attempt_at - rig.clock.now <= 2  # 2^0 * jitter

    # oldest still in backoff → nothing is attempted, not even newer clips
    assert rig.sender.send_cycle().retried == 0 and rig.api.uploads == 1
    rig.clock.advance(2)
    rig.api.ingest_status = None
    assert rig.sender.send_cycle().sent == 3


def test_backoff_grows_and_caps_at_300() -> None:
    rng = random.Random(0)
    delays = [backoff_seconds(n, 300, rng) for n in range(12)]
    assert delays[0] <= 1 and delays[3] > delays[1]
    assert max(delays) <= 300
    assert delays[-1] >= 240  # capped region, 20% jitter


def test_expired_token_refreshes_once(rig: Rig) -> None:
    rig.capture(1)
    rig.auth.token()  # cache tok1
    rig.api.expire_tokens = True
    assert rig.sender.send_cycle().sent == 1
    assert rig.api.token_calls == 2


def test_token_cached_until_near_expiry(rig: Rig) -> None:
    rig.capture(2)
    rig.sender.send_cycle()
    assert rig.api.token_calls == 1
    rig.clock.advance(900 - 59)
    rig.capture(1)
    rig.sender.send_cycle()
    assert rig.api.token_calls == 2


def test_device_disabled_discards_and_pauses(rig: Rig) -> None:
    rig.capture(2)
    rig.api.ingest_status = 403
    rig.api.ingest_error = "device_disabled"
    result = rig.sender.send_cycle()
    assert result.discarded == 2  # rejected clip + everything still unsent
    assert rig.api.uploads == 1
    assert rig.state.capture_enabled is False
    assert rig.outbox.depth() == 0
    # while disabled, newly captured clips are dropped without any upload
    rig.capture(1)
    assert rig.sender.send_cycle().discarded == 1
    assert rig.api.uploads == 1


def test_other_403_quarantines_and_stops(rig: Rig) -> None:
    rig.capture(3)
    rig.api.ingest_status = 403
    rig.api.ingest_error = "scope_violation"
    result = rig.sender.send_cycle()
    assert result.quarantined == 1 and rig.state.stopped
    assert rig.outbox.counts() == {"quarantined": 1, "pending": 2}
    assert rig.sender.send_cycle().sent == 0 and rig.api.uploads == 1


def test_413_quarantines_item_but_continues(rig: Rig) -> None:
    rig.capture(1)
    rig.api.ingest_status = 413
    rig.api.ingest_error = "payload_too_large"
    result = rig.sender.send_cycle()
    assert result.quarantined == 1 and not rig.state.stopped


def test_revoked_key_stops_agent(rig: Rig) -> None:
    rig.capture(1)
    rig.cfg.api_key = "dk_revoked"
    rig.sender.send_cycle()
    assert rig.state.stopped


def test_correlation_id_format() -> None:
    assert re.fullmatch(r"c-\d{8}-[0-9a-f]{12}", correlation_id())
