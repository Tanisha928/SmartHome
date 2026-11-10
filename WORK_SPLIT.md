# Work Division by Component (companion to PLAN.md)

Ownership follows the Group 9 design documents: each member owns **one vertical slice from API to UI**.

| Member | Component | Also owns (per SDD §5.1) |
|---|---|---|
| **Mithil Devisetty** | 1. System Dashboard | UI component library, navigation, WebSocket client, demo script, demo video |
| **Sakshat Patil** | 2. Home IoT Device Manager | Edge agent, device data model, heartbeat + connectivity logic, AWS env setup (with Tanisha) |
| **Vritika Malhotra** | 3. AI Alert Tracking & Monitoring | Policy engine, alert state machine, SNS notification, ML service integration, security hardening (with Tanisha) |
| **Tanisha Dave** | 4. System Database Management | PostgreSQL schema + migrations, MongoDB, repository layer, S3 access, ingest, Data Operations console |

Shared by all: API contract freeze, integration testing, AWS account/VPC, IEEE paper, demo video, final presentation. Each member writes unit tests for their own component and reviews one other member's pull requests.

**Review pairs (secondary reviewer):** Mithil ↔ Vritika, Sakshat ↔ Tanisha. If someone becomes unavailable, the reviewer carries the component.

---

## 0. Ground rules for working in parallel

1. **Branching:** `main` is protected. Branch names `mithil/<topic>`, `sakshat/<topic>`, `vritika/<topic>`, `tanisha/<topic>`. All merges by PR with one review.
2. **Folder ownership (CODEOWNERS):**
   - `backend/app/persistence/**`, `backend/alembic/**`, `backend/app/core/**`, `backend/app/auth/**` → Tanisha
   - `backend/app/iot/**`, `edge/**` → Sakshat
   - `backend/app/alerts/**`, `backend/app/ml/**`, `backend/app/workers/model_worker.py` → Vritika
   - `frontend/src/{routes,components,stores,api,lib,styles,test}/**`, `frontend/src/features/{auth,admin-live,owner-home}/**` → Mithil
   - `frontend/src/features/devices/**` → Sakshat; `frontend/src/features/alerts/**` → Vritika; `frontend/src/features/dataops/**` → Tanisha
   - `infra/terraform/**` → Sakshat + Tanisha; `scripts/**`, `docs/**` → shared
3. **Never edit another member's folder** without opening a PR they review. Need a change in someone's API? Open an issue titled `CONTRACT: <endpoint>` and update PLAN.md section 4 first.
4. **Mock first.** The moment the contract is frozen, Tanisha publishes the OpenAPI JSON (`/openapi.json` committed as `docs/openapi.json`). Mithil generates the TS client from it; each owner exposes stub responses so the frontend never waits.
5. **Daily integration rule:** merge to `main` at least once a day; CI (lint + unit tests) must stay green.
6. **Definition of done per task:** code + tests + OpenAPI docs + acceptance check from PLAN.md phase passes + PR merged.

---

## 1. Dependency map (who unblocks whom)

```
Tanisha: core + persistence + auth (PLAN Phases 1–2)  ──► unblocks everyone
      │
      ├─► Sakshat: IoT cloud (Ph 3) ─► Edge agent (Ph 6)
      ├─► Tanisha: Ingest (Ph 4) ─► Vritika: Alert pipeline (Ph 5) ─► WS hub
      └─► Mithil: frontend foundation (Ph 7) runs in parallel using MSW mocks
                    └─► feature modules by each owner (Ph 8–10)
All: integration (Ph 11–12)
```

**Critical early hand-offs (do these first):**
| Hand-off | From → To | Deadline |
|---|---|---|
| Docker Compose + LocalStack + CI skeleton | Tanisha → all | Day 1 |
| Alembic migration 0001 + models + repositories skeleton | Tanisha → Sakshat, Vritika | Day 2–3 |
| `core` (JWT, deps, errors, correlation id) + auth endpoints + seed data | Tanisha → all | Day 3 |
| Frozen `docs/openapi.json` + MSW fixtures | Tanisha + owners → Mithil | Day 3 |
| `Classifier` interface + `MockClassifier` | Vritika → Tanisha, Sakshat | Day 3 |
| Ingest endpoint + SQS message format | Tanisha → Vritika, Sakshat | Day 6 |

