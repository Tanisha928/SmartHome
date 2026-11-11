# Smart Home Platform API (stub)

Authoritative contract is served at runtime from FastAPI (`/openapi.json`) and mirrored in `docs/openapi.json`.

## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/signup` | Creates owner; 409 duplicate email |
| POST | `/api/auth/login` | Access token + `rt` cookie; 429 after 5 fails/15 min |
| POST | `/api/auth/refresh` | Rotates refresh cookie |
| POST | `/api/auth/logout` | Clears cookie |
| GET/PUT | `/api/users/me` | Profile |
| GET/PUT | `/api/users/me/saved-views` | Admin saved filters |

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

IoT, alerts, and WebSocket routes are owned by Sakshat and Vritika — see PLAN.md sections 6–8.
