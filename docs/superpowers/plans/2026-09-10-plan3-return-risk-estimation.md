# Plan-3 Return and Risk Estimation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从冻结的 `FundUniverseSnapshot` 和 PIT 历史序列生成可复现、经校验且仅以 ABSOLUTE 口径供 Stage ⑥消费的年化 `mu` 与 `Sigma`。

**Architecture:** 纯数值算法位于 `strategy_library.estimation`，只接收已组装的稠密矩阵；`portfolio_service.estimation` 负责 PIT 输入、版本、持久化、状态机和下游端口。ABSOLUTE 与 EXCESS 独立对齐并形成完整结果包，Factor 交叉核对通过注入 Protocol 完成。

**Tech Stack:** Python 3.12、NumPy 2.x、SQLAlchemy 2、PostgreSQL/JSONB、Alembic、pytest、Ruff、mypy。

**Spec:** `docs/superpowers/specs/2026-09-10-plan3-return-risk-estimation-design.md`

## Global Constraints

- LIVE 拒绝任何 `PROVISIONAL` 参数；BACKTEST 只能显式启用实验版本。
- 输入固定为 `SIMPLE` 日收益、756 交易日窗口、252 年化、季度适用期。
- 生产结果统一为年化尺度；`mu_daily * 252`，`Sigma_daily * 252`。
- ABSOLUTE 与 EXCESS 不共享矩阵、风险、成员集合或 observation fingerprint。
- 完整案例矩阵不得含 NaN，不填充，不做 pairwise deletion，不启发式逐只剔除。
- `T < 3N` 拒绝，`3N <= T < 5N` WARNING。
- `variance[i] == Sigma[i,i]`，`volatility[i] == sqrt(Sigma[i,i])`。
- 只允许通过 Gate 的 ABSOLUTE 结果进入 Stage ⑥；EXCESS 始终不可批准用于 M1 优化。
- `strategy_library` 不依赖 I/O、SQLAlchemy 或运行模式；`portfolio_service` 不依赖 `factor_service`。
- 不引入 sklearn 或其他 ML 依赖；数值实现只依赖 NumPy。
- 周期性 OOS 质量评估属于 Plan-3B，不在本计划实现。

## File Map

| File | Responsibility |
|---|---|
| `config/policy/estimation/v1.yaml` | 估计参数与方法选择 |
| `config/policy/estimation/validation_v1.yaml` | 当次 Validation Gate 阈值 |
| `src/fip/strategy_library/estimation/types.py` | 纯算法输入输出值对象 |
| `src/fip/strategy_library/estimation/alignment.py` | 完整案例日期对齐 |
| `src/fip/strategy_library/estimation/returns.py` | James-Stein `mu` |
| `src/fip/strategy_library/estimation/covariance.py` | 常相关 Ledoit-Wolf、risk、rho |
| `src/fip/strategy_library/estimation/validation.py` | 纯 Validation Gate |
| `src/fip/services/portfolio_service/estimation/models.py` | 七张 Plan-3 ORM 表 |
| `src/fip/services/portfolio_service/estimation/repositories.py` | Run、结果、幂等和只读查询 |
| `src/fip/services/portfolio_service/estimation/inputs.py` | Universe、PIT NAV/Benchmark 输入组装 |
| `src/fip/services/portfolio_service/estimation/service.py` | Run 生命周期和业务事务编排 |
| `src/fip/services/factor_service/estimation_adapter.py` | Factor 风险只读适配器 |
| `db/migrations/versions/0027_plan3_estimation.py` | 七表、约束和索引 |

---

### Task 1: Complete Policies and Numeric Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/policy/estimation/v1.yaml`
- Create: `config/policy/estimation/validation_v1.yaml`
- Modify: `src/fip/services/portfolio_service/estimation/policy.py`
- Modify: `src/fip/services/portfolio_service/estimation/__init__.py`
- Test: `tests/unit/test_estimation_policy.py`
- Test: `tests/integration/test_estimation_policy_persistence.py`

**Interfaces:**
- Produces: `EstimationValidationPolicy`, `load_estimation_validation_policy(path, mode)`, `persist_estimation_validation_policy_version(session, policy) -> int`.
- Adds to `EstimationPolicy`: `numeric_scale="ANNUALIZED"`, `covariance_ddof=1`, `mu_cross_section_ddof=1`.