---

## 2. Member 1 — Mithil Devisetty: System Dashboard (Component 1)

**Scope:** React SPA shell, shared UI library, auth state, API client, WebSocket client, role-based routing, live monitoring, owner home, exports, demo mode. Does **not** classify, access DBs, or decide severity.

### Tasks
| # | Task | PLAN ref | Output |
|---|---|---|---|
| M1 | Vite + TS + Tailwind scaffold, lint, Vitest, MSW, Playwright config | Ph 7 | `frontend/` boots |
| M2 | `apiClient.ts`: bearer + `X-Correlation-Id`, error normalization, single coordinated refresh + one retry on 401, 403 handling | 7.1 | tests: refresh-once, 403 message |
| M3 | `authStore` (in-memory token), login/signup pages (A1), role redirect, `RouteGuard` (return path kept) | 7.1/7.2 | tests: guard redirects |
| M4 | Shared UI library: `DataView` (loading/empty/error+correlation id/stale), `SeverityBadge` (color+icon+text), tables, dialogs, toasts, form fields, 44 px targets, 16 px base | 7.1/7.3 | storybook-style demo page |
| M5 | `alertSocket.ts` state machine (disconnected→connecting→catching_up→live→backoff/polling→refreshing_token), bounded backoff 1–30 s, REST catch-up with `updated_since`, 30 s polling fallback | 7.1 | state-machine tests |
| M6 | `alertStore.ts`: reject unknown/out-of-scope, dedupe by `alert_id`, ignore older `version`, bounded list | 7.1 | unit tests |
| M7 | A2 Live alert map: category tiles as filters, filter rail, **Save view** (calls `GET/PUT /api/users/me/saved-views`), Leaflet pins by severity, synchronized list, flash on insert | 7.2 | screen + tests |
| M8 | A3 Alert history: table, search, date range, sort, filter rail, CSV/PDF export via `exportService` (CSV escaping + formula-injection guard) | 7.2 | screen + tests |
| M9 | A7 Settings and activity | 7.2 | screen |
| M10 | H1 Owner home (status banner, alert card with **This is fine / Call for help**, device tiles), H3 Owner history with friendly labels (`lib/labels.ts`) | 7.2 | screens |
| M11 | Mounting: admin and owner layout shells, left nav, house selector, mounting points for features owned by others (A4/A8/H2 devices; A5/A6/H4/H5 alerts; D1–D5 data ops) | 7.2 | route table |
| M12 | Demo mode (`VITE_DEMO_MODE`) with MSW fixtures for every endpoint | 7.3 | demo works with no backend |
| M13 | Playwright E2E: admin flow, owner flow, conflict flow; owner-leak test (no `confidence` in owner DOM/API) | Ph 8–9 | CI job |
| M14 | Demo script (`scripts/demo.md`), demo video production | §13 | video |

**Backend dependencies you consume:** `/api/auth/*`, `/api/houses`, `/api/alerts*`, `/api/stats/alerts`, `WS /ws/alerts`.
**You provide to others:** `DataView`, `SeverityBadge`, form/table/dialog components, route mounting points, `apiClient` (they must use it, not raw `fetch`).

**Acceptance (your phase exit):** PLAN Phase 7, 8 (A2/A3/A7) and 9 (H1/H3) checks; Playwright admin flow green against mocks first, then real stack.

---

## 3. Member 2 — Sakshat Patil: Home IoT Device Manager (Component 2)

**Scope:** rooms, devices, keys, heartbeat, commands, connectivity, edge agent, device UI, and (with Tanisha) AWS environment.

