# Plan-5 API/Web Server Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Connect the local FastAPI server to PostgreSQL and the existing domain services so the frozen M1.7 frontend contract works against real data and persistent asynchronous operations.

**Architecture:** Keep `fip.api` as a thin contract-facing boundary. Route handlers validate request/query data and delegate to explicit repository/application adapters; domain services and SQLAlchemy repositories own business semantics. Persistent operations use the existing `governance.calculation_job` model and `JobSubmitter`, while API-specific result references and audit data remain in application adapters. Local development continues through `make api-dev`; containerization and deployment are out of scope.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL/psycopg, Alembic, pytest/httpx, React/Vite frontend.

**Spec:** `docs/superpowers/specs/2026-09-16-plan4-contract-freeze-design.md`, `docs/10-api/06-m17-frontend-contracts.md`, `frontend/openapi/m17.yaml`, `docs/10-api/01-api-overview.md`, `docs/10-api/02-fund-api.md`, `docs/10-api/04-portfolio-api.md`, `docs/10-api/05-backtest-api.md`.

## Global Constraints

- Preserve every frozen `/api/v1` path, method, operation ID, status code, and response envelope.
- Do not add Docker, container orchestration, deployment manifests, or cloud-specific infrastructure.
- Local startup remains `make api-dev`; database selection remains controlled by `FIP_DATABASE_URL`.
- All point-in-time reads must carry the requested `as_of_date` and version metadata; never silently use current data for historical requests.
- Empty collections are successful responses; missing individual resources are contract-shaped `404` responses.
- Long-running optimization and backtest commands remain asynchronous with `202`, `operation_id`, and operation polling.
- Authorization is enforced by the server even when the frontend hides controls.
- Every task must add or update tests before implementation and run its focused test before moving on.

## File Map

- `src/fip/api/`: HTTP boundary, request context, contract models, routes, repositories, and operation adapters.
- `src/fip/platform/jobs/`: existing persistent job model and submitter; only targeted additions are allowed.
- `src/fip/services/`: existing domain services and repository adapters; API integration must call these instead of duplicating business logic.
- `tests/api/`: HTTP contract and application-service tests.
- `tests/integration/`: PostgreSQL-backed API integration tests.
- `db/migrations/versions/`: only migrations required for persistent API operation/result/audit state.
- `Makefile`, `README.md`, `frontend/README.md`: local startup and verification commands.

### Task 1: Freeze the database-backed API seams

**Files:**
- Create: `tests/api/test_repository_contracts.py`
- Create: `src/fip/api/repositories.py` (extend the existing adapter)
- Create: `src/fip/api/dependencies.py`

**Interfaces:**
- `ApiRepositories` exposes `funds`, `universes`, `portfolios`, `decisions`, and `backtests` adapters.
- `get_api_repositories(request) -> ApiRepositories` supplies one request-scoped session/adapter set.
- Each detail adapter returns a typed mapping or raises `NotFoundError`; list adapters return deterministic, sorted rows.

- [ ] Write failing tests proving repositories are request-scoped, list ordering is deterministic, and missing IDs map to `NotFoundError`.
- [ ] Implement dependency construction from `FIP_DATABASE_URL` using the existing SQLAlchemy metadata/session conventions.
- [ ] Run `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_repository_contracts.py -q` and verify green.

### Task 2: Implement real fund and universe reads

**Files:**
- Modify: `src/fip/api/routers/reads.py`
- Create: `src/fip/api/fund_queries.py`
- Create: `src/fip/api/universe_queries.py`
- Create: `tests/api/test_fund_routes.py`
- Create: `tests/api/test_universe_routes.py`

**Interfaces:**
- Fund list accepts the frozen filters, page/page_size, sort/order, and `as_of_date`.
- Fund detail, NAV series, evaluations, and scores delegate to existing fund/data/factor repositories.
- Universe list/detail returns selected and rejected members plus exclusion conditions.

- [ ] Add failing HTTP tests with seeded repository fakes for filters, pagination, PIT metadata, and deterministic tie-break ordering.
- [ ] Implement query adapters without duplicating calculation or eligibility rules.
- [ ] Add explicit 404 and invalid-date/enum tests, then run the focused route tests.

### Task 3: Implement real portfolio, optimization, and decision reads

**Files:**
- Modify: `src/fip/api/routers/reads.py`
- Create: `src/fip/api/portfolio_queries.py`
- Create: `tests/api/test_portfolio_routes.py`

**Interfaces:**
- Portfolio list returns only resources visible to the current principal and uses the frozen pagination metadata.
- Portfolio detail includes holdings/allocations/constraints data required by the frontend contract.
- Optimization and decision reads expose business statuses independently from technical operation status.

- [ ] Add failing tests for resource visibility, portfolio pagination, optimization result references, and decision snapshots.
- [ ] Implement adapters over existing portfolio/decision data services and preserve their domain status values.
- [ ] Run focused tests and the complete API suite.

### Task 4: Persist asynchronous operations and idempotency

