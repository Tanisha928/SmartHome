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

IoT, alerts, and WebSocket routes are owned by Sakshat and Vritika — see PLAN.md sections 6–8.