### Tasks — backend (`backend/app/iot`)
| # | Task | PLAN ref |
|---|---|---|
| S1 | `RoomService` + `POST/GET/PATCH /api/rooms` (409 duplicate label, scope checks) | 6.1 |
| S2 | `DeviceService.register`: resolve house from room, unique serial 409 `duplicate_serial`, API key `dk_...` generated, sha256 stored, **shown once**, initial `offline` | 6.1 |
| S3 | `GET/PATCH/DELETE /api/devices`, owner restricted to `status`; threshold 0.50–0.99 admin only (422); soft remove + key revoke; `rotate-key` | 6.1 |
| S4 | `DeviceAuthService` + `POST /api/auth/device-token` (15-min JWT bound to device_id+house_id; 401 on bad/revoked key; rate limit) | 5.2 |
| S5 | `HeartbeatService.handle`: 403 `device_mismatch` + security log, update `last_heartbeat/wifi_rssi/online`, write telemetry (via `TelemetryRepository`), return commands + changed config | 6.1 |
| S6 | `CommandQueue.issue`: 409 `command_pending`, 60-min expiry; `POST /command-ack` | 6.1/6.2 |
| S7 | `ConnectivitySweeper.run`: offline after 10 min; publishes `device.updated` events (FR-4 within 5 s) | 6.2 |
| S8 | `POST /api/houses/{id}/disable|enable` cascade in one transaction, partial-failure rollback | 6.1 |
| S9 | Unit tests (freezegun for 10-minute rule, mismatch, key rotation, rollback) | Ph 3 |

### Tasks — edge (`edge/`)
| # | Task | PLAN ref |
|---|---|---|
| S10 | `outbox.py` SQLite per SDD 4.1.3, 2 GB cap pruning | 6.3 |
| S11 | `device_auth.py` token cache/refresh; `sender.py` loop (oldest-first, backoff max 300 s, `device_disabled` discard, 403 quarantine) | 6.3 |
| S12 | `config_sync.py` (enable/disable immediate, reboot, thresholds, command ack) | 6.3 |
| S13 | `simulator.py` + `cli.py` (`simulate`, `--burst`, `--offline-for`), sample WAVs | 6.3 |
| S14 | Edge tests: restart persistence, replay exactly once, disable discards unsent | Ph 6 |

### Tasks — frontend (`frontend/src/features/devices`)
| # | Task | PLAN ref |
|---|---|---|
| S15 | A4 Device management (house + device registration forms with Add/Update/Disable/Enable/Remove, search, house tree, disable-house confirm showing count, one-time API-key modal) | 7.2 |
| S16 | A8 Fleet view (connectivity stats, table) | 7.2 |
| S17 | H2 Owner "My devices" (add room, add device by serial, per-device capture toggle, no raw IDs) | 7.2 |

### Infra (with Tanisha)
| # | Task | PLAN ref |
|---|---|---|
| S18 | Terraform: VPC/subnets/SGs, ALB + target groups + health checks, ASG (API + workers), IAM roles, Nginx + systemd, deploy script | Ph 11 |
| S19 | CloudWatch alarms and dashboards for CPU, queue depth, latency | Ph 11 |

**You consume:** repositories (`DeviceRepository`, `CommandRepository`, `TelemetryRepository`) from Tanisha; `DataView`/forms from Mithil; ingest endpoint for the agent.
**You provide:** device inventory API (consumed by dashboard and alert service for room/device metadata), `device.updated` events, edge simulator (used by everyone for demos and load tests).

**Acceptance:** PLAN Phases 3 and 6; Phase 11 infra checks.

---

## 4. Member 3 — Vritika Malhotra: AI Alert Tracking & Monitoring (Component 3)

**Scope:** turn inference into auditable alerts: thresholds, severity, dedupe, recipients, SNS, state machine, stats, WebSocket fan-out, model worker, ML integration.

