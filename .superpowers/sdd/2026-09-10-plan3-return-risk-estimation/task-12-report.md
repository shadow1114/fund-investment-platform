# Task 12 Report — Architecture, Documentation, and Quality Gates

Date: 2026-09-14

Branch: `main`

Status: documentation complete; PostgreSQL-backed verification blocked by the local environment

## Outcome

Updated the five scoped architecture/API/database documents to match the implemented Plan-3
contract and updated the Plan-3 ledger. The documents now describe:

- the actual seven Plan-3 tables and their Run + Basis grains;
- independent ABSOLUTE and EXCESS packages and exact member ordering;
- checksummed complete lower-triangle covariance/correlation payloads;
- canonical float64 string encoding and persisted diagnostics/Validation details;
- the annualized Stage ⑥ contract (`mu` and `Sigma` both scaled by 252);
- the six Run lifecycle states and separate `approved_for_optimization` semantics;
- transactional rejection/failure behavior; and
- explicit Plan-3B, Portfolio Construction/optimizer, ML, transaction-cost, and backtest-timeline
  deferral.

No production code, migration, configuration, or test file was changed.

## Files

- `docs/02-architecture/02-service-architecture.md`
  - Added the implemented Stage ⑤ service assembly, annualized Stage ⑥ provider boundary,
    lifecycle/approval split, failure transactions, and deferred scope.
- `docs/02-architecture/03-data-architecture.md`
  - Added independent basis result-package semantics, lower-triangle transport/persistence,
    annualized consumption boundary, and closed the obsolete matrix-serialization TBD.
- `docs/10-api/04-portfolio-api.md`
  - Replaced the old per-fund return field with `mu`; replaced full-square response examples with
    structured lower-triangle payloads; separated `run_status` from API-derived
    `approval_status`.
- `docs/11-database/03-erd.md`
  - Replaced the earlier conceptual matrix-member model with the actual seven-table ERD and
    documented basis grains, Validation, status/approval, encoding, and Stage ⑥ semantics.
- `docs/11-database/04-database-design.md`
  - Aligned the catalog and physical design with migration `0027_plan3_estimation.py`, including
    exact keys, foreign-key delete behavior, constraints, payloads, numeric encoding, and
    transaction boundaries.
- `.superpowers/sdd/2026-09-10-plan3-return-risk-estimation/progress.md`
  - Recorded Task 12 documentation completion and the unresolved database-runtime gate.
- `.superpowers/sdd/2026-09-10-plan3-return-risk-estimation/task-12-report.md`
  - This report.

## Verification Commands and Results

The workspace path contains non-ASCII characters. The first literal unit command inherited
`LC_ALL=C` and Python failed while importing `site` with `UnicodeDecodeError`. A minimal probe
confirmed `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8` gives `sys.getfilesystemencoding() == "utf-8"`;
all subsequent commands used that environment prefix. This changes only process locale, not the
command under test.

| Command | Result |
|---|---|
| `.venv/bin/pytest tests/unit -q` | Initial environment failure before pytest collection: ASCII could not decode the workspace path. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/unit -q` | PASS, exit 0; 292 collected tests, all dots completed to 100%. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/fitness -q` | PASS, exit 0; 37 collected tests. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/integration -m integration -q` | BLOCKED, exit 1; 246 collected. Shared `db_engine` fixture cannot connect to `postgresql+psycopg://localhost/fip_test`: `127.0.0.1:5432 Connection refused`. The run produced one non-database pass and setup errors for the database-backed cases; no product assertion failed. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/repro/test_estimation_reproducibility.py -q` | BLOCKED, exit 1; one setup error at the same PostgreSQL connection. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/ruff check src tests` | PASS, exit 0: `All checks passed!` |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/mypy` | PASS, exit 0: `Success: no issues found in 99 source files` |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/integration/test_autogenerate_gate.py tests/integration/test_temporal_constraints.py -q` | BLOCKED, exit 1; 43 collected, one non-database pass and 42 setup errors at the same PostgreSQL connection. ORM drift and CHECK snapshot assertions did not execute. |
| `git diff --check` | PASS, exit 0. |

Environment diagnosis:

- `tests/conftest.py` targets `postgresql+psycopg://localhost/fip_test` and resets/migrates it at
  session start.
- `brew services list` reports no PostgreSQL service.
- no `postgres`, `pg_ctl`, or `pg_isready` binary exists under the standard Homebrew,
  `/Applications`, or user paths inspected;
- no `docker` executable is installed.

Per the parent task direction, no package/runtime was installed and no database result is
fabricated. Plan-3 cannot be declared complete until the three database-backed commands above
are rerun successfully with PostgreSQL available.

## Spec §8 Acceptance Criteria → Tests

