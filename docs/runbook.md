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
- Production Terraform provisions the encrypted RDS instance, private data subnet group, S3 clip/backup bucket, and SQS queues. MongoDB must be supplied on a private data-tier host or managed service and configured through `MONGO_URL`.