### Tasks — backend (`backend/app/alerts`, `ml`, `workers/model_worker.py`)
| # | Task | PLAN ref |
|---|---|---|
| V1 | `catalog.py` (sound → category → default severity) and `SeverityMapper` (0.90 boundary rules) | 8.1–8.2 |
| V2 | `ThresholdResolver` (device → house → global → 0.80) + `GET/PUT /api/admin/thresholds` (admin only) | 8.1 |
| V3 | `DuplicateDetector` (same sound + room within 60 s; counter on prior alert) | 8.1 |
| V4 | `PolicyEngine.handle` per the 10-step pipeline (idempotent on redelivery; one transaction for alert + history + event scored; publish after commit) | 8.1 |
| V5 | `AlertStateService.transition` with `expected_state`, atomic history, 409 `state_conflict` (`current_state`, `last_actor`), 422 `invalid_transition`; role matrix | 8.4–8.5 |
| V6 | `RecipientResolver` (category/severity/channel prefs) and `NotificationDispatcher` (SNS, retries 5/15/45 s, delivery rows, resend) | 8.3 |
| V7 | `EscalationTimer` (critical in new/notified > 5 min → escalated, system actor) | 8.6 |
| V8 | Alert APIs: list with all filters (incl. confidence band, `updated_since`), detail (signed clip URL; owner payload sanitized), PATCH state, export CSV/PDF, `resend` | 8.4 |
| V9 | `StatsService` + `/api/stats/alerts`, `/api/stats/false-alerts` (low-sample < 20) | 8.7 |
| V10 | `notification-prefs` GET/PUT (scope 403) | 8.4 |
| V11 | WebSocket hub: `ws.py`, subprotocol auth, house/admin groups, ping 25 s, Postgres LISTEN/NOTIFY fan-out across instances | 8.8 |
| V12 | `ml/classifier.py` Protocol + `MockClassifier` + `ModelClassifier` stub; `preprocess.py` | 9 |
| V13 | `model_worker.py`: SQS long-poll, clip fetch, classify, `PolicyEngine.handle`, delete on success, graceful SIGTERM, DLQ failed-marking | 9 |
| V14 | `/internal/inference-results` test adapter (guarded by key) | D10 |
| V15 | Tests: threshold truth table, severity boundaries, below-threshold log, 60 s vs 61 s dedupe, redelivery = one alert, full transition matrix, SNS retry timing, all-fail stays `new`, auto-escalate, WS isolation | Ph 5 |

### Tasks — frontend (`frontend/src/features/alerts`)
| # | Task | PLAN ref |
|---|---|---|
| V16 | A5 Alert detail side panel (waveform + playback, map thumbnail, delivery table, history timeline, 4 action buttons with note, Resend failed) | 7.2 |
| V17 | A6 False-alert analytics (ranked table, trend chart, low-sample flag, inline threshold editing, click-through to A3) | 7.2 |
| V18 | H4 Owner alert detail (read-mostly, Dismiss; no confidence/model) | 7.2 |
| V19 | H5 Profile + notification matrix (email/SMS per category + min severity) | 7.2 |

### Shared (with Tanisha)
| # | Task |
|---|---|
| V20 | Security hardening + scope-isolation negative tests (PLAN Ph 12) |
| V21 | ML integration with the real provided model once supplied (activity N) |

**You consume:** `AlertRepository`, `InferenceLogRepository`, `EventRepository`, `NotificationRepository`, `ClipStore` from Tanisha; device/room metadata via `DeviceRepository`; SNS/SQS via LocalStack.
**You provide:** alert REST + WS contract to Mithil, `alert.created/updated` events, alert audit trail used by Data Ops.

**Acceptance:** PLAN Phase 5 checks plus frontend parts of Phases 8–9.

---

## 5. Member 4 — Tanisha Dave: System Database Management (Component 4)

**Scope:** foundation for everyone: scaffold/infra-as-compose, core utilities, auth, schema, repositories, ingest, jobs, data-ops console.

### Tasks — foundation (do first; unblocks the team)
| # | Task | PLAN ref |
|---|---|---|
| T1 | Repo scaffold, `docker-compose.yml`, LocalStack init (S3, SQS+DLQ, SNS), `.env.example`, Makefile, CI, CODEOWNERS, `.cursor/rules` | Ph 0 |
| T2 | `core/`: config, structured JSON logging, correlation-id middleware, error classes + handlers, JWT/password/key-hash utils, `deps.py` (claims, role guards), rate limiter | Ph 1 |
| T3 | Alembic `0001_initial` with all 13 tables, constraints, indexes, append-only trigger on `alert_state_history` | 4.1 |
| T4 | Mongo client + `ensure_indexes` (`inference_logs`, `sensor_telemetry` TTL 30 d) | 4.2 |
| T5 | `ClipStore` (SSE, signed URL, delete) and `QueuePublisher` | 4.3 |
| T6 | `BaseRepository.apply_scope` (+ `admin_read_audit`) and **all repositories** with the signatures in PLAN 4.4 (publish skeletons first so others can code against them) | 4.4 |
| T7 | Seed script (admin, owners, 3 houses, rooms, devices, residents), `create_admin.py` | Ph 1 |
| T8 | Import-linter test (no DB/AWS imports outside persistence) | §3 |

