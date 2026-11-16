# Smart Home Platform API

The authoritative contract is served at runtime from FastAPI (`/openapi.json`) and mirrored in [`docs/openapi.json`](openapi.json). The generated frontend types are in `frontend/src/api/generated.ts`; regenerate them with `npm run generate:api` after changing the contract.

## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/signup` | Creates owner; 409 duplicate email |
| POST | `/api/auth/login` | Access token + `rt` cookie; 429 after 5 fails/15 min |
| POST | `/api/auth/refresh` | Rotates refresh cookie |
| POST | `/api/auth/logout` | Clears cookie |
| GET/PUT | `/api/users/me` | Profile |
| GET/PUT | `/api/users/me/saved-views` | Admin saved filters |
| GET/PUT | `/api/users/me/dashboard-settings` | Per-user map and notification defaults |

## Houses / ingest / data ops (Tanisha)

| Method | Path | Notes |
|---|---|---|
| POST/GET | `/api/houses` | Admin create; scoped list |
| GET | `/api/houses/{id}` | Rooms + devices |
| POST | `/api/ingest/events` | Device JWT multipart clip upload |
| GET | `/api/events/{id}` | Event status |
| GET | `/api/admin/data/health` | Dependency health tiles |
| GET | `/api/admin/events` | Pipeline list |
| POST | `/api/admin/events/{id}/retry` | 409 if scored |
| GET | `/api/admin/inference-logs` | Mongo explorer |
| GET | `/api/admin/audit` | `?export=csv` supported |
| GET/PUT | `/api/admin/retention` | D1 validation on IA vs expire |

## Alerts and monitoring (Vritika)

All user alert routes require a bearer user token and enforce house scope. Admin
responses may include confidence; owner, family, and caregiver responses do not.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/alerts` | Scoped list with category, severity, state, sound, date, confidence, and search filters |
| GET | `/api/alerts/{id}` | Alert detail with state history and notification deliveries |
| PATCH | `/api/alerts/{id}/state` | Optimistic transition; stale writes return 409 |
| POST | `/api/alerts/{id}/resend` | Admin-only failed-notification resend |
| GET | `/api/alerts/export` | Scoped CSV or PDF export |
| GET | `/api/stats/alerts` | Counts by severity, category, and state |
| GET | `/api/stats/false-alerts` | False-positive rate with low-sample flag |
| GET/PUT | `/api/notification-prefs` | Owner notification matrix for a house |
| GET/PUT | `/api/admin/thresholds` | Admin threshold overrides |
| POST | `/internal/inference-results` | Internal-key protected policy adapter |
| WebSocket | `/ws/alerts?house_id={id}` | JWT bearer subprotocol with house isolation |

## IoT devices

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/api/rooms` | Scoped room inventory and creation |
| PATCH | `/api/rooms/{id}` | Update a room label or type |
| GET/POST | `/api/devices` | Inventory and one-time API-key registration |
| PATCH/DELETE | `/api/devices/{id}` | Update, disable, or soft-remove a device |
| POST | `/api/devices/{id}/rotate-key` | Revoke the old key and return a new one once |
| POST | `/api/devices/{id}/heartbeat` | Device JWT heartbeat, telemetry, commands, and config |
| POST | `/api/devices/{id}/command` | Queue a device command with conflict protection |
| POST | `/api/houses/{id}/disable` | Transactional house/device disable cascade |
| POST | `/api/houses/{id}/enable` | Re-enable a house and its devices |
| POST | `/api/auth/device-token` | Short-lived device JWT bound to device and house |

IoT, alerts, and WebSocket routes are owned by Sakshat and Vritika — see PLAN.md sections 6–8.

## Backup and retention behavior

`RetentionJob` applies the S3 lifecycle policy, ensures Mongo TTL indexes, checks the latest automated RDS snapshot, and runs `mongodump --archive --gzip` before uploading the archive under the configured S3 backup prefix. A missing `RDS_INSTANCE_IDENTIFIER`, disabled Mongo dump, missing `mongodump`, or failed AWS operation is recorded as `not_configured`, `disabled`, or `failed`; it is never reported as a successful backup.
