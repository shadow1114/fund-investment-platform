# Plan-7 Nested Response Contract Modeling and Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete and freeze the typed nested response contracts for every Plan-5/6 API domain—fund detail, NAV, evaluation, score, universe, portfolio, optimization, decision, and backtest—so the Python API, frozen OpenAPI document, generated frontend client, PostgreSQL acceptance fixtures, and recursive validation rules describe the same payloads.

**Architecture:** Treat `frontend/openapi/m17.yaml` as the external contract source of truth and mirror its component graph with strict Pydantic v2 models in `src/fip/api/schemas.py`. Route handlers select an endpoint-specific payload model through a central operation registry; envelopes remain separate from domain payloads, and technical operation status remains separate from business status. The frontend consumes the checked-in OpenAPI-generated types rather than hand-written duplicates.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL/psycopg, Alembic, pytest/httpx, React/Vite/TypeScript, Vitest, Playwright, openapi-typescript/orval.

**Spec:** `frontend/openapi/m17.yaml`, `docs/10-api/06-m17-frontend-contracts.md`, `docs/superpowers/plans/2026-09-19-plan5-api-server-integration.md`, `docs/superpowers/plans/2026-09-20-plan6-api-operational-readiness.md`, and the current route implementations under `src/fip/api/routers/`.

## Global Constraints

- Preserve every frozen `/api/v1` path, method, operation ID, status code, response envelope, field name, enum value, nullability rule, pagination rule, and PIT/version metadata rule.
- Do not add deployment or Docker work. Local startup remains `make api-dev`, `make worker-dev`, and PostgreSQL through `FIP_DATABASE_URL`.
- The OpenAPI component names and field shapes in `frontend/openapi/m17.yaml` are authoritative. Any discrepancy must be resolved explicitly in the plan execution with a compatibility test; do not invent a second response shape.
- Every nested model rejects unknown fields (`extra="forbid"`) unless the frozen OpenAPI component intentionally contains an open-ended object; such objects use an explicit typed mapping instead of `dict[str, object]`.
- A missing, unavailable, or not-applicable metric must preserve its existing `value`, `status`, and `reason` semantics; do not convert nullable metrics into zeroes or silently omit status information.
- List envelopes, detail envelopes, command-response envelopes, and operation envelopes remain distinct types even when they contain similar fields.
- Every task starts with a failing test and leaves a focused command that can be run independently.

## File Map

- `src/fip/api/schemas.py`: strict reusable nested component models and endpoint payload/envelope models.
- `src/fip/api/app.py`, `src/fip/api/routers/reads.py`, `src/fip/api/routers/commands.py`: operation-to-payload registry and recursive response validation.
- `frontend/openapi/m17.yaml`: frozen contract source; update only when parity tests prove the current document is missing a required frozen field.
- `frontend/src/api/`, `frontend/src/generated/` (or the configured generated output): regenerated TypeScript types and client response aliases.
- `tests/api/test_response_contract_models.py`, `tests/api/test_nested_contracts.py`: model and route-level recursive validation tests.
- `tests/integration/test_response_contract_postgres.py`: PostgreSQL-backed acceptance fixtures for all response domains.
- `frontend/src/**/*.test.*`, `frontend/e2e/`: generated-type and UI contract consumers.
- `Makefile`, `frontend/package.json`, `frontend/README.md`: repeatable Plan-7 checks and local acceptance instructions.
- `.superpowers/sdd/2026-09-20-plan7-response-contract-modeling/progress.md`: execution ledger, compatibility decisions, and final freeze evidence.

### Task 1: Inventory and lock the nested component matrix

**Files:**
- Create: `tests/api/test_contract_inventory.py`
- Create: `.superpowers/sdd/2026-09-20-plan7-response-contract-modeling/progress.md`
- Modify: `docs/10-api/06-m17-frontend-contracts.md`

