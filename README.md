# Intelligent Cloud Platform for Smart Homes

Group 9 modular monolith: FastAPI backend, React dashboard, edge agent, LocalStack AWS services.

## Quick start

```bash
cp .env.example .env
make up
# API: http://localhost:8000/healthz
# UI:  http://localhost:5173
```

See `PLAN.md` for architecture and phased acceptance checks. See `WORK_SPLIT.md` for component ownership.

## Ownership

| Member | Component |
|---|---|
| Mithil Devisetty | System Dashboard |
| Sakshat Patil | Home IoT Device Manager |
| Vritika Malhotra | AI Alert Tracking & Monitoring |
| Tanisha Dave | System Database Management |

## Commands

- `make up` / `make down` — Docker Compose stack
- `make migrate` — Alembic upgrade
- `make test` — unit tests
- `make seed` — seed admin/owners/houses
- `make lint` — ruff + mypy
