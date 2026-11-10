# Edge agent (Component 2 — Sakshat)

Python agent that runs on (or simulates) a home audio/camera device. It holds **no AWS
credentials**: it exchanges its device API key for a 15-minute JWT and talks HTTPS to the API.

```
capture (FileCapture / Simulator) → SQLite outbox → sender (oldest-first, backoff) → POST /api/ingest/events
                                     ↑ buffer_depth          heartbeat ↔ commands/config (ConfigSync)
```

## Install

```bash
cd edge
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## Configure (env vars or `--env-file`)

| Var | Default | |
|---|---|---|
| `API_BASE` | `http://localhost:8000` | |
| `DEVICE_ID`, `API_KEY`, `HOUSE_ID` | — | from the one-time key modal in A4 / H2 |
| `OUTBOX_DB` | `outbox.sqlite` | |
| `CLIP_DIR` | `clips` | drop WAV/MP4 into `CLIP_DIR/inbox` for `run` |
| `HEARTBEAT_SEC` / `SEND_CYCLE_SEC` | 60 / 5 | |
| `BUFFER_CAP_GB` | 2 | oldest unsent clips dropped beyond this |

## Commands

```bash
edge-agent make-samples --out samples               # synthetic glass_break/smoke_fire_alarm/fall/distress WAVs
edge-agent run                                      # watch CLIP_DIR/inbox, upload, heartbeat
edge-agent simulate --wav samples/glass_break.wav --every 30s --room living
edge-agent simulate --wav samples/fall.wav --every 1s --burst 5 --count 12        # load test
edge-agent simulate --wav samples/glass_break.wav --every 10s --offline-for 120s  # buffering demo
edge-agent status                                   # outbox counts, buffer bytes
```

## Behaviour

- Every clip is written to the outbox before any network call; survives restarts.
- Upload order is oldest-first. If the oldest clip is backing off (2^n s, max 300 s, jitter),
  newer clips wait. Re-sends are safe: the API dedupes on `(device_id, captured_at)`.
- `device_disabled` → discard unsent clips and pause capture. Any other 403 → quarantine the clip
  and stop until credentials are fixed. 400/413 → quarantine that clip only.
- Heartbeat reports `buffer_depth`; responses carry `enable`/`disable`/`reboot` commands
  (acked via `/command-ack`) and config (`capture_enabled`, `threshold`, `version`).
- Every request carries `X-Correlation-Id: c-YYYYMMDD-<hex>`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Backend contract tests that drive this agent against the real API live in
`backend/tests/unit/iot/test_edge_contract.py` (run after `pip install -e ../edge`).
