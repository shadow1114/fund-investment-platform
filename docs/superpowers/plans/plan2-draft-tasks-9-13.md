# Plan-2 实现计划草案 · Task 9–13（计算流核心）

> **本文件是草案**，供并入 `docs/superpowers/plans/2026-09-02-plan2-factor-and-evaluation.md`。
> 接口契约以该计划的「跨任务接口契约」节为**唯一权威**；本草案不发明契约中已有的名字与签名。
> 契约中**缺失**的名字（kernel 函数、Threshold Resolver、`factor_effectiveness` 的写入形状等）
> 在各任务的 `Interfaces` 中首次定义，并在文末「起草期间发现的矛盾与遗漏」逐条登记。

## 本草案共用的前置事实（写实现前先核对）

| 事实 | 出处 | 对 Task 9–13 的影响 |
|---|---|---|
| 包落位为 `src/fip/libs/quant_engine` / `src/fip/libs/strategy_library` | D-3 | 但**仓库现状是 `src/fip/quant_engine` / `src/fip/strategy_library`**（Plan-1 建的空包），且 `tests/unit/test_package_layout.py` 与 `tests/fitness/test_architecture.py` 都按现状写死。Task 4 必须完成搬迁并同步这两个测试，Task 9 才能按本草案的路径落文件 |
| `NavNumeric = Numeric(18, 8)`、`RatioNumeric = Numeric(12, 8)` | `src/fip/platform/db/types.py` | 因子 `raw_value` 出口量化到 8 位小数、`ROUND_HALF_UP`；`normalized_value`（分位）同样 8 位 |
| strategy_library **不得** import `sqlalchemy` / `fip.platform.db.*` | SDL-1、`tests/fitness/test_architecture.py` | 标度 `8` 与质量字面量 `"INFERRED"` 只能在 strategy_library 里**写常量**，由**测试**去钉住它与 `NavNumeric.scale` / `AvailabilityQuality.INFERRED` 一致（Plan-1 对 `DISCLOSURE_LAG_DAYS` 用的就是这个模式） |
| 高精度只在**出口**量化 | `normalization/adjusted_nav.py` | 所有 kernel **不量化**，只有 `compute_factor` / `normalize_peer_group` / `evaluate_effectiveness` 在返回前量化 |
| AKShare 链路 `availability_quality` 恒为 `INFERRED` | G-15、Plan-1 交接 | 见文末矛盾 ②：D-10 的 WARNING 第二触发条件会让 M1 的 `FactorStatus.VALID` **不可达** |

---

### Task 9: 10 个因子的纯函数 + Metric Version 登记

**Files:**

- Create: `src/fip/libs/strategy_library/factor/__init__.py`
- Create: `src/fip/libs/strategy_library/factor/definitions.py`
- Create: `src/fip/libs/strategy_library/factor/status.py`
- Create: `src/fip/libs/strategy_library/factor/compute.py`
- Create: `config/strategy/factor/v1.yaml`
- Modify: `config/strategy/metric/v1.yaml`
- Test: `tests/unit/test_factor_definitions.py`
- Test: `tests/unit/test_factor_kernels.py`
- Test: `tests/unit/test_factor_compute.py`
- Test: `tests/unit/test_factor_reproducibility.py`
- Test: `tests/unit/test_metric_config_pinning.py`

**Interfaces:**

*Consumes*（Task 3 产出，签名取自计划的接口契约，**不得改**）：

```python
from fip.libs.quant_engine.series import returns, rolling_windows, running_max
from fip.libs.quant_engine.stats import mean, stdev
# returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]
# rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]
# running_max(xs: Sequence[Decimal]) -> list[Decimal]
# mean(xs: Sequence[Decimal]) -> Decimal
# stdev(xs: Sequence[Decimal], ddof: int) -> Decimal
```

*Produces*（契约已定义的原样落地；kernel 为本任务新增）：

```python
# fip.libs.strategy_library.factor.definitions
class FactorCategory(StrEnum): RET; RISK; RAP; STAB
class PreferenceDirection(StrEnum): HIGHER_IS_BETTER; LOWER_IS_BETTER      # 契约
class FactorDependency(StrEnum): ADJUSTED_NAV; RISK_FREE_RATE; MAR
class ObservationUnit(StrEnum): DAILY_RETURN; MONTHLY_RETURN
@dataclass(frozen=True, slots=True)
class FactorDefinition:
    factor_id: str; name: str; category: FactorCategory; sub_score: str
    direction: PreferenceDirection; dependencies: tuple[FactorDependency, ...]
    min_obs: int; observation_unit: ObservationUnit
FACTORS: dict[str, FactorDefinition]                 # 10 条，键为 Factor ID
TRADING_DAYS_PER_YEAR: int = 252
VOLATILITY_DDOF: int = 1
ROLLING_WINDOW_POINTS: int = 252
ROLLING_STEP_POINTS: int = 21
VALUE_SCALE: int = 8

# fip.libs.strategy_library.factor.status
class FactorStatus(StrEnum): VALID; WARNING; INVALID; UNAVAILABLE          # 契约
class UnavailableReason(StrEnum): INSUFFICIENT_HISTORY; BENCHMARK_UNAVAILABLE;
    RISK_FREE_RATE_UNAVAILABLE; MAR_NOT_CONFIGURED; ZERO_MAX_DRAWDOWN;
    ZERO_DOWNSIDE_VOLATILITY; ZERO_TRACKING_ERROR; ZERO_VOLATILITY;
    MAR_SERIES_NOT_SUPPORTED          # 第 9 值【补齐】，见 Task 10 Step 4
class WarningReason(StrEnum): NEAR_MIN_OBS; INFERRED_AVAILABILITY
class InvalidReason(StrEnum): NON_FINITE; NEGATIVE_VARIANCE
INFERRED_QUALITY: str = "INFERRED"
WARNING_OBS_MULTIPLIER: Decimal = Decimal("1.5")

# fip.libs.strategy_library.factor.compute —— kernel（纯数学，不量化、不判 status）
def annualized_return(navs, periods_per_year) -> Decimal
def volatility(rets, ddof, periods_per_year) -> Decimal
def downside_volatility(rets, mar_annual, ddof, periods_per_year) -> Decimal
def max_drawdown(navs) -> Decimal
def sharpe_ratio(ann_return, vol, risk_free) -> Decimal | None
def sortino_ratio(ann_return, downside_vol, mar_annual) -> Decimal | None
def calmar_ratio(ann_return, mdd) -> Decimal | None
def month_end_positions(dates) -> list[int]
def monthly_returns(navs, dates) -> list[Decimal]
def win_rate(monthly_rets) -> Decimal | None
def rolling_return(navs, window, step, periods_per_year) -> Decimal | None
def rolling_sharpes(navs, window, step, risk_free, ddof, periods_per_year) -> list[Decimal] | None
def rolling_sharpe_stability(sharpes, ddof) -> Decimal | None

# fip.libs.strategy_library.factor.compute —— 契约入口
@dataclass(frozen=True, slots=True)
class FactorInput: ...       # 契约原文，字段一字不改
@dataclass(frozen=True, slots=True)
class FactorResult: ...      # 契约原文，字段一字不改
def compute_factor(factor_id: str, inp: FactorInput) -> FactorResult
```

---

- [ ] **Step 1: 写因子身份的失败测试**

10 个因子的 Factor ID / 类别 / 方向 / 依赖直接抄 D-8 的表。这条测试是「因子清单」的
唯一机器可读来源——写错方向的后果是分位整条翻转，而翻转后的分数看起来完全正常。

```python
# tests/unit/test_factor_definitions.py
from fip.libs.strategy_library.factor.definitions import (
    FACTORS,
    FactorCategory,
    FactorDependency,
    ObservationUnit,
    PreferenceDirection,
)

EXPECTED = {
    "F-RET-001":  ("年化收益率",          FactorCategory.RET,  "Return",         PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV,)),
    "F-RET-002":  ("Rolling Return",      FactorCategory.RET,  "Return",         PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV,)),
    "F-RISK-001": ("Volatility",          FactorCategory.RISK, "Risk",           PreferenceDirection.LOWER_IS_BETTER,  (FactorDependency.ADJUSTED_NAV,)),
    "F-RISK-002": ("Downside Volatility", FactorCategory.RISK, "Risk",           PreferenceDirection.LOWER_IS_BETTER,  (FactorDependency.ADJUSTED_NAV, FactorDependency.MAR)),
    "F-RISK-003": ("Maximum Drawdown",    FactorCategory.RISK, "Risk",           PreferenceDirection.LOWER_IS_BETTER,  (FactorDependency.ADJUSTED_NAV,)),
    "F-RAP-001":  ("Sharpe Ratio",        FactorCategory.RAP,  "Risk-Adjusted",  PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV, FactorDependency.RISK_FREE_RATE)),
    "F-RAP-002":  ("Sortino Ratio",       FactorCategory.RAP,  "Risk-Adjusted",  PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV, FactorDependency.MAR)),
    "F-RAP-003":  ("Calmar Ratio",        FactorCategory.RAP,  "Risk-Adjusted",  PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV,)),
    "F-STAB-001": ("Win Rate",            FactorCategory.STAB, "Stability",      PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV,)),
    "F-STAB-002": ("Rolling Sharpe 稳定性", FactorCategory.STAB, "Stability",     PreferenceDirection.HIGHER_IS_BETTER, (FactorDependency.ADJUSTED_NAV, FactorDependency.RISK_FREE_RATE)),
}


def test_exactly_ten_factors():
    assert set(FACTORS) == set(EXPECTED)


def test_每个因子的身份与_D8_表一致():
    for factor_id, (name, category, sub_score, direction, deps) in EXPECTED.items():
        d = FACTORS[factor_id]
        assert (d.name, d.category, d.sub_score, d.direction, d.dependencies) == (
            name, category, sub_score, direction, deps
        ), factor_id


def test_min_obs_按观测单位分档():
    """D-10：日频 252、Rolling 类 504（两个窗口）、月频 36。"""
    assert FACTORS["F-RET-001"].min_obs == 252
    assert FACTORS["F-RET-001"].observation_unit is ObservationUnit.DAILY_RETURN
    assert FACTORS["F-RET-002"].min_obs == 504
    assert FACTORS["F-STAB-002"].min_obs == 504
    assert FACTORS["F-STAB-001"].min_obs == 36
    assert FACTORS["F-STAB-001"].observation_unit is ObservationUnit.MONTHLY_RETURN


def test_没有中性方向():
    """D-11.3：上游的「中性」不属四值枚举，M1 不实现，枚举里必须只有两个值。"""
    assert {d.value for d in PreferenceDirection} == {
        "HIGHER_IS_BETTER", "LOWER_IS_BETTER"
    }
```

跑一遍确认**失败**（模块尚不存在）：

```bash
.venv/bin/pytest tests/unit/test_factor_definitions.py -q
# 预期：ModuleNotFoundError: No module named 'fip.libs.strategy_library.factor'
```

- [ ] **Step 2: 实现 `definitions.py`，跑通 Step 1**

```python
# src/fip/libs/strategy_library/factor/definitions.py
"""10 个因子的身份。纯维度定义 —— 不含计算、不碰数据库（SDL-1）。

因子清单与公式的来源是设计定案 D-8 / D-9，整个因子域文档在仓库中缺失，
本模块与 config/strategy/factor/v1.yaml 里的口径项【全部标 PROVISIONAL】，
拿到正式的 04-factor 文档后应整体替换而不是逐条改。
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class FactorCategory(StrEnum):
    RET = "RET"
    RISK = "RISK"
    RAP = "RAP"
    STAB = "STAB"


class PreferenceDirection(StrEnum):
    """方向枚举。

    已知缺口（D-11 第 3 点）：上游在 Active Equity 画像下把 Tracking Error 的方向
    称为「中性」，而「中性」不是这里的任何一个值。M1 无 Benchmark、TE 恒
    UNAVAILABLE，因此本 Plan 【不实现】中性方向 —— 这是登记在案的缺口，不是遗漏。
    """

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class FactorDependency(StrEnum):
    ADJUSTED_NAV = "ADJUSTED_NAV"
    RISK_FREE_RATE = "RISK_FREE_RATE"
    MAR = "MAR"


class ObservationUnit(StrEnum):
    """观测数按什么单位计 —— 决定 min_obs 的量纲。

    Win Rate 的 min_obs = 36 指的是【36 个月度收益】，不是 36 个交易日。
    两者相差 21 倍，混用会让一只成立两个月的基金通过日频阈值。
    """

    DAILY_RETURN = "DAILY_RETURN"
    MONTHLY_RETURN = "MONTHLY_RETURN"


# ---- Metric Version 口径常量 ----------------------------------------------
# 这些值同时登记在 config/strategy/metric/v1.yaml。为什么代码里也要有一份：
# strategy_library 是纯函数层，读 YAML 属 I/O，SDL-1 禁止。为什么两份不会分叉：
# tests/unit/test_metric_config_pinning.py 逐条断言两者相等 ——
# Plan-1 对 cli.DISCLOSURE_LAG_DAYS 用的是同一个模式（常量在代码里、由测试钉住）。
TRADING_DAYS_PER_YEAR = 252          # DECIDED（10-api/01 §12.3）
VOLATILITY_DDOF = 1                  # PROVISIONAL（D-9：样本标准差）
ROLLING_WINDOW_POINTS = 252          # PROVISIONAL（D-9 rolling.window_days）
ROLLING_STEP_POINTS = 21             # PROVISIONAL（D-9 rolling.step_days）
RETURN_BASIS = "SIMPLE"              # PROVISIONAL（D-9）
MAR_DAILY_CONVERSION = "SIMPLE_DIVISION"   # PROVISIONAL【补齐】，见 Task 10
VALUE_SCALE = 8                      # = NavNumeric.scale，由测试钉住

MIN_OBS_DAILY = 252
MIN_OBS_ROLLING = 504                # 两个窗口（D-10）
MIN_OBS_MONTHLY = 36

# 出口量化步长。ROUND_HALF_UP 与 PostgreSQL numeric 舍入一致 —— 若用 Python
# 默认的 ROUND_HALF_EVEN，恰落在半个 ulp 上的值会与库里的值差 1 个 ulp。
VALUE_QUANTUM = Decimal(1).scaleb(-VALUE_SCALE)


@dataclass(frozen=True, slots=True)
class FactorDefinition:
    factor_id: str
    name: str
    category: FactorCategory
    sub_score: str          # 取值必须落在 Task 14 的 SubScoreName 上，由该任务的测试钉住
    direction: PreferenceDirection
    dependencies: tuple[FactorDependency, ...]
    min_obs: int
    observation_unit: ObservationUnit


_NAV = (FactorDependency.ADJUSTED_NAV,)
_NAV_RF = (FactorDependency.ADJUSTED_NAV, FactorDependency.RISK_FREE_RATE)
_NAV_MAR = (FactorDependency.ADJUSTED_NAV, FactorDependency.MAR)

FACTORS: dict[str, FactorDefinition] = {
    d.factor_id: d
    for d in (
        FactorDefinition("F-RET-001", "年化收益率", FactorCategory.RET, "Return",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RET-002", "Rolling Return", FactorCategory.RET, "Return",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV,
                         MIN_OBS_ROLLING, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RISK-001", "Volatility", FactorCategory.RISK, "Risk",
                         PreferenceDirection.LOWER_IS_BETTER, _NAV,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RISK-002", "Downside Volatility", FactorCategory.RISK, "Risk",
                         PreferenceDirection.LOWER_IS_BETTER, _NAV_MAR,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RISK-003", "Maximum Drawdown", FactorCategory.RISK, "Risk",
                         PreferenceDirection.LOWER_IS_BETTER, _NAV,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RAP-001", "Sharpe Ratio", FactorCategory.RAP, "Risk-Adjusted",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV_RF,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RAP-002", "Sortino Ratio", FactorCategory.RAP, "Risk-Adjusted",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV_MAR,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-RAP-003", "Calmar Ratio", FactorCategory.RAP, "Risk-Adjusted",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV,
                         MIN_OBS_DAILY, ObservationUnit.DAILY_RETURN),
        FactorDefinition("F-STAB-001", "Win Rate", FactorCategory.STAB, "Stability",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV,
                         MIN_OBS_MONTHLY, ObservationUnit.MONTHLY_RETURN),
        FactorDefinition("F-STAB-002", "Rolling Sharpe 稳定性", FactorCategory.STAB, "Stability",
                         PreferenceDirection.HIGHER_IS_BETTER, _NAV_RF,
                         MIN_OBS_ROLLING, ObservationUnit.DAILY_RETURN),
    )
}
```

```bash
.venv/bin/pytest tests/unit/test_factor_definitions.py -q   # 预期 4 passed
```

- [ ] **Step 3: `status.py` —— Factor Status 四值的生产方触发条件（D-10）**

先写失败测试：

```python
# tests/unit/test_factor_compute.py（本文件后续步骤继续追加）
from decimal import Decimal

from fip.libs.strategy_library.factor.status import (
    INFERRED_QUALITY,
    FactorStatus,
    UnavailableReason,
    WarningReason,
    observation_status,
)


def test_观测数低于_min_obs_是_UNAVAILABLE_不是_WARNING():
    status, reason = observation_status(251, 252, "EXACT")
    assert status is FactorStatus.UNAVAILABLE
    assert reason == UnavailableReason.INSUFFICIENT_HISTORY.value


def test_落在_min_obs_到_1_5_倍之间是_WARNING():
    assert observation_status(252, 252, "EXACT") == (
        FactorStatus.WARNING, WarningReason.NEAR_MIN_OBS.value
    )
    assert observation_status(377, 252, "EXACT") == (
        FactorStatus.WARNING, WarningReason.NEAR_MIN_OBS.value
    )
    assert observation_status(378, 252, "EXACT") == (FactorStatus.VALID, "")


def test_链路含_INFERRED_一律_WARNING():
    """G-15：AKShare 链路恒 INFERRED，所以这条在 M1 是常态而非例外。"""
    assert observation_status(1000, 252, INFERRED_QUALITY) == (
        FactorStatus.WARNING, WarningReason.INFERRED_AVAILABILITY.value
    )


def test_INFERRED_字面量与平台枚举一致():
    """strategy_library 不得 import platform.source（SDL-1），因此这里写的是
    字面量。字面量与枚举分叉时，WARNING 会静默不再触发 —— 由本测试钉住。"""
    from fip.platform.source.availability import AvailabilityQuality

    assert INFERRED_QUALITY == AvailabilityQuality.INFERRED.value
```

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q
# 预期：ModuleNotFoundError: ...factor.status
```

实现：

```python
# src/fip/libs/strategy_library/factor/status.py
"""Factor Status 四值的【生产方】触发条件（设计定案 D-10）。

上游 01-fund-evaluation §7.3 只给了消费方规则（VALID 参与 / WARNING 参与但标记
须传递 / INVALID 不参与且告警 / UNAVAILABLE 不参与按缺失处理）。生产方何时置哪个值
在缺失的 04-factor/08-factor-output 里，因此本模块全部为【补齐 · PROVISIONAL】。
"""

from decimal import Decimal
from enum import StrEnum


