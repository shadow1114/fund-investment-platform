# Plan-2 起草稿 · Task 7–8（`factor` / `evaluation` 两个 schema 共 14 张表）

> 本文是 `docs/superpowers/plans/2026-09-02-plan2-factor-and-evaluation.md` 中
> Task 7 与 Task 8 的详细步骤草稿。裁定依据一律指向
> `docs/superpowers/specs/2026-09-02-plan2-factor-and-evaluation-design.md`
> （D-12 ~ D-18）与该计划的 Global Constraints（G-7、G-8、G-14 ~ G-17）。
>
> **本稿新增的裁定**（上游抽取与设计定案都没覆盖到、我在起草中被迫作出的）
> 集中列在文末「起草中发现的矛盾与遗漏」一节，逐条给出理由与影响面。
> 它们在代码里一律按 G-14 标 `PROVISIONAL` 并指向本文件。

---

### Task 7: `factor` schema 五张表 + 迁移 0016

**Files:**

- Create: `src/fip/platform/db/enums.py`
- Create: `src/fip/services/factor_service/models/__init__.py`
- Create: `src/fip/services/factor_service/models/factor.py`
- Create: `db/migrations/versions/0016_factor_schema.py`
- Create: `tests/integration/test_factor_schema.py`
- Modify: `db/migrations/env.py`（新增一行 model 模块 import —— 漏了它
  `Base.metadata` 就没有这五张表，autogenerate 会静默失效）
- Modify: `tests/integration/check_constraints.snapshot`（G-17，由测试重新生成，不手写）

**Interfaces:**

```python
# ---- Consumes（Plan-1 已产出，不得重新发明）----
from fip.platform.db.base import Base
from fip.platform.db.mixins import VersionedMixin, temporal_check_constraints
#   temporal_check_constraints(table: str) -> tuple[CheckConstraint, CheckConstraint]
#   —— quality_source + 五子句 time_order（anchor = effective_at，已钉 UTC）
from fip.platform.db.types import NavNumeric, RatioNumeric
#   NavNumeric  = Numeric(18, 8)   # 净值 / 因子 raw_value
#   RatioNumeric= Numeric(12, 8)   # 比率 / 分数 / 分位（0~9999.99999999）
# 外键目标：fund.fund_share_class.id（BIGINT）

# ---- Produces（Task 8 / 9 / 12 / 13 / 14 / 17 消费）----
# src/fip/platform/db/enums.py
factor_category_enum: postgresql.ENUM            # RET RISK RAP STAB REL
preference_direction_enum: postgresql.ENUM       # HIGHER_IS_BETTER LOWER_IS_BETTER
                                                 # TARGET_RANGE STRATEGY_DEPENDENT
factor_status_enum: postgresql.ENUM              # VALID WARNING INVALID UNAVAILABLE
factor_unavailable_reason_enum: postgresql.ENUM  # 八类
factor_run_status_enum: postgresql.ENUM          # RUNNING COMPLETED FAILED
factor_effectiveness_verdict_enum: postgresql.ENUM  # VALID INVALID
provenance_enum: postgresql.ENUM                 # DECIDED PROVISIONAL

# src/fip/services/factor_service/models/factor.py
class FactorDefinition(Base)                     # factor.factor_definition
class FactorVersion(Base)                        # factor.factor_version
class FactorRun(Base)                            # factor.factor_run
class FactorValue(Base, VersionedMixin)          # factor.factor_value
class FactorEffectiveness(Base)                  # factor.factor_effectiveness
```

- [ ] **Step 1: 新建 `src/fip/platform/db/enums.py`（七个 PG 枚举的唯一声明点）**

放在 platform 层而非某个 service 下，理由有二：`preference_direction_enum`
被 `factor.factor_definition` 与 `evaluation.fund_score_attribution` **两个
schema、两个 service** 同时使用，放进任一 service 都会逼出一条
services → services 的模块级依赖；而 `availability_quality_enum` 已经在
`platform/db/mixins.py` 里立了同样的先例。依赖方向仍是单向的
（services → platform），不触碰 `test_platform_layer_does_not_import_services_at_module_level`。

```python
# src/fip/platform/db/enums.py
"""全平台共享的 PostgreSQL 枚举类型【声明】（不是创建）。

⚠️ 必须用 postgresql.ENUM，【不得】用 sa.Enum。
sa.Enum 会【静默忽略】create_type 标志 —— 它不认这个参数，于是每次
CREATE TABLE 之前都会试图再发一次 CREATE TYPE，第二张用同一枚举的表
就会炸在 "type ... already exists"，而且错误发生在迁移中途、事务已经
建了一半的表。本仓库在 availability_quality_enum 上踩过这个坑，
mixins.py 里的写法（postgresql.ENUM + create_type=False）是唯一正确的。

枚举类型本体由迁移 0016 / 0017 用 op.execute("CREATE TYPE ...") 创建，
【不带 schema 限定】，因此落在 public —— 与 0001 建的
availability_quality_enum 一致，也是 tests/conftest.py 里
`DROP SCHEMA public CASCADE` 能把它们一次性清干净的前提。改成建在业务
schema 下会让测试库重置漏掉它们，第二次测试会话即失败。
"""
from sqlalchemy.dialects.postgresql import ENUM

# ---- factor schema（迁移 0016 创建）----

factor_category_enum = ENUM(
    "RET", "RISK", "RAP", "STAB", "REL",
    name="factor_category_enum", create_type=False,
)

preference_direction_enum = ENUM(
    "HIGHER_IS_BETTER", "LOWER_IS_BETTER", "TARGET_RANGE", "STRATEGY_DEPENDENT",
    name="preference_direction_enum", create_type=False,
)
"""四取值原样沿用上游（FS:177-182）。

⚠️ 已知缺口：上游在 Active Equity 画像下把 Tracking Error 的方向称为
「中性」，而「中性」不在这四个取值里。M1 无 Benchmark、TE 恒
UNAVAILABLE，本 Plan【不实现】中性方向（设计定案 D-11 第 3 点）。
拿到真正的 04-factor 文档后若确认需要第五个取值，走 ALTER TYPE ... ADD VALUE。
"""

factor_status_enum = ENUM(
    "VALID", "WARNING", "INVALID", "UNAVAILABLE",
    name="factor_status_enum", create_type=False,
)

factor_unavailable_reason_enum = ENUM(
    "INSUFFICIENT_HISTORY",
    "BENCHMARK_UNAVAILABLE",
    "RISK_FREE_RATE_UNAVAILABLE",
    "MAR_NOT_CONFIGURED",
    "ZERO_MAX_DRAWDOWN",
    "ZERO_DOWNSIDE_VOLATILITY",
    "ZERO_TRACKING_ERROR",
    "ZERO_VOLATILITY",
    name="factor_unavailable_reason_enum", create_type=False,
)
"""八类逐字抄自 10-api/03-factor-api.md §4.3.5。

MAR_NOT_CONFIGURED 与「mar_policy = ZERO」是两回事：后者是【已配置】状态，
因子正常返回值。G-6 的「必填无默认」正是靠这个区分才有意义。
ZERO_MAX_DRAWDOWN / ZERO_DOWNSIDE_VOLATILITY 是「好消息型」不可用 ——
它们不是错误，不得告警，更不得填 inf（G-3）。
"""

factor_run_status_enum = ENUM(
    "RUNNING", "COMPLETED", "FAILED",
    name="factor_run_status_enum", create_type=False,
)

factor_effectiveness_verdict_enum = ENUM(
    "VALID", "INVALID",
    name="factor_effectiveness_verdict_enum", create_type=False,
)

provenance_enum = ENUM(
    "DECIDED", "PROVISIONAL",
    name="provenance_enum", create_type=False,
)
"""G-14 的落库形态：每一条【补齐】项在数据里也必须自报家门。

只标在 YAML 里不够 —— 因子定义会被灌进 factor_definition 表后由 API 读出，
查询方看不到 YAML。PROVISIONAL 的行必须在数据层面就能被筛出来。
"""
```

- [ ] **Step 2: 先写失败的集成测试 `tests/integration/test_factor_schema.py`**

G-18：每条测试都必须先证伪。本步只写测试，此刻 5 张表都不存在。

```python
# tests/integration/test_factor_schema.py
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.grouping import GroupingStatus
from fip.services.factor_service.models.factor import (
    FactorDefinition,
    FactorEffectiveness,
    FactorRun,
    FactorValue,
    FactorVersion,
)

pytestmark = pytest.mark.integration

ING = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)
EFF = dt.date(2026, 8, 31)


def _times():
    """INFERRED 路径：两个来源皆 NULL（G-15 —— AKShare 链路一律 INFERRED）。"""
    return dict(
        available_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=ING,
    )


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-FAC", product_name="因子测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="因子测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


@pytest.fixture()
def sharpe(db_session) -> FactorVersion:
    d = FactorDefinition(
        factor_id="F-RAP-001", factor_name="Sharpe Ratio", category="RAP",
        preference_direction="HIGHER_IS_BETTER",
        usage_display=True, usage_scoring=True, usage_screening=True,
        usage_portfolio=False, usage_backtest=True, provenance="DECIDED",
    )
    db_session.add(d)
    db_session.flush()
    v = FactorVersion(
        factor_definition_id=d.id, version_label="v1", formula_ref="metric.sharpe",
        metric_config_digest="0" * 64, min_obs=252,
        requires_risk_free_rate=True, requires_mar=False, requires_benchmark=False,
        provenance="PROVISIONAL",
    )
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture()
def run(db_session) -> FactorRun:
    r = FactorRun(
        decision_at=EFF, strategy_version="SV-2026-08-31-a1b2c3",
        code_version="0.1.0+g1234567", evaluation_policy_version="EP-v1",
        data_version="DV-2026-08-31", status="RUNNING",
        started_at=ING, finished_at=None, duration_ms=None,
    )
    db_session.add(r)
    db_session.flush()
    return r


def _value(share_class, sharpe, run, **overrides):
    row = dict(
        share_class_id=share_class.id, factor_id="F-RAP-001", window="1Y",
        effective_at=EFF, version=1,
        factor_version_id=sharpe.id, factor_run_id=run.id,
        raw_value=Decimal("1.23456789"), normalized_value=Decimal("87.50000000"),
        status="VALID", unavailable_reason=None, observation_count=252,
        peer_group_snapshot_id=None, peer_group_version=None,
        risk_free_rate_currency="CNY", risk_free_rate_tenor="1Y",
        risk_free_rate_version=1, risk_free_rate_quality="INFERRED",
        evaluation_policy_version=None, data_version="DV-2026-08-31",
        **_times(),
    )
    row.update(overrides)
    return FactorValue(**row)


# ---------------------------------------------------------------- 身份与唯一性

def test_factor_id_must_match_its_category(db_session):
    """F-RET-001 不得声明 category=RAP —— ID 前缀与类别是同一件事的两种写法。"""
    db_session.add(FactorDefinition(
        factor_id="F-RET-001", factor_name="错配", category="RAP",
        preference_direction="HIGHER_IS_BETTER",
        usage_display=True, usage_scoring=True, usage_screening=False,
        usage_portfolio=False, usage_backtest=False, provenance="PROVISIONAL",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_factor_must_declare_at_least_one_usage(db_session):
    """Usage 五列全 false 的因子没有任何用途，是配置错误而非合法状态。"""
    db_session.add(FactorDefinition(
        factor_id="F-RET-002", factor_name="无用途", category="RET",
        preference_direction="HIGHER_IS_BETTER",
        usage_display=False, usage_scoring=False, usage_screening=False,
        usage_portfolio=False, usage_backtest=False, provenance="PROVISIONAL",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_factor_run_idempotency_key_is_unique(db_session, run):
    """幂等键 (decision_at, strategy_version)（03-erd:440）。"""
    db_session.add(FactorRun(
        decision_at=run.decision_at, strategy_version=run.strategy_version,
        code_version="0.1.0+other", evaluation_policy_version="EP-v1",
        data_version="DV-2026-08-31", status="RUNNING",
        started_at=ING, finished_at=None, duration_ms=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------------- D-13：两个部分唯一索引的对照

def test_no_policy_factor_cannot_be_duplicated(db_session, share_class, sharpe, run):
    """evaluation_policy_version IS NULL 时，五元组唯一（ux_factor_value_no_policy）。

    这是 PostgreSQL 的 NULL 不参与唯一性比较所造成的洞：一条普通的
    UNIQUE(..., evaluation_policy_version) 对 NULL 行【完全不生效】，
    同一个因子值可以被重复写入。部分唯一索引是上游选定的方案 A。
    """
    db_session.add(_value(share_class, sharpe, run))
    db_session.flush()
    db_session.add(_value(share_class, sharpe, run))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_policy_version_is_part_of_identity(db_session, share_class, sharpe, run):
    """D-13：evaluation_policy_version【进】唯一约束 —— 不同评价政策是不同的值。

    同一 (share_class, factor, window, effective_at, version) 下，
    EP-v1 与 EP-v2 必须能共存。
    """
    db_session.add(_value(share_class, sharpe, run, evaluation_policy_version="EP-v1"))
    db_session.add(_value(share_class, sharpe, run, evaluation_policy_version="EP-v2"))
    db_session.flush()          # 两行都必须落库


def test_same_policy_version_cannot_be_duplicated(db_session, share_class, sharpe, run):
    db_session.add(_value(share_class, sharpe, run, evaluation_policy_version="EP-v1"))
    db_session.flush()
    db_session.add(_value(share_class, sharpe, run, evaluation_policy_version="EP-v1"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_risk_free_rate_ref_is_not_part_of_identity(db_session, share_class, sharpe, run):
    """D-13 的反面：risk_free_rate_ref 是【溯源】，不进唯一约束。

    仅 R_f 溯源不同的两行必须被拒 —— 它们是同一个因子值，
    R_f 由 (currency, tenor, decision_at) 唯一确定（04-database-design:570）。
    """
    db_session.add(_value(share_class, sharpe, run))
    db_session.flush()
    db_session.add(_value(share_class, sharpe, run, risk_free_rate_tenor="3Y"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_window_is_part_of_identity(db_session, share_class, sharpe, run):
    """D-13：window 必须进唯一键 —— 窗口不进 Factor ID（03-erd:410）。"""
    db_session.add(_value(share_class, sharpe, run, window="1Y"))
    db_session.add(_value(share_class, sharpe, run, window="3Y"))
    db_session.flush()          # 两行都必须落库


# ------------------------------------------------------- G-3：UNAVAILABLE 不填值

def test_unavailable_must_not_carry_a_value(db_session, share_class, sharpe, run):
    """G-3：UNAVAILABLE 不得被任何填充值替代 —— 0 也不行。"""
    db_session.add(_value(
        share_class, sharpe, run, status="UNAVAILABLE",
        unavailable_reason="ZERO_MAX_DRAWDOWN",
        raw_value=Decimal("0"), normalized_value=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unavailable_must_carry_a_reason(db_session, share_class, sharpe, run):
    """「没法算」必须说明为什么没法算，否则事后无法区分数据问题与业务常态。"""
    db_session.add(_value(
        share_class, sharpe, run, status="UNAVAILABLE",
        unavailable_reason=None, raw_value=None, normalized_value=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_valid_must_not_carry_an_unavailable_reason(db_session, share_class, sharpe, run):
    db_session.add(_value(
        share_class, sharpe, run, unavailable_reason="ZERO_VOLATILITY"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_carries_no_value_and_no_reason(db_session, share_class, sharpe, run):
    """INVALID =「算了但算错了」，须告警；它不是 UNAVAILABLE，没有 reason 八类。"""
    db_session.add(_value(
        share_class, sharpe, run, status="INVALID",
        raw_value=None, normalized_value=None, unavailable_reason=None,
    ))
    db_session.flush()


def test_normalized_value_requires_peer_group_context(db_session, share_class, sharpe, run):
    """标准化值离开 Peer Group 上下文就不可解释（03-erd §9.1）。"""
    db_session.add(_value(
        share_class, sharpe, run,
        normalized_value=Decimal("87.5"),
        peer_group_snapshot_id=None, peer_group_version=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_risk_free_rate_ref_is_all_or_nothing(db_session, share_class, sharpe, run):
    """四个必备字段（currency/tenor/version/quality）缺一不可（§9.2.1）。

    缺 tenor 则无法验证期限匹配是否正确 —— 那正是这条溯源存在的理由。
    """
    db_session.add(_value(share_class, sharpe, run, risk_free_rate_tenor=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


# --------------------------------------------------------------- 时序与不可变

def test_factor_value_inherits_the_five_clause_time_order(db_session, share_class, sharpe, run):
    """available_at 早于 effective_at 是前视偏差，版本化表必须拒收（clause 4）。"""
    db_session.add(_value(
        share_class, sharpe, run,
        available_at=dt.datetime(2026, 8, 30, tzinfo=dt.UTC)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_factor_value_has_no_updated_at(db_session):
    """禁止 UPDATE 的表不设 updated_at —— 这是一个有意的设计信号（§4.3）。"""
    cols = db_session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'factor' AND table_name = 'factor_value'"
    )).scalars().all()
    assert "updated_at" not in cols


def test_factor_value_is_not_partitioned(db_session):
    """本稿裁定：M1 不分区（见文末「起草中发现的矛盾与遗漏」第 4 条）。

    这条测试锁住的是【当前的选择】。将来若要分区，必须先把它改掉，
    从而强制改动者正面看到「分区键必须进入两个部分唯一索引」这件事。
    """
    kind = db_session.execute(text(
        "SELECT relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'factor' AND c.relname = 'factor_value'"
    )).scalar_one()
    assert kind == "r"          # 'p' 才是分区表


# ------------------------------------------------------------ factor_run 状态机

def test_completed_run_must_have_finished_at_and_duration(db_session, run):
    run.status = "COMPLETED"
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_running_run_must_not_have_finished_at(db_session, run):
    run.finished_at = ING
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------------------- factor_effectiveness

def test_valid_verdict_requires_ic_and_icir(db_session, sharpe, run):
    """D-1：factor_effectiveness 的存在性是 Score 产出的前置条件。

    判 VALID 却没有 IC / ICIR，等于「未经检验就拍权重」—— 上游明确堵死
    的那条捷径（FS:346 及其反例）。
    """
    db_session.add(FactorEffectiveness(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT",
        test_window_start=dt.date(2021, 1, 1), test_window_end=dt.date(2026, 1, 1),
        ic=None, icir=None, n_periods=60, verdict="VALID",
        validation_policy_version="VP-v1",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_verdict_may_omit_ic(db_session, sharpe, run):
    """反面：INVALID 允许 IC 缺失 —— 「算不出 IC」本身就是判 INVALID 的理由之一。"""
    db_session.add(FactorEffectiveness(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT",
        test_window_start=dt.date(2021, 1, 1), test_window_end=dt.date(2026, 1, 1),
        ic=None, icir=None, n_periods=0, verdict="INVALID",
        validation_policy_version="VP-v1",
    ))
    db_session.flush()


def test_test_window_must_be_ordered(db_session, sharpe, run):
    db_session.add(FactorEffectiveness(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT",
        test_window_start=dt.date(2026, 1, 1), test_window_end=dt.date(2021, 1, 1),
        ic=Decimal("0.05"), icir=Decimal("0.4"), n_periods=60, verdict="VALID",
        validation_policy_version="VP-v1",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 3: 运行确认失败（G-18，把失败输出写进报告）**

```bash
.venv/bin/pytest tests/integration/test_factor_schema.py -v
```

Expected: **全部 collection error** ——
`ModuleNotFoundError: No module named 'fip.services.factor_service.models'`。
这是「先证伪」的第一形态；Step 6 之后还会有第二形态（模型在、表不在，
`ProgrammingError: relation "factor.factor_value" does not exist`）。
两次失败输出都要贴进任务报告。

- [ ] **Step 4: 写 ORM 模型 `src/fip/services/factor_service/models/factor.py`**

G-16 是本步的第一约束：**下面每一条 CheckConstraint / Index / UniqueConstraint
都必须在迁移 0016 里逐字出现，反之亦然**。本仓库已被「库里有而 metadata 里没有」
咬出过三次误删迁移。

```python
# src/fip/services/factor_service/models/factor.py
import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.enums import (
    factor_category_enum,
    factor_effectiveness_verdict_enum,
    factor_run_status_enum,
    factor_status_enum,
    factor_unavailable_reason_enum,
    preference_direction_enum,
    provenance_enum,
)
from fip.platform.db.mixins import (
    VersionedMixin,
    availability_quality_enum,
    temporal_check_constraints,
)
from fip.platform.db.types import NavNumeric, RatioNumeric

# --------------------------------------------------------------------------
# CHECK 的 SQL 字面量集中在这里，迁移 0016 里【逐字复制】同样的字符串。
# 刻意不让迁移 import 这些常量：迁移是不可编辑的历史，它产出的 DDL 必须与
# 当初执行时逐字相同；import 会让今后对本文件的修改追溯性地改写旧迁移
# （0011 / 0013 的注释里记着这条教训）。重复是有意的。
# --------------------------------------------------------------------------

# factor_id 的前缀必须与 category 一致。两者是同一件事的两种写法，
# 允许它们分叉就等于允许一个 RAP 因子自称 F-RET-001，
# 而下游按前缀分子分（RET→Return Score）时会静默归错子分。
FACTOR_ID_SHAPE_SQL = "factor_id ~ ('^F-' || category::text || '-[0-9]{3}$')"

