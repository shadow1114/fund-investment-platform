# Plan-2 Evaluation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Git restriction:** Do not run Git commands, create commits, switch branches, or create worktrees unless the user explicitly authorizes Git operations. Each task ends with a non-Git review checkpoint.

**Goal:** 在 Plan-1 的 PIT 数据底座上交付可按历史决策时点复现的 Benchmark、Peer Group、15 因子、OOS 有效性检验、正式评分、排名、Tier 与 Universe 闭环。

**Architecture:** Plan-2 按 `data_service -> fund_service -> factor_service -> fund_service` 单向推进。数据库访问留在 Service/Repository 层，计算规则放入无 I/O 的 `strategy_library`；所有历史读取通过构造期绑定 `DecisionExecutionContext` 的 `PitDataContext`，所有结果引用真实 Policy/Metric/Peer Group 版本。

**Tech Stack:** Python 3.12、SQLAlchemy 2、Alembic、PostgreSQL、NumPy/Pandas、pytest、Ruff、mypy、PyYAML。

**Spec:** `docs/superpowers/specs/2026-09-08-plan2-evaluation-pipeline-design.md`

## Global Constraints

- 本计划只覆盖 M1.2–M1.4；不实现对外 API、前端、组合优化、回测编排或官方 Benchmark 文档自动解析。
- 不执行任何 Git 操作，除非用户在执行阶段明确授权。
- 全程 TDD：每条保护性测试必须先在实现前失败，再以最小实现转绿。
- Python 必须使用 3.12；项目命令从 `.venv/bin/` 执行。
- 配置叶子必须精确包含 `value`、`status`、`source`；`value` 不得是映射。
- 正式 Score 必须依赖 OOS 有效性结论；`UNAVAILABLE`、`INVALID`、`VALIDATION_PENDING` 不得互相替代。
- 不得用 0、均值或上期值填补 `UNAVAILABLE` 数据。
- Peer Group 构建不得读取 Score、Ranking 或 Universe。
- `strategy_library` 不得依赖 SQLAlchemy、HTTP、AKShare 或 `RuntimeMode`。
- Expense Ratio 是 Fund Data，不注册 Factor；R² 只展示，不评分。
- 四类 Profile 固定使用 `PROFILE_FIXED_V1`；每组权重之和必须为 1。
- 数据库 CHECK 必须同时维护 ORM 声明、Alembic 迁移和约束快照。
- 迁移文件必须固化当时的 SQL，不从活代码导入约束常量。

---

## File Map

### Existing files to modify

- `src/fip/platform/decision_data/pit.py`: 统一 PIT 可见截止时刻并暴露数据 Repository。
- `src/fip/services/data_service/repositories/nav.py`: 消费统一 `visible_until`。
- `src/fip/services/data_service/normalization/backfill.py`: 删除重复的时点翻译。
- `src/fip/services/data_service/ingest.py`: 数据源优先级、批处理隔离和新增数据集编排。
- `src/fip/services/data_service/models/fund.py`: `base_currency`、区间唯一性和经理任职约束。
- `src/fip/services/data_service/models/market.py`: Benchmark 市场实体注册。
- `src/fip/services/data_service/models/governance.py`: Policy Version 唯一性与版本装载支持。
- `db/migrations/env.py`: 注册新增 ORM 模块。
- `tests/integration/check_constraints.snapshot`: 同步新增 CHECK 表达式。

### New production modules

- `src/fip/services/data_service/models/benchmark.py`: Benchmark 五表。
- `src/fip/services/data_service/repositories/{classification,fee,risk_free_rate,benchmark}.py`: PIT 数据访问。
- `src/fip/services/data_service/batch.py`: 批处理结果与对象级失败隔离。
- `src/fip/services/fund_service/policy.py`: Evaluation/Validation Policy 解析和持久化。
- `src/fip/services/fund_service/peer_group/{models,builder,repository}.py`: Peer Group 快照。
- `src/fip/services/factor_service/models.py`: Factor 五表。
- `src/fip/services/factor_service/{calculation,validation,repositories}.py`: Factor 编排与持久化。
- `src/fip/strategy_library/{factor_types,returns,risk,risk_adjusted,relative,stability,normalization,validation,scoring,ranking,universe}.py`: 纯计算规则。
- `src/fip/services/fund_service/models.py`: Evaluation 十表。
- `src/fip/services/fund_service/{scoring,ranking,tier,universe,pipeline,repositories}.py`: 评价闭环编排与原子写入。

### Migration strategy

- `0016_plan2_data_contracts.py`: Plan-1 交接修复、`base_currency`、区间索引与排除约束。
- `0017_benchmark_and_policy.py`: Benchmark 五表及 Policy Version 约束。
- `0018_peer_group.py`: Peer Group 两表。
- `0019_factor_pipeline.py`: Factor 五表。
- `0020_evaluation_pipeline.py`: Evaluation 十表。

每个迁移单独升级、降级、再升级；不得把五个迁移压成一个不可审查的大文件。

---

### Task 1: 收紧 Plan-1 PIT 可见性契约

**Files:**
- Modify: `src/fip/platform/decision_data/pit.py`
- Modify: `src/fip/services/data_service/repositories/nav.py`
- Modify: `src/fip/services/data_service/normalization/backfill.py`
- Modify: `tests/unit/test_pit_port.py`
- Create: `tests/unit/test_visible_until.py`
- Modify: `tests/integration/test_pit_nav_repository.py`

**Interfaces:**
- Produces: `PitDataContext.visible_until: datetime`
- Produces: `visible_until_for(decision_at: date) -> datetime`
- Produces: `NavPoint.adjusted_nav: Decimal`
- Produces: `NavPoint.chain_availability_quality: str`
- Consumes: `DecisionExecutionContext.decision_at`

- [ ] **Step 1: 为唯一时点翻译规则写失败测试**

```python
from datetime import UTC, date, datetime, time

from fip.platform.decision_data.pit import visible_until_for

def test_visible_until_is_utc_end_of_decision_day():
    assert visible_until_for(date(2026, 9, 8)) == datetime.combine(
        date(2026, 9, 8), time.max, tzinfo=UTC
    )
```

