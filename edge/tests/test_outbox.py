"""S10: SQLite outbox persistence, ordering, state transitions, cap pruning."""

from __future__ import annotations

from pathlib import Path

from edge_agent.outbox import Outbox
from tests.conftest import Clock, Rig


def _clip(tmp: Path, name: str, size: int = 100) -> Path:
    path = tmp / name
    path.write_bytes(b"x" * size)
    return path


def test_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "o.sqlite"
    ob = Outbox(db)
    ob.enqueue(1, _clip(tmp_path, "a.wav"), "2026-11-10T12:00:00.000Z", {"duration_sec": 1.0})
    ob.enqueue(1, _clip(tmp_path, "b.wav"), "2026-11-10T12:00:01.000Z")
    ob.close()

    reopened = Outbox(db)
    items = reopened.oldest_unsent(10)
    assert [i.clip_path.name for i in items] == ["a.wav", "b.wav"]
    assert items[0].payload == {"duration_sec": 1.0}
    assert reopened.depth() == 2


def test_oldest_first_by_captured_at(tmp_path: Path) -> None:
    ob = Outbox(tmp_path / "o.sqlite")
    ob.enqueue(1, _clip(tmp_path, "late.wav"), "2026-11-10T12:00:05.000Z")
    ob.enqueue(1, _clip(tmp_path, "early.wav"), "2026-11-10T12:00:01.000Z")
    assert [i.clip_path.name for i in ob.oldest_unsent(10)] == ["early.wav", "late.wav"]
    assert len(ob.oldest_unsent(1)) == 1


def test_mark_sent_deletes_clip_and_leaves_queue(tmp_path: Path) -> None:
    ob = Outbox(tmp_path / "o.sqlite")
    clip = _clip(tmp_path, "a.wav")
    ob.enqueue(1, clip, "2026-11-10T12:00:00.000Z")
    ob.mark_sent(ob.oldest_unsent(1)[0])
    assert not clip.exists()
    assert ob.depth() == 0
    assert ob.counts() == {"sent": 1}


def test_record_retry_hides_item_until_due(tmp_path: Path) -> None:
    clock = Clock()
    ob = Outbox(tmp_path / "o.sqlite", clock=clock)
    ob.enqueue(1, _clip(tmp_path, "a.wav"), "2026-11-10T12:00:00.000Z")
    item = ob.oldest_unsent(1)[0]
    ob.record_retry(item, 30, "HTTP 503")
    assert ob.oldest_unsent(10) == []
    clock.advance(30)
    retried = ob.oldest_unsent(10)[0]
    assert retried.attempts == 1 and retried.last_error == "HTTP 503"


def test_discard_unsent_and_quarantine(tmp_path: Path) -> None:
    ob = Outbox(tmp_path / "o.sqlite")
    a, b, c = (_clip(tmp_path, f"{n}.wav") for n in "abc")
    ob.enqueue(1, a, "2026-11-10T12:00:00.000Z")
    ob.enqueue(1, b, "2026-11-10T12:00:01.000Z")
    ob.enqueue(1, c, "2026-11-10T12:00:02.000Z")
    ob.quarantine(ob.oldest_unsent(1)[0], "403 scope_violation")
    assert a.exists()  # quarantined clips are kept for inspection
    assert ob.discard_unsent() == 2
    assert not b.exists() and not c.exists()
    assert ob.counts() == {"quarantined": 1, "discarded": 2}


def test_prune_respects_cap_dropping_oldest(tmp_path: Path) -> None:
    ob = Outbox(tmp_path / "o.sqlite")
    for n in range(5):
        ob.enqueue(1, _clip(tmp_path, f"{n}.wav", size=1000), f"2026-11-10T12:00:0{n}.000Z")
    ob.mark_sent(ob.oldest_unsent(1)[0])
    assert ob.buffer_bytes() == 4000
    dropped = ob.prune(2500)
    assert dropped == 2
    assert [i.clip_path.name for i in ob.oldest_unsent(10)] == ["3.wav", "4.wav"]
    assert "sent" not in ob.counts()


def test_record_clip_reads_wav_duration(rig: Rig) -> None:
    rig.capture(1)
    item = rig.outbox.oldest_unsent(1)[0]
    assert item.payload["duration_sec"] == 0.1
    assert item.clip_path.parent == rig.cfg.spool_dir
    assert item.clip_path.name.startswith("glass_break-")


def test_simulator_burst_has_unique_timestamps(rig: Rig) -> None:
    from edge_agent.simulator import Simulator

    sim = Simulator(rig.outbox, rig.cfg.device_id, rig.cfg.spool_dir, rig.wav, room=None)
    sim.emit(20)
    items = rig.outbox.oldest_unsent(50)
    assert len({i.captured_at for i in items}) == 20
    assert len({i.clip_path for i in items}) == 20
    assert all(i.clip_path.exists() for i in items)