class FactorStatus(StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class UnavailableReason(StrEnum):
    """10-api/03 §4.3.5 的八类，外加一条【补齐】。

    ⚠️ 与 D-10 的冲突已在设计层裁定：D-10 把「分母为 0」列在 INVALID 下，
    而 D-9 与本枚举（ZERO_MAX_DRAWDOWN / ZERO_VOLATILITY / ZERO_DOWNSIDE_VOLATILITY）
    把同一情形列在 UNAVAILABLE 下。**取 UNAVAILABLE** ——「窗口内无回撤」是好消息型
    不可用，不是算错了；把它标成 INVALID 会触发 evaluation_status = FAILED 并告警，
    对一只从未回撤的基金发告警是错的。INVALID 只留给真正的数学失效（见 InvalidReason）。
    """

    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"
    RISK_FREE_RATE_UNAVAILABLE = "RISK_FREE_RATE_UNAVAILABLE"
    MAR_NOT_CONFIGURED = "MAR_NOT_CONFIGURED"
    ZERO_MAX_DRAWDOWN = "ZERO_MAX_DRAWDOWN"
    ZERO_DOWNSIDE_VOLATILITY = "ZERO_DOWNSIDE_VOLATILITY"
    ZERO_TRACKING_ERROR = "ZERO_TRACKING_ERROR"
    ZERO_VOLATILITY = "ZERO_VOLATILITY"
    # 【补齐】mar_policy = RISK_FREE 时 MAR 是序列，而契约的 FactorInput.mar 是标量，
    # 装不下它。绝不把序列塌陷成标量（Plan-1 在 adjusted_nav 标量列上的同一教训），
    # 因此如实产出 UNAVAILABLE。见 Task 10 Step 4 与文末矛盾 ①。
    MAR_SERIES_NOT_SUPPORTED = "MAR_SERIES_NOT_SUPPORTED"


class WarningReason(StrEnum):
    NEAR_MIN_OBS = "NEAR_MIN_OBS"
    INFERRED_AVAILABILITY = "INFERRED_AVAILABILITY"


class InvalidReason(StrEnum):
    """「算了但算错了」—— 须告警。分母为 0 不在此列，见 UnavailableReason 的说明。"""

    NON_FINITE = "NON_FINITE"
    NEGATIVE_VARIANCE = "NEGATIVE_VARIANCE"


# 链路聚合后的 availability_quality（Task 2 产出）里出现这个值 → WARNING。
# 字面量而非 import：strategy_library 不得依赖 platform.source（SDL-1）。
# 与 AvailabilityQuality.INFERRED 的一致性由 tests/unit/test_factor_compute.py
# ::test_INFERRED_字面量与平台枚举一致 钉住。
INFERRED_QUALITY = "INFERRED"

WARNING_OBS_MULTIPLIER = Decimal("1.5")


def observation_status(
    observation_count: int, min_obs: int, chain_quality: str
) -> tuple[FactorStatus, str]:
    """按 D-10 判定「观测数 + 链路质量」这一维的 status。

    依赖缺失（R_f / MAR）不在这里判 —— 那一维由 compute_factor 更早地短路，
    且【优先级更高】：见 compute_factor 的 docstring。

    返回 (status, reason)。VALID 时 reason 为空串 —— 契约规定 reason 只在
    status 非 VALID 时必填。
    """
    if observation_count < min_obs:
        return FactorStatus.UNAVAILABLE, UnavailableReason.INSUFFICIENT_HISTORY.value
    if chain_quality == INFERRED_QUALITY:
        return FactorStatus.WARNING, WarningReason.INFERRED_AVAILABILITY.value
    if Decimal(observation_count) < Decimal(min_obs) * WARNING_OBS_MULTIPLIER:
        return FactorStatus.WARNING, WarningReason.NEAR_MIN_OBS.value
    return FactorStatus.VALID, ""
```

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q   # 预期 4 passed
```

- [ ] **Step 4: kernel 的失败测试 —— 10 个因子逐个给出手算期望值**

主夹具 `NAVS_A = [100, 200, 100, 200]`（4 个点、3 个收益率）。手算全过程：

```
r        = [200/100−1, 100/200−1, 200/100−1] = [1, −0.5, 1]
mean(r)  = (1 − 0.5 + 1)/3 = 0.5
Σ(r−μ)²  = 0.5² + (−1)² + 0.5² = 0.25 + 1 + 0.25 = 1.5
var(ddof=1) = 1.5/2 = 0.75          stdev = √0.75
periods_per_year 取 3（= N），使年化指数 252/N 变成 1，全部结果落在有限小数上：
  年化收益率 = (200/100)^(3/3) − 1 = 2 − 1 = 1
  Volatility = √0.75 × √3 = √2.25 = 1.5
  running_max = [100, 200, 200, 200]
  回撤        = [0, 0, 1 − 100/200, 0] = [0, 0, 0.5, 0]  → MDD = 0.5
  Calmar      = 1 / 0.5 = 2
  Sharpe(R_f = 0.1) = (1 − 0.1)/1.5 = 0.9/1.5 = 0.6
  下行（MAR = 0，MAR_daily = 0）：min(r, 0) = [0, −0.5, 0]
     μ = −1/6，偏差 [1/6, −1/3, 1/6]，平方和 = 1/36 + 4/36 + 1/36 = 1/6
     var = (1/6)/2 = 1/12，stdev = √(1/12)
     Downside Vol = √(1/12) × √3 = √(3/12) = √0.25 = 0.5
  Sortino(MAR = 0) = (1 − 0)/0.5 = 2
  下行（MAR = 0.3，MAR_daily = 0.3/3 = 0.1）：min(r − 0.1, 0) = [0, −0.6, 0]
     μ = −0.2，偏差 [0.2, −0.4, 0.2]，平方和 = 0.04 + 0.16 + 0.04 = 0.24
     var = 0.12，stdev = √0.12，Downside Vol = √0.12 × √3 = √0.36 = 0.6
  periods_per_year 取 252 时：年化收益率 = 2^84 − 1 = 19342813113834066795298815
```

```python
# tests/unit/test_factor_kernels.py
"""10 个因子的 kernel。每条断言的期望值都是手算得到的，不是跑一遍实现抄回来的。

periods_per_year 在多数用例里取 3 而不是 252 —— 让年化指数 252/N 恰好为 1，
全部中间量落在有限小数上，期望值可以逐位手写。252 的路径另有专门用例。
"""

import datetime as dt
from decimal import Decimal, localcontext

import pytest

from fip.libs.strategy_library.factor.compute import (
    annualized_return,
    calmar_ratio,
    downside_volatility,
    max_drawdown,
    month_end_positions,
    monthly_returns,
    rolling_return,
    rolling_sharpe_stability,
    rolling_sharpes,
    sharpe_ratio,
    sortino_ratio,
    volatility,
    win_rate,
)

D = Decimal
NAVS_A = [D(100), D(200), D(100), D(200)]
TOL = D("1e-25")   # 无理数期望值用闭式对照，容差远严于 G-2 的 1e-10


def close(actual: Decimal, expected: Decimal) -> bool:
    return abs(actual - expected) < TOL


# ---- F-RET-001 年化收益率 -------------------------------------------------
def test_年化收益率_指数为1时精确等于1():
    assert annualized_return(NAVS_A, 3) == D(1)


def test_年化收益率_252_口径等于2的84次方减1():
    """(200/100)^(252/3) − 1 = 2^84 − 1。2^84 = 19342813113834066795298816。"""
    assert annualized_return(NAVS_A, 252) == D(2) ** 84 - 1
    assert annualized_return(NAVS_A, 252) == D("19342813113834066795298815")


# ---- F-RISK-001 Volatility -----------------------------------------------
def test_volatility_等于1点5():
    """√0.75 × √3 = √2.25 = 1.5，精确。"""
    assert close(volatility([D(1), D("-0.5"), D(1)], 1, 3), D("1.5"))


def test_volatility_ddof_1_与_0_不同():
    """ddof 是 PROVISIONAL 口径选择，改动必须让测试变红。
    ddof=0：var = 1.5/3 = 0.5，vol = √0.5 × √3 = √1.5 = 1.224744871…"""
    with localcontext() as ctx:
        ctx.prec = 60
        assert close(volatility([D(1), D("-0.5"), D(1)], 0, 3), D("1.5").sqrt())


# ---- F-RISK-002 Downside Volatility --------------------------------------
def test_下行波动_MAR为0时等于0点5():
    assert close(downside_volatility([D(1), D("-0.5"), D(1)], D(0), 1, 3), D("0.5"))


def test_下行波动_MAR为0点3时等于0点6():
    """MAR_daily = 0.3/3 = 0.1（SIMPLE_DIVISION 口径），√0.12 × √3 = √0.36 = 0.6。"""
    assert close(downside_volatility([D(1), D("-0.5"), D(1)], D("0.3"), 1, 3), D("0.6"))


# ---- F-RISK-003 Maximum Drawdown -----------------------------------------
def test_最大回撤等于0点5且取正值():
    assert max_drawdown(NAVS_A) == D("0.5")


def test_单调上升序列的最大回撤恰为0():
    assert max_drawdown([D(100), D(110), D(120)]) == D(0)


# ---- F-RAP-001 Sharpe ----------------------------------------------------
def test_sharpe_等于0点6():
    assert close(sharpe_ratio(D(1), D("1.5"), D("0.1")), D("0.6"))


def test_sharpe_在波动为0时返回_None_不是_inf():
    """D-9：Volatility = 0 → UNAVAILABLE。绝不填 inf、不填极大值（G-3）。"""
    assert sharpe_ratio(D(1), D(0), D("0.1")) is None


# ---- F-RAP-002 Sortino ---------------------------------------------------
def test_sortino_等于2():
    assert close(sortino_ratio(D(1), D("0.5"), D(0)), D(2))


def test_sortino_在下行波动为0时返回_None():
    assert sortino_ratio(D(1), D(0), D(0)) is None


# ---- F-RAP-003 Calmar ----------------------------------------------------
def test_calmar_等于2():
    assert calmar_ratio(D(1), D("0.5")) == D(2)


def test_calmar_在最大回撤为0时返回_None_不是_inf():
    """C-6 在因子层的体现 —— 这是本任务最容易做错的一处。"""
    assert calmar_ratio(D(1), D(0)) is None


# ---- F-STAB-001 Win Rate -------------------------------------------------
MONTH_END_NAVS = [D(100), D(110), D(121), D(110), D(121)]
MONTH_END_DATES = [
    dt.date(2024, 1, 31), dt.date(2024, 2, 29), dt.date(2024, 3, 29),
    dt.date(2024, 4, 30), dt.date(2024, 5, 31),
]


def test_月末取点只取每个自然月的最后一个观测():
    dates = [dt.date(2024, 1, 5), dt.date(2024, 1, 31), dt.date(2024, 2, 29)]
    assert month_end_positions(dates) == [1, 2]


def test_胜率等于0点75():
    """月度收益 [+0.1, +0.1, −0.0909…, +0.1] → 3 胜 / 4 期 = 0.75，精确。"""
    rets = monthly_returns(MONTH_END_NAVS, MONTH_END_DATES)
    assert len(rets) == 4
    assert win_rate(rets) == D("0.75")


def test_胜率把恰好为0的月份计为非胜():
    assert win_rate([D(0), D("0.1")]) == D("0.5")


# ---- F-RET-002 Rolling Return --------------------------------------------
NAVS_R = [D(100), D(200), D(100), D(200), D(300)]


def test_rolling_return_是各窗口年化收益率的均值():
    """window=3, step=1 → 三个窗口 [100,200,100] [200,100,200] [100,200,300]。
    periods_per_year = 2 使每个窗口的指数 2/2 = 1：
      窗口年化 = [100/100−1, 200/200−1, 300/100−1] = [0, 0, 2]
      均值 = 2/3 = 0.666666…"""
    with localcontext() as ctx:
        ctx.prec = 60
        expected = D(2) / D(3)
    assert close(rolling_return(NAVS_R, 3, 1, 2), expected)


# ---- F-STAB-002 Rolling Sharpe 稳定性 -------------------------------------
def test_rolling_sharpes_逐窗口计算():
    """窗口 1/2 的年化 = 0、vol = √1.125 × √2 = √2.25 = 1.5 → Sharpe = 0；
    窗口 3 的年化 = 2、r = [1, 0.5]、μ = 0.75、Σ(r−μ)² = 0.125、var = 0.125、
    vol = √0.125 × √2 = √0.25 = 0.5 → Sharpe = 2/0.5 = 4。"""
    sharpes = rolling_sharpes(NAVS_R, 3, 1, D(0), 1, 2)
    assert sharpes is not None
    assert [close(s, e) for s, e in zip(sharpes, [D(0), D(0), D(4)], strict=True)] == [
        True, True, True
    ]


def test_稳定性取负标准差():
    """[1, 2, 3]：μ = 2，Σ(x−μ)² = 2，var = 2/2 = 1，stdev = 1 → 稳定性 = −1。"""
    assert rolling_sharpe_stability([D(1), D(2), D(3)], 1) == D(-1)


def test_稳定性对_NAVS_R_的手算值():
    """Sharpe 序列 [0, 0, 4]：μ = 4/3，Σ(x−μ)² = 16/9 + 16/9 + 64/9 = 96/9，
    var = 96/18 = 16/3，stdev = √(16/3) → 稳定性 = −√(16/3) = −2.309401…"""
    with localcontext() as ctx:
        ctx.prec = 60
        expected = -(D(16) / D(3)).sqrt()
    sharpes = rolling_sharpes(NAVS_R, 3, 1, D(0), 1, 2)
    assert close(rolling_sharpe_stability(sharpes, 1), expected)


def test_任一窗口波动为0时整个稳定性因子不可算():
    """G-3：不得把那个窗口悄悄跳过 —— 跳过会改变样本，且没有任何信号。"""
    navs = [D(100), D(200), D(100), D(200), D(400)]  # 末窗口 [100,200,400] 收益恒 +1
    assert rolling_sharpes(navs, 3, 1, D(0), 1, 2) is None
```

```bash
.venv/bin/pytest tests/unit/test_factor_kernels.py -q
# 预期：ImportError: cannot import name 'annualized_return' from
#       'fip.libs.strategy_library.factor.compute'（模块尚不存在）
```

- [ ] **Step 5: 实现 kernel（`compute.py` 上半部），跑通 Step 4**

```python
# src/fip/libs/strategy_library/factor/compute.py
"""10 个因子的纯函数。

分两层：
  · kernel（本文件上半部）—— 纯数学。不量化、不判 status、不认识 FactorInput。
    它们是可以手算校对的最小单元，测试用的期望值全部来自手算。
  · compute_factor（下半部）—— 契约入口。做输入校验、依赖检查、status 判定、
    出口量化，并把 kernel 的 None 翻译成 UNAVAILABLE + reason。

精度策略照抄 normalization/adjusted_nav.py 的教训：内部一律高精度，
【只在出口量化】。先降精度再累乘会让舍入误差随链路长度累积。
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_UP,
    Decimal,
    DecimalException,
    localcontext,
)

from fip.libs.quant_engine.series import returns, rolling_windows, running_max
from fip.libs.quant_engine.stats import mean, stdev
from fip.libs.strategy_library.factor.definitions import (
    FACTORS,
    MIN_OBS_MONTHLY,
    RETURN_BASIS,
    ROLLING_STEP_POINTS,
    ROLLING_WINDOW_POINTS,
    TRADING_DAYS_PER_YEAR,
    VALUE_QUANTUM,
    VOLATILITY_DDOF,
    FactorDependency,
    ObservationUnit,
)
from fip.libs.strategy_library.factor.status import (
    FactorStatus,
    InvalidReason,
    UnavailableReason,
    observation_status,
)

# 与 adjusted_nav 同一组常数：60 位对外精度 + 60 位保护位。滚动窗口的 Sharpe
# 序列可达数百项，每项内部又是一次开方与除法，保护位不能省。
_PRECISION = 60
_GUARD_DIGITS = 60
_COMPUTE_PRECISION = _PRECISION + _GUARD_DIGITS

ZERO = Decimal(0)
ONE = Decimal(1)


# ==========================================================================
# kernel —— 纯数学
# ==========================================================================

def annualized_return(navs: Sequence[Decimal], periods_per_year: int) -> Decimal:
    """GEOMETRIC 年化：(adj_T / adj_0)^(periods_per_year / N) − 1，N = len(navs) − 1。

    口径为 PROVISIONAL（D-9）：与算术年化在波动大时差异显著。
    """
    if len(navs) < 2:
        raise ValueError(f"年化收益率至少需要 2 个净值点，实得 {len(navs)}")
    if navs[0] <= 0 or navs[-1] <= 0:
        raise ValueError("净值必须为正 —— 复权净值链路已构造性保证，此处只做防御")
    n = Decimal(len(navs) - 1)
    return (navs[-1] / navs[0]) ** (Decimal(periods_per_year) / n) - ONE


def volatility(
    rets: Sequence[Decimal], ddof: int, periods_per_year: int
) -> Decimal:
    """stdev(r, ddof) × √periods_per_year。"""
    return stdev(rets, ddof=ddof) * Decimal(periods_per_year).sqrt()


def downside_deviations(
    rets: Sequence[Decimal], mar_annual: Decimal, periods_per_year: int
) -> list[Decimal]:
    """min(r_t − MAR_daily, 0)。

    MAR_daily = MAR_annual / periods_per_year（SIMPLE_DIVISION）——【补齐 PROVISIONAL】。
    另一种口径是几何折算 (1 + MAR)^(1/252) − 1；两者在 MAR 较大时差异可观，
    因此这是一次真正的口径选择而不是实现细节，登记在 metric/v1.yaml。
    """
    mar_daily = mar_annual / Decimal(periods_per_year)
    return [min(r - mar_daily, ZERO) for r in rets]


def downside_volatility(
    rets: Sequence[Decimal], mar_annual: Decimal, ddof: int, periods_per_year: int
) -> Decimal:
    deviations = downside_deviations(rets, mar_annual, periods_per_year)
    return stdev(deviations, ddof=ddof) * Decimal(periods_per_year).sqrt()


def max_drawdown(navs: Sequence[Decimal]) -> Decimal:
    """max over t of (1 − adj_t / running_max(adj)_t)。取正值，越小越好。

    basis = ADJUSTED_NAV（DECIDED）：回撤必须含分红再投资，否则分红当天会被
    记成一笔回撤。
    """
    peaks = running_max(navs)
    return max(ONE - nav / peak for nav, peak in zip(navs, peaks, strict=True))


def sharpe_ratio(
    ann_return: Decimal, vol: Decimal, risk_free: Decimal
) -> Decimal | None:
    """(年化收益率 − R_f) / Volatility。Volatility = 0 时返回 None。

    返回 None 而不是 inf / 极大值：调用方必须把它记成 UNAVAILABLE（G-3）。
    """
    if vol == ZERO:
        return None
    return (ann_return - risk_free) / vol


def sortino_ratio(
    ann_return: Decimal, downside_vol: Decimal, mar_annual: Decimal
) -> Decimal | None:
    if downside_vol == ZERO:
        return None
    return (ann_return - mar_annual) / downside_vol


def calmar_ratio(ann_return: Decimal, mdd: Decimal) -> Decimal | None:
    """年化收益率 / Max Drawdown。MDD = 0 时返回 None，【不得】填 inf。"""
    if mdd == ZERO:
        return None
    return ann_return / mdd


def month_end_positions(dates: Sequence[dt.date]) -> list[int]:
    """每个自然月最后一个观测日在原序列中的下标，按时间升序。

    用「该月出现过的最后一个观测」而不是「日历月末」：月末可能是非交易日，
    按日历日取会静默丢掉整个月。
    """
    last: dict[tuple[int, int], int] = {}
    for i, day in enumerate(dates):
        last[(day.year, day.month)] = i
    return [last[k] for k in sorted(last)]


def monthly_returns(
    navs: Sequence[Decimal], dates: Sequence[dt.date]
) -> list[Decimal]:
    positions = month_end_positions(dates)
    return returns([navs[i] for i in positions], RETURN_BASIS)


def win_rate(monthly_rets: Sequence[Decimal]) -> Decimal | None:
    """count(月度收益 > 0) / count(月度收益)。

    恰为 0 的月份计为非胜：`> 0` 而不是 `>= 0`。frequency = MONTHLY 为
    PROVISIONAL —— 日频胜率接近 50%，无区分度。
    """
    if not monthly_rets:
        return None
    wins = sum(1 for r in monthly_rets if r > ZERO)
    return Decimal(wins) / Decimal(len(monthly_rets))


def rolling_annualized_returns(
    navs: Sequence[Decimal], window: int, step: int, periods_per_year: int
) -> list[Decimal]:
    return [
        annualized_return(w, periods_per_year)
        for w in rolling_windows(navs, window, step)
    ]


def rolling_return(
    navs: Sequence[Decimal], window: int, step: int, periods_per_year: int
) -> Decimal | None:
    """滚动窗口年化收益率的【均值】。

    ⚠️【补齐 PROVISIONAL】D-9 的公式表给了 9 条公式，唯独没给 F-RET-002 的
    聚合式。取均值的理由是量纲：D-21 裁定 Rolling Return 归 RET 正是因为
    「它的量纲是收益率」，而均值保持量纲、中位数同样保持但对窗口重叠更迟钝。
    """
    values = rolling_annualized_returns(navs, window, step, periods_per_year)
    if not values:
        return None
    return mean(values)


def rolling_sharpes(
    navs: Sequence[Decimal],
    window: int,
    step: int,
    risk_free: Decimal,
    ddof: int,
    periods_per_year: int,
) -> list[Decimal] | None:
    """逐窗口的 Sharpe 序列。任一窗口不可算 → 整体返回 None。

    为什么不跳过不可算的窗口：跳过会静默改变样本集（稳定性是对这个样本集的
    离散度），而且没有任何信号告诉下游「这条序列少了两项」。G-3 的同一条原则：
    不可算就是不可算，不得用一个「差不多的」样本替代。
    """
    out: list[Decimal] = []
    for w in rolling_windows(navs, window, step):
        rets = returns(w, RETURN_BASIS)
        vol = volatility(rets, ddof, periods_per_year)
        sharpe = sharpe_ratio(annualized_return(w, periods_per_year), vol, risk_free)
        if sharpe is None:
            return None
        out.append(sharpe)
    return out or None


def rolling_sharpe_stability(
    sharpes: Sequence[Decimal] | None, ddof: int
) -> Decimal | None:
    """−stdev(滚动 Sharpe 序列, ddof)。取负使「越大越好」的方向统一。"""
    if sharpes is None or len(sharpes) < 2:
        return None
    return -stdev(sharpes, ddof=ddof)
```

```bash
.venv/bin/pytest tests/unit/test_factor_kernels.py -q   # 预期 20 passed
```

- [ ] **Step 6: `compute_factor` 的失败测试 —— 状态机与 G-3 的四条不可填充路径**

```python
# tests/unit/test_factor_compute.py（追加）
import datetime as dt
from decimal import Decimal, localcontext

import pytest

from fip.libs.strategy_library.factor.compute import (
    FactorInput,
    FactorResult,
    compute_factor,
)

D = Decimal


def _series(n_returns: int, r: str, start: str = "100"):
    """等比序列：n_returns 个收益率、n_returns + 1 个净值点。日期取连续自然日。"""
    navs = [D(start)]
    for _ in range(n_returns):
        navs.append(navs[-1] * (D(1) + D(r)))
    base = dt.date(2020, 1, 1)
    dates = [base + dt.timedelta(days=i) for i in range(len(navs))]
    return tuple(navs), tuple(dates)


def _input(n_returns=400, r="0.001", *, quality="EXACT", rf=D("0.02"), mar=D(0)):
    navs, dates = _series(n_returns, r)
    return FactorInput(
        effective_at=dates[-1],
        adjusted_navs=navs,
        nav_dates=dates,
        chain_quality=quality,
        risk_free_rate=rf,
        mar=mar,
    )


def test_年化收益率_等比序列的闭式对照():
    """253 个点、252 个收益率，指数 252/252 = 1 → (1.001)^252 − 1。"""
    result = compute_factor("F-RET-001", _input(252, "0.001"))
    with localcontext() as ctx:
        ctx.prec = 120
        expected = (D("1.001") ** 252 - 1).quantize(D("1e-8"), rounding="ROUND_HALF_UP")
    assert result.value == expected
    assert result.observation_count == 252


def test_零波动序列的_Sharpe_是_UNAVAILABLE_且_value_为_None():
    """G-3：绝不填 0、不填 inf、不填上期值。"""
    result = compute_factor("F-RAP-001", _input(400, "0.001"))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.value is None
    assert result.reason == UnavailableReason.ZERO_VOLATILITY.value


def test_单调上升序列的_Calmar_是_UNAVAILABLE_不是_inf():
    result = compute_factor("F-RAP-003", _input(400, "0.001"))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.value is None
    assert result.reason == UnavailableReason.ZERO_MAX_DRAWDOWN.value


def test_从未下跌的序列下行波动为_UNAVAILABLE():
    result = compute_factor("F-RISK-002", _input(400, "0.001", mar=D(0)))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.reason == UnavailableReason.ZERO_DOWNSIDE_VOLATILITY.value


@pytest.mark.parametrize("factor_id", ["F-RISK-002", "F-RAP-002"])
def test_mar_未配置时依赖_MAR_的因子一律_UNAVAILABLE(factor_id):
    """G-6：mar_policy 必填无默认。mar=None 表示未配置，绝不当作 0。"""
    result = compute_factor(factor_id, _input(400, "0.001", mar=None))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.value is None
    assert result.reason == UnavailableReason.MAR_NOT_CONFIGURED.value


@pytest.mark.parametrize("factor_id", ["F-RAP-001", "F-STAB-002"])
def test_rf_不可得时依赖_Rf_的因子一律_UNAVAILABLE(factor_id):
    """不得默认 R_f = 0（FE:656）。"""
    result = compute_factor(factor_id, _input(600, "0.001", rf=None))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.reason == UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value


def test_依赖缺失的优先级高于观测数不足():
    """两者都成立时只能报一个 reason。取依赖缺失 —— 它是【政策级】故障，
    对全体基金一致；被数据稀疏掩盖会让一次配置遗漏永远查不出来。"""
    result = compute_factor("F-RAP-002", _input(10, "0.001", mar=None))
    assert result.reason == UnavailableReason.MAR_NOT_CONFIGURED.value


def test_观测数不足时是_UNAVAILABLE_且_observation_count_如实返回():
    result = compute_factor("F-RET-001", _input(100, "0.001"))
    assert result.status is FactorStatus.UNAVAILABLE
    assert result.reason == UnavailableReason.INSUFFICIENT_HISTORY.value
    assert result.observation_count == 100      # 「差多少」必须可见


def test_月频因子的_observation_count_是月度收益数():
    """400 个自然日 ≈ 14 个月 → 13 个月度收益 < 36 → UNAVAILABLE。"""
    result = compute_factor("F-STAB-001", _input(400, "0.001"))
    assert result.observation_count == 13
    assert result.status is FactorStatus.UNAVAILABLE


def test_INFERRED_链路让_VALID_不可达():
    """G-15 + D-10 的连带后果：AKShare 链路恒 INFERRED，M1 的因子最好情况是
    WARNING。这条测试把这个事实钉住 —— 否则下游会把 WARNING 当异常处理。"""
    result = compute_factor("F-RET-001", _input(400, "0.001", quality="INFERRED"))
    assert result.status is FactorStatus.WARNING
    assert result.reason == WarningReason.INFERRED_AVAILABILITY.value


def test_未知_factor_id_响亮失败():
    with pytest.raises(KeyError):
        compute_factor("F-NOPE-999", _input())


def test_日期与净值长度不一致响亮失败():
    navs, dates = _series(10, "0.001")
    with pytest.raises(ValueError, match="长度"):
        compute_factor("F-RET-001", FactorInput(
            effective_at=dates[-1], adjusted_navs=navs, nav_dates=dates[:-1],
            chain_quality="EXACT", risk_free_rate=D("0.02"), mar=D(0),
        ))


def test_日期未按升序响亮失败():
    navs, dates = _series(10, "0.001")
    with pytest.raises(ValueError, match="升序"):
        compute_factor("F-RET-001", FactorInput(
            effective_at=dates[-1], adjusted_navs=navs,
            nav_dates=tuple(reversed(dates)),
            chain_quality="EXACT", risk_free_rate=D("0.02"), mar=D(0),
        ))
```

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q
# 预期：ImportError: cannot import name 'compute_factor'
```

- [ ] **Step 7: 实现 `compute_factor`，跑通 Step 6**

```python
# src/fip/libs/strategy_library/factor/compute.py（追加到文件末尾）

# ==========================================================================
# 契约入口
# ==========================================================================

@dataclass(frozen=True, slots=True)
class FactorInput:
    """因子计算的全部输入。纯函数只吃它，不碰数据库（SDL-1）。

    字段一字不改地取自计划的跨任务接口契约。数据经 Plan-1 的 PIT 端口注入，
    因此「可见性」这件事在进入本模块之前就已经被构造性地保证了。
    """

    effective_at: dt.date
    adjusted_navs: tuple[Decimal, ...]
    nav_dates: tuple[dt.date, ...]
    chain_quality: str
    risk_free_rate: Decimal | None
    mar: Decimal | None


@dataclass(frozen=True, slots=True)
class FactorResult:
    factor_id: str
    value: Decimal | None
    status: FactorStatus
    reason: str
    observation_count: int


def _quantize(value: Decimal) -> Decimal:
    """出口量化到 factor_value.raw_value 的标度（NUMERIC(18, 8)）。

    ROUND_HALF_UP 对齐 PostgreSQL 的 numeric 舍入 —— 换成 ROUND_HALF_EVEN，
    恰落在半个 ulp 上的值会与库里的值差 1 个 ulp，可复现性对照随即分叉。
    """
    return value.quantize(VALUE_QUANTUM, rounding=ROUND_HALF_UP)


def _validate(inp: FactorInput) -> None:
    if len(inp.adjusted_navs) != len(inp.nav_dates):
        raise ValueError(
            f"净值与日期长度不一致：{len(inp.adjusted_navs)} vs {len(inp.nav_dates)}"
        )
    if any(b <= a for a, b in zip(inp.nav_dates, inp.nav_dates[1:], strict=False)):
        raise ValueError("nav_dates 必须严格按日期升序且不重复")
    if any(v <= 0 for v in inp.adjusted_navs):
        raise ValueError("复权净值必须为正")


def _observation_count(inp: FactorInput, unit: ObservationUnit) -> int:
    if unit is ObservationUnit.MONTHLY_RETURN:
        return max(len(month_end_positions(inp.nav_dates)) - 1, 0)
    return max(len(inp.adjusted_navs) - 1, 0)


def _compute_value(factor_id: str, inp: FactorInput) -> tuple[Decimal | None, str]:
    """算出裸值。返回 (值, 不可算原因)；值非 None 时原因为空串。

    调用方保证：观测数已达标、依赖已可得。因此这里只可能因为「分母为 0」
    这一类【好消息型】不可用而返回 None。
    """
    navs = list(inp.adjusted_navs)
    rets = returns(navs, RETURN_BASIS)
    ppy = TRADING_DAYS_PER_YEAR

    if factor_id == "F-RET-001":
        return annualized_return(navs, ppy), ""

    if factor_id == "F-RET-002":
        value = rolling_return(navs, ROLLING_WINDOW_POINTS, ROLLING_STEP_POINTS, ppy)
        return (value, "") if value is not None else (
            None, UnavailableReason.INSUFFICIENT_HISTORY.value
        )

    if factor_id == "F-RISK-001":
        return volatility(rets, VOLATILITY_DDOF, ppy), ""

    if factor_id == "F-RISK-002":
        assert inp.mar is not None
        value = downside_volatility(rets, inp.mar, VOLATILITY_DDOF, ppy)
        if value == ZERO:
            return None, UnavailableReason.ZERO_DOWNSIDE_VOLATILITY.value
        return value, ""

    if factor_id == "F-RISK-003":
        return max_drawdown(navs), ""

    if factor_id == "F-RAP-001":
        assert inp.risk_free_rate is not None
        vol = volatility(rets, VOLATILITY_DDOF, ppy)
        value = sharpe_ratio(annualized_return(navs, ppy), vol, inp.risk_free_rate)
        if value is None:
            return None, UnavailableReason.ZERO_VOLATILITY.value
        return value, ""

    if factor_id == "F-RAP-002":
        assert inp.mar is not None
        dvol = downside_volatility(rets, inp.mar, VOLATILITY_DDOF, ppy)
        value = sortino_ratio(annualized_return(navs, ppy), dvol, inp.mar)
        if value is None:
            return None, UnavailableReason.ZERO_DOWNSIDE_VOLATILITY.value
        return value, ""

    if factor_id == "F-RAP-003":
        value = calmar_ratio(annualized_return(navs, ppy), max_drawdown(navs))
        if value is None:
            return None, UnavailableReason.ZERO_MAX_DRAWDOWN.value
        return value, ""

    if factor_id == "F-STAB-001":
        value = win_rate(monthly_returns(navs, list(inp.nav_dates)))
        return (value, "") if value is not None else (
            None, UnavailableReason.INSUFFICIENT_HISTORY.value
        )

    if factor_id == "F-STAB-002":
        assert inp.risk_free_rate is not None
        sharpes = rolling_sharpes(
            navs, ROLLING_WINDOW_POINTS, ROLLING_STEP_POINTS,
            inp.risk_free_rate, VOLATILITY_DDOF, ppy,
        )
        value = rolling_sharpe_stability(sharpes, VOLATILITY_DDOF)
        if value is None:
            return None, UnavailableReason.ZERO_VOLATILITY.value
        return value, ""

    raise KeyError(f"未登记的 Factor ID：{factor_id}")


def compute_factor(factor_id: str, inp: FactorInput) -> FactorResult:
    """按 Factor ID 计算一个因子。

    判定顺序（【补齐】，由 test_依赖缺失的优先级高于观测数不足 钉住）：
      ① 输入结构性错误 → 抛异常（这是编程错误，不是业务缺失，绝不吞成 UNAVAILABLE）
      ② 必需依赖缺失（R_f / MAR）→ UNAVAILABLE。**优先于 ③** —— 依赖缺失是政策级
         故障，对全体基金一致；若被数据稀疏掩盖，一次 mar_policy 遗漏永远查不出来
      ③ 观测数 < min_obs → UNAVAILABLE(INSUFFICIENT_HISTORY)
      ④ 裸值算不出（分母为 0）→ UNAVAILABLE，reason 取 ZERO_* 三类之一
      ⑤ 数学失效（NaN / 负方差）→ INVALID，须告警
      ⑥ 其余 → observation_status 判 VALID / WARNING

    value 在 UNAVAILABLE / INVALID 时【恒为 None】—— 不填 0、不填上期值、
    不填 inf、不填组内均值（G-3）。
    """
    definition = FACTORS[factor_id]
    _validate(inp)
    observations = _observation_count(inp, definition.observation_unit)

    if FactorDependency.MAR in definition.dependencies and inp.mar is None:
        return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                            UnavailableReason.MAR_NOT_CONFIGURED.value, observations)
    if (
        FactorDependency.RISK_FREE_RATE in definition.dependencies
        and inp.risk_free_rate is None
    ):
        return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                            UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value,
                            observations)

    status, reason = observation_status(
        observations, definition.min_obs, inp.chain_quality
    )
    if status is FactorStatus.UNAVAILABLE:
        return FactorResult(factor_id, None, status, reason, observations)

    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        try:
            value, unavailable_reason = _compute_value(factor_id, inp)
        except DecimalException:
            # 「算了但算错了」——须告警（10-api/03 §4.3.5）。与④的区别：
            # ④ 是「这个业务情形下本来就没有定义」，⑤ 是「数值链路坏了」。
            return FactorResult(factor_id, None, FactorStatus.INVALID,
                                InvalidReason.NON_FINITE.value, observations)
        if value is None:
            return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                                unavailable_reason, observations)
        if not value.is_finite():
            return FactorResult(factor_id, None, FactorStatus.INVALID,
                                InvalidReason.NON_FINITE.value, observations)
        quantized = _quantize(value)

    return FactorResult(factor_id, quantized, status, reason, observations)
