# Intelligent Cloud Platform for Smart Homes — Implementation Plan (for Cursor)

> Source of truth: Group 9 *System Design Document* (Oct 10, 2026) and *Component Design* (Nov 1, 2026).
> FR-/NFR- IDs below refer to the SDD. UI IDs (A1–A8, H1–H5, D1–D5) refer to the GUI pages.
> **How to use with Cursor:** put this file at repo root as `PLAN.md`. Work one phase at a time. For each phase, tell Cursor: *"Read PLAN.md sections 0–3 and Phase N. Implement only Phase N. Follow the file paths, signatures, and acceptance checks exactly. Do not change the API contract in section 4."* Commit after every phase passes its acceptance checks.

---

## 0. Ground rules for Cursor (paste into `.cursor/rules/project.mdc` too)

1. **Modular monolith first.** One FastAPI app (`backend/app`) containing the four components as Python packages, plus separate worker processes. Do not create microservices. Components talk only through the interfaces in section 3.
2. **Only the `persistence` package touches PostgreSQL, MongoDB, S3, SQS publishing.** Every other module imports repository classes. Enforce with an import-linter test (Phase 1).
3. **Tenant isolation is mandatory.** A tenant = one house. Every repository query on tenant data goes through `BaseRepository.apply_scope(query, claims)`. Admin reads of a house are written to `admin_read_audit`.
4. **Integer IDs, ISO-8601 UTC timestamps (`...Z`), `X-Correlation-Id` on every request/response/log line/SQS message.**
5. **Error format everywhere:** `{"error": "<machine_code>", "message": "<human text>", "details": {...optional}}`. Use 400 validation, 401 unauthenticated, 403 scope violation, 404 not found, 409 state conflict, 413 too large, 422 invalid transition, 429 rate limit, 503 dependency unavailable.
6. **No secrets in code.** All config via env vars (section 2.4). Edge devices hold no AWS credentials.
7. **Every feature ships with tests** (pytest for backend/edge, Vitest + Testing Library for frontend). A phase is done only when its acceptance checks pass.
8. **Local dev uses Docker Compose with LocalStack** (S3, SQS, SNS) + Postgres 16 + MongoDB 7. Production uses real AWS. Switch by env var `AWS_ENDPOINT_URL`.
9. Prefer small, typed, documented functions. Python 3.12, type hints everywhere, `ruff` + `mypy --strict` on `app/`. TypeScript `strict: true` on the frontend.

---

## 1. Decisions that resolve gaps/conflicts in the design docs

Cursor must follow these; they are not optional.

| # | Topic | Decision |
|---|-------|----------|
| D1 | Clip retention vs S3 IA conflict | Two **separate configurable settings** in `retention_policy`: `clip_expire_days` (default **30**) and `clip_ia_transition_days` (default **null = disabled**). Validation: if both set, `ia_transition_days < expire_days`. Default config deletes at 30 days with no IA transition. |
| D2 | Heartbeat transport | SDD mentions MQTT; component design uses REST heartbeat. **Implement REST heartbeat only** (`POST /api/devices/{id}/heartbeat`). MQTT is out of scope; note as future work. |
| D3 | Threshold catalog | Single catalog in `backend/app/alerts/catalog.py` (section 8.2). Smoke/fire alarm are one sound type `smoke_fire_alarm`. |
| D4 | Owner "This is fine" | → transition to `false_positive` (actor recorded). Owner "Call for help" → transition to `escalated`. Both only allowed from `new`/`notified`. |
| D5 | Alert state machine | See section 8.5 matrix. Terminal: `resolved`, `false_positive`. |
| D6 | Refresh tokens | Access JWT (30 min) in memory on client; refresh token (7 days) in **httpOnly, Secure, SameSite=Strict cookie** `rt`. `POST /api/auth/refresh` reads cookie. Logout clears it. |
| D7 | WebSocket auth | Client sends subprotocol list `["bearer", "<JWT>"]`; server validates JWT, accepts with subprotocol `"bearer"`. House scope comes from the JWT claims; optional `?house_id=` narrows within claims. |
| D8 | Signup | `POST /api/auth/signup` creates role `owner` user with **no house links**. House links happen when an admin registers a house with `owner_email` (link existing user, or create a user with a random temp password + `must_reset=true`, log the reset token in dev). |
| D9 | Device capture toggle (owner) | Owner toggles via `PATCH /api/devices/{id}` `{status: "enabled"|"disabled"}` (owners allowed only `status`, only within their house). Admin may also change label/threshold/room. |
| D10 | Inference transport | Production: model worker consumes SQS, runs classifier, then **calls `PolicyEngine.handle()` in-process via the worker's import** (same codebase). The HTTP `POST /internal/inference-results` is a test adapter only, guarded by `INTERNAL_API_ENABLED=true` and an `X-Internal-Key` header. |
| D11 | ML model | The "provided models" interface is unknown. Define `Classifier` protocol (section 9) with `MockClassifier` (deterministic by filename/label) and `ModelClassifier` (wrapper to be filled when the real model is supplied). Default `CLASSIFIER=mock`. |
| D12 | PDF export | CSV is required. PDF export (FR-18 low priority) done last via server-side `reportlab` on `GET /api/alerts/export?format=pdf`. |
| D13 | Camera/video | Treat video clips (MP4) the same as audio (WAV): stored, queued, classified by audio track only in this release. |
| D14 | Hard delete | No destructive alert API. Device "Remove" = soft revoke (`removed_at`, key revoked); house "Disable" = status `disabled`, cascades to devices in one DB transaction. |
| D15 | Edge protocol | HTTPS only. Edge agent = Python package `edge/` with SQLite outbox and a simulator mode that replays WAV files. |

---

## 2. Architecture, tooling and repository layout

### 2.1 Tech stack (fixed)
- **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0 (sync engine + `psycopg[binary]` 3), Alembic, Pydantic v2, `pymongo`, `boto3`, `python-jose` (JWT), `passlib[bcrypt]`, `httpx`, `structlog`, `tenacity`.
- **Workers:** same codebase, entrypoints `python -m app.workers.model_worker`, `python -m app.workers.sweepers`.
- **Frontend:** React 18 + Vite + TypeScript, React Router 6, TanStack Query, Zustand (stores), Tailwind CSS + Radix primitives (or shadcn/ui), Leaflet (react-leaflet) for the live map, Recharts for charts, Vitest, Testing Library, MSW for API mocks, Playwright for E2E.
- **Edge:** Python 3.12, `httpx`, `sqlite3`, `pydantic`, `tenacity`; CLI via `typer`.
- **Infra:** Docker, Docker Compose, LocalStack, Terraform (AWS: VPC, ALB, ASG, RDS, SQS+DLQ, SNS, S3, CloudWatch). Nginx in front of Uvicorn in prod.

### 2.2 Repository layout (create exactly this)

