"""S14: outage buffering, oldest-first replay, exactly-once delivery, restart persistence."""

from __future__ import annotations

import random

import httpx

from edge_agent.device_auth import DeviceAuth
from edge_agent.outbox import Outbox
from edge_agent.sender import Sender
from edge_agent.state import AgentState
from tests.conftest import Rig


def _drain(rig: Rig, sender: Sender | None = None, max_cycles: int = 200) -> None:
    sender = sender or rig.sender
    for _ in range(max_cycles):
        if rig.outbox.depth() == 0:
            return
        sender.send_cycle()
        rig.clock.advance(301)  # past any backoff
    raise AssertionError("outbox never drained")


def test_outage_then_replay_exactly_once_in_order(rig: Rig) -> None:
    rig.api.down = True
    rig.capture(5)
    for _ in range(4):  # ~2 minutes of failed cycles
        rig.sender.send_cycle()
        rig.clock.advance(30)
    assert rig.outbox.depth() == 5 and rig.api.stored == []

    rig.api.down = False
    _drain(rig)
    captured = [k[1] for k in rig.api.stored]
    assert len(captured) == 5 and len(set(captured)) == 5
    assert captured == sorted(captured)


def test_lost_response_is_resent_and_deduplicated(rig: Rig) -> None:
    rig.capture(3)
    rig.api.lose_responses = 2  # server stored the clip, client never heard back
    _drain(rig)
    assert len(rig.api.stored) == 3  # no duplicates on the server
    assert rig.api.uploads == 5  # two re-sends answered with duplicate:true
    assert rig.outbox.depth() == 0 and "quarantined" not in rig.outbox.counts()


def test_restart_mid_outage_replays_after_reboot(rig: Rig) -> None:
    rig.api.down = True
    rig.capture(4)
    rig.sender.send_cycle()
    rig.outbox.close()

    # "power cycle": fresh process, same SQLite file
    rig.api.down = False
    client = httpx.Client(transport=httpx.MockTransport(rig.api.handler))
    outbox = Outbox(rig.cfg.outbox_db, clock=rig.clock)
    state = AgentState(started_at=rig.clock())
    sender = Sender(
        outbox,
        client,
        DeviceAuth(client, rig.cfg, clock=rig.clock),
        rig.cfg,
        state,
        clock=rig.clock,
        rng=random.Random(2),
    )
    rig.outbox = outbox
    _drain(rig, sender)
    assert len(rig.api.stored) == 4