```

`MIN_OBS_MONTHLY` 在实现里未直接引用（它经 `FACTORS` 生效），import 会被 ruff 判为
未使用——从 import 清单里去掉。

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q   # 预期 17 passed
.venv/bin/ruff check src tests && make typecheck
```

- [ ] **Step 8: G-2 可复现性测试（先证伪）**

```python
# tests/unit/test_factor_reproducibility.py
"""G-2：同一输入重算必须一致，容差 1e-10。

为什么这条测试不是恒真的：因子链路里有三处会引入不确定性 ——
① 用 set / dict 迭代顺序参与求和；② 用 float 中转；③ 依赖 decimal 的
全局上下文精度（被别的测试改过就会分叉）。本测试把第三种显式做出来。
"""

import decimal
from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor.compute import compute_factor
from fip.libs.strategy_library.factor.definitions import FACTORS

from tests.unit.test_factor_compute import _input  # 复用夹具

TOLERANCE = Decimal("1e-10")


@pytest.mark.parametrize("factor_id", sorted(FACTORS))
def test_同一输入重算一致(factor_id):
    inp = _input(600, "0.0007")
    first = compute_factor(factor_id, inp)
    second = compute_factor(factor_id, inp)
    assert first.status is second.status
    assert first.reason == second.reason
    if first.value is None:
        assert second.value is None
    else:
        assert abs(first.value - second.value) < TOLERANCE


@pytest.mark.parametrize("factor_id", sorted(FACTORS))
def test_结果不随调用方的_decimal_上下文精度而变(factor_id):
    """compute_factor 必须自己用 localcontext 钉住精度。若它依赖全局上下文，
    一个把 prec 设成 9 的调用方就能让因子值悄悄变化。"""
    inp = _input(600, "0.0007")
    baseline = compute_factor(factor_id, inp)
    with decimal.localcontext() as ctx:
        ctx.prec = 9
        narrowed = compute_factor(factor_id, inp)
    if baseline.value is None:
        assert narrowed.value is None
    else:
        assert abs(baseline.value - narrowed.value) < TOLERANCE
```

先证伪的做法：把 `compute_factor` 里的 `with localcontext() as ctx: ctx.prec = ...`
临时删掉再跑，确认第二条测试变红，再恢复。

```bash
.venv/bin/pytest tests/unit/test_factor_reproducibility.py -q   # 预期 20 passed
```

- [ ] **Step 9: Metric Version 与因子清单登记入配置 + 钉死测试**

`config/strategy/metric/v1.yaml` 追加（**保留现有 `annualization` 与 `adjusted_nav` 两节**）：

```yaml
factor:
  return_basis:
    value: SIMPLE
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 —— 与年化/Sharpe 的行业惯例一致；对数收益不可横截面相加"
  volatility_ddof:
    value: 1
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 —— 样本标准差；文档未给"
  annualized_return_method:
    value: GEOMETRIC
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 —— (P_T/P_0)^(252/N) − 1"
  max_drawdown_basis:
    value: ADJUSTED_NAV
    status: DECIDED
    source: "Plan-2 设计定案 D-9 —— 回撤必须含分红再投资"
  win_rate_frequency:
    value: MONTHLY
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 —— 日频胜率接近 50% 无区分度"
  rolling_window_points:
    value: 252
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 rolling.window_days；单位为【净值点数】不是自然日"
  rolling_step_points:
    value: 21
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-9 rolling.step_days"
  rolling_return_aggregation:
    value: MEAN
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— D-9 公式表未给 F-RET-002 的聚合式，取窗口年化收益率均值"
  mar_daily_conversion:
    value: SIMPLE_DIVISION
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— MAR_daily = MAR_annual / 252；几何折算是另一口径"
  sharpe_risk_free_source:
    value: RISK_FREE_CURVE
    status: DECIDED
    source: "Plan-2 设计定案 D-9 —— 按 policy/evaluation 的 (curve_code, currency, tenor) 解析"
  min_obs_daily:
    value: 252
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-10 —— 上游 03-factor-definition 的缺省值本身标着 <TBD-FD-3>"
  min_obs_rolling:
    value: 504
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-10 —— 两个窗口"
  min_obs_monthly:
    value: 36
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-10 —— 单位是【月度收益数】不是交易日数"
  warning_obs_multiplier:
    value: 1.5
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-10 —— [min_obs, min_obs × 1.5) 落 WARNING"
  value_scale:
    value: 8
    status: DECIDED
    source: "= NavNumeric 的标度 NUMERIC(18, 8)；出口量化用 ROUND_HALF_UP 对齐 PostgreSQL"
```

`config/strategy/factor/v1.yaml`（新建，10 个因子的清单与 Factor Usage）：

```yaml
# 因子清单 v1 —— Owner: factor-service
# 全部条目为【补齐】：因子域的八份上游文档（02-factor-taxonomy /
# 03-factor-definition / 05-factor-normalization / 06-factor-versioning /
# 07-factor-validation / 08-factor-output …）在仓库中一份都不存在。
# 来源：docs/superpowers/specs/2026-09-02-plan2-factor-and-evaluation-design.md D-8。
# 拿到正式文档后【整体替换】本文件，不要逐条改。
scoring_factor_ids:
  value:
    - F-RET-001
    - F-RET-002
    - F-RISK-001
    - F-RISK-002
    - F-RISK-003
    - F-RAP-001
    - F-RAP-002
    - F-RAP-003
    - F-STAB-001
    - F-STAB-002
  status: PROVISIONAL
  source: "Plan-2 设计定案 D-8 —— 从 SCORING 清单扣除 REL 全类 / 费率 / VaR / Rolling 全家族后的 10 个"
excluded:
  rel_family:
    value: BENCHMARK_UNAVAILABLE
    status: DECIDED
    source: "Benchmark 四层建模推到 M2（spec §6.2）；REL 子分恒 UNAVAILABLE 是设计而非缺陷"
  fee:
    value: NO_DATA_SOURCE
    status: DECIDED
    source: "fund.fund_fee 表 Plan-1 建了但从未灌数 —— UNAVAILABLE，不得静默填 0"
  var_cvar:
    value: DISTRIBUTION_METHOD_UNDECIDED
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-8 —— 需先定历史法/参数法/Cornish-Fisher，推到 M2"
```

> `scoring_factor_ids` 的 `value` 是一个**列表**，不是映射——`platform/config/loader.py`
> 的叶子判定只拒绝 `value` 为 **dict** 的情形，列表可以通过。写实现前先跑
> `test_factor_config_loads` 确认这条假设成立；若加载器把它拒了，改为
> `f_ret_001.enabled` 这类逐项叶子，不要去放宽加载器。

钉死测试：

```python
# tests/unit/test_metric_config_pinning.py
"""配置与代码常量的一致性。

为什么需要它：strategy_library 是纯函数层，不能读 YAML（SDL-1），所以口径值在
代码里有一份。两份一旦分叉，配置会变成【看起来在治理、实际不生效】的摆设 ——
比没有配置更坏。Plan-1 的 DISCLOSURE_LAG_DAYS 用的是同一个模式。
"""

import pathlib

from fip.libs.strategy_library.factor import definitions as defs
from fip.libs.strategy_library.factor.status import WARNING_OBS_MULTIPLIER
from fip.platform.config.loader import load_config_file
from fip.platform.db.types import NavNumeric
from fip.platform.decision_data.context import RuntimeMode

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _metric():
    return load_config_file(
        ROOT / "config" / "strategy" / "metric" / "v1.yaml", RuntimeMode.BACKTEST
    )


def test_口径常量与_metric_配置逐条一致():
    cfg = _metric()
    assert cfg.get("annualization.trading_days_per_year") == defs.TRADING_DAYS_PER_YEAR
    assert cfg.get("factor.return_basis") == defs.RETURN_BASIS
    assert cfg.get("factor.volatility_ddof") == defs.VOLATILITY_DDOF
    assert cfg.get("factor.rolling_window_points") == defs.ROLLING_WINDOW_POINTS
    assert cfg.get("factor.rolling_step_points") == defs.ROLLING_STEP_POINTS
    assert cfg.get("factor.mar_daily_conversion") == defs.MAR_DAILY_CONVERSION
    assert cfg.get("factor.min_obs_daily") == defs.MIN_OBS_DAILY
    assert cfg.get("factor.min_obs_rolling") == defs.MIN_OBS_ROLLING
    assert cfg.get("factor.min_obs_monthly") == defs.MIN_OBS_MONTHLY
    assert str(cfg.get("factor.warning_obs_multiplier")) == str(WARNING_OBS_MULTIPLIER)
    assert cfg.get("factor.value_scale") == defs.VALUE_SCALE


def test_出口标度与_NavNumeric_一致():
    """factor_value.raw_value 是 NUMERIC(18, 8)。标度改了却没改这里，
    因子值会带着 8 位以上的计算噪声进库，可复现性对照随即分叉。"""
    assert defs.VALUE_SCALE == int(NavNumeric.scale or 0)


def test_因子清单与_factor_配置一致():
    cfg = load_config_file(
        ROOT / "config" / "strategy" / "factor" / "v1.yaml", RuntimeMode.BACKTEST
    )
    assert sorted(cfg.get("scoring_factor_ids")) == sorted(defs.FACTORS)


def test_全部补齐项都标了_PROVISIONAL():
    """G-14：【补齐】项必须标 PROVISIONAL 并指向设计定案文档。"""
    params = _metric().parameters
    for path in ("factor.return_basis", "factor.volatility_ddof",
                 "factor.rolling_return_aggregation", "factor.mar_daily_conversion",
                 "factor.min_obs_daily"):
        assert params[path].status.value == "PROVISIONAL", path
        assert "D-" in params[path].source or "补齐" in params[path].source, path
```

先跑确认失败（配置节尚未追加）：

```bash
.venv/bin/pytest tests/unit/test_metric_config_pinning.py -q
# 预期：KeyError: 配置项不存在：factor.return_basis
```

追加配置后：

```bash
.venv/bin/pytest tests/unit/test_metric_config_pinning.py -q   # 预期 4 passed
```

- [ ] **Step 10: 全量回归并提交**

```bash
.venv/bin/ruff check src tests
make typecheck
.venv/bin/pytest tests/unit tests/fitness -q
git add -A && git commit -m "feat(factor): 10 个因子的纯函数与 Metric Version 登记

kernel 与 compute_factor 两层：kernel 纯数学、可手算校对，compute_factor 做
依赖检查、status 判定与出口量化。Calmar 在 MDD=0、Sharpe 在 Volatility=0、
Sortino 在下行波动=0 时一律 UNAVAILABLE 且 value 为 None —— 不填 0、不填 inf（G-3）。
mar_policy 未配置时 F-RISK-002 / F-RAP-002 一律 UNAVAILABLE（G-6）。
D-9 未给 F-RET-002 的聚合式，补齐为窗口年化收益率均值（PROVISIONAL）。"
```

---

### Task 10: Threshold Resolver（R_f 的 PIT 解析 + MAR 三模式）

> **本任务包含一次灌数。** Plan-1 交接明确登记：「`ParsedYieldPoint` 没有生产调用方 ——
> `risk_free_rate` 的灌数属 Plan-2」。没有 R_f 行，`F-RAP-001` / `F-STAB-002` 会在
> 端到端链路上恒 `UNAVAILABLE`，而那看起来和「解析器写错了」一模一样。

**Files:**

- Create: `src/fip/libs/strategy_library/threshold/__init__.py`
- Create: `src/fip/libs/strategy_library/threshold/mar.py`
- Create: `src/fip/services/data_service/repositories/risk_free.py`
- Create: `src/fip/services/factor_service/thresholds.py`
- Modify: `src/fip/platform/decision_data/pit.py`
- Modify: `src/fip/services/data_service/adapters/akshare/parse.py`
- Modify: `src/fip/services/data_service/ingest.py`
- Modify: `src/fip/platform/cli.py`
- Modify: `config/policy/evaluation/v1.yaml`
- Test: `tests/unit/test_mar_policy.py`
- Test: `tests/unit/test_evaluation_config.py`
- Test: `tests/integration/test_ingest_risk_free_rate.py`
- Test: `tests/integration/test_risk_free_pit.py`

**Interfaces:**

*Consumes*：

```python
# Task 1 产出（H-1 的归位）—— 全平台唯一的 decision_at → available_at 翻译规则
PitDataContext.visible_until -> dt.datetime
# Plan-1 既有
from fip.services.data_service.adapters.akshare.parse import ParsedYieldPoint  # curve_code/effective_at/tenor/rate
from fip.services.data_service.models.market import RiskFreeRate               # PK(curve_code,currency,tenor,effective_at,version)
from fip.platform.source.availability import declared_lag_availability
from fip.libs.strategy_library.factor.status import UnavailableReason
```

*Produces*：

```python
# fip.platform.decision_data.pit（追加）
@dataclass(frozen=True, slots=True)
class RiskFreeRatePoint:
    effective_at: dt.date; rate: Decimal; version: int; availability_quality: str

@runtime_checkable
class RiskFreeRatePitRepository(Protocol):
    def latest_visible_rate(self, curve_code: str, currency: str, tenor: str
                            ) -> RiskFreeRatePoint | None: ...
    def rate_series(self, curve_code: str, currency: str, tenor: str,
                    date_from: dt.date, date_to: dt.date) -> list[RiskFreeRatePoint]: ...
PitDataContext.risk_free_rates() -> RiskFreeRatePitRepository

# fip.libs.strategy_library.threshold.mar（纯函数，不碰数据库）
class MarPolicy(StrEnum): ZERO = "ZERO"; FIXED = "FIXED"; RISK_FREE = "RISK_FREE"
@dataclass(frozen=True, slots=True)
class MarResolution:
    policy: MarPolicy | None
    annualized: Decimal | None                       # ZERO / FIXED：窗口内的标量
    series: tuple[tuple[dt.date, Decimal], ...] | None  # RISK_FREE：逐期序列
    unavailable_reason: str | None
def resolve_mar(policy_name: str | None, fixed_value: Decimal | None,
                risk_free_series: Sequence[tuple[dt.date, Decimal]] | None) -> MarResolution
def mar_for_factor_input(res: MarResolution) -> tuple[Decimal | None, str | None]

# fip.services.factor_service.thresholds（装配层，可以碰数据库）
@dataclass(frozen=True, slots=True)
class RiskFreeRateRef:
    curve_code: str; currency: str; tenor: str; version: int; rate_source_quality: str
@dataclass(frozen=True, slots=True)
class ResolvedThresholds:
    risk_free_rate: Decimal | None
    risk_free_rate_ref: RiskFreeRateRef | None
    mar: Decimal | None
    mar_unavailable_reason: str | None
    mar_policy: MarPolicy | None
class ThresholdResolver:
    def __init__(self, rates: RiskFreeRatePitRepository, config: ConfigSet) -> None
    def resolve(self, base_currency: str, date_from: dt.date, date_to: dt.date
                ) -> ResolvedThresholds

# fip.services.data_service.ingest（追加）
IngestService.ingest_risk_free_rate(self, start_date: str, end_date: str) -> int
```

---

- [ ] **Step 1: 先证伪 —— 现有 evaluation 配置里有一个被禁止的 MAR 兜底值**

`config/policy/evaluation/v1.yaml` 当前含：

```yaml
mar:
  default:
    value: 0.0
    status: PROVISIONAL
```

这正是 `FE:474` 逐字禁止的东西：「**`ZERO` 是「第一版推荐取值」，不是「不填时的兜底」**」。
一个叫 `mar.default` 的配置项，语义就是兜底。先写测试把它钉死：

```python
# tests/unit/test_evaluation_config.py
"""Evaluation Policy 配置的形状约束。

G-6：mar_policy 必填无默认。这条约束的落地形式是【配置里不得存在任何名为
default / fallback 的 MAR 项】—— 一次配置遗漏就会静默产出看起来完全正常的
Sortino，而没有任何信号表明这个值背后没有决策（FE:481）。
"""

import pathlib

import pytest

from fip.platform.config.loader import load_config_file
from fip.platform.decision_data.context import RuntimeMode

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _cfg():
    return load_config_file(
        ROOT / "config" / "policy" / "evaluation" / "v1.yaml", RuntimeMode.BACKTEST
    )


def test_不得存在_MAR_兜底项():
    paths = set(_cfg().parameters)
    forbidden = {p for p in paths if p.startswith("mar.") and (
        p.endswith(".default") or p.endswith(".fallback")
    )}
    assert not forbidden, f"MAR 不得有兜底值（FE:474 / G-6）：{sorted(forbidden)}"


def test_mar_policy_是显式配置项():
    """『显式配置为 ZERO』与『没配置所以当作 0』数值相同、含义相反。
    前者必须在配置里看得见。"""
    assert _cfg().get("mar.mar_policy") == "ZERO"


def test_FIXED_模式的取值在_ZERO_模式下不得存在():
    """mar_value 仅 CUSTOM/FIXED 模式必填（FE:454-460）。ZERO 模式下留着它，
    会让一次 mar_policy 的改动静默启用一个没人复核过的数值。"""
    assert "mar.fixed_value" not in _cfg().parameters


def test_Rf_解析键三件齐全():
    cfg = _cfg()
    assert cfg.get("risk_free_rate.curve_code") == "CN_TREASURY"
    assert cfg.get("risk_free_rate.currency") == "CNY"
    assert cfg.get("risk_free_rate.tenor") == "1Y"


def test_peer_group_粒度与最小样本量在同一配置源():
    """G-7：标准化 / 排名 / 分层三处必须同一配置源。"""
    cfg = _cfg()
    assert cfg.get("peer_group.classification_level") == "L1"
    assert cfg.get("peer_group.min_peer_group_size") == 30
```