- [ ] **Step 2: 运行测试并确认导入失败**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py -v`

Expected: FAIL，原因是 `visible_until_for` 尚不存在。

- [ ] **Step 3: 增加唯一实现并从上下文暴露**

```python
def visible_until_for(decision_at: dt.date) -> dt.datetime:
    return dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)

class PitDataContext:
    @property
    def visible_until(self) -> dt.datetime:
        return visible_until_for(self.decision_at)
```

将 `SqlNavPitRepository` 构造参数改为 `visible_until: datetime`，`PitDataContext.navs()` 传入 `self.visible_until`；`backfill_adjusted_nav()` 调用同一 helper，不再复制 `datetime.combine(...)`。

同时将 `NavPoint.adjusted_nav` 收紧为 `Decimal`。保留每行自身的 `availability_quality`，新增
`chain_availability_quality` 表达从序列起点到该点参与复权计算的 NAV/Distribution 中最弱质量，
质量顺序固定为 `EXACT > DERIVED > INFERRED`，不让单行 `EXACT` 掩盖上游链路的 `INFERRED`。

- [ ] **Step 4: 锁住 Repository 无查询时点参数的性质**

扩展 `tests/unit/test_pit_port.py`，断言 `NavPitRepository.adjusted_nav_series` 仍不接受 `decision_at`、`as_of`、`available_at`。扩展 Repository 集成测试，断言：

```python
assert all(point.adjusted_nav is not None for point in result)
assert result[-1].availability_quality == "EXACT"
assert result[-1].chain_availability_quality == "INFERRED"
```

保持现有 fail-closed 语义：链路中任一点无法计算时整段抛 `AdjustedNavUnavailable`；前缀可用性不在 Plan-2 内另造一套半结果语义。

- [ ] **Step 5: 运行局部验证**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py tests/unit/test_pit_port.py tests/integration/test_pit_nav_repository.py -v`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认全仓只有 `visible_until_for()` 定义 `decision_at -> UTC 日终` 规则；记录测试结果，不执行 Git 操作。

---

### Task 2: 把时序模型约束变成可执行架构契约

**Files:**
- Create: `tests/fitness/test_model_temporal_contracts.py`
- Modify: `tests/fitness/test_architecture.py`

**Interfaces:**
- Consumes: `Base.registry.mappers`
- Consumes: `IntervalMixin`、`VersionedMixin`、`TIME_ORDER_SQL`、`INTERVAL_TIME_ORDER_SQL`
- Produces: CI 中对错误约束生成器和新增 ORM 注册遗漏的自动失败。

- [ ] **Step 1: 编写可被错误模型证伪的测试 helper**

```python
def assert_temporal_contract(model: type[Base]) -> None:
    checks = {
        str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    if issubclass(model, IntervalMixin):
        assert INTERVAL_TIME_ORDER_SQL in checks
        assert any("valid_to IS NULL OR valid_to > valid_from" in sql for sql in checks)
    elif issubclass(model, VersionedMixin):
        assert TIME_ORDER_SQL in checks
```

在测试内声明一个刻意继承 `IntervalMixin` 却使用 `temporal_check_constraints()` 的临时模型，先确认 helper 会失败，再遍历真实 mapper。

- [ ] **Step 2: 运行测试并确认错误模型触发失败**

Run: `.venv/bin/pytest tests/fitness/test_model_temporal_contracts.py -v`

Expected: FAIL，错误指出临时 Interval 模型使用了版本化约束。

- [ ] **Step 3: 将负例改为显式 `pytest.raises(AssertionError)`，遍历真实模型**

```python
with pytest.raises(AssertionError):
    assert_temporal_contract(BrokenIntervalModel)

for mapper in Base.registry.mappers:
    assert_temporal_contract(mapper.class_)
```

- [ ] **Step 4: 运行架构测试**

Run: `.venv/bin/pytest tests/fitness/test_model_temporal_contracts.py tests/fitness/test_architecture.py -v`

Expected: PASS。

- [ ] **Step 5: 人工检查点**

确认测试检查 SQL 文本而非只检查 constraint 名称；不执行 Git 操作。

---

### Task 3: 补齐区间表约束、索引与 Alembic 漂移闸门

**Files:**
- Create: `db/migrations/versions/0016_plan2_data_contracts.py`
- Modify: `src/fip/services/data_service/models/fund.py`
- Create: `tests/integration/test_alembic_autogenerate.py`
- Modify: `tests/integration/test_fund_dimensions.py`
- Modify: `tests/integration/check_constraints.snapshot`

**Interfaces:**
- Produces: `FundShareClass.base_currency: str`
- Produces: 同一基金与同一经理的任职区间不重叠。
- Produces: 分类、状态、费率的开放区间业务键唯一。

- [ ] **Step 1: 写数据库不变量失败测试**

新增测试覆盖：

```python
def test_same_manager_assignment_cannot_overlap(db_session): ...
def test_different_managers_can_overlap_for_co_management(db_session): ...
def test_only_one_open_classification_per_scheme(db_session): ...
def test_only_one_open_fee_per_type(db_session): ...
def test_share_class_has_base_currency(db_session): ...
```

第一条插入同一 `(fund_id, manager_id)` 的重叠 `daterange` 并期望 `IntegrityError`；第二条使用不同 manager 并期望成功。

- [ ] **Step 2: 运行测试确认缺失约束**

Run: `.venv/bin/pytest tests/integration/test_fund_dimensions.py -v -m integration`

Expected: FAIL，重叠任职被数据库接受或 `base_currency` 不存在。

- [ ] **Step 3: 在 ORM 与 0016 迁移中镜像结构**

