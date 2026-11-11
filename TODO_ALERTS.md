# Vritika — AI Alert Tracking TODO

Branch: `vritika/alert-mvp`

This checklist tracks the work assigned to Component 3 in `PLAN.md` and
`WORK_SPLIT.md`. Check items only when the implementation and its focused tests
are committed.

## MVP milestone

- [x] Create alert sound catalog and accepted prediction selection — `fdc1795`
- [x] Implement severity mapping and confidence boundaries — `fdc1795`
- [x] Implement device → house → global → default threshold resolution — `fdc1795`
- [x] Add duplicate-detector boundary — `fdc1795`
- [x] Implement role-aware alert state machine — `fdc1795`
- [x] Add deterministic mock classifier and preprocessing boundary — `fdc1795`
- [x] Implement the initial policy engine — `fdc1795`
- [x] Add unit tests for catalog, severity, thresholds, and state rules — `fdc1795`
- [x] Add scoped alert list/detail/state API — `e838e6b`
- [x] Hide confidence from owner alert responses — `e838e6b`
- [x] Register alert routes in the FastAPI application — `e838e6b`
- [x] Add alert API contract tests — `e838e6b`
- [x] Replace the idle model worker with the mock-classifier pipeline — `1072fd6`
- [x] Add policy-engine integration tests with fake repositories — `d15d0db`
- [x] Add an end-to-end queued-event → classifier → alert flow — `d15d0db`

## Remaining assigned backend work

- [x] Add Mongo inference-log decisions for every policy outcome — `d15d0db`
- [x] Add recipient resolution from notification preferences — `8ccd836`
- [x] Add SNS notification dispatch — `8ccd836`
- [x] Add notification retry delays: 5, 15, and 45 seconds — `8ccd836`
- [x] Add notification resend endpoint — `8ccd836`
- [x] Add automatic escalation timer for critical alerts — `8ccd836`
- [x] Add complete alert filters, including date and confidence ranges — `0266d05`
- [x] Add alert history and delivery details to the detail endpoint — `0266d05`
- [x] Add CSV export — `0266d05`
- [x] Add PDF export — `0266d05`
- [x] Add alert statistics endpoint — `0266d05`
- [x] Add false-alert statistics and low-sample flag — `0266d05`
- [x] Add notification-preferences endpoints — `0266d05`
- [x] Add admin threshold-management endpoints — `0266d05`
- [x] Add guarded internal inference-results adapter — `0266d05`
- [x] Add WebSocket alert hub with JWT subprotocol authentication — `0266d05`
- [x] Add WebSocket house-isolation tests — `0266d05`

## Frontend work

- [x] Add admin alert-detail side panel — `7c929d6`
- [x] Add notification delivery table and state-history timeline — `7c929d6`
- [x] Add false-alert analytics screen — `7c929d6`
- [x] Add owner alert-detail screen — `7c929d6`
- [x] Add owner profile and notification matrix — `7c929d6`
- [x] Verify owners never receive confidence or model details in the UI — `7c929d6`

## Security and integration validation

- [x] Test every alert endpoint across two house scopes — `bc67ea5`
- [x] Test admin, owner, family, and caregiver permissions — `04197e5`
- [x] Test stale state conflicts and invalid transitions through HTTP — `bc67ea5`
- [x] Test critical-alert auto-escalation — `8ccd836`
- [ ] Run backend unit tests and lint — Python/pytest/ruff unavailable locally
- [ ] Run Docker/LocalStack end-to-end alert flow — Docker daemon unavailable locally
- [x] Update API documentation and OpenAPI output — `bc67ea5`
- [x] Test duplicate inference redelivery creates one alert — `04197e5` (policy coverage)
- [x] Test below-threshold inference creates no alert — `04197e5` (policy coverage)

## Deferred model work

- [ ] Integrate the real supplied ML model through `ModelClassifier`