```
smart-home-platform/
├─ PLAN.md
├─ README.md
├─ docker-compose.yml
├─ .env.example
├─ .cursor/rules/project.mdc
├─ backend/
│  ├─ pyproject.toml
│  ├─ alembic.ini
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py                      # FastAPI app factory, router mounting, middleware
│  │  ├─ core/
│  │  │  ├─ config.py                 # Pydantic Settings
│  │  │  ├─ security.py               # JWT encode/decode, password hash, key hash
│  │  │  ├─ deps.py                   # get_current_claims, require_role, get_db
│  │  │  ├─ errors.py                 # AppError subclasses + exception handlers
│  │  │  ├─ middleware.py             # correlation-id, scope middleware, access log
│  │  │  ├─ logging.py                # structlog JSON config
│  │  │  └─ ratelimit.py              # simple in-memory/Redis-less limiter for login
│  │  ├─ persistence/                 # === COMPONENT 4: Database Management (Tanisha) ===
│  │  │  ├─ pg/models.py              # SQLAlchemy models (11 core + 2 proposed)
│  │  │  ├─ pg/session.py
│  │  │  ├─ mongo/client.py
│  │  │  ├─ s3/clip_store.py          # ClipStore.put / signed_url / delete
│  │  │  ├─ queue/publisher.py        # QueuePublisher (SQS)
│  │  │  ├─ repositories/
│  │  │  │  ├─ base.py                # BaseRepository.apply_scope + admin audit
│  │  │  │  ├─ house_repo.py
│  │  │  │  ├─ user_repo.py
│  │  │  │  ├─ room_repo.py
│  │  │  │  ├─ device_repo.py
│  │  │  │  ├─ event_repo.py
│  │  │  │  ├─ alert_repo.py
│  │  │  │  ├─ notification_repo.py
│  │  │  │  ├─ prefs_repo.py
│  │  │  │  ├─ command_repo.py
│  │  │  │  ├─ inference_log_repo.py  # MongoDB
│  │  │  │  ├─ telemetry_repo.py      # MongoDB
│  │  │  │  ├─ audit_repo.py
│  │  │  │  └─ retention_repo.py
│  │  │  ├─ ingest/service.py         # IngestService.handle
│  │  │  ├─ jobs/stuck_event_sweeper.py
│  │  │  ├─ jobs/retention_job.py
│  │  │  └─ api/                      # /api/houses, /api/ingest, /api/events, /api/admin/data|events|audit|retention|inference-logs
│  │  ├─ auth/                        # shared auth service (login/signup/refresh/me)
│  │  ├─ iot/                         # === COMPONENT 2: IoT Device Manager (Sakshat) ===
│  │  │  ├─ room_service.py
│  │  │  ├─ device_service.py
│  │  │  ├─ device_auth_service.py
│  │  │  ├─ heartbeat_service.py
│  │  │  ├─ command_queue.py
│  │  │  ├─ connectivity_sweeper.py
│  │  │  └─ api.py                    # /api/rooms, /api/devices, /api/auth/device-token
│  │  ├─ alerts/                      # === COMPONENT 3: AI Alert Tracking (Vritika) ===
│  │  │  ├─ catalog.py
│  │  │  ├─ policy_engine.py
│  │  │  ├─ threshold_resolver.py
│  │  │  ├─ duplicate_detector.py
│  │  │  ├─ severity_mapper.py
│  │  │  ├─ recipient_resolver.py
│  │  │  ├─ notification_dispatcher.py
│  │  │  ├─ alert_state_service.py
│  │  │  ├─ escalation_timer.py
│  │  │  ├─ stats_service.py
│  │  │  ├─ event_publisher.py        # WebSocket fan-out hub
│  │  │  ├─ api.py                    # /api/alerts*, /api/stats/*, /api/notification-prefs, /api/admin/thresholds
│  │  │  └─ ws.py                     # /ws/alerts
│  │  ├─ ml/
│  │  │  ├─ classifier.py             # Protocol + MockClassifier + ModelClassifier
│  │  │  └─ preprocess.py
│  │  └─ workers/
│  │     ├─ model_worker.py
│  │     └─ sweepers.py               # runs connectivity, stuck-event, escalation, retention loops
│  └─ tests/ (unit/, integration/, e2e/, conftest.py)
├─ edge/
│  ├─ pyproject.toml
│  ├─ edge_agent/{cli.py,config.py,agent.py,capture.py,outbox.py,sender.py,device_auth.py,config_sync.py,simulator.py}
│  └─ tests/
├─ frontend/
│  ├─ package.json, vite.config.ts, tsconfig.json, tailwind.config.ts
│  └─ src/{main.tsx,App.tsx,routes/,api/,stores/,components/,features/{auth,admin,owner,devices,alerts,dataops},lib/,styles/,test/}
├─ infra/terraform/ (vpc.tf alb.tf asg.tf rds.tf sqs.tf sns.tf s3.tf cloudwatch.tf iam.tf variables.tf outputs.tf)
├─ infra/nginx/default.conf
├─ scripts/{seed_dev_data.py, simulate_glass_break.sh, create_admin.py}
└─ docs/{api.md, runbook.md, test-plan.md}
```

### 2.3 Docker Compose services (Phase 0)
`postgres:16` (db `smarthome`), `mongo:7`, `localstack` (services: s3,sqs,sns), `backend` (uvicorn, reload), `model-worker`, `sweepers`, `frontend` (vite dev). `localstack-init` script creates: S3 bucket `smarthome-clips` (SSE-AES256, block public access), SQS queues `inference-events` (+ DLQ `inference-events-dlq`, `maxReceiveCount=3`, visibility timeout 120 s, long-poll 20 s), SNS topic prefix `house-` (topics created per house on house creation: `house-{id}`).

### 2.4 Environment variables (`.env.example`)
```
ENV=dev
DATABASE_URL=postgresql+psycopg://smart:smart@postgres:5432/smarthome
MONGO_URL=mongodb://mongo:27017
MONGO_DB=smarthome
AWS_REGION=us-west-2
AWS_ENDPOINT_URL=http://localstack:4566        # empty in prod
S3_BUCKET=smarthome-clips
SQS_QUEUE_URL=...inference-events
SQS_DLQ_URL=...inference-events-dlq
SNS_TOPIC_PREFIX=house-
JWT_SECRET=change-me
JWT_ALG=HS256
ACCESS_TOKEN_MIN=30
REFRESH_TOKEN_DAYS=7
DEVICE_TOKEN_MIN=15
MAX_CLIP_MB=25
SIGNED_URL_TTL_SEC=300
OFFLINE_AFTER_MIN=10
CMD_EXPIRE_MIN=60
DUP_WINDOW_SEC=60
ESCALATE_AFTER_MIN=5
DEFAULT_THRESHOLD=0.80
SNS_RETRY_SECONDS=5,15,45
CLASSIFIER=mock                               # mock | model
INTERNAL_API_ENABLED=true
INTERNAL_API_KEY=dev-internal
CORS_ORIGINS=http://localhost:5173
TELEMETRY_TTL_DAYS=30
```