```bash
.venv/bin/pytest tests/unit/test_evaluation_config.py -q
# 预期：test_不得存在_MAR_兜底项 FAILED（mar.default 存在）
#       其余四条 KeyError: 配置项不存在
```

- [ ] **Step 2: 改配置，跑通 Step 1**

`config/policy/evaluation/v1.yaml` 全文替换为：

```yaml
# Evaluation Policy v1 —— MAR、R_f 解析口径、Peer Group 粒度
# Owner: fund-service（01-system-architecture §8.2.1 第 1 子项）
#
# ⚠️ mar 段【没有】default —— 这是刻意的。FE:474：「ZERO 是第一版推荐取值，
# 不是不填时的兜底」。mar_policy 缺失时，依赖 MAR 的因子一律 UNAVAILABLE，
# 绝不回退成 0（G-6）。由 tests/unit/test_evaluation_config.py 钉住。
mar:
  mar_policy:
    value: ZERO
    status: PROVISIONAL
    source: "上游 FE:464-470 第一版推荐取值（已定案 2026-08-27）；本行是一次【显式决策】，不是默认值"
risk_free_rate:
  curve_code:
    value: CN_TREASURY
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— 中债三条曲线中唯一的无风险曲线；另两条（CN_MTN_AAA / CN_BANK_AAA）是信用债，实测 10Y 高约 30bp"
  currency:
    value: CNY
    status: PROVISIONAL
    source: "上游 TBD-18；与 fund_share_class.base_currency 取自同一字段（FR:116）"
  tenor:
    value: 1Y
    status: PROVISIONAL
    source: "上游 TBD-18 待投研与数据共同确定"
peer_group:
  classification_scheme:
    value: AKSHARE_FUND_TYPE
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-5 —— 数据供应商的商业分类，非投研资产类别体系"
  classification_level:
    value: L1
    status: PROVISIONAL
    source: "Plan-2 设计定案 D-7（IMP-TBD-2）—— L2 分组会大量触发 INSUFFICIENT_SAMPLE"
  min_peer_group_size:
    value: 30
    status: DECIDED
    source: "上游 FR:340 / BR:532 已定案 2026-08-27；判定基数是 n_effective 不是组规模"
```

```bash
.venv/bin/pytest tests/unit/test_evaluation_config.py -q   # 预期 5 passed
```

- [ ] **Step 3: MAR 三模式的失败测试**

```python
# tests/unit/test_mar_policy.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor.status import UnavailableReason
from fip.libs.strategy_library.threshold.mar import (
    MarPolicy,
    mar_for_factor_input,
    resolve_mar,
)

D = Decimal
RF = [(dt.date(2024, 1, 2), D("0.023")), (dt.date(2024, 1, 3), D("0.0231"))]


def test_未配置时不解析出任何数值():
    res = resolve_mar(None, None, RF)
    assert res.policy is None
    assert res.annualized is None and res.series is None
    assert res.unavailable_reason == UnavailableReason.MAR_NOT_CONFIGURED.value


def test_空串同样视为未配置():
    assert resolve_mar("", None, RF).unavailable_reason == (
        UnavailableReason.MAR_NOT_CONFIGURED.value
    )


def test_ZERO_模式解析为标量0():
    res = resolve_mar("ZERO", None, RF)
    assert res.policy is MarPolicy.ZERO
    assert res.annualized == D(0)
    assert res.series is None


def test_ZERO_与未配置的差别不在数值而在_status():
    """两者算出来的 MAR 都是 0，但一个有决策、一个没有。
    这条测试是 FE:481 的机器可读形式。"""
    configured = resolve_mar("ZERO", None, RF)
    missing = resolve_mar(None, None, RF)
    assert configured.annualized == D(0)
    assert missing.annualized is None
    assert configured.unavailable_reason is None


def test_FIXED_模式必须给值否则响亮失败():
    with pytest.raises(ValueError, match="FIXED"):
        resolve_mar("FIXED", None, RF)


def test_FIXED_模式解析为配置值():
    res = resolve_mar("FIXED", D("0.03"), RF)
    assert res.policy is MarPolicy.FIXED and res.annualized == D("0.03")


def test_RISK_FREE_模式解析为序列而不是标量():
    res = resolve_mar("RISK_FREE", None, RF)
    assert res.policy is MarPolicy.RISK_FREE
    assert res.annualized is None
    assert res.series == tuple(RF)


def test_RISK_FREE_模式在_Rf_缺失时不可解析():
    res = resolve_mar("RISK_FREE", None, [])
    assert res.series is None
    assert res.unavailable_reason == UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value


def test_未登记的模式名响亮失败():
    with pytest.raises(ValueError, match="mar_policy"):
        resolve_mar("AVERAGE_OF_PEERS", None, RF)


def test_序列型_MAR_不得塌陷成标量喂进_FactorInput():
    """契约的 FactorInput.mar 是 Decimal | None —— 一个标量装不下序列。
    取均值/首值/末值都是在伪造一个从未被决策的标尺（Plan-1 在
    adjusted_nav 标量列上的同一教训）。因此如实产出 UNAVAILABLE。"""
    value, reason = mar_for_factor_input(resolve_mar("RISK_FREE", None, RF))
    assert value is None
    assert reason == UnavailableReason.MAR_SERIES_NOT_SUPPORTED.value


def test_标量型_MAR_原样传出():
    assert mar_for_factor_input(resolve_mar("ZERO", None, RF)) == (D(0), None)
    assert mar_for_factor_input(resolve_mar("FIXED", D("0.03"), RF)) == (D("0.03"), None)
```

```bash
.venv/bin/pytest tests/unit/test_mar_policy.py -q
# 预期：ModuleNotFoundError: No module named 'fip.libs.strategy_library.threshold'
```

- [ ] **Step 4: 实现 MAR 三模式**

```python
# src/fip/libs/strategy_library/threshold/mar.py
"""MAR（Minimum Acceptable Return）解析。

MAR 是【评价标准】不是市场数据（FE:429）：即使数值等于 R_f 也必须独立建模，
否则评价标准的变更会伪装成数据更新而绕过版本治理（FE:747 / C-7）。
因此本模块与 R_f 的解析【不共用任何字段】，只在 RISK_FREE 模式下把 R_f
序列作为入参接进来。
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fip.libs.strategy_library.factor.status import UnavailableReason


class MarPolicy(StrEnum):
    """三模式（FE:464-468）。

    ⚠️ 命名分歧：上游把第三种模式称为 `CUSTOM`，本 Plan 的任务描述用的是
    `FIXED`。两者指同一件事（「配置一个固定数值」）。此处取 `FIXED`，并在
    落库时保持同名；若日后要与上游对齐，改的是这一个枚举值加一次数据迁移，
    不是一处散落的字符串。见本草案文末矛盾 ④。
    """

    ZERO = "ZERO"
    FIXED = "FIXED"
    RISK_FREE = "RISK_FREE"


@dataclass(frozen=True, slots=True)
class MarResolution:
    """解析结果。

    annualized 与 series 【互斥】：ZERO / FIXED 下 MAR 在窗口内是标量，
    RISK_FREE 下它是随时间变化的序列（FE:483-498）。把两者塞进同一个字段
    会让下游无法区分「MAR = 2.3%」与「MAR 恰好在这一天是 2.3%」。
    """

    policy: MarPolicy | None
    annualized: Decimal | None
    series: tuple[tuple[dt.date, Decimal], ...] | None
    unavailable_reason: str | None


def resolve_mar(
    policy_name: str | None,
    fixed_value: Decimal | None,
    risk_free_series: Sequence[tuple[dt.date, Decimal]] | None,
) -> MarResolution:
    """按 mar_policy 解析 MAR。

    policy_name 为 None 或空串 = 【未配置】→ 不解析出任何数值，
    reason = MAR_NOT_CONFIGURED。这与 policy_name == "ZERO" 数值相同、含义相反：
    前者是标尺从未被确认，后者是有人决定了标尺（FE:481）。**不得合并这两条分支。**

    未登记的模式名抛 ValueError 而不是回退到未配置：拼错 "ZER0" 若静默退化成
    「未配置」，看到的现象是「Sortino 全体 UNAVAILABLE」，与真的没配一模一样。
    """
    if not policy_name:
        return MarResolution(None, None, None,
                             UnavailableReason.MAR_NOT_CONFIGURED.value)
    try:
        policy = MarPolicy(policy_name)
    except ValueError:
        raise ValueError(
            f"未登记的 mar_policy：{policy_name!r}；合法值为 "
            f"{[p.value for p in MarPolicy]}"
        ) from None

    if policy is MarPolicy.ZERO:
        return MarResolution(policy, Decimal(0), None, None)

    if policy is MarPolicy.FIXED:
        if fixed_value is None:
            raise ValueError("mar_policy = FIXED 时 mar.fixed_value 必填（FE:456）")
        return MarResolution(policy, fixed_value, None, None)

    if not risk_free_series:
        return MarResolution(policy, None, None,
                             UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value)
    return MarResolution(policy, None, tuple(risk_free_series), None)


def mar_for_factor_input(res: MarResolution) -> tuple[Decimal | None, str | None]:
    """把解析结果压成契约 FactorInput.mar 能接的形状。

    ⚠️ RISK_FREE 模式在这里【必然】退化为不可用：契约的 FactorInput.mar 是
    `Decimal | None`，一个标量装不下一条序列。取均值 / 首值 / 末值都是在伪造
    一个从未被任何人决策过的标尺 —— 与 Plan-1 在 adjusted_nav 标量列上的教训
    完全同型（标量副本装不下二元函数）。因此如实返回 UNAVAILABLE。

    这是**接口契约的缺口**而不是本模块的取舍：要真正支持 RISK_FREE，
    必须给 FactorInput 增加一个逐期 MAR 序列字段。见本草案文末矛盾 ①。
    """
    if res.unavailable_reason is not None:
        return None, res.unavailable_reason
    if res.series is not None:
        return None, UnavailableReason.MAR_SERIES_NOT_SUPPORTED.value
    return res.annualized, None
```

```bash
.venv/bin/pytest tests/unit/test_mar_policy.py -q   # 预期 11 passed
```

- [ ] **Step 5: R_f 灌数的失败测试**

```python
# tests/integration/test_ingest_risk_free_rate.py
import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.market import RiskFreeRate
from fip.platform.source.port import SourceRecord

pytestmark = pytest.mark.integration

FRAME = pd.DataFrame([
    {"曲线名称": "中债国债收益率曲线", "日期": dt.date(2024, 1, 2),
     "3月": 2.10, "6月": 2.15, "1年": 2.30, "3年": 2.40, "5年": 2.50,
     "7年": 2.55, "10年": 2.5601, "30年": 3.00},
    {"曲线名称": "中债中短期票据收益率曲线(AAA)", "日期": dt.date(2024, 1, 2),
     "3月": 2.64, "6月": 2.70, "1年": 2.80, "3年": 2.90, "5年": 3.00,
     "7年": 3.02, "10年": 3.0482, "30年": 3.40},
])


class _StubAdapter:
    provider_code = "AKSHARE"
    adapter_version = "1"

    def fetch(self, dataset, **params):
        buffer = io.BytesIO()
        FRAME.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset, payload=buffer.getvalue(), row_count=len(FRAME),
            ingested_at=dt.datetime(2026, 9, 2, tzinfo=dt.UTC),
            request_params={k: str(v) for k, v in params.items()},
            published_at=None, provider_available_at=None,
        )


def _service(db_session):
    return IngestService(db_session, _StubAdapter(), disclosure_lag_days=1)


def test_灌入后每条曲线的每个期限各成一行(db_session):
    inserted = _service(db_session).ingest_risk_free_rate("20240102", "20240102")
    assert inserted == 16          # 2 条曲线 × 8 个期限
    treasury = db_session.query(RiskFreeRate).filter_by(
        curve_code="CN_TREASURY", tenor="1Y"
    ).one()
    assert treasury.rate == Decimal("0.02300000")   # 2.30% → 小数
    assert treasury.currency == "CNY"


def test_三个时间来源如实留空_质量为_INFERRED(db_session):
    """C-12 / G-15：AKShare 给不出披露时刻，另两列必须保持 NULL。"""
    _service(db_session).ingest_risk_free_rate("20240102", "20240102")
    row = db_session.query(RiskFreeRate).filter_by(
        curve_code="CN_TREASURY", tenor="1Y"
    ).one()
    assert row.published_at is None and row.provider_available_at is None
    assert row.availability_quality == "INFERRED"
    assert row.available_at == dt.datetime(2024, 1, 3, tzinfo=dt.UTC)


def test_值未变时重跑不产生新版本(db_session):
    service = _service(db_session)
    service.ingest_risk_free_rate("20240102", "20240102")
    assert service.ingest_risk_free_rate("20240102", "20240102") == 0


def test_国债曲线缺席时响亮失败(db_session, monkeypatch):
    """Plan-1 交接登记的缺口：未登记的曲线名被静默跳过，只有『一条都认不出来』
    才报错。若上游只给国债曲线改名，R_f 会静默消失而信用债曲线照常入库 ——
    下游算出来的 Sharpe 用的是信用债收益率，不报错、不告警。"""
    only_credit = FRAME[FRAME["曲线名称"] != "中债国债收益率曲线"]

    class _CreditOnly(_StubAdapter):
        def fetch(self, dataset, **params):
            buffer = io.BytesIO()
            only_credit.to_parquet(buffer, index=False)
            return SourceRecord(
                dataset=dataset, payload=buffer.getvalue(), row_count=len(only_credit),
                ingested_at=dt.datetime(2026, 9, 2, tzinfo=dt.UTC),
                request_params={}, published_at=None, provider_available_at=None,
            )

    with pytest.raises(ValueError, match="CN_TREASURY"):
        IngestService(db_session, _CreditOnly(), 1).ingest_risk_free_rate(
            "20240102", "20240102"
        )
```

```bash
.venv/bin/pytest tests/integration/test_ingest_risk_free_rate.py -q -m integration
# 预期：AttributeError: 'IngestService' object has no attribute 'ingest_risk_free_rate'
```

- [ ] **Step 6: 实现 R_f 灌数**

先在 `parse.py` 里补曲线 → 币种映射（币种是 `RiskFreeRate` 主键的一部分，
而 `ParsedYieldPoint` 不带它 —— 这个空档必须在适配器层补上，不能让 ingest 现编）：

```python
# src/fip/services/data_service/adapters/akshare/parse.py（追加在 _CURVE_CODES 之后）

# 曲线 → 计价币种。RiskFreeRate 的主键是 (curve_code, currency, tenor,
# effective_at, version)，而 ParsedYieldPoint 【不带 currency】——中债的三条
# 曲线全部是人民币曲线，这个事实属于「这条曲线是什么」，因此登记在适配器层。
# 不放在 ingest 里现填：那等于让灌数编排去猜一条曲线的币种。
CURVE_CURRENCIES: dict[str, str] = {
    "CN_TREASURY": "CNY",
    "CN_MTN_AAA": "CNY",
    "CN_BANK_AAA": "CNY",
}

# 无风险曲线的唯一取值。灌数编排断言它必须出现 —— 见 IngestService
# .ingest_risk_free_rate 的说明。
RISK_FREE_CURVE_CODE = "CN_TREASURY"
```

再在 `ingest.py` 里加灌数方法（并把 `_next_version` 的类型标注放宽到含 `RiskFreeRate`）：

```python
# src/fip/services/data_service/ingest.py（追加 import 与方法）
from fip.services.data_service.adapters.akshare.parse import (
    CURVE_CURRENCIES,
    RISK_FREE_CURVE_CODE,
    parse_yield_curve_frame,
)
from fip.services.data_service.models.market import FundDistribution, FundNav, RiskFreeRate

    def ingest_risk_free_rate(self, start_date: str, end_date: str) -> int:
        """灌入中债收益率曲线。

        available_at 由【声明的披露时滞】推导，质量恒为 INFERRED —— 与净值同一
        条规则（C-12：published_at / provider_available_at 拿不到就留 NULL，
        绝不回填）。

        为什么要断言 CN_TREASURY 存在：parse_yield_curve_frame 对未登记的曲线名
        【静默跳过】，只有一条都认不出来才报错。若上游只把国债曲线改了名，
        本次灌数会「成功」写入两条信用债曲线，而 R_f 表里没有任何国债行 ——
        下游 Sharpe 会解析不到 R_f 而全体 UNAVAILABLE，现象与「还没灌数」
        完全一致，要到排查很久之后才会发现是曲线改名。
        """
        record = self._adapter.fetch(
            "risk_free_rate", start_date=start_date, end_date=end_date
        )
        payload = self._store_raw(record)
        parsed = parse_yield_curve_frame(record.payload)
        if not any(p.curve_code == RISK_FREE_CURVE_CODE for p in parsed):
            raise ValueError(
                f"本批 {start_date}~{end_date} 的收益率曲线里没有 "
                f"{RISK_FREE_CURVE_CODE} —— 上游很可能改了国债曲线的名称。"
                "不要在这里放行：R_f 缺失与曲线改名的现象完全一致。"
            )

        inserted = 0
        for point in parsed:
            currency = CURVE_CURRENCIES[point.curve_code]
            keys = {
                "curve_code": point.curve_code,
                "currency": currency,
                "tenor": point.tenor,
                "effective_at": point.effective_at,
            }
            latest = self._session.execute(
                select(RiskFreeRate)
                .filter_by(**keys)
                .order_by(RiskFreeRate.version.desc())
                .limit(1)
            ).scalars().first()
            if latest is not None and latest.rate == point.rate:
                continue    # 值未变，不产生新版本（与 ingest_nav 同一条规则）
            self._session.add(RiskFreeRate(
                **keys,
                version=self._next_version(RiskFreeRate, **keys),
                rate=point.rate,
                raw_payload_id=payload.id,
                **self._times(point.effective_at, record.ingested_at),
            ))
            inserted += 1
        self._session.flush()
        return inserted
```

`datasets.py` 已声明 `risk_free_rate` 数据集与列契约，无需改动。

```bash
.venv/bin/pytest tests/integration/test_ingest_risk_free_rate.py -q -m integration
# 预期 4 passed
```

- [ ] **Step 7: R_f 的 PIT 解析端口与实现（失败测试先行）**

```python
# tests/integration/test_risk_free_pit.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext, RecomputeScope, RuntimeMode, TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.models.market import RiskFreeRate

pytestmark = pytest.mark.integration


def _row(day, rate, version=1, available_offset_days=1):
    return RiskFreeRate(
        curve_code="CN_TREASURY", currency="CNY", tenor="1Y",
        effective_at=day, version=version, rate=Decimal(rate),
        available_at=dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC)
        + dt.timedelta(days=available_offset_days),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 9, 2, tzinfo=dt.UTC),
    )


def _ctx(session, decision_at):
    return PitDataContext(
        DecisionExecutionContext(
            decision_id=f"T-{decision_at}", decision_at=decision_at,
            data_as_of=decision_at, strategy_version="test",
            runtime_mode=RuntimeMode.BACKTEST, trigger_type=TriggerType.MANUAL,
            recompute_scope=RecomputeScope.NONE,
        ),
        session,
    )


def test_只看得见_available_at_不晚于_decision_at_的行(db_session):
    """G-1：available_at <= decision_at 是唯一可见性规则。
    effective_at <= decision_at 是错的 —— 它会让一条 1-10 生效、1-15 才披露的
    利率在 1-12 就被看到（静默前视偏差）。"""
    db_session.add_all([
        _row(dt.date(2024, 1, 10), "0.023", available_offset_days=5),
        _row(dt.date(2024, 1, 8), "0.022"),
    ])
    db_session.flush()
    repo = _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates()
    point = repo.latest_visible_rate("CN_TREASURY", "CNY", "1Y")
    assert point is not None
    assert point.effective_at == dt.date(2024, 1, 8)   # 不是 1-10


def test_同一生效日取可见的最大_version(db_session):
    day = dt.date(2024, 1, 8)
    db_session.add_all([_row(day, "0.022", 1), _row(day, "0.0225", 2)])
    db_session.flush()
    repo = _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates()
    point = repo.latest_visible_rate("CN_TREASURY", "CNY", "1Y")
    assert point.rate == Decimal("0.02250000") and point.version == 2


def test_无可见行时返回_None_不返回0(db_session):
    """FE:656：R_f 不可得 → Sharpe UNAVAILABLE，【不得默认 R_f = 0】。"""
    db_session.add(_row(dt.date(2024, 1, 8), "0.022", available_offset_days=30))
    db_session.flush()
    repo = _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates()
    assert repo.latest_visible_rate("CN_TREASURY", "CNY", "1Y") is None


def test_曲线码是解析键的一部分(db_session):
    """三条曲线的同一个 (日期, 期限) 不得混淆 —— 实测信用债 10Y 高约 30bp。"""
    day = dt.date(2024, 1, 8)
    treasury = _row(day, "0.022")
    credit = _row(day, "0.028")
    credit.curve_code = "CN_MTN_AAA"
    db_session.add_all([treasury, credit])
    db_session.flush()
    repo = _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates()
    assert repo.latest_visible_rate("CN_TREASURY", "CNY", "1Y").rate == Decimal("0.02200000")
    assert repo.latest_visible_rate("CN_MTN_AAA", "CNY", "1Y").rate == Decimal("0.02800000")


def test_序列查询按生效日升序且逐日取最大可见_version(db_session):
    db_session.add_all([
        _row(dt.date(2024, 1, 8), "0.022", 1),
        _row(dt.date(2024, 1, 8), "0.0225", 2),
        _row(dt.date(2024, 1, 9), "0.023", 1),
    ])
    db_session.flush()
    repo = _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates()
    series = repo.rate_series(
        "CN_TREASURY", "CNY", "1Y", dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    )
    assert [(p.effective_at, p.rate) for p in series] == [
        (dt.date(2024, 1, 8), Decimal("0.02250000")),
        (dt.date(2024, 1, 9), Decimal("0.02300000")),
    ]
```

```bash
.venv/bin/pytest tests/integration/test_risk_free_pit.py -q -m integration
# 预期：AttributeError: 'PitDataContext' object has no attribute 'risk_free_rates'
```

实现：

```python
# src/fip/platform/decision_data/pit.py（追加）

@dataclass(frozen=True, slots=True)
class RiskFreeRatePoint:
    effective_at: dt.date
    rate: Decimal
    version: int
    availability_quality: str


@runtime_checkable
class RiskFreeRatePitRepository(Protocol):
    """时点感知的无风险利率访问。

    与 NavPitRepository 同一形状：decision_at 在构造期绑定，方法签名里没有
    时点参数（PIT-A2）。`latest_visible_rate` 不是 PIT-A3 禁止的『取最新一条』
    —— 它取的是【截至 decision_at 可见的】最新一条，时点条件无法被调用方省略。
    """

    def latest_visible_rate(
        self, curve_code: str, currency: str, tenor: str
    ) -> RiskFreeRatePoint | None: ...

    def rate_series(
        self, curve_code: str, currency: str, tenor: str,
        date_from: dt.date, date_to: dt.date,
    ) -> list[RiskFreeRatePoint]: ...


# PitDataContext 内追加：
    def risk_free_rates(self) -> RiskFreeRatePitRepository:
        # 延迟 import：与 navs() 同理，模块级 import 会让 platform 层依赖
        # services 层，反转架构规定的依赖方向。
        from fip.services.data_service.repositories.risk_free import (
            SqlRiskFreeRatePitRepository,
        )

        return SqlRiskFreeRatePitRepository(
            session=self._session, visible_until=self.visible_until
        )
```