- [ ] **Step 1: Write failing policy tests**

```python
def test_estimation_policy_fixes_numeric_conventions():
    policy = load_estimation_policy(POLICY, RuntimeMode.LIVE)
    assert policy.numeric_scale == "ANNUALIZED"
    assert policy.covariance_ddof == policy.mu_cross_section_ddof == 1

def test_validation_policy_persists_as_distinct_kind(db_session):
    policy = load_estimation_validation_policy(VALIDATION, RuntimeMode.LIVE)
    row_id = persist_estimation_validation_policy_version(db_session, policy)
    assert db_session.get(PolicyVersion, row_id).policy_kind == "estimation_validation"
```

- [ ] **Step 2: Verify the tests fail**

Run: `.venv/bin/pytest tests/unit/test_estimation_policy.py tests/integration/test_estimation_policy_persistence.py -q`

Expected: FAIL because the validation policy API and numeric convention fields do not exist.

- [ ] **Step 3: Implement the policy contract**

Add `dependencies = ["numpy>=2.1,<3"]` under `[project]`. Add the three numeric convention fields to `v1.yaml`. Create `validation_v1.yaml` with this exact value shape and a `source` string on every leaf:

```yaml
sample_size:
    minimum_t_over_n: {value: 3, status: DECIDED, source: "Plan-3 D-7"}
    warning_t_over_n: {value: 5, status: DECIDED, source: "Plan-3 D-7"}
matrix:
    psd_relative_tolerance: {value: 1.0e-8, status: DECIDED, source: "Plan-3 D-7"}
    symmetry_tolerance: {value: 1.0e-12, status: DECIDED, source: "Plan-3 D-7"}
    correlation_tolerance: {value: 1.0e-12, status: DECIDED, source: "Plan-3 D-7"}
    condition_warning: {value: 1.0e4, status: DECIDED, source: "Plan-3 D-7"}
    condition_reject: {value: 1.0e6, status: DECIDED, source: "Plan-3 D-7"}
cross_check:
    relative_tolerance: {value: 1.0e-6, status: DECIDED, source: "Plan-3 D-4"}
```

`EstimationValidationPolicy` has one typed field per leaf plus `version` and `provisional_parameters`. Reuse the immutable `PolicyVersion` persistence pattern and reject conflicting content.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_estimation_policy.py tests/integration/test_estimation_policy_persistence.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml config/policy/estimation src/fip/services/portfolio_service/estimation/policy.py src/fip/services/portfolio_service/estimation/__init__.py tests/unit/test_estimation_policy.py tests/integration/test_estimation_policy_persistence.py
git commit -m "feat: finalize estimation policies"
```

### Task 2: Add Pure Types and Canonical Encoding

**Files:**
- Create: `src/fip/strategy_library/estimation/__init__.py`
- Create: `src/fip/strategy_library/estimation/types.py`
- Create: `src/fip/strategy_library/estimation/encoding.py`
- Create: `tests/unit/test_estimation_encoding.py`

**Interfaces:**
- Produces the following immutable DTOs:

```python
@dataclass(frozen=True, slots=True)
class DatedReturn:
    effective_at: dt.date
    value: float

@dataclass(frozen=True, slots=True)
class AlignedReturns:
    instrument_order: tuple[int, ...]
    observation_dates: tuple[dt.date, ...]
    matrix: np.ndarray
    excluded_instruments: tuple[tuple[int, str], ...]
    dropped_dates: tuple[dt.date, ...]

@dataclass(frozen=True, slots=True)
class ReturnEstimateResult:
    sample_mean_daily: np.ndarray
    target_daily: float
    shrinkage_intensity: float
    shrunk_mu_annualized: np.ndarray
    annualized_mu: np.ndarray
    clipped: np.ndarray

