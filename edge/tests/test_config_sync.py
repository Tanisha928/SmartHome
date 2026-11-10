"""S12: heartbeat body, config application, commands and acks."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tests.conftest import Rig


def test_heartbeat_reports_buffer_depth_and_version(rig: Rig) -> None:
    rig.capture(2)
    rig.clock.advance(42)
    rig.sync.heartbeat()
    hb = rig.api.heartbeats[-1]
    assert hb["buffer_depth"] == 2
    assert hb["config_version"] == 0
    assert hb["uptime_sec"] == 42


def test_config_applied_and_version_tracked(rig: Rig) -> None:
    rig.api.config = {"capture_enabled": True, "threshold": 0.85, "version": 3}
    rig.sync.heartbeat()
    assert rig.state.config_version == 3 and rig.state.threshold == 0.85
    rig.api.config = None
    rig.sync.heartbeat()
    assert rig.api.heartbeats[-1]["config_version"] == 3


def test_disable_command_discards_unsent_and_acks(rig: Rig) -> None:
    rig.capture(3)
    rig.api.pending_commands = [{"command_id": 11, "command": "disable"}]
    rig.sync.heartbeat()
    assert rig.state.capture_enabled is False
    assert rig.outbox.depth() == 0
    assert rig.api.acks == [{"command_id": 11, "result": "ok"}]
    assert rig.sender.send_cycle().sent == 0

    rig.api.pending_commands = [{"command_id": 12, "command": "enable"}]
    rig.sync.heartbeat()
    assert rig.state.capture_enabled is True


def test_config_capture_disabled_also_discards(rig: Rig) -> None:
    rig.capture(1)
    rig.api.config = {"capture_enabled": False, "threshold": None, "version": 2}
    rig.sync.heartbeat()
    assert rig.outbox.depth() == 0


def test_reboot_sets_restart_flag(rig: Rig) -> None:
    rig.api.pending_commands = [{"command_id": 5, "command": "reboot"}]
    rig.sync.heartbeat()
    assert rig.state.restart_requested
    assert rig.api.acks[-1]["result"] == "ok"


def test_heartbeat_failure_is_tolerated(rig: Rig) -> None:
    rig.api.down = True
    assert rig.sync.heartbeat() is None


def test_simulated_offline_skips_network(rig: Rig) -> None:
    rig.state.offline_until = rig.clock.now + 120
    rig.capture(2)
    assert rig.sync.heartbeat() is None
    rig.sender.send_cycle()
    assert rig.api.uploads == 0 and rig.outbox.depth() == 2
    rig.clock.advance(121 + 300)
    while rig.outbox.depth():
        rig.sender.send_cycle()
        rig.clock.advance(301)
    assert len(rig.api.stored) == 2


def test_simulate_count_stops_after_n_intervals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`simulate --count N` emits exactly N intervals and exits once the buffer drains."""
    from typer.testing import CliRunner

    from edge_agent import cli
    from edge_agent.simulator import write_tone_wav
    from tests.conftest import FakeApi

    api = FakeApi()
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(api.handler))

    monkeypatch.setattr("edge_agent.agent.httpx.Client", fake_client)
    monkeypatch.setattr("edge_agent.agent.threading.Event.wait", lambda self, t=None: False)
    wav = write_tone_wav(tmp_path / "glass_break.wav", freq_hz=440.0, seconds=0.1)
    env = {
        "API_BASE": "http://api.test",
        "DEVICE_ID": "7",
        "API_KEY": "dk_good",
        "HOUSE_ID": "3",
        "OUTBOX_DB": str(tmp_path / "o.sqlite"),
        "CLIP_DIR": str(tmp_path / "clips"),
        "SEND_CYCLE_SEC": "0.001",
    }
    result = CliRunner().invoke(
        cli.app, ["simulate", "--wav", str(wav), "--every", "0", "--count", "3"], env=env
    )
    assert result.exit_code == 0, result.output
    assert len(api.stored) == 3
