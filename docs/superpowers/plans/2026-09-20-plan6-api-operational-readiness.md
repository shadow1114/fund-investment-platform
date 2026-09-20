# Plan-6 API Operational Readiness and Local Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen Plan-5 FastAPI/PostgreSQL service operationally safe for local continuous use by adding a replaceable identity boundary, explicit resource authorization, durable asynchronous execution, health/readiness diagnostics, bounded request behavior, and frontend live-mode resilience without changing the frozen M1.7 business API.

**Architecture:** Keep `fip.api` as a thin HTTP boundary and move runtime concerns into small platform adapters. A verified-principal provider feeds a policy service; a PostgreSQL-backed job runner claims `CalculationJob` rows and invokes registered application handlers; health, metrics, and structured request events observe those boundaries without changing business payloads. The frontend keeps same-origin `/api/v1` as its default, while an explicit development base URL and typed error/polling behavior make local live integration testable.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL/psycopg, Alembic, pytest/httpx, React/Vite/TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/plans/2026-09-19-plan5-api-server-integration.md`, `docs/10-api/06-m17-frontend-contracts.md`, `docs/10-api/01-api-overview.md`, `frontend/openapi/m17.yaml`, and the deferred-items list in `frontend/README.md`.

## Global Constraints

- Preserve every frozen `/api/v1` path, method, operation ID, status code, response envelope, field name, enum value, nullability rule, and PIT/version metadata rule.
- Keep local startup command-based: `make api-dev`, `make worker-dev`, and `FIP_DATABASE_URL`; do not add Docker, deployment manifests, cloud services, or container orchestration.
- Never treat a development header as production authentication; production requests without a verified principal fail closed with `401`.
- Resource authorization is server-side and must run before reads or commands; a hidden frontend control is never an authorization decision.
- Operation technical status stays separate from optimization, decision, and backtest business status. A submitted job is not a completed calculation.
- PostgreSQL is the source of truth for jobs, leases, audit events, and health checks; in-memory state is test-only.
- New operational endpoints use `/health/*` and `/metrics` and must not alter the frozen `/api/v1` contract.
- Every task adds a failing test before implementation and leaves an independently runnable focused test command.

## File Map

- `src/fip/settings.py`: typed runtime settings for authentication mode, worker lease, request limits, and observability switches.
- `src/fip/api/auth.py`, `src/fip/api/context.py`: verified identity provider boundary and request principal context.
- `src/fip/api/policy.py`: resource and operation authorization decisions shared by reads and commands.
- `src/fip/platform/jobs/`: claim/lease/state-transition primitives and handler registry for durable local workers.
- `src/fip/api/health.py`, `src/fip/api/observability.py`: liveness/readiness, request event, and metrics adapters.
- `src/fip/api/errors.py`, `src/fip/api/app.py`: stable error-code registry, rate-limit handling, and exception mapping.
- `frontend/src/api/`: configurable API base URL, typed error normalization, and operation polling behavior.
- `tests/api/`, `tests/integration/`, `tests/unit/`, `frontend/src/**/*.test.*`: focused contract and local PostgreSQL/frontend tests.
- `Makefile`, `README.md`, `frontend/README.md`: local worker startup, health checks, and acceptance commands.
- `.superpowers/sdd/2026-09-20-plan6-api-operational-readiness/progress.md`: execution ledger and final freeze record created when implementation starts.

### Task 1: Freeze runtime settings and local process boundaries

**Files:**
- Modify: `src/fip/settings.py`
- Modify: `src/fip/api/app.py`
- Modify: `Makefile`
- Modify: `README.md`
- Create: `tests/unit/test_runtime_settings.py`
- Create: `tests/api/test_process_boundaries.py`

**Interfaces:**
- `Settings` exposes `environment: Literal["development", "test", "production"]` loaded from the existing `FIP_ENV` variable, `database_url`, `worker_lease_seconds: int`, `worker_poll_seconds: float`, `max_page_size: int`, `rate_limit_per_minute: int`, and `require_verified_principal: bool`.
- `create_app(settings_override: Settings | None = None, *, persistent_operations: bool = False, strict_contracts: bool = False) -> FastAPI` uses the override only in tests and preserves the existing default app.
- `make worker-dev` runs `PYTHONPATH=src .venv/bin/python -m fip.platform.jobs.worker`; `make api-health-check` runs `curl --fail http://127.0.0.1:8000/health/ready`; neither command starts a second HTTP server.

