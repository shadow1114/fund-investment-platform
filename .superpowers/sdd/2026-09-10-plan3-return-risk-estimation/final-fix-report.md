# Final Plan-3 Fix Report

Date: 2026-09-14

## Scope and outcome

This fix wave completes the post-review corrections to the Plan-3 estimation
service while preserving the staged working-tree changes that preceded it.

- A provisional estimation or validation policy now creates an auditable
  `RUNTIME_ELIGIBILITY` reject result. LIVE always fails this gate; BACKTEST
  passes it only when the service is explicitly constructed with
  `allow_experimental=True`. The eligibility result and its provisional paths
  are also written for an input-rejected basis, so a fail-closed decision does
  not lose its evidence.
- Pure numerical estimator domain failures are basis-local. The rejected basis
  receives `NUMERICAL_INPUT_REJECTED` lineage and audit data, while the other
  basis continues through the normal calculation and persistence transaction.
- `run()` does not retry an existing `FAILED` run. It returns the existing
  non-final state (including `RUNNING`) without calculating; `retry()` is the
  only explicit `FAILED -> RUNNING` transition.
- Service startup now verifies the persisted Plan-3 method code,
  implementation path, complete method specification, full parameter content,
  immutable estimation-policy content, and immutable validation-policy
  content. The parameter payload includes the ABSOLUTE/EXCESS return-basis
  contract; only the policy label is excluded from that independent payload.
- D-4A now uses `delta_sigma = (pi_hat - rho_hat) / (gamma_hat * T)`. The
  frozen covariance fixture and clamp references were independently
  recomputed for that denominator.
- Factor cross-check details retain the selected factor value, run, and
  version identifiers. Aggregate details retain each selected member result.
- The real PIT service fixture now contains visible classifications and a
  complete benchmark history. It covers successful, independently persisted
  ABSOLUTE and EXCESS result packages, while the reproducibility test asserts
  both successful bases and no rejected-basis audit row.

## Verification

| Command | Result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/unit/test_estimation_service.py tests/unit/test_covariance_estimation.py tests/unit/test_estimation_policy.py tests/unit/test_estimation_validation.py -q` | PASS: 72 tests. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/ruff check src/fip/services/portfolio_service/estimation src/fip/strategy_library/estimation tests/unit/test_estimation_service.py tests/unit/test_covariance_estimation.py tests/integration/test_estimation_service.py tests/repro/test_estimation_reproducibility.py` | PASS. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/pytest tests/integration/test_estimation_service.py tests/repro/test_estimation_reproducibility.py --collect-only -q` | PASS: 7 tests collected. |
| `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 .venv/bin/mypy` | PASS: no issues in 99 source files. |
| `git diff --check` | PASS. |

The PostgreSQL-backed service and reproducibility tests were not claimed as
executed: this host's existing Task-12 diagnosis remains applicable
(`127.0.0.1:5432` has no PostgreSQL service/runtime). The new tests collect
successfully, but must run against PostgreSQL before Plan-3 can be declared
fully database-verified.