迁移顺序：增加 nullable `base_currency` -> 将既有行填为显式 M1 默认 `CNY` -> 设置 `NOT NULL`；再创建：

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE fund.fund_manager_assignment
ADD CONSTRAINT ex_fma_same_manager_non_overlapping
EXCLUDE USING gist (
  fund_id WITH =,
  manager_id WITH =,
  daterange(valid_from, valid_to, '[)') WITH &&
);
CREATE INDEX idx_fma_manager_valid_from
ON fund.fund_manager_assignment (manager_id, valid_from);
CREATE INDEX idx_fma_fund_valid_from
ON fund.fund_manager_assignment (fund_id, valid_from);
```

开放区间唯一索引分别使用：

```text
fund_classification_history: (fund_id, classification_scheme) WHERE valid_to IS NULL
fund_status_history: (share_class_id) WHERE valid_to IS NULL
fund_fee: (share_class_id, fee_type) WHERE valid_to IS NULL
```

ORM 中逐项声明相同名称、列顺序和 `postgresql_where`。

- [ ] **Step 4: 建立 autogenerate 零漂移测试**

`tests/integration/test_alembic_autogenerate.py` 使用 `MigrationContext.configure(connection)` 和 `compare_metadata(context, Base.metadata)`；过滤规则复用 `db/migrations/env.py` 的 `include_object`，断言 diff 为空。

- [ ] **Step 5: 验证迁移往返和约束**

Run: `.venv/bin/alembic -x db=test upgrade head`

Run: `.venv/bin/alembic -x db=test downgrade 0015 && .venv/bin/alembic -x db=test upgrade head`

Run: `.venv/bin/pytest tests/integration/test_fund_dimensions.py tests/integration/test_temporal_constraints.py tests/integration/test_alembic_autogenerate.py -v -m integration`

Expected: PASS，autogenerate diff 为空。

- [ ] **Step 6: 人工检查点**

核对 ORM、迁移和 snapshot 三处约束完全一致；不执行 Git 操作。

---

### Task 4: 下沉批处理错误隔离并版本化披露时滞

**Files:**
- Create: `src/fip/services/data_service/batch.py`
- Modify: `src/fip/services/data_service/ingest.py`
- Modify: `src/fip/platform/cli.py`
- Create: `tests/integration/test_ingest_batch_isolation.py`
- Modify: `tests/integration/test_ingest_service.py`
- Modify: `tests/integration/test_cli.py`

**Interfaces:**
- Produces: `BatchItemStatus = SUCCESS | UNAVAILABLE | INVALID | FAILED`
- Produces: `FundIngestSubject(share_class_id: int, provider_fund_id: str)`
- Produces: `BatchItemResult(subject_id: int, status: BatchItemStatus, error: str | None)`
- Produces: `BatchIngestResult(items: tuple[BatchItemResult, ...])`
- Produces: `IngestService.ingest_nav_batch(subjects: Sequence[FundIngestSubject]) -> BatchIngestResult`
- Consumes: `DataSourcePriority.disclosure_lag_days`

- [ ] **Step 1: 写一只失败不阻断整批的集成测试**

构造三个 subject，使第二个在 `rebuild_adjusted_nav()` 抛 `AdjustedNavUnavailable`；断言第一、第三个为 `SUCCESS`，第二个为 `UNAVAILABLE`，三项结果顺序稳定。

- [ ] **Step 2: 运行测试确认异常仍中断整批**

Run: `.venv/bin/pytest tests/integration/test_ingest_batch_isolation.py -v -m integration`

Expected: FAIL，第三个 subject 未执行。

- [ ] **Step 3: 实现对象级 savepoint 与状态映射**

```python
for subject in subjects:
    try:
        with self._session.begin_nested():
            self.ingest_nav(subject.share_class_id, subject.provider_fund_id)
            self.ingest_distributions(subject.share_class_id, subject.provider_fund_id)
            self.rebuild_adjusted_nav(subject.share_class_id)
    except AdjustedNavUnavailable as exc:
        results.append(BatchItemResult(subject.share_class_id, UNAVAILABLE, str(exc)))
    except ValueError as exc:
        results.append(BatchItemResult(subject.share_class_id, INVALID, str(exc)))
    else:
        results.append(BatchItemResult(subject.share_class_id, SUCCESS, None))
```

未知系统异常不得吞掉；继续向上抛出。CLI 只负责展示 `BatchIngestResult`，不再承担领域异常隔离。

- [ ] **Step 4: 从 `DataSourcePriority` 读取披露时滞**

增加 `IngestService` 工厂查询 `(dataset_id, field_name, rule_version)` 对应规则；缺失规则响亮失败，不回退 `DISCLOSURE_LAG_DAYS`。保留 CLI 常量仅到迁移期，测试转绿后删除。

- [ ] **Step 5: 运行局部测试**

Run: `.venv/bin/pytest tests/integration/test_ingest_batch_isolation.py tests/integration/test_ingest_service.py tests/integration/test_cli.py -v -m integration`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认 `UNAVAILABLE` 与系统异常走不同路径，且已成功对象不因邻居失败回滚；不执行 Git 操作。

---

### Task 5: 建立分类、费率和无风险利率 PIT 数据面

**Files:**
- Modify: `src/fip/platform/decision_data/pit.py`
- Create: `src/fip/services/data_service/repositories/classification.py`
- Create: `src/fip/services/data_service/repositories/fee.py`
- Create: `src/fip/services/data_service/repositories/risk_free_rate.py`
- Create: `src/fip/strategy_library/fund_data.py`
- Create: `src/fip/strategy_library/rates.py`
- Create: `tests/integration/test_dimension_pit_repositories.py`
- Modify: `tests/unit/test_pit_port.py`
- Create: `tests/unit/test_fund_data.py`
- Create: `tests/unit/test_rates.py`

**Interfaces:**
- Produces: `ClassificationPoint(classification_code, valid_from, availability_quality)`
- Produces: `FeePoint(fee_type, rate, valid_from, availability_quality)`
- Produces: `RiskFreeRatePoint(effective_at, tenor, rate, version, availability_quality)`
- Produces: `PitDataContext.classifications()`、`.fees()`、`.risk_free_rates()`

- [ ] **Step 1: 写三个 Repository 的 PIT 失败测试**

每类数据都准备：决策日前可见版本、决策日后才披露版本、同一业务时点的高版本；断言只返回 `available_at <= visible_until` 中版本最高者。

- [ ] **Step 2: 运行测试确认 Repository 不存在**

Run: `.venv/bin/pytest tests/integration/test_dimension_pit_repositories.py -v -m integration`

Expected: FAIL，模块或 context accessor 尚不存在。

- [ ] **Step 3: 实现 context-bound Protocol 与 SQL Repository**

```python
class ClassificationPitRepository(Protocol):
    def current(self, fund_id: int) -> ClassificationPoint | None: ...