- [ ] **Step 1: Write the failing settings and command tests**

```python
def test_production_defaults_require_verified_identity(monkeypatch):
    monkeypatch.setenv("FIP_ENV", "production")
    monkeypatch.delenv("FIP_REQUIRE_VERIFIED_PRINCIPAL", raising=False)
    settings = Settings()
    assert settings.require_verified_principal is True


def test_worker_dev_command_is_local_and_not_containerized():
    makefile = Path("Makefile").read_text()
    assert "worker-dev:" in makefile
    assert "fip.platform.jobs.worker" in makefile
    assert "docker" not in makefile.split("worker-dev:", 1)[1].split("\n\n", 1)[0]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/unit/test_runtime_settings.py tests/api/test_process_boundaries.py -q`

Expected: FAIL because the new settings fields, app override, and `worker-dev` target do not exist.

- [ ] **Step 3: Implement the smallest settings/process boundary**

Add the typed fields with validation (`worker_lease_seconds >= 5`, `worker_poll_seconds > 0`, `1 <= max_page_size <= 500`, `rate_limit_per_minute > 0`), pass an optional settings object into app state, and document the three local commands `api-dev`, `worker-dev`, and `api-health-check`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/unit/test_runtime_settings.py tests/api/test_process_boundaries.py -q`

Expected: PASS with no change to the frozen `/api/v1` route list.

- [ ] **Step 5: Commit**

```bash
git add src/fip/settings.py src/fip/api/app.py Makefile README.md tests/unit/test_runtime_settings.py tests/api/test_process_boundaries.py
git commit -m "feat: define local api and worker runtime boundaries"
```

### Task 2: Replace the header-only identity seam with verified-principal and policy adapters

**Files:**
- Modify: `src/fip/api/auth.py`
- Modify: `src/fip/api/context.py`
- Create: `src/fip/api/policy.py`
- Modify: `src/fip/api/routers/reads.py`
- Modify: `src/fip/api/routers/commands.py`
- Create: `tests/api/test_identity_boundary.py`
- Create: `tests/api/test_resource_policy.py`
- Create: `tests/integration/test_api_policy_postgres.py`

**Interfaces:**
- `VerifiedPrincipalProvider.resolve(request: Request) -> Principal | None` is the replaceable production identity boundary; the development header provider is selected only when `environment == "development"` and `require_verified_principal` is false.
- `ResourcePolicy.can_read(principal: Principal, resource_type: str, resource_id: str, session: Session) -> bool` and `ResourcePolicy.can_write(...) -> bool` return decisions without raising for ordinary invisibility.
- `require_read_access(...)` and `require_write_access(...)` raise the existing `AuthenticationError`/`ForbiddenError` and are called by both route families before repository access or mutation.

- [ ] **Step 1: Write failing identity and policy tests**

```python
def test_production_rejects_development_headers(monkeypatch):
    monkeypatch.setenv("FIP_ENV", "production")
    request = make_request(headers={"X-User-ID": "USR-1", "X-Roles": "admin"})
    with pytest.raises(AuthenticationError):
        resolve_principal(request)


def test_portfolio_policy_hides_unowned_resource(db_session):
    principal = Principal(user_id="USR-2", roles=("Researcher",), can_review_decisions=False)
    assert ResourcePolicy().can_read(principal, "portfolio", "P-OWNER-1", db_session) is False
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_identity_boundary.py tests/api/test_resource_policy.py -q`

Expected: FAIL because production identity resolution is currently coupled to environment/header parsing and authorization rules are duplicated inside routes.

- [ ] **Step 3: Implement the provider and policy boundary**

Keep the existing `Principal` shape and frozen session response. Move portfolio/decision ownership checks into `ResourcePolicy`, inject the provider through FastAPI dependency overrides, and make production fail closed when no verified provider has supplied a principal. Do not select a concrete external OAuth/JWT vendor in this task; the provider interface is the integration seam.

- [ ] **Step 4: Run API and PostgreSQL policy tests**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_identity_boundary.py tests/api/test_resource_policy.py tests/api/test_authz.py -q` and `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/integration/test_api_policy_postgres.py -q -m integration`.