@dataclass(frozen=True, slots=True)
class CovarianceEstimateResult:
    sample_covariance_daily: np.ndarray
    target_covariance_daily: np.ndarray
    covariance: np.ndarray
    correlation: np.ndarray
    variance: np.ndarray
    volatility: np.ndarray
    shrinkage_intensity: float
    sample_min_eigenvalue: float
    sample_max_eigenvalue: float
    sample_condition_number: float
    final_min_eigenvalue: float
    final_max_eigenvalue: float
    final_condition_number: float

@dataclass(frozen=True, slots=True)
class FactorRiskObservation:
    factor_run_id: int
    factor_value_id: int
    factor_version_id: int
    volatility: float | None
    window: str
    observation_fingerprint: str | None
    return_type: str | None
    ddof: int | None
    annualization: int | None
    status: str
```

- Produces: `encode_float64(value) -> str`, `encode_lower_triangle(matrix) -> tuple[str, ...]`, `decode_lower_triangle(values, size) -> np.ndarray`, `canonical_checksum(payload) -> str`.

- [ ] **Step 1: Write failing round-trip tests**

```python
def test_lower_triangle_round_trips_float64_exactly():
    matrix = np.array([[0.1, -0.0], [-0.0, np.nextafter(0.2, 1.0)]])
    encoded = encode_lower_triangle(matrix)
    assert np.array_equal(decode_lower_triangle(encoded, 2), matrix)
    assert canonical_checksum({"values": encoded}) == canonical_checksum({"values": encoded})
```

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/pytest tests/unit/test_estimation_encoding.py -q`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement immutable values and encoding**

Use `repr(float(value))` for `FLOAT64_SHORTEST_ROUNDTRIP_V1`, reject NaN/Infinity, serialize canonical JSON with sorted keys and compact separators, and hash UTF-8 bytes with SHA-256. Encode lower triangle in row-major order `(0,0), (1,0), (1,1), ...`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_estimation_encoding.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/strategy_library/estimation tests/unit/test_estimation_encoding.py
git commit -m "feat: add estimation value types and encoding"
```

### Task 3: Implement Alignment and James-Stein Returns

**Files:**
- Create: `src/fip/strategy_library/estimation/alignment.py`
- Create: `src/fip/strategy_library/estimation/returns.py`
- Create: `tests/unit/test_estimation_alignment.py`
- Create: `tests/unit/test_expected_returns.py`

**Interfaces:**
- Consumes: `Mapping[int, Sequence[DatedReturn]]` in frozen instrument order.
- Produces: `complete_case_alignment(series, instrument_order) -> AlignedReturns`.
- Produces: `estimate_expected_returns(matrix, annualization=252) -> ReturnEstimateResult`.

- [ ] **Step 1: Write failing alignment and known-answer tests**

```python
def test_complete_case_uses_intersection_without_fill():
    series = {
        10: (DatedReturn(date(2026, 1, 1), 0.01), DatedReturn(date(2026, 1, 2), 0.02), DatedReturn(date(2026, 1, 3), 0.03)),
        20: (DatedReturn(date(2026, 1, 1), 0.04), DatedReturn(date(2026, 1, 3), 0.06)),
    }
    result = complete_case_alignment(series, (10, 20))
    assert result.instrument_order == (10, 20)
    assert result.matrix.shape == (2, 2)
    assert not np.isnan(result.matrix).any()
    assert result.dropped_dates == (date(2026, 1, 2),)

def test_james_stein_matches_positive_part_formula():
    matrix = np.array([[.01,.02,.00,.03],[.02,.01,.01,.04],[.00,.03,.02,.02],
                       [.01,.02,.01,.03],[.03,.00,.02,.05]])
    result = estimate_expected_returns(matrix, annualization=252)
    assert result.shrinkage_intensity == pytest.approx(0.07467532467532466)
    assert result.annualized_mu == pytest.approx([3.62209091, 4.08845455, 3.15572727, 8.28572727])
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/unit/test_estimation_alignment.py tests/unit/test_expected_returns.py -q`

Expected: FAIL with missing functions.

- [ ] **Step 3: Implement the spec D-3 and D-4A formulas**

Alignment excludes only series with fewer than two valid returns, then intersects dates once. James-Stein uses `S=np.cov(X,rowvar=False,ddof=1)`, grand mean target, positive-part `delta_mu`, 252 annualization, and final cross-sectional clipping with `ddof=1`. Reject `N<4`, non-finite input, and non-degenerate invalid dispersion; record raw, shrunk, clipped values and mask.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_estimation_alignment.py tests/unit/test_expected_returns.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/strategy_library/estimation/alignment.py src/fip/strategy_library/estimation/returns.py tests/unit/test_estimation_alignment.py tests/unit/test_expected_returns.py
git commit -m "feat: estimate aligned expected returns"
```