**Interfaces:**
- Define one registry keyed by operation ID for the 19 domain operations `getFund`, `getFundNavSeries`, `getFundEvaluations`, `getFundScores`, `listUniverses`, `getUniverse`, `listPortfolios`, `getPortfolio`, `submitOptimization`, `getOptimization`, `getDecision`, `reviewDecision`, `createBacktest`, `validateBacktest`, `runBacktest`, `getBacktestStatus`, `getBacktestResult`, `getBacktestPerformance`, and `getBacktestBiasCheck`. `getSession` and `getOperation` stay on their already-frozen shared models and are asserted separately.
- Record the exact root response component and nested components for each operation, including `Fund` → `Benchmark` → `BenchmarkComponent`/`Fee`, `FundEvaluation` → `DataCompleteness`/`FactorResult`, `FundScore` → `SubScores`/`ScoreAttribution`, `Universe` → `UniverseCondition`/`UniverseMember`, `Optimization` → `Weight`/`PostOptimizationRisk`, `Decision` → `DecisionReview`, and `BacktestResult` → `PerformanceMetrics`/`BacktestSummary`/significance layers/series.
- The inventory test parses the YAML and fails if an operation points to an unregistered response component or if a registered component is not reachable from an operation.

- [ ] **Step 1: Write the failing inventory test**

```python
def test_every_nested_response_operation_has_a_registered_component():
    document = yaml.safe_load(Path("frontend/openapi/m17.yaml").read_text())
    operation_ids = collect_operation_ids(document["paths"], include_shared=False)
    assert set(RESPONSE_COMPONENT_REGISTRY) == operation_ids
    for operation_id, component in RESPONSE_COMPONENT_REGISTRY.items():
        assert component in document["components"]["schemas"]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_contract_inventory.py -q`

Expected: FAIL because the endpoint registry and progress ledger do not exist.

- [ ] **Step 3: Record the matrix and compatibility decisions**

Add the registry and a table in the frontend contract document. Explicitly document that existing broad Python fields (`points`, `members`, `excluded`, `progress`, `result`, `review`, `portfolio_benchmark`, `benchmark`, `fee_structure`, `factor_results`, `sub_scores`, and `attribution`) are migration targets, not accepted final types.

- [ ] **Step 4: Run the inventory test**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_contract_inventory.py -q`

Expected: PASS and a progress ledger containing the operation/component matrix.

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_contract_inventory.py docs/10-api/06-m17-frontend-contracts.md .superpowers/sdd/2026-09-20-plan7-response-contract-modeling/progress.md
git commit -m "docs: inventory plan7 nested response contracts"
```

### Task 2: Implement strict shared and fund/NAV/evaluation/score models

**Files:**
- Modify: `src/fip/api/schemas.py`
- Create: `tests/api/test_response_contract_models.py`

**Interfaces:**
- Add strict models aligned to the OpenAPI components `MetricStatus`, `NullableMetric`, `VersionReferences`, `AvailabilityQualityDistribution`, `ResponseMeta`, `FundSummary`, `BenchmarkComponent`, `Benchmark`, `Fee`, `Fund`, `NavPoint`, `NavSeries`, `NavSeriesMeta`, `DataCompleteness`, `FactorResult`, `FundEvaluation`, `FundEvaluationMeta`, `SubScores`, `ScoreAttribution`, `FundScore`, and `FundScoreMeta`.
- Define endpoint payloads/envelopes with explicit item types: `FundListPayload`, `FundPayload`, `NavSeriesPayload`, `FundEvaluationPayload`, and `FundScorePayload`; no endpoint may expose `list[dict[str, object]]` for these domains.
- Preserve decimal/date/UUID serialization and nullable metric status/reason fields exactly as the current OpenAPI document specifies.

- [ ] **Step 1: Add failing nested model tests**