### Tasks — auth + houses (`backend/app/auth`, `persistence/api`)
| # | Task | PLAN ref |
|---|---|---|
| T9 | Auth endpoints: signup, login (429 limiter), refresh cookie rotation, logout, `users/me`, saved-views | 5.2 |
| T10 | Houses API: `POST/GET /api/houses`, `GET /api/houses/{id}`, owner linking (D8), SNS topic per house | Ph 2 |

### Tasks — ingest + jobs + admin data APIs
| # | Task | PLAN ref |
|---|---|---|
| T11 | `IngestService.handle` + `POST /api/ingest/events` (validation, 413, 403, duplicate 200, S3 503, SQS-failure 202) + `GET /api/events/{id}` | 4.5 |
| T12 | `StuckEventSweeper`, `RetentionJob`, backup-status recording (RDS snapshot check, weekly mongodump → S3) | 4.6 |
| T13 | Admin data APIs: `data/health`, `events`, `events/{id}/retry`, `inference-logs`, `audit`, `retention` (D1 validation) | 4.6 |
| T14 | `sweepers.py` runner wiring connectivity (Sakshat), escalation (Vritika), stuck-event and retention loops | Ph 4 |
| T15 | Tests per business table 4.4 + load check 50 clips/min | Ph 4 |

### Tasks — frontend (`frontend/src/features/dataops`)
| # | Task |
|---|---|
| T16 | D1 Data health tiles (15 s refresh) · D2 Event pipeline (state tabs, retry per row, 409 handling) · D3 Inference explorer · D4 Audit log + CSV export · D5 Retention & backup |

### Infra / shared
| # | Task |
|---|---|
| T17 | RDS (encrypted, daily snapshots), MongoDB EC2, S3 + VPC endpoint, SQS/DLQ, SNS in Terraform (with Sakshat) |
| T18 | Publish `docs/openapi.json`, `docs/api.md`, runbook, test plan |
| T19 | Security hardening + scope-isolation negative tests (with Vritika) |

**You provide:** everything others import. Priority order: T1 → T2 → T3 → T6 skeleton → T9 → T5 → T11.
**Acceptance:** PLAN Phases 0–2 and 4, plus Phase 10 and your part of 11–12.

---

## 6. Week-by-week schedule (compressed to today, Nov 9 → Dec 11, 2026)

The SDD schedule had implementation finishing Nov 16, so this assumes the team is catching up. Milestones stay: **M3 Nov 16, M4 Nov 30, M5 Dec 11.**

### Week 1 — Nov 9–15 (foundations in parallel)
| Member | Goals |
|---|---|
| Tanisha | T1–T8 by Nov 11; T9–T10 by Nov 13; T5 + T11 started; publish OpenAPI |
| Sakshat | S1–S6 against repository skeletons (Nov 10–14); S10–S11 edge outbox/sender with a mock server |
| Vritika | V1–V3, V12, V5 (state service tests against in-memory repos), V15 unit tests for pure logic |
| Mithil | M1–M6 (client, auth, UI library, socket, store) using MSW; M3 login flow |

**M3 target (Nov 16):** each component passes its own tests against mocks.

### Week 2 — Nov 16–22 (feature completion)
| Member | Goals |
|---|---|
| Tanisha | T11 ingest done, T12–T15 jobs/admin APIs, T16 D1–D2 |
| Sakshat | S7–S9, S12–S14, S15 (A4), S16 |
| Vritika | V4, V6–V11, V13–V14 (end-to-end pipeline with real ingest), V16 (A5) |
| Mithil | M7 (A2 + live), M8 (A3), M10 (H1/H3), M11 mounting of others' modules |

### Week 3 — Nov 23–29 (integration)
| Member | Goals |
|---|---|
| All | End-to-end slice: edge simulator → ingest → worker → alert → dashboard (do this by Nov 25) |
| Tanisha | D3–D5, T17 Terraform data tier |
| Sakshat | S17 (H2), S18–S19 Terraform compute + alarms, load test scripts |
| Vritika | V17–V19 (A6, H4, H5), V20 negative tenancy tests |
| Mithil | M12 demo mode, M13 Playwright flows, fix integration bugs |