### Task 4: Implement Constant-Correlation Ledoit-Wolf

**Files:**
- Create: `src/fip/strategy_library/estimation/covariance.py`
- Create: `tests/unit/test_covariance_estimation.py`

**Interfaces:**
- Consumes: finite dense `np.ndarray`, shape `(T, N)`.
- Produces: `estimate_covariance(matrix, annualization=252) -> CovarianceEstimateResult` containing sample/target/final matrices, `delta_sigma`, diagnostics, variance, volatility, and rho.

- [ ] **Step 1: Write failing reference tests**

```python
def test_constant_correlation_matches_frozen_reference():
    matrix = np.array([[.01,.02,.00],[.02,.01,.01],[.00,.03,.02],
                       [.01,.02,.01],[.03,.00,.02],[.02,.01,.03]])
    result = estimate_covariance(matrix, annualization=252)
    expected = np.array([[.02772,-.02370351,.00390865],
                         [-.02370351,.02772,-.00792514],
                         [.00390865,-.00792514,.02772]])
    assert result.shrinkage_intensity == pytest.approx(0.21734234234234234)
    assert result.covariance == pytest.approx(expected, abs=1e-8)
    assert np.diag(result.covariance) == pytest.approx(result.variance)

def test_zero_variance_is_rejected():
    constant_column = np.array([[.01,.02],[.01,.03],[.01,.04]])
    with pytest.raises(ValueError, match="positive sample variance"):
        estimate_covariance(constant_column, annualization=252)
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/unit/test_covariance_estimation.py -q`

Expected: FAIL with missing function.

- [ ] **Step 3: Implement the frozen formula**

Port the Ledoit-Wolf 2003 constant-correlation `pi_hat`, `rho_hat`, `gamma_hat` calculation using NumPy only. Preserve `diag(S)`, clamp `delta_sigma` to `[0,1]`, annualize once, derive `rho` from final `Sigma`, and do not project to PSD. Freeze reference values in the test from an independently evaluated implementation, not from the function under test.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_covariance_estimation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/strategy_library/estimation/covariance.py tests/unit/test_covariance_estimation.py
git commit -m "feat: add constant correlation covariance"
```

### Task 5: Implement the Pure Validation Gate

**Files:**
- Create: `src/fip/strategy_library/estimation/validation.py`
- Create: `tests/unit/test_estimation_validation.py`

**Interfaces:**
- Produces: `validate_bundle(bundle, policy, factor_observations) -> tuple[ValidationResult, ...]`.
- Consumes: `tuple[FactorRiskObservation, ...]` from Task 2; this task performs no SQL lookup.
- `ValidationResult`: `code`, `severity` (`REJECT|WARNING`), `status` (`PASSED|FAILED`), `detail`.

- [ ] **Step 1: Write one failing test per blocking class**

```python
@pytest.mark.parametrize("mutation,code", [
    ("too_few_rows", "MIN_T_OVER_N"),
    ("nan", "NON_FINITE"),
    ("asymmetric", "SIGMA_NOT_SYMMETRIC"),
    ("zero_variance", "NON_POSITIVE_VARIANCE"),
    ("negative_eigenvalue", "SIGMA_NOT_PSD"),
    ("bad_correlation", "CORRELATION_OUT_OF_RANGE"),
])
def test_gate_rejects_invalid_bundle(valid_bundle, mutation, code):
    assert failed_code(validate_bundle(mutate(valid_bundle, mutation), POLICY, ())) == code
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/unit/test_estimation_validation.py -q`

Expected: FAIL with missing validation API.

- [ ] **Step 3: Implement all D-7 rules**

Use relative PSD floor `-1e-8 * max(lambda_max, 1e-16)`. Reject non-finite condition numbers and values over `1e6`; warn over `1e4`. Factor comparison is `COMPARABLE` only for exactly one matching candidate; relative error uses `abs(a-b)/max(abs(a),abs(b),1e-16)`. Zero/multiple matches return `NOT_COMPARABLE` WARNING. Return every rule result, including passes, for auditability.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/unit/test_estimation_validation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/strategy_library/estimation/validation.py tests/unit/test_estimation_validation.py
git commit -m "feat: add estimation validation gate"
```