# 每个 Factor 必须声明至少一种用途（BR:939-949 §14.1）。
FACTOR_USAGE_SQL = (
    "usage_display OR usage_scoring OR usage_screening "
    "OR usage_portfolio OR usage_backtest"
)

# Analysis Period 六值（BR:701-711 §9.1，「不新增」）。window 与
# evaluation_period 共用同一个域。
PERIOD_DOMAIN_SQL = "{col} IN ('1M', '3M', '6M', '1Y', '3Y', '5Y')"

# factor_run 的状态机：RUNNING 时不得有结束时点，终态必须有。
FACTOR_RUN_STATE_SQL = (
    "(status = 'RUNNING' AND finished_at IS NULL AND duration_ms IS NULL) OR "
    "(status IN ('COMPLETED', 'FAILED') "
    " AND finished_at IS NOT NULL AND duration_ms IS NOT NULL)"
)

# status 四值与 (raw_value, unavailable_reason) 的联动。这是 G-3 的数据库防线：
#   VALID / WARNING → 有值，无 reason
#   INVALID         → 算错了，无值，也没有 reason（reason 八类全属「没法算」）
#   UNAVAILABLE     → 无值，且必须说明为什么
FACTOR_VALUE_STATUS_SQL = (
    "(status IN ('VALID', 'WARNING') "
    " AND raw_value IS NOT NULL AND unavailable_reason IS NULL) OR "
    "(status = 'INVALID' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND unavailable_reason IS NULL) OR "
    "(status = 'UNAVAILABLE' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND unavailable_reason IS NOT NULL)"
)

# R_f 溯源四列（§9.2.1）要么齐备要么全空。缺 tenor 则无法验证期限匹配，
# 那正是这四列存在的唯一理由。
RF_REF_SQL = (
    "num_nonnulls(risk_free_rate_currency, risk_free_rate_tenor, "
    "risk_free_rate_version, risk_free_rate_quality) IN (0, 4)"
)

# 标准化上下文成对出现，且标准化值不得脱离上下文存在（03-erd §9.1）。
PEER_CTX_SQL = (
    "(peer_group_snapshot_id IS NULL AND peer_group_version IS NULL) OR "
    "(peer_group_snapshot_id IS NOT NULL AND peer_group_version IS NOT NULL)"
)
NORMALIZED_NEEDS_CTX_SQL = (
    "normalized_value IS NULL OR peer_group_snapshot_id IS NOT NULL"
)

# 判 VALID 却拿不出 IC / ICIR，等于未经检验就拍权重（FS:346）。
EFFECTIVENESS_VERDICT_SQL = (
    "verdict = 'INVALID' OR (ic IS NOT NULL AND icir IS NOT NULL)"
)