---

## 3. Component boundaries and interfaces (do not violate)

| Consumer | Provider | Interface |
|---|---|---|
| Dashboard | IoT Manager | REST `/api/houses`, `/api/rooms`, `/api/devices*` |
| Dashboard | Alert Tracking | REST `/api/alerts*`, `/api/stats/*`, `/api/notification-prefs`, WS `/ws/alerts` |
| Dashboard | Auth | REST `/api/auth/*` |
| IoT + Alert + Ingest + Auth | Persistence | Python repository classes only |
| Edge agent | IoT Manager | `/api/auth/device-token`, `/api/devices/{id}/heartbeat`, `/api/devices/{id}/command-ack` |
| Edge agent | Ingest | `POST /api/ingest/events` |
| Model worker | Persistence | SQS consume, `ClipStore.get_bytes`, `EventRepository` |
| Model worker | Alert Tracking | `PolicyEngine.handle(inference_result)` (in-process) |

Add `backend/tests/unit/test_import_rules.py` using `import-linter` or an AST scan: modules outside `app/persistence` must not import `sqlalchemy`, `pymongo`, or `boto3` (except `app/persistence/**`, `app/notifications/sns.py` for SNS publish, and `alembic/`).

---

## 4. Data layer specification (Component 4 — build first)

### 4.1 PostgreSQL schema (Alembic migration `0001_initial`)
Types: `serial`/`bigint` identity PKs, `timestamptz` for times, `CHECK` constraints for enums (or PG enums).

```sql
users(user_id PK, email UNIQUE NOT NULL, password_hash NOT NULL, full_name, phone,
      role CHECK in ('owner','admin') NOT NULL, must_reset bool DEFAULT false, created_at)
houses(house_id PK, address_line, city, state, postal_code, latitude numeric, longitude numeric,
       timezone NOT NULL, status CHECK in ('active','disabled') DEFAULT 'active', created_at,
       UNIQUE(address_line, postal_code))                       -- 409 duplicate
user_houses(user_id FK, house_id FK, relation CHECK in ('owner','family','caregiver'),
            PRIMARY KEY(user_id, house_id))                      -- index (user_id, house_id)
residents(resident_id PK, house_id FK, full_name, birth_year, care_notes)
rooms(room_id PK, house_id FK, room_type CHECK in ('kitchen','living','bedroom','bath','other'),
      label NOT NULL, UNIQUE(house_id, label))                   -- 409 duplicate label
devices(device_id PK, room_id FK, house_id FK, device_type CHECK in ('audio','camera'),
        serial_no UNIQUE NOT NULL, label, status CHECK in ('enabled','disabled') DEFAULT 'enabled',
        conn_state CHECK in ('online','offline') DEFAULT 'offline', wifi_rssi int, last_heartbeat timestamptz,
        threshold numeric(3,2) NULL CHECK (threshold BETWEEN 0.50 AND 0.99),
        api_key_hash text NOT NULL, api_key_prefix text, key_revoked_at timestamptz NULL,
        removed_at timestamptz NULL, config_version int DEFAULT 1, created_at)
device_commands(command_id PK, device_id FK, command CHECK in ('enable','disable','reboot'),
        status CHECK in ('pending','delivered','completed','failed','expired') DEFAULT 'pending',
        issued_by FK users, issued_at, delivered_at, completed_at, expires_at, result text)
events(event_id PK, device_id FK, house_id FK, s3_key, duration_sec numeric, captured_at timestamptz,
       received_at timestamptz DEFAULT now(), processing_state CHECK in ('queued','scored','failed') DEFAULT 'queued',
       retry_count int DEFAULT 0, last_published_at timestamptz, correlation_id text, decision text,
       UNIQUE(device_id, captured_at))
alerts(alert_id PK, event_id FK UNIQUE, house_id FK, room_id FK, device_id FK, resident_id FK NULL,
       alert_category CHECK in ('emergency','safety','security','resident','animal'), sound_type,
       confidence numeric(4,3), severity CHECK in ('critical','high','medium','low'),
       state CHECK in ('new','notified','acknowledged','escalated','resolved','false_positive') DEFAULT 'new',
       resolved_by FK users NULL, suppressed_count int DEFAULT 0, version int DEFAULT 1,
       created_at, updated_at, resolved_at)
alert_state_history(history_id PK, alert_id FK, from_state, to_state, actor_user_id FK NULL (NULL = system),
       note, changed_at)                                         -- append-only: REVOKE UPDATE/DELETE via trigger
alert_notifications(notification_id PK, alert_id FK, recipient_id FK users NULL, recipient_label,
       channel CHECK in ('email','sms'), status CHECK in ('pending','sent','failed'), attempts int DEFAULT 0,
       last_error, sent_at, UNIQUE(alert_id, recipient_id, channel))
notification_prefs(pref_id PK, user_id FK, house_id FK, alert_category, email bool, sms bool,
       min_severity CHECK in ('critical','high','medium','low'), UNIQUE(user_id, house_id, alert_category))
-- proposed additions
admin_read_audit(audit_id PK, actor_user_id FK, house_id, action text, resource text, ts, correlation_id)
retention_policy(id PK=1 singleton, clip_expire_days int DEFAULT 30, clip_ia_transition_days int NULL,
       telemetry_ttl_days int DEFAULT 30, updated_by FK, updated_at)
threshold_overrides(id PK, scope CHECK in ('global','house','device'), scope_id int NULL, sound_type text,
       threshold numeric(3,2), updated_by, updated_at, UNIQUE(scope, scope_id, sound_type))
backup_status(id PK, kind CHECK in ('rds_snapshot','mongo_dump'), taken_at, status, location)
```

**Indexes (from SDD):** `alerts(house_id, created_at DESC)`, `alerts(state, severity)`, `alerts(house_id, alert_category, created_at)`, `devices(house_id, conn_state)`, `devices(last_heartbeat)`, `events(processing_state, received_at)`, `user_houses(user_id, house_id)`. Add `alert_state_history(alert_id, changed_at)`, `device_commands(device_id, status)`.

A DB trigger on `alert_state_history` raises on UPDATE/DELETE. A trigger on `alerts` is **not** used; versioning is in code (`version` increments on each transition).

### 4.2 MongoDB
- `inference_logs`: as in SDD (event_id, house_id, device_id, s3_key, model{name,version,runtime_ms}, predictions[], features{}, policy{threshold,decision,alert_id}, correlation_id, created_at). Indexes: `{house_id:1, created_at:-1}`, `{event_id:1}` unique, `{"model.version":1}`. `policy.decision` ∈ `alert_created | below_threshold | duplicate_suppressed | unknown_label`.
- `sensor_telemetry`: `{device_id, house_id, reading_type, payload{wifi_rssi,uptime_sec,buffer_depth}, processed, ts}`; indexes `{device_id:1, ts:-1}`, TTL on `ts` = 30 days.
- Create indexes in `persistence/mongo/client.py::ensure_indexes()` called at app startup.

