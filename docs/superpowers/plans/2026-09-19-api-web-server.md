# API/Web Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Build a runnable FastAPI Web server whose `/api/v1` surface matches the frozen M1.7 OpenAPI contract and exposes existing domain services through explicit adapters.

**Architecture:** `fip.api` owns application creation, request context, unified envelopes, error mapping, and contract-facing routers. A small in-memory operation registry provides deterministic asynchronous submission/polling until the persistent job adapter is wired; domain adapters remain separate so route schemas cannot leak ORM objects. Unavailable records return contract-shaped 404/409/422 errors rather than fabricated success data.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, pytest/httpx, PyYAML.

**Spec:** `docs/superpowers/specs/2026-09-16-plan4-contract-freeze-design.md`, `frontend/openapi/m17.yaml`, `docs/10-api/06-m17-frontend-contracts.md`.

## Global Constraints

- Every public route is under `/api/v1/`; no unfreezed route is added.
- Responses use the frozen `{data, meta}` success envelope and `{error, meta}` error envelope.
- Long-running optimization and backtest commands return `202` with `operation_id` and are polled through `/api/v1/operations/{operation_id}`.
- Server authorization remains authoritative; UI visibility is not authorization.
- IDs and query semantics follow `frontend/openapi/m17.yaml`; no custom aliases are invented.
- Tests must run with the repository's Python 3.12 toolchain and preserve existing checks.

### Task 1: Add dependency and app-factory contract tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.lock`
- Create: `tests/api/test_app_contract.py`

**Interfaces:**
- Produces `fip.api.app.create_app()` returning a FastAPI application.
- Produces a test that loads `frontend/openapi/m17.yaml`, compares every path/method, and checks `/api/v1/session` and `/api/v1/operations/{operation_id}` envelope shapes.

- [ ] Write the failing contract test and run `pytest tests/api/test_app_contract.py -q`; it must fail because `fip.api` does not exist.
- [ ] Add FastAPI and Uvicorn runtime dependencies plus the locked versions required by the environment.
- [ ] Re-run the focused test and keep the failure at the missing app/routes boundary before implementation.

### Task 2: Implement application core and unified contracts

**Files:**
- Create: `src/fip/api/__init__.py`
- Create: `src/fip/api/app.py`
- Create: `src/fip/api/contracts.py`
- Create: `src/fip/api/errors.py`
- Create: `src/fip/api/context.py`
- Modify: `tests/api/test_app_contract.py`

**Interfaces:**
- `create_app() -> FastAPI` mounts the frozen router set and emits OpenAPI metadata.
- `success(data, *, meta=None, status_code=200)` returns the standard envelope.
- `ApiError(status_code, code, message, details=None)` serializes to the frozen error envelope.
- Every response receives an `X-Request-ID` (propagated from the request when supplied).

- [ ] Add tests for success/error envelope, request ID propagation, 404 mapping, and OpenAPI route parity.
- [ ] Implement the minimal middleware, Pydantic envelope models, exception handlers, and app factory.
- [ ] Run `pytest tests/api/test_app_contract.py -q` and verify green.

### Task 3: Implement session, read routes, and deterministic not-found behavior

**Files:**
- Create: `src/fip/api/routers/reads.py`
- Create: `src/fip/api/repositories.py`
- Create: `tests/api/test_read_routes.py`

**Interfaces:**
- `GET /api/v1/session` returns authenticated principal capability data from request context.
- Frozen fund, universe, portfolio, decision, optimization, and backtest read routes return typed envelopes.
- Repository adapters expose `get_*`/`list_*` methods and raise `NotFoundError` when no record is available.

- [ ] Add tests for session capability response, pagination defaults, query validation, and a contract-shaped 404.
- [ ] Implement read route schemas/adapters with empty collection responses where the contract requires them.
- [ ] Run focused read tests and existing unit tests.

### Task 4: Implement asynchronous submission and review routes

**Files:**
- Create: `src/fip/api/operations.py`
- Create: `src/fip/api/routers/commands.py`
- Create: `tests/api/test_command_routes.py`

**Interfaces:**
- `OperationRegistry.submit(kind, resource_id, idempotency_key) -> OperationRecord` is idempotent.
- Optimization and backtest run commands return `202` with `operation_id`; polling returns `RUNNING`, `COMPLETED`, `FAILED`, or `BLOCKED` plus `result_ref` when available.
- Decision review enforces `APPROVED`, `REJECTED`, `OVERRIDDEN`; override requires `reason` and unauthorized review returns `403`.

- [ ] Add tests for 202 responses, repeated `Idempotency-Key`, operation polling, review authorization, and override validation.
- [ ] Implement the registry, command routers, and explicit status transitions.
- [ ] Run focused command tests and ensure no command returns a fabricated completed result.

### Task 5: Add startup, contract verification, and documentation

**Files:**
- Modify: `Makefile`
- Create: `tests/api/test_openapi_parity.py`
- Modify: `README.md`
- Modify: `frontend/README.md`

**Interfaces:**
- `make api-dev` starts `uvicorn fip.api.app:create_app --factory`.
- `make api-check` validates route/method parity and runs API tests.

- [ ] Add a parity test that fails on missing/extra path or method and mismatched operation IDs.
- [ ] Add Make targets and startup documentation, including `FIP_DATABASE_URL` and auth-development behavior.
- [ ] Run `make api-check`, `LC_ALL=en_US.UTF-8 make check`, and the frontend check.
- [ ] Review the diff for contract drift before declaring the server ready.