### Task 6: Extend PIT Benchmark and Universe Reads

**Files:**
- Modify: `src/fip/platform/decision_data/pit.py`
- Modify: `src/fip/services/data_service/repositories/benchmark.py`
- Modify: `src/fip/services/fund_service/universe.py`
- Create: `tests/integration/test_benchmark_history.py`
- Modify: `tests/unit/test_universe.py`

**Interfaces:**
- Produces: `BenchmarkResolutionSegment` and `BenchmarkPitRepository.resolve_history(...)` from the spec.
- Produces: `UniverseRepository.load_selected_members_ordered(snapshot_id) -> tuple[int, ...]`.

- [ ] **Step 1: Write failing PIT and ordering tests**

```python
def test_resolve_history_obeys_effective_and_available_time(db_session, benchmark_history):
    context, share_class_id = benchmark_history
    segments = PitDataContext(context, db_session).benchmarks().resolve_history(
        share_class_id, "HYBRID", date(2025, 1, 1), date(2025, 6, 30)
    )
    assert [(x.effective_from, x.effective_to) for x in segments] == [
        (date(2025, 1, 1), date(2025, 4, 1)),
        (date(2025, 4, 1), date(2025, 7, 1)),
    ]
    assert [(x.index_id, x.weight) for x in segments[0].components] == [
        (101, Decimal("0.6")), (202, Decimal("0.4"))
    ]

def test_selected_members_are_sorted(repository):
    assert repository.load_selected_members_ordered(SNAPSHOT_ID) == (3, 8, 21)
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/integration/test_benchmark_history.py tests/unit/test_universe.py -q`

Expected: FAIL because both query APIs are missing.

- [ ] **Step 3: Implement PIT history and ordering**

The history SQL selects mappings whose effective intervals overlap the requested range and whose `available_at <= visible_until`, applies share-class precedence over classification fallback per segment, and returns half-open non-overlapping segments. Include component weights; index observation versions are captured when materializing each segment. Do not add `decision_at` parameters to repository methods.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/integration/test_benchmark_history.py tests/unit/test_universe.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/platform/decision_data/pit.py src/fip/services/data_service/repositories/benchmark.py src/fip/services/fund_service/universe.py tests/integration/test_benchmark_history.py tests/unit/test_universe.py
git commit -m "feat: expose PIT benchmark history"
```

### Task 7: Assemble ABSOLUTE and EXCESS Inputs

**Files:**
- Create: `src/fip/services/portfolio_service/estimation/inputs.py`
- Create: `tests/integration/test_estimation_inputs.py`

**Interfaces:**
- Produces: `EstimationInputAssembler.load(context, snapshot_id, policy) -> tuple[EstimationBasisInput, ...]` ordered ABSOLUTE then EXCESS.
- `EstimationBasisInput` includes basis, matrix, order, dates, exclusions, dropped dates, full lineage, observation fingerprint, and basis fingerprint.
- Defines the service-owned Protocol:

```python
class FactorRiskCrossCheckProvider(Protocol):
    def load_candidates(
        self, share_class_id: int, decision_id: str
    ) -> tuple[FactorRiskObservation, ...]: ...
```

- [ ] **Step 1: Write failing input tests**

```python
def test_basis_inputs_are_independently_aligned(db_session):
    absolute, excess = assembler(db_session).load(CONTEXT, SNAPSHOT_ID, POLICY)
    assert absolute.return_basis == "ABSOLUTE"
    assert excess.return_basis == "EXCESS"
    assert absolute.observation_dates != excess.observation_dates
    assert SWITCH_DATE not in excess.observation_dates
    assert SWITCH_DATE in absolute.observation_dates
```

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/pytest tests/integration/test_estimation_inputs.py -q`

