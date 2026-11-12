"""`edge-agent run | simulate | status | make-samples` (PLAN 6.3)."""

from __future__ import annotations

import json
import logging
import signal
import threading
import time
from pathlib import Path

import typer

from edge_agent.agent import Agent
from edge_agent.config import EdgeConfig
from edge_agent.outbox import Outbox
from edge_agent.simulator import Simulator, make_samples, parse_duration

app = typer.Typer(help="Smart Home edge agent", no_args_is_help=True)


def _setup(env_file: Path | None, verbose: bool) -> EdgeConfig:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not verbose:  # one line per HTTP request drowns out heartbeats/uploads; -v brings it back
        logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = EdgeConfig.load(env_file)
    if not cfg.device_id or not cfg.api_key:
        raise typer.BadParameter("DEVICE_ID and API_KEY must be set (env or --env-file)")
    return cfg


def _stop_on_signals() -> threading.Event:
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    return stop


@app.command()
def run(
    env_file: Path | None = typer.Option(None, "--env-file", help="KEY=VALUE config file"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the agent: watch CLIP_DIR/inbox, upload, heartbeat."""
    cfg = _setup(env_file, verbose)
    agent = Agent(cfg)
    agent.run(_stop_on_signals())
    if agent.state.auth_failed:
        typer.echo("Device key rejected. Get a new key from A4 (Rotate key) and restart.", err=True)
        raise typer.Exit(code=2)


@app.command()
def simulate(
    wav: Path = typer.Option(..., "--wav", exists=True, dir_okay=False, help="clip to replay"),
    every: str = typer.Option("30s", "--every", help="interval between clips, e.g. 30s, 2m"),
    room: str | None = typer.Option(None, "--room", help="room label (metadata only)"),
    burst: int = typer.Option(1, "--burst", min=1, help="clips per interval (load tests)"),
    count: int = typer.Option(0, "--count", min=0, help="stop after N intervals (0 = forever)"),
    offline_for: str | None = typer.Option(
        None, "--offline-for", help="pretend the network is down for this long at start"
    ),
    env_file: Path | None = typer.Option(None, "--env-file"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the agent while replaying WAV clips as if captured."""
    cfg = _setup(env_file, verbose)
    agent = Agent(cfg)
    sim = Simulator(agent.outbox, cfg.device_id, cfg.spool_dir, wav, room=room)
    interval = parse_duration(every)
    if offline_for:
        agent.state.offline_until = time.time() + parse_duration(offline_for)
        typer.echo(f"network offline for {offline_for}; clips will buffer")

    stop = _stop_on_signals()
    state = {"next": 0.0, "intervals": 0}

    def on_tick(a: Agent) -> None:
        now = time.time()
        more = not count or state["intervals"] < count
        if more and now >= state["next"] and a.state.capture_enabled:
            sim.emit(burst)
            state["intervals"] += 1
            state["next"] = now + interval
            typer.echo(f"emitted {burst} clip(s); buffer depth={a.outbox.depth()}")
        if count and state["intervals"] >= count and a.outbox.depth() == 0:
            stop.set()

    agent.run(stop, on_tick=on_tick)


@app.command()
def status(env_file: Path | None = typer.Option(None, "--env-file")) -> None:
    """Show outbox counts and buffer size."""
    cfg = EdgeConfig.load(env_file)
    outbox = Outbox(cfg.outbox_db)
    typer.echo(
        json.dumps(
            {
                "device_id": cfg.device_id,
                "api_base": cfg.api_base,
                "outbox": outbox.counts(),
                "buffer_depth": outbox.depth(),
                "buffer_bytes": outbox.buffer_bytes(),
                "buffer_cap_bytes": cfg.buffer_cap_bytes,
            },
            indent=2,
        )
    )
    outbox.close()


@app.command("make-samples")
def make_samples_cmd(
    out: Path = typer.Option(Path("samples"), "--out", help="directory for generated WAVs"),
) -> None:
    """Generate the synthetic sample WAVs (glass_break, smoke_fire_alarm, fall, distress)."""
    for path in make_samples(out):
        typer.echo(path)


if __name__ == "__main__":
    app()