### 4.3 S3 `ClipStore`
- Key: `clips/{house_id}/{yyyy}/{mm}/{dd}/evt-{event_id}.wav|mp4` (use `captured_at` date).
- `put(house_id, event_id, bytes, content_type, captured_at) -> key` with `ServerSideEncryption='AES256'`.
- `signed_url(key, ttl=SIGNED_URL_TTL_SEC) -> str`, `get_bytes(key)`, `delete(key)`.
- Bucket: private, public access blocked, bucket policy denies non-TLS. Lifecycle rules are applied by `RetentionJob` from `retention_policy` (D1).

### 4.4 Repositories — required method signatures
```python
class BaseRepository:
    def apply_scope(self, stmt, claims: Claims, house_col): ...   # claims.role=='admin' -> record admin read audit, no filter
                                                                  # else filter house_col IN claims.house_ids; empty -> no rows
class DeviceRepository:   get(id, claims), list(filters, page, claims), create(...), update(...), find_by_serial, mark_offline_stale(cutoff)
class EventRepository:    create_if_new(device_id, captured_at, s3_key, house_id, duration, correlation_id)->(event, created),
                          find(device_id, captured_at), get(id), list_admin(state, house, age, page), mark_scored(id, decision),
                          list_stale_queued(older_than), increment_retry(id), set_failed(id)
class AlertRepository:    create_with_history_and_mark_event_scored(...), transition(alert_id, expected, next, actor, note)->Alert (single txn,
                          WHERE state = expected else raises StateConflict with current_state+last_actor), append_history, list(filters, page, claims),
                          get_detail(id, claims), find_recent(sound_type, room_id, within_sec), increment_suppressed(id), stats(...)
class InferenceLogRepository: write(doc)->id, query(filters, page)
class TelemetryRepository:    write_heartbeat(...), latest(device_id)
class NotificationRepository: create_pending(alert_id, recipients), mark_sent/failed, list_for_alert
class AuditRepository:        log_admin_read(...), query(house, actor, type, range, page)
class RetentionRepository:    get(), put(...)
```
Page contract: `?page=1&page_size=25` → `{items:[...], total, page, page_size}`; `page_size` max 100.

### 4.5 Ingest service (exact behavior — see section 5.4 pseudocode in the design doc)
Order: validate multipart (clip ≤ 25 MB else 413; WAV/MP4 only; `house_id`, `device_id`, `captured_at` required; `duration_sec` optional>0) → device JWT (`type=device`) → device exists, `status=enabled`, `device.house_id == token.house_id == form house_id` else 403 `scope_violation`/`device_disabled` + security log → `find(device_id, captured_at)` duplicate → 200 `{event_id, duplicate:true}` → allocate event id → `ClipStore.put` (failure → 503 `storage_unavailable`) → `create_if_new` (if not created: delete S3 key, return 200 duplicate) → publish SQS message (failure: log, keep `queued`, still return 202) → `202 {event_id, duplicate:false}`. SQS message body is exactly the JSON in SDD 4.2.2 (event_id, house_id, device_id, s3_key, captured_at, correlation_id).

### 4.6 Jobs
- **StuckEventSweeper** (every 60 s): events `queued` with `last_published_at IS NULL OR < now()-5min` → republish, `retry_count++`, if `retry_count > 5` → `failed`.
- **RetentionJob** (daily): apply `retention_policy` to S3 lifecycle (`put_bucket_lifecycle_configuration`), ensure Mongo TTL index matches `telemetry_ttl_days`, read RDS snapshot status (mock in dev) into `backup_status`.
- **Admin data APIs:** per SDD 4.2 table (`/api/admin/data/health`, `/api/admin/events`, `/api/admin/events/{id}/retry` (409 if already scored; sets `queued` and republishes), `/api/admin/inference-logs`, `/api/admin/audit`, `/api/admin/retention` GET/PUT with 400 on invalid range).
- Health endpoint returns `{postgres, mongo, s3, sqs:{visible, in_flight}, dlq:{visible}, backups:{rds_snapshot_age_h, mongo_dump_age_d}, unprocessed_events}`.


---

## 5. Auth service (shared) — specification

### 5.1 JWT claims
User token: `{sub: user_id, type:"user", role:"owner"|"admin", house_ids:[...], iat, exp, jti}`.
Device token: `{sub: device_id, type:"device", device_id, house_id, iat, exp(15 min)}`.
Dependencies in `core/deps.py`: `get_claims()` (401 on invalid/expired), `require_role("admin")`, `require_user()`, `require_device()`.

### 5.2 Endpoints
| Endpoint | Behavior |
|---|---|
| `POST /api/auth/signup` | email, password (≥10 chars), full_name, phone → 201 owner user. 409 on duplicate email. |
| `POST /api/auth/login` | email, password → `{access_token, expires_in, user:{id,name,role,house_ids}}` + sets `rt` cookie. 401 bad credentials, 429 after 5 failures/15 min per IP+email. bcrypt verify with constant-time dummy hash for unknown email. |
| `POST /api/auth/refresh` | reads cookie → new access token (rotates refresh token). 401 if invalid. |
| `POST /api/auth/logout` | clears cookie. |
| `GET /api/users/me`, `PUT /api/users/me` | profile (name, phone, email). |
| `POST /api/auth/device-token` | `{device_id, api_key}` → verify `sha256(api_key)==api_key_hash`, not revoked/removed → 200 `{access_token, expires_in:900}`; 401 `invalid_key`. Rate-limit per device. |

Role redirects on frontend: admin → `/admin`, owner → `/owner`.

---

## 6. IoT Device Manager (Component 2) — specification

### 6.1 Endpoints (all `/api/...`)
| Method/path | Who | Rules |
|---|---|---|
| `POST /rooms` | admin, owner (own house) | `{house_id, room_type, label}` → 201; 409 duplicate label in house; 403 scope. |
| `GET /rooms?house_id=` | both | scoped list. |
| `PATCH /rooms/{id}` | both | rename label/type. |
| `POST /devices` | admin, owner | `{room_id, device_type, serial_no, label}` → resolve house from room; serial unique else 409 `duplicate_serial`; generate API key `dk_` + `secrets.token_urlsafe(32)`; store sha256 + prefix; initial `conn_state=offline`; return device + `api_key` **once**. |
| `GET /devices` | both | filters `house_id, room_id, status, connectivity, page`; returns `conn_state, last_heartbeat, wifi_rssi`. Owner response omits `api_key_prefix`, `serial_no` stays (owner types it). |
| `PATCH /devices/{id}` | admin all fields; owner only `status` | `threshold` 0.50–0.99 admin only else 422; bump `config_version`; on `status` change also enqueue enable/disable command. |
| `DELETE /devices/{id}` | admin, owner | soft remove: `removed_at=now`, `key_revoked_at=now`; excluded from lists. |
| `POST /devices/{id}/rotate-key` | admin | new key shown once, old revoked. |
| `POST /devices/{id}/command` | admin, owner(enable/disable only) | `{command}` → 202 `{command_id}`; 409 `command_pending` if same pending command exists; expires after 60 min. |
| `POST /devices/{id}/heartbeat` | device JWT | body `{wifi_rssi:int, uptime_sec:int>=0, buffer_depth:int>=0, config_version:int}`; JWT `device_id` must equal path id else 403 `device_mismatch` + security log. Updates `last_heartbeat`, `wifi_rssi`, `conn_state=online`; writes telemetry; marks pending commands `delivered`; returns `{commands:[{command_id,command}], config:{capture_enabled, threshold, version}}` (config only if version changed or first call). |
| `POST /devices/{id}/command-ack` | device JWT | `{command_id, result}` → mark `completed`/`failed`. |
| `POST /houses/{id}/disable` & `/enable` | admin | cascades to all devices in one transaction; response lists counts; partial failure rolls back. |