```python
def test_fund_rejects_unknown_nested_benchmark_field():
    payload = valid_fund_payload()
    payload["benchmark"]["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        FundPayload.model_validate(payload)


def test_evaluation_preserves_unavailable_metric_reason():
    model = FundEvaluationPayload.model_validate(valid_evaluation_payload())
    assert model.factor_results[0].metric.status == "unavailable"
    assert model.factor_results[0].metric.reason == "INSUFFICIENT_HISTORY"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_response_contract_models.py -q`

Expected: FAIL because the endpoint-specific nested classes and strict recursive validation are missing.

- [ ] **Step 3: Implement the models and fixtures**

Use reusable strict base configuration, typed lists/maps, discriminated unions where the OpenAPI schema uses status variants, and field aliases only where the frozen wire name differs from Python naming. Keep compatibility aliases at the boundary only; do not retain broad fields on the public payload classes.

- [ ] **Step 4: Run model and serialization tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_response_contract_models.py -q`

Expected: PASS for valid payloads, unknown nested fields, nullability, enum values, and JSON round trips.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/schemas.py tests/api/test_response_contract_models.py
git commit -m "feat: model fund nav evaluation and score responses"
```

### Task 3: Implement universe/portfolio/optimization/decision/backtest models

**Files:**
- Modify: `src/fip/api/schemas.py`
- Create: `tests/api/test_nested_contracts.py`

**Interfaces:**
- Add strict models for `UniverseSummary`, `UniverseCondition`, `UniverseMember`, `Universe`, `UniverseMeta`, `PortfolioSummary`, `Portfolio`, `PortfolioListMeta`, `Weight`, `OptimizationRequest`, `OptimizationSubmission`, `Optimization`, `PostOptimizationRisk`, `OptimizationMeta`, `DecisionReview`, `Decision`, `DecisionReviewRequest`, `DecisionReviewOutcome`, `DecisionMeta`, `Money`, `BacktestCreateRequest`, `BacktestCreated`, `BacktestValidation`, `ValidationIssue`, `BacktestRun`, `BacktestStatus`, `PerformanceMetrics`, `BacktestSummary`, `ExcessReturn`, all four significance layers, `BacktestResult`, `BacktestResultMeta`, `SeriesPoint`, `CumulativeReturnSeries`, `BacktestSeries`, `BacktestPerformance`, `BiasStatus`, `BiasCheck`, `PointInTimeBiasCheck`, `TransactionCostBiasCheck`, and `BacktestBiasCheck`.
- Define typed list/detail/command envelopes for each corresponding OpenAPI component and keep `OperationEnvelope` separate from business result envelopes.
- Preserve nested status/error fields, monetary precision, series ordering, and bias-check evidence fields exactly as documented.

- [ ] **Step 1: Add failing tests for each domain**

```python
@pytest.mark.parametrize("factory,model", [
    (valid_universe, UniversePayload),
    (valid_portfolio, PortfolioPayload),
    (valid_optimization, OptimizationPayload),
    (valid_decision, DecisionPayload),
    (valid_backtest_result, BacktestResultPayload),
    (valid_bias_check, BacktestBiasCheckPayload),
])
def test_nested_domain_payload_rejects_unknown_fields(factory, model):
    payload = factory()
    payload["nested_unknown"] = True
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_backtest_result_keeps_all_significance_layers():
    result = BacktestResultPayload.model_validate(valid_backtest_result())
    assert result.statistical_significance is not None
    assert result.effect_size_significance is not None
    assert result.robustness_significance is not None
    assert result.economic_significance is not None
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_nested_contracts.py -q`

Expected: FAIL because these domain models are currently represented by generic mappings or empty subclasses.

- [ ] **Step 3: Implement the domain models**

Model every nested object from the component graph, including recursive portfolio holdings/weights, optimization risk details, decision review outcome, backtest significance layers, cumulative series, and both bias-check branches. Use exact wire names and explicit `None` handling.

