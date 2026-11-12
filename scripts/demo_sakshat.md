# Component 2 demo — Home IoT Device Manager (Sakshat)

Live demo (3 pts) + scenario video (2 pts). Shows the component's UI (A4 Devices, A8 Fleet,
H2 My devices), its backend (rooms, devices, keys, heartbeat, commands, connectivity, house
cascade) and the edge agent (outbox, upload, config sync, offline replay), plus its unit tests.

Rehearsed end to end on a fresh stack on 2026-11-11. Total runtime about 8 minutes.

## One-time setup

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && cd ..
cd edge && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && cd ..
cd frontend && npm ci && cd ..
```

Docker Desktop must be running.

## Before each take (about 1 minute)

```bash
scripts/demo_reset.sh -y
```

Wipes local data, starts Postgres, Mongo, LocalStack, API, model worker and sweepers with
**demo timings** (`docker-compose.demo.yml`: device offline 1 minute after its last heartbeat,
sweeper every 10 s), migrates, seeds, and creates a demo owner with no house yet.

Then, in a second terminal, start the UI and open http://localhost:5173:

```bash
cd frontend && VITE_API_BASE=http://localhost:8000 npm run dev
```

| Login | Email | Password |
|---|---|---|
| Admin | `admin@smarthome.local` | `admin-password-1` |
| Owner | `owner.demo@example.com` | `demo-owner-1` |

Terminal layout that works on screen: **T1** UI dev server (minimised), **T2** edge agent logs,
**T3** commands. Browser: admin in a normal window, owner in a private window.

## Live demo script

| # | Do | Say / point at | Proves |
|---|---|---|---|
| 0 | T3: `cd backend && .venv/bin/python -m pytest tests/unit/iot -q`<br>`cd ../edge && .venv/bin/python -m pytest -q`<br>`cd ../frontend && npx vitest run src/features/devices` | 87 component tests: 32 backend, 33 edge, 22 UI. Mention the 10-minute offline rule, duplicate serial 409, device mismatch 403, key rotation, cascade rollback, outage replay. | Unit demo |
| 1 | Admin → **Devices** (A4). Register house: `10 Demo Lane`, Seattle, WA, `98109`, lat `47.62`, lng `-122.35`, owner email `owner.demo@example.com` → **Add house** | "House #4 registered. Owner … linked." The house appears in the tree on the right. | House registration, owner linking |
| 2 | Register device: house #4 → Room **+ New room…** (Living room) → serial `SN-DEMO-001` → label `Living room mic` → **Add** | One-time key dialog: "It will not be shown again." **Copy key**, note the device id (`#8 …`) in the tree. | Device + room registration, key shown once |
| 3 | Same serial again → **Add** | "That serial number is already registered." | Unique serial (409) |
| 4 | T2: `scripts/demo_agent.sh <device_id> <api_key> 4` | Agent log `heartbeat ok …`. In A4 the row flips **○ Offline → ● Online** with RSSI, no reload. Open **Fleet** (A8): Online tile counts it. | Device auth (key → 15-min JWT), heartbeat, live status |
| 5 | T3: `scripts/simulate_glass_break.sh` | T2: `captured glass_break-…`, `sent=1`. **Live alerts** shows the glass-break alert. | Edge capture → outbox → ingest |
| 6 | Owner window: log in → **My devices** (H2) → switch **Listening** off | Admin A4 shows **⏸ Disabled** immediately. T2 within 5 s: `command received: disable`, `capture=off`. | Owner toggle, enable/disable ≤ 5 s (FR-4, NFR-11) |
| 7 | T3: `scripts/simulate_glass_break.sh` | T2: `capture disabled; dropped 1 new clip(s)`. Nothing uploads. Switch Listening back **on**. | Disabled device captures nothing |
| 8 | A4: click the device → **Send reboot** (press twice) | "Reboot queued…", then "That command is already waiting for the device." T2: `command received: reboot`, `restart requested`. | Command queue, ack, `command_pending` |
| 9 | A4: device selected → threshold `0.85` → **Update**. Owner tries nothing (owners only get the Listening switch). | Admin-only fields; owner UI has no raw IDs or thresholds. | Role rules (owner = status only) |
| 10 | T3: `docker compose stop backend` → `scripts/simulate_glass_break.sh 3` → `scripts/demo_status.sh` | `buffer_depth: 3` while the API is down. | Edge outbox buffering (FR-20) |
| 11 | T3: `docker compose start backend` → wait ~10 s → `scripts/demo_status.sh` | `buffer_depth: 0`. **Data → Event pipeline** (D2) shows them once each; the server dedupes resends. A4 reconnects by itself. | Replay oldest-first, exactly once |
| 12 | T2: Ctrl-C the agent. Wait ~70 s on A4 / Fleet. | Row flips to **○ Offline** without a reload; Fleet Offline tile +1. | Offline after missed heartbeats (FR-5) |
| 13 | A4: **Rotate key** → restart the agent with the *old* key: `scripts/demo_agent.sh` | New key dialog; agent log shows the old key rejected and the agent stops. | Key rotation / revocation |
| 14 | A4: **Disable house** on house #4 → confirm dialog says "all 1 device(s)" → confirm. Then **Enable house**. | Cascade in one transaction; device shows Disabled, then Enabled. | House disable cascade |

If the API is restarted (step 11), the browser stays signed in; if you reload a page, sign in
again (tokens are kept in memory only, by design).

## Video shot list (3–4 minutes, one take)

1. **0:00** Title card: Component 2, Home IoT Device Manager. One sentence: registers houses, rooms
   and devices, authenticates devices, tracks heartbeat/connectivity, sends commands, and runs the
   edge agent that buffers and uploads clips.
2. **0:15** Tests running (step 0), final counts on screen.
3. **0:40** Register house + device, key dialog (steps 1–2).
4. **1:10** Start agent, device goes Online live; Fleet view (step 4).
5. **1:35** Glass-break clip uploads (step 5).
6. **1:55** Owner switches Listening off → admin sees Disabled; agent drops the next clip (steps 6–7).
7. **2:25** Send reboot → agent acks (step 8).
8. **2:45** Outage: buffer depth 3 → restore → replayed once (steps 10–11).
9. **3:20** Stop agent → Offline (step 12); trim the wait in editing.
10. **3:40** Close: requirements covered (FR-1–5, FR-20, NFR-11) and what's next (AWS deploy).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `demo_reset.sh` stuck waiting for the API | `docker compose logs backend`; Docker Desktop must be running. |
| Device never goes Online | Check the agent terminal for `invalid_key` (wrong key or device id); rerun `scripts/demo_agent.sh <id> <key> <house>`. |
| UI shows "Missing bearer token" / signed out | You reloaded the page; sign in again. |
| Owner sees no devices | Register the house with `owner.demo@example.com` **before** the owner logs in. |
| Replay slow after restore | Wait 10 s; the demo agent caps retry backoff at 5 s (`MAX_BACKOFF_SEC`). |