**M4 target (Nov 30):** system deployed on EC2 behind the ALB; end-to-end alert works from device to dashboard.

### Week 4–5 — Dec 1–11 (testing, evidence, delivery)
| Who | Work |
|---|---|
| All | Integration + load testing (NFR-1…5 evidence), security hardening, CloudWatch screenshots |
| Mithil | M14 demo script + video (T) |
| All | IEEE paper (U), presentation (V), final package (W) |

**M5 (Dec 11):** live demo, video, paper, package submitted.

---

## 7. Per-member Cursor prompt (copy into Cursor in the member's own branch)

**Mithil:** *"Read PLAN.md sections 0–3, 7 and WORK_SPLIT.md section 2. I own the frontend shell and shared UI. Implement tasks M1–M6 first using MSW mocks generated from docs/openapi.json. Do not modify files outside `frontend/src/{routes,components,stores,api,lib,styles,test}` and `features/{auth,admin-live,owner-home}`."*

**Sakshat:** *"Read PLAN.md sections 0–3, 6 and WORK_SPLIT.md section 3. I own `backend/app/iot`, `edge/` and `frontend/src/features/devices`. Implement S1–S9 using the repository interfaces in `app/persistence/repositories` (code against the skeleton signatures; do not touch SQL). Then S10–S14. Write the tests listed."*

**Vritika:** *"Read PLAN.md sections 0–3, 8, 9 and WORK_SPLIT.md section 4. I own `backend/app/alerts`, `backend/app/ml`, `workers/model_worker.py` and `frontend/src/features/alerts`. Implement V1–V5 as pure, unit-tested logic first, then the dispatcher, APIs, WebSocket hub and worker. Follow the pipeline order in 8.1 and the transition matrix in 8.5 exactly."*

**Tanisha:** *"Read PLAN.md sections 0–5, 10 and WORK_SPLIT.md section 5. I own the foundation. Do T1 → T2 → T3 → T6 (skeleton signatures first, commit immediately) → T9 → T5 → T11 in that order, then the rest. Everything other members import must have stable signatures matching PLAN 4.4."*

---

## 8. Integration checkpoints and test ownership

| Checkpoint | Date | Test | Owner |
|---|---|---|---|
| Contract frozen | Nov 11 | `docs/openapi.json` committed; MSW fixtures cover all endpoints | Tanisha + Mithil |
| Ingest → SQS format | Nov 14 | Edge simulator upload creates a queued event and SQS message | Tanisha + Sakshat |
| Pipeline slice | Nov 25 | Clip → alert row → WS push → visible in A2/H1 | Vritika + Mithil |
| Conflict flow | Nov 25 | Two admins acknowledge simultaneously → second sees 409 UI | Vritika + Mithil |
| Capture-disable flow | Nov 26 | Owner toggles off → edge stops, admin sees state ≤ 5 s | Sakshat + Mithil |
| DLQ flow | Nov 27 | Forced failures → D1/D2 retry | Tanisha |
| Tenant isolation | Nov 28 | House A token vs house B on every endpoint, WS, signed URL, export | Vritika + Tanisha |
| Deployed E2E | Nov 30 | Everything on EC2 behind ALB | All |
| Load/NFR evidence | Dec 4 | 100 sessions, 50 clips/min, p95 latency numbers, ASG scale-out | Sakshat + Tanisha |

## 9. Risks specific to this split
- **Tanisha is the critical path.** Mitigation: she publishes skeleton signatures and the OpenAPI stub early; Sakshat can fall back to implementing `RoomService`/`DeviceService` against in-memory fakes; Mithil uses MSW.
- **Real ML model not available.** Vritika builds against `MockClassifier`; the adapter is swapped in V21.
- **Frontend is shared by four people.** Mithil owns the shell and shared components; others only add files under their `features/*` folder and consume shared components, to avoid merge conflicts.
- **Real devices absent.** The edge simulator (Sakshat, S13) is treated as a first-class deliverable and used by everyone for demos and load tests.
