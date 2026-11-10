# Operations runbook (draft)

## Local stack

```bash
cp .env.example .env
make up
make migrate
make seed
curl -sf localhost:8000/healthz
```

## Common tasks

- **Create admin:** `python scripts/create_admin.py admin@example.com 'long-password'`
- **Replay stuck events:** sweepers loop every 60s; or `POST /api/admin/events/{id}/retry`
- **Retention:** `PUT /api/admin/retention` then optional `POST /api/admin/retention/run`
- **DLQ:** inspect LocalStack queue `inference-events-dlq`; D1 shows visible count

## Gaps for teammates

- Connectivity sweeper and escalation timer hooks are wired in `app/workers/sweepers.py` but implementations live with Sakshat/Vritika.
- Production Terraform data tier stubs are under `infra/terraform/` — complete with Sakshat (T17/S18).