class FeePitRepository(Protocol):
    def current(self, share_class_id: int) -> tuple[FeePoint, ...]: ...

class RiskFreeRatePitRepository(Protocol):
    def series(
        self, currency: str, tenor: str, date_from: dt.date, date_to: dt.date
    ) -> tuple[RiskFreeRatePoint, ...]: ...
```

构造器只接受 `(session, visible_until)`；方法不接受任何查询时点参数。

- [ ] **Step 4: 实现费率聚合和 Rf 期限解析的纯函数测试**

在两个不依赖后续 Factor 模块的纯计算文件中增加：

```python
# strategy_library/fund_data.py
def expense_ratio(fees: Sequence[FeePoint]) -> Decimal: ...

# strategy_library/rates.py
def interpolate_rate(
    lower: TenorRate, upper: TenorRate, target_days: int
) -> Decimal: ...
```

只合计 management/custodian/sales-service；精确期限缺失时仅相邻期限线性插值，跨币种输入抛 `ValueError`。

- [ ] **Step 5: 运行局部验证**

Run: `.venv/bin/pytest tests/unit/test_pit_port.py tests/unit/test_fund_data.py tests/unit/test_rates.py tests/integration/test_dimension_pit_repositories.py -v`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认所有新 PIT 方法均无法由调用方传入或省略 `decision_at`；不执行 Git 操作。

---

### Task 6: 建立 Benchmark 五表与 PIT 解析

**Files:**
- Create: `src/fip/services/data_service/models/benchmark.py`
- Create: `src/fip/services/data_service/repositories/benchmark.py`
- Modify: `src/fip/platform/decision_data/pit.py`
- Modify: `db/migrations/env.py`
- Create: `db/migrations/versions/0017_benchmark_and_policy.py`
- Create: `tests/integration/test_benchmark_repository.py`
- Modify: `tests/integration/test_temporal_constraints.py`
- Modify: `tests/integration/check_constraints.snapshot`

**Interfaces:**
- Produces: `BenchmarkDefinition`、`BenchmarkIndex(index_type: PRICE | TOTAL_RETURN | FULL_PRICE)`、`BenchmarkComponent`、`BenchmarkMapping`、`BenchmarkIndexValue`
- Produces: `BenchmarkResolution(benchmark_id, components, mapping_source, mapping_version, status)`
- Produces: `BenchmarkPitRepository.resolve(share_class_id, classification_code)`
- Produces: `BenchmarkPitRepository.index_series(index_id, date_from, date_to)`

- [ ] **Step 1: 写映射优先级和 PIT 失败测试**

覆盖基金级人工映射优先于分类默认、未来披露映射不可见、Composite 权重和必须为 1、
任一必需成分在某日缺失时该日整体 `UNAVAILABLE` 且不得重归一、无映射返回
`BENCHMARK_UNAVAILABLE`。另断言 Active/Passive 默认使用 `CSI_300_TOTAL_RETURN`、Bond 使用
`CHINA_BOND_COMPOSITE_FULL_PRICE`、Hybrid 保留 60/40 两个 Component；指定类型不可得时
不得降级为其他指数类型。

- [ ] **Step 2: 运行测试确认表与 Repository 不存在**

Run: `.venv/bin/pytest tests/integration/test_benchmark_repository.py -v -m integration`

Expected: FAIL。

- [ ] **Step 3: 实现五张 ORM 表及 0017 迁移**

`benchmark_definition` 表示平台逻辑基准；`benchmark_index` 表示 Provider 指数标识；`benchmark_component` 保存复合成分和 Decimal 权重；`benchmark_mapping` 使用 `IntervalMixin` 保存基金级或分类级规则；`benchmark_index_value` 使用 `VersionedMixin` 保存指数值。

数据库约束至少包括：component 权重 `(0, 1]`、同一 benchmark 成分唯一、映射 scope 字段一致性、`index_type` 非空且支持 `PRICE/TOTAL_RETURN/FULL_PRICE`、指数值正数、PIT 查询索引。

- [ ] **Step 4: 实现严格解析顺序**

```python
def resolve(self, share_class_id: int, classification_code: str) -> BenchmarkResolution:
    fund_mapping = self._fund_mapping(share_class_id)
    if fund_mapping is not None:
        return self._materialize(fund_mapping)
    class_mapping = self._classification_mapping(classification_code)
    if class_mapping is not None:
        return self._materialize(class_mapping)
    return BenchmarkResolution.unavailable("BENCHMARK_UNAVAILABLE")
