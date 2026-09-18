# Task 2 Implementation Report

## Status

Complete. Commit: `8323759 feat: add frozen m17 openapi client`.

## Implemented

- Added the OpenAPI 3.1.0 projection at `frontend/openapi/m17.yaml` for all 22 frozen M1.7 paths and operations.
- Projected the shared success/error envelope, pagination, provenance/version metadata, PIT metadata, nullable metric status/reason semantics, session, operation, fund, universe, portfolio, optimization, decision, and backtest resources.
- Made non-`OPTIMAL` optimization `target_weights` null through an OpenAPI 3.1 conditional schema, while retaining explicit infeasibility diagnostics.
- Added Orval 7.17 generation through the existing `api:generate` script. It cleans and writes only `frontend/src/api/generated/` and currently produces `m17.ts` plus `m17.schemas.ts`.
- Generated all required typed client functions:
  - `getSession`, `getOperation`
  - `listFunds`, `getFund`, `getFundNavSeries`, `getFundEvaluations`, `getFundScores`
  - `listUniverses`, `getUniverse`
  - `listPortfolios`, `getPortfolio`, `submitOptimization`, `getOptimization`
  - `getDecision`, `reviewDecision`
  - `createBacktest`, `validateBacktest`, `runBacktest`, `getBacktestStatus`, `getBacktestResult`, `getBacktestPerformance`, `getBacktestBiasCheck`
- Added `http.ts` with envelope unwrapping, status-aware `ApiError`, and idempotency-header construction.
- Added stable hierarchical React Query keys and typed query-option factories for every frozen read operation.
- Added mutation hooks for optimization submission, decision review, backtest creation, validation, and execution, including relevant cache invalidation.
- Preserved Task 1 scripts and Make targets. Only the placeholder `api:generate` script was replaced; the existing `dev`, `build`, `test`, `lint`, `format:check`, and `check` scripts remain unchanged.

## TDD Evidence

1. Added the path/version contract test and observed the expected `ENOENT` failure because `frontend/openapi/m17.yaml` did not exist.
2. Added the projection and observed the path/version contract pass.
3. Added HTTP helper tests and observed the expected missing-module failure for `./http` before implementation.
4. Implemented `http.ts`; both HTTP helper tests passed.
5. Added query-key/mutation-helper tests and observed the expected missing-module failure for `./mutations` before implementation.
6. Implemented `queries.ts` and `mutations.ts`; all helper tests passed.
7. Expanded contract tests to check exact frozen paths, all generated exports, nullable metric structure, conditional optimization weights, provenance fields, and bias-check statuses. The new assertions failed before the corresponding schema tightening and passed afterward.

## Verification

- Required focused verification:
  - `npm test -- --run src/api/contract.test.ts`: 1 file, 4 tests passed.
  - `npm run build`: TypeScript and Vite production build passed.
- Full frontend verification:
  - `npm run check`: passed.
  - Formatting: passed.
  - ESLint: 0 errors, 38 warnings from Orval-generated unused disable comments.
  - Tests: 5 files, 11 tests passed.
  - Production build: passed.
- `git diff --check`: passed before commit.

## Concerns

- Orval emits 38 harmless ESLint warnings for unused `@typescript-eslint/no-redeclare` disable comments in the generated schema file. There are no lint errors, and generated files were not manually edited.
- Existing React Router v7 future-flag warnings still appear in `App.test.tsx`; they predate this task and do not affect the new API tests or build.

---

## Review Fix Report

Review-fix commit: `04bbd91 fix: harden frozen m17 api contracts`.

### Findings resolved

1. Added `style: form` and `explode: false` to all four frozen multi-value query parameters. Added `orval.config.ts` with `fetch.explode: false` because Orval's fetch generator otherwise overrides the per-parameter setting. Generated URLs now serialize one comma-separated value for `fund_type`, `lifecycle_status`, `investment_eligibility`, and `include_series`.
2. Required status/reason companions for nullable fund sub-scores, total score, universe ranking metrics, optimization objective and post-optimization volatility, Sharpe ratio, excess returns, significance metrics, and performance-series values. Existing shared factor `status`/`reason_code` fields are now required where they explain nullable factor values.
3. Added endpoint-specific `FundListMeta` and `PortfolioListMeta`. Fund lists require as-of date, data version, version references, PIT flag, pagination, and availability-quality distribution. Portfolio lists require version references, PIT flag, and pagination. Query helpers throw `CONTRACT_ERROR` when required list metadata is absent.
4. Added nullable equal-weight baseline result and performance-series representations with required baseline status/reason fields, supporting `equal_weight_baseline_enabled=false` without inventing data.
5. Added `normalizeOptimization` at the query boundary. It rejects any non-`OPTIMAL` result carrying target weights with `CONTRACT_ERROR`, covering the invariant Orval cannot retain from the OpenAPI conditional schema.
6. Added explicit `UNKNOWN` variants to generated business-status types and recursive API-boundary normalization that maps unfamiliar enum/status values to `UNKNOWN` rather than exposing an unsafe value or crashing the UI.
7. Added `PointInTimeBiasCheck` and `TransactionCostBiasCheck` schemas requiring `availability_quality_distribution` and `unmodeled_costs`, respectively.
8. Expanded focused contract tests for generated parameter serialization, nullable companions, endpoint-specific metadata, disabled baselines, optimization invariants, unknown enum normalization/generated variants, and bias-check evidence requirements.