Expected: FAIL with missing assembler.

- [ ] **Step 3: Implement PIT input assembly**

Load each share class's `fund_id`, resolve its PIT classification through
`PitDataContext.classifications().current(fund_id)`, and use that classification for Benchmark
fallback. Use `PitDataContext` APIs only for time-sensitive values. Calculate simple returns only
between adjacent available NAV observations; an explicit unavailable observation breaks the chain.
Build each segment's composite Benchmark series without filling or weight renormalization, delete
each mapping/weight switch return date, then align each basis independently. Canonicalize the exact
lineage fields listed in spec section 7 before hashing.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/integration/test_estimation_inputs.py -q`

Expected: PASS. Also run `.venv/bin/pytest tests/fitness/test_architecture.py -q` and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/services/portfolio_service/estimation/inputs.py tests/integration/test_estimation_inputs.py
git commit -m "feat: assemble estimation PIT inputs"
```

### Task 8: Add ORM Models and Migration

**Files:**
- Create: `src/fip/services/portfolio_service/estimation/models.py`
- Create: `db/migrations/versions/0027_plan3_estimation.py`
- Modify: `db/migrations/env.py`
- Modify: `tests/integration/test_autogenerate_gate.py`
- Create: `tests/integration/test_plan3_estimation_migration.py`
- Modify: `tests/integration/test_temporal_constraints.py`

**Interfaces:**
- Produces the seven tables and exact keys from spec section 6.
- Run idempotency unique key includes all seven identity columns.

- [ ] **Step 1: Write failing metadata and constraint tests**

```python
def test_plan3_tables_exist(db_session):
    names = inspect(db_session.connection()).get_table_names(schema="portfolio")
    assert set(PLAN3_TABLES) <= set(names)

def test_run_idempotency_is_database_enforced(db_session):
    db_session.add_all([make_run(), make_run()])
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/integration/test_plan3_estimation_migration.py -q`

Expected: FAIL because the tables do not exist.

- [ ] **Step 3: Implement ORM and migration together**

Use `portfolio` schema. Store per-fund numeric values as canonical strings rather than `Numeric`; matrix payload uses JSONB lower triangle. `input_lineage_fingerprint` is nullable only while status is `PENDING`, `RUNNING`, or `FAILED`, and required for final business statuses via a CHECK constraint. Add status/basis/severity checks, nonnegative count checks, FKs with `RESTRICT`, result-child deletes with `CASCADE`, indexes for approved ABSOLUTE lookup, and all ORM equivalents. Register models in both Alembic and autogenerate test imports; append new CHECK expressions to the golden constraint snapshot.

- [ ] **Step 4: Run migration gates**

Run: `.venv/bin/pytest tests/integration/test_plan3_estimation_migration.py tests/integration/test_autogenerate_gate.py tests/integration/test_temporal_constraints.py -q`

Expected: PASS with zero metadata drift.

- [ ] **Step 5: Commit**

```bash
git add src/fip/services/portfolio_service/estimation/models.py db/migrations/versions/0027_plan3_estimation.py db/migrations/env.py tests/integration/test_plan3_estimation_migration.py tests/integration/test_autogenerate_gate.py tests/integration/test_temporal_constraints.py
git commit -m "feat: persist estimation runs and results"
```

### Task 9: Implement Run and Result Repositories

**Files:**
- Create: `src/fip/services/portfolio_service/estimation/repositories.py`
- Create: `tests/integration/test_estimation_repositories.py`

**Interfaces:**
- Produces: `EstimationRunRepository.start(identity) -> StartRunResult`.
- Produces: `retry_failed(run_id)`, `complete(run_id, bundles, fingerprint)`, `reject(...)`, `fail(run_id, error_code)`.
- Produces: `ApprovedEstimationProvider.load(run_id) -> ApprovedEstimation`.

- [ ] **Step 1: Write failing lifecycle and mixed-basis tests**

```python
def test_same_key_with_different_fingerprint_conflicts(repository):
    run_id = repository.complete_run(IDENTITY, "a" * 64, BUNDLES)
    with pytest.raises(EstimationRunConflict):
        repository.complete_run(IDENTITY, "b" * 64, BUNDLES)

def test_approved_provider_cannot_mix_basis_or_run(repository):
    with pytest.raises(EstimationIntegrityError):
        repository.load_approved(MIXED_RESULT_RUN_ID)
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/integration/test_estimation_repositories.py -q`