### 6.2 Logic details
- `ConnectivitySweeper.run()` (every 60 s): enabled devices with `last_heartbeat < now-10min` → `conn_state=offline`. Return changed count. Publish a WebSocket `device.updated` event (extension) so the dashboard tile updates within 5 s of enable/disable (FR-4) — also publish on command issue/ack.
- Disabled devices: ingest rejects with `device_disabled`. `capture_enabled=false` in config.
- Command expiry: `CommandQueue` marks pending rows older than 60 min `expired` during heartbeat handling and the sweeper.
- Online rule: enabled AND heartbeat within 10 min. Disabled devices that still heartbeat show `online/disabled`.

### 6.3 Edge agent (`edge/`)
Modules and behavior:
- `config.py`: env/file config: `API_BASE`, `DEVICE_ID`, `API_KEY`, `HOUSE_ID`, `OUTBOX_DB=outbox.sqlite`, `CLIP_DIR`, `HEARTBEAT_SEC=60`, `SEND_CYCLE_SEC=5`, `BUFFER_CAP_GB=2`.
- `outbox.py`: SQLite table exactly as SDD 4.1.3 (`outbox(local_id, device_id, clip_path, captured_at, payload_json, state, attempts, last_error)`) + index. API: `enqueue`, `oldest_unsent(limit)`, `mark_sent` (delete local clip), `record_retry(item, backoff)` (store `next_attempt_at`), `discard`, `discard_unsent`, `quarantine`, prune oldest `sent` rows when buffer > cap.
- `device_auth.py`: exchange key for JWT, cache until 60 s before expiry, refresh on 401.
- `sender.py`: loop per pseudocode in component design 2.3: if capture disabled → pause + `discard_unsent`; for each of oldest 10 → upload; 200/202 mark_sent; `device_disabled` discard; 403 quarantine & stop; else retry with exponential backoff (max 300 s, jitter). Always send header `X-Correlation-Id` (generate `c-YYYYMMDD-<random>`).
- `config_sync.py`: apply heartbeat response (commands: enable/disable/reboot(=restart loop) ; config versions); ack commands.
- `capture.py`: real mic capture is optional; v1 implements `FileCapture`.
- `simulator.py`: `edge-agent simulate --wav glass_break.wav --every 30s --room living`; writes clips to outbox as if captured. Also `--burst N` for load tests and `--offline-for 120s` to test buffering.
- CLI (`typer`): `edge-agent run`, `edge-agent simulate`, `edge-agent status`.

---

## 7. Dashboard (Component 1) — specification

### 7.1 Core frontend modules (mirror class design 1.3)
- `stores/authStore.ts` (Zustand): `login`, `logout`, `refresh`, `user`, `role`, `houseIds`, token held only in memory.
- `api/apiClient.ts`: attaches `Authorization: Bearer`, `X-Correlation-Id` (uuid); normalizes errors to `{status, error, message, correlationId}`; on 401 performs **one coordinated refresh** (shared promise) then retries once; on 403 emits an "access denied" toast/page; on 409 `state_conflict` surfaces details.
- `api/alertSocket.ts`: states `disconnected → connecting → catching_up → live`, plus `backoff_polling` and `refreshing_token` (diagram 1.3). Bounded exponential backoff (1,2,4,8,16,30 s). After reconnect: REST catch-up `GET /api/alerts?updated_since=<last_seen_ts>`. Polling fallback every 30 s while not live. Subprotocol `["bearer", token]`.
- `stores/alertStore.ts`: `applyMessage(evt)` → ignore unknown types, ignore out-of-scope `house_id`, dedupe by `alert_id`, ignore same/older `version`, update list + stats tiles; bounded list (200).
- `features/alerts/alertActions.ts`: `changeAlert(alertId, nextState, note)` using `expected_state`; on 409 refetch alert, show "changed by {last_actor} at {time}", replace in store.
- `lib/exportService.ts`: `toCsv(filters, columns)` pages through `GET /api/alerts`, RFC4180 escaping, neutralize formula injection (prefix `'` for cells starting with `= + - @`).
- `components/DataView.tsx`: generic wrapper rendering **loading skeleton / empty with next action / error with retry + correlation id / stale with age** (FR-15, UI-04).
- `components/RouteGuard.tsx`: not signed in → `/login?return=...`; owner on `/admin/*` → redirect `/owner`; admin on `/owner/*` allowed only if `?house=` selected.
- `components/SeverityBadge.tsx`: color + icon + text (critical red, high amber, medium blue, low grey).

### 7.2 Screens (route → API)
| ID | Route | Contents | APIs |
|---|---|---|---|
| A1/H-login | `/login`, `/signup` | centered card; inline field errors; role redirect | auth |
| A2 | `/admin` | category tiles (clickable filters), filter rail (sound type, confidence range, category, severity, house search, date window, **Save view** stored per admin in `notification-prefs`-style `saved_views` table → add `GET/PUT /api/users/me/saved-views`), Leaflet map with severity pins (house lat/lng), synchronized list, new alerts flash once | alerts, stats, WS |
| A3 | `/admin/history` | full-width table; search by house ID/alert ID, date range, sort (timestamp, confidence, severity), filter rail, export CSV/PDF | alerts |
| A4 | `/admin/devices` | left forms: house registration (address, timezone, owner email), device registration (house, room type, device type, serial) with Add/Update/Disable/Enable/Remove; right: search by house/device ID, house tree with state/heartbeat/RSSI; disable-house confirm dialog with device count; one-time API key modal with copy | houses, rooms, devices |
| A5 | `/admin/alerts/:id` (side panel over list) | all fields, waveform+audio playback from signed URL, map thumbnail, recipient delivery table, state history, actions Acknowledge/Escalate/Resolve/Mark false with optional note; **Resend failed** | alerts detail, PATCH, resend |
| A6 | `/admin/false-alerts` | ranked table (sound type, false/total, rate, low-sample flag if <20), trend line chart, window selector, export; row click → A3 filtered; threshold editing inline | stats/false-alerts, admin/thresholds |
| A7 | `/admin/settings` | default map location, notification defaults, own activity table | users/me, audit |
| A8 | `/admin/fleet` | connectivity stats (online/offline/disabled counts), fleet table | devices, stats |
| D1–D5 | `/admin/data/health|events|inference|audit|retention` | see section 10 | admin/data APIs |
| H1 | `/owner` | greeting, house selector (if >1), status banner ("All clear" green or red alert card with sound label, room, time, buttons **This is fine** / **Call for help**), device tiles strip | alerts, devices |
| H2 | `/owner/devices` | simplified A4: add room, add device by serial, per-device capture toggle, no raw IDs | rooms, devices |
| H3 | `/owner/history` | friendly labels table ("Possible fall"), fewer filters | alerts |
| H4 | `/owner/alerts/:id` | what/when/where/clip/who notified/resolved by, **Dismiss**; never show confidence/threshold/model | alerts detail |
| H5 | `/owner/profile` | name, phone, email, per-category matrix (email/SMS checkbox + min severity) | users/me, notification-prefs |