```

不得自动选择名称相近指数或当前最新映射。

- [ ] **Step 5: 验证迁移、约束和 Repository**

Run: `.venv/bin/alembic -x db=test upgrade head`

Run: `.venv/bin/pytest tests/integration/test_benchmark_repository.py tests/integration/test_temporal_constraints.py tests/integration/test_alembic_autogenerate.py -v -m integration`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认 `benchmark_index` 未因 Plan-2 设计第 4 节简写而遗漏；不执行 Git 操作。

---

### Task 7: 装载并持久化 Evaluation/Validation Policy

**Files:**
- Modify: `src/fip/services/data_service/models/governance.py`
- Create: `src/fip/services/fund_service/policy.py`
- Modify: `db/migrations/versions/0017_benchmark_and_policy.py`
- Modify: `tests/unit/test_config_loader.py`
- Create: `tests/unit/test_evaluation_policy.py`
- Create: `tests/integration/test_policy_version.py`

**Interfaces:**
- Produces: `EvaluationPolicy`、`ValidationPolicy`、`ProfileWeights`、`BetaTargetRanges`、`TrackingErrorRules`
- Produces: `load_evaluation_policy(path: Path, runtime_mode: RuntimeMode) -> EvaluationPolicy`
- Produces: `persist_policy_version(session, policy) -> int`

- [ ] **Step 1: 写配置契约失败测试**

断言四类 Profile 存在、各列和为 1、minimum sample 为 30、MAR 为 `ZERO`、R² 不在评分权重、
Beta 区间分别为 Active `[0.85,1.15]`、Passive `[0.98,1.02]`、Bond/Hybrid `[0.90,1.10]`，
四类 TE 规则完整，未知 Factor ID 被拒绝、Policy `(kind, version_label)` 唯一。

- [ ] **Step 2: 运行测试确认尚无领域 Policy**

Run: `.venv/bin/pytest tests/unit/test_evaluation_policy.py tests/integration/test_policy_version.py -v`

Expected: FAIL。

- [ ] **Step 3: 在现有 `ConfigSet` 之上构造强类型 Policy**

```python
@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    version: str
    minimum_peer_group_size: int
    mar: Decimal
    profile_weights: Mapping[str, Mapping[str, Decimal]]
    beta_target_ranges: Mapping[str, tuple[Decimal, Decimal]]
    tracking_error_rules: Mapping[str, str]
    minimum_scoring_factors: int
    minimum_data_completeness: Decimal
```

解析器必须逐项检查 `ParameterStatus.DECIDED`；不得在领域代码中再次读取 YAML。

- [ ] **Step 4: 持久化不可变版本**

对 `(policy_kind, version_label)` 建唯一约束；相同 content 重入返回既有 ID，不同 content 使用相同版本号时抛 `PolicyVersionConflict`，禁止原地覆盖。

- [ ] **Step 5: 运行局部验证**

Run: `.venv/bin/pytest tests/unit/test_config_loader.py tests/unit/test_evaluation_policy.py tests/integration/test_policy_version.py -v`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认运行期对象只携带强类型值和持久化 version ID；不执行 Git 操作。

---

### Task 8: 构建 Peer Group 快照

**Files:**
- Create: `src/fip/services/fund_service/peer_group/__init__.py`
- Create: `src/fip/services/fund_service/peer_group/models.py`
- Create: `src/fip/services/fund_service/peer_group/builder.py`
- Create: `src/fip/services/fund_service/peer_group/repository.py`
- Create: `src/fip/services/fund_service/models.py`
- Create: `db/migrations/versions/0018_peer_group.py`
- Modify: `db/migrations/env.py`
- Create: `tests/unit/test_peer_group.py`
- Create: `tests/integration/test_peer_group_snapshot.py`
- Modify: `tests/fitness/test_architecture.py`

**Interfaces:**
- Produces: `PeerGroupKey(classification_code, base_currency)`
- Produces: `PeerGroupCandidate(share_class_id, key, grouping_status, status, reason)`
- Produces: `build_peer_group_snapshot(context, candidates, policy_version_id) -> PeerGroupSnapshotResult`
- Produces: `PeerGroupSnapshotRepository.save(result) -> int`

- [ ] **Step 1: 写纯构建规则失败测试**

覆盖四类允许分类、`(classification_code, base_currency)` 分组、未知分类为 `UNSUPPORTED_CLASSIFICATION`、`grouping_status = UNCONFIRMED` 为 `GROUPING_UNCONFIRMED`、相同输入顺序无关、构建函数不接受 Score/Universe。

- [ ] **Step 2: 运行测试确认模块不存在**

Run: `.venv/bin/pytest tests/unit/test_peer_group.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现纯 builder**

```python
def build_peer_groups(
    candidates: Sequence[PeerGroupCandidate],
    supported_profiles: Mapping[str, str],
) -> tuple[PeerGroupDraft, ...]:
    ...
```

输出按 `classification_code, base_currency, share_class_id` 确定性排序；不读取数据库。

- [ ] **Step 4: 建表并实现快照持久化**

`peer_group_snapshot` 保存 `decision_id`、key、policy version、`decision_at`、状态与成员数；`peer_group_member` 保存全体成员及成员状态。相同 decision/key 的重复保存必须幂等或显式冲突，不得生成歧义快照。

- [ ] **Step 5: 扩展架构适应度检查**

扫描 `fund_service/peer_group` imports，禁止依赖 `scoring`、`ranking`、`tier`、`universe`。

- [ ] **Step 6: 运行验证**

Run: `.venv/bin/pytest tests/unit/test_peer_group.py tests/integration/test_peer_group_snapshot.py tests/fitness/test_architecture.py -v`

Expected: PASS。

- [ ] **Step 7: 人工检查点**

确认 unsupported 和 grouping-unconfirmed 对象均被记录且不进入组，不动态创建新 Profile；不执行 Git 操作。

---

### Task 9: 建立 Factor 类型系统与原 10 项纯计算器

**Files:**
- Create: `src/fip/strategy_library/factor_types.py`
- Create: `src/fip/strategy_library/returns.py`
- Create: `src/fip/strategy_library/risk.py`
- Create: `src/fip/strategy_library/risk_adjusted.py`
- Create: `src/fip/strategy_library/stability.py`
- Create: `tests/unit/test_factor_returns.py`
- Create: `tests/unit/test_factor_risk.py`
- Create: `tests/unit/test_factor_risk_adjusted.py`
- Create: `tests/unit/test_factor_stability.py`

**Interfaces:**
- Produces: `FactorStatus = AVAILABLE | UNAVAILABLE | INVALID`
- Produces: `FactorResult(factor_id, value, status, reason, observations)`
- Produces: `ReturnObservation(effective_at, value)`
- Consumes: `MetricParameters`、MAR、Rf。

- [ ] **Step 1: 为原 10 个 Factor 写表驱动失败测试**

覆盖：

```text
F-RET-001 Annualized Return
F-RET-002 Cumulative Return
F-RISK-001 Volatility
F-RISK-002 Downside Volatility
F-RISK-003 Maximum Drawdown
F-RAP-001 Sharpe Ratio
F-RAP-002 Sortino Ratio
F-RAP-003 Calmar Ratio
F-STAB-001 Positive Return Ratio
F-STAB-005 Rolling Sharpe
```