### TDD evidence

- The expanded contract suite initially failed five focused cases: repeated multi-value serialization, optional nullable companions, absent endpoint metadata schemas, non-null baseline modeling, and absent bias-specific schemas.
- HTTP boundary tests initially failed for missing optimization validation, unknown-status normalization, and missing-metadata detection.
- Each focused suite passed after the corresponding schema/runtime change and client regeneration.

### Verification

- `npm run check`: passed formatting, lint gate, all tests, and production build.
- Tests: 5 files, 20 tests passed.
- Focused API tests: 3 files, 18 tests passed.
- Production TypeScript/Vite build: passed.
- Lint remains at 0 errors with the same 38 Orval-generated unused-disable warnings.
- `git diff --check`: passed before commit.

---

## Scoped Re-review Fix: Field-specific Enum Normalization

Fix commit: `9eaabc4 fix: normalize m17 enums per field`.

### Changes

- Replaced the global cross-enum whitelist with per-field allowed-value sets. Metric companion statuses use the shared `MetricStatus` set; the overloaded `status` field is resolved from the containing response shape and bias-check path.
- A value valid only for another enum is now normalized correctly. For example, `optimization_status: "COMPLETED"` becomes `UNKNOWN`, while `optimization_status: "OPTIMAL"` is preserved.
- Added `UNKNOWN` to every response enum normalized at the API boundary, including factor direction, attribution enums, universe enums, decision review action, backtest validation/result/performance enums, and the created/run backtest statuses. Request-only enums remain strict.
- Regenerated Orval schemas and added compile-time contract coverage proving the generated direction and status types accept `UNKNOWN`.
- Added focused runtime tests for cross-enum optimization values and unknown direction normalization.

### TDD and verification commands/output

RED command:

```text
$ npm test -- --run src/api/http.test.ts src/api/contract.test.ts
Test Files  2 failed (2)
Tests  2 failed | 15 passed (17)
```

The failures were the intended assertions: `optimization_status: "COMPLETED"` was incorrectly preserved, and `FactorResult.direction` did not contain `UNKNOWN`.

Client generation:

```text
$ npm run api:generate
🍻 orval v7.17.0 - A swagger client generator for typescript
m17: Cleaning output folder
🎉 m17 - Your OpenAPI spec has been converted into ready to use orval!
```

Focused API and type verification:

```text
$ npm test -- --run src/api/http.test.ts src/api/contract.test.ts src/api/helpers.test.ts && npx tsc -p tsconfig.app.json --noEmit && git diff --check
Test Files  3 passed (3)
Tests  20 passed (20)
```

`tsc --noEmit` and `git diff --check` completed with exit code 0 and no output.

Full frontend verification:

```text
$ npm run check
All matched files use Prettier code style!
✖ 41 problems (0 errors, 41 warnings)
Test Files  5 passed (5)
Tests  22 passed (22)
✓ 77 modules transformed.
✓ built in 3.00s
```

The 41 warnings are Orval-generated unused `@typescript-eslint/no-redeclare` disable comments. The existing React Router v7 future-flag warnings also remain; neither warning class is a failure.

## Scoped Re-review Fix: Optimization Submission Status Isolation

Fix commit: `fix: normalize optimization submission status`.

### Changes

- Added `UNKNOWN` to the OpenAPI and generated `OptimizationSubmissionStatus` enum.
- Special-cased response records containing both `operation_id` and `optimization_id` so optimization submission statuses accept only `RUNNING` and `UNKNOWN`; generic operation records retain their own full status enum.
- Added runtime cross-enum normalization coverage and compile-time/generated-schema coverage for the optimization submission status.

### Verification

- `npm test -- --run src/api/http.test.ts src/api/contract.test.ts`: 2 files, 18 tests passed.
- `npx tsc -p tsconfig.app.json --noEmit`: passed.
- `npm run check`: passed formatting, lint (0 errors; 41 existing generated-file warnings), all tests (5 files, 23 tests), and production build.