Expected: FAIL with missing repository.

- [ ] **Step 3: Implement locking, state transitions and payload checks**

Use the database unique key plus `SELECT ... FOR UPDATE`. Ordinary calls return an existing final/RUNNING Run; explicit retry alone performs `FAILED -> RUNNING`. Before save, assert exact order and dimensions across Return/Risk/Covariance. The approved query filters final approved Run and ABSOLUTE basis, then verifies checksum and decodes lower triangle.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/integration/test_estimation_repositories.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/services/portfolio_service/estimation/repositories.py tests/integration/test_estimation_repositories.py
git commit -m "feat: add estimation repositories"
```

### Task 10: Add Factor Cross-Check Adapter

**Files:**
- Create: `src/fip/services/factor_service/estimation_adapter.py`
- Create: `tests/integration/test_factor_risk_cross_check.py`
- Modify: `tests/fitness/test_architecture.py`

**Interfaces:**
- Implements the `FactorRiskCrossCheckProvider.load_candidates(share_class_id, decision_id)` Protocol without being imported by portfolio_service.
- Returns all `F-RISK-001` candidates with Factor IDs and lineage needed by Task 5.

- [ ] **Step 1: Write failing candidate and dependency tests**

```python
def test_adapter_returns_all_candidates_in_stable_order(db_session, factor_risk_candidates):
    share_class_id = factor_risk_candidates
    candidates = SqlFactorRiskCrossCheckProvider(db_session).load_candidates(
        share_class_id, "decision-1"
    )
    assert tuple(x.factor_value_id for x in candidates) == (101, 205)

def test_portfolio_service_has_no_factor_service_import():
    assert not portfolio_factor_imports()
```

- [ ] **Step 2: Verify the tests fail**

Run: `.venv/bin/pytest tests/integration/test_factor_risk_cross_check.py tests/fitness/test_architecture.py -q`

Expected: FAIL because the adapter is missing; architecture test remains green.

- [ ] **Step 3: Implement the read-only adapter**

Join `FactorRun`, `FactorValue`, `FactorVersion`, and `FactorDefinition`; filter `decision_id`, `share_class_id`, and `factor_id="F-RISK-001"`; never select by latest row. Parse lineage conservatively: missing `ddof`, annualization, return type, or observation dates produces a candidate that cannot be `COMPARABLE`. Composition root code passes this adapter into `EstimationService`; no portfolio module imports its concrete class.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/integration/test_factor_risk_cross_check.py tests/fitness/test_architecture.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/services/factor_service/estimation_adapter.py tests/integration/test_factor_risk_cross_check.py tests/fitness/test_architecture.py
git commit -m "feat: expose factor risk cross check"
```

### Task 11: Orchestrate Estimation and Publish Approved Results

**Files:**
- Create: `src/fip/services/portfolio_service/estimation/service.py`
- Modify: `src/fip/services/portfolio_service/estimation/__init__.py`
- Create: `tests/integration/test_estimation_service.py`
- Create: `tests/repro/test_estimation_reproducibility.py`

**Interfaces:**
- Produces: `EstimationService.run(context, universe_snapshot_id) -> EstimationRunResult`.
- Produces: transaction A/B/C behavior from spec D-9.
- Exports: `ApprovedEstimationProvider`, `ApprovedEstimation` with annualized `mu`, `Sigma`, order and version closure.

- [ ] **Step 1: Write failing end-to-end service tests**

```python
def test_absolute_success_and_excess_failure_is_warning(service):
    result = service.run(CONTEXT, SNAPSHOT_ID)
    assert result.status == "COMPLETED_WITH_WARNING"
    assert result.approved_for_optimization is True
    assert result.basis_statuses["EXCESS"] == "REJECTED"

def test_unhandled_failure_rolls_back_results_and_marks_run_failed(service):
    run_id = service.run_with_fault(CONTEXT, SNAPSHOT_ID)
    assert load_run(run_id).status == "FAILED"
    assert result_row_count(run_id) == 0
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/integration/test_estimation_service.py -q`