Expected: development tests retain their explicit header behavior, production requests return `401`, and unowned resources return `403` or an empty authorized list as required by the existing contract.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/auth.py src/fip/api/context.py src/fip/api/policy.py src/fip/api/routers/reads.py src/fip/api/routers/commands.py tests/api tests/integration/test_api_policy_postgres.py
git commit -m "feat: centralize verified identity and resource policy"
```

### Task 3: Add durable job claiming, leases, and explicit handler execution

**Files:**
- Modify: `src/fip/platform/jobs/models.py`
- Modify: `src/fip/platform/jobs/submitter.py`
- Create: `src/fip/platform/jobs/executor.py`
- Create: `src/fip/platform/jobs/worker.py`
- Create: `db/migrations/versions/0032_calculation_job_leases.py`
- Modify: `src/fip/api/operations.py`
- Create: `tests/unit/test_job_executor.py`
- Create: `tests/integration/test_job_worker_postgres.py`

**Interfaces:**
- `JobContext` is a frozen dataclass containing `job: CalculationJob`, `session: Session`, `worker_id: str`, and `now: datetime`.
- `JobOutcome` is a tagged value with constructors `completed(result_ref: str | None = None)`, `blocked(code: str, message: str)`, and `failed(code: str, message: str)`.
- `JobExecutor.register(job_type: str, handler: Callable[[JobContext], JobOutcome]) -> None` registers one handler per job type; duplicate registrations raise `ValueError`.
- `JobExecutor.claim_one(session: Session, worker_id: str, now: datetime) -> CalculationJob | None` atomically claims the oldest eligible `RUNNING` job and records `claimed_by`, `lease_expires_at`, and `updated_at`.
- `JobExecutor.execute_one(session: Session, worker_id: str, now: datetime) -> JobOutcome | None` runs a registered handler and persists `COMPLETED`, `BLOCKED`, `FAILED`, or `CANCELLED` with error code/detail and progress.
- A handler may not return a business status as a technical job status; business statuses remain in the optimization/backtest/decision records.

- [ ] **Step 1: Write failing executor and lease tests**

```python
def test_failed_handler_is_persisted_as_failed_not_completed(db_session):
    executor = JobExecutor({"backtest": lambda _: JobOutcome.failed("ENGINE_ERROR", "boom")})
    job = seed_job(db_session, job_type="backtest", status="RUNNING")
    executor.execute_one(db_session, "worker-a", datetime.now(UTC))
    db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.error_code == "ENGINE_ERROR"


def test_expired_lease_can_be_reclaimed(db_session):
    job = seed_job(db_session, status="RUNNING", claimed_by="dead-worker", lease_expires_at=past())
    claimed = JobExecutor({}).claim_one(db_session, "worker-b", datetime.now(UTC))
    assert claimed is not None and claimed.execution_id == job.execution_id
    assert claimed.claimed_by == "worker-b"
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/unit/test_job_executor.py -q`

Expected: FAIL because the job table has no lease columns and no executor/worker module exists.

- [ ] **Step 3: Add the migration and executor**

Add nullable `claimed_by`, `lease_expires_at`, and `last_error_at` columns plus an index over `(status, lease_expires_at, created_at)`. Use a PostgreSQL transaction with `SELECT ... FOR UPDATE SKIP LOCKED` so two local workers cannot claim the same row. Register optimization and backtest application handlers as explicit adapters; if a handler is unavailable, persist `FAILED` with `HANDLER_UNAVAILABLE` instead of reporting `COMPLETED`.

- [ ] **Step 4: Add the local worker loop and run integration tests**

Implement `python -m fip.platform.jobs.worker --once` and a polling loop that sleeps `settings.worker_poll_seconds`, renews leases before expiry, and exits cleanly on SIGTERM. Run `alembic upgrade head` before the PostgreSQL test and verify duplicate claims, lease recovery, terminal mapping, and operation polling.

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/unit/test_job_executor.py -q` and `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/integration/test_job_worker_postgres.py tests/api/test_persistent_operations.py -q -m integration`.

- [ ] **Step 5: Commit**