**Files:**
- Modify: `src/fip/api/operations.py`
- Modify: `src/fip/api/routers/commands.py`
- Modify: `src/fip/api/routers/operations.py`
- Modify: `src/fip/platform/jobs/submitter.py`
- Create: `tests/api/test_persistent_operations.py`

**Interfaces:**
- `PersistentOperationService.submit(kind, resource_id, idempotency_key, principal) -> OperationRecord` delegates to `JobSubmitter`.
- `get(operation_id)` reads `governance.calculation_job` and returns `RUNNING`, `COMPLETED`, `BLOCKED`, `FAILED`, or `CANCELLED` with `failure`/`result_ref`.
- Repeated idempotency keys return the original operation and resource IDs across process restarts.

- [ ] Add failing PostgreSQL integration tests for duplicate submissions, persisted polling, and failure/blocking state mapping.
- [ ] Implement the service using the existing job model and transaction boundaries; do not retain the in-memory registry for production code.
- [ ] Run API unit tests plus the PostgreSQL integration test against a dedicated test database.

### Task 5: Implement optimization, backtest, and review commands

**Files:**
- Modify: `src/fip/api/routers/commands.py`
- Create: `src/fip/api/command_services.py`
- Create: `tests/api/test_command_services.py`
- Create: `tests/integration/test_api_commands.py`

**Interfaces:**
- Optimization submission creates a persistent optimization request and returns `202` with `operation_id` and `optimization_id`.
- Backtest creation returns `201`; configuration validation returns the frozen validation result; run submission returns `202`.
- Decision review validates `APPROVED`, `REJECTED`, and `OVERRIDDEN`; `OVERRIDDEN` requires a reason and writes an audit record.

- [ ] Add failing tests for command payload validation, authorization, idempotency, and audit fields.
- [ ] Implement application services that invoke existing optimization/backtest/decision domain services.
- [ ] Run integration tests with PostgreSQL fixtures and verify no command reports business completion merely because the HTTP request succeeded.

### Task 6: Replace placeholder response dictionaries with strict models

**Files:**
- Modify: `src/fip/api/contracts.py`
- Create: `src/fip/api/schemas.py`
- Modify: `src/fip/api/routers/reads.py`
- Modify: `src/fip/api/routers/commands.py`
- Create: `tests/api/test_response_models.py`

**Interfaces:**
- Every frozen response has a Pydantic response model matching `frontend/openapi/m17.yaml` required fields and enums.
- Metric fields preserve `null`, `status`, and `reason`; percentages remain decimal fractions.
- Validation failures use the frozen error envelope and status codes.

- [ ] Add failing model-validation tests for required metadata, unknown enum rejection at the server boundary, and nullable metric triples.
- [ ] Implement response models and attach them to FastAPI routes.
- [ ] Run OpenAPI generation/parity tests and focused response tests.

### Task 7: Add authentication boundary and audit policy

**Files:**
- Modify: `src/fip/api/context.py`
- Create: `src/fip/api/auth.py`
- Create: `src/fip/api/audit.py`
- Create: `tests/api/test_authz.py`
- Create: `tests/integration/test_api_audit.py`

**Interfaces:**
- `Principal` is produced by an injectable authentication dependency; the development header path is explicit and disabled when `FIP_ENV=production`.
- Resource access checks are applied to portfolio and decision routes.
- Review actions write actor, action, reason, timestamp, and request ID to the governance audit store.

- [ ] Add failing tests for unauthenticated `401`, unauthorized `403`, visible-resource filtering, and review audit rows.
- [ ] Implement the injectable auth boundary and audit writer without changing frontend route paths.
- [ ] Run focused auth tests and PostgreSQL audit integration tests.

### Task 8: Real frontend integration and local acceptance

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `frontend/README.md`
- Create: `tests/integration/test_api_frontend_fixture.py`

**Interfaces:**
- `make api-dev` starts the real app using local environment configuration.
- `make api-check` runs contract, API, and repository tests; a separate integration target runs PostgreSQL tests.
- Frontend requests remain same-origin `/api/v1` and work against the local server without MSW.

- [ ] Add a failing smoke test that starts the local app and verifies session, fund list, portfolio list, operation polling, and error rendering paths.
- [ ] Implement only local command/documentation changes; do not add Docker or deployment files.
- [ ] Run API tests, PostgreSQL integration tests, `LC_ALL=en_US.UTF-8 make check`, and `make frontend-check`.

## Final Acceptance Checklist

- [ ] `make api-dev` starts locally without Docker.
- [ ] `GET /openapi.json` matches `frontend/openapi/m17.yaml`.
- [ ] PostgreSQL-backed fund, universe, portfolio, decision, and backtest flows pass integration tests.
- [ ] Async operations survive process restart and preserve idempotency.
- [ ] Authentication, resource visibility, decision review authorization, and audit records are tested.
- [ ] Frontend pages work against the local API without MSW fixtures.
- [ ] `LC_ALL=en_US.UTF-8 make check`, API integration checks, and `make frontend-check` pass.
- [ ] No Docker, deployment, or cloud infrastructure changes were introduced.