- [ ] **Step 4: Run focused and global schema tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_nested_contracts.py tests/api/test_app_contract.py -q`

Expected: PASS with no route or operation-ID changes.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/schemas.py tests/api/test_nested_contracts.py
git commit -m "feat: model universe portfolio optimization decision and backtest responses"
```

### Task 4: Bind endpoint responses to the strict model registry

**Files:**
- Modify: `src/fip/api/app.py`
- Modify: `src/fip/api/routers/reads.py`
- Modify: `src/fip/api/routers/commands.py`
- Create: `tests/api/test_endpoint_response_binding.py`

**Interfaces:**
- Replace the current common payload fallback with `RESPONSE_MODEL_REGISTRY[operation_id]`, whose values are the strict payload/envelope classes from Tasks 2–3.
- Route adapters return model instances or validate repository dictionaries through the selected model before serialization; a malformed nested repository row produces the existing stable `500` error envelope and request ID.
- The registry covers all 19 operation IDs from Task 1 and has a test that fails on missing, duplicate, or generic response bindings.

- [ ] **Step 1: Add failing route-binding tests**

```python
def test_get_fund_returns_typed_nested_benchmark(client, fund_fixture):
    response = client.get(f"/api/v1/funds/{fund_fixture.id}")
    assert response.status_code == 200
    assert response.json()["data"]["benchmark"]["components"][0]["weight"] is not None


def test_unknown_nested_repository_field_is_not_leaked(client, monkeypatch):
    monkeypatch.setattr("fip.api.routers.reads.load_fund", lambda *_: {**valid_fund_payload(), "leak": 1})
    response = client.get("/api/v1/funds/FND-1")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_endpoint_response_binding.py -q`

Expected: FAIL because routes still use the broad common payload and do not recursively validate the selected operation model.

- [ ] **Step 3: Implement the central binding**

Add one registry lookup in the response adapter, map each route to its operation ID, and preserve all existing status/error/pagination behavior. Remove only unreachable generic response paths after the registry is complete.

- [ ] **Step 4: Run all API contract tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/api/test_endpoint_response_binding.py tests/api/test_app_contract.py tests/api/test_authz.py -q`

Expected: PASS and the frozen route list, operation IDs, and response status matrix remain unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/fip/api/app.py src/fip/api/routers/reads.py src/fip/api/routers/commands.py tests/api/test_endpoint_response_binding.py
git commit -m "feat: bind api operations to strict response models"
```

### Task 5: Synchronize OpenAPI-generated frontend types and consumers

**Files:**
- Modify: `frontend/openapi/m17.yaml` only if the parity test identifies a documented omission
- Modify: `frontend/orval.config.ts` or the existing generator configuration only when required by the checked-in setup
- Regenerate: configured files under `frontend/src/generated/`
- Create: `frontend/src/api/response-contracts.test.ts`
- Modify: `frontend/src/**/*.ts`, `frontend/src/**/*.tsx` only where generic response aliases are consumed

**Interfaces:**
- Generated types must expose the same nested component names and optional/nullable markers as the OpenAPI document; frontend code must consume generated `Fund`, `NavSeries`, `FundEvaluation`, `FundScore`, `Universe`, `Portfolio`, `Optimization`, `Decision`, and backtest types.
- No hand-written `Record<string, unknown>` may represent one of the nine frozen response domains in API hooks or page state.
- The generator command is deterministic and documented; generated diffs are reviewed for accidental path or operation changes.

- [ ] **Step 1: Add failing frontend type tests**

```ts
import type { Fund, BacktestResult } from "./generated";

test("generated fund type exposes nested benchmark components", () => {
  const fund = {} as Fund;
  expect(fund.benchmark?.components?.[0]?.weight).toBeDefined();
});

test("backtest result exposes every significance layer", () => {
  const result = {} as BacktestResult;
  expect(result.statistical_significance).toBeDefined();
  expect(result.economic_significance).toBeDefined();
});
```