```bash
git add src/fip/platform/jobs src/fip/api/operations.py db/migrations/versions/0032_calculation_job_leases.py tests/unit/test_job_executor.py tests/integration/test_job_worker_postgres.py
git commit -m "feat: add durable job leases and local worker execution"
```

### Task 4: Add liveness, readiness, structured request events, and metrics

**Files:**
- Create: `src/fip/api/health.py`
- Create: `src/fip/api/observability.py`
- Modify: `src/fip/api/app.py`
- Modify: `Makefile`
- Modify: `README.md`
- Create: `tests/api/test_health_endpoints.py`
- Create: `tests/api/test_observability.py`

**Interfaces:**
- `GET /health/live` returns `{"status": "ok"}` without touching PostgreSQL.
- `GET /health/ready` returns `200` only when PostgreSQL connectivity and Alembic head are available; otherwise it returns `503` with a stable error envelope outside `/api/v1`.
- `GET /metrics` returns deterministic text counters `fip_http_requests_total`, `fip_http_errors_total`, `fip_job_status_total`, and `fip_job_queue_depth`.
- `RequestEventSink.emit(event: RequestEvent) -> None` records request ID, route, method, status code, duration milliseconds, and principal ID; the default local sink writes one JSON object per line to the application logger.

- [ ] **Step 1: Write failing health and observability tests**

```python
def test_liveness_does_not_require_database():
    app = create_app(settings_override=offline_settings())
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    app = create_app(settings_override=offline_settings())
    monkeypatch.setattr("fip.api.health.database_ready", lambda *_: False)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_health_endpoints.py tests/api/test_observability.py -q`

Expected: FAIL because the operational routes, event sink, and metrics registry do not exist.

- [ ] **Step 3: Implement the endpoints and middleware sink**

Mount the three operational routes without `/api/v1`, reuse the request ID generated by existing middleware, and keep metric labels bounded to route templates and known status classes. Readiness must issue a short-lived `SELECT 1` and compare the current Alembic revision with the database head; it must not run migrations automatically.

- [ ] **Step 4: Verify local commands and full API tests**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_health_endpoints.py tests/api/test_observability.py tests/api/test_app_contract.py -q` and `make api-dev` in a separate terminal, then `curl -fsS http://127.0.0.1:8000/health/live`.