每项至少包含已知数值案例、空输入、窗口不足、零分母和不连续日期。

- [ ] **Step 2: 运行测试确认计算器不存在**

Run: `.venv/bin/pytest tests/unit/test_factor_returns.py tests/unit/test_factor_risk.py tests/unit/test_factor_risk_adjusted.py tests/unit/test_factor_stability.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现日收益公共入口和十项计算**

内部计算统一使用 `float64`，计算和持久化出口不主动舍入或截断；展示精度不属于本层。年化因子与最小观测规则从 Metric Policy 注入，不写死 252 或阈值。零分母返回 `UNAVAILABLE` 和稳定 `reason_code`，不抛系统异常；上游输入为 `INVALID` 时结果传播为 `INVALID` 并告警。

- [ ] **Step 4: 运行计算与架构测试**

Run: `.venv/bin/pytest tests/unit/test_factor_returns.py tests/unit/test_factor_risk.py tests/unit/test_factor_risk_adjusted.py tests/unit/test_factor_stability.py tests/fitness/test_architecture.py -v`

Expected: PASS，strategy library 无 I/O 或 runtime 分支。

- [ ] **Step 5: 人工检查点**

逐一对应 `config/strategy/metric/v1.yaml` 中原 10 个 ID；不执行 Git 操作。

---

### Task 10: 实现 5 个 Benchmark 因子

**Files:**
- Create: `src/fip/strategy_library/relative.py`
- Modify: `src/fip/strategy_library/stability.py`
- Create: `tests/unit/test_factor_relative.py`
- Modify: `tests/unit/test_factor_stability.py`

**Interfaces:**
- Produces: `align_return_series(fund, benchmark, risk_free) -> AlignedReturns`
- Produces: Alpha、Beta、Information Ratio、Tracking Error、R² 的 `FactorResult`
- Consumes: PIT Fund NAV、Benchmark index series、同币种 Rf。

- [ ] **Step 1: 写对齐和回归失败测试**

覆盖完全对齐、共同日期配对观测少于 60、Benchmark 缺失、Rf 缺失、常数 Benchmark 导致回归不可识别、Composite Benchmark 加权收益、R² display-only metadata。

- [ ] **Step 2: 运行测试确认模块不存在**

Run: `.venv/bin/pytest tests/unit/test_factor_relative.py tests/unit/test_factor_stability.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现显式日期内连接和 OLS**

```python
def calculate_relative_factors(
    fund_returns: Sequence[ReturnObservation],
    benchmark_returns: Sequence[ReturnObservation],
    risk_free_rates: Sequence[RiskFreeRatePoint],
    annualization: int,
) -> tuple[FactorResult, ...]:
    ...
```

只在共同日期计算且至少保留 60 个配对观测；不 forward-fill。Alpha 年化，Beta 为斜率，Tracking Error 年化，Information Ratio 使用主动收益，R² 注册 `DISPLAY` usage。

- [ ] **Step 4: 验证 5 项计算**

Run: `.venv/bin/pytest tests/unit/test_factor_relative.py tests/unit/test_factor_stability.py -v`

Expected: PASS。

- [ ] **Step 5: 人工检查点**

确认 `F-REL-002/003/004/005` 和 `F-STAB-002` 全部覆盖，Expense Ratio 未出现在 Factor registry；不执行 Git 操作。

---

### Task 11: 建立 Factor 五表、Run 编排与持久化

**Files:**
- Create: `src/fip/services/factor_service/models.py`
- Create: `src/fip/services/factor_service/repositories.py`
- Create: `src/fip/services/factor_service/calculation.py`
- Create: `db/migrations/versions/0019_factor_pipeline.py`
- Modify: `db/migrations/env.py`
- Create: `tests/integration/test_factor_persistence.py`
- Create: `tests/integration/test_factor_run.py`
- Modify: `tests/integration/test_alembic_autogenerate.py`

**Interfaces:**
- Produces: `FactorDefinition`、`FactorVersion`、`FactorRun`、`FactorValue`、`FactorEffectiveness`
- Produces: `calculate_factor_run(context, peer_group_snapshot_id, input_provider, metric_version_id) -> FactorRunResult`
- Produces: `FactorRepository.save_run(result) -> int`

- [ ] **Step 1: 写版本闭包和幂等失败测试**

断言每个 value 引用 factor version/run、`raw_value` 与 `[0,100]` 的 `normalized_value` 可同时保存、Active/Hybrid TE 允许 `normalized_value = null`、输入质量摘要与 Benchmark/Policy/Metric 版本闭包完整、重跑相同幂等键不重复、不同 version 不覆盖旧值、R² 可保存但 usage 不含 SCORING。

- [ ] **Step 2: 运行测试确认表不存在**

Run: `.venv/bin/pytest tests/integration/test_factor_persistence.py tests/integration/test_factor_run.py -v -m integration`

Expected: FAIL。

- [ ] **Step 3: 实现 0019 与 ORM**

`factor_value` 的业务唯一键覆盖 `share_class_id`、`factor_version_id`、`window`、`effective_at`、`version` 和可空 `evaluation_policy_version_id`；保存 `reason_code`、输入质量摘要、`adjustment_policy_version`、Benchmark Mapping/Definition/Index Value、Metric/Normalization Policy 引用，为 PIT 版本解析建立索引。`factor_effectiveness` 唯一键覆盖 factor version、peer group snapshot、evaluation window、sample split、validation policy version。

- [ ] **Step 4: 实现 Run 编排**

编排只负责从 `PitDataContext` 组装输入、调用纯计算函数、映射状态并保存；单基金 `UNAVAILABLE` 不阻断同组其他基金，`INVALID` 记录对象级失败。

- [ ] **Step 5: 验证迁移和运行结果**

Run: `.venv/bin/alembic -x db=test upgrade head`

Run: `.venv/bin/pytest tests/integration/test_factor_persistence.py tests/integration/test_factor_run.py tests/integration/test_alembic_autogenerate.py -v -m integration`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