```python
# src/fip/services/data_service/repositories/risk_free.py
"""R_f 的 PIT 访问。

版本解析与净值完全同一条规则：对每个 effective_at，在 available_at <=
decision_at 的行中取 version 最大者。差别只在业务键是
(curve_code, currency, tenor) 而不是 share_class_id。
"""

import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import RiskFreeRatePoint

_LATEST_SQL = text("""
    SELECT effective_at, rate, version, availability_quality
    FROM market.risk_free_rate
    WHERE curve_code = :curve_code
      AND currency = :currency
      AND tenor = :tenor
      AND available_at <= :visible_until
    ORDER BY effective_at DESC, version DESC
    LIMIT 1
""")

_SERIES_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, rate, version, availability_quality
    FROM market.risk_free_rate
    WHERE curve_code = :curve_code
      AND currency = :currency
      AND tenor = :tenor
      AND available_at <= :visible_until
      AND effective_at BETWEEN :date_from AND :date_to
    ORDER BY effective_at, version DESC
""")


class SqlRiskFreeRatePitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        # visible_until 由 PitDataContext 统一翻译（H-1）。这里【不】自己
        # 再写一遍 dt.datetime.combine(decision_at, time.max) —— 那正是
        # Plan-1 交接点名的「翻译规则被复制成多份」的第三份拷贝。
        self._visible_until = visible_until

    def _params(self, curve_code: str, currency: str, tenor: str) -> dict[str, object]:
        return {
            "curve_code": curve_code, "currency": currency, "tenor": tenor,
            "visible_until": self._visible_until,
        }

    def latest_visible_rate(
        self, curve_code: str, currency: str, tenor: str
    ) -> RiskFreeRatePoint | None:
        row = self._session.execute(
            _LATEST_SQL, self._params(curve_code, currency, tenor)
        ).mappings().first()
        if row is None:
            # 【不得】回退成 0（FE:656）。返回 None，由调用方记成 UNAVAILABLE。
            return None
        return RiskFreeRatePoint(
            row["effective_at"], row["rate"], row["version"],
            row["availability_quality"],
        )

    def rate_series(
        self, curve_code: str, currency: str, tenor: str,
        date_from: dt.date, date_to: dt.date,
    ) -> list[RiskFreeRatePoint]:
        params = self._params(curve_code, currency, tenor)
        params.update({"date_from": date_from, "date_to": date_to})
        return [
            RiskFreeRatePoint(
                r["effective_at"], r["rate"], r["version"], r["availability_quality"]
            )
            for r in self._session.execute(_SERIES_SQL, params).mappings().all()
        ]
```

```bash
.venv/bin/pytest tests/integration/test_risk_free_pit.py -q -m integration   # 预期 5 passed
```

- [ ] **Step 8: `ThresholdResolver` 装配 + 溯源留痕**

```python
# src/fip/services/factor_service/thresholds.py
"""Threshold Resolver —— 把 Evaluation Policy 与 PIT 数据解析成因子计算的两个阈值。

分层：R_f 的解析要碰数据库，属 service 层；MAR 的政策逻辑是纯函数，
住在 libs/strategy_library/threshold/mar.py。两者【不共用字段】（C-7）。
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from fip.libs.strategy_library.threshold.mar import (
    MarPolicy,
    mar_for_factor_input,
    resolve_mar,
)
from fip.platform.config.loader import ConfigSet
from fip.platform.decision_data.pit import RiskFreeRatePitRepository


@dataclass(frozen=True, slots=True)
class RiskFreeRateRef:
    """factor_value.risk_free_rate_ref 的溯源内容。

    上游（04-database-design §9.2.1）要求四个字段：currency / tenor / version /
    rate_source_quality。**本 Plan 补第五个 curve_code** —— Plan-1 的
    RiskFreeRate 主键第一列就是它，中债同一天有国债 / 中短期票据AAA /
    商业银行普通债AAA 三条曲线，缺了它，溯源无法回答「这个 Sharpe 用的是
    哪条曲线」。上游的四字段清单成文时还没有 curve_code 这个维度。

    version 记的是【解析基准】（截至 decision_at 的可见版本），不是窗口内
    每一期的 version 列表（04-database-design §9.2.1）。
    """

    curve_code: str
    currency: str
    tenor: str
    version: int
    rate_source_quality: str


@dataclass(frozen=True, slots=True)
class ResolvedThresholds:
    risk_free_rate: Decimal | None
    risk_free_rate_ref: RiskFreeRateRef | None
    mar: Decimal | None
    mar_unavailable_reason: str | None
    mar_policy: MarPolicy | None


class ThresholdResolver:
    def __init__(self, rates: RiskFreeRatePitRepository, config: ConfigSet) -> None:
        self._rates = rates
        self._config = config

    def resolve(
        self, base_currency: str, date_from: dt.date, date_to: dt.date
    ) -> ResolvedThresholds:
        """解析某只基金在本次决策下的 R_f 与 MAR。

        base_currency 由调用方从 fund_share_class.base_currency 取，
        **与 Peer Group 的划分维度取自同一字段**（FR:116）—— 否则会出现
        「按 A 币种分组、按 B 币种解析利率」的错配。因此这里【不】读配置里的
        risk_free_rate.currency 作为解析键，只用它做一致性校验。
        """
        configured_currency = str(self._config.get("risk_free_rate.currency"))
        if base_currency != configured_currency:
            raise ValueError(
                f"基金计价币种 {base_currency} 与 Evaluation Policy 的 R_f 币种 "
                f"{configured_currency} 不一致 —— M1 只登记了一条 {configured_currency} "
                "曲线，静默按配置币种解析会产生跨币种的 Sharpe"
            )
        curve_code = str(self._config.get("risk_free_rate.curve_code"))
        tenor = str(self._config.get("risk_free_rate.tenor"))

        point = self._rates.latest_visible_rate(curve_code, base_currency, tenor)
        rf = point.rate if point is not None else None
        ref = (
            RiskFreeRateRef(curve_code, base_currency, tenor, point.version,
                            point.availability_quality)
            if point is not None else None
        )

        try:
            policy_name = str(self._config.get("mar.mar_policy"))
        except KeyError:
            # 【关键】配置项缺失不是异常路径而是业务路径：mar_policy 无默认，
            # 缺失时依赖 MAR 的因子一律 UNAVAILABLE（G-6）。这里绝不填 ZERO。
            policy_name = ""
        try:
            fixed_value = Decimal(str(self._config.get("mar.fixed_value")))
        except KeyError:
            fixed_value = None

        rf_series = (
            [(p.effective_at, p.rate)
             for p in self._rates.rate_series(
                 curve_code, base_currency, tenor, date_from, date_to)]
            if policy_name == MarPolicy.RISK_FREE.value else None
        )
        mar_resolution = resolve_mar(policy_name or None, fixed_value, rf_series)
        mar_value, mar_reason = mar_for_factor_input(mar_resolution)

        return ResolvedThresholds(
            risk_free_rate=rf, risk_free_rate_ref=ref,
            mar=mar_value, mar_unavailable_reason=mar_reason,
            mar_policy=mar_resolution.policy,
        )
```

追加两条集成断言到 `tests/integration/test_risk_free_pit.py`：

```python
def test_解析器在_mar_policy_缺失时不填_ZERO(db_session, tmp_path):
    """G-6 的端到端形式。"""
    from fip.platform.config.loader import load_config_file
    from fip.platform.decision_data.context import RuntimeMode
    from fip.services.factor_service.thresholds import ThresholdResolver

    cfg_file = tmp_path / "v1.yaml"
    cfg_file.write_text(
        "risk_free_rate:\n"
        "  curve_code: {value: CN_TREASURY, status: DECIDED, source: test}\n"
        "  currency: {value: CNY, status: DECIDED, source: test}\n"
        "  tenor: {value: 1Y, status: DECIDED, source: test}\n",
        encoding="utf-8",
    )
    db_session.add(_row(dt.date(2024, 1, 8), "0.022"))
    db_session.flush()
    resolver = ThresholdResolver(
        _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates(),
        load_config_file(cfg_file, RuntimeMode.BACKTEST),
    )
    resolved = resolver.resolve("CNY", dt.date(2024, 1, 1), dt.date(2024, 1, 31))
    assert resolved.risk_free_rate == Decimal("0.02200000")
    assert resolved.mar is None
    assert resolved.mar_unavailable_reason == "MAR_NOT_CONFIGURED"


def test_溯源引用带曲线码与质量(db_session):
    from fip.platform.config.loader import load_config_file
    from fip.platform.decision_data.context import RuntimeMode
    from fip.services.factor_service.thresholds import ThresholdResolver
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    db_session.add(_row(dt.date(2024, 1, 8), "0.022"))
    db_session.flush()
    resolver = ThresholdResolver(
        _ctx(db_session, dt.date(2024, 1, 12)).risk_free_rates(),
        load_config_file(
            root / "config" / "policy" / "evaluation" / "v1.yaml",
            RuntimeMode.BACKTEST,
        ),
    )
    ref = resolver.resolve("CNY", dt.date(2024, 1, 1), dt.date(2024, 1, 31)).risk_free_rate_ref
    assert (ref.curve_code, ref.currency, ref.tenor) == ("CN_TREASURY", "CNY", "1Y")
    assert ref.version == 1 and ref.rate_source_quality == "INFERRED"
```

- [ ] **Step 9: CLI 接上灌数命令，全量回归并提交**

```python
# src/fip/platform/cli.py（追加）
def cmd_ingest_rates(args: argparse.Namespace) -> None:
    with _session() as session:
        inserted = _service(session).ingest_risk_free_rate(args.date_from, args.date_to)
        session.commit()
    print(f"无风险利率 {inserted} 行")


# main() 内追加：
    p_rates = sub.add_parser("ingest-rates", help="灌入中债收益率曲线（R_f 的来源）")
    p_rates.add_argument("--from", required=True, dest="date_from", help="YYYYMMDD")
    p_rates.add_argument("--to", required=True, dest="date_to", help="YYYYMMDD")
    p_rates.set_defaults(func=cmd_ingest_rates)
```

```bash
.venv/bin/ruff check src tests && make typecheck
.venv/bin/pytest tests/unit tests/fitness -q
.venv/bin/pytest tests/integration -q -m integration
git add -A && git commit -m "feat(threshold): R_f 的 PIT 解析与灌数 + MAR 三模式

R_f 走 (curve_code, currency, tenor) 三键 + available_at <= decision_at 解析，
不可得时返回 None，绝不默认 R_f = 0。灌数断言 CN_TREASURY 必须出现 ——
上游只给国债曲线改名会让 R_f 静默消失而信用债照常入库。
MAR 与 R_f 不共用任何字段（C-7）；mar_policy 未配置 → MAR_NOT_CONFIGURED，
不回退 ZERO（G-6）。RISK_FREE 模式产出序列，契约的标量 FactorInput.mar
装不下它，如实产出 MAR_SERIES_NOT_SUPPORTED 而非塌陷取值。
删除 config/policy/evaluation 里被禁止的 mar.default 兜底项。"
```

---

### Task 11: Peer Group 构建 + B1 快照原子写入

**Files:**

- Create: `db/migrations/versions/0018_share_class_base_currency.py`
- Create: `src/fip/libs/strategy_library/peer_group/__init__.py`
- Create: `src/fip/libs/strategy_library/peer_group/build.py`
- Create: `src/fip/services/data_service/repositories/classification.py`
- Create: `src/fip/services/fund_service/peer_group_writer.py`
- Modify: `src/fip/services/data_service/models/fund.py`
- Modify: `src/fip/services/data_service/ingest.py`
- Modify: `src/fip/platform/decision_data/pit.py`
- Modify: `tests/fitness/test_architecture.py`
- Modify: `tests/integration/check_constraints.snapshot`
- Test: `tests/unit/test_peer_group_build.py`
- Test: `tests/integration/test_peer_group_snapshot.py`

**Interfaces:**

*Consumes*：

```python
from fip.services.data_service.models.fund import FundClassificationHistory, FundShareClass
from fip.services.data_service.models.evaluation import PeerGroupSnapshot, PeerGroupMember  # Task 8 产出
PitDataContext.visible_until -> dt.datetime      # Task 1
```

*Produces*：

```python
# fip.libs.strategy_library.peer_group.build（纯函数；G-5：不得 import 评分 / Universe）
UNCLASSIFIED: str = "UNCLASSIFIED"
class ClassificationLevel(StrEnum): L1 = "L1"; L2 = "L2"
class ExclusionReason(StrEnum):
    UNCLASSIFIED_CODE = "UNCLASSIFIED_CODE"
    CLASSIFICATION_MISSING = "CLASSIFICATION_MISSING"
    CURRENCY_UNKNOWN = "CURRENCY_UNKNOWN"
@dataclass(frozen=True, slots=True)
class PeerGroupKey:                    # 契约原文
    classification_scheme: str; classification_code: str; base_currency: str
    def key_string(self) -> str        # = f"{scheme}|{code}|{currency}"，落 classification_key
@dataclass(frozen=True, slots=True)
class PeerGroupCandidate:
    share_class_id: int; classification_scheme: str | None
    classification_code: str | None; classification_history_id: int | None
    base_currency: str | None
@dataclass(frozen=True, slots=True)
class ExcludedCandidate:
    share_class_id: int; reason: ExclusionReason
@dataclass(frozen=True, slots=True)
class PeerGroupBuild:
    groups: tuple[tuple[PeerGroupKey, tuple[int, ...]], ...]
    excluded: tuple[ExcludedCandidate, ...]
    classification_history_ids: tuple[int, ...]     # 「所用分类版本」（FR-PEER-001 Output）
def derive_classification_code(code: str, level: ClassificationLevel) -> str
def build_peer_groups(candidates, level) -> PeerGroupBuild

# fip.services.data_service.repositories.classification
@dataclass(frozen=True, slots=True)
class ClassificationPoint:
    share_class_id: int; classification_scheme: str; classification_code: str
    history_id: int; base_currency: str | None
class SqlClassificationPitRepository:
    def candidates_as_of(self, effective_at: dt.date) -> list[PeerGroupCandidate]

# fip.services.fund_service.peer_group_writer
class PeerGroupSnapshotWriter:
    def __init__(self, session: Session) -> None
    def write_b1(self, effective_at: dt.date, build: PeerGroupBuild) -> dict[str, int]
```

---

- [ ] **Step 1: 先证伪 —— `fund_share_class` 根本没有 `base_currency` 列**

`FR:105` 把 `Currency` 定为 Peer Group 的**强制**划分维度，`FR:116` 进一步要求它与
R_f 解析键的 `currency` **取自同一字段 `fund_share_class.base_currency`**。
Plan-1 落地的 `FundShareClass` 只有 `id / fund_id / share_class_code / display_name /
inception_date / created_at / updated_at` —— **这一列不存在**。

```python
# tests/integration/test_peer_group_snapshot.py（第一条）
import datetime as dt

import pytest

from fip.services.data_service.models.fund import FundShareClass

pytestmark = pytest.mark.integration


def test_份额类别带计价币种与其来源(db_session, fund_fixture):
    """FR:116 —— Peer Group 的划分维度与 R_f 的解析键必须取自同一字段。
    没有这一列，两者只能各自现编，就会出现「按 A 币种分组、按 B 币种解析利率」。"""
    row = db_session.get(FundShareClass, fund_fixture.share_class_id)
    assert row.base_currency == "CNY"
    assert row.base_currency_source == "PROVIDER_SCOPE_DECLARED"
```

```bash
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration
# 预期：AttributeError: type object 'FundShareClass' has no attribute 'base_currency'
```

- [ ] **Step 2: 迁移 0018 + ORM + 灌数时如实写入来源**

```python
# db/migrations/versions/0018_share_class_base_currency.py
"""份额类别的计价币种

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"


def upgrade() -> None:
    # 两列都可空：AKShare 的 fund_name_em 【不提供】币种。写死 'CNY' 作为
    # NOT NULL 的 server_default 等于伪造数据（C-12 同型）。取而代之：
    # 由一条【声明的推导规则】填值，并把规则本身写进 base_currency_source，
    # 与 declared_lag_availability 让 available_at 恒为 INFERRED 是同一手法。
    op.add_column("fund_share_class",
                  sa.Column("base_currency", sa.String(8), nullable=True),
                  schema="fund")
    op.add_column("fund_share_class",
                  sa.Column("base_currency_source", sa.String(32), nullable=True),
                  schema="fund")
    op.create_check_constraint(
        "ck_share_class_currency_source",
        "fund_share_class",
        "(base_currency IS NULL AND base_currency_source IS NULL) OR "
        "(base_currency IS NOT NULL AND base_currency_source IS NOT NULL)",
        schema="fund",
    )


def downgrade() -> None:
    op.drop_constraint("ck_share_class_currency_source", "fund_share_class",
                       schema="fund", type_="check")
    op.drop_column("fund_share_class", "base_currency_source", schema="fund")
    op.drop_column("fund_share_class", "base_currency", schema="fund")
```

```python
# src/fip/services/data_service/models/fund.py（FundShareClass 内追加）
    # G-16：迁移里建的约束必须【同时】在 ORM 声明，否则 autogenerate 会生成
    # 一条 DROP。__table_args__ 追加：
    #   CheckConstraint(
    #       "(base_currency IS NULL AND base_currency_source IS NULL) OR "
    #       "(base_currency IS NOT NULL AND base_currency_source IS NOT NULL)",
    #       name="ck_share_class_currency_source",
    #   ),
    base_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # 币种的【来源】必须与币种同在。只有值没有来源时，无法区分
    # 「供应商告诉我们是 CNY」与「我们假定它是 CNY」——后者在引入第二个
    # provider 或第一只外币份额时会静默出错。
    base_currency_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

```python
# src/fip/services/data_service/ingest.py（ingest_fund_list 内，新建 FundShareClass 时）
# AKShare 的 fund_name_em 覆盖范围是中国大陆公募，全部以人民币计价与申赎。
# 这是一条【声明的推导规则】，不是从数据里读到的事实 —— 因此 source 记为
# PROVIDER_SCOPE_DECLARED 而不是 PROVIDER_REPORTED。引入第二个 provider 或
# 第一只外币计价份额之前，必须把它换成真实字段。
BASE_CURRENCY_BY_PROVIDER_SCOPE = {"AKSHARE": ("CNY", "PROVIDER_SCOPE_DECLARED")}
...
currency, currency_source = BASE_CURRENCY_BY_PROVIDER_SCOPE[self._adapter.provider_code]
share_class = FundShareClass(
    ..., base_currency=currency, base_currency_source=currency_source
)
```

重新生成 CHECK 黄金快照（G-17：autogenerate 对 CHECK 表达式失明）：

```bash
.venv/bin/alembic -x db=test upgrade head
.venv/bin/pytest tests/integration/test_temporal_constraints.py -q -m integration --snapshot-update \
  || python scripts/dump_check_constraints.py > tests/integration/check_constraints.snapshot
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration   # 第一条转绿
```

> 快照的重新生成方式以 `tests/integration/test_schemas.py` 里现有的生成逻辑为准；
> 若仓库没有 `scripts/dump_check_constraints.py`，就按该测试里的 SQL 手工导出。
> **不要**把新约束从快照里漏掉——快照是 CHECK 的唯一防线。

- [ ] **Step 3: Peer Group 构建的失败测试（纯函数）**

```python
# tests/unit/test_peer_group_build.py
import pytest

from fip.libs.strategy_library.peer_group.build import (
    UNCLASSIFIED,
    ClassificationLevel,
    ExclusionReason,
    PeerGroupCandidate,
    PeerGroupKey,
    build_peer_groups,
    derive_classification_code,
)

SCHEME = "AKSHARE_FUND_TYPE"


def _c(sid, code, currency="CNY", history_id=None):
    return PeerGroupCandidate(
        share_class_id=sid,
        classification_scheme=SCHEME if code is not None else None,
        classification_code=code,
        classification_history_id=history_id if history_id is not None else sid * 10,
        base_currency=currency,
    )


def test_L1_由连字符前缀派生且不另存一列():
    assert derive_classification_code("混合型-偏股", ClassificationLevel.L1) == "混合型"
    assert derive_classification_code("混合型-偏股", ClassificationLevel.L2) == "混合型-偏股"
    assert derive_classification_code("货币型", ClassificationLevel.L1) == "货币型"


def test_按分类与币种两维分组():
    build = build_peer_groups(
        [_c(1, "混合型-偏股"), _c(2, "混合型-灵活"), _c(3, "债券型-长债"),
         _c(4, "混合型-偏股", currency="USD")],
        ClassificationLevel.L1,
    )
    assert dict(build.groups) == {
        PeerGroupKey(SCHEME, "混合型", "CNY"): (1, 2),
        PeerGroupKey(SCHEME, "债券型", "CNY"): (3,),
        PeerGroupKey(SCHEME, "混合型", "USD"): (4,),
    }


def test_UNCLASSIFIED_不构成任何_Peer_Group():
    """D-6：空『基金类型』如实落库为 UNCLASSIFIED（不丢弃、不猜测），
    但它不是一个类别，是「我们不知道它属于哪个类别」。"""
    build = build_peer_groups([_c(1, UNCLASSIFIED), _c(2, "股票型")],
                              ClassificationLevel.L1)
    assert [k for k, _ in build.groups] == [PeerGroupKey(SCHEME, "股票型", "CNY")]
    assert build.excluded == (
        ExcludedCandidate(1, ExclusionReason.UNCLASSIFIED_CODE),
    )


def test_缺分类与缺币种分别如实登记原因():
    build = build_peer_groups(
        [_c(1, None), _c(2, "股票型", currency=None)], ClassificationLevel.L1
    )
    assert build.groups == ()
    assert {e.share_class_id: e.reason for e in build.excluded} == {
        1: ExclusionReason.CLASSIFICATION_MISSING,
        2: ExclusionReason.CURRENCY_UNKNOWN,
    }


def test_成员与分组顺序确定():
    """G-2：同一输入重算必须一致。dict / set 的迭代顺序不得泄漏到输出。"""
    a = build_peer_groups([_c(3, "股票型"), _c(1, "股票型"), _c(2, "债券型")],
                          ClassificationLevel.L1)
    b = build_peer_groups([_c(2, "债券型"), _c(1, "股票型"), _c(3, "股票型")],
                          ClassificationLevel.L1)
    assert a.groups == b.groups
    assert a.groups[0][1] == (1, 3)


def test_所用分类版本被完整带出():
    """FR-PEER-001 Output：成员列表 + 组规模 + 【所用分类版本】。
    只留构建规则不留结果，历史 Peer Group 不可重建（04-database-design §10.1.1）。"""
    build = build_peer_groups([_c(1, "股票型", history_id=77),
                               _c(2, "股票型", history_id=88)],
                              ClassificationLevel.L1)
    assert build.classification_history_ids == (77, 88)


def test_一只基金只能落进一个组():
    build = build_peer_groups([_c(1, "股票型")], ClassificationLevel.L1)
    members = [sid for _, ids in build.groups for sid in ids]
    assert len(members) == len(set(members))