Expected: FAIL with missing service.

- [ ] **Step 3: Implement orchestration and result publication**

`EstimationService.__init__` accepts the `FactorRiskCrossCheckProvider` Protocol from Task 7. For
each basis and included share class, call `load_candidates(share_class_id, context.decision_id)` and
pass the returned DTOs to Task 5; the service never imports the SQL adapter. Construct all remaining
dependencies from immutable policies and their persisted version IDs. Transaction A starts the Run;
transaction B loads both basis inputs, calculates, validates, persists audit results and sets the
final state atomically; transaction C marks uncaught failures. A rejected ABSOLUTE always makes Run
`REJECTED`; EXCESS cannot set approval true. Return existing final Runs only after rebuilding and
matching the lineage fingerprint.

- [ ] **Step 4: Add and run reproducibility tests**

The repro test runs the real PIT-backed service twice for one historical decision, asserts one business Run, identical order/checksums/status/exclusions, and decoded elementwise absolute difference `<=1e-10`.

Run: `.venv/bin/pytest tests/integration/test_estimation_service.py tests/repro/test_estimation_reproducibility.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fip/services/portfolio_service/estimation/service.py src/fip/services/portfolio_service/estimation/__init__.py tests/integration/test_estimation_service.py tests/repro/test_estimation_reproducibility.py
git commit -m "feat: orchestrate return risk estimation"
```

### Task 12: Close Architecture, Documentation, and Quality Gates

**Files:**
- Modify: `docs/02-architecture/02-service-architecture.md`
- Modify: `docs/02-architecture/03-data-architecture.md`
- Modify: `docs/10-api/04-portfolio-api.md`
- Modify: `docs/11-database/03-erd.md`
- Modify: `docs/11-database/04-database-design.md`
- Modify: `.superpowers/sdd/2026-09-10-plan3-return-risk-estimation/progress.md`

**Interfaces:**
- Documents the actual seven-table schema, lower-triangle payload, annualized Stage ⑥ contract, statuses, and Plan-3B deferral.

- [ ] **Step 1: Update documentation from implemented interfaces**

Remove obsolete names such as `expected_return`, full-square matrix payloads, and `APPROVED` Run status. Document API status as approval semantics, not an ORM status enum.

- [ ] **Step 2: Run focused and full tests**

```bash
.venv/bin/pytest tests/unit -q
.venv/bin/pytest tests/fitness -q
.venv/bin/pytest tests/integration -m integration -q
.venv/bin/pytest tests/repro/test_estimation_reproducibility.py -q
.venv/bin/ruff check src tests
.venv/bin/mypy
```

Expected: all commands exit 0.

- [ ] **Step 3: Verify migration drift explicitly**

Run: `.venv/bin/pytest tests/integration/test_autogenerate_gate.py tests/integration/test_temporal_constraints.py -q`

Expected: PASS; ORM metadata and migrated database have zero diff, CHECK snapshot matches.

- [ ] **Step 4: Review spec coverage**

Map each acceptance criterion in spec section 8 to at least one test. Confirm no Task implements Plan-3B, optimizer logic, ML, transaction cost, or backtest timeline.

- [ ] **Step 5: Commit**

```bash
git add docs .superpowers/sdd
git commit -m "docs: publish estimation contracts"
```

## Execution Order

```text
1 -> 2 -> 3 -> 4 -> 5
1 -> 6 -> 7 -> 10
2 + 5 + 7 -> 8 -> 9
5 + 9 + 10 -> 11 -> 12
```

Tasks 3, 4, and 6 may run in parallel after Tasks 1 and 2. Task 10 starts after Task 7 defines the Protocol. Tasks 8, 9, and 11 remain sequential because they share the persistent Run contract.

## Definition of Done

Plan-3 is complete only when a real PIT-backed historical decision produces an approved ABSOLUTE annualized `mu`/`Sigma` bundle, an independently aligned EXCESS audit bundle, complete lineage and Validation records, and a second identical invocation returns the same business Run with decoded numeric error `<=1e-10`. Pure algorithm tests without real Service assembly do not satisfy completion.