Friendly label map in `lib/labels.ts`: `fall→"Possible fall"`, `smoke_fire_alarm→"Smoke alarm"`, `intruder→"Stranger at door"`, `glass_break→"Glass breaking"`, `loud_argument→"Loud argument"`, `gunshot→"Loud bang (possible gunshot)"`, `distress→"Someone may need help"`, `explosion→"Explosion sound"`, `unusual_inactivity→"Unusual quiet"`, `animal→"Animal sound"`.

### 7.3 UI standards (apply globally)
16 px base font; 44 px min touch targets; visible text with every severity color; accessible labels (`aria-*`); keyboard-navigable; Tailwind blue/teal palette; light theme; toasts for critical alerts (admin) and a banner (owner). Tokens only in memory. Never display raw IDs/model/confidence to owners. Demonstration data mode (`VITE_DEMO_MODE=true`) uses MSW fixtures (UI-06).

---

## 8. Alert Tracking & Monitoring (Component 3) — specification

### 8.1 Pipeline (`PolicyEngine.handle(result)`) — implement exactly
1. Load event; if `processing_state == "scored"` → return stored decision (idempotent redelivery).
2. `best = select_catalog_prediction(predictions)` = highest-confidence prediction whose label is in the catalog. None → log decision `unknown_label`, mark scored, return.
3. `threshold = ThresholdResolver.resolve(device_id, house_id, sound_type)`: device override → house override → global override → `DEFAULT_THRESHOLD` 0.80 (truth table from design 3.4).
4. `confidence < threshold` → write inference log `below_threshold`, mark event scored, return (no alert).
5. `DuplicateDetector.find_recent(sound_type, room_id, within=60s)` → if match: increment prior alert `suppressed_count`, log `duplicate_suppressed`, mark scored, return.
6. **One transaction:** create alert (state `new`), history row (`null→new`, actor system), mark event scored with decision.
7. Write Mongo inference log (`alert_created`, includes `alert_id`).
8. **After commit** publish `alert.created` over the WebSocket hub.
9. `RecipientResolver.resolve(alert)` → `NotificationDispatcher.dispatch` via SNS; if at least one delivery accepted → transition `new→notified` with history + publish `alert.updated`.
10. All recipients failed → alert stays `new`, eligible for resend.

### 8.2 Sound catalog (`catalog.py`)
| sound_type (label) | category | default severity |
|---|---|---|
| fall, distress, gunshot, explosion | emergency | critical (never downgraded) |
| smoke_fire_alarm, loud_argument | safety | high; → medium if confidence < 0.90 |
| intruder, glass_break | security | high; → medium if confidence < 0.90 |
| unusual_inactivity, unusual_room_pattern | resident | medium; → low if confidence < 0.90 |
| animal | animal | low |

`SeverityMapper.map(category, sound_type, confidence)` implements the table. Unit test every row at 0.89/0.90 boundaries.