```

```bash
.venv/bin/pytest tests/unit/test_peer_group_build.py -q
# 预期：ModuleNotFoundError: No module named 'fip.libs.strategy_library.peer_group'
```

- [ ] **Step 4: 实现 Peer Group 构建**

```python
# src/fip/libs/strategy_library/peer_group/build.py
"""Peer Group 构建。

⚠️ 本模块【不得】import 评分 / 排名 / Universe 任何模块（G-5 / C-4 /
FR-PEER-001）。违反会形成 Score → Universe → Peer Group → Score 的循环依赖 ——
它不会报错，只会让每次重算得到不同的排名（FR:89）。
由 tests/fitness/test_architecture.py 断言，不是靠这条注释保证。

划分维度 = Fund Classification × Currency（FR:105）。Market 不作为维度：
同一币种下的不同上市地不影响可比性，按 Market 细分只会缩小组规模、触发更多
INSUFFICIENT_SAMPLE（FR:114）。
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

UNCLASSIFIED = "UNCLASSIFIED"


class ClassificationLevel(StrEnum):
    L1 = "L1"
    L2 = "L2"


class ExclusionReason(StrEnum):
    """为什么这只基金不进任何 Peer Group。

    三个原因必须分开：「分类是空串」「压根没有分类记录」「不知道币种」是三件
    不同的事，合并成一个 EXCLUDED 会重演 Plan-1 在 grouping_status 上吃过的亏
    （「没识别出后缀」≠「确认没有后缀」）。
    """

    UNCLASSIFIED_CODE = "UNCLASSIFIED_CODE"
    CLASSIFICATION_MISSING = "CLASSIFICATION_MISSING"
    CURRENCY_UNKNOWN = "CURRENCY_UNKNOWN"


@dataclass(frozen=True, slots=True)
class PeerGroupKey:
    classification_scheme: str
    classification_code: str
    base_currency: str

    def key_string(self) -> str:
        """落 peer_group_snapshot.classification_key 的业务键字符串。

        上游对 classification_key 的构成「文档未给值」（BLOCK-1）。用竖线分隔
        三段而不是 JSON：它进唯一约束 (classification_key, effective_at, version)，
        必须是稳定、可索引、逐字节可比的。分隔符取 '|' 是因为 AKShare 的
        基金类型取值里出现的是连字符，不会与它冲突。
        """
        return f"{self.classification_scheme}|{self.classification_code}|{self.base_currency}"


@dataclass(frozen=True, slots=True)
class PeerGroupCandidate:
    share_class_id: int
    classification_scheme: str | None
    classification_code: str | None
    classification_history_id: int | None
    base_currency: str | None


@dataclass(frozen=True, slots=True)
class ExcludedCandidate:
    share_class_id: int
    reason: ExclusionReason


@dataclass(frozen=True, slots=True)
class PeerGroupBuild:
    groups: tuple[tuple[PeerGroupKey, tuple[int, ...]], ...]
    excluded: tuple[ExcludedCandidate, ...]
    classification_history_ids: tuple[int, ...]


def derive_classification_code(code: str, level: ClassificationLevel) -> str:
    """L1 = 连字符前缀，L2 = 完整原串。

    L1 【不另存一列】（D-5）：派生规则属 Strategy Library，不属数据。
    多存一列就多一份可能与原串分叉的真值。
    """
    return code.split("-")[0] if level is ClassificationLevel.L1 else code


def build_peer_groups(
    candidates: "list[PeerGroupCandidate]", level: ClassificationLevel
) -> PeerGroupBuild:
    """把候选成员按 (分类, 币种) 分组。

    输出顺序完全确定（按 key_string 排序、组内按 share_class_id 排序）——
    G-2 要求同一输入重算一致，而 dict / defaultdict 的迭代顺序在跨进程时
    不构成保证。
    """
    buckets: dict[PeerGroupKey, list[int]] = defaultdict(list)
    excluded: list[ExcludedCandidate] = []
    history_ids: set[int] = set()

    for candidate in candidates:
        if candidate.classification_code is None or candidate.classification_scheme is None:
            excluded.append(ExcludedCandidate(
                candidate.share_class_id, ExclusionReason.CLASSIFICATION_MISSING))
            continue
        if candidate.classification_code == UNCLASSIFIED:
            excluded.append(ExcludedCandidate(
                candidate.share_class_id, ExclusionReason.UNCLASSIFIED_CODE))
            continue
        if not candidate.base_currency:
            excluded.append(ExcludedCandidate(
                candidate.share_class_id, ExclusionReason.CURRENCY_UNKNOWN))
            continue
        key = PeerGroupKey(
            candidate.classification_scheme,
            derive_classification_code(candidate.classification_code, level),
            candidate.base_currency,
        )
        buckets[key].append(candidate.share_class_id)
        if candidate.classification_history_id is not None:
            history_ids.add(candidate.classification_history_id)

    groups = tuple(
        (key, tuple(sorted(ids)))
        for key, ids in sorted(buckets.items(), key=lambda kv: kv[0].key_string())
    )
    return PeerGroupBuild(
        groups=groups,
        excluded=tuple(sorted(excluded, key=lambda e: e.share_class_id)),
        classification_history_ids=tuple(sorted(history_ids)),
    )
```

```bash
.venv/bin/pytest tests/unit/test_peer_group_build.py -q   # 预期 7 passed
```

- [ ] **Step 5: G-5 的适应度测试（先证伪）**

现有 `tests/fitness/test_architecture.py` 的 C-4 检查扫描的是
`services/fund_service/peer_group`，而本 Plan 把 Peer Group 放在
`libs/strategy_library/peer_group` —— **现有守卫扫不到新模块**。
同文件的 `test_peer_group_guard_is_visible_not_silent` 也仍在断言
`services/fund_service/peer_group` 尚未创建。两处都要改。

```python
# tests/fitness/test_architecture.py（改）
# ① C-4 检查改为扫描新落位，并把 evaluation schema 的模型也列为禁止依赖
def test_peer_group_module_does_not_depend_on_scoring_or_universe():
    """C-4 / G-5 / FR-PEER-001：Peer Group 的构成不得依赖 Fund Score 或
    Fund Universe。违反会形成 Score → Universe → Peer Group → Score 的循环
    依赖 —— 它不会报错，只会让每次重算得到不同的排名。"""
    forbidden = (
        "fip.libs.strategy_library.score",
        "fip.libs.strategy_library.ranking",
        "fip.libs.strategy_library.universe",
        "fip.services.fund_service",
        "fip.services.factor_service",
    )
    offenders = []
    for f in _py_files("libs", "strategy_library", "peer_group"):
        for module in _dotted_imports(f):
            if any(_touches(module, prefix) for prefix in forbidden):
                offenders.append((f.name, module))
    assert not offenders, f"Peer Group 出现对评分/Universe 的依赖：{offenders}"


def test_peer_group_module_actually_exists():
    """把上一条从『空洞成立』变成『真的在查东西』。

    Plan-1 的教训之二：比没有测试更坏的是有一条自称是 oracle、实际恒真的测试。
    上一条在被扫描目录不存在时 _py_files 返回 []，assert not [] 恒真。"""
    assert _py_files("libs", "strategy_library", "peer_group"), (
        "libs/strategy_library/peer_group 不存在 —— C-4 检查会静默恒真"
    )


# ② GUARDED_ROOTS 追加两项（原为 ("strategy_library",) / ("quant_engine",)，
#    Task 4 搬迁后应为 ("libs", "strategy_library") / ("libs", "quant_engine")）：
#       ("libs", "strategy_library", "peer_group"),
# ③ 删除 test_peer_group_guard_is_visible_not_silent —— 它断言的
#    services/fund_service/peer_group 已被本 Plan 明确落在 libs 下，
#    继续留着会指向一个永远不会出现的路径。
```

```bash
.venv/bin/pytest tests/fitness -q
# 先在改动前跑一次，确认 test_peer_group_module_actually_exists 是 FAILED；
# 建好模块后转绿。
```

- [ ] **Step 6: 分类的 PIT 读取 + B1 原子写入（失败测试先行）**

```python
# tests/integration/test_peer_group_snapshot.py（追加）
import datetime as dt

from fip.libs.strategy_library.peer_group.build import (
    ClassificationLevel, build_peer_groups,
)
from fip.services.data_service.models.evaluation import (
    PeerGroupMember, PeerGroupSnapshot,
)
from fip.services.data_service.repositories.classification import (
    SqlClassificationPitRepository,
)
from fip.services.fund_service.peer_group_writer import PeerGroupSnapshotWriter


def test_分类按_available_at_解析_不用_effective_at(db_session, classified_funds):
    """G-1。一条 8-01 生效、9-10 才披露的分类修订，在 9-01 的决策里不得可见 ——
    否则历史 Peer Group 会被未来的分类调整污染，且污染完全不可见。"""
    repo = SqlClassificationPitRepository(
        db_session, visible_until=dt.datetime(2026, 9, 1, 23, 59, 59, tzinfo=dt.UTC)
    )
    codes = {c.share_class_id: c.classification_code
             for c in repo.candidates_as_of(dt.date(2026, 9, 1))}
    assert codes[classified_funds.revised_id] == "混合型-偏股"      # 修订前
    assert codes[classified_funds.revised_id] != "股票型"           # 不是修订后


def test_B1_快照与全部成员一并提交(db_session, classified_funds):
    build = build_peer_groups(
        SqlClassificationPitRepository(
            db_session, visible_until=dt.datetime(2026, 9, 1, 23, 59, 59, tzinfo=dt.UTC)
        ).candidates_as_of(dt.date(2026, 9, 1)),
        ClassificationLevel.L1,
    )
    written = PeerGroupSnapshotWriter(db_session).write_b1(dt.date(2026, 9, 1), build)
    snapshots = db_session.query(PeerGroupSnapshot).all()
    assert len(snapshots) == len(written) == len(build.groups)
    total_members = db_session.query(PeerGroupMember).count()
    assert total_members == sum(len(ids) for _, ids in build.groups)


def test_成员写入失败时快照整体回滚(db_session, classified_funds, monkeypatch):
    """D-18 / 01-system-architecture:855：B1 = 快照 + 全部成员，一并提交。
    写入不完整 → 整体回滚，本次决策视为未产生。"""
    build = build_peer_groups(
        [  # 第二个成员指向不存在的份额类别，触发 FK 违约
            *SqlClassificationPitRepository(
                db_session,
                visible_until=dt.datetime(2026, 9, 1, 23, 59, 59, tzinfo=dt.UTC),
            ).candidates_as_of(dt.date(2026, 9, 1)),
        ],
        ClassificationLevel.L1,
    )
    broken = build.__class__(
        groups=(*build.groups[:1],
                (build.groups[0][0], (*build.groups[0][1], 10**9))),
        excluded=build.excluded,
        classification_history_ids=build.classification_history_ids,
    )
    with pytest.raises(Exception):
        PeerGroupSnapshotWriter(db_session).write_b1(dt.date(2026, 9, 1), broken)
    db_session.rollback()
    assert db_session.query(PeerGroupSnapshot).count() == 0
    assert db_session.query(PeerGroupMember).count() == 0


def test_同一业务键重跑升_version(db_session, classified_funds):
    build = build_peer_groups(
        SqlClassificationPitRepository(
            db_session, visible_until=dt.datetime(2026, 9, 1, 23, 59, 59, tzinfo=dt.UTC)
        ).candidates_as_of(dt.date(2026, 9, 1)),
        ClassificationLevel.L1,
    )
    writer = PeerGroupSnapshotWriter(db_session)
    writer.write_b1(dt.date(2026, 9, 1), build)
    writer.write_b1(dt.date(2026, 9, 1), build)
    versions = sorted(
        s.version for s in db_session.query(PeerGroupSnapshot).all()
    )
    assert versions[:2] == [1, 2] or versions.count(1) == len(build.groups)


def test_UNCLASSIFIED_的基金不出现在任何成员行里(db_session, classified_funds):
    build = build_peer_groups(
        SqlClassificationPitRepository(
            db_session, visible_until=dt.datetime(2026, 9, 1, 23, 59, 59, tzinfo=dt.UTC)
        ).candidates_as_of(dt.date(2026, 9, 1)),
        ClassificationLevel.L1,
    )
    PeerGroupSnapshotWriter(db_session).write_b1(dt.date(2026, 9, 1), build)
    member_ids = {m.share_class_id for m in db_session.query(PeerGroupMember).all()}
    assert classified_funds.unclassified_id not in member_ids
```

```bash
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration
# 预期：ModuleNotFoundError: ...repositories.classification
```

- [ ] **Step 7: 实现分类 PIT 读取与 B1 写入**

```python
# src/fip/services/data_service/repositories/classification.py
"""分类的 PIT 读取。

区间型表的 PIT 解析比版本化事实表多一维：既要 available_at <= decision_at
（我们当时知道的那一版），又要 valid_from <= effective_at < valid_to
（那一版在评价时点是否生效）。少任何一维都会静默取错分类，而错的分类
会把一只基金放进错的 Peer Group —— 分位、排名、Tier 全部被污染且不可见。
"""

import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.libs.strategy_library.peer_group.build import PeerGroupCandidate

_SQL = text("""
    SELECT DISTINCT ON (sc.id)
           sc.id AS share_class_id,
           sc.base_currency,
           h.id  AS history_id,
           h.classification_scheme,
           h.classification_code
    FROM fund.fund_share_class sc
    JOIN fund.fund_classification_history h ON h.fund_id = sc.fund_id
    WHERE h.available_at <= :visible_until
      AND h.valid_from <= :effective_at
      AND (h.valid_to IS NULL OR h.valid_to > :effective_at)
    ORDER BY sc.id, h.valid_from DESC, h.available_at DESC, h.id DESC
""")


class SqlClassificationPitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def candidates_as_of(self, effective_at: dt.date) -> list[PeerGroupCandidate]:
        """本时点的 Peer Group 候选成员。

        LEFT JOIN 与 INNER JOIN 的选择：这里用 INNER JOIN，因此【没有】可见分类
        记录的份额类别根本不出现在结果里，而不是带着 classification_code = None
        出现。构建函数的 CLASSIFICATION_MISSING 分支因此只在调用方另行补入
        无分类候选时才触发 —— 调用方（Task 17 的装配）负责把全量份额类别与本
        结果做差集，如实登记「这些基金当时没有可见分类」。不要在这里悄悄丢弃它们。
        """
        rows = self._session.execute(
            _SQL, {"visible_until": self._visible_until, "effective_at": effective_at}
        ).mappings().all()
        return [
            PeerGroupCandidate(
                share_class_id=r["share_class_id"],
                classification_scheme=r["classification_scheme"],
                classification_code=r["classification_code"],
                classification_history_id=r["history_id"],
                base_currency=r["base_currency"],
            )
            for r in rows
        ]
```

```python
# src/fip/services/fund_service/peer_group_writer.py
"""B1 快照的原子写入。

SB-1：evaluation schema 的写入权唯一属于 fund_service（G-13）。
D-18：B1 = peer_group_snapshot 1 行 + 全部 peer_group_member 一并提交；
写入不完整 → 整体回滚，本次决策视为未产生。
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fip.libs.strategy_library.peer_group.build import PeerGroupBuild
from fip.services.data_service.models.evaluation import (
    PeerGroupMember,
    PeerGroupSnapshot,
)


class PeerGroupSnapshotWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def write_b1(
        self, effective_at: dt.date, build: PeerGroupBuild
    ) -> dict[str, int]:
        """写入本时点的全部 Peer Group 快照与成员，返回 classification_key → 快照 id。

        一个事务覆盖全部组：B1 的边界是「本次决策的 Peer Group 构成」，
        写一半的构成不是一个更小的正确构成，而是一个错的构成。
        """
        written: dict[str, int] = {}
        with self._session.begin_nested():
            for key, member_ids in build.groups:
                classification_key = key.key_string()
                current = self._session.execute(
                    select(func.max(PeerGroupSnapshot.version)).where(
                        PeerGroupSnapshot.classification_key == classification_key,
                        PeerGroupSnapshot.effective_at == effective_at,
                    )
                ).scalar_one_or_none()
                snapshot = PeerGroupSnapshot(
                    classification_key=classification_key,
                    classification_scheme=key.classification_scheme,
                    classification_code=key.classification_code,
                    base_currency=key.base_currency,
                    effective_at=effective_at,
                    version=1 if current is None else int(current) + 1,
                    peer_group_size=len(member_ids),
                    # FR-PEER-001 Output 的第三项：所用分类版本。只留构建规则
                    # 不留结果，历史 Peer Group 不可重建（04-database-design §10.1.1）。
                    classification_history_ids=list(build.classification_history_ids),
                )
                self._session.add(snapshot)
                self._session.flush()
                for share_class_id in member_ids:
                    self._session.add(PeerGroupMember(
                        peer_group_snapshot_id=snapshot.id,
                        share_class_id=share_class_id,
                        effective_at=effective_at,
                    ))
                self._session.flush()
                written[classification_key] = snapshot.id
        return written
```

> `PeerGroupSnapshot` / `PeerGroupMember` 的列由 **Task 8** 建（迁移 0017）。
> 本任务用到的列为：`classification_key` / `classification_scheme` /
> `classification_code` / `base_currency` / `effective_at` / `version` /
> `peer_group_size` / `classification_history_ids`（`ARRAY(BigInteger)` 或 JSONB）。
> 若 Task 8 没建 `classification_history_ids`，B1 的「所用分类版本」无处安放 ——
> 见文末矛盾 ⑥。

```bash
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration   # 预期 6 passed
.venv/bin/pytest tests/fitness -q
.venv/bin/ruff check src tests && make typecheck
git add -A && git commit -m "feat(peer-group): Fund Classification × Currency 分组与 B1 原子快照

新增 fund_share_class.base_currency + base_currency_source（迁移 0018）——
FR:116 要求分组维度与 R_f 解析键取自同一字段，Plan-1 未建该列。
币种由【声明的推导规则】填入并如实记录来源，不写 NOT NULL 兜底。
UNCLASSIFIED / 无分类 / 无币种三种排除原因分开登记（D-6）。
G-5 的适应度检查改扫 libs/strategy_library/peer_group，并补一条
『被扫目录必须存在』断言 —— 原检查在目录不存在时恒真。"
```

---

### Task 12: 因子标准化（Peer Group 内 Percentile Rank + 方向转换）

**Files:**

- Create: `src/fip/libs/strategy_library/factor/normalize.py`
- Modify: `src/fip/libs/strategy_library/peer_group/build.py`（加一个配置路径常量）
- Modify: `tests/fitness/test_architecture.py`
- Test: `tests/unit/test_factor_normalize.py`
- Test: `tests/fitness/test_single_config_source.py`

**Interfaces:**

*Consumes*：

```python
from fip.libs.strategy_library.factor.definitions import PreferenceDirection   # Task 9
from fip.libs.strategy_library.factor.status import FactorStatus               # Task 9
```

*Produces*：

```python
# fip.libs.strategy_library.factor.normalize
class CrossSectionStatus(StrEnum):
    NORMAL = "NORMAL"; INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"   # = cross_section_status_enum
PERCENTILE_SCALE: int = 8

def percentile_rank(values: Sequence[Decimal],
                    direction: PreferenceDirection) -> list[Decimal | None]:
    """契约原文。p = (N − Rank) / (N − 1) × 100；N == 1 → None；
    LOWER_IS_BETTER 先取负再排。"""

def competition_ranks(values: Sequence[Decimal]) -> list[int]
    """COMPETITION_RANK（D-20）：并列占用相同名次，随后名次被跳过。Rank=1 最优。"""

@dataclass(frozen=True, slots=True)
class NormalizedFactorValue:
    share_class_id: int
    rank: int | None
    n_effective: int
    percentile: Decimal | None
    status: CrossSectionStatus

def normalize_peer_group(
    entries: Sequence[tuple[int, Decimal | None]],
    direction: PreferenceDirection,
    min_peer_group_size: int,
) -> list[NormalizedFactorValue]

# fip.libs.strategy_library.peer_group.build（追加）
MIN_PEER_GROUP_SIZE_CONFIG_PATH: str = "peer_group.min_peer_group_size"
```

---

- [ ] **Step 1: 失败测试 —— 分位公式、并列、方向转换、N==1、n_effective**

```python
# tests/unit/test_factor_normalize.py
"""Percentile Rank 与方向转换。

期望值全部手算：
  公式 p = (N − Rank) / (N − 1) × 100，COMPETITION_RANK（并列占同名次）。
"""

from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor.definitions import PreferenceDirection
from fip.libs.strategy_library.factor.normalize import (
    CrossSectionStatus,
    competition_ranks,
    normalize_peer_group,
    percentile_rank,
)

D = Decimal
HIGH = PreferenceDirection.HIGHER_IS_BETTER
LOW = PreferenceDirection.LOWER_IS_BETTER


def test_无并列时分位落在_0_到_100_的两端():
    """values = [50, 40, 30, 20, 10]，N = 5，Rank = 1..5
       p = (5−1)/4×100, (5−2)/4×100, … = 100, 75, 50, 25, 0"""
    assert percentile_rank([D(50), D(40), D(30), D(20), D(10)], HIGH) == [
        D("100.00000000"), D("75.00000000"), D("50.00000000"),
        D("25.00000000"), D("0.00000000"),
    ]


def test_COMPETITION_RANK_并列占用相同名次并跳过后续名次():
    """values = [50, 40, 40, 20, 10] → Rank = 1, 2, 2, 4, 5（没有 3）。"""
    assert competition_ranks([D(50), D(40), D(40), D(20), D(10)]) == [1, 2, 2, 4, 5]
    assert percentile_rank([D(50), D(40), D(40), D(20), D(10)], HIGH) == [
        D("100.00000000"), D("75.00000000"), D("75.00000000"),
        D("25.00000000"), D("0.00000000"),
    ]


def test_LOWER_IS_BETTER_先取负再排_与排完再100减p_结果不同():
    """D-11 第 2 点的判据。values = [10, 20, 20, 30, 40]，LOWER_IS_BETTER。

    先取负：oriented = [−10, −20, −20, −30, −40]
            Rank = 1, 2, 2, 4, 5  →  p = 100, 75, 75, 25, 0
    排完再 100 − p：按原值降序 Rank = 5, 3, 3, 2, 1
            p_high = 0, 50, 50, 75, 100  →  100 − p_high = 100, 50, 50, 25, 0
    并列的那一对：75 ≠ 50。这就是「两者在有并列时结果不同」的确切形状。"""
    values = [D(10), D(20), D(20), D(30), D(40)]
    got = percentile_rank(values, LOW)
    assert got == [D("100.00000000"), D("75.00000000"), D("75.00000000"),
                   D("25.00000000"), D("0.00000000")]

    naive = [D(100) - p for p in percentile_rank(values, HIGH)]
    assert naive == [D("100.00000000"), D("50.00000000"), D("50.00000000"),
                     D("25.00000000"), D("0.00000000")]
    assert got != naive          # ← 这条断言就是裁定本身


def test_N为1时返回_None_不是50也不是100():
    assert percentile_rank([D(42)], HIGH) == [None]


def test_N为0时返回空列表():
    assert percentile_rank([], HIGH) == []


def test_全部并列时人人100():
    """N = 3 全相等 → Rank 全为 1 → p = (3−1)/2×100 = 100。
    这是公式的直接后果，不是特例分支 —— 若实现里出现 if all_equal 就说明写错了。"""
    assert percentile_rank([D(7), D(7), D(7)], HIGH) == [D("100.00000000")] * 3


# ---- normalize_peer_group：UNAVAILABLE 的排除与 n_effective -----------------

def _entries(n_valid: int, n_missing: int = 0):
    entries = [(i, D(1000 - i)) for i in range(n_valid)]
    entries += [(1000 + i, None) for i in range(n_missing)]
    return entries


def test_UNAVAILABLE_不参与分位计算也不被当作最差值():
    """FS:250 —— 不得把 UNAVAILABLE 当作最差值参与排名。"""
    out = normalize_peer_group(_entries(30, n_missing=5), HIGH, 30)
    by_id = {o.share_class_id: o for o in out}
    assert all(by_id[1000 + i].percentile is None for i in range(5))
    assert all(by_id[1000 + i].rank is None for i in range(5))
    assert by_id[0].percentile == D("100.00000000")
    assert by_id[0].n_effective == 30            # 不是 35


def test_判定基数是_n_effective_不是组规模():
    """G-7 / BR:542 —— 一个 50 只基金的组里若某指标只有 25 只可算，
    该指标仍属小样本。"""
    out = normalize_peer_group(_entries(25, n_missing=25), HIGH, 30)
    assert all(o.status is CrossSectionStatus.INSUFFICIENT_SAMPLE for o in out)
    assert all(o.percentile is None and o.rank is None for o in out)
    assert {o.n_effective for o in out} == {25}   # FR:356：仍须返回，调用方要知道差多少


def test_恰好达到阈值时正常产出():
    out = normalize_peer_group(_entries(30), HIGH, 30)
    assert all(o.status is CrossSectionStatus.NORMAL for o in out)
    assert max(o.percentile for o in out) == D("100.00000000")


def test_INSUFFICIENT_SAMPLE_不是错误状态且每个成员都有一行():
    """FR:358 + BLOCK-12 的 CHECK：INSUFFICIENT_SAMPLE 的行仍然落库。
    不落库会让历史查询无法区分『当时样本不足』与『当时根本没算』。"""
    out = normalize_peer_group(_entries(3), HIGH, 30)
    assert len(out) == 3


def test_输出顺序与输入顺序一致():
    """G-2：调用方按 share_class_id 对齐结果，顺序漂移会静默错位。"""
    entries = [(9, D(1)), (3, D(3)), (7, D(2))]
    assert [o.share_class_id for o in normalize_peer_group(entries, HIGH, 1)] == [9, 3, 7]