| # | Acceptance criterion | At least one mapped test |
|---:|---|---|
| 1 | Historical `decision_at` reconstructs Universe, basis matrices, `mu`, `Sigma`, `rho`, Validation | `tests/repro/test_estimation_reproducibility.py::test_real_pit_estimation_is_reproducible_and_idempotent`; `tests/integration/test_estimation_inputs.py::test_lineage_and_fingerprints_cover_the_pit_inputs` |
| 2 | Each bundle has identical member set/order across `mu`, `Sigma`, `rho` | `tests/integration/test_estimation_repositories.py::test_complete_rejects_dimension_order_or_member_mismatch_before_save` |
| 3 | ABSOLUTE and EXCESS have independent data, matrices, lineage; no cross-basis mixing | `tests/integration/test_estimation_inputs.py::test_basis_inputs_are_independently_aligned`; `tests/integration/test_estimation_repositories.py::test_approved_provider_cannot_mix_basis_or_run` |
| 4 | No missing-data fill; dropped dates and exclusion reasons persist deterministically | `tests/unit/test_estimation_alignment.py::test_complete_case_uses_intersection_without_fill`; `tests/integration/test_estimation_repositories.py::test_reject_persists_input_rejection_without_fabricating_numeric_results` |
| 5 | Non-PSD, zero variance, insufficient samples, or unapproved config cannot reach Stage ⑥ | `tests/unit/test_estimation_validation.py::test_gate_rejects_each_blocking_bundle_violation`; `tests/unit/test_covariance_estimation.py::test_zero_variance_is_rejected`; `tests/unit/test_estimation_policy.py::test_live_estimation_rejects_provisional_parameters` |
| 6 | Same-input rerun error ≤ `1e-10`; concurrent calls create no duplicate business Run | `tests/repro/test_estimation_reproducibility.py::test_real_pit_estimation_is_reproducible_and_idempotent`; `tests/integration/test_estimation_repositories.py::test_concurrent_start_unique_key_race_returns_one_run` |
| 7 | Validation rejection is auditable; system failure leaves no partial result and exposes `FAILED` | `tests/integration/test_estimation_repositories.py::test_reject_persists_audit_bundle_but_never_approves`; `tests/integration/test_estimation_service.py::test_unhandled_failure_rolls_back_results_and_marks_run_failed` |
| 8 | Backtest and Live share one Service and differ by `DecisionExecutionContext` | `tests/fitness/test_architecture.py::test_strategy_library_has_no_runtime_mode_branch`; `tests/integration/test_estimation_service.py::test_absolute_success_and_excess_input_rejection_is_warning` exercises the Service with a BACKTEST context, while `tests/unit/test_estimation_policy.py::test_estimation_policy_v1_matches_decided_contract` validates the same policy path in LIVE mode |
| 9 | Stage ⑥ reads only approved ABSOLUTE annualized `mu`, `Sigma`, exact order | `tests/integration/test_estimation_repositories.py::test_approved_provider_returns_absolute_annualized_bundle_and_version_closure`; `tests/integration/test_estimation_repositories.py::test_complete_rejects_nonannualized_result_bundle`; `tests/integration/test_estimation_repositories.py::test_approved_provider_cannot_mix_basis_or_run` |

The mapped PostgreSQL-backed tests exist and were inspected, but their fresh execution is subject
to the database limitation recorded above.

## Out-of-Scope Review

Reviewed the Plan-3 commit range `706e192^..cc85326` by name and content:

```bash
git diff --name-only 706e192^..cc85326 | sort
git diff 706e192^..cc85326 -- src db/migrations config pyproject.toml \
  | rg '^\\+.*(Plan-3B|Return MAE|Risk RMSE|Kupiec|optimizer|optimi[sz]e|transaction.?cost|backtest timeline|sklearn|tensorflow|torch|xgboost)'
```

The content scan returned no matches. The changed production surface is confined to estimation
policies, PIT/benchmark inputs, pure return/covariance/validation functions, Plan-3 persistence,
repository/provider, Factor risk cross-check adapter, and orchestration. No Task implements:

- Plan-3B OOS scheduling or future-realization resolution;
- Portfolio Construction or optimizer logic;
- ML models or ML dependencies;
- transaction-cost logic; or
- a backtest timeline.

`approved_for_optimization` and `ApprovedEstimationProvider` are authorization/consumption
boundaries only; they do not implement optimization.

## Self-Review

- Compared all seven documented table names, grains, statuses, constraints, and delete actions
  against `src/fip/services/portfolio_service/estimation/models.py` and
  `db/migrations/versions/0027_plan3_estimation.py`.
- Compared API payload fields against the canonical encoding and repository decode/validation
  contract.
- Verified active response examples no longer expose full-square covariance/correlation fields.
- Verified scoped-doc search has no obsolete per-fund return field, full-square response key,
  covariance-member table, or `APPROVED` Run status contract.
- Verified all edits remain within the five requested docs and the Plan-3 SDD ledger/report.
- No integration or drift success claim is made without PostgreSQL evidence.
