# SDD ledger — plan: docs/superpowers/plans/2026-09-20-plan6-api-operational-readiness.md

## Execution

- Task 1: complete — runtime settings, local worker/API command boundaries, and focused tests.
- Task 2: complete — verified-principal seam, centralized resource policy, and PostgreSQL visibility test.
- Task 3: complete — calculation-job lease columns, `SKIP LOCKED` claim, terminal outcome mapping, and local worker module.
- Task 4: complete — liveness/readiness, request event metrics, request IDs, and health tests.
- Task 5: complete — stable error-code registry, page-size guard, and process-local rate limiter.
- Task 6: complete — Orval fetch mutator, configurable `VITE_API_BASE_URL`, typed response errors, and bounded operation polling.

## Freeze

## Acceptance

- `make check`: 614 Python unit/fitness/integration tests passed; mypy reported no issues in 125 source files.
- `make api-check`: 58 API tests passed.
- PostgreSQL API/worker/policy/Plan-6 acceptance: 4 integration tests passed.
- `make frontend-check`: 106 Vitest tests, production build, and 10 Playwright tests passed. Existing generated-schema, React Router, ECharts, and bundle-size warnings remain non-blocking.
- Database migration head: `0032_calculation_job_leases`.

Plan-6 frozen on 2026-09-20. The plan does not include deployment, containerization, external identity-provider selection, external execution callbacks, report export, or shared multi-instance quota storage.