```

```bash
.venv/bin/pytest tests/unit/test_factor_normalize.py -q
# 预期：ModuleNotFoundError: ...factor.normalize
```

- [ ] **Step 2: 实现 `normalize.py`**

```python
# src/fip/libs/strategy_library/factor/normalize.py
"""Peer Group 内的 Percentile Rank 与方向转换（设计定案 D-11）。

方法已定案（FS:216 / BR:1016）：Percentile Rank / Peer Group 内排名。
「这不是 TBD」（FS:225）——未来若引入 Z-Score 或 Min-Max，属 Scoring Version 的
Major 变更。第一阶段【不做异常值处理】：Percentile Rank 对极值不敏感；
若改用 Z-Score，异常值处理会成为必需项，那是方法选择的连带后果，不可分开决策。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum

from fip.libs.strategy_library.factor.definitions import PreferenceDirection

# = 迁移里的 cross_section_status_enum AS ENUM ('NORMAL', 'INSUFFICIENT_SAMPLE')
class CrossSectionStatus(StrEnum):
    NORMAL = "NORMAL"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


# factor_value.normalized_value 是 NUMERIC(12, 8)
PERCENTILE_SCALE = 8
_PERCENTILE_QUANTUM = Decimal(1).scaleb(-PERCENTILE_SCALE)
_COMPUTE_PRECISION = 60
_HUNDRED = Decimal(100)


def competition_ranks(values: Sequence[Decimal]) -> list[int]:
    """COMPETITION_RANK（D-20，上游 03-fund-ranking §8.2 已定案）。

    Rank_i = 1 + |{j : value_j > value_i}|。并列占用相同名次，随后的名次被跳过
    （1, 2, 2, 4）。传入的 values 必须已经完成方向转换 —— 本函数一律「越大越优」。
    """
    return [1 + sum(1 for other in values if other > value) for value in values]


def percentile_rank(
    values: Sequence[Decimal], direction: PreferenceDirection
) -> list[Decimal | None]:
    """Peer Group 内分位。

    公式与 ranking 统一为 p = (N − Rank) / (N − 1) × 100（D-11 第 1 点）——
    文档从未说两者一致，但用两套分位公式会让「因子分位」与「排名分位」对同一只
    基金给出不同的数，无法解释。端点为 0 / 100 的约定还让 Fund Tier 的
    5% / 20% / 50% / 80% 阈值语义直观：「前 5%」就是 percentile >= 95。

    N == 1 → None。**不是 50，也不是 100** —— 一只基金的组里「分位」没有意义，
    给它一个数就是在编造一个不存在的比较（FS:877 / FR:341）。

    LOWER_IS_BETTER 【先取负再排分位】，而不是排完再 100 − p（D-11 第 2 点）。
    两者在有并列时结果不同：COMPETITION_RANK 下并列占用相同名次，取负使并列关系
    在同一侧保持。由 test_LOWER_IS_BETTER_先取负再排_与排完再100减p_结果不同 钉住。
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [None]

    oriented = (
        [-v for v in values]
        if direction is PreferenceDirection.LOWER_IS_BETTER
        else list(values)
    )
    ranks = competition_ranks(oriented)
    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        denominator = Decimal(n - 1)
        return [
            ((Decimal(n - rank) / denominator) * _HUNDRED).quantize(
                _PERCENTILE_QUANTUM, rounding=ROUND_HALF_UP
            )
            for rank in ranks
        ]


@dataclass(frozen=True, slots=True)
class NormalizedFactorValue:
    """G-8：Rank / n_effective / Percentile 三者都必须落库。

    只存 Rank 则历史分位不可还原；只存 Percentile 则「差多少」不可见。
    peer_group_size 由调用方另行落库（它是快照的属性，不是本函数的输入）。
    """

    share_class_id: int
    rank: int | None
    n_effective: int
    percentile: Decimal | None
    status: CrossSectionStatus


def normalize_peer_group(
    entries: Sequence[tuple[int, Decimal | None]],
    direction: PreferenceDirection,
    min_peer_group_size: int,
) -> list[NormalizedFactorValue]:
    """对一个 Peer Group 内某一个因子做标准化。

    entries 是 (share_class_id, 因子值或 None)。None 表示该因子对这只基金
    UNAVAILABLE —— 它【不参与】分位计算，也【不得】被当作最差值参与排名
    （FS:250）。把它当最差值等于宣称「数据不足 = 表现最差」。

    n_effective = 可算的成员数，判定基数就是它而不是组规模（G-7 / BR:542）。
    n_effective < min_peer_group_size 时不做任何横截面派生量，全体标
    INSUFFICIENT_SAMPLE，但 n_effective 仍如实返回 —— 返回 17 与返回 29
    对调用方的含义不同（FR:356）。这不是错误状态（FR:358）。

    返回顺序与 entries 一致。
    """
    participating = [(sid, value) for sid, value in entries if value is not None]
    n_effective = len(participating)

    if n_effective < min_peer_group_size:
        return [
            NormalizedFactorValue(sid, None, n_effective, None,
                                  CrossSectionStatus.INSUFFICIENT_SAMPLE)
            for sid, _ in entries
        ]

    oriented = (
        [-value for _, value in participating]
        if direction is PreferenceDirection.LOWER_IS_BETTER
        else [value for _, value in participating]
    )
    ranks = competition_ranks(oriented)
    percentiles = percentile_rank([value for _, value in participating], direction)
    resolved = {
        sid: (rank, percentile)
        for (sid, _), rank, percentile in zip(
            participating, ranks, percentiles, strict=True
        )
    }
    return [
        NormalizedFactorValue(
            sid,
            resolved[sid][0] if sid in resolved else None,
            n_effective,
            resolved[sid][1] if sid in resolved else None,
            CrossSectionStatus.NORMAL,
        )
        for sid, _ in entries
    ]
```

```bash
.venv/bin/pytest tests/unit/test_factor_normalize.py -q   # 预期 11 passed
```

- [ ] **Step 3: G-7「三处同一配置源」的适应度测试（先证伪）**

`MIN_PEER_GROUP_SIZE = 30` 被三个地方消费：标准化（本任务）、排名与 Tier（Task 15）。
只要有第二处写死 `30`，三者就会在阈值调整时分叉，而分叉不会报错 ——
只会让「排名说样本足够、分层说样本不足」。

```python
# tests/fitness/test_single_config_source.py
"""G-7：MIN_PEER_GROUP_SIZE 的三个消费方必须来自同一配置源。

做法是禁止裸字面量：配置路径只允许出现在一个常量定义处，阈值本身不得在
src 里以裸 30 的形式与 peer group / sample 之类的名字同现。
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
CONFIG_PATH = "peer_group.min_peer_group_size"


def test_配置路径字符串只出现在唯一的常量定义处():
    hits = [
        p for p in SRC.rglob("*.py")
        if CONFIG_PATH in p.read_text(encoding="utf-8")
    ]
    assert [p.name for p in hits] == ["build.py"], (
        f"{CONFIG_PATH} 出现在多个文件：{[str(p) for p in hits]}；"
        "应统一从 peer_group.build.MIN_PEER_GROUP_SIZE_CONFIG_PATH 取"
    )


def test_没有任何模块把_30_写死成最小样本量():
    offenders = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not (isinstance(node.value, ast.Constant) and node.value.value == 30):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any("PEER" in n.upper() or "SAMPLE" in n.upper() for n in names):
                offenders.append((path.name, names))
    assert not offenders, f"最小样本量被写死：{offenders}"
```

```bash
.venv/bin/pytest tests/fitness/test_single_config_source.py -q
# 先证伪：在 normalize.py 顶部临时加一行
#     MIN_PEER_GROUP_SIZE = 30
# 跑一次确认 test_没有任何模块把_30_写死成最小样本量 FAILED，再删掉。
```

在 `peer_group/build.py` 末尾追加常量：

```python
# src/fip/libs/strategy_library/peer_group/build.py（追加）
# MIN_PEER_GROUP_SIZE 的唯一配置路径。标准化（factor/normalize）、排名与
# Tier（Task 15）三处都从这里取路径，再由装配层去 ConfigSet 读值 ——
# G-7 要求三处同一配置源，而「同一个字符串常量」是它唯一可机器校验的形式。
MIN_PEER_GROUP_SIZE_CONFIG_PATH = "peer_group.min_peer_group_size"
```

```bash
.venv/bin/pytest tests/fitness -q
.venv/bin/ruff check src tests && make typecheck
git add -A && git commit -m "feat(factor): Peer Group 内 Percentile Rank 与方向转换

p = (N − Rank) / (N − 1) × 100，与 ranking 统一；N == 1 → None（不是 50 / 100）。
LOWER_IS_BETTER 先取负再排 —— 有并列时与『排完再 100 − p』结果不同，
由一条对照测试把两条路径的差异做出来当作裁定的判据（D-11）。
UNAVAILABLE 不参与分位、不当最差值；判定基数是 n_effective 不是组规模（G-7）；
Rank / n_effective / Percentile 三者都进返回值（G-8）。"
```

---

### Task 13: 因子有效性检验（IC / ICIR）

> **边界（D-1）**：本任务只做「能让 Score 合法产出」的最小检验 —— IC、ICIR、
> 以及按 `validation_policy` 阈值判定 `VALID` / `INVALID`。**不做**分层单调性、
> 因子间相关性剔除（`相关系数 > 0.8 视为冗余`）、Rolling 因子全家族 —— 那些仍属 M2。

**Files:**

- Create: `src/fip/libs/strategy_library/factor/effectiveness.py`
- Create: `src/fip/services/factor_service/effectiveness_writer.py`
- Create: `config/policy/validation/v1.yaml`
- Test: `tests/unit/test_factor_effectiveness.py`
- Test: `tests/unit/test_validation_config.py`
- Test: `tests/integration/test_factor_effectiveness_writer.py`

**Interfaces:**

*Consumes*：

```python
from fip.libs.quant_engine.correlation import spearman   # Task 3：spearman(xs, ys) -> Decimal
from fip.libs.quant_engine.stats import mean, stdev      # Task 3
from fip.libs.strategy_library.factor.normalize import NormalizedFactorValue   # Task 12
from fip.services.data_service.models.factor import FactorEffectiveness        # Task 7（迁移 0016）
```

*Produces*：

```python
# fip.libs.strategy_library.factor.effectiveness
class EffectivenessVerdict(StrEnum):
    VALID = "VALID"; INVALID = "INVALID"; INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
class ValidationSegment(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"; RECENT_3Y = "RECENT_3Y"
class EffectivenessReason(StrEnum):
    PASSED = "PASSED"; IC_MEAN_BELOW_THRESHOLD = "IC_MEAN_BELOW_THRESHOLD"
    ICIR_BELOW_THRESHOLD = "ICIR_BELOW_THRESHOLD"; ZERO_IC_DISPERSION = "ZERO_IC_DISPERSION"
    TOO_FEW_CROSS_SECTIONS = "TOO_FEW_CROSS_SECTIONS"

@dataclass(frozen=True, slots=True)
class CrossSection:
    effective_at: dt.date
    percentiles: tuple[Decimal, ...]
    forward_returns: tuple[Decimal, ...]

@dataclass(frozen=True, slots=True)
class EffectivenessThresholds:
    ic_mean_min: Decimal; icir_abs_min: Decimal
    min_cross_sections: int; min_names_per_cross_section: int; ic_std_ddof: int

@dataclass(frozen=True, slots=True)
class EffectivenessResult:
    factor_id: str; segment: ValidationSegment
    ic_series: tuple[Decimal, ...]
    ic_mean: Decimal | None; ic_std: Decimal | None; icir: Decimal | None
    n_cross_sections: int; verdict: EffectivenessVerdict; reason: EffectivenessReason

def cross_section_ic(section: CrossSection, min_names: int) -> Decimal | None
def evaluate_segment(factor_id, segment, sections, thresholds) -> EffectivenessResult
def combine_segments(results: Sequence[EffectivenessResult]) -> EffectivenessVerdict

# fip.services.factor_service.effectiveness_writer
class EffectivenessWriter:
    def __init__(self, session: Session) -> None
    def write(self, profile: str, peer_group_key: str, factor_version_id: int,
              results: Sequence[EffectivenessResult],
              validation_from: dt.date, validation_to: dt.date) -> int
```

---

- [ ] **Step 1: 失败测试 —— IC / ICIR 的手算值与 G-3 的零离散度分支**

```python
# tests/unit/test_factor_effectiveness.py
"""IC / ICIR。期望值全部手算。

IC   = 同一时点横截面上「因子值分位」与「后续收益」的 Spearman 相关
ICIR = IC 序列的均值 / 标准差
"""

import datetime as dt
from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor.effectiveness import (
    CrossSection,
    EffectivenessReason,
    EffectivenessThresholds,
    EffectivenessVerdict,
    ValidationSegment,
    combine_segments,
    cross_section_ic,
    evaluate_segment,
)

D = Decimal
TH = EffectivenessThresholds(
    ic_mean_min=D("0.02"), icir_abs_min=D("0.3"),
    min_cross_sections=3, min_names_per_cross_section=5, ic_std_ddof=1,
)


def _section(day, percentiles, forwards):
    return CrossSection(dt.date(2024, day, 1), tuple(map(D, percentiles)),
                        tuple(map(D, forwards)))


def test_完全同序的横截面_IC_等于1():
    """Spearman 在两列名次完全一致时恒为 1。"""
    s = _section(1, ["100", "75", "50", "25", "0"],
                 ["0.05", "0.03", "0.01", "-0.01", "-0.03"])
    assert cross_section_ic(s, 5) == D(1)


def test_完全反序的横截面_IC_等于负1():
    s = _section(1, ["100", "75", "50", "25", "0"],
                 ["-0.03", "-0.01", "0.01", "0.03", "0.05"])
    assert cross_section_ic(s, 5) == D(-1)


def test_已知错位的横截面_IC_等于0点8():
    """ρ = 1 − 6Σd² / (n(n²−1))。名次差 d = [−1, 1, −1, 1, 0]，Σd² = 4，
    n = 5 → 1 − 24/120 = 0.8。"""
    s = _section(1, ["0", "25", "50", "75", "100"],
                 ["0.02", "0.01", "0.04", "0.03", "0.05"])
    assert cross_section_ic(s, 5) == D("0.8")


def test_横截面名数不足时该时点不产出_IC():
    """样本不足的横截面不能贡献一个『看起来正常』的相关系数。
    跳过它而不是把它记成 0 —— 记 0 会把 IC 均值拉向 0（G-3 同一原则）。"""
    s = _section(1, ["100", "0"], ["0.05", "-0.01"])
    assert cross_section_ic(s, 5) is None


def test_ICIR_是_IC_序列的均值除以标准差():
    """IC 序列 = [0.1, 0.2, 0.3]：μ = 0.2，Σ(x−μ)² = 0.02，
    var(ddof=1) = 0.01，σ = 0.1 → ICIR = 0.2 / 0.1 = 2。"""
    sections = [
        _section(1, ["100", "75", "50", "25", "0"], ["0.05", "0.03", "0.01", "-0.01", "-0.03"]),
    ]
    result = evaluate_segment(
        "F-RAP-001", ValidationSegment.FULL_HISTORY, sections, TH,
        _ic_override=[D("0.1"), D("0.2"), D("0.3")],
    )
    assert result.ic_mean == D("0.2")
    assert result.ic_std == D("0.1")
    assert result.icir == D(2)
    assert result.verdict is EffectivenessVerdict.VALID
    assert result.reason is EffectivenessReason.PASSED


def test_IC_均值低于阈值判_INVALID():
    result = evaluate_segment(
        "F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
        _ic_override=[D("0.01"), D("0.02"), D("0.005")],
    )
    assert result.verdict is EffectivenessVerdict.INVALID
    assert result.reason is EffectivenessReason.IC_MEAN_BELOW_THRESHOLD


def test_ICIR_低于阈值判_INVALID():
    """IC = [0.1, −0.06, 0.02]：μ = 0.02，符合 IC 阈值；
    Σ(x−μ)² = 0.0064 + 0.0064 + 0 = 0.0128，var = 0.0064，σ = 0.08，
    ICIR = 0.02/0.08 = 0.25 < 0.3 → INVALID。"""
    result = evaluate_segment(
        "F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
        _ic_override=[D("0.1"), D("-0.06"), D("0.02")],
    )
    assert result.ic_mean == D("0.02")
    assert result.icir == D("0.25")
    assert result.verdict is EffectivenessVerdict.INVALID
    assert result.reason is EffectivenessReason.ICIR_BELOW_THRESHOLD


def test_IC_序列零离散度时_ICIR_为_None_不是_inf():
    """G-3 在检验层的体现：σ = 0 时 ICIR 无定义。绝不填 inf、不填极大值。
    判定取【失败关闭】的方向 —— 未通过检验的因子权重为 0，且在归因中留痕。"""
    result = evaluate_segment(
        "F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
        _ic_override=[D("0.1"), D("0.1"), D("0.1")],
    )
    assert result.icir is None
    assert result.verdict is EffectivenessVerdict.INVALID
    assert result.reason is EffectivenessReason.ZERO_IC_DISPERSION


def test_横截面数不足时是_INSUFFICIENT_EVIDENCE_不是_INVALID():
    """『检验尚未产出』与『检验做了没通过』是两件事：前者让 Score 落
    VALIDATION_PENDING（FS:342），后者让该因子权重为 0（FS:344）。
    合并两者会让『还没检验』伪装成『检验过、不行』。"""
    result = evaluate_segment(
        "F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
        _ic_override=[D("0.5"), D("0.5")],
    )
    assert result.verdict is EffectivenessVerdict.INSUFFICIENT_EVIDENCE
    assert result.reason is EffectivenessReason.TOO_FEW_CROSS_SECTIONS


def test_双段均须通过才算_VALID():
    """BR:345：检验区间 = 全历史滚动 + 最近 3 年，双段均须通过。"""
    good = evaluate_segment("F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
                            _ic_override=[D("0.1"), D("0.2"), D("0.3")])
    bad = evaluate_segment("F-RAP-001", ValidationSegment.RECENT_3Y, [], TH,
                           _ic_override=[D("0.01"), D("0.02"), D("0.005")])
    assert combine_segments([good, good]) is EffectivenessVerdict.VALID
    assert combine_segments([good, bad]) is EffectivenessVerdict.INVALID


def test_任一段证据不足则整体证据不足():
    good = evaluate_segment("F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
                            _ic_override=[D("0.1"), D("0.2"), D("0.3")])
    thin = evaluate_segment("F-RAP-001", ValidationSegment.RECENT_3Y, [], TH,
                            _ic_override=[D("0.5"), D("0.5")])
    assert combine_segments([good, thin]) is EffectivenessVerdict.INSUFFICIENT_EVIDENCE


def test_只给一段时不得视为双段通过():
    good = evaluate_segment("F-RAP-001", ValidationSegment.FULL_HISTORY, [], TH,
                            _ic_override=[D("0.1"), D("0.2"), D("0.3")])
    with pytest.raises(ValueError, match="两段"):
        combine_segments([good])
```

```bash
.venv/bin/pytest tests/unit/test_factor_effectiveness.py -q
# 预期：ModuleNotFoundError: ...factor.effectiveness
```

- [ ] **Step 2: 实现 `effectiveness.py`**

```python
# src/fip/libs/strategy_library/factor/effectiveness.py
"""因子有效性检验的最小集（设计定案 D-1）。

为什么它在 Plan-2 而不是 M2：FS:346「factor_effectiveness 的存在性是 Score 产出
的【前置条件，不是可选的补充信息】」，且 FS:327-346 明确堵死了「先按等权上线、
等检验出来再调」这条捷径 ——「与未经检验就拍权重完全等价，差别只是拍的值恰好
是等权」。没有本模块，M1.4 的 Score / Tier 验收标准自己通不过。

本模块【不做】：分层单调性、因子间相关性剔除（相关系数 > 0.8 视为冗余）、
Rolling 因子全家族。那些仍属 M2（D-1 明列的边界）。
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import StrEnum

from fip.libs.quant_engine.correlation import spearman
from fip.libs.quant_engine.stats import mean, stdev

_COMPUTE_PRECISION = 60


