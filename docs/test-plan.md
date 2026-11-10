# Test plan (Component 4 focus)

## Unit (Tanisha)

- `test_healthz`, `test_security`, `test_ratelimit`, `test_correlation_middleware`
- `test_scope_filter`, `test_event_repo`, `test_import_rules`
- `test_auth_flows`, `test_houses_api`
- `test_ingest_service` (413/403/200 duplicate/503/202 SQS fail)
- `test_stuck_event_sweeper`, `test_retention_validation`
- `test_ingest_load_smoke` (50 clips simulated)

## Integration (shared)

- docker compose: migrate + seed + ingest → SQS message
- admin retry after forced failure / DLQ
- tenant isolation negative suite (with Vritika, Phase 12)

## Frontend

- Data ops screens mount under `/admin/data/*` once Mithil adds routes
- Vitest for D1 refresh / D2 409 messaging when shell is ready