固定同一输入重跑并比较 Factor 值绝对误差不超过 `1e-10`，且排序结果完全一致；不执行 Git 操作。

---

### Task 12: 实现 OOS 有效性检验与 Peer Group 标准化

**Files:**
- Create: `src/fip/strategy_library/validation.py`
- Create: `src/fip/strategy_library/normalization.py`
- Create: `src/fip/services/factor_service/validation.py`
- Create: `tests/unit/test_factor_validation.py`
- Create: `tests/unit/test_factor_normalization.py`
- Create: `tests/integration/test_factor_effectiveness.py`

**Interfaces:**
- Produces: `SampleSplit(in_sample_end, out_of_sample_start, out_of_sample_end)`
- Produces: `FactorEffectivenessResult(ic, icir, monotonic, redundancy_group, verdict)`
- Produces: `normalize_factor(values, direction, target_range, minimum_sample) -> tuple[NormalizedFactorValue, ...]`

- [ ] **Step 1: 写 OOS 检验失败测试**

覆盖时间顺序切分、禁止随机重排、Rank IC、ICIR、五层收益单调性、`|Spearman rho| > 0.8` 冗余、无 OOS 为 `VALIDATION_PENDING`、阈值失败为 `INVALID`。

- [ ] **Step 2: 写标准化失败测试**

覆盖 Peer Group 内 percentile、并列值平均秩、输出 `normalized_value ∈ [0,100]`、四种方向、四类 Beta 目标区间、Passive/Bond TE 方向、有效样本小于 30 返回 `UNAVAILABLE`、raw value 不被覆盖。Active/Hybrid TE 只返回 raw value 与 percentile，不在 Factor 层执行复合算子。

- [ ] **Step 3: 运行测试确认模块不存在**

Run: `.venv/bin/pytest tests/unit/test_factor_validation.py tests/unit/test_factor_normalization.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现纯函数与服务编排**

Validation 只消费已冻结 OOS 区间；服务层从 Policy 获取阈值并把 `FactorEffectivenessResult` 写入 `factor_effectiveness`。Normalization 绑定 `peer_group_snapshot_id` 和 policy version，不跨组计算。

- [ ] **Step 5: 验证数值与持久化**

Run: `.venv/bin/pytest tests/unit/test_factor_validation.py tests/unit/test_factor_normalization.py tests/integration/test_factor_effectiveness.py -v`

Expected: PASS。

- [ ] **Step 6: 人工检查点**

确认 OOS 结果没有反向修改参数或固定权重，`VALIDATION_PENDING` 与 `INVALID` 有独立测试；不执行 Git 操作。

---

### Task 13: 实现固定权重评分、排名和 Tier

**Files:**
- Create: `src/fip/strategy_library/scoring.py`
- Create: `src/fip/strategy_library/ranking.py`
- Create: `src/fip/services/fund_service/scoring.py`
- Create: `src/fip/services/fund_service/ranking.py`
- Create: `src/fip/services/fund_service/tier.py`
- Extend: `src/fip/services/fund_service/models.py`
- Create: `db/migrations/versions/0020_evaluation_pipeline.py`
- Create: `tests/unit/test_scoring.py`
- Create: `tests/unit/test_ranking.py`
- Create: `tests/unit/test_tier.py`
- Create: `tests/integration/test_score_persistence.py`

**Interfaces:**
- Produces: `FundEvaluation`、`FundScore`、`FundScoreAttribution`、`FundRanking`、`FundTier`
- Produces: `calculate_score(evaluation, factors, effectiveness, expense_ratio, policy) -> FundScoreResult`
- Produces: `rank_peer_group(scores, minimum_sample) -> tuple[FundRankingResult, ...]`
- Produces: `classify_tier(ranking, policy) -> FundTierResult`

- [ ] **Step 1: 写评分状态机失败测试**

覆盖：无 OOS 为 `VALIDATION_PENDING`；无效指标权重为 0 并保留 `EXCLUDED` 归因；缺失指标按固定权重比例重归一；少于两个有效加权指标或完整度低于 0.8 为 `UNAVAILABLE`；R² 不进入总分；Expense Ratio 以 `LOWER_IS_BETTER` 参与评分；`weight_source = PROFILE_FIXED_V1`；`normalized_value` 已为 `[0,100]`，评分层不得再次乘 100。

同时覆盖 TE 复合算子：Active 在 `IR > 0.5` 时按 `sqrt(TE × IR)` 越高越好、`IR <= 0` 时按 `sqrt(TE)` 越低越好、`0 < IR <= 0.5` 返回中性值 50；Hybrid 在 `Sharpe > 1.0` 时按 `sqrt(TE × Sharpe)` 越高越好，否则按 `sqrt(TE)` 越低越好；Passive 直接越低越好；Bond 年化 TE 超过 1.5% 时为 0。复合 `interaction_value` 只占用 TE 权重，不叠加独立 TE 贡献。

- [ ] **Step 2: 写排名与 Tier 失败测试**

有效样本少于 30 时排名和 Tier 均不可用；并列分数使用平均秩；按 Profile 分开排名；Tier 阈值使用配置并返回 `n_effective`。

- [ ] **Step 3: 运行纯计算测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_scoring.py tests/unit/test_ranking.py tests/unit/test_tier.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现纯评分与排名规则**

```python
def calculate_score(...) -> FundScoreResult:
    eligible = [item for item in inputs if item.effectiveness == VALID]
    if effectiveness_missing:
        return FundScoreResult.validation_pending()
    if len(eligible) < policy.minimum_scoring_factors:
        return FundScoreResult.unavailable("INSUFFICIENT_FACTORS")
    weights = renormalize_profile_weights(eligible, policy.profile_weights)
    total_score = sum(item.scoring_value * weights[item.metric_id] for item in eligible)
    return FundScoreResult.available(total_score, ...)