class EffectivenessVerdict(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    # 「检验尚未产出」——与 INVALID 严格区分：前者让 Score 落 VALIDATION_PENDING
    # （FS:342），后者让该因子权重为 0 并在归因中留痕（FS:344）。
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ValidationSegment(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"
    RECENT_3Y = "RECENT_3Y"


class EffectivenessReason(StrEnum):
    PASSED = "PASSED"
    IC_MEAN_BELOW_THRESHOLD = "IC_MEAN_BELOW_THRESHOLD"
    ICIR_BELOW_THRESHOLD = "ICIR_BELOW_THRESHOLD"
    ZERO_IC_DISPERSION = "ZERO_IC_DISPERSION"
    TOO_FEW_CROSS_SECTIONS = "TOO_FEW_CROSS_SECTIONS"


@dataclass(frozen=True, slots=True)
class CrossSection:
    """一个时点的横截面。

    percentiles 与 forward_returns 【按同一顺序对齐同一批基金】。两列都必须
    来自同一个 Peer Group —— 跨组混合会把不同收益分布的基金放在一条相关系数里。
    """

    effective_at: dt.date
    percentiles: tuple[Decimal, ...]
    forward_returns: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class EffectivenessThresholds:
    ic_mean_min: Decimal
    icir_abs_min: Decimal
    min_cross_sections: int
    min_names_per_cross_section: int
    ic_std_ddof: int


@dataclass(frozen=True, slots=True)
class EffectivenessResult:
    factor_id: str
    segment: ValidationSegment
    ic_series: tuple[Decimal, ...]
    ic_mean: Decimal | None
    ic_std: Decimal | None
    icir: Decimal | None
    n_cross_sections: int
    verdict: EffectivenessVerdict
    reason: EffectivenessReason


def cross_section_ic(section: CrossSection, min_names: int) -> Decimal | None:
    """一个时点的 IC = Spearman(因子分位, 后续收益)。

    名数不足 min_names 时返回 None 而不是 0：把样本不足的时点记成 IC = 0
    会把整条序列的均值拖向 0，而那个 0 不是观测，是填充（G-3）。
    """
    if len(section.percentiles) != len(section.forward_returns):
        raise ValueError(
            f"{section.effective_at} 的分位与后续收益长度不一致："
            f"{len(section.percentiles)} vs {len(section.forward_returns)}"
        )
    if len(section.percentiles) < min_names:
        return None
    return spearman(section.percentiles, section.forward_returns)


def evaluate_segment(
    factor_id: str,
    segment: ValidationSegment,
    sections: Sequence[CrossSection],
    thresholds: EffectivenessThresholds,
    _ic_override: Sequence[Decimal] | None = None,
) -> EffectivenessResult:
    """对一个检验区间求 IC 序列并判定。

    _ic_override 只供单元测试直接喂 IC 序列（免去为了测判定逻辑而构造
    几十个横截面）。生产路径一律不传。

    判定（阈值来自 config/policy/validation/v1.yaml，全部 PROVISIONAL）：
      · 横截面数 < min_cross_sections → INSUFFICIENT_EVIDENCE（检验尚未产出）
      · σ(IC) == 0                    → ICIR 无定义 → INVALID(ZERO_IC_DISPERSION)
        【绝不填 inf】。取失败关闭方向：未通过检验的因子权重为 0 且留痕，
        比让一个 ICIR 算不出来的因子拿到满权重安全。
      · IC 均值 < ic_mean_min         → INVALID
      · |ICIR| < icir_abs_min         → INVALID
      · 其余                          → VALID
    """
    if _ic_override is not None:
        ic_series = tuple(_ic_override)
    else:
        ic_series = tuple(
            ic for ic in (
                cross_section_ic(s, thresholds.min_names_per_cross_section)
                for s in sections
            )
            if ic is not None
        )

    n = len(ic_series)
    if n < thresholds.min_cross_sections:
        return EffectivenessResult(
            factor_id, segment, ic_series, None, None, None, n,
            EffectivenessVerdict.INSUFFICIENT_EVIDENCE,
            EffectivenessReason.TOO_FEW_CROSS_SECTIONS,
        )

    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        ic_mean = mean(ic_series)
        ic_std = stdev(ic_series, ddof=thresholds.ic_std_ddof)
        icir = None if ic_std == 0 else ic_mean / ic_std

    if icir is None:
        return EffectivenessResult(
            factor_id, segment, ic_series, ic_mean, ic_std, None, n,
            EffectivenessVerdict.INVALID, EffectivenessReason.ZERO_IC_DISPERSION,
        )
    if ic_mean < thresholds.ic_mean_min:
        return EffectivenessResult(
            factor_id, segment, ic_series, ic_mean, ic_std, icir, n,
            EffectivenessVerdict.INVALID, EffectivenessReason.IC_MEAN_BELOW_THRESHOLD,
        )
    if abs(icir) < thresholds.icir_abs_min:
        return EffectivenessResult(
            factor_id, segment, ic_series, ic_mean, ic_std, icir, n,
            EffectivenessVerdict.INVALID, EffectivenessReason.ICIR_BELOW_THRESHOLD,
        )
    return EffectivenessResult(
        factor_id, segment, ic_series, ic_mean, ic_std, icir, n,
        EffectivenessVerdict.VALID, EffectivenessReason.PASSED,
    )


def combine_segments(
    results: Sequence[EffectivenessResult],
) -> EffectivenessVerdict:
    """双段均须通过（BR:345：全历史滚动 + 最近 3 年）。

    必须恰好两段：只跑一段就宣布 VALID 等于把「双段」这个要求悄悄降级成
    「单段」，而降级不会报错。
    """
    segments = {r.segment for r in results}
    if segments != {ValidationSegment.FULL_HISTORY, ValidationSegment.RECENT_3Y}:
        raise ValueError(
            f"必须提供两段检验结果（FULL_HISTORY + RECENT_3Y），实得 {sorted(segments)}"
        )
    if any(r.verdict is EffectivenessVerdict.INSUFFICIENT_EVIDENCE for r in results):
        return EffectivenessVerdict.INSUFFICIENT_EVIDENCE
    if all(r.verdict is EffectivenessVerdict.VALID for r in results):
        return EffectivenessVerdict.VALID
    return EffectivenessVerdict.INVALID
```

```bash
.venv/bin/pytest tests/unit/test_factor_effectiveness.py -q   # 预期 12 passed
```

- [ ] **Step 3: `config/policy/validation/v1.yaml`（新建）+ 钉死测试**

```yaml
# Validation Policy v1 —— 因子有效性检验的阈值
# Owner: validation_policy（FS:350「本域是消费方不是定义方：阈值属
# validation_policy，由 04-factor 产出检验数值、由该 Policy 判定 VALID/INVALID」）
#
# 全部为【推荐默认，非定案】——FS:348 / BR:345 原话是「业务方可改」。
effectiveness:
  ic_mean_min:
    value: 0.02
    status: PROVISIONAL
    source: "上游 FS:348 / BR:345「IC 均值 >= 0.02」推荐默认，非定案"
  icir_abs_min:
    value: 0.3
    status: PROVISIONAL
    source: "上游 FS:348 / BR:345「|ICIR| >= 0.3」推荐默认，非定案"
  min_cross_sections:
    value: 12
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— 文档未给『IC 序列至少多长才算检验产出』；取 12 期（月频一年）"
  min_names_per_cross_section:
    value: 30
    status: DECIDED
    source: "= MIN_PEER_GROUP_SIZE（FR:340）—— 横截面统计量在小于该值时不产出"
  ic_std_ddof:
    value: 1
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— 与 volatility.ddof 保持一致"
  forward_horizon_days:
    value: 21
    status: PROVISIONAL
    source: "Plan-2 起草补齐 —— 文档未给『后续收益』的期限；取 21 个交易日（约一个月）"
segments:
  recent_lookback_days:
    value: 756
    status: PROVISIONAL
    source: "上游 BR:345「最近 3 年」= 3 × 252 个交易日"
  require_both:
    value: true
    status: PROVISIONAL
    source: "上游 BR:345「全历史滚动 + 最近 3 年双段均须通过」"
```

```python
# tests/unit/test_validation_config.py
import pathlib
from decimal import Decimal

from fip.platform.config.loader import load_config_file
from fip.platform.decision_data.context import RuntimeMode

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _cfg():
    return load_config_file(
        ROOT / "config" / "policy" / "validation" / "v1.yaml", RuntimeMode.BACKTEST
    )


def test_阈值取上游推荐默认():
    cfg = _cfg()
    assert Decimal(str(cfg.get("effectiveness.ic_mean_min"))) == Decimal("0.02")
    assert Decimal(str(cfg.get("effectiveness.icir_abs_min"))) == Decimal("0.3")


def test_阈值全部标_PROVISIONAL_并指向上游行号():
    """G-14。上游原话是『推荐默认，非定案』『业务方可改』——
    标 DECIDED 会让下游以为这是投研拍过板的值。"""
    params = _cfg().parameters
    for path in ("effectiveness.ic_mean_min", "effectiveness.icir_abs_min",
                 "effectiveness.min_cross_sections", "segments.require_both"):
        assert params[path].status.value == "PROVISIONAL", path
        assert params[path].source, path


def test_横截面最小名数与_MIN_PEER_GROUP_SIZE_一致():
    """两处若分叉，会出现『排名说样本不足、IC 说样本够』。"""
    evaluation = load_config_file(
        ROOT / "config" / "policy" / "evaluation" / "v1.yaml", RuntimeMode.BACKTEST
    )
    assert _cfg().get("effectiveness.min_names_per_cross_section") == evaluation.get(
        "peer_group.min_peer_group_size"
    )
```

```bash
.venv/bin/pytest tests/unit/test_validation_config.py -q   # 先跑：文件不存在 → FAILED；建好后 3 passed
```

- [ ] **Step 4: 落库（`factor.factor_effectiveness`）**

先写失败测试：

```python
# tests/integration/test_factor_effectiveness_writer.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor.effectiveness import (
    EffectivenessReason, EffectivenessResult, EffectivenessVerdict, ValidationSegment,
)
from fip.services.data_service.models.factor import FactorEffectiveness
from fip.services.factor_service.effectiveness_writer import EffectivenessWriter

pytestmark = pytest.mark.integration

D = Decimal


def _result(segment, verdict, reason):
    return EffectivenessResult(
        factor_id="F-RAP-001", segment=segment,
        ic_series=(D("0.1"), D("0.2"), D("0.3")),
        ic_mean=D("0.2"), ic_std=D("0.1"), icir=D(2),
        n_cross_sections=3, verdict=verdict, reason=reason,
    )


def test_逐段落库且带检验区间(db_session, factor_version_fixture):
    written = EffectivenessWriter(db_session).write(
        profile="DEFAULT", peer_group_key="AKSHARE_FUND_TYPE|股票型|CNY",
        factor_version_id=factor_version_fixture.id,
        results=[
            _result(ValidationSegment.FULL_HISTORY, EffectivenessVerdict.VALID,
                    EffectivenessReason.PASSED),
            _result(ValidationSegment.RECENT_3Y, EffectivenessVerdict.VALID,
                    EffectivenessReason.PASSED),
        ],
        validation_from=dt.date(2019, 1, 1), validation_to=dt.date(2026, 9, 1),
    )
    assert written == 2
    rows = db_session.query(FactorEffectiveness).all()
    assert {r.segment for r in rows} == {"FULL_HISTORY", "RECENT_3Y"}
    assert {r.validation_from for r in rows} == {dt.date(2019, 1, 1)}
    assert rows[0].ic_mean == D("0.20000000") and rows[0].icir == D("2.00000000")


def test_ICIR_不可算时落_NULL_不落_0(db_session, factor_version_fixture):
    """G-3：UNAVAILABLE 不得被任何填充值替代。0 与 NULL 在这里含义相反 ——
    0 表示『算出来是 0』，NULL 表示『算不出来』。"""
    EffectivenessWriter(db_session).write(
        profile="DEFAULT", peer_group_key="AKSHARE_FUND_TYPE|股票型|CNY",
        factor_version_id=factor_version_fixture.id,
        results=[
            EffectivenessResult("F-RAP-001", ValidationSegment.FULL_HISTORY,
                                (D("0.1"),) * 3, D("0.1"), D(0), None, 3,
                                EffectivenessVerdict.INVALID,
                                EffectivenessReason.ZERO_IC_DISPERSION),
            _result(ValidationSegment.RECENT_3Y, EffectivenessVerdict.VALID,
                    EffectivenessReason.PASSED),
        ],
        validation_from=dt.date(2019, 1, 1), validation_to=dt.date(2026, 9, 1),
    )
    row = db_session.query(FactorEffectiveness).filter_by(
        segment="FULL_HISTORY"
    ).one()
    assert row.icir is None
    assert row.verdict == "INVALID" and row.reason == "ZERO_IC_DISPERSION"


def test_Peer_Group_是检验结果身份的一部分(db_session, factor_version_fixture):
    """同一因子在股票型组里有效、在债券型组里无效是完全正常的结果。
    不带 peer_group_key，两个结果会互相覆盖或产生一条无法解释的合并值。"""
    writer = EffectivenessWriter(db_session)
    for key in ("AKSHARE_FUND_TYPE|股票型|CNY", "AKSHARE_FUND_TYPE|债券型|CNY"):
        writer.write(
            profile="DEFAULT", peer_group_key=key,
            factor_version_id=factor_version_fixture.id,
            results=[
                _result(ValidationSegment.FULL_HISTORY, EffectivenessVerdict.VALID,
                        EffectivenessReason.PASSED),
                _result(ValidationSegment.RECENT_3Y, EffectivenessVerdict.VALID,
                        EffectivenessReason.PASSED),
            ],
            validation_from=dt.date(2019, 1, 1), validation_to=dt.date(2026, 9, 1),
        )
    assert db_session.query(FactorEffectiveness).count() == 4
```

```bash
.venv/bin/pytest tests/integration/test_factor_effectiveness_writer.py -q -m integration
# 预期：ModuleNotFoundError: ...factor_service.effectiveness_writer
```

实现：

```python
# src/fip/services/factor_service/effectiveness_writer.py
"""factor.factor_effectiveness 的写入。

SB-1 / G-13：factor schema 的写入权唯一属于 factor_service。

⚠️ 本模块要求 factor_effectiveness 至少有这些列（由 Task 7 的迁移 0016 建）：
    id, factor_version_id (FK → factor.factor_version, RESTRICT),
    factor_id, evaluation_profile, peer_group_key, segment,
    validation_from, validation_to,
    ic_mean NUMERIC(12,8) NULL, ic_std NUMERIC(12,8) NULL,
    icir NUMERIC(12,8) NULL, n_cross_sections INT,
    verdict VARCHAR + CHECK(VALID/INVALID/INSUFFICIENT_EVIDENCE),
    reason VARCHAR, computed_at TIMESTAMPTZ
其中 peer_group_key 与 segment 是【本 Plan 对 D-16 字段清单的扩展】——
D-16 给的是 (profile, factor_id, valid/invalid, IC, ICIR, 检验区间)，
不含这两列。理由见本草案文末矛盾 ⑤。
"""

import datetime as dt
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from fip.libs.strategy_library.factor.effectiveness import EffectivenessResult
from fip.services.data_service.models.factor import FactorEffectiveness

_SCALE = Decimal("1e-8")


def _q(value: Decimal | None) -> Decimal | None:
    """出口量化。None 原样传出 —— NULL 与 0 在这里含义相反（G-3）。"""
    return None if value is None else value.quantize(_SCALE, rounding=ROUND_HALF_UP)


class EffectivenessWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        profile: str,
        peer_group_key: str,
        factor_version_id: int,
        results: Sequence[EffectivenessResult],
        validation_from: dt.date,
        validation_to: dt.date,
    ) -> int:
        rows = [
            FactorEffectiveness(
                factor_version_id=factor_version_id,
                factor_id=r.factor_id,
                evaluation_profile=profile,
                peer_group_key=peer_group_key,
                segment=r.segment.value,
                validation_from=validation_from,
                validation_to=validation_to,
                ic_mean=_q(r.ic_mean),
                ic_std=_q(r.ic_std),
                icir=_q(r.icir),
                n_cross_sections=r.n_cross_sections,
                verdict=r.verdict.value,
                reason=r.reason.value,
                computed_at=dt.datetime.now(dt.UTC),
            )
            for r in results
        ]
        self._session.add_all(rows)
        self._session.flush()
        return len(rows)
```

```bash
.venv/bin/pytest tests/integration/test_factor_effectiveness_writer.py -q -m integration
# 预期 3 passed
```

- [ ] **Step 5: 全量回归并提交**

```bash
.venv/bin/ruff check src tests
make typecheck
.venv/bin/pytest tests/unit tests/fitness -q
.venv/bin/pytest tests/integration -q -m integration
git add -A && git commit -m "feat(factor): 因子有效性检验最小集（IC / ICIR）

IC = 同一时点横截面上因子分位与后续收益的 Spearman；ICIR = IC 序列均值/标准差。
σ(IC) = 0 时 ICIR 落 NULL 而不是 inf，判定取失败关闭方向（G-3）。
『检验尚未产出』(INSUFFICIENT_EVIDENCE) 与『检验没通过』(INVALID) 严格区分 ——
前者让 Score 落 VALIDATION_PENDING，后者让该因子权重为 0 并在归因中留痕。
阈值全部标 PROVISIONAL：上游原话是『推荐默认，非定案』『业务方可改』。
不做分层单调性与相关性剔除（仍属 M2，D-1 的边界）。"
```

---

## 起草期间发现的矛盾与遗漏

> 以下每一条都会在实现期造成返工或静默错误，**需要计划作者先裁决**。
> 编号在上文的代码注释中被引用。

### ① `FactorInput.mar` 是标量，装不下 `RISK_FREE` 模式的 MAR 序列 —— **阻塞级**

接口契约写的是 `mar: Decimal | None  # None 表示 mar_policy 未配置`，
而 `FE:483-498` 与任务描述都明确 `RISK_FREE` 模式下 **MAR 在窗口内是序列**。
一个标量字段有三种「装下去」的办法（取均值 / 取首值 / 取末值），三种都是在
伪造一个从未被决策过的标尺 —— 这与 Plan-1 在 `market.fund_nav.adjusted_nav`
标量列上花三轮才想明白的教训完全同型（标量副本装不下二元函数）。

本草案的处置：`resolve_mar` 如实产出序列，`mar_for_factor_input` 在 `RISK_FREE`
下返回 `(None, MAR_SERIES_NOT_SUPPORTED)`，因子 `UNAVAILABLE`。这是安全的，
但意味着 **`RISK_FREE` 模式在 M1 实际不可用**。

需要裁决：(a) 给 `FactorInput` 增加 `mar_series: tuple[tuple[date, Decimal], ...] | None`
字段（改契约），还是 (b) 在计划里明写「M1 只支持 `ZERO` / `FIXED`」并把
`RISK_FREE` 的实现推到 M2。本草案按 (b) 写，但把 (a) 需要的解析能力留在了
`MarResolution.series` 里。

### ② D-10 的 WARNING 第二触发条件让 `FactorStatus.VALID` 在 M1 不可达

D-10：「输入序列的 `availability_quality` 链路中含 `INFERRED`」→ `WARNING`。
G-15 与 Plan-1 交接：AKShare 链路 **100% 是 `INFERRED`**（上游给不出披露时刻）。
两条相乘 = M1 的每一个因子、每一只基金、每一个时点都是 `WARNING`，`VALID`
一次也不会出现。

后果不是错误，但会传导：`FE:194-199` 要求「`WARNING` 参与，但标记须随评价结果
传递」，于是**全部** Score 都会带 WARNING 标记；下游若把 WARNING 当异常处理，
M1 会表现为「什么都不正常」。与 D-19 里「M1 的常态是 `PARTIAL`」需要被显式
断言是同一类问题。

建议：要么把「链路含 INFERRED」降级为一个独立的 `quality_flag` 字段（不占用
`FactorStatus`），要么在计划里明写「M1 因子的常态是 WARNING」并要求测试断言它
（本草案按后者写了 `test_INFERRED_链路让_VALID_不可达`）。

### ③ D-10 与 D-9 / `unavailable_reason` 八类枚举对「分母为 0」的归类相反

- D-10 表格：`INVALID` ←「计算过程产生数学上无意义的结果（**分母为 0**、负方差、NaN）」
- D-9 与 `10-api/03` §4.3.5：`ZERO_MAX_DRAWDOWN` / `ZERO_VOLATILITY` /
  `ZERO_DOWNSIDE_VOLATILITY` 都是 **`unavailable_reason`**，且 `ZERO_MAX_DRAWDOWN`
  被明确标注为「**好消息型**不可用」。

差别是实质性的：`INVALID` 会传导到 `evaluation_status = FAILED` 并**须告警**
（`FE:391`、`FE:659`），而 `UNAVAILABLE` 是「正常业务情形，不需要修复」。
按 D-10 实现，一只从未回撤的基金会触发告警。

本草案按 **UNAVAILABLE** 实现，并在 `status.py` 的枚举 docstring 里记了理由。
需要计划作者确认，并相应修订 D-10 的表格。

### ④ MAR 第三模式的名字：任务描述用 `FIXED`，上游用 `CUSTOM`

`FE:454-460` 逐字抄录的字段表写的是 `mar_policy | ZERO / RISK_FREE / **CUSTOM**`，
`mar_value` 与 `mar_quotation_basis`「仅 `CUSTOM` 模式必填」。任务描述（以及本草案）
用的是 `FIXED`。两者指同一件事，但它会落进 `evaluation_policy` 配置与
`factor_value.evaluation_policy_version` 的可复现链路里 —— 改名要带一次数据迁移。
建议在计划里钉死一个，本草案暂取 `FIXED`。

另：上游还要求 `CUSTOM` 模式必填 `mar_quotation_basis`（年化口径）。本草案的
`resolve_mar` 只要求 `fixed_value`，**没有**实现 `mar_quotation_basis` —— 这是
一个如实登记的缺口，需要决定是补上还是明确推到 M2。

### ⑤ `factor_effectiveness` 的粒度：D-16 的字段清单缺 Peer Group 维度 —— **影响 Task 7 建表**

D-16 给的是 `(profile, factor_id, valid/invalid, IC, ICIR, 检验区间)`。
但 IC 是**横截面**统计量，而本平台的横截面就是 Peer Group（标准化、排名、分位、
分层四者必须用同一个 Peer Group，`FR:574` C-2）。同一个因子在股票型组里有效、
在债券型组里无效是完全正常的结果；不带 `peer_group_key`，两个结果只能互相覆盖，
或者被迫跨组池化 —— 而跨组池化会把不同收益分布的基金放进同一条相关系数里。

本草案按「`factor_effectiveness` 含 `peer_group_key` 与 `segment` 两列」实现。
**这需要 Task 7 在迁移 0016 里建出这两列**，而 Task 7 的实现者只看到 D-16 的清单，
不会知道。建议把这两列写进 Task 7 的需求。

顺带：D-16 说「`factor_effectiveness`（由 D-1 拉入）」，但计划的任务表里
Task 7 的标题是「`factor` schema **五张表**」，而 D-16 只列了四张
（`factor_definition` / `factor_version` / `factor_run` / `factor_effectiveness`）
外加 `factor_value` —— 数得上五张，但没有一处把五张表逐一点名，建议在 Task 7 里列全。

### ⑥ `peer_group_snapshot` 缺「所用分类版本」的落点 —— **影响 Task 8 建表**

`FR-PEER-001` Output 与 `01-system-architecture:839` 都要求 B1 = 「组成员 +
**所用分类版本**」，而 digest §3.2.1 明确记「其余字段（组规模、所用分类版本、
`evaluation_profile`、`min_sample_size` 引用…）**文档未给字段清单**」。
本草案的 `PeerGroupSnapshotWriter` 写 `classification_history_ids`
（`ARRAY(BigInteger)` 或 JSONB）。需要 Task 8 建出它，否则「所用分类版本」
无处安放，而 §10.1.1 说得很清楚：只存构建规则不存结果，历史 Peer Group 不可重建。

### ⑦ `fund.fund_share_class` 没有 `base_currency` 列 —— **阻塞 Task 11，且不在任何任务的 Files 里**

`FR:105` 把 Currency 定为 Peer Group 的强制划分维度，`FR:116` 要求它与 R_f 解析键
的 `currency` **取自同一字段 `fund_share_class.base_currency`**。Plan-1 落地的
`FundShareClass` 只有 7 列，没有这一列，全仓 `grep base_currency` 在 `src/` 下
零命中（`RiskFreeRate.currency` 是另一张表的另一列）。

这意味着 Task 11 必须包含一次 schema 变更（本草案写成迁移 0018），而计划的
File Structure 只列了 `0016（factor schema）`、`0017（evaluation schema）`。
另外 AKShare 的 `fund_name_em` **不提供币种**，所以它只能由一条【声明的推导规则】
填入（本草案：`PROVIDER_SCOPE_DECLARED` + 独立的 `base_currency_source` 列）。
需要裁决：这一列归 Task 11、还是提前到 Task 5 / Task 6 的灌数任务。

### ⑧ Threshold Resolver 在 File Structure 里没有落点

计划的 `libs/strategy_library/` 目录树列了 `factor/`、`peer_group/`、`score/`、
`ranking/`、`universe/`，**没有** threshold 或 policy 目录，而 Task 10 的产物
（MAR 三模式的纯逻辑）正属于策略领域逻辑。本草案落成
`libs/strategy_library/threshold/mar.py` + `services/factor_service/thresholds.py`
（前者纯、后者碰库）。需要在 File Structure 里补上。

### ⑨ D-9 的公式表只给了 9 条公式，`F-RET-002` Rolling Return 的聚合式缺失

D-9 的代码块列了 `r_t` / 年化收益率 / Volatility / Downside Vol / Max Drawdown /
Sharpe / Sortino / Calmar / Win Rate / Rolling Sharpe 稳定性 —— 唯独没有
Rolling Return。「滚动窗口的年化收益率」是一个**序列**，落成一个因子值需要一次
聚合（均值 / 中位数 / 末值 / 加权），四种选择的数值差异可观。
本草案补齐为 **均值**（PROVISIONAL，登记在 `metric/v1.yaml` 的
`factor.rolling_return_aggregation`）。需要确认。

同类的两个未给值：`rolling.window_days` / `step_days` 的**单位**（自然日还是
净值点数）——本草案取净值点数并改名为 `*_points`；以及 MAR 的**日频折算口径**
（简单除以 252 还是几何折算）——本草案取 `SIMPLE_DIVISION`。

### ⑩ 契约的 `percentile_rank` 无法单独承担 G-7 / G-8

契约签名是 `percentile_rank(values, direction) -> list[Decimal | None]`：
没有 `n_effective`、没有 Rank、没有 `min_peer_group_size`。而 G-7 要求按
`n_effective` 判 `INSUFFICIENT_SAMPLE`，G-8 要求 Rank / n_effective / Percentile
三者都落库。本草案把 `percentile_rank` 保留为**纯内核**（严格照契约），
另加 `normalize_peer_group` 承担排除 UNAVAILABLE、算 `n_effective`、判阈值、
产出三元组。若计划作者希望契约里就体现这一层，需要把 `normalize_peer_group`
提到接口契约节。

### ⑪ 计划的包路径与仓库现状不一致 —— 会在 Task 9 第一行 import 就炸

计划 File Structure 与 D-3 写的是 `src/fip/libs/quant_engine` /
`src/fip/libs/strategy_library`，仓库里是 `src/fip/quant_engine` /
`src/fip/strategy_library`（Plan-1 建的空包），并且
`tests/unit/test_package_layout.py::test_all_layer_packages_importable`
与 `tests/fitness/test_architecture.py`（`_py_files("strategy_library")`、
`GUARDED_ROOTS`）都按现状写死。Task 4「strategy_library 骨架」必须把搬迁与这两个
测试的同步列为显式步骤，否则 Task 9 的实现者会在两条路径之间自行选一条。

### ⑫ 现有 `config/policy/evaluation/v1.yaml` 里的 `mar.default: 0.0` 直接违反 G-6

这不是遗漏而是**已经存在的违规**：`FE:474` 逐字写着「`ZERO` 是第一版推荐取值，
不是不填时的兜底」，而一个叫 `mar.default` 的配置项语义就是兜底。Task 10 Step 2
删除它。登记在此是因为它在 Plan-1 就已入库，任何「照着现有配置写」的实现者
都会把它读进来。

### ⑬ 两条更小的登记

- **`risk_free_rate_ref` 的四个必备字段不含 `curve_code`**（digest §9.2.1）。
  但 Plan-1 的 `RiskFreeRate` 主键第一列就是 `curve_code`，中债同一天有三条曲线，
  实测信用债 10Y 比国债高约 30bp。缺了它，溯源无法回答「这个 Sharpe 用的是哪条
  曲线」。本草案补为第五个字段。
- **`ParsedYieldPoint` 不带 `currency`**，而 `RiskFreeRate` 的主键含它。
  Plan-1 交接只说「`curve_code` 与 `RiskFreeRate.curve_code` 只在结构上对齐，
  未端到端跑通」，没提这个空档。本草案在适配器层补 `CURVE_CURRENCIES` 映射 ——
  「这条曲线是什么币种」属于曲线的身份，不能让灌数编排现编。