Expected: liveness works before PostgreSQL is available, readiness reports the dependency state, and no `/api/v1` OpenAPI operation changes.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/health.py src/fip/api/observability.py src/fip/api/app.py Makefile README.md tests/api/test_health_endpoints.py tests/api/test_observability.py
git commit -m "feat: add api health readiness and local observability"
```

### Task 5: Stabilize error taxonomy, page-size limits, and local rate limiting

**Files:**
- Modify: `src/fip/api/errors.py`
- Modify: `src/fip/api/app.py`
- Modify: `src/fip/api/routers/reads.py`
- Modify: `src/fip/api/contracts.py`
- Create: `src/fip/api/limits.py`
- Create: `tests/api/test_error_taxonomy.py`
- Create: `tests/api/test_request_limits.py`

**Interfaces:**
- `ApiError.code` values used by the M1.7 server are registered in `ERROR_CODES` with HTTP status and retryability: `VALIDATION_ERROR`, `AUTHENTICATION_REQUIRED`, `FORBIDDEN`, `RESOURCE_NOT_FOUND`, `CONFLICT`, `BUSINESS_RULE_VIOLATION`, `SERVICE_UNAVAILABLE`, and `RATE_LIMITED`.
- `PageRequest(page: int, page_size: int)` rejects `page < 1` and `page_size` outside `1..settings.max_page_size`, returning the existing validation envelope.
- `LocalRateLimiter.allow(principal_key: str, route_key: str, now: float) -> RateLimitDecision` is process-local and deterministic for development/tests; a rejected request returns `429` and `Retry-After` without changing business payloads.

- [ ] **Step 1: Write failing taxonomy and limit tests**

```python
def test_page_size_above_configured_max_is_validation_error(client):
    response = client.get("/api/v1/funds?page_size=501")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rate_limit_is_429_with_retry_after(client, limiter):
    client.app.state.rate_limiter = limiter.with_limit(1)
    client.get("/api/v1/funds", headers={"X-User-ID": "USR-1"})
    response = client.get("/api/v1/funds", headers={"X-User-ID": "USR-1"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["error"]["code"] == "RATE_LIMITED"
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_error_taxonomy.py tests/api/test_request_limits.py -q`

Expected: FAIL because page-size validation is route-specific and there is no stable error registry or limiter.

- [ ] **Step 3: Implement bounded validation and limiter**

Centralize the error registry and exception-to-envelope mapping, apply the configured page limit to every paginated read, and install the limiter as a dependency after authentication but before repository access. Keep limiter state replaceable so a later shared store can be added without changing handlers; do not claim the process-local limiter is a multi-instance quota.

- [ ] **Step 4: Run API and parity checks**

Run: `LC_ALL=en_US.UTF-8 make api-check` and `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_openapi_parity.py tests/api/test_error_taxonomy.py tests/api/test_request_limits.py -q`.

Expected: all frozen operation IDs and response schemas remain unchanged; only documented HTTP headers and operational error behavior are added.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/errors.py src/fip/api/app.py src/fip/api/routers/reads.py src/fip/api/contracts.py src/fip/api/limits.py tests/api/test_error_taxonomy.py tests/api/test_request_limits.py
git commit -m "feat: bound api errors pagination and local rate limits"
```

### Task 6: Make the frontend resilient in live local mode

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/errors.ts`
- Modify: `frontend/src/api/operations.ts`
- Modify: `frontend/src/pages/PortfolioPage.tsx`
- Modify: `frontend/src/pages/BacktestPage.tsx`
- Modify: `frontend/src/pages/FundResearchPage.tsx`
- Modify: `frontend/README.md`
- Create: `frontend/src/api/liveMode.test.ts`
- Create: `tests/integration/test_api_frontend_live.py`

**Interfaces:**
- `apiBaseUrl(): string` returns `import.meta.env.VITE_API_BASE_URL` when non-empty, otherwise `window.location.origin` with the existing same-origin `/api/v1` paths.
- `ApiError` contains `status`, `code`, `message`, `requestId`, and `retryAfterSeconds`; JSON parsing never turns a non-2xx response into an empty list.
- `pollOperation(operationId: string, options: { signal?: AbortSignal; intervalMs?: number; maxAttempts?: number }): Promise<OperationModel>` stops on `COMPLETED`, `BLOCKED`, `FAILED`, or `CANCELLED`, and throws the typed error on timeout/abort.

- [ ] **Step 1: Write failing frontend tests**

```typescript
it("uses VITE_API_BASE_URL only when configured", () => {
  expect(apiBaseUrl({ VITE_API_BASE_URL: "http://127.0.0.1:8000" })).toBe(
    "http://127.0.0.1:8000",
  )
  expect(apiBaseUrl({ VITE_API_BASE_URL: "" })).toBe(window.location.origin)
})

it("does not convert a 403 response into an empty collection", async () => {
  server.use(http.get("*/api/v1/funds", () => HttpResponse.json(errorEnvelope("FORBIDDEN"), { status: 403 })))
  await expect(listFunds()).rejects.toMatchObject({ status: 403, code: "FORBIDDEN" })
})
```

- [ ] **Step 2: Run the focused frontend tests to verify they fail**

Run: `cd frontend && npm test -- --run src/api/liveMode.test.ts`

Expected: FAIL because the generated client currently always uses relative paths and the page hooks do not expose typed API errors or bounded polling.

- [ ] **Step 3: Implement base URL, error normalization, and polling**

Wrap the generated Orval client rather than editing generated files, preserve the default same-origin behavior, surface `X-Request-ID` and `Retry-After`, and add abortable polling with a finite default attempt count. Update page states so `401`, `403`, `429`, `503`, and terminal operation failures render distinct actionable messages.

- [ ] **Step 4: Run frontend and real-server smoke tests**

Run: `cd frontend && npm test -- --run src/api/liveMode.test.ts` and `npm run check`; then run `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/integration/test_api_frontend_live.py -q -m integration` against `make api-dev` with PostgreSQL.

Expected: default same-origin pages continue to pass existing tests, a configured local API URL works, and non-2xx responses remain visible to the user.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api frontend/src/pages frontend/README.md frontend/src/api/liveMode.test.ts tests/integration/test_api_frontend_live.py
git commit -m "feat: harden frontend live api mode and operation polling"
```

### Task 7: Run end-to-end acceptance and freeze Plan-6

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `frontend/README.md`
- Create: `tests/integration/test_plan6_acceptance.py`
- Create: `.superpowers/sdd/2026-09-20-plan6-api-operational-readiness/progress.md`

**Interfaces:**
- `make plan6-check` runs Python unit/API checks, PostgreSQL migrations and worker tests, local health checks, and `make frontend-check` without Docker.
- `tests/integration/test_plan6_acceptance.py` verifies the single local flow: readiness → authenticated session → authorized fund/portfolio read → idempotent async submission → worker terminal state → typed frontend-visible error.
- The ledger records commit IDs, exact commands, database target, known warnings, and the freeze decision; it does not claim deployment readiness.

- [ ] **Step 1: Write the failing acceptance test and command target**

```python
def test_plan6_local_flow(api_client, worker, seeded_database):
    assert api_client.get("/health/ready").status_code == 200
    submitted = api_client.post("/api/v1/backtests", json=seeded_database.backtest_payload)
    operation = api_client.post(
        f"/api/v1/backtests/{submitted.json()['data']['backtest_id']}/runs",
        headers={"Idempotency-Key": "plan6-run-1"},
    )
    worker.run_once()
    polled = api_client.get(f"/api/v1/operations/{operation.json()['data']['operation_id']}")
    assert polled.json()["data"]["status"] in {"COMPLETED", "FAILED", "BLOCKED"}
```

- [ ] **Step 2: Run the acceptance test to identify missing wiring**

Run: `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/integration/test_plan6_acceptance.py -q -m integration`

Expected: FAIL only until the preceding runtime, policy, worker, health, limits, and frontend tasks are wired into the local process.

- [ ] **Step 3: Add the aggregate local command and documentation**

Make `plan6-check` run `make check`, `make api-check`, `make test-api-integration`, the Plan-6 integration test, and `make frontend-check` in that order. Document PostgreSQL prerequisites, `FIP_*` settings, `make api-dev`, `make worker-dev`, `curl /health/ready`, and the explicit fact that this plan does not deploy or containerize the service.

- [ ] **Step 4: Run the complete acceptance matrix**

Run:

```bash
alembic -x db=test upgrade head
LC_ALL=en_US.UTF-8 make plan6-check
```

Expected: Python checks, API contract/parity checks, PostgreSQL worker/policy checks, local FastAPI health/readiness, frontend format/lint/test/typecheck/build/Playwright checks, and the aggregate acceptance test all pass. Record any non-blocking existing frontend warnings separately.

- [ ] **Step 5: Freeze the plan**

Write the final ledger with the exact acceptance output, migration revision, verified local startup commands, remaining out-of-scope items (external authentication provider, external execution-system callbacks, report export, and shared multi-instance rate-limit storage), and the final commit ID. Commit:

```bash
git add Makefile README.md frontend/README.md tests/integration/test_plan6_acceptance.py .superpowers/sdd/2026-09-20-plan6-api-operational-readiness/progress.md
git commit -m "docs: freeze plan6 local operational readiness"
```

## Final Acceptance Checklist

- [ ] `make api-dev` and `make worker-dev` run locally with PostgreSQL and no container runtime.
- [ ] Production-mode requests cannot authenticate through `X-User-ID`/`X-Roles`; the provider seam is injectable for the eventual standard HTTP identity middleware.
- [ ] Portfolio, decision, optimization, and backtest access decisions are centralized and covered by PostgreSQL-backed tests.
- [ ] Two workers cannot claim the same job; expired leases are reclaimable; unavailable handlers never produce false `COMPLETED` status.
- [ ] `/health/live`, `/health/ready`, request events, and bounded metrics are available without changing `/api/v1`.
- [ ] Error codes, page limits, `429`/`Retry-After`, and request IDs are deterministic and covered by API tests.
- [ ] Frontend live mode supports same-origin and explicit `VITE_API_BASE_URL`, typed non-2xx errors, and abortable bounded operation polling.
- [ ] `LC_ALL=en_US.UTF-8 make plan6-check` passes against PostgreSQL; frontend and API checks remain green.
- [ ] No Docker, deployment, cloud infrastructure, report-export, or external execution callback implementation is included.