### 8.3 Recipients & notifications
- `RecipientResolver`: for the alert's house, collect users via `user_houses`, join `notification_prefs` for the alert category; include a user/channel iff pref enabled for that channel and `alert.severity >= min_severity` (severity order critical>high>medium>low). If no prefs exist, defaults: owners get email+sms for critical/high. Also include house-level **security contact** for category `security`/`emergency` (store as notification_prefs rows of a seeded "security" user, or a `house_contacts` extension table — choose `users` with `role='owner'`/relation `caregiver`; keep simple).
- `NotificationDispatcher.dispatch`: create `alert_notifications` rows `pending`; publish to SNS topic `house-{id}` (email) / direct SMS publish by phone; on failure retry at **5, 15, 45 s** (`tenacity`, run in a background thread/task so the pipeline doesn't block >1s); record `attempts`, `status`, `last_error`; emit `alert.updated` when delivery table changes.
- `POST /api/alerts/{id}/resend` (admin): retries only `failed` rows.
- Emergency/911 is simulated: SNS to registered contacts only.

### 8.4 API (see section 4.2 of SDD; implement all)
`GET /api/alerts` (filters: `house_id, from, to, category, severity, state, sound_type, min_confidence, max_confidence, q (alert id), updated_since, page, page_size, sort`), `GET /api/alerts/{id}` (alert + history + deliveries + `clip_url` signed + resident name; owner response strips confidence/model), `PATCH /api/alerts/{id}/state`, `GET /api/alerts/export?format=csv|pdf`, `GET /api/stats/alerts`, `GET /api/stats/false-alerts`, `GET/PUT /api/notification-prefs`, `GET/PUT /api/admin/thresholds`, `POST /api/alerts/{id}/resend`, `WS /ws/alerts`, `POST /internal/inference-results`.

`PATCH` example: body `{to_state, expected_state, note?}`. Server: verify role + house scope → check transition allowed (422 `invalid_transition`) → `UPDATE ... WHERE state=expected_state` (0 rows → 409 `state_conflict` with `{current_state, last_actor, changed_at}`) → append history in same transaction → publish `alert.updated`. Returns updated alert.

### 8.5 Transition matrix
| From | Admin allowed | Owner/family allowed | System |
|---|---|---|---|
| new | notified(system only), acknowledged, escalated, false_positive | escalated ("Call for help"), false_positive ("This is fine") | → notified, → escalated (critical after 5 min) |
| notified | acknowledged, escalated, false_positive | escalated, false_positive | → escalated (critical after 5 min) |
| acknowledged | escalated, resolved, false_positive | none | none |
| escalated | resolved, false_positive | none | none |
| resolved / false_positive | none | none | terminal |

### 8.6 Escalation timer
`EscalationTimer.run()` (sweeper, every 30 s): critical alerts in `new`/`notified` older than `ESCALATE_AFTER_MIN` → transition `escalated` (actor NULL/system, note "auto-escalated"), re-dispatch to escalation contacts, publish `alert.updated`. Returns count.

### 8.7 Stats
- `/api/stats/alerts`: counts by severity/category/state and per-day trend for `from..to`, scoped.
- `/api/stats/false-alerts`: per sound_type `false_positive / total`, `sample_count`, `low_sample = total < 20`.

### 8.8 WebSocket hub (`ws.py` + `event_publisher.py`)
In-process `ConnectionManager` keyed by `house_id` and an `admin` group. Events: `{"type":"alert.created"|"alert.updated"|"device.updated","version":int,"house_id":int,"alert":{...}}` (owner payload sanitized). Validate JWT from subprotocol; close with 4401 on invalid. Heartbeat ping every 25 s. Because production has 2+ instances behind ALB, publish events through **Postgres `LISTEN/NOTIFY`** (channel `alert_events`) so every instance fans out locally. Implement with a background listener task.

---

## 9. ML / model worker

- `ml/classifier.py`: `class Classifier(Protocol): def classify(self, audio_bytes: bytes, meta: dict) -> list[Prediction]` where `Prediction(label:str, confidence:float)`; also returns `model_name`, `model_version`, `runtime_ms`, `features`.
- `MockClassifier`: if filename/metadata contains a catalog label → that label at 0.93, plus a distractor at 0.05; random mode with seed for load tests; env `MOCK_LABEL` override.
- `preprocess.py`: resample to 16 kHz mono (use `soundfile`/`librosa` if available), segment, compute `rms`, `peak_db`, `duration_sec` features.
- `workers/model_worker.py`: long-poll SQS (20 s, batch 1–5); for each: parse body, check event exists & not scored, `ClipStore.get_bytes`, classify, build result, call `PolicyEngine.handle`, delete the message on success; on exception leave message (SQS redrives 3× → DLQ) and set event `failed` when moved to DLQ (a small DLQ watcher in sweepers marks events `failed`). Graceful shutdown: SIGTERM finishes in-flight message. Emit CloudWatch metrics (`inference_latency_ms`).

---

## 10. Data Operations console (D1–D5) — frontend + API wiring
D1 health tiles (PostgreSQL/Mongo/S3 status, SQS & DLQ counts, refresh every 15 s); D2 event pipeline (state tabs queued/scored/failed, house filter, age filter, per-row Retry → `POST /api/admin/events/{id}/retry`, shows 409 as "already scored"); D3 inference explorer (model version, label, confidence range, date); D4 audit log (actor/house/date/action filters, export CSV); D5 retention & backup (edit `clip_expire_days`, `clip_ia_transition_days`, telemetry TTL with validation messages, snapshot history list). Admin only.

---

## 11. Phased build order with acceptance checks

Give Cursor one phase at a time. After each phase run `make test` (create a Makefile with `up`, `down`, `migrate`, `test`, `lint`, `seed`).

### Phase 0 — Scaffolding (½ day)
Tasks: repo layout (2.2), `pyproject.toml` (deps listed in 2.1), `docker-compose.yml`, LocalStack init script, `.env.example`, `Makefile`, GitHub Actions CI (lint + unit tests), `.cursor/rules/project.mdc` with section 0.
Accept: `docker compose up` starts all infra; `GET /healthz` returns 200; CI green.

### Phase 1 — Core + Persistence (Component 4 foundation)
Tasks: `core/*` (config, errors, correlation-id middleware, JSON logging, JWT utils, deps), Alembic migration 0001 (section 4.1), Mongo indexes, `ClipStore`, `QueuePublisher`, `BaseRepository.apply_scope`, all repositories (4.4), `scripts/seed_dev_data.py` (1 admin, 2 owners, 3 houses with rooms/devices, residents), import-linter test.
Accept: unit tests for scope filter (house A token cannot read house B → 403/empty), alert transition atomicity & conflict (`StateConflict`), `create_if_new` uniqueness; migrations up/down clean; admin read writes `admin_read_audit`.

### Phase 2 — Auth + Houses
Tasks: section 5 endpoints; `POST/GET /api/houses`, `GET /api/houses/{id}` (with rooms/devices), owner linking (D8), SNS topic creation per house, rate-limited login, role guards; create_admin script.
Accept: tests: signup/login/refresh/logout; 401/403/429; cross-house 403; house create 409 duplicate; JWT contains correct `house_ids`.

### Phase 3 — IoT Manager (cloud)
Tasks: section 6.1–6.2 services/endpoints, device-token, heartbeat, command queue + expiry, connectivity sweeper, house enable/disable cascade, `device.updated` events (stub hub until Phase 5).
Accept: tests for duplicate serial 409, heartbeat device mismatch 403, online/offline after 10 min (use freezegun), `command_pending` 409, threshold range 422, API key shown once and revocable (rotate → old key 401), disable-house rollback on partial failure.

### Phase 4 — Ingest + queue + stuck sweeper
Tasks: section 4.5, `POST /api/ingest/events`, `GET /api/events/{id}`, `StuckEventSweeper`, admin events/retry/health endpoints, retention endpoints + `RetentionJob`.
Accept: tests per business table 4.4: 400 invalid metadata, 413 >25 MB, 403 mismatch/disabled, 200 duplicate (no second S3 object), S3 failure → 503 nothing persisted, SQS failure → 202 + sweeper republish, admin retry 409 when scored. Load check: 50 clips/min for 2 min without loss.

### Phase 5 — Alert Tracking
Tasks: sections 8 and 9: catalog, resolver, severity mapper, duplicate detector, policy engine, dispatcher (LocalStack SNS), state service, recipient resolver, escalation timer, stats, notification prefs, thresholds admin API, WebSocket hub with Postgres LISTEN/NOTIFY, internal test adapter, `model_worker`, `MockClassifier`.
Accept: tests: threshold truth table (all 4 rows); severity boundaries; below-threshold → no alert but Mongo log; duplicate within 60 s suppressed, at 61 s creates new; redelivery of same event creates one alert; transition matrix (every allowed/forbidden cell → 200/422); 409 on stale `expected_state` with `current_state` & `last_actor`; SNS failure retries at 5/15/45 s (patch sleep) then `failed` and alert stays `new`; all-failed → resend works; critical alert auto-escalates at 5 min; false-alert stats low-sample flag at <20; WS test: client for house A never receives house B events; end-to-end with edge simulator: clip → alert in < 10 s p95 locally.

### Phase 6 — Edge agent
Tasks: section 6.3 + tests (outbox persistence across restart, backoff, disable discards unsent, 403 quarantine, offline replay ordering oldest-first).
Accept: `edge-agent simulate` against local stack produces an alert; killing the backend for 2 min then restoring replays all buffered clips exactly once (idempotent).

### Phase 7 — Frontend foundation
Tasks: Vite app, Tailwind, router, `apiClient`, `authStore`, `RouteGuard`, `DataView`, `SeverityBadge`, MSW handlers + demo mode, login/signup pages, layout shells (admin/owner), typed API client generated from FastAPI OpenAPI (`openapi-typescript`).
Accept: Vitest tests: 401→refresh→retry once, 403 message, route guard redirects (owner→/admin denied), DataView four states.

### Phase 8 — Admin screens
Tasks: A2 (map + live list + WS), A3, A4, A5, A6, A7, A8, `alertSocket`, `alertStore`, `alertActions`, CSV export.
Accept: Vitest: store dedupe/out-of-scope/older-version ignored; conflict flow shows last actor; socket state machine transitions & backoff; Playwright: sign in → register device → heartbeat appears → simulated glass-break appears without refresh → acknowledge with note → resolve.

### Phase 9 — Owner screens
Tasks: H1–H5, capture toggle, friendly labels, no confidence/IDs leaked (add test that scans owner API responses and rendered DOM for `confidence`).
Accept: Playwright: owner sees red card live, "This is fine" → false_positive; capture off → edge stops uploading within one heartbeat; admin view reflects it.

### Phase 10 — Data Operations console
Tasks: D1–D5 screens + CSV audit export.
Accept: dead-letter scenario: force 3 failures → DLQ>0 shown in D1, event failed in D2, retry returns it to queued then scored.

### Phase 11 — AWS deployment (Terraform) & observability
Tasks (SDD 4.3/3.1): VPC 10.0.0.0/16 two AZs (public 10.0.1/2, private app 10.0.11/12, private data 10.0.21/22); ALB (HTTPS, ACM, redirect 80→443, target groups `/api/*`, `/api/ingest/*`, `/`, health `/healthz` 15 s, least-outstanding-requests, stickiness off, WS upgrade); ASG API (t3.medium, min 2 max 6, CPU>60% or 1000 req/target/min); ASG model workers (min 1 max 8, SQS visible>100 for 2 min, lifecycle hook finish-in-flight); RDS PostgreSQL 16 (encrypted, Multi-AZ optional, daily snapshots) + read replica optional; MongoDB 7 on EC2 (private); S3 (SSE, versioning off, lifecycle from retention policy), VPC gateway endpoint for S3; SQS + DLQ; SNS; IAM instance roles (no keys); security groups exactly per SDD 3.1.1 table; SSM Session Manager, no SSH; CloudWatch alarms: API p95>500 ms 5 min, queue>500, DLQ>0, inference p95>3 s, alert-delivery failure>0 in 5 min, EC2 status check failed; billing alarm at 70%. Nginx config, systemd units, user-data scripts, deploy script that builds frontend and syncs static to Nginx.
Accept: two instances healthy in separate AZs; killing one instance keeps API available; scale-out observed under load test.

### Phase 12 — Hardening, load test, docs
Tasks: negative tenancy test suite (token for house A → house B endpoints all 403, including WS, signed clip URL, stats, exports); k6/Locust tests: 100 concurrent dashboard sessions with list p95 < 500 ms (NFR-2/3), 50 clips/min sustained and a burst absorbed by SQS (NFR-4), alert latency p95 < 10 s (NFR-1) — export CloudWatch screenshots; TLS checks; backups verification (NFR-12); README, `docs/api.md` from OpenAPI, runbook, test plan.
Accept: all NFR evidence gathered; demo script runs (section 13).

---

## 12. Cross-cutting acceptance checklist (maps to requirements)
- FR-1..FR-3: house/room/device CRUD with validation. FR-4: enable/disable reflected ≤5 s (WS `device.updated`). FR-5: offline after 10 min. FR-6/7: S3 store + SQS non-blocking. FR-8/9: classification + threshold alert. FR-10/11/12: severity, recipients, state machine, per-recipient delivery. FR-13: all filters incl. confidence band. FR-14–18: dashboard, four data states, scope, live push, CSV/PDF. FR-19: Mongo inference logs with model version + features. FR-20: edge outbox.
- NFR-1 latency <10 s p95; NFR-2 <500 ms; NFR-3 100 sessions; NFR-4 50 clips/min; NFR-5 2 AZs; NFR-6 TLS ≥1.2; NFR-7 SSE-S3 + RDS encryption; NFR-8 tenant filter + negative tests; NFR-9 audit of every transition (actor, ts, prior state); NFR-10 retention per D1; NFR-11 per-device disable; NFR-12 daily RDS snapshots, weekly Mongo dump (cron `mongodump` → S3, record in `backup_status`).

## 13. Demo script (build `scripts/demo.md`)
1. Admin logs in. 2. Registers house + room + device; copies API key. 3. Starts `edge-agent` with that key; first heartbeat flips device to online. 4. `simulate_glass_break.sh` → alert appears live in admin map and owner banner (no refresh), SMS/email delivery rows visible. 5. Admin acknowledges with note → owner view updates. 6. Admin resolves. 7. Owner disables capture → edge stops uploading. 8. Kill network for 2 min → buffer depth rises → restore → replay. 9. D1/D2 retry flow after forced DLQ. 10. Show CloudWatch dashboards and ASG scale-out under load.

## 14. Test inventory to create (names for Cursor)
Backend unit: `test_scope_filter`, `test_threshold_resolver`, `test_severity_mapper`, `test_duplicate_detector`, `test_policy_engine`, `test_alert_state_machine`, `test_recipient_resolver`, `test_dispatcher_retry`, `test_ingest_service`, `test_heartbeat_service`, `test_connectivity_sweeper`, `test_command_queue`, `test_stuck_event_sweeper`, `test_retention_validation`, `test_auth_flows`, `test_import_rules`. Integration (docker): `test_end_to_end_pipeline`, `test_ws_scope_isolation`, `test_dlq_flow`. Edge: `test_outbox`, `test_sender_backoff`, `test_replay_after_outage`. Frontend: `apiClient.test`, `alertStore.test`, `alertSocket.test`, `RouteGuard.test`, `DataView.test`, `exportService.test`. E2E (Playwright): admin flow, owner flow, conflict flow, data-ops retry flow.

## 15. Suggested Cursor prompts (copy per phase)
- *"Implement Phase 1 from PLAN.md. Create the SQLAlchemy models and the Alembic migration exactly per section 4.1, the Mongo index setup per 4.2, ClipStore per 4.3, and the repository classes per 4.4. Write the tests listed in Phase 1 acceptance. Do not add endpoints yet."*
- *"Implement Phase 5 (Alert Tracking) from PLAN.md sections 8 and 9. Follow the pipeline order in 8.1 literally and the transition matrix in 8.5. Include unit tests for every row of the tables."*
- *"Implement Phase 8 (admin screens). Use the generated OpenAPI TypeScript client, TanStack Query for fetching, DataView for all four states, and follow the screen table in 7.2."*

## 16. Open items to confirm with the team (log in `docs/decisions.md`)
Retention vs IA (D1 default chosen); real ML model interface (D11); recipient/escalation contact model (8.3); whether PDF export is needed for the demo (D12); MQTT scope (D2). Anything changed here must update this file first.