class FactorDefinition(Base):
    """因子的【身份】—— 纯维度表，不带任何时序列。

    D-16：全仓没有本表的字段清单（BLOCK-2，定义它的 04-factor/03 不在仓库），
    形状由本 Plan 自行设计。字段全部为【补齐】，故 provenance 列存在。

    为什么方向落在这里而不是 Scoring Policy：上游只说「方向必须由 Policy
    声明，不得从字段名推断」（FS:186），没说方向不能是因子的固有属性。
    Volatility 在任何画像下都是越低越好 —— 把它拆到 Policy 里会让每个
    Policy 都得重抄一遍十个方向，抄漏一个就是静默反号。真正随画像变化的
    是 TARGET_RANGE / STRATEGY_DEPENDENT 两类（Beta、Tracking Error），
    它们在 M1 全部落在 REL、恒 UNAVAILABLE，本表的取值对它们不产生影响。
    M2 引入多 Profile 时，Profile 级覆盖走 Scoring Policy 的
    preference_directions，本列退化为默认值。
    """

    __tablename__ = "factor_definition"
    __table_args__ = (
        UniqueConstraint("factor_id", name="uq_factor_definition_factor_id"),
        CheckConstraint(FACTOR_ID_SHAPE_SQL, name="ck_factor_definition_id_shape"),
        CheckConstraint(FACTOR_USAGE_SQL, name="ck_factor_definition_usage"),
        {"schema": "factor"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 业务键。factor_value.factor_id 与 fund_score_attribution.factor_id 都
    # 外键指向它（01-postgresql.md:421 点名 factor_value → factor_definition
    # 为 RESTRICT），因此它必须是 UNIQUE 而不只是「事实上唯一」。
    factor_id: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(factor_category_enum, nullable=False)
    preference_direction: Mapped[str] = mapped_column(
        preference_direction_enum, nullable=False
    )
    # Factor Usage 五列（BR:939-949 §14.1）。刻意【不】用一个数组或 JSONB：
    # 「usage 决定因子能出现在哪里」（10-api/03 §4.1.2），这五个值会进
    # WHERE（「取全部 SCORING 因子」），按 01-postgresql §13.2 的判据必须结构化。
    usage_display: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usage_scoring: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usage_screening: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usage_portfolio: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usage_backtest: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance: Mapped[str] = mapped_column(provenance_enum, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 主数据表，允许 UPDATE，故设 updated_at（04-database-design §4.2/§4.3）。
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class FactorVersion(Base):
    """因子的【口径版本】—— Strategy Version 第 1 项（Metric Version）。

    D-16：公式版本 + min_obs + 依赖声明。同样是【补齐】（BLOCK-2）。

    metric_config_digest 是本表唯一一个上游没有暗示过的列，加它的理由是
    G-2（可复现性容差 1e-10）：version_label 只是一个人写的字符串，
    有人改了 config/strategy/metric/v1.yaml 里的 ddof 却忘了升 label，
    同一个 version_label 下就有了两套口径，而因子值看起来完全正常。
    digest 让这种漂移在写入时就能被比对出来。

    requires_* 三列是【依赖声明】，D-10 的 UNAVAILABLE 触发条件直接读它们：
    requires_mar 且 mar_policy 未配置 → MAR_NOT_CONFIGURED（G-6，无默认值）。
    把依赖写在数据里而不是代码 if 里，是为了让「哪些因子会因缺 MAR 而消失」
    可以被查询回答，而不是靠读代码。
    """

    __tablename__ = "factor_version"
    __table_args__ = (
        UniqueConstraint(
            "factor_definition_id", "version_label", name="uq_factor_version_label"
        ),
        CheckConstraint("min_obs > 0", name="ck_factor_version_min_obs"),
        CheckConstraint(
            "char_length(metric_config_digest) = 64",
            name="ck_factor_version_digest_shape",
        ),
        {"schema": "factor"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_definition_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_definition.id", ondelete="RESTRICT"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    # 指向 config/strategy/metric/v1.yaml 里的键，不在库里重存公式本身。
    formula_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # D-10【补齐, PROVISIONAL】：日频 252 / Rolling 504 / 月频 36。
    min_obs: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_risk_free_rate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_mar: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_benchmark: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance: Mapped[str] = mapped_column(provenance_enum, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class FactorRun(Base):
    """一次计算批次。幂等键 (decision_at, strategy_version)（03-erd:440）。

    「它使『某次批量计算产出了哪些值』可追溯，且是幂等键的载体。」

    ⚠️ BLOCK-13 未被设计定案裁定：strategy_version 存的是九项 Strategy
    Version 的整体标识，还是仅 Metric Version —— 文档未给值。本稿取
    【九项整体标识】（M1 已落地的四项 —— metric / evaluation_policy /
    code / data —— 的确定性摘要），并把这四项各自单列，理由是幂等键必须
    覆盖「换了任何一项就该重算」的全部输入；只放 Metric Version 会让改了
    MAR 之后的重跑被当成同一批次而静默跳过。构成规则登记在
    config/strategy/factor/v1.yaml，标 PROVISIONAL。

    本表是【状态流转表】（RUNNING → COMPLETED / FAILED），按
    04-database-design §4.3 允许 UPDATE，故设 updated_at ——
    与 factor_value 的「禁止 UPDATE、不设 updated_at」正好相反，
    这个差别本身就是设计信号。
    """

    __tablename__ = "factor_run"
    __table_args__ = (
        UniqueConstraint(
            "decision_at", "strategy_version", name="uq_factor_run_idempotency"
        ),
        CheckConstraint(FACTOR_RUN_STATE_SQL, name="ck_factor_run_state"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_factor_run_time_order",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_factor_run_duration"
        ),
        {"schema": "factor"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # DATE，与 PitDataContext.decision_at 同类型（platform/decision_data/context.py）。
    decision_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)
    # 可空：不依赖 MAR 的批次没有评价政策版本（与 factor_value 同一语义，D-13）。
    evaluation_policy_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(factor_run_status_enum, nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class FactorValue(Base, VersionedMixin):
    """全部因子结果 —— 【版本化事实表】（七列标准 + 两组 CHECK）。

    ── 时点列是 effective_at，不是 as_of_date（D-12 / BLOCK-6）──
    上游 04-database-design 内部矛盾：PK / 分区键 / W2 索引写 as_of_date，
    而同一文件 §9.3【已定案】的两个部分唯一索引写 effective_at，§4.4 的
    版本化标准列也是 effective_at。裁定统一为 effective_at：as_of_date 在
    Plan-1 落地的 20 张表里一次都没出现过，它是 API 层的查询参数名
    （PIT 语义），不是存储列名。

    ── 为什么 PK 是代理键而不是上游那五列 ──
    上游 PK 写的是 (share_class_id, factor_id, window, as_of_date, version)，
    但同一文件已定案的 ux_factor_value_with_policy 存在的【全部意义】就是
    让这五元组相同、仅 evaluation_policy_version 不同的两行共存（D-13：
    同一因子在不同评价政策下是不同的值）。五列 PK 会把这条定案索引变成
    永远无法被触发的死代码 —— 两条定案互相抵消。
    而六列 PK 也不成立：evaluation_policy_version 对不依赖 MAR 的因子
    必须为 NULL，PK 列不允许 NULL。
    因此身份由【两个部分唯一索引】承担，PK 退为代理键。这不是绕开约束，
    是唯一能同时满足两条定案的形状。详见本文件末尾发现清单第 3 条。

    ── 不分区（本稿裁定，PROVISIONAL）──
    上游按 as_of_date 月分区，依据是 1.5 亿行。M1 的量级是
    300 份额类别 × 10 因子 × ~250 个交易日 ≈ 75 万行，且 Plan-1 已经证明
    分区表带来真实成本（fund_nav 的 31 张子表在约束递归、TRUNCATE 级联、
    迁移往返上都要额外处理）。已实测 PostgreSQL 17 允许分区表上的部分唯一
    索引（分区键在索引列中即可），所以将来要分区不存在结构性障碍：
    effective_at 已经在两个索引里了。见 test_factor_value_is_not_partitioned。

    ── 禁止 UPDATE，不设 updated_at ──（04-database-design:117/:543）
    """

    __tablename__ = "factor_value"
    __table_args__ = (
        *temporal_check_constraints("factor_value"),
        CheckConstraint(FACTOR_VALUE_STATUS_SQL, name="ck_factor_value_status"),
        CheckConstraint(RF_REF_SQL, name="ck_factor_value_rf_ref"),
        CheckConstraint(PEER_CTX_SQL, name="ck_factor_value_peer_ctx"),
        CheckConstraint(
            NORMALIZED_NEEDS_CTX_SQL, name="ck_factor_value_normalized_ctx"
        ),
        CheckConstraint(
            "observation_count >= 0", name="ck_factor_value_observation_count"
        ),
        CheckConstraint(
            PERIOD_DOMAIN_SQL.format(col='"window"'), name="ck_factor_value_window"
        ),
        # ── D-13 的两个部分唯一索引：逐字照抄 04-database-design §9.3 的
        #    定案 SQL（as_of_date → effective_at 由 D-12 统一）。
        #    PostgreSQL 中 NULL 不参与唯一性比较，一条普通的
        #    UNIQUE(..., evaluation_policy_version) 对 NULL 行【完全不生效】，
        #    这正是上游选方案 A 而非触发器 / 生成列的原因。
        #    两条 postgresql_where 必须与迁移 0016 逐字一致（含 WHERE 子句），
        #    否则 autogenerate 会把它们当成待删除对象 —— 本仓库已三次被
        #    「库里有约束而 ORM metadata 里没有」咬出误删迁移。
        Index(
            "ux_factor_value_no_policy",
            "share_class_id", "factor_id", "window", "effective_at", "version",
            unique=True,
            postgresql_where=text("evaluation_policy_version IS NULL"),
        ),
        Index(
            "ux_factor_value_with_policy",
            "share_class_id", "factor_id", "window", "effective_at", "version",
            "evaluation_policy_version",
            unique=True,
            postgresql_where=text("evaluation_policy_version IS NOT NULL"),
        ),
        # W1：单基金单因子时间序列 + §15.1 的 PIT 点查通用要求
        # (business_key, available_at, version DESC)。两个部分唯一索引都带
        # WHERE，覆盖不到全表，所以 W1 需要一条非部分索引。
        Index(
            "ix_factor_value_pit",
            "share_class_id", "factor_id", "window", "effective_at",
            "available_at", text("version DESC"),
        ),
        # W2：横截面 —— 索引覆盖（04-database-design:659 逐字，as_of_date → effective_at）。
        Index(
            "ix_factor_value_cross_section",
            "effective_at", "factor_id", "share_class_id",
            postgresql_include=["raw_value", "normalized_value"],
        ),
        # W3：Peer Group 内分位（:1022 逐字）。
        Index(
            "ix_factor_value_peer_group",
            "peer_group_snapshot_id", "effective_at", "factor_id",
        ),
        # 批次追溯（:661 逐字）。
        Index("ix_factor_value_run", "factor_run_id"),
        {"schema": "factor"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    # 外键指向 factor_definition.factor_id（01-postgresql.md:421 点名 RESTRICT）。
    # 存业务键而非代理键，是为了让上游那条五元组身份原样可读。
    factor_id: Mapped[str] = mapped_column(
        ForeignKey("factor.factor_definition.factor_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # ⚠️ "window" 是 PostgreSQL 保留字（窗口函数），必须加引号。
    # SQLAlchemy 的 postgresql 方言把它列在 RESERVED_WORDS 里会自动加引号，
    # 但手写 SQL（含 CHECK 表达式）里必须自己写成 "window" —— 见上面
    # PERIOD_DOMAIN_SQL.format(col='"window"')。列名保留上游字面，不改名。
    window: Mapped[str] = mapped_column(String(4), nullable=False)
    factor_version_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_version.id", ondelete="RESTRICT"), nullable=False
    )
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    raw_value: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    normalized_value: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    status: Mapped[str] = mapped_column(factor_status_enum, nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(
        factor_unavailable_reason_enum, nullable=True
    )
    # D-10 的 WARNING / UNAVAILABLE 判据（观测数与 min_obs 的关系）在事后
    # 只有存下观测数才能复核，否则「为什么这条是 WARNING」无从回答。
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # ── 标准化上下文。03-erd §8.5：「Peer Group 与 Factor Value 的关系是
    #    『上下文』而非『归属』…这是一条弱关系（引用，非组合）」。
    #    FK 由迁移 0017 补上 —— evaluation.peer_group_snapshot 那时才存在。
    #    Task 8 Step 9 会同时改本文件与 0017，两处必须一起改。
    peer_group_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    peer_group_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ── R_f 溯源四列（§9.2.1）。BLOCK-14「JSONB 或列组」上游未裁决，
    #    本稿取【列组】：四个字段是固定的、要进 WHERE 的（「这只基金的 1Y 与
    #    3Y Sharpe 是不是用错了 tenor」是核对查询，不是展示），按
    #    01-postgresql §13.2 的判据必须结构化；JSONB 还会让键名拼错静默通过。
    #    「不进唯一约束」（:570）—— 它是溯源，与 evaluation_policy_version 相反。
    risk_free_rate_currency: Mapped[str | None] = mapped_column(
        String(8), nullable=True
    )
    risk_free_rate_tenor: Mapped[str | None] = mapped_column(String(8), nullable=True)
    risk_free_rate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_free_rate_quality: Mapped[str | None] = mapped_column(
        availability_quality_enum, nullable=True
    )
    # D-13：evaluation_policy_version【是】标识的一部分，进两个部分唯一索引。
    # 依赖 MAR 的因子必填、其余必须为 NULL —— NULL 与非 NULL 分别落进两个
    # 部分索引，这正是方案 A 的全部机制。
    evaluation_policy_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)


class FactorEffectiveness(Base):
    """IC / ICIR 检验结果 —— 由 D-1 从 M2 拉回 Plan-2。

    「factor_effectiveness 的存在性是 Score 产出的前置条件，不是可选的补充
    信息」（FS:346）。没有它，score_status 只能是 VALIDATION_PENDING，
    总分根本不产出，M1.4 的验收标准自己通不过。

    ── 为什么只有 factor_version_id、没有单独的 factor_id 列 ──
    D-16 描述本表为 (profile, factor_id, valid/invalid, IC, ICIR, 检验区间)，
    而 03-erd:448 与 04-database-design:620 都写的是 factor_version_id
    （「被检验的因子版本」，且它进 Business Key）。两者不冲突：factor_id
    是 factor_version → factor_definition 的传递属性。再存一份副本会造出
    第二份真值 —— 一条 factor_version_id 指向 A 因子、factor_id 写着 B
    的行在数据库层面无法被拒。检验的对象本来就是【口径版本】而不是因子：
    换了 ddof 就得重检，factor_id 不变而结论会变。

    本表不设 updated_at：检验结果一经产出即不可变，重检产生新行
    （新的 factor_run_id / 检验区间），旧行保留。
    """

    __tablename__ = "factor_effectiveness"
    __table_args__ = (
        UniqueConstraint(
            "factor_version_id", "evaluation_profile",
            "test_window_start", "test_window_end", "validation_policy_version",
            name="uq_factor_effectiveness_business",
        ),
        CheckConstraint(
            EFFECTIVENESS_VERDICT_SQL, name="ck_factor_effectiveness_verdict"
        ),
        CheckConstraint(
            "test_window_start < test_window_end",
            name="ck_factor_effectiveness_window",
        ),
        CheckConstraint("n_periods >= 0", name="ck_factor_effectiveness_n_periods"),
        {"schema": "factor"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factor_version_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_version.id", ondelete="RESTRICT"), nullable=False
    )
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    # M1 只有一个 Profile（设计定案 §7 已知缺口 3），但列必须在 ——
    # G-10「按 Profile 拆分」在 M1 是空洞成立的，缺了这一列，M2 加第二个
    # Profile 时会静默把两套检验结论叠在一起。
    evaluation_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    test_window_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    test_window_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    ic: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    icir: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    n_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(
        factor_effectiveness_verdict_enum, nullable=False
    )
    # 阈值本身不落本表（IC ≥ 0.02、|ICIR| ≥ 0.3 属 validation_policy，
    # FS:350「本域是消费方不是定义方」）。这里只存判定【结果】与用的是哪一版。
    validation_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: 建包并在 `db/migrations/env.py` 注册（漏了它 autogenerate 静默失效）**

```python
# src/fip/services/factor_service/models/__init__.py
```
（空文件，与 `data_service/models/__init__.py` 一致。）

```python
# db/migrations/env.py —— 在既有的 services 层 import 之后追加一行
from fip.services.data_service.models import raw  # noqa: F401 — services 层
from fip.services.factor_service.models import factor  # noqa: F401 — services 层
```

`tests/fitness/test_architecture.py::test_every_orm_model_module_is_registered_in_env`
会校验这份清单与 `src/fip` 下实际存在的 Base 子类模块一致 —— 漏了这行，
它会直接失败，不必等到 autogenerate 出事。

- [ ] **Step 6: 写迁移 `db/migrations/versions/0016_factor_schema.py`**

用 `op.create_table` + `sa.Column` 而非 raw SQL：`window` 是 PostgreSQL
保留字，交给 SQLAlchemy 加引号比手写靠谱；且 0013 已立了这个先例。

```python
# db/migrations/versions/0016_factor_schema.py
"""factor schema 五张表 + 七个枚举

Plan-2 Task 7。落 factor_definition / factor_version / factor_run /
factor_value / factor_effectiveness。

裁定依据（docs/superpowers/specs/2026-09-02-plan2-factor-and-evaluation-design.md）：
  · D-12  时点列统一为 effective_at，不是 as_of_date（BLOCK-6）
  · D-13  evaluation_policy_version 进唯一约束；risk_free_rate_ref 不进；
          window 必须进
  · D-16  三张表的字段设计属【补齐】（BLOCK-2），形状随本 Plan 给出
  · D-1   factor_effectiveness 由 M2 拉回 Plan-2

【已冻结的字面量】迁移是不可编辑的历史，它产出的 DDL 必须与当初执行时逐字
相同。因此本文件【不】import ORM 模块里的 SQL 常量，而是把当时的字符串原样
固化在这里；今后的语义变更一律由新迁移承担（0011 / 0013 的同一条教训）。
唯一的例外是 mixins 的 QUALITY_SOURCE_SQL —— 与 0013 保持一致的写法。

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_SCHEMA = "factor"

# ---- 冻结的 CHECK 字面量（与 ORM 中的常量逐字相同）----
_QUALITY_SOURCE_SQL = (
    "(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR "
    "(availability_quality = 'DERIVED' AND provider_available_at IS NULL "
    " AND published_at IS NOT NULL) OR "
    "(availability_quality = 'INFERRED' AND provider_available_at IS NULL "
    " AND published_at IS NULL)"
)
# 五子句（clause 1..5），anchor = effective_at 且已钉 UTC —— 与迁移 0015
# 之后 mixins.TIME_ORDER_SQL 的产出逐字相同。
_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= "
    "(effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= (effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(available_at >= COALESCE(provider_available_at, published_at))"
)
_FACTOR_ID_SHAPE_SQL = "factor_id ~ ('^F-' || category::text || '-[0-9]{3}$')"
_FACTOR_USAGE_SQL = (
    "usage_display OR usage_scoring OR usage_screening "
    "OR usage_portfolio OR usage_backtest"
)
_WINDOW_DOMAIN_SQL = "\"window\" IN ('1M', '3M', '6M', '1Y', '3Y', '5Y')"
_FACTOR_RUN_STATE_SQL = (
    "(status = 'RUNNING' AND finished_at IS NULL AND duration_ms IS NULL) OR "
    "(status IN ('COMPLETED', 'FAILED') "
    " AND finished_at IS NOT NULL AND duration_ms IS NOT NULL)"
)
_FACTOR_VALUE_STATUS_SQL = (
    "(status IN ('VALID', 'WARNING') "
    " AND raw_value IS NOT NULL AND unavailable_reason IS NULL) OR "
    "(status = 'INVALID' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND unavailable_reason IS NULL) OR "
    "(status = 'UNAVAILABLE' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND unavailable_reason IS NOT NULL)"
)
_RF_REF_SQL = (
    "num_nonnulls(risk_free_rate_currency, risk_free_rate_tenor, "
    "risk_free_rate_version, risk_free_rate_quality) IN (0, 4)"
)
_PEER_CTX_SQL = (
    "(peer_group_snapshot_id IS NULL AND peer_group_version IS NULL) OR "
    "(peer_group_snapshot_id IS NOT NULL AND peer_group_version IS NOT NULL)"
)
_NORMALIZED_NEEDS_CTX_SQL = (
    "normalized_value IS NULL OR peer_group_snapshot_id IS NOT NULL"
)
_EFFECTIVENESS_VERDICT_SQL = (
    "verdict = 'INVALID' OR (ic IS NOT NULL AND icir IS NOT NULL)"
)

# ---- 枚举。create_type=False：类型由下面的 op.execute 显式创建。
# ⚠️ 用 postgresql.ENUM 而不是 sa.Enum —— 后者【静默忽略】create_type，
# 会在第二张用同一枚举的表上炸 "type already exists"（本仓库踩过）。
_ENUM_DDL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("factor_category_enum", ("RET", "RISK", "RAP", "STAB", "REL")),
    ("preference_direction_enum", (
        "HIGHER_IS_BETTER", "LOWER_IS_BETTER", "TARGET_RANGE", "STRATEGY_DEPENDENT")),
    ("factor_status_enum", ("VALID", "WARNING", "INVALID", "UNAVAILABLE")),
    ("factor_unavailable_reason_enum", (
        "INSUFFICIENT_HISTORY", "BENCHMARK_UNAVAILABLE",
        "RISK_FREE_RATE_UNAVAILABLE", "MAR_NOT_CONFIGURED",
        "ZERO_MAX_DRAWDOWN", "ZERO_DOWNSIDE_VOLATILITY",
        "ZERO_TRACKING_ERROR", "ZERO_VOLATILITY")),
    ("factor_run_status_enum", ("RUNNING", "COMPLETED", "FAILED")),
    ("factor_effectiveness_verdict_enum", ("VALID", "INVALID")),
    ("provenance_enum", ("DECIDED", "PROVISIONAL")),
)


def _enum(name: str) -> postgresql.ENUM:
    values = dict(_ENUM_DDL)[name]
    return postgresql.ENUM(*values, name=name, create_type=False)


_QUALITY_ENUM = postgresql.ENUM(
    "EXACT", "DERIVED", "INFERRED",
    name="availability_quality_enum", create_type=False,
)


def _time_source_columns() -> list[sa.Column]:
    """VersionedMixin 的七列标准中的六列（effective_at / version 单列写出）。"""
    return [
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_quality", _QUALITY_ENUM, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    ]


def upgrade() -> None:
    # 枚举【不带 schema 限定】→ 落在 public，与 0001 的
    # availability_quality_enum 一致，也是 tests/conftest.py 的
    # `DROP SCHEMA public CASCADE` 能清干净它们的前提。
    for name, values in _ENUM_DDL:
        rendered = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({rendered})")

    # ---------------------------------------------------------- factor_definition
    op.create_table(
        "factor_definition",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("factor_id", sa.String(length=32), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("category", _enum("factor_category_enum"), nullable=False),
        sa.Column(
            "preference_direction", _enum("preference_direction_enum"), nullable=False
        ),
        sa.Column("usage_display", sa.Boolean(), nullable=False),
        sa.Column("usage_scoring", sa.Boolean(), nullable=False),
        sa.Column("usage_screening", sa.Boolean(), nullable=False),
        sa.Column("usage_portfolio", sa.Boolean(), nullable=False),
        sa.Column("usage_backtest", sa.Boolean(), nullable=False),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(_FACTOR_ID_SHAPE_SQL, name="ck_factor_definition_id_shape"),
        sa.CheckConstraint(_FACTOR_USAGE_SQL, name="ck_factor_definition_usage"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("factor_id", name="uq_factor_definition_factor_id"),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------- factor_version
    op.create_table(
        "factor_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("factor_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("version_label", sa.String(length=32), nullable=False),
        sa.Column("formula_ref", sa.String(length=128), nullable=False),
        sa.Column("metric_config_digest", sa.String(length=64), nullable=False),
        sa.Column("min_obs", sa.Integer(), nullable=False),
        sa.Column("requires_risk_free_rate", sa.Boolean(), nullable=False),
        sa.Column("requires_mar", sa.Boolean(), nullable=False),
        sa.Column("requires_benchmark", sa.Boolean(), nullable=False),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint("min_obs > 0", name="ck_factor_version_min_obs"),
        sa.CheckConstraint(
            "char_length(metric_config_digest) = 64",
            name="ck_factor_version_digest_shape",
        ),
        sa.ForeignKeyConstraint(
            ["factor_definition_id"], ["factor.factor_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "factor_definition_id", "version_label", name="uq_factor_version_label"
        ),
        schema=_SCHEMA,
    )

    # ----------------------------------------------------------------- factor_run
    op.create_table(
        "factor_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("decision_at", sa.Date(), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("code_version", sa.String(length=64), nullable=False),
        sa.Column("evaluation_policy_version", sa.String(length=32), nullable=True),
        sa.Column("data_version", sa.String(length=32), nullable=False),
        sa.Column("status", _enum("factor_run_status_enum"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(_FACTOR_RUN_STATE_SQL, name="ck_factor_run_state"),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_factor_run_time_order",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_factor_run_duration"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_at", "strategy_version", name="uq_factor_run_idempotency"
        ),
        schema=_SCHEMA,
    )

    # --------------------------------------------------------------- factor_value
    op.create_table(
        "factor_value",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("factor_id", sa.String(length=32), nullable=False),
        # 保留字，SQLAlchemy 会渲染成 "window"。
        sa.Column("window", sa.String(length=4), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("factor_version_id", sa.BigInteger(), nullable=False),
        sa.Column("factor_run_id", sa.BigInteger(), nullable=False),
        sa.Column("raw_value", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column(
            "normalized_value", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column("status", _enum("factor_status_enum"), nullable=False),
        sa.Column(
            "unavailable_reason",
            _enum("factor_unavailable_reason_enum"), nullable=True,
        ),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        # FK 由 0017 补（evaluation.peer_group_snapshot 此刻还不存在）。
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("peer_group_version", sa.Integer(), nullable=True),
        sa.Column("risk_free_rate_currency", sa.String(length=8), nullable=True),
        sa.Column("risk_free_rate_tenor", sa.String(length=8), nullable=True),
        sa.Column("risk_free_rate_version", sa.Integer(), nullable=True),
        sa.Column("risk_free_rate_quality", _QUALITY_ENUM, nullable=True),
        sa.Column("evaluation_policy_version", sa.String(length=32), nullable=True),
        sa.Column("data_version", sa.String(length=32), nullable=False),
        *_time_source_columns(),
        sa.CheckConstraint(_QUALITY_SOURCE_SQL, name="ck_factor_value_quality_source"),
        sa.CheckConstraint(_TIME_ORDER_SQL, name="ck_factor_value_time_order"),
        sa.CheckConstraint(_FACTOR_VALUE_STATUS_SQL, name="ck_factor_value_status"),
        sa.CheckConstraint(_RF_REF_SQL, name="ck_factor_value_rf_ref"),
        sa.CheckConstraint(_PEER_CTX_SQL, name="ck_factor_value_peer_ctx"),
        sa.CheckConstraint(
            _NORMALIZED_NEEDS_CTX_SQL, name="ck_factor_value_normalized_ctx"
        ),
        sa.CheckConstraint(
            "observation_count >= 0", name="ck_factor_value_observation_count"
        ),
        sa.CheckConstraint(_WINDOW_DOMAIN_SQL, name="ck_factor_value_window"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_id"], ["factor.factor_definition.factor_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_version_id"], ["factor.factor_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_run_id"], ["factor.factor_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    # D-13 的两个部分唯一索引 —— 逐字照抄 04-database-design §9.3 定案 SQL
    # （as_of_date → effective_at 由 D-12 统一）。WHERE 子句必须与 ORM 的
    # postgresql_where 逐字一致，否则 autogenerate 会提议 DROP。
    op.create_index(
        "ux_factor_value_no_policy", "factor_value",
        ["share_class_id", "factor_id", "window", "effective_at", "version"],
        unique=True, schema=_SCHEMA,
        postgresql_where=sa.text("evaluation_policy_version IS NULL"),
    )
    op.create_index(
        "ux_factor_value_with_policy", "factor_value",
        ["share_class_id", "factor_id", "window", "effective_at", "version",
         "evaluation_policy_version"],
        unique=True, schema=_SCHEMA,
        postgresql_where=sa.text("evaluation_policy_version IS NOT NULL"),
    )
    op.create_index(
        "ix_factor_value_pit", "factor_value",
        ["share_class_id", "factor_id", "window", "effective_at",
         "available_at", sa.text("version DESC")],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_factor_value_cross_section", "factor_value",
        ["effective_at", "factor_id", "share_class_id"],
        schema=_SCHEMA,
        postgresql_include=["raw_value", "normalized_value"],
    )
    op.create_index(
        "ix_factor_value_peer_group", "factor_value",
        ["peer_group_snapshot_id", "effective_at", "factor_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_factor_value_run", "factor_value", ["factor_run_id"], schema=_SCHEMA
    )

    # -------------------------------------------------------- factor_effectiveness
    op.create_table(
        "factor_effectiveness",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("factor_version_id", sa.BigInteger(), nullable=False),
        sa.Column("factor_run_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluation_profile", sa.String(length=32), nullable=False),
        sa.Column("test_window_start", sa.Date(), nullable=False),
        sa.Column("test_window_end", sa.Date(), nullable=False),
        sa.Column("ic", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("icir", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("n_periods", sa.Integer(), nullable=False),
        sa.Column(
            "verdict", _enum("factor_effectiveness_verdict_enum"), nullable=False
        ),
        sa.Column("validation_policy_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            _EFFECTIVENESS_VERDICT_SQL, name="ck_factor_effectiveness_verdict"
        ),
        sa.CheckConstraint(
            "test_window_start < test_window_end",
            name="ck_factor_effectiveness_window",
        ),
        sa.CheckConstraint("n_periods >= 0", name="ck_factor_effectiveness_n_periods"),
        sa.ForeignKeyConstraint(
            ["factor_version_id"], ["factor.factor_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_run_id"], ["factor.factor_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "factor_version_id", "evaluation_profile",
            "test_window_start", "test_window_end", "validation_policy_version",
            name="uq_factor_effectiveness_business",
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    # 反 FK 顺序：effectiveness / value 先走，然后 run / version / definition。
    op.drop_table("factor_effectiveness", schema=_SCHEMA)
    op.drop_index("ix_factor_value_run", table_name="factor_value", schema=_SCHEMA)
    op.drop_index(
        "ix_factor_value_peer_group", table_name="factor_value", schema=_SCHEMA
    )
    op.drop_index(
        "ix_factor_value_cross_section", table_name="factor_value", schema=_SCHEMA
    )
    op.drop_index("ix_factor_value_pit", table_name="factor_value", schema=_SCHEMA)
    op.drop_index(
        "ux_factor_value_with_policy", table_name="factor_value", schema=_SCHEMA
    )
    op.drop_index(
        "ux_factor_value_no_policy", table_name="factor_value", schema=_SCHEMA
    )
    op.drop_table("factor_value", schema=_SCHEMA)
    op.drop_table("factor_run", schema=_SCHEMA)
    op.drop_table("factor_version", schema=_SCHEMA)
    op.drop_table("factor_definition", schema=_SCHEMA)
    for name, _ in reversed(_ENUM_DDL):
        op.execute(f"DROP TYPE IF EXISTS {name}")
```

- [ ] **Step 7: upgrade → downgrade → upgrade 往返验证**

`psql` / `createdb` 不在 PATH，全部经 venv 里的 psycopg / SQLAlchemy 与
`FIP_DATABASE_URL` 指定库。先在一个一次性库上做，不碰 `fip_dev`：

```bash
# 建一次性验证库（createdb 不可用 → 用 psycopg 的 autocommit 连接执行 CREATE DATABASE）
.venv/bin/python - <<'PY'
import psycopg
with psycopg.connect("postgresql://localhost/postgres", autocommit=True) as c:
    c.execute("DROP DATABASE IF EXISTS fip_rt0016")
    c.execute("CREATE DATABASE fip_rt0016")
print("fip_rt0016 ready")
PY

export FIP_DATABASE_URL=postgresql+psycopg://localhost/fip_rt0016
.venv/bin/alembic -x db=dev upgrade head        # 0001 → 0016
.venv/bin/alembic -x db=dev downgrade 0015      # 0016 的 downgrade()
.venv/bin/alembic -x db=dev upgrade head        # 再上来一次
.venv/bin/alembic -x db=dev current             # 期望：0016 (head)
```

往返后必须验证「五张表 + 七个枚举都回来了、且 downgrade 时确实都走干净了」：

```bash
.venv/bin/python - <<'PY'
import psycopg
Q_T = """SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='factor' AND c.relkind IN ('r','p') ORDER BY 1"""
Q_E = """SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
         WHERE n.nspname='public' AND t.typtype='e' ORDER BY 1"""
with psycopg.connect("postgresql://localhost/fip_rt0016") as c:
    print("tables:", [r[0] for r in c.execute(Q_T)])
    print("enums :", [r[0] for r in c.execute(Q_E)])
PY
```

Expected:
```
tables: ['factor_definition', 'factor_effectiveness', 'factor_run', 'factor_value', 'factor_version']
enums : ['availability_quality_enum', 'factor_category_enum',
         'factor_effectiveness_verdict_enum', 'factor_run_status_enum',
         'factor_status_enum', 'factor_unavailable_reason_enum',
         'preference_direction_enum', 'provenance_enum']
```

**downgrade 漏删枚举是本步最可能的失败形态**：`DROP TABLE` 不会连带删掉
枚举类型，第二次 `upgrade` 会炸在 `type ... already exists`。上面的
往返序列（downgrade 后再 upgrade）就是专门用来把它逼出来的 —— 若
`downgrade()` 里少了那个 `DROP TYPE` 循环，第三条 alembic 命令必然失败。

验证完删库：

```bash
.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://localhost/postgres', autocommit=True) as c:
    c.execute('DROP DATABASE IF EXISTS fip_rt0016')
print('dropped')"
unset FIP_DATABASE_URL
```

- [ ] **Step 8: G-16 闸门 —— autogenerate 必须报告零操作**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev revision --autogenerate -m "probe-0016" 2>&1 | tail -20
```

Expected: 生成的迁移文件里 `upgrade()` / `downgrade()` **都只有 `pass`**。
确认后立刻删掉探针文件：

```bash
rm db/migrations/versions/*probe-0016*.py
```

最常见的三种非零输出与成因：
- `op.drop_index('ux_factor_value_no_policy', ...)` → ORM 的
  `postgresql_where` 与迁移的 WHERE 子句不逐字相同；
- `op.create_index('ix_factor_value_cross_section', ...)` → ORM 漏了
  `postgresql_include`；
- 整张表被提议 DROP → `env.py` 忘了 import `factor` 模块（Step 5）。

- [ ] **Step 9: G-17 —— 重新生成 CHECK 黄金快照**

autogenerate **对 CHECK 表达式失明**（实测把整条约束换成 `CHECK (1=1)`
它仍报零操作）。本任务新增了 11 条 CHECK，必须重新生成快照：

```bash
# ① 重新生成（该命令【故意】以失败结束，这是设计如此）
FIP_WRITE_CHECK_SNAPSHOT=1 .venv/bin/pytest \
    tests/integration/test_temporal_constraints.py -k snapshot

# ② 逐条确认 diff —— 只应新增 factor.* 的行，不得有任何既有行被改动
git diff tests/integration/check_constraints.snapshot

# ③ 不带环境变量重跑，必须绿
.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot
```

Expected diff：只新增 factor schema 下的 11 条（`ck_factor_definition_id_shape`、
`ck_factor_definition_usage`、`ck_factor_version_min_obs`、
`ck_factor_version_digest_shape`、`ck_factor_run_state`、
`ck_factor_run_time_order`、`ck_factor_run_duration`、
`ck_factor_value_quality_source`、`ck_factor_value_time_order`、
`ck_factor_value_status`、`ck_factor_value_rf_ref`、`ck_factor_value_peer_ctx`、
`ck_factor_value_normalized_ctx`、`ck_factor_value_observation_count`、
`ck_factor_value_window`、`ck_factor_effectiveness_verdict`、
`ck_factor_effectiveness_window`、`ck_factor_effectiveness_n_periods`）。
**既有的 fund / market / governance 行一行都不得变** —— 若变了，说明
0016 里冻结的 `_TIME_ORDER_SQL` 与 mixins 的现状不一致，先查那个。

- [ ] **Step 10: 全量验证**

```bash
.venv/bin/pytest tests/integration/test_factor_schema.py -v   # 新测试全绿
.venv/bin/pytest tests/unit tests/fitness tests/integration    # 281 + 新增，全绿
.venv/bin/ruff check src tests
make typecheck
```

Expected: 281 passed 之上新增本任务的用例，无 failed / error；ruff 与
mypy strict 均无输出。

---

### Task 8: `evaluation` schema 九张表 + 迁移 0017

**Files:**

- Create: `src/fip/services/fund_service/models/__init__.py`
- Create: `src/fip/services/fund_service/models/evaluation.py`
- Create: `db/migrations/versions/0017_evaluation_schema.py`
- Create: `tests/integration/test_evaluation_schema.py`
- Modify: `src/fip/platform/db/enums.py`（追加 9 个 `evaluation` 侧枚举声明）
- Modify: `src/fip/services/factor_service/models/factor.py`
  （Task 7 留下的 `peer_group_snapshot_id` 在本任务补上 FK —— 目标表此刻才存在）
- Modify: `db/migrations/env.py`
- Modify: `tests/integration/check_constraints.snapshot`（G-17，由测试重新生成）

**Interfaces:**

```python
# ---- Consumes（Task 7 产出 + Plan-1）----
from fip.platform.db.base import Base
from fip.platform.db.mixins import VersionedMixin, temporal_check_constraints
from fip.platform.db.types import NavNumeric, RatioNumeric
from fip.platform.db.enums import preference_direction_enum   # Task 7 已声明
# 外键目标：
#   fund.fund_share_class.id                                   BIGINT
#   fund.fund_classification_history.id                        BIGINT
#   fund.investment_eligibility (share_class_id, effective_at, version)  复合 PK
#   factor.factor_run.id                                       BIGINT
#   factor.factor_value.id                                     BIGINT
#   factor.factor_definition.factor_id                         VARCHAR(32) UNIQUE

# ---- Produces（Task 11 / 14 / 15 / 16 / 17 消费）----
# src/fip/platform/db/enums.py（追加）
cross_section_status_enum: postgresql.ENUM    # NORMAL INSUFFICIENT_SAMPLE
score_status_enum: postgresql.ENUM            # COMPLETED PARTIAL UNAVAILABLE
                                              # VALIDATION_PENDING INSUFFICIENT_FACTORS
sub_score_status_enum: postgresql.ENUM        # AVAILABLE UNAVAILABLE INSUFFICIENT_FACTORS
sub_score_name_enum: postgresql.ENUM          # Return Risk Risk-Adjusted
                                              # Stability "Relative Performance"
fund_tier_enum: postgresql.ENUM               # A+ A B C D
selection_status_enum: postgresql.ENUM        # SELECTED REJECTED
universe_status_enum: postgresql.ENUM         # COMPLETED INSUFFICIENT_UNIVERSE
condition_outcome_enum: postgresql.ENUM       # PASS FAIL NOT_EVALUABLE
attribution_participation_enum: postgresql.ENUM  # INCLUDED EXCLUDED

# src/fip/services/fund_service/models/evaluation.py
class PeerGroupSnapshot(Base)          # evaluation.peer_group_snapshot   【快照】
class PeerGroupMember(Base)            # evaluation.peer_group_member     【明细·不分区】
class FundScore(Base, VersionedMixin)  # evaluation.fund_score            【版本化事实】
class FundScoreAttribution(Base)       # evaluation.fund_score_attribution【明细】
class FundRanking(Base)                # evaluation.fund_ranking          【派生·0..1】
class FundTier(Base)                   # evaluation.fund_tier             【派生·0..1】
class FundUniverseSnapshot(Base)       # evaluation.fund_universe_snapshot【快照】
class FundUniverseMember(Base)         # evaluation.fund_universe_member  【明细·含 REJECTED】
class SelectionConditionResult(Base)   # evaluation.selection_condition_result
```

**本任务贯穿全程的四条硬约束**（每张表都要对照）：

| # | 约束 | 落法 |
|---|---|---|
| D-18 | 快照表**不设 `updated_at`** | 九张表**没有一张**有 `updated_at`；`fund_score` 是版本化事实表，同样禁止 UPDATE |
| D-18 | FK **一律 `ON DELETE RESTRICT`** | 全部 22 条 FK 无一例外；不使用 `CASCADE`（`04-database-design:1081` 的 CASCADE 白名单只点名 `binding_constraint`） |
| D-18 | 快照相关表**只建必要的 PK 与 FK 索引** | 不为「可能的查询」预建（`:1039`）。唯一的例外写在 `fund_score_attribution` 上并给出理由 |
| D-17 | `REJECTED` 与**全部**条件结果落库 | `fund_universe_member.selection_status` + `selection_condition_result` 存全部条件；条件求值不得短路（测试在 Task 16 断言） |

- [ ] **Step 1: 在 `src/fip/platform/db/enums.py` 追加 9 个枚举**

```python
# src/fip/platform/db/enums.py —— 在 factor 侧枚举之后追加

# ---- evaluation schema（迁移 0017 创建）----

cross_section_status_enum = ENUM(
    "NORMAL", "INSUFFICIENT_SAMPLE",
    name="cross_section_status_enum", create_type=False,
)
"""逐字采用上游已定案的 CREATE TYPE（04-database-design:718）。

G-7：判定基数是 n_effective（某指标的有效参与数）而非组规模 ——
一个 50 只基金的组里若某指标只有 25 只可算，该指标仍属小样本。
阈值本身（MIN_PEER_GROUP_SIZE = 30）【不落】fund_ranking / fund_tier，
它属 governance.policy_version 的 Peer Group Policy（min_sample_size），
标准化 / 排名 / 分层三处共用同一配置来源。表里存的是判定【结果】，
不是判定【参数】（:734）。
"""

score_status_enum = ENUM(
    "COMPLETED", "PARTIAL", "UNAVAILABLE",
    "VALIDATION_PENDING", "INSUFFICIENT_FACTORS",
    name="score_status_enum", create_type=False,
)
"""D-19：五值。上游有三种说法（FS:590 三值 / FS:342 加 VALIDATION_PENDING /
FS:336 又冒出 NOT_AVAILABLE），裁定 NOT_AVAILABLE 与 UNAVAILABLE 是同一
概念的两种拼写，统一取 UNAVAILABLE（与 factor_status_enum 一致）。

⚠️ M1 的【常态是 PARTIAL】—— Relative Performance Score 恒 UNAVAILABLE
（无 Benchmark）。这必须被测试显式断言，否则「PARTIAL 是正常的」这个
事实会在下游被当成异常处理。
"""

sub_score_status_enum = ENUM(
    "AVAILABLE", "UNAVAILABLE", "INSUFFICIENT_FACTORS",
    name="sub_score_status_enum", create_type=False,
)
"""子分级状态。刻意与 score_status_enum 分开：子分没有 PARTIAL
（子分要么算出来了要么没有），也没有 VALIDATION_PENDING（那是整条
Score 的前置条件，不是某个子分的）。共用一个枚举会让三个不可能的
取值在子分列上变成合法值。

INSUFFICIENT_FACTORS 对应上游已定案的「子分内有效指标数 < 2 时该子分
UNAVAILABLE，不做权重重分配」—— 它与「一个因子都没有」是不同的事实，
分开才能事后回答「是因子太少还是完全没算」。
"""

sub_score_name_enum = ENUM(
    "Return", "Risk", "Risk-Adjusted", "Stability", "Relative Performance",
    name="sub_score_name_enum", create_type=False,
)
"""五个子分的命名【固定，不得更改】（02-fund-scoring.md:93「沿用上游
§4.2 ③-S，命名不得更改」）。原样保留空格与连字符，包括
"Relative Performance" 中间的空格 —— 改成 RELATIVE_PERFORMANCE 就是
「更改命名」。跨任务接口契约里的 SubScoreName 取的正是这五个字面量。
"""

fund_tier_enum = ENUM(
    "A+", "A", "B", "C", "D",
    name="fund_tier_enum", create_type=False,
)
"""五档（04-fund-classification.md:110-116，本域不得改动）。

⚠️ BLOCK-12：上游没有给这个类型名，也没有 CREATE TYPE 语句 —— 类型名
为【补齐】。取值本身是逐字的。
"""

selection_status_enum = ENUM(
    "SELECTED", "REJECTED",
    name="selection_status_enum", create_type=False,
)
"""D-17 / G-11 的载体。REJECTED 不是「不落库」的同义词 ——
「若只存入池成员 → 无法验证是否有基金被错误排除 → 而错误排除正是
幸存者偏差的表现形式」（03-erd §9.2）。
"""

universe_status_enum = ENUM(
    "COMPLETED", "INSUFFICIENT_UNIVERSE",
    name="universe_status_enum", create_type=False,
)
"""快照级状态（05-fund-selection.md:308）。规模不足时「标
INSUFFICIENT_UNIVERSE 并阻断本期组合构建，不降级为『用更少的基金优化』」。
落成列而不是抛异常了事：阻断本身是需要留痕的事实，否则历史查询无法区分
「当时池子太小」与「当时根本没跑」。
"""

condition_outcome_enum = ENUM(
    "PASS", "FAIL", "NOT_EVALUABLE",
    name="condition_outcome_enum", create_type=False,
)
"""前两值来自 §14.2 的 ✓/✗。

NOT_EVALUABLE 是【补齐】：上游把「存全部条件」的理由写成「只存未通过项
→ 无法区分『通过了』与『根本没评估』，而后者会在条件集变更时大量出现」
（04-database-design §10.3.1）。存全部条件解决了条件集变更那一半，但还有
另一半 —— 某条件的输入本身 UNAVAILABLE（如 Sharpe 下限，而该基金 Sharpe
不可算）。把它记成 FAIL 会把「没法判」伪装成「判了，没过」，正是 G-3
在条件层的同一个错误。
"""

attribution_participation_enum = ENUM(
    "INCLUDED", "EXCLUDED",
    name="attribution_participation_enum", create_type=False,
)
"""§10.4：「被排除的因子必须记录【为什么被排除】，而非从归因中消失。」
EXCLUDED 的行同样落库，带原权重与重分配去向。
"""
```

- [ ] **Step 2: 先写失败的集成测试 `tests/integration/test_evaluation_schema.py`**

G-18：本步只写测试，此刻九张表都不存在。

```python
# tests/integration/test_evaluation_schema.py
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundShareClass,
    InvestmentEligibility,
)
from fip.services.factor_service.models.factor import FactorRun
from fip.services.fund_service.models.evaluation import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTier,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupMember,
    PeerGroupSnapshot,
    SelectionConditionResult,
)

pytestmark = pytest.mark.integration

ING = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)
AVAIL = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
EFF = dt.date(2026, 8, 31)


def _times():
    return dict(available_at=AVAIL, availability_quality="INFERRED",
                published_at=None, provider_available_at=None, ingested_at=ING)


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-EVA", product_name="评价测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="评价测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


@pytest.fixture()
def classification(db_session, share_class) -> FundClassificationHistory:
    row = FundClassificationHistory(
        fund_id=share_class.fund_id, classification_scheme="AKSHARE_FUND_TYPE",
        classification_code="混合型-偏股", valid_from=dt.date(2020, 1, 1),
        valid_to=None, **_times(),
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture()
def peer_group(db_session) -> PeerGroupSnapshot:
    snap = PeerGroupSnapshot(
        classification_scheme="AKSHARE_FUND_TYPE", classification_level="L1",
        classification_code="混合型", base_currency="CNY",
        effective_at=EFF, version=1, member_count=42,
        classification_policy_version="CP-v1", peer_group_policy_version="PGP-v1",
        code_version="0.1.0+g1234567",
    )
    db_session.add(snap)
    db_session.flush()
    return snap


@pytest.fixture()
def run(db_session) -> FactorRun:
    r = FactorRun(
        decision_at=EFF, strategy_version="SV-eva", code_version="0.1.0+g1234567",
        evaluation_policy_version="EP-v1", data_version="DV-2026-08-31",
        status="COMPLETED", started_at=ING, finished_at=ING, duration_ms=1200,
    )
    db_session.add(r)
    db_session.flush()
    return r


def _score(share_class, peer_group, run, **overrides):
    row = dict(
        share_class_id=share_class.id, evaluation_profile="DEFAULT",
        evaluation_period="1Y", effective_at=EFF, version=1,
        total_score=Decimal("85.000"), score_status="PARTIAL",
        return_score=Decimal("80.000"), return_score_status="AVAILABLE",
        risk_score=Decimal("70.000"), risk_score_status="AVAILABLE",
        risk_adjusted_score=Decimal("90.000"), risk_adjusted_score_status="AVAILABLE",
        stability_score=Decimal("88.000"), stability_score_status="AVAILABLE",
        relative_performance_score=None,
        relative_performance_score_status="UNAVAILABLE",
        data_completeness=Decimal("0.8000"),
        peer_group_snapshot_id=peer_group.id, peer_group_version=peer_group.version,
        scoring_policy_version="SP-v1", evaluation_policy_version="EP-v1",
        factor_run_id=run.id, data_version="DV-2026-08-31",
        code_version="0.1.0+g1234567", **_times(),
    )
    row.update(overrides)
    return FundScore(**row)


# ------------------------------------------------------- D-6：UNCLASSIFIED 不成组

def test_unclassified_cannot_form_a_peer_group(db_session):
    """D-6：空 基金类型 映射为 UNCLASSIFIED，如实落库，但【不得构成任何 Peer Group】。

    它不是一个类别，是「我们不知道它属于哪个类别」—— 与 Plan-1 在
    grouping_status 上反复吃过亏的那条区分是同一条。
    """
    db_session.add(PeerGroupSnapshot(
        classification_scheme="AKSHARE_FUND_TYPE", classification_level="L1",
        classification_code="UNCLASSIFIED", base_currency="CNY",
        effective_at=EFF, version=1, member_count=3,
        classification_policy_version="CP-v1", peer_group_policy_version="PGP-v1",
        code_version="0.1.0+g1234567",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_peer_group_business_key_is_unique(db_session, peer_group):
    db_session.add(PeerGroupSnapshot(
        classification_scheme=peer_group.classification_scheme,
        classification_level="L1", classification_code="混合型",
        base_currency="CNY", effective_at=EFF, version=1, member_count=9,
        classification_policy_version="CP-v2", peer_group_policy_version="PGP-v1",
        code_version="0.1.0+g1234567",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------- D-14：peer_group_member 不分区

def test_peer_group_member_is_not_partitioned(db_session):
    """D-14：上游给的 PK (peer_group_snapshot_id, share_class_id) 不含分区键
    effective_at，在 PostgreSQL 层面根本不成立（分区表的 PK 必须包含分区键）。
    裁定 M1 不分区，于是上游那条 PK 原样成立。
    """
    kind = db_session.execute(text(
        "SELECT relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'evaluation' AND c.relname = 'peer_group_member'"
    )).scalar_one()
    assert kind == "r"


def test_peer_group_member_pk_is_the_upstream_pair(db_session, peer_group,
                                                   share_class, classification):
    db_session.add(PeerGroupMember(
        peer_group_snapshot_id=peer_group.id, share_class_id=share_class.id,
        classification_history_id=classification.id,
    ))
    db_session.flush()
    db_session.add(PeerGroupMember(
        peer_group_snapshot_id=peer_group.id, share_class_id=share_class.id,
        classification_history_id=classification.id,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


# --------------------------------------------------------- G-4 / D-19：fund_score

def test_m1_normal_state_is_partial(db_session, share_class, peer_group, run):
    """D-19：M1 的常态是 PARTIAL —— Relative Performance Score 恒 UNAVAILABLE。

    这条测试锁住的是「PARTIAL 是正常的」这个事实本身。不锁住它，
    下游迟早会把 PARTIAL 当异常处理，从而把 M1 的每一次评分都报成故障。
    """
    db_session.add(_score(share_class, peer_group, run))
    db_session.flush()


def test_unavailable_sub_score_must_be_null(db_session, share_class, peer_group, run):
    """G-3 在子分层的形态：UNAVAILABLE 的子分不得带 0 分。

    「按 0 分参与评分」是上游明确列为【严禁】的两种缺失处理之一。
    """
    db_session.add(_score(
        share_class, peer_group, run,
        relative_performance_score=Decimal("0.000"),
        relative_performance_score_status="UNAVAILABLE",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_available_sub_score_must_have_a_value(db_session, share_class, peer_group, run):
    db_session.add(_score(
        share_class, peer_group, run,
        stability_score=None, stability_score_status="AVAILABLE",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_validation_pending_score_has_no_total(db_session, share_class, peer_group, run):
    """D-1 / FS:342：factor_effectiveness 未产出 → Score 不产出。

    VALIDATION_PENDING 却带着总分，等于「先按等权上线，等检验出来再调」——
    上游明确堵死的那条捷径。
    """
    db_session.add(_score(
        share_class, peer_group, run,
        score_status="VALIDATION_PENDING", total_score=Decimal("85.000"),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_data_completeness_is_mandatory(db_session, share_class, peer_group, run):
    """G-4：data_completeness 是【输出必备字段】，NOT NULL 落到数据库层。"""
    db_session.add(_score(share_class, peer_group, run, data_completeness=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_peer_group_version_is_mandatory(db_session, share_class, peer_group, run):
    """「缺 peer_group_version 则分数不可复现」（02-fund-scoring.md:536）。"""
    db_session.add(_score(share_class, peer_group, run, peer_group_version=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------------------------------ 归因（§10.3/§10.4）

def _attr(score, **overrides):
    row = dict(
        fund_score_id=score.id, sub_score="Risk-Adjusted", factor_id="F-RAP-001",
        window="1Y", factor_value_id=None,
        raw_value=Decimal("1.23456789"), normalized_score=Decimal("87.50000000"),
        direction="HIGHER_IS_BETTER", participation="INCLUDED",
        configured_weight=Decimal("0.30000000"),
        reallocated_weight=Decimal("0.10000000"),
        weight=Decimal("0.40000000"),
        weighted_contribution=Decimal("35.00000000"),
        exclusion_reason=None, provenance="PROVISIONAL",
    )
    row.update(overrides)
    return FundScoreAttribution(**row)


def test_included_weight_must_equal_configured_plus_reallocated(
    db_session, share_class, peer_group, run
):
    """§10.4：「否则用户无法解释『为什么 Sharpe 的贡献比配置的权重高』。」

    把「配置权重 / 接收到的重分配 / 实际生效权重」三者都存下来，并让
    数据库校验它们自洽 —— 只存一个实际权重，重分配这件事就消失了。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_attr(score, weight=Decimal("0.99000000")))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_excluded_factor_keeps_its_original_weight(
    db_session, share_class, peer_group, run
):
    """§10.4：被排除的因子必须记录为什么被排除，而非从归因中消失。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_attr(
        score, factor_id="F-RAP-002", participation="EXCLUDED",
        raw_value=None, normalized_score=None, weighted_contribution=None,
        configured_weight=Decimal("0.20000000"),
        reallocated_weight=Decimal("0"), weight=Decimal("0"),
        exclusion_reason="MAR_NOT_CONFIGURED",
    ))
    db_session.flush()


def test_excluded_factor_must_state_a_reason(db_session, share_class, peer_group, run):
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_attr(
        score, factor_id="F-RAP-002", participation="EXCLUDED",
        raw_value=None, normalized_score=None, weighted_contribution=None,
        configured_weight=Decimal("0.20000000"),
        reallocated_weight=Decimal("0"), weight=Decimal("0"),
        exclusion_reason=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_weight_must_not_be_negative(db_session, share_class, peer_group, run):
    """04-database-design:1061：weight >= 0 属数据库层 CHECK。

    Σ weight = 1 属【应用层】（:1068，跨行且形态随配置变化），不在这里。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_attr(score, configured_weight=Decimal("-0.10000000")))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------- G-7 / G-8：ranking 与 tier

def _ranking(score, peer_group, **overrides):
    row = dict(
        fund_score_id=score.id, peer_group_snapshot_id=peer_group.id,
        peer_group_version=peer_group.version, evaluation_profile="DEFAULT",
        ranking_metric="TOTAL_SCORE", effective_at=EFF, evaluation_period="1Y",
        rank=7, n_effective=42, peer_group_size=45,
        percentile=Decimal("85.3659"), ranking_status="NORMAL",
        confidence_flag=False, tie_method="COMPETITION_RANK",
        ranking_policy_version="RP-v1", scoring_policy_version="SP-v1",
    )
    row.update(overrides)
    return FundRanking(**row)


def test_insufficient_sample_still_lands_a_row(db_session, share_class, peer_group, run):
    """「INSUFFICIENT_SAMPLE 的行仍然落库，不是不写行」（:730）。

    不落库会让历史查询无法区分「当时样本不足」与「当时根本没算」。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_ranking(
        score, peer_group, rank=None, percentile=None,
        n_effective=17, ranking_status="INSUFFICIENT_SAMPLE", confidence_flag=True,
    ))
    db_session.flush()


def test_insufficient_sample_must_not_carry_a_rank(
    db_session, share_class, peer_group, run
):
    """上游逐字给出的联动 CHECK（04-database-design:722-728）。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_ranking(
        score, peer_group, rank=3, percentile=None,
        n_effective=17, ranking_status="INSUFFICIENT_SAMPLE",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_normal_ranking_requires_both_rank_and_percentile(
    db_session, share_class, peer_group, run
):
    """G-8：Rank / n_effective / Percentile 三者都必须落库。

    只存 Rank 则历史分位不可还原 —— 组规模会变，事后无法反推当时的分母。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_ranking(score, peer_group, percentile=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_n_effective_cannot_exceed_peer_group_size(
    db_session, share_class, peer_group, run
):
    """n_effective 是有效参与数，不是组规模 —— 但它不可能【多于】组规模。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add(_ranking(score, peer_group, n_effective=99, peer_group_size=45))
    with pytest.raises(IntegrityError):
        db_session.flush()


def _tier(ranking, **overrides):
    row = dict(
        fund_ranking_id=ranking.id, tier="A", classification_status="NORMAL",
        n_effective=42, percentile=Decimal("85.3659"), total_score=Decimal("85.000"),
        peer_sharpe_median=Decimal("0.62000000"),
        peer_max_drawdown_median=Decimal("0.18000000"),
        data_completeness=Decimal("0.8000"), confidence_flag=False,
        classification_policy_version="CLP-v1",
    )
    row.update(overrides)
    return FundTier(**row)


def test_tier_must_not_be_output_without_peer_medians(
    db_session, share_class, peer_group, run
):
    """G-9：Fund Tier 不得单独输出，必须与组内 Sharpe 中位数 + MDD 中位数同屏。

    「仅展示 Tier 视为违反本条」。落到数据库：有 Tier 就必须有两个中位数，
    否则这一行在被读出来的那一刻就已经违反了 G-9，而展示层没有任何办法补救。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    ranking = _ranking(score, peer_group)
    db_session.add(ranking)
    db_session.flush()
    db_session.add(_tier(ranking, peer_sharpe_median=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_insufficient_sample_produces_no_tier(db_session, share_class, peer_group, run):
    """§8.5 已定案：n_effective < 30 时 tier = null，
    classification_status = INSUFFICIENT_SAMPLE，且【不得默认为最低档】。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    ranking = _ranking(
        score, peer_group, rank=None, percentile=None,
        n_effective=17, ranking_status="INSUFFICIENT_SAMPLE", confidence_flag=True,
    )
    db_session.add(ranking)
    db_session.flush()
    db_session.add(_tier(
        ranking, tier=None, classification_status="INSUFFICIENT_SAMPLE",
        n_effective=17, percentile=None, confidence_flag=True,
        peer_sharpe_median=None, peer_max_drawdown_median=None,
    ))
    db_session.flush()


def test_insufficient_sample_must_not_carry_a_tier(
    db_session, share_class, peer_group, run
):
    """本 Plan【补齐】的 fund_tier 联动 CHECK（上游只给了 fund_ranking 的）。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    ranking = _ranking(score, peer_group)
    db_session.add(ranking)
    db_session.flush()
    db_session.add(_tier(
        ranking, tier="D", classification_status="INSUFFICIENT_SAMPLE",
        n_effective=17, percentile=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_tier_is_zero_or_one_per_ranking(db_session, share_class, peer_group, run):
    """03-erd §9.4：Ranking 与 Tier 是 Score 的派生，基数 0..1 不是 1:1。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    ranking = _ranking(score, peer_group)
    db_session.add(ranking)
    db_session.flush()
    db_session.add(_tier(ranking))
    db_session.flush()
    db_session.add(_tier(ranking, tier="B"))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------------------------- D-15 / D-17：Universe

@pytest.fixture()
def eligibility(db_session, share_class) -> InvestmentEligibility:
    row = InvestmentEligibility(
        share_class_id=share_class.id, effective_at=EFF, version=1,
        eligibility_status="FULLY_ELIGIBLE", **_times(),
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture()
def universe(db_session, peer_group, run) -> FundUniverseSnapshot:
    snap = FundUniverseSnapshot(
        decision_at=EFF, peer_group_snapshot_id=peer_group.id,
        peer_group_version=peer_group.version, universe_strategy="A",
        snapshot_status="COMPLETED", candidate_count=1200, selected_count=50,
        selection_policy_version="SEL-v1", eligibility_rules_version="ELG-v1",
        condition_version="COND-v1", scoring_policy_version=None,
        classification_policy_version=None, ranking_policy_version=None,
        evaluation_policy_version="EP-v1", factor_run_id=run.id,
        data_version="DV-2026-08-31", code_version="0.1.0+g1234567",
    )
    db_session.add(snap)
    db_session.flush()
    return snap


def test_strategy_a_allows_empty_scoring_columns(db_session, universe):
    """FR-UNIV-001 BR-3：策略 A 下评分字段为空是【正常情况】，不构成留痕缺失。

    universe 这个 fixture 本身就是断言 —— 它带着三个 NULL 的 policy 版本
    成功落库。若这些列被写成 NOT NULL，M1 的 Universe 根本建不起来。
    """
    assert universe.id is not None


def test_strategy_b_requires_a_scoring_policy_version(db_session, peer_group, run):
    db_session.add(FundUniverseSnapshot(
        decision_at=dt.date(2026, 8, 28), peer_group_snapshot_id=peer_group.id,
        peer_group_version=peer_group.version, universe_strategy="B",
        snapshot_status="COMPLETED", candidate_count=1200, selected_count=50,
        selection_policy_version="SEL-v1", eligibility_rules_version="ELG-v1",
        condition_version="COND-v1", scoring_policy_version=None,
        classification_policy_version=None, ranking_policy_version=None,
        evaluation_policy_version="EP-v1", factor_run_id=run.id,
        data_version="DV-2026-08-31", code_version="0.1.0+g1234567",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rejected_member_lands_with_a_version_reference(
    db_session, universe, share_class, eligibility
):
    """D-15：investment_eligibility 存【版本引用】，不存取值副本。

    引用 + Plan-1 的三时点 + version 已经构造性地保证了「按
    available_at <= decision_at 取当时那一版」。存副本则引入第二份真值，
    两者一旦分叉无法判定谁对 —— 这正是 adjusted_nav 标量列的教训。
    """
    db_session.add(FundUniverseMember(
        fund_universe_snapshot_id=universe.id, share_class_id=share_class.id,
        selection_status="REJECTED", fund_score_id=None, fund_ranking_id=None,
        fund_tier_id=None, data_completeness=None,
        eligibility_effective_at=eligibility.effective_at,
        eligibility_version=eligibility.version,
    ))
    db_session.flush()


def test_eligibility_reference_must_point_at_a_real_version(
    db_session, universe, share_class, eligibility
):
    """FK ON DELETE RESTRICT（D-15）+ 引用必须指向真实存在的那一版。"""
    db_session.add(FundUniverseMember(
        fund_universe_snapshot_id=universe.id, share_class_id=share_class.id,
        selection_status="SELECTED", fund_score_id=None, fund_ranking_id=None,
        fund_tier_id=None, data_completeness=None,
        eligibility_effective_at=eligibility.effective_at,
        eligibility_version=99,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_eligibility_row_cannot_be_deleted_while_referenced(
    db_session, universe, share_class, eligibility
):
    """D-15 补的那一条：快照的 FK 为 ON DELETE RESTRICT。"""
    db_session.add(FundUniverseMember(
        fund_universe_snapshot_id=universe.id, share_class_id=share_class.id,
        selection_status="SELECTED", fund_score_id=None, fund_ranking_id=None,
        fund_tier_id=None, data_completeness=None,
        eligibility_effective_at=eligibility.effective_at,
        eligibility_version=eligibility.version,
    ))
    db_session.flush()
    # DELETE 本身就会撞上 RESTRICT，异常在 execute 处抛出而不是 flush 处 ——
    # 因此 execute 必须写在 raises 块【里面】。
    with pytest.raises(IntegrityError):
        db_session.execute(text(
            "DELETE FROM fund.investment_eligibility WHERE share_class_id = :sc"
        ), {"sc": share_class.id})


def test_selected_count_cannot_exceed_candidate_count(db_session, peer_group, run):
    db_session.add(FundUniverseSnapshot(
        decision_at=dt.date(2026, 8, 27), peer_group_snapshot_id=peer_group.id,
        peer_group_version=peer_group.version, universe_strategy="A",
        snapshot_status="COMPLETED", candidate_count=10, selected_count=50,
        selection_policy_version="SEL-v1", eligibility_rules_version="ELG-v1",
        condition_version="COND-v1", scoring_policy_version=None,
        classification_policy_version=None, ranking_policy_version=None,
        evaluation_policy_version="EP-v1", factor_run_id=run.id,
        data_version="DV-2026-08-31", code_version="0.1.0+g1234567",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------- §14.2：不得只保存布尔值

@pytest.fixture()
def member(db_session, universe, share_class, eligibility) -> FundUniverseMember:
    m = FundUniverseMember(
        fund_universe_snapshot_id=universe.id, share_class_id=share_class.id,
        selection_status="REJECTED", fund_score_id=None, fund_ranking_id=None,
        fund_tier_id=None, data_completeness=None,
        eligibility_effective_at=eligibility.effective_at,
        eligibility_version=eligibility.version,
    )
    db_session.add(m)
    db_session.flush()
    return m


def _cond(member, **overrides):
    row = dict(
        fund_universe_member_id=member.id, condition_id="C-SHARPE-FLOOR",
        condition_version="COND-v1", condition_expression="sharpe >= 0.5",
        outcome="FAIL", actual_value=Decimal("0.31000000"), actual_text=None,
        threshold_value=Decimal("0.50000000"), gap=Decimal("0.19000000"),
    )
    row.update(overrides)
    return SelectionConditionResult(**row)


def test_a_judged_condition_must_carry_an_actual_value(db_session, member):
    """§14.2：❌ selected = true / false —— 只保存布尔值不被接受。

    「实际值」是回答「放宽某条件能新增多少基金」的唯一依据。
    """
    db_session.add(_cond(member, actual_value=None, actual_text=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_passing_condition_has_no_gap(db_session, member):
    db_session.add(_cond(
        member, outcome="PASS", actual_value=Decimal("0.72000000"),
        gap=Decimal("0.22000000"),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_not_evaluable_condition_carries_no_value(db_session, member):
    """输入本身 UNAVAILABLE 的条件既不是 PASS 也不是 FAIL。

    把它记成 FAIL 会把「没法判」伪装成「判了，没过」—— G-3 在条件层的同一个错误。
    """
    db_session.add(_cond(
        member, condition_id="C-SORTINO-FLOOR", outcome="NOT_EVALUABLE",
        actual_value=None, actual_text=None, threshold_value=None, gap=None,
    ))
    db_session.flush()


def test_same_condition_recorded_once_per_member(db_session, member):
    db_session.add(_cond(member))
    db_session.flush()
    db_session.add(_cond(member, outcome="PASS", gap=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------- D-18 / §4.3：不设 updated_at

@pytest.mark.parametrize("table", [
    "peer_group_snapshot", "peer_group_member", "fund_score",
    "fund_score_attribution", "fund_ranking", "fund_tier",
    "fund_universe_snapshot", "fund_universe_member", "selection_condition_result",
])
def test_no_snapshot_table_has_updated_at(db_session, table):
    """「快照一旦产生即不可变 —— 无需 updated_at 的业务语义」（03-erd:930）。

    「禁止 UPDATE 的表不设 updated_at ⚠️ …这是一个有意的设计信号」（:105-113）。
    这条参数化测试是那个信号的守卫：谁将来给某张表加了 updated_at，
    就必须先来把它删掉，从而正面看到自己在改变什么。
    """
    cols = db_session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'evaluation' AND table_name = :t"
    ), {"t": table}).scalars().all()
    assert cols, f"evaluation.{table} 不存在"
    assert "updated_at" not in cols


@pytest.mark.parametrize("table", [
    "peer_group_snapshot", "peer_group_member", "fund_score",
    "fund_score_attribution", "fund_ranking", "fund_tier",
    "fund_universe_snapshot", "fund_universe_member", "selection_condition_result",
])
def test_every_foreign_key_is_restrict(db_session, table):
    """D-18：FK 一律 ON DELETE RESTRICT。

    PostgreSQL 把 RESTRICT 存成 confdeltype='r'，把【未声明】存成 'a'
    （NO ACTION）。两者行为在非延迟约束下几乎一致，所以漏写 ON DELETE
    不会被任何功能测试发现 —— 只有直接读 pg_constraint 才看得出来。
    """
    rows = db_session.execute(text(
        "SELECT c.conname, c.confdeltype FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "WHERE c.contype = 'f' AND n.nspname = 'evaluation' AND t.relname = :t"
    ), {"t": table}).all()
    assert rows, f"evaluation.{table} 没有任何外键"
    assert all(d == "r" for _, d in rows), [r for r in rows if r[1] != "r"]


def test_factor_value_peer_group_fk_exists(db_session):
    """Task 7 留下的那条 FK 在本任务补上（目标表此刻才存在）。"""
    n = db_session.execute(text(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conname = 'fk_factor_value_peer_group_snapshot'"
    )).scalar_one()
    assert n == 1
```

- [ ] **Step 3: 运行确认失败（G-18）**

```bash
.venv/bin/pytest tests/integration/test_evaluation_schema.py -v
```

Expected: 全部 collection error ——
`ModuleNotFoundError: No module named 'fip.services.fund_service.models'`。
Step 6 之后会转为第二形态（`relation "evaluation.peer_group_snapshot" does not exist`）。
两次失败输出都贴进任务报告。

- [ ] **Step 4: 写 ORM 模型 `src/fip/services/fund_service/models/evaluation.py`（前四张表）**

```python
# src/fip/services/fund_service/models/evaluation.py
import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.enums import (
    attribution_participation_enum,
    condition_outcome_enum,
    cross_section_status_enum,
    fund_tier_enum,
    preference_direction_enum,
    provenance_enum,
    score_status_enum,
    selection_status_enum,
    sub_score_name_enum,
    sub_score_status_enum,
    universe_status_enum,
)
from fip.platform.db.mixins import VersionedMixin, temporal_check_constraints
from fip.platform.db.types import NavNumeric, RatioNumeric

# --------------------------------------------------------------------------
# CHECK 的 SQL 字面量。迁移 0017 里【逐字复制】同样的字符串（不 import，
# 理由见 0011 / 0013 的「已冻结的字面量」注释）。
# --------------------------------------------------------------------------

# Analysis Period 六值（BR:701-711 §9.1，「不新增」）。
PERIOD_DOMAIN_SQL = "{col} IN ('1M', '3M', '6M', '1Y', '3Y', '5Y')"

# D-6：UNCLASSIFIED 如实落库（在 fund.fund_classification_history 里），
# 但【不得构成任何 Peer Group】。这条 CHECK 是那句话的数据库形态。
NOT_UNCLASSIFIED_SQL = "classification_code <> 'UNCLASSIFIED'"

# D-7：Peer Group 粒度默认 L1（PROVISIONAL），取值 L1 / L2，不得硬编码在代码里，
# 但域必须锁住 —— 写进第三个值就是配置错误。
CLASSIFICATION_LEVEL_SQL = "classification_level IN ('L1', 'L2')"


def sub_score_pairing_sql(value_col: str, status_col: str) -> str:
    """子分的值与状态必须成对。

    G-3 在子分层的形态：UNAVAILABLE 的子分【不得】带 0 分。
    「按 0 分参与评分」与「用同类均值填充」是上游明确列为严禁的两种做法，
    而它们在数据里长得跟正常分数一模一样 —— 只有把 status 与 value 的
    联动写进数据库，这两种做法才会在写入的那一刻就失败。
    """
    return (
        f"({status_col} = 'AVAILABLE' AND {value_col} IS NOT NULL) OR "
        f"({status_col} <> 'AVAILABLE' AND {value_col} IS NULL)"
    )


# 总分与 score_status 的联动（D-19 的五值）。
SCORE_TOTAL_SQL = (
    "(score_status IN ('COMPLETED', 'PARTIAL') AND total_score IS NOT NULL) OR "
    "(score_status IN ('UNAVAILABLE', 'VALIDATION_PENDING', 'INSUFFICIENT_FACTORS') "
    " AND total_score IS NULL)"
)

# score_scale = 0–100（02-fund-scoring.md:490）。
# ⚠️ 与 Tier 阈值不同，这是一个【量纲】而不是一个【决策阈值】：
# C-1「阈值配置化，严禁硬编码」针对的是分位区间（95/80/50/20），
# 那些【刻意不进 CHECK】，见 FundTier 的注释。0–100 的标尺若真要改，
# 属 Major 级变更（口径不可比），走新迁移是合适的。
SCORE_SCALE_SQL = "{col} IS NULL OR ({col} >= 0 AND {col} <= 100)"
COMPLETENESS_SQL = "data_completeness >= 0 AND data_completeness <= 1"

# 归因：INCLUDED 与 EXCLUDED 两条完全不同的形状（§10.3 / §10.4）。
ATTRIBUTION_SHAPE_SQL = (
    "(participation = 'INCLUDED' "
    " AND normalized_score IS NOT NULL AND weighted_contribution IS NOT NULL "
    " AND exclusion_reason IS NULL "
    " AND weight = configured_weight + reallocated_weight) OR "
    "(participation = 'EXCLUDED' "
    " AND normalized_score IS NULL AND weighted_contribution IS NULL "
    " AND exclusion_reason IS NOT NULL "
    " AND weight = 0 AND reallocated_weight = 0)"
)

# 上游【逐字】给出的联动 CHECK（04-database-design:722-728）。
RANKING_STATUS_SQL = (
    "(ranking_status = 'NORMAL' AND rank IS NOT NULL AND percentile IS NOT NULL) OR "
    "(ranking_status = 'INSUFFICIENT_SAMPLE' AND rank IS NULL AND percentile IS NULL)"
)
# 【补齐】—— 上游只给了 fund_ranking 的版本，fund_tier 的没给
# （BLOCK-9 / 04-database-design:「§10.1.2」）。按同一形态推导，
# 并加上 §8.5 已定案的「n_effective < 30 时 tier = null」。
TIER_STATUS_SQL = (
    "(classification_status = 'NORMAL' "
    " AND tier IS NOT NULL AND percentile IS NOT NULL) OR "
    "(classification_status = 'INSUFFICIENT_SAMPLE' "
    " AND tier IS NULL AND percentile IS NULL)"
)
# G-9 的数据库防线：有 Tier 就必须有组内绝对水平两项。
TIER_PEER_LEVEL_SQL = (
    "tier IS NULL OR "
    "(peer_sharpe_median IS NOT NULL AND peer_max_drawdown_median IS NOT NULL)"
)

# 策略 B/C 必须有 Scoring Policy Version；策略 A 可空（FR-UNIV-001 BR-3）。
UNIVERSE_STRATEGY_SQL = "universe_strategy IN ('A', 'B', 'C')"
UNIVERSE_SCORING_SQL = (
    "universe_strategy = 'A' OR scoring_policy_version IS NOT NULL"
)

# §14.2：不得只保存布尔值 —— 判过的条件必须带实际值；
# NOT_EVALUABLE 则必须什么都不带（否则「没法判」会被伪装成「判了」）。
CONDITION_SHAPE_SQL = (
    "(outcome = 'NOT_EVALUABLE' "
    " AND actual_value IS NULL AND actual_text IS NULL AND gap IS NULL) OR "
    "(outcome = 'PASS' "
    " AND (actual_value IS NOT NULL OR actual_text IS NOT NULL) "
    " AND gap IS NULL) OR "
    "(outcome = 'FAIL' "
    " AND (actual_value IS NOT NULL OR actual_text IS NOT NULL))"
)


class PeerGroupSnapshot(Base):
    """【快照表】。Business Key = (classification_key, effective_at, version)。

    ── classification_key 不单独存一列 ──
    上游给了这个名字但「类型与构成 文档未给值」。它就是跨任务接口契约里的
    PeerGroupKey =(classification_scheme, classification_code, base_currency)。
    把三列再拼成一个字符串列存一遍，就是又一份可以与三列分叉的真值
    （Plan-1 在 adjusted_nav 标量列上花了三轮才想明白的那件事）。
    因此唯一约束直接建在三列 + effective_at + version 上，
    classification_key 作为【名字】留在文档里，不作为【列】留在库里。

    ── 没有 evaluation_profile 列 ──
    Peer Group 的划分维度是 Fund Classification × Currency（FR:105），
    Profile 是排名层的概念（G-10「同一 Peer Group 内多个 Profile 时
    按 Profile 拆分子排名」—— 拆的是排名，不是组）。把 Profile 放进本表
    会让 B1 的构建依赖评价配置，正面撞上 G-5「Peer Group 构建不得 import
    评分 / Universe 模块」。Profile 落在 fund_score / fund_ranking 上。

    ── effective_at 就是构建该组时的 decision_at ──
    03-erd:925 给的时间字段是 effective_at + version；跨任务接口契约里
    FactorInput.effective_at 明写「= decision_at」。再加一列 decision_at
    同样是第二份真值。PIT 可见性由构建时的 available_at <= decision_at
    保证（G-1），成员表里 classification_history_id 记的正是当时选中的那一版。

    D-18：快照表不设 updated_at。
    """

    __tablename__ = "peer_group_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "classification_scheme", "classification_code", "base_currency",
            "effective_at", "version", name="uq_peer_group_snapshot_business",
        ),
        CheckConstraint(NOT_UNCLASSIFIED_SQL, name="ck_peer_group_not_unclassified"),
        CheckConstraint(CLASSIFICATION_LEVEL_SQL, name="ck_peer_group_level"),
        CheckConstraint("member_count >= 0", name="ck_peer_group_member_count"),
        CheckConstraint("version >= 1", name="ck_peer_group_version"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    classification_scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    # D-7【补齐, PROVISIONAL】：默认 L1。取值来自配置项
    # peer_group.classification_level，【不得硬编码】—— 本列存的是
    # 「这个快照当时用的是哪一层」，是结果不是参数。
    classification_level: Mapped[str] = mapped_column(String(2), nullable=False)
    classification_code: Mapped[str] = mapped_column(String(32), nullable=False)
    # 与 R_f 解析用的是【同一字段】（跨任务接口契约 PeerGroupKey）。
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # FR-PEER-001 Output 与 B1 边界都点名「所用分类版本」。
    classification_policy_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    # G-7：min_sample_size 属 governance.policy_version 的 Peer Group Policy，
    # 三处（标准化 / 排名 / 分层）共用同一配置源。这里存的是「用了哪一版」。
    peer_group_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PeerGroupMember(Base):
    """【明细表 · 不分区】（D-14）。

    上游给的 PK (peer_group_snapshot_id, share_class_id) 不含分区键
    effective_at，而 PostgreSQL 要求分区表的 PK/UNIQUE 必须包含分区键 ——
    两条互不相容，文档未裁决（BLOCK-7）。D-14 裁定 M1 不分区，于是上游
    那条 PK【原样成立】，不必为了对齐一个本身不成立的设计而改主键。

    classification_history_id 是 D-15 同一原则在本表的应用：存指向
    fund.fund_classification_history 的【引用】，而不是把当时的
    classification_code 抄一份进来。「回测必须使用当时的分类」
    （BR:378-383）—— 引用 + 区间型表的 available_at 已经构造性地保证了这点，
    抄一份则会在分类被修订时静默分叉。
    """

    __tablename__ = "peer_group_member"
    __table_args__ = (
        # 「快照相关表只建必要的 PK 与 FK 索引」（:1039）。PK 的前缀列
        # 已经覆盖 peer_group_snapshot_id 的 FK 查找，故只补另外两条 FK 索引。
        Index("ix_peer_group_member_share_class", "share_class_id"),
        Index("ix_peer_group_member_classification", "classification_history_id"),
        {"schema": "evaluation"},
    )

    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    classification_history_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_classification_history.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundScore(Base, VersionedMixin):
    """【版本化事实表】—— 总分 + 五子分（七列标准 + 两组 CHECK）。

    ── BLOCK-8 的落法 ──
    ERD 让 fund_score 依赖 fund_evaluation（03-erd:487），但后者属 M2+，
    M1 不落。于是「evaluation_status / data_completeness 落在哪张表」文档
    未给值。D-19 已经把 score_status 的五值定在 Score 上，本表据此承载
    score_status + data_completeness，不建 fund_evaluation_id 列 ——
    建一个永远为 NULL 的外键列比不建更糟：它会让「M1 到底有没有
    fund_evaluation」这件事在数据里看起来是可选的。

    ── 代理主键 + 业务唯一键 ──
    fund_score_attribution / fund_ranking 都要以单列 FK 指向它；用五列
    复合 PK 会让每个明细表复制五列外键。业务身份由 uq_fund_score_business
    保证，与 factor_value 同一形状。

    ── 不分区 ──
    上游按 as_of_date 年分区，依据是 3,000 万行。M1 是
    300 份额类别 × 1 Profile × 6 Period × ~250 天 ≈ 45 万行。同 D-14 的
    理由：不为一个尚未到来的量级引入 Plan-1 已证实的分区成本。分区键
    effective_at 已在业务唯一键中，将来要分区不存在结构性障碍。

    D-18 / §4.3：禁止 UPDATE，不设 updated_at。
    """

    __tablename__ = "fund_score"
    __table_args__ = (
        *temporal_check_constraints("fund_score"),
        UniqueConstraint(
            "share_class_id", "evaluation_profile", "evaluation_period",
            "effective_at", "version", name="uq_fund_score_business",
        ),
        CheckConstraint(
            PERIOD_DOMAIN_SQL.format(col="evaluation_period"),
            name="ck_fund_score_period",
        ),
        CheckConstraint(SCORE_TOTAL_SQL, name="ck_fund_score_total"),
        CheckConstraint(
            SCORE_SCALE_SQL.format(col="total_score"), name="ck_fund_score_scale_total"
        ),
        CheckConstraint(
            sub_score_pairing_sql("return_score", "return_score_status"),
            name="ck_fund_score_return",
        ),
        CheckConstraint(
            sub_score_pairing_sql("risk_score", "risk_score_status"),
            name="ck_fund_score_risk",
        ),
        CheckConstraint(
            sub_score_pairing_sql(
                "risk_adjusted_score", "risk_adjusted_score_status"
            ),
            name="ck_fund_score_risk_adjusted",
        ),
        CheckConstraint(
            sub_score_pairing_sql("stability_score", "stability_score_status"),
            name="ck_fund_score_stability",
        ),
        CheckConstraint(
            sub_score_pairing_sql(
                "relative_performance_score", "relative_performance_score_status"
            ),
            name="ck_fund_score_relative",
        ),
        CheckConstraint(COMPLETENESS_SQL, name="ck_fund_score_completeness"),
        Index(
            "ix_fund_score_pit",
            "share_class_id", "evaluation_profile", "evaluation_period",
            "effective_at", "available_at", text("version DESC"),
        ),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    # M1 只有一个 Profile，但列必须在 —— G-10 在 M1 是【空洞成立】的，
    # 缺了这列，M2 加第二个 Profile 时两套分数会静默叠在同一个业务键上。
    evaluation_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_period: Mapped[str] = mapped_column(String(4), nullable=False)
    total_score: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    score_status: Mapped[str] = mapped_column(score_status_enum, nullable=False)
    # 五个子分。命名固定不得更改（02-fund-scoring.md:93）；列名是那五个
    # 名字的 snake_case，枚举 sub_score_name_enum 保留原字面。
    return_score: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    return_score_status: Mapped[str] = mapped_column(
        sub_score_status_enum, nullable=False
    )
    risk_score: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    risk_score_status: Mapped[str] = mapped_column(
        sub_score_status_enum, nullable=False
    )
    risk_adjusted_score: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    risk_adjusted_score_status: Mapped[str] = mapped_column(
        sub_score_status_enum, nullable=False
    )
    stability_score: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    stability_score_status: Mapped[str] = mapped_column(
        sub_score_status_enum, nullable=False
    )
    # M1 恒 UNAVAILABLE（无 Benchmark）。「这不是缺陷，而是正好在 M1 就把
    # UNAVAILABLE 与 Data Completeness 机制跑通 —— 基于 4 个子分的 85 分与
    # 基于 5 个子分的 85 分必须可区分」（spec §6.2）。
    relative_performance_score: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    relative_performance_score_status: Mapped[str] = mapped_column(
        sub_score_status_enum, nullable=False
    )
    # G-4：输出必备字段，NOT NULL。
    data_completeness: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 「缺 peer_group_version 则分数不可复现」（02-fund-scoring.md:536）。
    peer_group_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # 因子口径（Metric Version）与批次经 factor_run 一次带全，不再单列
    # factor_version —— 一次 Score 用的是一整批因子，逐个列出无处安放。
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)


class FundScoreAttribution(Base):
    """【明细表】—— 归因必须能回答「为什么是这个分数」。

    03-erd §9.3：必须是独立实体，【不得】用 JSONB 整体存储 ——
    「归因分析需要按 factor_id 聚合」，进 WHERE / GROUP BY 的字段必须结构化。

    ── 为什么这里【允许】存 raw_value 的副本 ──
    D-15 的「引用而非副本」是对的，但它的理由是「两份真值可能分叉」。
    factor_value 是【禁止 UPDATE】的版本化表，(id) 一经写入其
    raw_value / normalized_value 永不改变，副本在结构上无法分叉 ——
    这与 adjusted_nav 的情形正好相反（后者是 (行, decision_at) 的二元函数，
    标量列根本装不下）。而上游把 raw_value 列为【必须保留的六项】之一，
    并给了理由：「只有标准化值时用户看不懂『0.83 分』从何而来」（:456）。
    因此这里同时存 factor_value_id（溯源，可空）与两个副本，并在 Task 14
    加一条测试断言副本与被引用行一致。

    ── 权重的三列而不是一列 ──
    §10.4 要求记录「排除原因 / 原权重 / 重分配去向」。重分配【去向】是
    一对多（Sortino 被排除 → Sharpe +X%、Calmar +X%），写成一列指针装不下，
    写成 JSONB 又违反 §9.3。改成在【接收方】的行上记 reallocated_weight：
    weight = configured_weight + reallocated_weight 这条恒等式由 CHECK 保证，
    「为什么 Sharpe 的贡献比配置的权重高」直接读得出来。
    """

    __tablename__ = "fund_score_attribution"
    __table_args__ = (
        UniqueConstraint(
            "fund_score_id", "factor_id", "window",
            name="uq_fund_score_attribution_factor",
        ),
        CheckConstraint(ATTRIBUTION_SHAPE_SQL, name="ck_fund_score_attribution_shape"),
        # 04-database-design:1061：weight >= 0 属数据库层 CHECK。
        # Σ weight = 1 属【应用层】（:1068，跨行）—— 不在这里。
        CheckConstraint(
            "configured_weight >= 0 AND reallocated_weight >= 0 AND weight >= 0",
            name="ck_fund_score_attribution_weight",
        ),
        CheckConstraint(
            PERIOD_DOMAIN_SQL.format(col='"window"'),
            name="ck_fund_score_attribution_window",
        ),
        # 「快照相关表只建必要的 PK 与 FK 索引」的【唯一例外】，理由是
        # 03-erd §9.3 把「可按因子聚合分析」写成了本表存在的判据本身：
        # 没有这条索引，「哪个因子贡献最大」要全表扫。
        Index("ix_fund_score_attribution_factor", "factor_id"),
        Index("ix_fund_score_attribution_value", "factor_value_id"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_score_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_score.id", ondelete="RESTRICT"), nullable=False
    )
    sub_score: Mapped[str] = mapped_column(sub_score_name_enum, nullable=False)
    factor_id: Mapped[str] = mapped_column(
        ForeignKey("factor.factor_definition.factor_id", ondelete="RESTRICT"),
        nullable=False,
    )
    window: Mapped[str] = mapped_column(String(4), nullable=False)
    # 可空：UNAVAILABLE 的因子可能连 factor_value 行都没有
    # （如 REL 全类 —— 无 Benchmark 时根本不发起计算）。
    factor_value_id: Mapped[int | None] = mapped_column(
        ForeignKey("factor.factor_value.id", ondelete="RESTRICT"), nullable=True
    )
    raw_value: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    normalized_score: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    # 「该因子在本 Profile 下的方向」（§10.3）。存下来是因为 M2 的
    # STRATEGY_DEPENDENT 会让它随 Profile 变 —— 那时回看历史归因，
    # 必须知道当时用的是哪个方向，否则分位的正负号无从解释。
    direction: Mapped[str] = mapped_column(preference_direction_enum, nullable=False)
    participation: Mapped[str] = mapped_column(
        attribution_participation_enum, nullable=False
    )
    configured_weight: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    reallocated_weight: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    weight: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    weighted_contribution: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    exclusion_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # G-14：权重方案整体属【补齐】（上游明说「具体权重数值文档未给值」）。
    provenance: Mapped[str] = mapped_column(provenance_enum, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: 续写 `evaluation.py`（后五张表）**

```python
# src/fip/services/fund_service/models/evaluation.py —— 接上文


class FundRanking(Base):
    """【派生表 · 基数 0..1】。

    「Score 存在但 Peer Group 仅 1 只基金 → 无 Ranking」（03-erd §9.4），
    因此本表不是 fund_score 的必然伴随物，唯一键建在
    (fund_score_id, ranking_metric) 上而非把 fund_score_id 设成 PK。

    ── BLOCK-5：本表是不是版本化事实表 —— 文档未明确 ──
    它既不在 03-erd:905 的事实型清单里（那里只有 "Score"），也不在 :906 的
    状态型清单里。本稿裁定【不是】：Ranking 是 Score 的纯函数派生，
    Score 已经带了三时点 + version，Ranking 再带一套 available_at 会产生
    「分数在 T 可见但它的排名在 T 不可见」这种无法解释的状态。
    可见性沿用被引用的 fund_score 那一行。记为 PROVISIONAL。

    G-8：Rank / n_effective / Percentile 三者都必须落库 ——
    只存 Rank 则历史分位不可还原（组规模会变，事后反推不出当时的分母）。
    """

    __tablename__ = "fund_ranking"
    __table_args__ = (
        UniqueConstraint(
            "fund_score_id", "ranking_metric", name="uq_fund_ranking_scope"
        ),
        # 上游【逐字】给出的联动 CHECK（04-database-design:722-728）。
        CheckConstraint(RANKING_STATUS_SQL, name="ck_fund_ranking_status"),
        CheckConstraint(
            "n_effective >= 0 AND peer_group_size >= 0 "
            "AND n_effective <= peer_group_size",
            name="ck_fund_ranking_counts",
        ),
        CheckConstraint("rank IS NULL OR rank >= 1", name="ck_fund_ranking_rank"),
        CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="ck_fund_ranking_percentile",
        ),
        CheckConstraint(
            PERIOD_DOMAIN_SQL.format(col="evaluation_period"),
            name="ck_fund_ranking_period",
        ),
        Index("ix_fund_ranking_peer_group", "peer_group_snapshot_id"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_score_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_score.id", ondelete="RESTRICT"), nullable=False
    )
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    peer_group_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # G-10：同一 Peer Group 内多个 Profile 时按 Profile 拆分子排名，
    # 不产出跨 Profile 统一排名。列在这里，唯一键经 fund_score_id 传导。
    evaluation_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    # 「按什么排的」—— Total Score 是默认，也支持单项子分 / 单个 Factor。
    ranking_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    evaluation_period: Mapped[str] = mapped_column(String(4), nullable=False)
    # 「rank」在 PostgreSQL 里是非保留关键字（可作列名），无需改名。
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # G-7：判定基数是 n_effective（该指标的有效参与数）【不是】组规模。
    # 「n_effective 在两种状态下都必填 —— 它是判定依据，也是事后分析
    # 『哪些分类长期低于 30』的唯一数据来源」（:732）。
    n_effective: Mapped[int] = mapped_column(Integer, nullable=False)
    peer_group_size: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    ranking_status: Mapped[str] = mapped_column(
        cross_section_status_enum, nullable=False
    )
    confidence_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # D-20：Tie Method = COMPETITION_RANK（§8.2 定案；D-9 的「TBD」是
    # 决策登记表未同步的编辑遗漏）。存下来是因为换了 tie method 会让
    # 同一批分数产出不同的 rank 与分位分母。
    tie_method: Mapped[str] = mapped_column(String(24), nullable=False)
    ranking_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundTier(Base):
    """【派生表 · 基数 0..1】。五档 A+ / A / B / C / D。

    ── BLOCK-9 的裁定：组内绝对水平落【本表】，不落 peer_group_snapshot ──
    上游未裁决。落本表的理由不是方便，是 G-5：peer_group_snapshot 由 B1
    写入，而 B1「不得 import 评分 / Universe 模块」。组内 Sharpe 中位数与
    MDD 中位数是【因子派生量】—— 把它们放进 peer_group_snapshot，B1 就必须
    先算因子才能写快照，直接撞上 G-5，还会让 Peer Group 的构建依赖 Score
    链路（FR-PEER-001 BR-1 明令禁止）。

    ── fund_tier 的联动 CHECK 是【补齐】 ──
    04-database-design 只给了 fund_ranking 的版本，本表的没给（:734 一节
    的 SQL 块里只有 fund_ranking）。TIER_STATUS_SQL 按同一形态推导，
    并合并 §8.5 已定案的「n_effective < 30 → tier = null」。

    ── 分位阈值（95 / 80 / 50 / 20）刻意【不】进 CHECK ──
    很想加一条「tier='A+' → percentile >= 95」，它确实能挡住
    04-fund-classification.md:214 说的那处「极易出错的换算」。但 C-1
    明令「阈值配置化，严禁硬编码」，而 CHECK 里的字面量就是硬编码 ——
    业务方改一次分位区间就要发一支迁移，且历史行会被新阈值判为违规
    （C-8：Policy 变更不覆盖历史 Tier）。边界校验三项（完备性 / 互斥性 /
    单调性）由 Task 15 的单元测试对着配置断言，那里改阈值不用改代码。
    """

    __tablename__ = "fund_tier"
    __table_args__ = (
        UniqueConstraint("fund_ranking_id", name="uq_fund_tier_ranking"),
        CheckConstraint(TIER_STATUS_SQL, name="ck_fund_tier_status"),
        CheckConstraint(TIER_PEER_LEVEL_SQL, name="ck_fund_tier_peer_level"),
        CheckConstraint("n_effective >= 0", name="ck_fund_tier_n_effective"),
        CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="ck_fund_tier_percentile",
        ),
        CheckConstraint(
            SCORE_SCALE_SQL.format(col="total_score"), name="ck_fund_tier_score_scale"
        ),
        CheckConstraint(COMPLETENESS_SQL, name="ck_fund_tier_completeness"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_ranking_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_ranking.id", ondelete="RESTRICT"), nullable=False
    )
    # 可空：percentile = UNAVAILABLE（N=1）或 n_effective < 30 时【无 Tier】，
    # 且「不得默认为最低档」（D-8 / :368）。
    tier: Mapped[str | None] = mapped_column(fund_tier_enum, nullable=True)
    classification_status: Mapped[str] = mapped_column(
        cross_section_status_enum, nullable=False
    )
    n_effective: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(RatioNumeric, nullable=True)
    # G-9：Fund Tier 不得单独输出，必须与组内 Sharpe 中位数 + MDD 中位数同屏，
    # 「仅展示 Tier 视为违反本条」。两列 + TIER_PEER_LEVEL_SQL 是它的落法。
    peer_sharpe_median: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    peer_max_drawdown_median: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    data_completeness: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    confidence_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # C-4：分层必须记录当时的阈值配置版本。
    classification_policy_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundUniverseSnapshot(Base):
    """【快照表】—— 一次 Universe 生成。时间字段是 decision_at（03-erd:926）。

    D-18：B2 引用【已提交的】B1 快照 ID。两者各自原子，不要求同一事务 ——
    peer_group_snapshot_id 是 NOT NULL 的 FK，写 B2 时 B1 必须已经在库里，
    这条 FK 本身就是「B2 引用已提交的 B1」这句话的强制形态。

    「快照缺失时必须显式拒绝」（FR-UNIV-002）：不提供推算结果。这在存储侧
    的对应就是本表不设任何默认值、不允许 upsert —— 没有行就是没有行。

    策略 A 下评分字段为空【必须不报错】（FR-UNIV-001 BR-3），
    因此 scoring / classification / ranking 三个 policy 版本列可空。
    """

    __tablename__ = "fund_universe_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "decision_at", "selection_policy_version",
            name="uq_fund_universe_snapshot_business",
        ),
        CheckConstraint(UNIVERSE_STRATEGY_SQL, name="ck_fund_universe_strategy"),
        CheckConstraint(UNIVERSE_SCORING_SQL, name="ck_fund_universe_scoring_version"),
        CheckConstraint(
            "candidate_count >= 0 AND selected_count >= 0 "
            "AND selected_count <= candidate_count",
            name="ck_fund_universe_counts",
        ),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    peer_group_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # BLOCK-3：M1 做哪种构成策略上游没点名（spec 一处都没写「策略 A」三个字）。
    # 落成列而不是写死成 A：spec 说「三种构成策略」推到 M2+ 指的是【实现】，
    # 不是「快照不必记录用了哪种」。M1 只写 'A'，但列在，
    # 于是 M2 加 B/C 时历史快照仍然可解释。
    universe_strategy: Mapped[str] = mapped_column(String(1), nullable=False)
    snapshot_status: Mapped[str] = mapped_column(universe_status_enum, nullable=False)
    # D-17：候选集全部落库（约 1,200 行/次），不是最终 50 只。
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # 可复现性八要素（§16.1）。缺一则同一 decision_at 无法还原同一 Universe。
    selection_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    eligibility_rules_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scoring_policy_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    classification_policy_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    ranking_policy_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    evaluation_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundUniverseMember(Base):
    """【明细表 · 含 REJECTED】（D-17 / G-11）。

    「若只存入池成员 → 无法验证是否有基金被错误排除 → 而错误排除正是
    幸存者偏差的表现形式 → 且无法回答『放宽某条件能新增多少基金』」
    （03-erd §9.2）。数据量约 1,200 行/次，「但这是必需的」。

    ── D-15：investment_eligibility 存【版本引用】，不存取值副本 ──
    引用的形态是复合 FK (share_class_id, eligibility_effective_at,
    eligibility_version) → fund.investment_eligibility 的复合 PK
    (share_class_id, effective_at, version)。复用 share_class_id 这一列
    有额外好处：数据库会顺带保证「引用的那一版可投资性确实属于这只份额
    类别」—— 用一个代理键列做不到这一点。ON DELETE RESTRICT
    （fund.investment_eligibility 的行永不删除、永不原地修改）。

    ── 为什么不存「约束标注」 ──
    §13 写的是「investment_eligibility | 该时点可投资性状态与约束标注」。
    约束标注（可建仓 / 可加仓 / 可持有 / 可减仓）是 eligibility_status 的
    纯函数（§9.1 三处完全一致的那张表），存下来就是第三份真值。
    它由 strategy_library 从被引用的那一版派生。

    ── 评分字段可空 ──
    「策略 B/C 时必填、策略 A 时为空」（§13）。M1 是策略 A，
    fund_score_id / fund_ranking_id / fund_tier_id / data_completeness 全为 NULL
    是正常状态，不是留痕缺失（:147）。
    """

    __tablename__ = "fund_universe_member"
    __table_args__ = (
        UniqueConstraint(
            "fund_universe_snapshot_id", "share_class_id",
            name="uq_fund_universe_member",
        ),
        ForeignKeyConstraint(
            ["share_class_id", "eligibility_effective_at", "eligibility_version"],
            ["fund.investment_eligibility.share_class_id",
             "fund.investment_eligibility.effective_at",
             "fund.investment_eligibility.version"],
            ondelete="RESTRICT",
            name="fk_fund_universe_member_eligibility",
        ),
        CheckConstraint(
            "data_completeness IS NULL OR "
            "(data_completeness >= 0 AND data_completeness <= 1)",
            name="ck_fund_universe_member_completeness",
        ),
        Index("ix_fund_universe_member_share_class", "share_class_id"),
        Index("ix_fund_universe_member_score", "fund_score_id"),
        Index("ix_fund_universe_member_ranking", "fund_ranking_id"),
        Index("ix_fund_universe_member_tier", "fund_tier_id"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_universe_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_universe_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    selection_status: Mapped[str] = mapped_column(
        selection_status_enum, nullable=False
    )
    fund_score_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation.fund_score.id", ondelete="RESTRICT"), nullable=True
    )
    fund_ranking_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation.fund_ranking.id", ondelete="RESTRICT"), nullable=True
    )
    fund_tier_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation.fund_tier.id", ondelete="RESTRICT"), nullable=True
    )
    data_completeness: Mapped[Decimal | None] = mapped_column(
        RatioNumeric, nullable=True
    )
    # D-15 的版本引用两列（复合 FK 的另外两列，share_class_id 复用上面那一列）。
    eligibility_effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    eligibility_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SelectionConditionResult(Base):
    """【明细表 · 存全部条件】（已定案 · 04-database-design §10.3.1）。

    「只存未通过项 → 无法回答『这只基金通过了哪些条件』→ 也无法区分
    『通过了』与『根本没评估』—— 而后者会在条件集变更时大量出现。」

    约 9,600 行/次（1,200 候选 × 8 条件）。D-17 明令不做短路优化 ——
    「评估全部条件后一并记录」（§14.4）。条件求值不短路这件事本身在
    Task 16 由测试断言（那是本 Plan 最容易被『优化』掉的一处）。

    ── BLOCK-11：除 condition_version 外无任何字段名 ──
    §14.2 只给了示例格式（条件表达式 + ✓/✗ + 实际值 + 差距）。
    本表的列名全部为【补齐】，逐项对应那四栏：
      condition_expression / outcome / actual_value|actual_text / gap
    加上上游点名必含的 condition_version（「条件集本身会变更，
    不记录版本则历史结果无法解释」）。

    数值型与文本型实际值分两列，是因为「取同类前 20%」这种条件的实际值
    是 fund_tier = 'A+' 这样的枚举，塞进 NUMERIC 只能靠编码，
    而编码就是把可解释性重新丢掉。
    """

    __tablename__ = "selection_condition_result"
    __table_args__ = (
        UniqueConstraint(
            "fund_universe_member_id", "condition_id",
            name="uq_selection_condition_result",
        ),
        CheckConstraint(CONDITION_SHAPE_SQL, name="ck_selection_condition_shape"),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_universe_member_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_universe_member.id", ondelete="RESTRICT"),
        nullable=False,
    )
    condition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    condition_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_expression: Mapped[str] = mapped_column(String(256), nullable=False)
    outcome: Mapped[str] = mapped_column(condition_outcome_enum, nullable=False)
    actual_value: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    actual_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    # 「未通过时的差距」（§14.2）。只有 FAIL 才有意义 —— PASS 带 gap
    # 会让「还差多少」和「已经超出多少」混成一列。
    gap: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6: 补上 Task 7 留下的那条 FK（`factor_value.peer_group_snapshot_id`）**

Task 7 建 `factor_value` 时 `evaluation.peer_group_snapshot` 还不存在，
所以那一列当时【只有列没有 FK】。现在补上 —— ORM 与迁移必须同时改（G-16）。

```python
# src/fip/services/factor_service/models/factor.py

# ① 在 import 区补上 ForeignKeyConstraint
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,   # ← 新增
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

# ② FactorValue.__table_args__ 里，在 ix_factor_value_run 之后追加：
        # 迁移 0017 补上的 FK。03-erd §8.5 称 Peer Group 与 Factor Value 的
        # 关系是「上下文」而非「归属」（弱关系，引用非组合），但弱关系仍然
        # 是关系 —— 一个悬空的 peer_group_snapshot_id 会让「这个分位是在哪
        # 一组里算的」永久无法回答，而快照可复现正是它存在的全部理由。
        # 显式命名，使 ORM 与 op.create_foreign_key 两侧逐字对应。
        ForeignKeyConstraint(
            ["peer_group_snapshot_id"],
            ["evaluation.peer_group_snapshot.id"],
            ondelete="RESTRICT",
            name="fk_factor_value_peer_group_snapshot",
        ),
```

- [ ] **Step 7: 建包并在 `db/migrations/env.py` 注册**

```python
# src/fip/services/fund_service/models/__init__.py
```
（空文件。）

```python
# db/migrations/env.py —— 在 factor 那行之后追加
from fip.services.factor_service.models import factor  # noqa: F401 — services 层
from fip.services.fund_service.models import evaluation  # noqa: F401 — services 层
```

- [ ] **Step 8: 写迁移 `db/migrations/versions/0017_evaluation_schema.py`（枚举 + 前四张表）**

```python
# db/migrations/versions/0017_evaluation_schema.py
"""evaluation schema 九张表 + 9 个枚举，并补 factor_value 的 peer_group FK

Plan-2 Task 8。

裁定依据（docs/superpowers/specs/2026-09-02-plan2-factor-and-evaluation-design.md）：
  · D-14  peer_group_member 【不分区】（上游 PK 不含分区键，PG 层面不成立）
  · D-15  fund_universe_member.investment_eligibility 存【版本引用】，
          复合 FK → fund.investment_eligibility，ON DELETE RESTRICT
  · D-17  REJECTED 成员与全部条件结果落库，不做短路优化
  · D-18  B1 / B2 各自原子；快照表不设 updated_at；FK 一律 RESTRICT；
          只建必要的 PK 与 FK 索引
  · D-19  score_status 五值
  · G-7   cross_section_status_enum + n_effective（两状态都必填）
  · G-8   Rank / n_effective / Percentile 三者都落库

fund_tier 的联动 CHECK 是【补齐】—— 04-database-design 只给了
fund_ranking 的版本（见 ck_fund_tier_status 的注释）。

【已冻结的字面量】同 0016：不 import ORM 侧的 SQL 常量。

Revision ID: 0017
Revises: 0016
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

_SCHEMA = "evaluation"

_QUALITY_SOURCE_SQL = (
    "(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR "
    "(availability_quality = 'DERIVED' AND provider_available_at IS NULL "
    " AND published_at IS NOT NULL) OR "
    "(availability_quality = 'INFERRED' AND provider_available_at IS NULL "
    " AND published_at IS NULL)"
)
_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= "
    "(effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= (effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(available_at >= COALESCE(provider_available_at, published_at))"
)
_PERIOD_SQL = "{col} IN ('1M', '3M', '6M', '1Y', '3Y', '5Y')"
_NOT_UNCLASSIFIED_SQL = "classification_code <> 'UNCLASSIFIED'"
_CLASSIFICATION_LEVEL_SQL = "classification_level IN ('L1', 'L2')"
_SCORE_TOTAL_SQL = (
    "(score_status IN ('COMPLETED', 'PARTIAL') AND total_score IS NOT NULL) OR "
    "(score_status IN ('UNAVAILABLE', 'VALIDATION_PENDING', 'INSUFFICIENT_FACTORS') "
    " AND total_score IS NULL)"
)
_SCALE_SQL = "{col} IS NULL OR ({col} >= 0 AND {col} <= 100)"
_COMPLETENESS_SQL = "data_completeness >= 0 AND data_completeness <= 1"


def _pairing(value_col: str, status_col: str) -> str:
    return (
        f"({status_col} = 'AVAILABLE' AND {value_col} IS NOT NULL) OR "
        f"({status_col} <> 'AVAILABLE' AND {value_col} IS NULL)"
    )


_ATTRIBUTION_SHAPE_SQL = (
    "(participation = 'INCLUDED' "
    " AND normalized_score IS NOT NULL AND weighted_contribution IS NOT NULL "
    " AND exclusion_reason IS NULL "
    " AND weight = configured_weight + reallocated_weight) OR "
    "(participation = 'EXCLUDED' "
    " AND normalized_score IS NULL AND weighted_contribution IS NULL "
    " AND exclusion_reason IS NOT NULL "
    " AND weight = 0 AND reallocated_weight = 0)"
)
_RANKING_STATUS_SQL = (
    "(ranking_status = 'NORMAL' AND rank IS NOT NULL AND percentile IS NOT NULL) OR "
    "(ranking_status = 'INSUFFICIENT_SAMPLE' AND rank IS NULL AND percentile IS NULL)"
)
_TIER_STATUS_SQL = (
    "(classification_status = 'NORMAL' "
    " AND tier IS NOT NULL AND percentile IS NOT NULL) OR "
    "(classification_status = 'INSUFFICIENT_SAMPLE' "
    " AND tier IS NULL AND percentile IS NULL)"
)
_TIER_PEER_LEVEL_SQL = (
    "tier IS NULL OR "
    "(peer_sharpe_median IS NOT NULL AND peer_max_drawdown_median IS NOT NULL)"
)
_UNIVERSE_STRATEGY_SQL = "universe_strategy IN ('A', 'B', 'C')"
_UNIVERSE_SCORING_SQL = "universe_strategy = 'A' OR scoring_policy_version IS NOT NULL"
_CONDITION_SHAPE_SQL = (
    "(outcome = 'NOT_EVALUABLE' "
    " AND actual_value IS NULL AND actual_text IS NULL AND gap IS NULL) OR "
    "(outcome = 'PASS' "
    " AND (actual_value IS NOT NULL OR actual_text IS NOT NULL) "
    " AND gap IS NULL) OR "
    "(outcome = 'FAIL' "
    " AND (actual_value IS NOT NULL OR actual_text IS NOT NULL))"
)

_ENUM_DDL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cross_section_status_enum", ("NORMAL", "INSUFFICIENT_SAMPLE")),
    ("score_status_enum", (
        "COMPLETED", "PARTIAL", "UNAVAILABLE",
        "VALIDATION_PENDING", "INSUFFICIENT_FACTORS")),
    ("sub_score_status_enum", ("AVAILABLE", "UNAVAILABLE", "INSUFFICIENT_FACTORS")),
    ("sub_score_name_enum", (
        "Return", "Risk", "Risk-Adjusted", "Stability", "Relative Performance")),
    ("fund_tier_enum", ("A+", "A", "B", "C", "D")),
    ("selection_status_enum", ("SELECTED", "REJECTED")),
    ("universe_status_enum", ("COMPLETED", "INSUFFICIENT_UNIVERSE")),
    ("condition_outcome_enum", ("PASS", "FAIL", "NOT_EVALUABLE")),
    ("attribution_participation_enum", ("INCLUDED", "EXCLUDED")),
)


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*dict(_ENUM_DDL)[name], name=name, create_type=False)


def _existing(name: str) -> postgresql.ENUM:
    """0016 已建的枚举，在本迁移里只引用不创建。"""
    values = {
        "preference_direction_enum": (
            "HIGHER_IS_BETTER", "LOWER_IS_BETTER", "TARGET_RANGE",
            "STRATEGY_DEPENDENT"),
        "provenance_enum": ("DECIDED", "PROVISIONAL"),
        "availability_quality_enum": ("EXACT", "DERIVED", "INFERRED"),
    }[name]
    return postgresql.ENUM(*values, name=name, create_type=False)


def _time_source_columns() -> list[sa.Column]:
    return [
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "availability_quality", _existing("availability_quality_enum"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    ]


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True),
        server_default=sa.text("now()"), nullable=False,
    )


def upgrade() -> None:
    for name, values in _ENUM_DDL:
        rendered = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({rendered})")

    # ------------------------------------------------------- peer_group_snapshot
    op.create_table(
        "peer_group_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("classification_scheme", sa.String(length=32), nullable=False),
        sa.Column("classification_level", sa.String(length=2), nullable=False),
        sa.Column("classification_code", sa.String(length=32), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column(
            "classification_policy_version", sa.String(length=32), nullable=False
        ),
        sa.Column("peer_group_policy_version", sa.String(length=32), nullable=False),
        sa.Column("code_version", sa.String(length=64), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            _NOT_UNCLASSIFIED_SQL, name="ck_peer_group_not_unclassified"
        ),
        sa.CheckConstraint(_CLASSIFICATION_LEVEL_SQL, name="ck_peer_group_level"),
        sa.CheckConstraint("member_count >= 0", name="ck_peer_group_member_count"),
        sa.CheckConstraint("version >= 1", name="ck_peer_group_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "classification_scheme", "classification_code", "base_currency",
            "effective_at", "version", name="uq_peer_group_snapshot_business",
        ),
        schema=_SCHEMA,
    )

    # --------------------------------------------------------- peer_group_member
    # D-14：【不分区】。上游的 partition by effective_at 与它自己给的
    # PK (peer_group_snapshot_id, share_class_id) 互不相容 —— PostgreSQL
    # 要求分区表的 PK 必须包含分区键。不分区之后上游那条 PK 原样成立。
    op.create_table(
        "peer_group_member",
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("classification_history_id", sa.BigInteger(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["peer_group_snapshot_id"], ["evaluation.peer_group_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["classification_history_id"], ["fund.fund_classification_history.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("peer_group_snapshot_id", "share_class_id"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_peer_group_member_share_class", "peer_group_member",
        ["share_class_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_peer_group_member_classification", "peer_group_member",
        ["classification_history_id"], schema=_SCHEMA,
    )

    # ----------------------------------------------------------------- fund_score
    op.create_table(
        "fund_score",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluation_profile", sa.String(length=32), nullable=False),
        sa.Column("evaluation_period", sa.String(length=4), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("total_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("score_status", _enum("score_status_enum"), nullable=False),
        sa.Column("return_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column(
            "return_score_status", _enum("sub_score_status_enum"), nullable=False
        ),
        sa.Column("risk_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column(
            "risk_score_status", _enum("sub_score_status_enum"), nullable=False
        ),
        sa.Column(
            "risk_adjusted_score", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column(
            "risk_adjusted_score_status", _enum("sub_score_status_enum"),
            nullable=False,
        ),
        sa.Column("stability_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column(
            "stability_score_status", _enum("sub_score_status_enum"), nullable=False
        ),
        sa.Column(
            "relative_performance_score", sa.Numeric(precision=12, scale=8),
            nullable=True,
        ),
        sa.Column(
            "relative_performance_score_status", _enum("sub_score_status_enum"),
            nullable=False,
        ),
        sa.Column(
            "data_completeness", sa.Numeric(precision=12, scale=8), nullable=False
        ),
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_group_version", sa.Integer(), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=32), nullable=False),
        sa.Column("evaluation_policy_version", sa.String(length=32), nullable=False),
        sa.Column("factor_run_id", sa.BigInteger(), nullable=False),
        sa.Column("data_version", sa.String(length=32), nullable=False),
        sa.Column("code_version", sa.String(length=64), nullable=False),
        *_time_source_columns(),
        sa.CheckConstraint(_QUALITY_SOURCE_SQL, name="ck_fund_score_quality_source"),
        sa.CheckConstraint(_TIME_ORDER_SQL, name="ck_fund_score_time_order"),
        sa.CheckConstraint(
            _PERIOD_SQL.format(col="evaluation_period"), name="ck_fund_score_period"
        ),
        sa.CheckConstraint(_SCORE_TOTAL_SQL, name="ck_fund_score_total"),
        sa.CheckConstraint(
            _SCALE_SQL.format(col="total_score"), name="ck_fund_score_scale_total"
        ),
        sa.CheckConstraint(
            _pairing("return_score", "return_score_status"), name="ck_fund_score_return"
        ),
        sa.CheckConstraint(
            _pairing("risk_score", "risk_score_status"), name="ck_fund_score_risk"
        ),
        sa.CheckConstraint(
            _pairing("risk_adjusted_score", "risk_adjusted_score_status"),
            name="ck_fund_score_risk_adjusted",
        ),
        sa.CheckConstraint(
            _pairing("stability_score", "stability_score_status"),
            name="ck_fund_score_stability",
        ),
        sa.CheckConstraint(
            _pairing(
                "relative_performance_score", "relative_performance_score_status"
            ),
            name="ck_fund_score_relative",
        ),
        sa.CheckConstraint(_COMPLETENESS_SQL, name="ck_fund_score_completeness"),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["peer_group_snapshot_id"], ["evaluation.peer_group_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["factor_run_id"], ["factor.factor_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "share_class_id", "evaluation_profile", "evaluation_period",
            "effective_at", "version", name="uq_fund_score_business",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_fund_score_pit", "fund_score",
        ["share_class_id", "evaluation_profile", "evaluation_period",
         "effective_at", "available_at", sa.text("version DESC")],
        schema=_SCHEMA,
    )

    # ----------------------------------------------------- fund_score_attribution
    op.create_table(
        "fund_score_attribution",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_score_id", sa.BigInteger(), nullable=False),
        sa.Column("sub_score", _enum("sub_score_name_enum"), nullable=False),
        sa.Column("factor_id", sa.String(length=32), nullable=False),
        sa.Column("window", sa.String(length=4), nullable=False),
        sa.Column("factor_value_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_value", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column(
            "normalized_score", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column(
            "direction", _existing("preference_direction_enum"), nullable=False
        ),
        sa.Column(
            "participation", _enum("attribution_participation_enum"), nullable=False
        ),
        sa.Column(
            "configured_weight", sa.Numeric(precision=12, scale=8), nullable=False
        ),
        sa.Column(
            "reallocated_weight", sa.Numeric(precision=12, scale=8), nullable=False
        ),
        sa.Column("weight", sa.Numeric(precision=12, scale=8), nullable=False),
        sa.Column(
            "weighted_contribution", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column("exclusion_reason", sa.String(length=64), nullable=True),
        sa.Column("provenance", _existing("provenance_enum"), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            _ATTRIBUTION_SHAPE_SQL, name="ck_fund_score_attribution_shape"
        ),
        sa.CheckConstraint(
            "configured_weight >= 0 AND reallocated_weight >= 0 AND weight >= 0",
            name="ck_fund_score_attribution_weight",
        ),
        sa.CheckConstraint(
            _PERIOD_SQL.format(col='"window"'),
            name="ck_fund_score_attribution_window",
        ),
        sa.ForeignKeyConstraint(
            ["fund_score_id"], ["evaluation.fund_score.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_id"], ["factor.factor_definition.factor_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["factor_value_id"], ["factor.factor_value.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fund_score_id", "factor_id", "window",
            name="uq_fund_score_attribution_factor",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_fund_score_attribution_factor", "fund_score_attribution",
        ["factor_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_fund_score_attribution_value", "fund_score_attribution",
        ["factor_value_id"], schema=_SCHEMA,
    )
```

- [ ] **Step 9: 续写 0017（后五张表 + `factor_value` 的 FK + `downgrade()`）**

```python
# db/migrations/versions/0017_evaluation_schema.py —— upgrade() 续

    # --------------------------------------------------------------- fund_ranking
    op.create_table(
        "fund_ranking",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_score_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_group_version", sa.Integer(), nullable=False),
        sa.Column("evaluation_profile", sa.String(length=32), nullable=False),
        sa.Column("ranking_metric", sa.String(length=64), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column("evaluation_period", sa.String(length=4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("n_effective", sa.Integer(), nullable=False),
        sa.Column("peer_group_size", sa.Integer(), nullable=False),
        sa.Column("percentile", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column(
            "ranking_status", _enum("cross_section_status_enum"), nullable=False
        ),
        sa.Column("confidence_flag", sa.Boolean(), nullable=False),
        sa.Column("tie_method", sa.String(length=24), nullable=False),
        sa.Column("ranking_policy_version", sa.String(length=32), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=32), nullable=False),
        _created_at(),
        # 上游【逐字】给出的联动 CHECK（04-database-design:722-728）。
        sa.CheckConstraint(_RANKING_STATUS_SQL, name="ck_fund_ranking_status"),
        sa.CheckConstraint(
            "n_effective >= 0 AND peer_group_size >= 0 "
            "AND n_effective <= peer_group_size",
            name="ck_fund_ranking_counts",
        ),
        sa.CheckConstraint("rank IS NULL OR rank >= 1", name="ck_fund_ranking_rank"),
        sa.CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="ck_fund_ranking_percentile",
        ),
        sa.CheckConstraint(
            _PERIOD_SQL.format(col="evaluation_period"), name="ck_fund_ranking_period"
        ),
        sa.ForeignKeyConstraint(
            ["fund_score_id"], ["evaluation.fund_score.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["peer_group_snapshot_id"], ["evaluation.peer_group_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fund_score_id", "ranking_metric", name="uq_fund_ranking_scope"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_fund_ranking_peer_group", "fund_ranking",
        ["peer_group_snapshot_id"], schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ fund_tier
    op.create_table(
        "fund_tier",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_ranking_id", sa.BigInteger(), nullable=False),
        sa.Column("tier", _enum("fund_tier_enum"), nullable=True),
        sa.Column(
            "classification_status", _enum("cross_section_status_enum"),
            nullable=False,
        ),
        sa.Column("n_effective", sa.Integer(), nullable=False),
        sa.Column("percentile", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("total_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column(
            "peer_sharpe_median", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column(
            "peer_max_drawdown_median", sa.Numeric(precision=12, scale=8),
            nullable=True,
        ),
        sa.Column(
            "data_completeness", sa.Numeric(precision=12, scale=8), nullable=False
        ),
        sa.Column("confidence_flag", sa.Boolean(), nullable=False),
        sa.Column(
            "classification_policy_version", sa.String(length=32), nullable=False
        ),
        _created_at(),
        # ⚠️【补齐】：04-database-design 只给了 fund_ranking 的联动 CHECK，
        # fund_tier 的没给（BLOCK-9）。按同一形态推导，并合并 §8.5 已定案的
        # 「n_effective < 30 → tier = null，classification_status =
        # INSUFFICIENT_SAMPLE」。
        sa.CheckConstraint(_TIER_STATUS_SQL, name="ck_fund_tier_status"),
        # G-9 的数据库防线：有 Tier 就必须有组内绝对水平两项。
        sa.CheckConstraint(_TIER_PEER_LEVEL_SQL, name="ck_fund_tier_peer_level"),
        sa.CheckConstraint("n_effective >= 0", name="ck_fund_tier_n_effective"),
        sa.CheckConstraint(
            "percentile IS NULL OR (percentile >= 0 AND percentile <= 100)",
            name="ck_fund_tier_percentile",
        ),
        sa.CheckConstraint(
            _SCALE_SQL.format(col="total_score"), name="ck_fund_tier_score_scale"
        ),
        sa.CheckConstraint(_COMPLETENESS_SQL, name="ck_fund_tier_completeness"),
        sa.ForeignKeyConstraint(
            ["fund_ranking_id"], ["evaluation.fund_ranking.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_ranking_id", name="uq_fund_tier_ranking"),
        schema=_SCHEMA,
    )

    # ---------------------------------------------------- fund_universe_snapshot
    op.create_table(
        "fund_universe_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("decision_at", sa.Date(), nullable=False),
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_group_version", sa.Integer(), nullable=False),
        sa.Column("universe_strategy", sa.String(length=1), nullable=False),
        sa.Column(
            "snapshot_status", _enum("universe_status_enum"), nullable=False
        ),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("selection_policy_version", sa.String(length=32), nullable=False),
        sa.Column("eligibility_rules_version", sa.String(length=32), nullable=False),
        sa.Column("condition_version", sa.String(length=32), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=32), nullable=True),
        sa.Column(
            "classification_policy_version", sa.String(length=32), nullable=True
        ),
        sa.Column("ranking_policy_version", sa.String(length=32), nullable=True),
        sa.Column("evaluation_policy_version", sa.String(length=32), nullable=False),
        sa.Column("factor_run_id", sa.BigInteger(), nullable=False),
        sa.Column("data_version", sa.String(length=32), nullable=False),
        sa.Column("code_version", sa.String(length=64), nullable=False),
        _created_at(),
        sa.CheckConstraint(_UNIVERSE_STRATEGY_SQL, name="ck_fund_universe_strategy"),
        sa.CheckConstraint(
            _UNIVERSE_SCORING_SQL, name="ck_fund_universe_scoring_version"
        ),
        sa.CheckConstraint(
            "candidate_count >= 0 AND selected_count >= 0 "
            "AND selected_count <= candidate_count",
            name="ck_fund_universe_counts",
        ),
        # D-18：B2 引用【已提交的】B1 快照 ID。这条 NOT NULL 的 FK 就是那句话。
        sa.ForeignKeyConstraint(
            ["peer_group_snapshot_id"], ["evaluation.peer_group_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["factor_run_id"], ["factor.factor_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_at", "selection_policy_version",
            name="uq_fund_universe_snapshot_business",
        ),
        schema=_SCHEMA,
    )

    # ------------------------------------------------------ fund_universe_member
    op.create_table(
        "fund_universe_member",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_universe_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "selection_status", _enum("selection_status_enum"), nullable=False
        ),
        sa.Column("fund_score_id", sa.BigInteger(), nullable=True),
        sa.Column("fund_ranking_id", sa.BigInteger(), nullable=True),
        sa.Column("fund_tier_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "data_completeness", sa.Numeric(precision=12, scale=8), nullable=True
        ),
        sa.Column("eligibility_effective_at", sa.Date(), nullable=False),
        sa.Column("eligibility_version", sa.Integer(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "data_completeness IS NULL OR "
            "(data_completeness >= 0 AND data_completeness <= 1)",
            name="ck_fund_universe_member_completeness",
        ),
        sa.ForeignKeyConstraint(
            ["fund_universe_snapshot_id"],
            ["evaluation.fund_universe_snapshot.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fund_score_id"], ["evaluation.fund_score.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fund_ranking_id"], ["evaluation.fund_ranking.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fund_tier_id"], ["evaluation.fund_tier.id"], ondelete="RESTRICT"
        ),
        # D-15：investment_eligibility 存【版本引用】，复合 FK 指向
        # fund.investment_eligibility 的复合 PK。share_class_id 被两条 FK
        # 共用，因此数据库顺带保证「引用的那一版确实属于这只份额类别」。
        sa.ForeignKeyConstraint(
            ["share_class_id", "eligibility_effective_at", "eligibility_version"],
            ["fund.investment_eligibility.share_class_id",
             "fund.investment_eligibility.effective_at",
             "fund.investment_eligibility.version"],
            ondelete="RESTRICT", name="fk_fund_universe_member_eligibility",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fund_universe_snapshot_id", "share_class_id",
            name="uq_fund_universe_member",
        ),
        schema=_SCHEMA,
    )
    for col in ("share_class", "score", "ranking", "tier"):
        column = "share_class_id" if col == "share_class" else f"fund_{col}_id"
        op.create_index(
            f"ix_fund_universe_member_{col}", "fund_universe_member",
            [column], schema=_SCHEMA,
        )

    # ------------------------------------------------- selection_condition_result
    op.create_table(
        "selection_condition_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_universe_member_id", sa.BigInteger(), nullable=False),
        sa.Column("condition_id", sa.String(length=64), nullable=False),
        sa.Column("condition_version", sa.String(length=32), nullable=False),
        sa.Column("condition_expression", sa.String(length=256), nullable=False),
        sa.Column("outcome", _enum("condition_outcome_enum"), nullable=False),
        sa.Column("actual_value", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("actual_text", sa.String(length=64), nullable=True),
        sa.Column(
            "threshold_value", sa.Numeric(precision=18, scale=8), nullable=True
        ),
        sa.Column("gap", sa.Numeric(precision=18, scale=8), nullable=True),
        _created_at(),
        sa.CheckConstraint(_CONDITION_SHAPE_SQL, name="ck_selection_condition_shape"),
        sa.ForeignKeyConstraint(
            ["fund_universe_member_id"], ["evaluation.fund_universe_member.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fund_universe_member_id", "condition_id",
            name="uq_selection_condition_result",
        ),
        schema=_SCHEMA,
    )

    # ---- Task 7 留下的那条 FK：目标表到这里才存在。
    op.create_foreign_key(
        "fk_factor_value_peer_group_snapshot",
        "factor_value", "peer_group_snapshot",
        ["peer_group_snapshot_id"], ["id"],
        source_schema="factor", referent_schema="evaluation",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_factor_value_peer_group_snapshot", "factor_value",
        schema="factor", type_="foreignkey",
    )
    # 反 FK 顺序。
    op.drop_table("selection_condition_result", schema=_SCHEMA)
    for col in ("tier", "ranking", "score", "share_class"):
        op.drop_index(
            f"ix_fund_universe_member_{col}",
            table_name="fund_universe_member", schema=_SCHEMA,
        )
    op.drop_table("fund_universe_member", schema=_SCHEMA)
    op.drop_table("fund_universe_snapshot", schema=_SCHEMA)
    op.drop_table("fund_tier", schema=_SCHEMA)
    op.drop_index(
        "ix_fund_ranking_peer_group", table_name="fund_ranking", schema=_SCHEMA
    )
    op.drop_table("fund_ranking", schema=_SCHEMA)
    op.drop_index(
        "ix_fund_score_attribution_value",
        table_name="fund_score_attribution", schema=_SCHEMA,
    )
    op.drop_index(
        "ix_fund_score_attribution_factor",
        table_name="fund_score_attribution", schema=_SCHEMA,
    )
    op.drop_table("fund_score_attribution", schema=_SCHEMA)
    op.drop_index("ix_fund_score_pit", table_name="fund_score", schema=_SCHEMA)
    op.drop_table("fund_score", schema=_SCHEMA)
    op.drop_index(
        "ix_peer_group_member_classification",
        table_name="peer_group_member", schema=_SCHEMA,
    )
    op.drop_index(
        "ix_peer_group_member_share_class",
        table_name="peer_group_member", schema=_SCHEMA,
    )
    op.drop_table("peer_group_member", schema=_SCHEMA)
    op.drop_table("peer_group_snapshot", schema=_SCHEMA)
    for name, _ in reversed(_ENUM_DDL):
        op.execute(f"DROP TYPE IF EXISTS {name}")
```

- [ ] **Step 10: upgrade → downgrade → upgrade 往返验证**

```bash
.venv/bin/python - <<'PY'
import psycopg
with psycopg.connect("postgresql://localhost/postgres", autocommit=True) as c:
    c.execute("DROP DATABASE IF EXISTS fip_rt0017")
    c.execute("CREATE DATABASE fip_rt0017")
print("fip_rt0017 ready")
PY

export FIP_DATABASE_URL=postgresql+psycopg://localhost/fip_rt0017
.venv/bin/alembic -x db=dev upgrade head        # 0001 → 0017
.venv/bin/alembic -x db=dev downgrade 0016      # 0017 的 downgrade()
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev current             # 期望：0017 (head)
```

`downgrade 0016` 这一步专门用来逼出两个最可能的错误：

1. **`factor_value` 上的 FK 没先删** → `DROP TABLE peer_group_snapshot` 会
   报 `cannot drop table ... because other objects depend on it`。
   `downgrade()` 的第一句就是那条 `drop_constraint`。
2. **枚举没删干净** → 第三条 `upgrade` 炸在 `type ... already exists`。

再核对表与 FK 策略：

```bash
.venv/bin/python - <<'PY'
import psycopg
Q_T = """SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='evaluation' AND c.relkind IN ('r','p') ORDER BY 1"""
Q_F = """SELECT n.nspname||'.'||t.relname||'.'||c.conname, c.confdeltype
         FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
         JOIN pg_namespace n ON n.oid=t.relnamespace
         WHERE c.contype='f' AND n.nspname IN ('factor','evaluation')
         AND c.confdeltype <> 'r' ORDER BY 1"""
with psycopg.connect("postgresql://localhost/fip_rt0017") as c:
    print("tables:", [r[0] for r in c.execute(Q_T)])
    print("非 RESTRICT 的 FK（必须为空）:", c.execute(Q_F).fetchall())
PY
```

Expected:
```
tables: ['fund_ranking', 'fund_score', 'fund_score_attribution', 'fund_tier',
         'fund_universe_member', 'fund_universe_snapshot', 'peer_group_member',
         'peer_group_snapshot', 'selection_condition_result']
非 RESTRICT 的 FK（必须为空）: []
```

第二行是 D-18「FK 一律 `ON DELETE RESTRICT`」的直接验收 ——
PostgreSQL 把「未声明 ON DELETE」存成 `'a'`（NO ACTION），行为与 RESTRICT
在非延迟场景下几乎一致，**漏写不会被任何功能测试发现**，只有直接读
`pg_constraint.confdeltype` 才看得出来。

验证完删库：

```bash
.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://localhost/postgres', autocommit=True) as c:
    c.execute('DROP DATABASE IF EXISTS fip_rt0017')
print('dropped')"
unset FIP_DATABASE_URL
```

- [ ] **Step 11: G-16 闸门 —— autogenerate 必须报告零操作**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev revision --autogenerate -m "probe-0017" 2>&1 | tail -30
```

Expected: `upgrade()` / `downgrade()` 里**只有 `pass`**。确认后删探针文件：

```bash
rm db/migrations/versions/*probe-0017*.py
```

本任务最可能的三处非零输出：
- `op.drop_constraint('fk_factor_value_peer_group_snapshot', ...)` → Step 6
  只改了迁移没改 ORM（或反之）；
- `op.drop_constraint('fk_fund_universe_member_eligibility', ...)` → ORM 里
  复合 FK 的列顺序与迁移不一致（复合 FK 按列序比较）；
- 九张表被整体提议 DROP → `env.py` 忘了 import `evaluation` 模块（Step 7）。

- [ ] **Step 12: G-17 —— 重新生成 CHECK 黄金快照**

本任务新增 27 条 CHECK，autogenerate 对它们【完全失明】：

```bash
FIP_WRITE_CHECK_SNAPSHOT=1 .venv/bin/pytest \
    tests/integration/test_temporal_constraints.py -k snapshot
git diff tests/integration/check_constraints.snapshot
.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot
```

Expected diff：只新增 `evaluation.*` 的行。**逐条肉眼确认这三条**（它们
是本任务最容易写反的三处）：

1. `ck_fund_ranking_status` —— 必须与上游 04-database-design:722-728 的
   SQL 逐字同义（`NORMAL` → rank 与 percentile 都非空；`INSUFFICIENT_SAMPLE`
   → 两者都为空）。写成 `OR` 少一半就会放进「有 rank 没 percentile」的行，
   而 G-8 正是为了防这个。
2. `ck_fund_tier_status` —— 本 Plan 的【补齐】，diff 里要能看出它与
   `ck_fund_ranking_status` 是同一形态。
3. `ck_fund_score_relative` —— M1 的常态（`relative_performance_score` 为
   NULL 且 status = `UNAVAILABLE`）必须能通过；写成 `= 'UNAVAILABLE'` 而不是
   `<> 'AVAILABLE'` 会把 `INSUFFICIENT_FACTORS` 的子分全部拒掉。

**既有的 fund / market / governance / factor 行一行都不得变。**

- [ ] **Step 13: 全量验证**

```bash
.venv/bin/pytest tests/integration/test_evaluation_schema.py -v
.venv/bin/pytest tests/unit tests/fitness tests/integration
.venv/bin/ruff check src tests
make typecheck
```

Expected: Task 7 与 Task 8 的用例全绿，既有 281 条一条不减；ruff 与
mypy strict 无输出。

- [ ] **Step 14: 交付前对账 —— 14 张表逐表勾一遍**

对着下表逐行确认，任何一格对不上都不算完成：

| # | 表 | 时间模式 | 分区 | `updated_at` | 关键裁定 |
|---|---|---|---|---|---|
| 1 | `factor.factor_definition` | 纯维度 | 否 | ✅ 有（主数据） | 五列 Usage、方向、`provenance` |
| 2 | `factor.factor_version` | 纯维度 | 否 | ✅ 有（主数据） | `min_obs` + 三条依赖声明 |
| 3 | `factor.factor_run` | 批次 | 否 | ✅ 有（状态流转） | 幂等键 `(decision_at, strategy_version)` |
| 4 | `factor.factor_value` | 版本化事实 | **否**（本稿裁定） | ❌ 无 | D-12 `effective_at`；D-13 两个部分唯一索引；代理 PK |
| 5 | `factor.factor_effectiveness` | 明细 | 否 | ❌ 无 | D-1 拉入；`factor_version_id` 而非 `factor_id` |
| 6 | `evaluation.peer_group_snapshot` | 快照 | 否 | ❌ 无 | 无 `classification_key` 列；无 `evaluation_profile` 列；UNCLASSIFIED 不成组 |
| 7 | `evaluation.peer_group_member` | 明细 | **否**（D-14） | ❌ 无 | 上游 PK 原样成立；分类版本存引用 |
| 8 | `evaluation.fund_score` | 版本化事实 | **否**（本稿裁定） | ❌ 无 | D-19 五值；G-4 `data_completeness` NOT NULL |
| 9 | `evaluation.fund_score_attribution` | 明细 | **否**（本稿裁定） | ❌ 无 | 独立表非 JSONB；三列权重恒等式 |
| 10 | `evaluation.fund_ranking` | 派生 `0..1` | 否 | ❌ 无 | 上游逐字联动 CHECK；G-8 三者落库 |
| 11 | `evaluation.fund_tier` | 派生 `0..1` | 否 | ❌ 无 | 联动 CHECK 为【补齐】；G-9 两个中位数；阈值不进 CHECK |
| 12 | `evaluation.fund_universe_snapshot` | 快照 | 否 | ❌ 无 | 策略 A 评分列可空；引用已提交的 B1 |
| 13 | `evaluation.fund_universe_member` | 明细 | 否 | ❌ 无 | D-15 复合 FK 版本引用；D-17 含 REJECTED |
| 14 | `evaluation.selection_condition_result` | 明细 | 否 | ❌ 无 | D-17 存全部条件；`NOT_EVALUABLE` 第三值 |

---

## 起草中发现的矛盾与遗漏

以下六条**不是**设计定案里已有的裁定，是我在把 14 张表写成可执行 DDL 的
过程中撞到的。每条都给出了我在本稿里采取的做法与理由，但它们**应当被
复核**——尤其第 1、2、3 条，它们改变了上游「已定案」条目的形状。

1. **`factor_value` 的 PK 与它自己的两个部分唯一索引互相抵消（新发现，
   BLOCK-6 之外的第二处矛盾）。** 上游 PK 是
   `(share_class_id, factor_id, window, as_of_date, version)` 五列，而同一
   文件 §9.3【已定案】的 `ux_factor_value_with_policy` 存在的全部意义就是
   让这五元组相同、仅 `evaluation_policy_version` 不同的两行共存（D-13 的
   前半句）。五列 PK 会把那条定案索引变成永远无法触发的死代码；六列 PK
   又不成立（`evaluation_policy_version` 对不依赖 MAR 的因子必须为 NULL，
   PK 列不允许 NULL）。**本稿改用代理主键**，身份完全交给两个部分唯一索引。
   设计定案的 D-13 只处理了「哪些列进唯一约束」，没注意到它与 PK 的冲突。

2. **BLOCK-4（`factor_value` 与 `factor_version` 的关系是 FK 还是 VARCHAR）
   没有被任何一条 D 裁定。** D-16 只说 `factor_version` 引用
   `factor_definition`，没说 `factor_value` 怎么引用 `factor_version`。
   ERD 说 FK（`03-erd.md:396`），DB 设计说 `factor_version VARCHAR`
   （`:556`）。**本稿取 FK（`factor_version_id BIGINT`），不留 VARCHAR 副本**
   ——留副本就是第二份真值，而 `factor_effectiveness` 已经按
   `factor_version_id` 建 Business Key（`:620`），两处必须一致。

3. **BLOCK-14（`risk_free_rate_ref` 用 JSONB 还是列组）同样没有被裁定。**
   本稿取**列组四列**，理由是「验证期限匹配是否正确」是 WHERE 查询而不是
   展示，按 `01-postgresql §13.2` 必须结构化。**但其中 `rate_source_quality`
   有一处对不上**：上游提到该字段有 `INTERPOLATED` 取值（`FE:496`），
   而 Plan-1 落地的 `market.risk_free_rate` 用的是
   `availability_quality_enum`（`EXACT`/`DERIVED`/`INFERRED`），**没有插值
   路径也没有 `INTERPOLATED` 这个值**。本稿复用
   `availability_quality_enum`（存的是被引用那一版 R_f 的真实 quality），
   等 R_f 插值真的实现时需要重新审视 —— 那时 `INTERPOLATED` 到底是
   `availability_quality` 的第四个值还是另一个维度，上游没有说。

4. **`factor_value` 与 `fund_score` 的分区被本稿单方面取消。** 上游对两者
   分别定案了「按 `as_of_date` 月分区」（1.5 亿行）与「年分区」（3,000 万
   行）。D-14 只裁定了 `peer_group_member` 不分区。本稿把同一理由推广到
   这两张表（M1 量级分别约 75 万行与 45 万行；Plan-1 已证实分区的真实
   成本），**这超出了 D-14 的字面授权**，需要确认。
   顺带一个实测结论：我原以为「部分唯一索引 + 分区表」在 PostgreSQL 里
   不兼容，**实测 PG 17 是允许的**（分区键在索引列中即可，已在 `fip_dev`
   上验证 `CREATE UNIQUE INDEX ... WHERE ...` 于分区表及其子分区均成功）。
   所以将来要补分区不存在结构性障碍，`effective_at` 已经在两个索引里了。

5. **BLOCK-9 的另一半（`fund_tier` 的联动 CHECK）按要求补齐了，但 BLOCK-9
   的第一半（组内 Sharpe / MDD 中位数落哪张表）设计定案也没裁。** 本稿裁在
   `fund_tier`，理由是 G-5：这两个中位数是因子派生量，放进
   `peer_group_snapshot` 会让 B1 的构建依赖因子计算，正面违反「Peer Group
   构建不得 import 评分模块」。同时**这条 CHECK 有一个副作用需要确认**：
   `ck_fund_tier_peer_level` 规定「有 Tier 就必须有两个中位数」，于是
   组内 Sharpe 全部 `UNAVAILABLE` 时该组【不产出 Tier】。这是 G-9
   「仅展示 Tier 视为违反」的严格读法，但上游没有正面说过这种情形。

6. **两处上游「必须保留副本」与 D-15「引用而非副本」的张力，本稿分别处理，
   判据是「副本会不会分叉」。**
   - `fund_score_attribution.raw_value`：上游逐字要求保留（`:456`「只有
     标准化值时用户看不懂『0.83 分』从何而来」）。**保留副本**——
     `factor_value` 禁止 UPDATE 且版本钉死，副本在结构上不可能分叉，与
     `adjusted_nav`（`(行, decision_at)` 的二元函数，标量列装不下）不是
     一类问题。
   - `fund_universe_member.investment_eligibility`：D-15 已裁定存引用，
     本稿用复合 FK `(share_class_id, effective_at, version)` 实现。
     **顺带发现一个好处**：复用 `share_class_id` 这一列让数据库顺带保证
     「引用的那一版可投资性确实属于这只份额类别」，代理键做不到。
   - 同一判据下**未保留**的两处：`peer_group_snapshot.classification_key`
     （三列的拼接，不另存）与 `fund_universe_member` 的「约束标注」
     （`eligibility_status` 的纯函数，由 strategy_library 派生）。

另外两处**上游本身的遗漏**，本稿只是照单补齐、没有额外判断，一并记下备查：

- **BLOCK-11**：`selection_condition_result` 除 `condition_version` 外
  **一个字段名都没有**，§14.2 只给了示例格式。本稿的六列全部是【补齐】，
  其中 `NOT_EVALUABLE` 这个 outcome 取值是我加的第三值（上游只有 ✓/✗）——
  理由写在枚举的 docstring 里：输入 `UNAVAILABLE` 的条件被记成 `FAIL`，
  就是 G-3 在条件层的同一个错误。
- **BLOCK-12**：本次要落的枚举里，除 `cross_section_status_enum` 外
  **上游一个 `CREATE TYPE` 都没写**，类型名全部是【补齐】。
  `fund_tier_enum` 的取值（`A+`/`A`/`B`/`C`/`D`）与
  `sub_score_name_enum` 的取值（含 `Relative Performance` 中间那个空格）
  是逐字的，**类型名不是**。