- [ ] **Step 2: Run the focused frontend test to verify it fails**

Run: `cd frontend && npm run test -- response-contracts.test.ts`

Expected: FAIL or type-check failure while generated output or consumers still use generic aliases.

- [ ] **Step 3: Regenerate and migrate consumers**

Run the repository’s configured OpenAPI generator against `frontend/openapi/m17.yaml`; update hooks/pages to use generated nested types and preserve existing loading/error states. Do not hand-edit generated output.

- [ ] **Step 4: Run frontend checks**

Run: `make frontend-check`

Expected: generated type tests, Vitest, TypeScript build, and Playwright all pass with no endpoint path or operation-ID diff.

- [ ] **Step 5: Commit**

```bash
git add frontend/openapi frontend/src frontend/*.json frontend/*.ts
git commit -m "feat: synchronize generated frontend response contracts"
```

### Task 6: Run PostgreSQL/API/frontend acceptance and freeze Plan-7

**Files:**
- Create: `tests/integration/test_response_contract_postgres.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `frontend/README.md`
- Modify: `.superpowers/sdd/2026-09-20-plan7-response-contract-modeling/progress.md`

**Interfaces:**
- Add `make plan7-check` that runs Python contract tests, PostgreSQL integration tests, OpenAPI parity checks, and `make frontend-check` without Docker.
- PostgreSQL fixtures cover one representative valid response for every domain and at least one unavailable/null metric, empty list, validation issue, operation reference, significance layer, and bias-check branch.
- The freeze ledger records commit SHAs, commands, test counts, OpenAPI hash, generated-client hash, database migration revision, and any explicitly approved compatibility alias.

- [ ] **Step 1: Add failing PostgreSQL acceptance tests**

```python
@pytest.mark.integration
@pytest.mark.parametrize("operation_id", ALL_RESPONSE_OPERATION_IDS)
def test_postgres_response_matches_strict_contract(api_client, operation_id):
    response = invoke_seeded_operation(api_client, operation_id)
    assert response.status_code in {200, 201, 202}
    validate_operation_response(operation_id, response.json())
```

- [ ] **Step 2: Run acceptance tests to verify the gap**

Run: `FIP_DATABASE_URL=postgresql+psycopg://fip:fip@localhost:5432/fip PYTHONPATH=src .venv/bin/pytest tests/integration/test_response_contract_postgres.py -q -m integration`

Expected: FAIL until all endpoint bindings, fixtures, and recursive validators are complete.

- [ ] **Step 3: Implement the acceptance command and documentation**

Run migrations against the configured local PostgreSQL, seed deterministic fixtures, execute the API contract suite, verify generated frontend types, and document the exact local commands. Keep Docker and deployment explicitly out of scope.

- [ ] **Step 4: Run the complete Plan-7 gate**

Run: `make plan7-check`

Expected: all Python tests, PostgreSQL integration tests, OpenAPI parity checks, frontend tests/build, and Playwright checks pass; the frozen route and operation-ID snapshots are unchanged.

- [ ] **Step 5: Freeze the plan**

Update the progress ledger with evidence, mark every task complete, record the final contract hashes, and commit:

```bash
git add tests/integration/test_response_contract_postgres.py Makefile README.md frontend/README.md .superpowers/sdd/2026-09-20-plan7-response-contract-modeling/progress.md
git commit -m "docs: freeze plan7 response contract modeling"
```

## Completion Criteria

- All 19 frozen response operations have endpoint-specific strict models and recursive validation.
- No public Plan-7 response payload uses the former broad nested `dict[str, object]` fields.
- OpenAPI, Python serialization, generated TypeScript, API tests, frontend consumers, and PostgreSQL fixtures agree on names, nullability, enums, and nested structure.
- `make plan7-check` passes locally with PostgreSQL and without Docker.
- The progress ledger contains reproducible evidence and the final freeze commit.