```

v1 总分直接按 Profile 指标权重汇总，五子分只作为解释分组，不进行第二次子分加权。
其中普通指标的 `scoring_value = normalized_value`，Active/Hybrid TE 的 `scoring_value = interaction_value`。
保存每个 included/excluded/unavailable 指标的 `factor_id + window`、`raw_value`、
`normalized_value`/`interaction_value`、direction、configured/effective weight、weighted contribution、verdict 和 `reason_code`；每个子分均可回溯到这些指标贡献。

- [ ] **Step 5: 建立 Evaluation 表并保存版本引用**

0020 创建 `fund_evaluation`、`fund_score`、`fund_score_attribution`、`fund_ranking`、`fund_tier`；所有结果引用 peer group snapshot、policy version、factor run 和 decision ID，历史记录不可更新覆盖。

- [ ] **Step 6: 运行验证**

Run: `.venv/bin/alembic -x db=test upgrade head`

Run: `.venv/bin/pytest tests/unit/test_scoring.py tests/unit/test_ranking.py tests/unit/test_tier.py tests/integration/test_score_persistence.py -v`

Expected: PASS。

- [ ] **Step 7: 人工检查点**

逐 Profile 核对权重和为 1，并确认任何状态都没有把缺失值写成 0；不执行 Git 操作。

---

### Task 14: 实现 Universe 原子快照与端到端评价管线

**Files:**
- Create: `src/fip/strategy_library/universe.py`
- Create: `src/fip/services/fund_service/universe.py`
- Create: `src/fip/services/fund_service/repositories.py`
- Create: `src/fip/services/fund_service/pipeline.py`
- Extend: `src/fip/services/fund_service/models.py`
- Modify: `db/migrations/versions/0020_evaluation_pipeline.py`
- Create: `tests/unit/test_universe.py`
- Create: `tests/integration/test_universe_snapshot.py`
- Create: `tests/integration/test_evaluation_pipeline.py`
- Create: `tests/repro/test_evaluation_reproducibility.py`

**Interfaces:**
- Produces: `FundUniverseSnapshot`、`FundUniverseMember`、`SelectionConditionResult`
- Produces: `evaluate_candidate(condition, candidate) -> SelectionConditionResult`
- Produces: `EvaluationPipeline.run(context: DecisionExecutionContext) -> EvaluationPipelineResult`
- Transaction boundary: Peer Group B1 与 Universe B2 在同一 SQLAlchemy transaction 内提交。

- [ ] **Step 1: 写 Universe 完整留痕失败测试**

断言 `SELECTED` 与 `REJECTED` 都保存；每个成员保存全部条件结果而非只保存失败项；条件按稳定 ID 排序；`UNAVAILABLE` 条件不得当作通过。

- [ ] **Step 2: 写 B1 -> B2 原子性失败测试**

在 Universe 保存前注入异常；断言同一 transaction 内新建的 Peer Group、Score、Ranking、Tier、Universe 全部回滚。再执行成功路径，断言全部 version FK 可追溯。

- [ ] **Step 3: 运行测试确认闭环不存在**

Run: `.venv/bin/pytest tests/unit/test_universe.py tests/integration/test_universe_snapshot.py tests/integration/test_evaluation_pipeline.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现纯规则和单事务 pipeline**

```python
class EvaluationPipeline:
    def run(self, context: DecisionExecutionContext) -> EvaluationPipelineResult:
        with self._session.begin():
            peer_groups = self._peer_groups.build_and_save(context)
            factors = self._factors.calculate_validate_normalize(context, peer_groups)
            scores = self._scoring.calculate_and_save(context, peer_groups, factors)
            rankings = self._ranking.rank_and_save(context, scores)
            tiers = self._tier.classify_and_save(context, rankings)
            universe = self._universe.build_and_save(context, tiers)
        return EvaluationPipelineResult(...)
```

Pipeline 不包含投资规则，只编排固定顺序；所有规则从版本化 Policy/Metric 读取。

- [ ] **Step 5: 添加可复现性回归**

固定 Data Version、Metric Version、Policy Version、Code Version 和 `DecisionExecutionContext`，连续运行两次；断言 Factor/Score 绝对误差不超过 `1e-10`，成员集合、排名顺序、状态和 `reason_code` 完全一致。

- [ ] **Step 6: 运行端到端与全量验证**

Run: `.venv/bin/pytest tests/unit tests/fitness -v`

Run: `.venv/bin/pytest tests/integration -v -m integration`

Run: `.venv/bin/pytest tests/repro/test_evaluation_reproducibility.py -v`

Run: `.venv/bin/ruff check src tests`

Run: `.venv/bin/mypy`

Expected: 全部 PASS；无 lint 或类型错误。

- [ ] **Step 7: 最终人工验收**

逐项核对设计文档第 7 节七条验收标准；记录每条对应的测试名称和输出。确认无 API、前端、组合、回测或 Benchmark 自动解析代码混入；不执行 Git 操作。

---

## Requirement Traceability

| Spec requirement | Implementation task |
|---|---|
| Plan-1 PIT 翻译、IntervalMixin、防漂移 | Tasks 1–3 |
| 批处理隔离、披露时滞版本化 | Task 4 |
| 分类、费率、Rf PIT | Task 5 |
| 人工 Benchmark 与 Composite | Task 6 |
| Evaluation/Validation Policy 版本 | Task 7 |
| Peer Group 快照 | Task 8 |
| 原 10 个 Factor | Task 9 |
| 5 个 Benchmark Factor | Task 10 |
| Factor Run/Value 版本闭包 | Task 11 |
| OOS、冗余检查、标准化 | Task 12 |
| Score、Rank、Tier | Task 13 |
| Universe、B1→B2 原子性、复现性 | Task 14 |

## Explicitly Deferred

- 官方 Benchmark 文档解析、自动成分抽取和商业数据源。
- 完整 Walk-forward、市场状态分段、Rolling Factor 全家族和权重优化。
- QDII、货币基金以及四类 Profile 之外的动态分类。
- REST API、前端、组合优化、决策审核和回测编排。
- Plan-1 已知但不阻塞 Plan-2 评价闭环的管理人灌数与人工确认 UI；本计划只补数据库约束。