# Plan-2 实现计划 · M1.2 Peer Group + M1.3 因子 + M1.4 评价与候选池

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan-1 的 PIT 地基上建起计算流——从复权净值算出 10 个因子，
在 Peer Group 内标准化，产出五子分与归因，再据 Eligibility Rules 产出候选池快照。

**Architecture:** 填实 Plan-1 已建骨架的两个架构层——Quant Engine
（`src/fip/quant_engine`，数值，无业务语义）与 Strategy Library
（`src/fip/strategy_library`，策略领域逻辑，不含数据访问、无 runtime_mode 分支），
两个 Domain Service `factor_service`（写 `factor` schema）与 `fund_service`（写
`evaluation` schema）。计算全部为纯函数，数据经 Plan-1 的 PIT 端口注入。

**Tech Stack:** Python 3.12 · SQLAlchemy 2.x · Alembic · PostgreSQL 17 · numpy · Decimal

**Spec:** `docs/superpowers/specs/2026-09-02-plan2-factor-and-evaluation-design.md`
（21 条裁定与补齐）
**上游抽取**：`plan2-digest-factor-scoring.md`、`plan2-digest-universe-schema.md`
**Plan-1 交接**：`docs/superpowers/plans/2026-09-02-plan1-handoff.md`

## Global Constraints

每一条都是可验收项，非建议。任务的需求隐含包含本节全部内容。

| # | 约束 |
|---|---|
| G-1 | `available_at <= decision_at` 是唯一可见性规则。`effective_at <= decision_at` 是错的，会造成静默前视偏差 |
| G-2 | 因子值 / Score 的可复现性容差 **1e-10**；同一输入重算必须一致 |
| G-3 | `UNAVAILABLE` 不得被任何填充值替代——不得填 0、上期值、`inf`、组内均值 |
| G-4 | `data_completeness` 是**输出必备字段**，必须随 Score 一起呈现 |
| G-5 | Peer Group 构建**不得** import 评分 / Universe 模块（适应度测试断言） |
| G-6 | `mar_policy` 必填无默认；未配置则 `F-RISK-002` / `F-RAP-002` 一律 `UNAVAILABLE` |
| G-7 | `MIN_PEER_GROUP_SIZE = 30`，判定基数是 `n_effective` **不是**组规模；标准化 / 排名 / 分层三处必须同一配置源 |
| G-8 | `Rank` / `n_effective` / `Percentile` **三者都必须落库** |
| G-9 | `Fund Tier` 不得单独输出，必须与组内 Sharpe 中位数 + MDD 中位数同屏 |
| G-10 | 同一 Peer Group 内多个 Profile 时按 Profile 拆分子排名 |
| G-11 | `REJECTED` 成员与**全部**条件结果落库；条件求值**不得短路** |
| G-12 | SDL-1/2/3 与 QE-1 各配适应度测试 |
| G-13 | SB-1：每个 schema 写入权唯一（`factor` ← factor_service，`evaluation` ← fund_service） |
| G-14 | 所有【补齐】项在配置中标 `PROVISIONAL` 并指向设计定案文档 |
| G-15 | C-12：任何时间戳不得回填/伪造。AKShare 链路一律 `INFERRED`，另两列保持 NULL |
| G-16 | 凡迁移里建的约束/索引，ORM `__table_args__` 必须同时声明；收工时 `alembic revision --autogenerate` 必须报告零操作 |
| G-17 | CHECK 约束的防线是 `tests/integration/check_constraints.snapshot` 黄金快照，**不是** autogenerate（后者对 CHECK 表达式失明）。改约束后必须重新生成快照 |
| G-18 | 每条新测试都必须**先证伪**——在修复/实现前实际跑一遍确认失败，并把失败输出写进报告 |

## 分层与依赖方向

```
platform/api → services/* → strategy_library → quant_engine
services/*, strategy_library → platform/decision_data（接口）
```

反向依赖视为设计错误，由适应度测试拦截。

## File Structure

```
src/fip/
├── quant_engine/            # L1 数值层——矩阵、统计、时序。无业务语义
│   ├── stats.py             #   stdev/mean/median/percentile（Decimal 精度契约）
│   ├── series.py            #   收益率序列、滚动窗口、running max
│   └── correlation.py       #   Spearman / Pearson（IC 用）
└── strategy_library/        # L1 策略领域逻辑（Plan-1 已建空包）
    ├── factor/
    │   ├── definitions.py   #   10 个因子的身份与 Preference Direction
    │   ├── compute.py       #   10 个因子的纯函数
    │   ├── status.py        #   FactorStatus 四值与生产方触发条件
    │   ├── normalize.py     #   Peer Group 内 Percentile Rank + 方向转换
    │   └── effectiveness.py #   IC / ICIR 与 VALID/INVALID 判定
    ├── peer_group/build.py  #   Peer Group 构建（不 import score/universe）
    │                        #   【Task 11 必须同时改写 C-4 两条测试，见 P2-2】
    ├── score/
    │   ├── subscore.py      #   五子分
    │   ├── attribution.py   #   归因明细（含 invalid 因子留痕）
    │   └── completeness.py  #   Data Completeness
    ├── ranking/rank.py      #   COMPETITION_RANK + Percentile + Tier 五档
    └── universe/rules.py    #   Eligibility Rules 求值（不得短路）

src/fip/services/
├── factor_service/          # 写 factor schema
└── fund_service/            # 写 evaluation schema

db/migrations/versions/      # 0016（交接项四的三处约束）、0017（分类表开放区间索引）
                             # 0018（factor）、0019（evaluation）、0020（base_currency）
config/strategy/metric/v1.yaml       # 因子口径（追加）
config/strategy/factor/v1.yaml       # 因子清单与 Factor Usage（新建）
config/policy/evaluation/v1.yaml     # MAR / peer_group 粒度 / 阈值（追加）
config/policy/validation/v1.yaml     # IC/ICIR 阈值（新建）
```

## 任务总览与接口契约

> **接口契约由本计划统一给定。** 每个任务的实现者只看到自己那一节，
> 因此凡跨任务使用的名字、签名与类型，一律在此定义，任务内不得另行发明。

| # | 任务 | 依赖 | 迁移 |
|---|---|---|---|
| 1 | Plan-1 交接：`visible_until` 归位 + IntervalMixin 生成器适应度测试 + **交接项四的三处约束**（P2-3）+ **autogenerate 闸门自动化**（P2-10）+ **`derive_eligibility` 两分支互换的修正**（D-22） | — | **0016** |
| 2 | 收紧 PIT 数据契约：`NavPoint` 类型收窄 + 链路 quality 聚合（`NavSeries`） | 1 | — |
| 3 | `quant_engine` 填实 + QE-1 适应度测试（**不搬迁包**，P2-1） | — | — |
| 4 | `strategy_library` 骨架 + SDL-1/2/3 适应度测试（SDL-1 补 `fip.services.*` 前缀，D-27）+ Code Version 计算 | 3 | — |
| 5 | 基金分类灌入（`基金类型` → `fund_classification_history`） | 4 | **0017** |
| 6 | 批量灌数 ≥300 份额类别；`AdjustedNavUnavailable` 保护下沉到 service | 5 | — |
| 7 | `factor` schema 五张表（含 `quality_flag` P2-21、`peer_group_key`/`segment` P2-24、`curve_code` P2-30） | — | **0018** |
| 8 | `evaluation` schema 九张表（含 `classification_history_ids` P2-25；三张表唯一键含 Profile D-28） | 7 | **0019** |
| 9 | 10 个因子的纯函数 + Metric Version 登记（`mar_daily` P2-22、`quality_flag` P2-21、`FACTOR_IDS`/`PROFILE_DECLARED_FACTOR_IDS` D-24） | 3, 4 | — |
| 10 | Threshold Resolver（R_f 灌数 + PIT 解析 + MAR 三模式 `ZERO`/`CUSTOM`/`RISK_FREE`）+ **删除 `mar.default`**（P2-4） | 4, 7 | — |
| 11 | Peer Group 构建与 B1 快照原子写入 + **改写 C-4 两条测试**（P2-2） | 5, 8 | **0020** |
| 12 | 因子标准化（`percentile_rank` 内核 + `normalize_peer_group` 承担 n_effective/rank/三元组，P2-28；**+ `transpose_to_fund_view` 转置函数，PF-2**） | 9, 11 | — |
| 13 | 因子有效性检验（IC / ICIR，按 `peer_group_key` × `segment` 分组，P2-24） | 12 | — |
| 14 | 五子分 + 归因 + Data Completeness（分母取 13，D-24；`sub_score_weights` 五项各 0.2 标 PROVISIONAL，D-23；`score_status` 优先级 D-25） | 13 | — |
| 15 | 排名 / 分位 / Fund Tier | 14 | — |
| 16 | Eligibility Rules + B2 候选池快照（含 REJECTED）；`data_completeness_floor` 在 M1 取 **0.75/PROVISIONAL**（Ruling PF-4，见该任务开头） | 15 | — |
| 17 | `factor_service` / `fund_service` 装配 + SB-1 适应度测试 | 16 | — |
| 18 | CLI 与端到端验收（A-2 期望 `data_completeness = 0.76923077`，与 D-24 联动，D-29） | 17 | — |

**迁移链**（连续、无跳号、无重复；`down_revision` 依次相连）：

```
0015 (Plan-1 head)
  └─ 0016  Task 1   交接项四：fund_manager_assignment 的 EXCLUDE + 两索引、
  │                 fund_fee / fund_status_history 的开放区间部分唯一索引
  └─ 0017  Task 5   fund_classification_history 的开放区间唯一索引
  └─ 0018  Task 7   factor schema 五张表
  └─ 0019  Task 8   evaluation schema 九张表 + factor_value 的 FK 回补
  └─ 0020  Task 11  fund_share_class.base_currency + base_currency_source
```

### 跨任务接口契约（**唯一权威定义**）

> 每个任务的实现者只看到自己那一节，因此凡跨任务使用的名字、签名与类型，
> **一律在此定义，任务内不得另行发明**。本节与任务正文冲突时以本节为准；
> 本节与设计定案 spec 冲突时以 spec 为准。
>
> 本节末尾有一节 **【四份草稿间的九处冲突】** —— 那九个名字曾在四份并行草稿里
> 各说各话，controller 已逐条裁定（PF-1..PF-8），**正文已按裁定改完**。
> 那一节保留冲突描述作为记录：将来有人问「为什么是这个签名 / 这个值」，
> 能查到当初分歧是什么、裁定取了哪一边、代价是什么。

```python
# ====================================================================
# quant_engine（Task 3 产出，Task 9 / 12 / 13 消费）
#   落位 src/fip/quant_engine/ —— Plan-1 已建的空包，就地填实，【不搬迁】（P2-1）
# ====================================================================
def returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]: ...
def stdev(xs: Sequence[Decimal], ddof: int) -> Decimal: ...
def mean(xs: Sequence[Decimal]) -> Decimal: ...
def median(xs: Sequence[Decimal]) -> Decimal: ...
def running_max(xs: Sequence[Decimal]) -> list[Decimal]: ...
def rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]: ...
def spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal: ...

QE_PRECISION: int = 60
QE_GUARD_DIGITS: int = 60
SIMPLE: str = "SIMPLE"                      # 收益率口径字面量

class QuantEngineError(ValueError): ...     # 基类
class InsufficientObservations(QuantEngineError): ...
class MathematicallyUndefined(QuantEngineError): ...
class UnsupportedBasis(QuantEngineError): ...
# 异常 → status 的映射【由调用方按情形判定】（P2-20 修订 D-10）：
#   InsufficientObservations           → UNAVAILABLE(INSUFFICIENT_HISTORY)
#   MathematicallyUndefined / 分母为 0          → UNAVAILABLE(ZERO_*)      ← 良性不可算
#   MathematicallyUndefined / 负方差 / NaN      → INVALID                  ← 数值链路坏了
#   UnsupportedBasis                    → 抛出，不得吞成任何 status

# ====================================================================
# Task 2 产出（Task 9 / 17 消费）—— PIT 净值序列
# ====================================================================
@dataclass(frozen=True, slots=True)
class NavSeries:
    points: tuple[NavPoint, ...]
    chain_quality: str | None       # 空序列 ⟺ None（__post_init__ 双向锁死，P2-6）
def weakest_quality(qs: Iterable[str]) -> str | None: ...
    # EXACT > DERIVED > INFERRED，取最弱者；空输入返回 None
NavPitRepository.adjusted_nav_series(share_class_id, date_from, date_to) -> NavSeries

# ====================================================================
# Task 4 产出（SDL-3；Task 17 / 18 消费）—— Code Version
# ====================================================================
CODE_VERSION_ROOTS: tuple[pathlib.Path, ...]   # = (src/fip/quant_engine, src/fip/strategy_library)
def compute_code_version(roots: Iterable[pathlib.Path] | None = None) -> str: ...
    # 全仓 code_version 此前只是 DecisionExecutionContext 上的字面量 "cli"

# ====================================================================
# Task 4 产出，Task 5 / 11 消费（住 strategy_library/peer_group，P2-5）
# ====================================================================
CLASSIFICATION_SCHEME: str = "AKSHARE_FUND_TYPE"
UNCLASSIFIED_CODE: str = "UNCLASSIFIED"
def level_1(classification_code: str) -> str: ...        # "混合型-偏股" -> "混合型"
def is_groupable(classification_code: str) -> bool: ...  # UNCLASSIFIED 返回 False

# ====================================================================
# strategy_library/factor —— 契约类型（Task 4 建，Task 9 填实）
# ====================================================================
class FactorStatus(StrEnum):
    VALID = "VALID"; WARNING = "WARNING"; INVALID = "INVALID"; UNAVAILABLE = "UNAVAILABLE"
    # P2-21：WARNING 的【唯一】触发条件是「观测数落在 [min_obs, min_obs*1.5)」。
    #        「链路含 INFERRED」已删除 —— AKShare 链路 100% INFERRED（G-15），
    #        留着它会让 VALID 在 M1 完全不可达。
    # P2-20：分母为 0（ZERO_MAX_DRAWDOWN / ZERO_VOLATILITY / ZERO_DOWNSIDE_VOLATILITY）
    #        属 UNAVAILABLE，【不是】INVALID。INVALID 只留给 NaN / 负方差 / 序列自相矛盾。

class WarningReason(StrEnum):
    NEAR_MIN_OBS = "NEAR_MIN_OBS"           # P2-21：只剩这一个值

class UnavailableReason(StrEnum):           # 10-api/03 §4.3.5 八类 + 一条补齐
    INSUFFICIENT_HISTORY; BENCHMARK_UNAVAILABLE; RISK_FREE_RATE_UNAVAILABLE
    MAR_NOT_CONFIGURED; ZERO_MAX_DRAWDOWN; ZERO_DOWNSIDE_VOLATILITY
    ZERO_TRACKING_ERROR; ZERO_VOLATILITY
    MAR_SERIES_INCOMPLETE                   # 【补齐】RISK_FREE 模式下某期 R_f 缺失

class InvalidReason(StrEnum):
    NON_FINITE = "NON_FINITE"; NEGATIVE_VARIANCE = "NEGATIVE_VARIANCE"

class PreferenceDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"; LOWER_IS_BETTER = "LOWER_IS_BETTER"

@dataclass(frozen=True, slots=True)
class FactorInput:
    """因子计算的全部输入。纯函数只吃它，不碰数据库（SDL-1）。"""
    effective_at: date                      # = decision_at
    adjusted_navs: tuple[Decimal, ...]      # 按日期升序，已按 PIT 解析
    nav_dates: tuple[date, ...]
    chain_quality: str                      # Task 2 的 NavSeries.chain_quality
    risk_free_rate: Decimal | None          # None 表示不可解析
    mar_daily: tuple[Decimal, ...] | None   # 【P2-22】逐期序列，与收益率序列 1:1 对齐
                                            # （长度 = len(adjusted_navs) - 1）；
                                            # None = mar_policy 未配置 或 R_f 序列不完整。
                                            # **不是** 标量 `mar: Decimal | None`

@dataclass(frozen=True, slots=True)
class FactorResult:
    factor_id: str
    value: Decimal | None                   # UNAVAILABLE / INVALID 时为 None，【绝不填 0】
    status: FactorStatus
    reason: str                             # status 非 VALID 时必填
    observation_count: int
    quality_flag: str                       # 【P2-21】EXACT / DERIVED / INFERRED，
                                            # 与 status 正交，随结果传递不参与判定

def compute_factor(factor_id: str, inp: FactorInput) -> FactorResult: ...
def observation_status(observation_count: int, min_obs: int) -> tuple[FactorStatus, str]: ...
    # ⚠️ 【无】chain_quality 参数（P2-21）

# ---- 因子身份（Task 9 产出，Task 12 / 14 / 17 消费）----
FACTORS: dict[str, FactorDefinition]                  # 10 条，键为 Factor ID
FACTOR_IDS: tuple[str, ...]                           # 【D-24】可算的 10 个 = tuple(FACTORS)
REL_DECLARED_ONLY_FACTOR_IDS: tuple[str, ...]         # ("F-REL-002","F-REL-003","F-REL-004")
PROFILE_DECLARED_FACTOR_IDS: tuple[str, ...]          # 【D-24】声明的 13 个 = 10 + 3
def preference_direction(factor_id: str) -> PreferenceDirection: ...
# ⚠️ D-24：这是【两个不同的常量】，不得合并。data_completeness 的分母取
#    PROFILE_DECLARED_FACTOR_IDS（13）。只定义 FACTOR_IDS 的话分母会静默变回 10，
#    M1 的 completeness 恒为 1.0，spec §6.2「4 个子分的 85 分与 5 个子分的 85 分
#    必须可区分」被静默抹掉，Task 18 的 A-2 退化成恒真判据（D-29）。

# ====================================================================
# strategy_library/threshold（Task 10 产出，Task 9 / 17 消费）
# ====================================================================
class MarPolicy(StrEnum):
    ZERO = "ZERO"; CUSTOM = "CUSTOM"; RISK_FREE = "RISK_FREE"
    # 【P2-23】第三模式逐字取上游 §16.3 的 CUSTOM，**不是** FIXED；
    #          CUSTOM 必填 mar_quotation_basis

@dataclass(frozen=True, slots=True)
class MarResolution:
    policy: MarPolicy | None
    annualized: Decimal | None                          # ZERO / CUSTOM
    series: tuple[tuple[date, Decimal], ...] | None     # RISK_FREE
    quotation_basis: str | None                         # CUSTOM 必填
    unavailable_reason: str | None

def resolve_mar(policy_name: str | None, custom_value: Decimal | None,
                mar_quotation_basis: str | None,
                risk_free_series: Sequence[tuple[date, Decimal]] | None) -> MarResolution: ...
def mar_daily_series(res: MarResolution, period_dates: Sequence[date],
                     periods_per_year: int = 252) -> tuple[Decimal, ...] | None: ...
    # 【P2-22】三模式统一产出逐期序列，消费方【不分支】：
    #   ZERO      → 全零序列（这是显式决策，不是填充）
    #   CUSTOM    → 常数序列（按 mar_quotation_basis 声明的年化口径折算）
    #   RISK_FREE → 真实的 R_f 逐期序列 —— M1 【可用】，不再登记为缺口
    # 起草期的 mar_for_factor_input(res) -> (Decimal|None, str|None) 已【作废】

# ---- services/factor_service/thresholds（装配层，碰库）----
@dataclass(frozen=True, slots=True)
class RiskFreeRateRef:
    curve_code: str      # 【P2-30 第五字段，补】上游 §9.2.1 只给四个；中债同一天
                         # 三条曲线（实测信用债 10Y 高约 30bp），缺它答不出用了哪条
    currency: str; tenor: str; version: int; rate_source_quality: str

@dataclass(frozen=True, slots=True)
class ResolvedThresholds:
    risk_free_rate: Decimal | None
    risk_free_rate_ref: RiskFreeRateRef | None
    mar_daily: tuple[Decimal, ...] | None       # 【P2-22】直接就是 FactorInput.mar_daily
    mar_unavailable_reason: str | None
    mar_policy: MarPolicy | None

class ThresholdResolver:
    def __init__(self, rates: RiskFreeRatePitRepository, config: ConfigSet) -> None: ...
    def resolve(self, base_currency: str, date_from: date, date_to: date,
                period_dates: Sequence[date]) -> ResolvedThresholds: ...

# ---- 适配器层（Task 10）----
CURVE_CURRENCIES: dict[str, str]    # 【P2-30】{"CN_TREASURY":"CNY","CN_MTN_AAA":"CNY",
                                    #           "CN_BANK_AAA":"CNY"}
RISK_FREE_CURVE_CODE: str = "CN_TREASURY"
# ParsedYieldPoint 【不加】currency 字段 —— 币种由 CURVE_CURRENCIES 在适配器层补，
# 不让 ingest 现编（「这条曲线以什么计价」属于「这条曲线是什么」）。

# ====================================================================
# strategy_library/peer_group（Task 11 产出，Task 12 / 13 / 17 消费）
# ====================================================================
@dataclass(frozen=True, slots=True)
class PeerGroupKey:
    classification_scheme: str      # "AKSHARE_FUND_TYPE"
    classification_code: str        # L1 或 L2，由 peer_group.classification_level 决定
    base_currency: str              # 与 R_f 解析用的是【同一字段】fund_share_class.base_currency
    def key_string(self) -> str: ...   # f"{scheme}|{code}|{currency}"
                                       # 与 factor_effectiveness.peer_group_key 同形（P2-24）

class ClassificationLevel(StrEnum): L1 = "L1"; L2 = "L2"
class ExclusionReason(StrEnum):
    UNCLASSIFIED_CODE; CLASSIFICATION_MISSING; CURRENCY_UNKNOWN

@dataclass(frozen=True, slots=True)
class PeerGroupCandidate:
    share_class_id: int
    classification_scheme: str | None
    classification_code: str | None
    classification_history_id: int | None
    base_currency: str | None

@dataclass(frozen=True, slots=True)
class PeerGroupBuild:
    groups: Mapping[str, tuple[int, ...]]           # key_string -> 成员 share_class_id
    classification_history_ids: tuple[int, ...]     # 【P2-25】「所用分类版本」，落 B1
    exclusions: tuple[tuple[int, ExclusionReason], ...]

MIN_PEER_GROUP_SIZE_CONFIG_PATH: str = "peer_group.min_peer_group_size"
# G-7：标准化 / 排名 / 分层三处必须同一配置源，由 tests/fitness/test_single_config_source.py 钉住

# ====================================================================
# strategy_library/factor/normalize（Task 12 产出，Task 13 / 17 消费）
# ====================================================================
class CrossSectionStatus(StrEnum): NORMAL = "NORMAL"; INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"

def competition_ranks(values: Sequence[Decimal]) -> list[int]: ...
def percentile_rank(values: Sequence[Decimal], direction: PreferenceDirection
                    ) -> list[Decimal | None]: ...
    """【纯内核，P2-28 明令保持不动】Peer Group 内分位。
    p = (N - Rank) / (N - 1) * 100，COMPETITION_RANK。
    N == 1 时返回 None（不是 50、不是 100）。LOWER_IS_BETTER 先取负再排。"""

@dataclass(frozen=True, slots=True)
class NormalizedFactorValue:            # 【横截面视图】：一个因子、多只基金
    share_class_id: int
    factor_id: str
    raw_value: Decimal | None
    rank: int | None
    n_effective: int
    percentile: Decimal | None
    cross_section_status: CrossSectionStatus     # NORMAL / INSUFFICIENT_SAMPLE
    factor_status: FactorStatus                  # 【PF-1】原样透传自 FactorResult
    reason: str                                  # 【PF-1】原样透传自 FactorResult
    direction: PreferenceDirection               # 【PF-1】本次标准化用的方向

def normalize_peer_group(entries: Sequence[tuple[int, FactorResult]],
                         direction: PreferenceDirection,
                         min_peer_group_size: int) -> list[NormalizedFactorValue]: ...
    """【P2-28 + Ruling PF-1】承担 percentile_rank 之上的那一层：
    排除 UNAVAILABLE/INVALID → 算 n_effective → 判 INSUFFICIENT_SAMPLE
    → 产出 (rank, n_effective, percentile) 三元组（G-8 要求三者都落库）。
    D-26：N == 1 归入 INSUFFICIENT_SAMPLE。

    【本函数是 G-8 三元组（rank / n_effective / percentile）的唯一权威产出点】——
    Task 15 与 Task 17 一律消费它，不得各自再算一遍。Task 17 起草期那条
    「直接调 percentile_rank」的路径已删除：它三样都不产出，落库会是空的。

    输入取【最富的形态】`(share_class_id, FactorResult)`：FactorResult 带着
    status 与 reason，于是下游能回答「为什么这只基金的这个因子没参与」——
    那正是 D-23 / 归因链要求的。入参若退化成 `Decimal | None`，reason 就丢了。"""

def transpose_to_fund_view(by_factor: Mapping[str, Sequence[NormalizedFactorValue]],
                           *, window: str) -> dict[int, dict[str, NormalizedFactor]]: ...
    """【Ruling PF-2】横截面视图 → 归因视图的【转置】。

    NormalizedFactorValue 与 NormalizedFactor 不是重复，是同一份计算的两个视图：
    前者按 share_class_id 组织（一个因子、多只基金 → rank/percentile），
    后者按 factor_id 组织（一只基金、多个因子 → raw/normalized/reason）。
    标准化天然产出前者，评分与归因需要后者。真正缺的不是「合并」而是转置。

    入参键为 factor_id，值为该因子在本 Peer Group 内的全部
    NormalizedFactorValue；返回 share_class_id → {factor_id: NormalizedFactor}。
    `window` 是关键字参数：window 进因子身份（D-13）但【不在】FactorResult 上，
    只有调用方知道本次算的是哪个窗口。

    ⚠️ Task 17【不得】自己构造 NormalizedFactor，必须消费本函数的返回值。"""

# ====================================================================
# strategy_library/factor/effectiveness（Task 13 产出，Task 14 消费）
# ====================================================================
@dataclass(frozen=True, slots=True)
class EffectivenessResult:
    factor_id: str
    peer_group_key: str          # 【P2-24】IC 是横截面统计量，横截面就是 Peer Group
    segment: str                 # 【P2-24】检验分段；M1 恒 "FULL"
    ic: Decimal | None
    icir: Decimal | None
    n_periods: int
    is_valid: bool
    reason: str
# 落 factor.factor_effectiveness；peer_group_key 与 segment 【进】Business Key。

# ====================================================================
# strategy_library/score（Task 14 产出，Task 15 / 16 / 17 消费）
# ====================================================================
class ScoreStatus(StrEnum):
    COMPLETED = "COMPLETED"; PARTIAL = "PARTIAL"; UNAVAILABLE = "UNAVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"; INSUFFICIENT_FACTORS = "INSUFFICIENT_FACTORS"

FUND_SCORE_STATUS_PRIORITY: tuple[ScoreStatus, ...]
    # 【D-25】基金层优先级，越靠前越强：
    #   VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS > PARTIAL > COMPLETED
    # 同一枚举用于子分层与基金层，取值含义一致。M1 常态是 PARTIAL（REL 恒缺），
    # 必须有测试显式断言它是【正常】的。

class SubScoreName(StrEnum):
    RETURN = "Return"; RISK = "Risk"; RISK_ADJUSTED = "Risk-Adjusted"
    STABILITY = "Stability"; RELATIVE_PERFORMANCE = "Relative Performance"

class WeightSource(StrEnum):
    EQUAL_WITHIN_VALID = "EQUAL_WITHIN_VALID"; OPTIMIZED = "OPTIMIZED"

@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    profile_id: str
    declared_factors: Mapping[SubScoreName, tuple[str, ...]]   # 【声明】13 个（D-24）
    sub_score_weights: Mapping[SubScoreName, Decimal]          # 【D-23】五项各 0.2，
                                                               # status PROVISIONAL，
                                                               # source「上游禁止拍板但未给值」
    min_valid_factors_per_sub_score: int                       # 2（FS §9.3 已定案）

@dataclass(frozen=True, slots=True)
class NormalizedFactor:            # 【归因视图】：一只基金、多个因子
    # 【Ruling PF-2】与 NormalizedFactorValue 是【两个】类型，两个都保留 ——
    # 它们是同一份计算的两个视图，由 Task 12 的 transpose_to_fund_view 相连。
    factor_id: str
    window: str
    raw_value: Decimal | None
    normalized_score: Decimal | None
    status: FactorStatus
    direction: PreferenceDirection
    reason: str

@dataclass(frozen=True, slots=True)
class FactorAttribution:
    factor_id: str; window: str
    raw_value: Decimal | None; normalized_score: Decimal | None
    direction: PreferenceDirection
    weight: Decimal; weighted_contribution: Decimal | None
    exclusion_reason: str | None
    redistributed_to: tuple[str, ...]
    effectiveness_verdict: str          # VALID / INVALID / NOT_TESTED

@dataclass(frozen=True, slots=True)
class SubScoreResult:
    name: SubScoreName; value: Decimal | None; status: ScoreStatus
    weight_source: WeightSource
    applied_weight: Decimal | None
    attributions: tuple[FactorAttribution, ...]

@dataclass(frozen=True, slots=True)
class FundScoreResult:
    profile_id: str; total_score: Decimal | None; status: ScoreStatus
    data_completeness: Decimal            # 分母 = len(PROFILE_DECLARED_FACTOR_IDS) = 13
    sub_scores: tuple[SubScoreResult, ...]

def compute_sub_score(name, declared_factor_ids, factors, effectiveness,
                      min_valid_factors) -> SubScoreResult: ...
def compute_fund_score(profile: EvaluationProfile,
                       factors: Mapping[str, NormalizedFactor],
                       effectiveness: Mapping[str, FactorEffectiveness]
                       ) -> FundScoreResult: ...
def data_completeness(profile: EvaluationProfile,
                      sub_scores: Sequence[SubScoreResult]) -> Decimal: ...
    # M1 恒为 10/13 = 0.76923077（D-24 / D-29）

# ====================================================================
# strategy_library/ranking（Task 15 产出，Task 16 / 17 消费）
# ====================================================================
class TieMethod(StrEnum): COMPETITION_RANK; DENSE_RANK; ORDINAL_RANK
class FundTierLevel(StrEnum): A_PLUS = "A+"; A = "A"; B = "B"; C = "C"; D = "D"
    # 【Ruling PF-3】档位枚举叫 FundTierLevel；ORM 类叫 FundTier（Task 8）。
    # Task 17 起草期的 FundTierRow 已删除。

@dataclass(frozen=True, slots=True)
class RankingEntry:
    share_class_id: int; profile_id: str; metric_value: Decimal | None

@dataclass(frozen=True, slots=True)
class RankingResult:
    share_class_id: int; profile_id: str
    rank: int | None; percentile: Decimal | None
    n_effective: int; peer_group_size: int
    ranking_status: CrossSectionStatus; tie_method: TieMethod

@dataclass(frozen=True, slots=True)
class TierThresholds:
    a_plus: Decimal; a: Decimal; b: Decimal; c: Decimal      # 阈值配置化（C-1），不进 CHECK（P2-18）

@dataclass(frozen=True, slots=True)
class PeerGroupAbsoluteLevel:
    sharpe_median: Decimal | None; max_drawdown_median: Decimal | None
    # G-9：Fund Tier 不得单独输出。两个中位数落 fund_tier【每行自带】（P2-15 / D-28）

@dataclass(frozen=True, slots=True)
class TierResult:
    share_class_id: int; profile_id: str
    tier: FundTierLevel | None; percentile: Decimal | None
    rank: int | None; n_effective: int; total_score: Decimal | None
    classification_status: CrossSectionStatus
    peer_group_level: PeerGroupAbsoluteLevel        # 无默认值，G-9 的结构化落地

def rank_within_peer_group(entries, *, peer_group_size, min_peer_group_size
                           ) -> list[RankingResult]: ...
def assign_tier(ranking, *, total_score, thresholds, peer_group_level,
                min_peer_group_size) -> TierResult: ...
def peer_group_absolute_level(sharpe_values, mdd_values) -> PeerGroupAbsoluteLevel: ...

# ====================================================================
# strategy_library/universe（Task 16 产出，Task 17 消费）
# ====================================================================
class ConditionStatus(StrEnum): PASS; FAIL; NOT_EVALUABLE   # 【P2-17】第三值：输入
                                                            # UNAVAILABLE 所以判不了，
                                                            # 记成 FAIL 是编造否定结论
class SelectionStatus(StrEnum): SELECTED; REJECTED
class Operator(StrEnum): GTE; LTE; IN; NOT_IN
class EligibilityAction(StrEnum): ADMIT; ADMIT_WITH_CONSTRAINT; EXCLUDE
SELECTABLE_FIELDS: frozenset[str]

@dataclass(frozen=True, slots=True)
class Condition:
    condition_id: str; field: str; operator: Operator
    threshold: Decimal | tuple[str, ...]

@dataclass(frozen=True, slots=True)
class CandidateFacts:
    share_class_id: int
    investment_eligibility: str | None      # Task 1 修正后的 derive_eligibility 产出（D-22）
    evaluation_status: str | None
    data_completeness: Decimal | None
    total_score: Decimal | None
    percentile: Decimal | None
    fund_tier: str | None
    def value_of(self, field: str) -> object | None: ...

@dataclass(frozen=True, slots=True)
class ConditionResult:
    condition_id: str; condition_version: str; status: ConditionStatus
    actual_value: str | None; gap: Decimal | None

@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    share_class_id: int; selection_status: SelectionStatus
    condition_results: tuple[ConditionResult, ...]     # 【G-11】全部条件，不得短路
    constraint_note: str | None

def evaluate_condition(condition, facts, condition_version) -> ConditionResult: ...
def evaluate_all(conditions, facts, condition_version) -> tuple[ConditionResult, ...]: ...
def select(facts, conditions, condition_version, eligibility_handling) -> SelectionOutcome: ...

# ====================================================================
# services 层的写入口（Task 11 / 16 / 17；G-13 SB-1：schema 写入权唯一）
# ====================================================================
class PeerGroupSnapshotWriter:      # fund_service → evaluation schema
    def __init__(self, session: Session, *, classification_level: str,
                 classification_policy_version: str, peer_group_policy_version: str,
                 code_version: str) -> None: ...
        # 【PF-7】四个都是 peer_group_snapshot 的 NOT NULL 列，构造期注入
    def write_b1(self, effective_at: date, build: PeerGroupBuild) -> dict[str, int]: ...
class PeerGroupSnapshotMissing(RuntimeError): ...
class UniverseSnapshotWriter:       # fund_service → evaluation schema
    def write(self, *, decision_at, peer_group_snapshot_id, selection_policy_version,
              condition_version, min_universe_size, outcomes, eligibility_refs) -> int: ...

# ---- Investment Eligibility（Task 1 修正，Task 16 消费）----
def derive_eligibility(lifecycle: LifecycleStatus, subscription_open: bool,
                       redemption_open: bool) -> EligibilityStatus: ...
    """【D-22 修正后】的语义：
         暂停赎回（sub=True, red=False） → NOT_TRADABLE
         暂停申购（sub=False, red=True） → HOLD_ONLY
       本函数【永不】返回 EXIT_ONLY（生命周期条件，两个布尔推不出）
       与 LIMITED（需要配额/限购这第三维输入）—— 两处已登记缺口。"""
```

#### 【四份草稿间的九处冲突】—— **已由 controller 逐条裁定，本节记录裁定与理由**

> 以下名字在四份并行草稿里**给了不同的签名或不同的形状**。
> 权威裁定见
> `.superpowers/sdd/2026-09-02-plan2-factor-and-evaluation/progress.md`
> 的「Pre-flight 冲突扫描」PF-1..PF-8（⑨ 与 ① 合并裁定）。
>
> **冲突描述原样保留**，不是历史包袱而是记录：将来有人问
> 「为什么 `normalize_peer_group` 是这个签名」「为什么 M1 的 floor 是 0.75」，
> 能在这里查到当初分歧是什么、裁定取了哪一边、代价是什么。
> **计划正文已按裁定改完**，本节与正文若再有出入，以正文为准并回报 controller。

| # | 名字 | 当初的分歧 | 裁定 |
|---|---|---|---|
| ① | `normalize_peer_group` | **P2-28 的示意签名**：`(results: Sequence[FactorResult], direction, min_size) -> list[NormalizedFactor]`。**Task 12 草稿的签名**：`(entries: Sequence[tuple[int, Decimal \| None]], direction, min_peer_group_size) -> list[NormalizedFactorValue]`。前者吃因子结果对象、返回「归因视图」；后者吃 `(share_class_id, 值)` 二元组、返回「横截面视图」。两者的**输入类型、返回类型都不同** | ✅ **已按 PF-1 裁定解决**：签名统一为 `(entries: Sequence[tuple[int, FactorResult]], direction, min_peer_group_size) -> list[NormalizedFactorValue]` —— 输入取【最富的形态】（`FactorResult` 带着 status 与 reason），产出仍是横截面视图。二元组形态丢掉 reason，下游便答不出「为什么这只基金的这个因子没参与」，而那正是 D-23 / 归因链要求的 |
| ② | `NormalizedFactorValue`（Task 12/13） vs `NormalizedFactor`（Task 14/17） | **两个不同的 dataclass，字段不重叠**：前者按 `share_class_id` 组织，带 `rank / n_effective / percentile / CrossSectionStatus`；后者按 `factor_id` 组织，带 `raw_value / normalized_score / FactorStatus / direction / reason`。**计划里没有任何一处把前者转成后者**——Task 17 直接自己构造 `NormalizedFactor`，于是 Task 12 的产出类型实际上**没有消费方** | ✅ **已按 PF-2 裁定解决**：**两个都保留**。它们不是重复，是同一份计算的两个【视图】（横截面 vs 归因）；真正缺的不是「合并」而是【转置】。Task 12 补 `transpose_to_fund_view(dict[str, list[NormalizedFactorValue]], *, window) -> dict[int, dict[str, NormalizedFactor]]`；Task 17 **不得**自己构造 `NormalizedFactor`，必须消费转置结果 |
| ③ | `FundTier` | **Task 8** 用它命名 `evaluation.fund_tier` 的 **ORM 类**；**Task 15** 用它命名档位 **StrEnum**（`A+`/`A`/`B`/`C`/`D`）；**Task 17** 又把 ORM 类叫 `FundTierRow`。三份草稿三种用法 | ✅ **已按 PF-3 裁定解决**：ORM 类保持 `FundTier`（与 Plan-1 的 `FundNav` ↔ `market.fund_nav` 一致）；档位枚举一律 `FundTierLevel`；**Task 17 的 `FundTierRow` 删除**，直接用 ORM 类。Task 15 / 17 正文已全文改完 |
| ④ | `data_completeness_floor = 0.8` vs M1 `data_completeness = 10/13 = 0.76923077` | 两者**都是已定案**（前者 `05-fund-selection:121` DECIDED，后者 D-24）。相乘的后果是 **`COND-COMPLETENESS` 对 M1 每一只基金都判 FAIL，B2 候选池恒为空**，M1.4 的验收标准无从进行。属业务裁定，不属实现取舍 | ✅ **已按 PF-4 裁定解决**：M1 的 floor 取 **`0.75`**，`status: PROVISIONAL`，source 写明「上游的 0.8 是在【五子分齐全】的前提下定的…把一个为完整系统设计的阈值套到一个【被刻意裁剪过】的系统上是范畴错误…M2 恢复 REL 后必须改回 0.8」（全文见 Task 16 开头与 `config/policy/evaluation/v1.yaml`）。并在 Task 16 补一条测试断言 10/13 **严格大于**当前 floor —— M2 只改分母不改 floor 时它会红。**代价**：若业务方认为「REL 不可算就不该入池」，本裁定是错的，但那样应先改 spec 而不是让候选池静默为空。Task 16 开头与 Task 18 判据 A-4 的登记已同步更新（B2 **不再是恒空**） |
| ⑤ | `MathematicallyUndefined` vs `UndefinedResult` | 原契约把 quant_engine 的数学异常写作 `MathematicallyUndefined`，Task 3 草稿实现的是 `UndefinedResult`（另有 `QuantEngineError` 基类、`UnsupportedBasis`） | ✅ **已按 PF-5 裁定解决**：统一为契约的 **`MathematicallyUndefined`**，Task 3 的 `UndefinedResult` 全文改名 |
| ⑥ | `fund_manager_assignment` 的排他键字段名 | `01-postgresql §8.4` 写 `share_class_id`，`04-database-design §6.3` 写 `fund_id`，而 Plan-1 落地的 ORM 列是 `fund_id`；另有一条 2026-08-27 的「EXCLUDE 限于 `role='LEAD'`」 | ✅ **已按 PF-6 裁定解决**：随 ORM 与 §6.3，用 `(fund_id, manager_id, daterange)`。该形态【允许共同管理】（同一基金同期多位经理各占一行），故**不需要 role 列**来豁免；2026-08-27 那条针对的是退化的「仅 `fund_id` + daterange」形态，不适用于此。Task 1 正文已如此实现 |
| ⑦ | `peer_group_snapshot` 的列名 | **Task 8 建的是** `member_count`，且**刻意不建** `classification_key` 列（理由：三列 + `effective_at` + `version` 已构成唯一键，再拼一个字符串列是第二份真值）。**Task 11 的写入代码用的是** `peer_group_size=` 与 `classification_key=`。两处对不上，写入会直接 `TypeError` | ✅ **已按 PF-7 裁定解决**：`peer_group_snapshot` 必须含 `classification_key`（Peer Group 的【身份】，不存则快照无法自解释）、`member_count`、`classification_history_ids`（P2-25）三列。**Task 11 的 `peer_group_size=` 改为 `member_count=`**；Task 8 加建 `classification_key` 列，并用 `ck_peer_group_classification_key` 钉住它 = 三列的竖线拼接，把「第二份真值」的风险降级为受约束的物化 |
| ⑧ | `factor_value` 的列名 | **Task 17 的写入代码**用 `factor_status=` / `status_reason=` / `normalized_score=` / `availability_quality="DERIVED"`；**Task 7 建的列**是 `status` / `unavailable_reason`（枚举）/ `normalized_value`，`availability_quality` 由 `VersionedMixin` 提供且 G-15 要求恒 `INFERRED`。Task 17 还漏传 `factor_version_id` / `data_version` 等 NOT NULL 列 | ✅ **已按 PF-8 裁定解决**：一律以 **Task 7 建表**为准，Task 17 无条件对齐（`status` / `normalized_value`，补齐漏传的 NOT NULL 列）；**硬编码的 `availability_quality="DERIVED"` 删除** —— quality 由 mixin 给出、G-15 强制 `INFERRED`，写死 DERIVED **直接违反 C-12**。唯一**反向**改 Task 7 的一处：`unavailable_reason` 列**改名为 `status_reason`**、枚举**加入 `NEAR_MIN_OBS`** —— P2-21 之后 NEAR_MIN_OBS 是唯一的 WARNING 理由，它装不进名为 `unavailable_reason` 的枚举 |
| ⑨ | 谁承担 G-8 的三元组 | **P2-28 / Task 12** 把 `rank` / `n_effective` / `INSUFFICIENT_SAMPLE` 交给 `normalize_peer_group`；**Task 17 的装配代码绕开了它**，直接调 `percentile_rank`，于是三者一个都没算、也没落库。**Task 15** 又用 `rank_within_peer_group` 算了一遍同样的东西 | ✅ **已按 PF-1 裁定解决（①⑨ 合并）**：`normalize_peer_group` 是 G-8 三元组的**唯一权威产出点**，Task 15 与 Task 17 一律消费它，不得各自再算一遍。**Task 17 直接调 `percentile_rank` 的路径已删除**（它三样都不产出，落库会是空的）。⚠️ **残留**：Task 15 的 `rank_within_peer_group` 排的是 Fund Score 总分且要按 Profile 拆分，**无法**直接消费 `normalize_peer_group`（入参已裁定为 `FactorResult`）——本次未自行改动其算法结构，已在 Task 15 开头登记并上报 controller |

---

### Task 1: Plan-1 交接 H-1 + H-2 —— `visible_until` 归位 + IntervalMixin 生成器配对的适应度测试

**Files:**
- Modify: `src/fip/platform/decision_data/pit.py:1-64`（新增 `resolve_visible_until`、
  `PitDataContext.visible_until` 属性、改 `navs()` 的装配）
- Modify: `src/fip/services/data_service/repositories/nav.py:86-121`
  （构造期改收 `visible_until`，删掉第 113-116 行那份逐字拷贝）
- Modify: `src/fip/services/data_service/normalization/backfill.py:16-29,121`
  （第 121 行的第二份逐字拷贝改为调用唯一规则）
- Modify: `src/fip/services/data_service/models/fund.py:155-212`
  （`FundManagerAssignment` 补 `ExcludeConstraint` + 两个索引；`FundFee` /
  `FundStatusHistory` 各补一条开放区间部分唯一索引 —— 交接项四，P2-3）
- Create: `db/migrations/versions/0016_handoff_interval_invariants.py`
- Modify: `src/fip/services/data_service/eligibility.py:14-31,56-61`
  （`derive_eligibility` 两个分支互换 + 枚举注释 + `EXIT_ONLY` 缺口登记 —— D-22）
- Test: `tests/unit/test_visible_until.py`（新建）
- Test: `tests/fitness/test_temporal_mixin_pairing.py`（新建，H-2）
- Test: `tests/integration/test_autogenerate_gate.py`（新建，P2-10）
- Test: `tests/unit/test_eligibility.py`（新建，D-22）
- Test: `tests/integration/test_temporal_constraints.py`（追加三条不变式行为测试）

**Interfaces:**
- Consumes: 无（本任务是 Plan-2 的第一个任务）
- Produces:
  - `fip.platform.decision_data.pit.resolve_visible_until(decision_at: dt.date) -> dt.datetime`
    —— 全平台 `decision_at → available_at <= ?` 的**唯一**翻译规则实现
  - `PitDataContext.visible_until -> dt.datetime`（property，只读）
  - `SqlNavPitRepository.__init__(session: Session, visible_until: dt.datetime)`
    —— 构造签名从 `decision_at: dt.date` 改为 `visible_until: dt.datetime`；
    Task 2 在此基础上继续改 `adjusted_nav_series` 的返回类型
  - `fip.platform.db.mixins.INTERVAL_TIME_ORDER_SQL` / `TIME_ORDER_SQL` 成为
    「哪张表用哪个生成器」的机器可判定依据（Task 5 新增区间表写入时受其保护）
  - **迁移 `0016`** —— Plan-2 迁移链的链头。后续 `down_revision` 依次为
    0017(Task 5) → 0018(Task 7) → 0019(Task 8) → 0020(Task 11)
  - `derive_eligibility` 的**修正后**语义（Task 16 的 Eligibility Rules 直接消费）：
    暂停赎回 → `NOT_TRADABLE`；暂停申购 → `HOLD_ONLY`；本函数永不返回
    `EXIT_ONLY` / `LIMITED`（两处已登记缺口）
  - `tests/integration/test_autogenerate_gate.py` —— G-16 的机器闸门，
    Task 5 / 7 / 8 / 11 的每一支迁移都必须让它保持绿

---

- [ ] **Step 1: 写失败的测试（H-1 —— 规则归位 + 全仓唯一）**

新建 `tests/unit/test_visible_until.py`：

```python
"""`decision_at → visible_until` 的唯一翻译规则（Plan-1 交接项 H-1）。

这条规则是全平台唯一可见性规则 `available_at <= decision_at` 的落地形式。
Plan-1 结束时它以逐字拷贝的形式住在 repositories/nav.py 与
normalization/backfill.py 两处，没有共同归属、没有任何测试断言两者相等 ——
第三份拷贝写成 dt.time.min 时，回测与实盘会对同一个 decision_at 解析出不同
的可见集合，不报错、不告警。
"""

import ast
import datetime as dt
import pathlib

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext, resolve_visible_until

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
RULE_HOME = SRC / "platform" / "decision_data" / "pit.py"


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-VU",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def test_rule_resolves_to_utc_end_of_decision_day():
    """decision_at 是业务日期，可见性判定取该日【终了】时刻，钉在 UTC。"""
    assert resolve_visible_until(dt.date(2026, 8, 31)) == dt.datetime(
        2026, 8, 31, 23, 59, 59, 999999, tzinfo=dt.UTC
    )


def test_rule_is_end_of_day_not_start_of_day():
    """反向断言：写成 dt.time.min 会让整整一天的披露对当日决策不可见。

    这条测试存在的理由就是 H-1 描述的失败场景本身 —— 第三份拷贝写成
    time.min 不会报错，只会让两条路径解析出不同的可见集合。
    """
    day_start = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)
    assert resolve_visible_until(dt.date(2026, 8, 31)) != day_start


def test_context_property_delegates_to_the_same_rule():
    """PitDataContext 是 decision_at 的唯一构造入口，属性必须与规则一致。"""
    ctx = PitDataContext(context=_ctx(dt.date(2026, 8, 31)), session=object())
    assert ctx.visible_until == resolve_visible_until(dt.date(2026, 8, 31))


@pytest.mark.parametrize(
    "decision_at",
    [dt.date(1999, 12, 31), dt.date(2020, 2, 29), dt.date(2026, 8, 31)],
)
def test_property_and_function_agree_on_every_date(decision_at):
    ctx = PitDataContext(context=_ctx(decision_at), session=object())
    assert ctx.visible_until == resolve_visible_until(decision_at)


def _files_mentioning_time_max() -> set[pathlib.Path]:
    """AST 扫描 src/fip 下全部 .py，找出出现 `<something>.time.max` 的文件。

    用 AST 而非正则：正则会把注释和 docstring 里的说明文字也算进来，
    而这条检查必须能被注释准确描述而不被自己绊倒。
    """
    hits: set[pathlib.Path] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "max"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "time"
            ):
                hits.add(path)
    return hits


def test_the_rule_has_exactly_one_home_in_the_whole_source_tree():
    """`dt.time.max` 只允许出现在规则本身所在的那一个文件里。

    什么情况下它会红：任何人在第二个文件里再写一次
    `dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)`。
    这正是 Plan-1 结束时的状态（nav.py 与 backfill.py 各一份），所以本测试
    在修复前【必定】失败 —— 它不是恒真的 oracle。
    """
    assert _files_mentioning_time_max() == {RULE_HOME}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py -v`

Expected: FAIL —— 收集阶段即 `ImportError: cannot import name 'resolve_visible_until'
from 'fip.platform.decision_data.pit'`。临时把该 import 注释掉再跑
`-k the_rule_has_exactly_one_home`，会看到
`AssertionError: assert {.../repositories/nav.py, .../normalization/backfill.py} == {.../pit.py}`
—— 两份逐字拷贝被如实点名。把失败输出原样写进报告（G-18）。

- [ ] **Step 3: 最小实现**

`src/fip/platform/decision_data/pit.py` —— 在 `NavPoint` 之前插入规则函数，
并给 `PitDataContext` 加属性、改 `navs()` 的装配：

```python
def resolve_visible_until(decision_at: dt.date) -> dt.datetime:
    """把 decision_at（业务日期）翻译成 `available_at <= ?` 的时间戳上界。

    这是全平台唯一可见性规则 `available_at <= decision_at`（G-1）的**唯一**
    落地形式，本函数是它在代码中的唯一归属。

    ── 为什么必须只有一份（Plan-1 交接项 H-1）──

    Plan-1 结束时同一行 `dt.datetime.combine(decision_at, dt.time.max,
    tzinfo=dt.UTC)` 逐字住在 repositories/nav.py 与 normalization/backfill.py
    两个不同的层，没有共同归属、没有任何测试断言两者相等。Plan-2 要为
    risk_free_rate / fund_classification_history 写第二、第三个 PIT 读取路径，
    第三份拷贝只要写成 `dt.time.min`，两条路径就会对同一个 decision_at 解析出
    不同的可见集合 —— 不报错、不告警，回测和实盘看到不同的数据。

    ── 取日终而不是日初 ──

    decision_at 是【业务日期】，available_at 是【时间戳】。「当日可见」意味着
    当日任意时刻的披露都算数，因此上界取该日终了时刻。取日初会让整整一天的
    披露对当日决策不可见（信息偏少的方向也是错的：它会让因子在披露日当天
    静默变成 UNAVAILABLE）。

    ── 已知边界（Plan-1 交接项二.4，如实登记，本任务不修）──

    日终钉在 UTC。若披露时刻按 UTC+8 记，本规则相当于允许 decision_at 当天
    看到最多 8 小时【之后】的披露。这是 Plan-1 的既有约定，不是现算改造引入的；
    真正的修法是给 available_at 引入交易日历与市场时区，属后续项。
    """
    return dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
```

`PitDataContext` 内（紧跟 `decision_at` 属性之后）：

```python
    @property
    def visible_until(self) -> dt.datetime:
        """本次决策的可见性上界：`available_at <= visible_until`。

        PitDataContext 是 decision_at 的唯一构造入口，因此这条翻译规则的
        唯一对外出口就在这里。任何 PIT 读取实现都应当接收本属性的值，
        而不是自己再翻译一次 decision_at（H-1）。
        """
        return resolve_visible_until(self.decision_at)
```

`navs()` 的装配改为传上界而不是日期：

```python
        return SqlNavPitRepository(
            session=self._session, visible_until=self.visible_until
        )
```

`src/fip/services/data_service/repositories/nav.py` —— 构造期改收上界，
删掉方法体内那三行拷贝（原第 113-116 行）：

```python
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        """visible_until 由 PitDataContext.visible_until 注入。

        本类【不再】自己把 decision_at 翻译成时间戳上界：那条规则的唯一
        归属是 fip.platform.decision_data.pit.resolve_visible_until（H-1）。
        构造期注入上界与注入 decision_at 在 PIT-A2 上是等价的 —— 时点仍然
        不出现在任何方法签名里，调用方仍然无法省略它、无法绕过它取未来数据。
        """
        self._session = session
        self._visible_until = visible_until
```

`adjusted_nav_series` 方法体开头的三行替换为一行：

```python
        params = {
            "share_class_id": share_class_id,
            "visible_until": self._visible_until,
            "date_to": date_to,
        }
```

`src/fip/services/data_service/normalization/backfill.py` —— 顶部加 import，
第 121 行改为调用唯一规则：

```python
from fip.platform.decision_data.pit import resolve_visible_until
```

```python
    visible_until = resolve_visible_until(decision_at)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: `tests/unit/test_visible_until.py` 6 passed；既有 281 条不减。

- [ ] **Step 5: 写失败的测试（H-2 —— 两个生成器与两个 Mixin 必须配对）**

新建 `tests/fitness/test_temporal_mixin_pairing.py`：

```python
"""H-2：强制「凡继承 IntervalMixin 的表必须用 interval 生成器，反之亦然」。

platform/db/mixins.py 有两个时序约束生成器 —— temporal_check_constraints
（版本化事实表，五子句）与 interval_temporal_check_constraints（区间型状态表，
三子句）。选哪个此前【完全靠作者手工】，当前 11 张表全部选对。

失败场景（Plan-1 交接项 H-2）：Plan-2 新增区间表时复制粘贴抓了版本化的那个，
于是所有【提前公告】的行（公告 8-25、生效 9-01）在写入时被 clause 1 / clause 4
直接拒收 —— 而那正是 Plan-1 花了一整轮（迁移 0014）修掉的问题。

黄金快照抓不到它：新表本来就应该新增约束，快照给出的是一条完全正常的信号。
"""

import pytest
from sqlalchemy import CheckConstraint

from fip.platform.db.base import Base
from fip.platform.db.mixins import (
    INTERVAL_TIME_ORDER_SQL,
    TIME_ORDER_SQL,
    IntervalMixin,
    VersionedMixin,
)

# Base.metadata 的注册点与 db/migrations/env.py 保持一致：只有被 import 过的
# 模块才会出现在 registry 里。少 import 一个模块会让本测试对那张表【失明】，
# 因此这份清单必须与 env.py 的清单同步（后者由 test_architecture.py::
# test_every_orm_model_module_is_registered_in_env 守住）。
from fip.platform.jobs import models as _jobs_models  # noqa: F401
from fip.services.data_service.models import fund as _fund  # noqa: F401
from fip.services.data_service.models import governance as _governance  # noqa: F401
from fip.services.data_service.models import market as _market  # noqa: F401
from fip.services.data_service.models import raw as _raw  # noqa: F401


def _time_order_sql(cls) -> str | None:
    """返回该 model 的 ck_<表名>_time_order 约束的 SQL 文本；没有则 None。"""
    wanted = f"ck_{cls.__tablename__}_time_order"
    for constraint in cls.__table__.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == wanted:
            return str(constraint.sqltext)
    return None


def _mapped_classes() -> list[type]:
    return [mapper.class_ for mapper in Base.registry.mappers]


def _interval_models() -> list[type]:
    return [c for c in _mapped_classes() if issubclass(c, IntervalMixin)]


def _versioned_models() -> list[type]:
    return [c for c in _mapped_classes() if issubclass(c, VersionedMixin)]


def test_the_two_mixins_are_disjoint():
    """守卫：若哪天有人让 VersionedMixin 继承 IntervalMixin，下面两条会互相矛盾。"""
    overlap = set(_interval_models()) & set(_versioned_models())
    assert not overlap, f"同时被判定为区间型与版本化的 model：{overlap}"


def test_the_scan_is_not_vacuous():
    """守卫：漏 import model 模块会让本文件的断言在空集合上恒真。

    当前实际数量：区间型 5 张（provider_fund_identity / fund_manager_assignment
    / fund_classification_history / fund_status_history / fund_fee），
    版本化 4 张（fund_nav / fund_distribution / risk_free_rate /
    investment_eligibility）。新增表只会让数量变大，不会变小。
    """
    assert len(_interval_models()) >= 5
    assert len(_versioned_models()) >= 4


@pytest.mark.parametrize(
    "model", _interval_models(), ids=lambda c: c.__tablename__
)
def test_interval_tables_use_the_interval_generator(model):
    """继承 IntervalMixin ⇒ 必须是三子句（clause 2 / 3 / 5）。

    用错生成器不会有任何静态错误，只会在写入【提前公告】的行时被数据库拒收。
    """
    actual = _time_order_sql(model)
    assert actual is not None, (
        f"{model.__tablename__} 继承 IntervalMixin 却没有 ck_*_time_order 约束"
    )
    assert actual == INTERVAL_TIME_ORDER_SQL, (
        f"{model.__tablename__} 是区间型状态表，必须用 "
        "interval_temporal_check_constraints（三子句）。当前用的是版本化表的"
        "五子句生成器，clause 1 / clause 4 会拒收所有提前公告的行"
    )


@pytest.mark.parametrize(
    "model", _versioned_models(), ids=lambda c: c.__tablename__
)
def test_versioned_tables_use_the_versioned_generator(model):
    """反之亦然：不继承 IntervalMixin 的事实表必须是五子句。

    反向也必须断言：只查一个方向的话，把版本化表误接成三子句生成器会静默
    删掉 clause 1 / clause 4 —— 那是版本化表上真正的前视偏差防线。
    """
    actual = _time_order_sql(model)
    assert actual is not None, (
        f"{model.__tablename__} 继承 VersionedMixin 却没有 ck_*_time_order 约束"
    )
    assert actual == TIME_ORDER_SQL, (
        f"{model.__tablename__} 是版本化事实表，必须用 temporal_check_constraints"
        "（五子句）。当前用的是区间型的三子句生成器，clause 1 / clause 4 缺失，"
        "净值可以声称比它自己的生效日更早就已知"
    )
```

- [ ] **Step 6: 跑测试确认失败（H-2 必须【人为制造】红灯才算证伪）**

当前 11 张表全部选对，因此本测试一写出来就是绿的。绿灯不是证据 —— 按交接项
六.1「证伪是唯一的验收方式」，必须先制造一次真实的红灯：

Run:
```bash
.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path("src/fip/services/data_service/models/fund.py")
s = p.read_text(encoding="utf-8")
p.write_text(s.replace(
    '*interval_temporal_check_constraints("fund_fee")',
    '*temporal_check_constraints("fund_fee")', 1), encoding="utf-8")
PY
.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path("src/fip/services/data_service/models/fund.py")
s = p.read_text(encoding="utf-8")
assert "temporal_check_constraints,\n" in s or True
p.write_text(s.replace(
    "    IntervalMixin,\n",
    "    IntervalMixin,\n", 1), encoding="utf-8")
PY
grep -n "temporal_check_constraints" src/fip/services/data_service/models/fund.py | head -5
.venv/bin/pytest tests/fitness/test_temporal_mixin_pairing.py -v
```

Expected: FAIL with
`test_interval_tables_use_the_interval_generator[fund_fee] ... AssertionError:
fund_fee 是区间型状态表，必须用 interval_temporal_check_constraints（三子句）`
（若 `temporal_check_constraints` 尚未在该文件 import，先在 import 块里补上再制造，
制造完连同 import 一起还原）。把这段红灯输出写进报告，然后还原：

Run: `git checkout -- src/fip/services/data_service/models/fund.py`
Run: `.venv/bin/pytest tests/fitness/test_temporal_mixin_pairing.py -v`
Expected: 11 passed（9 张表 + 2 条守卫）。

- [ ] **Step 7: 交接项四 —— 三处缺失的数据库不变式（迁移 `0016`）**

> **归属裁定 P2-3**：Plan-1 交接项四点名的四件事里，`fund_classification_history`
> 的开放区间索引归 Task 5（它是第一个写入方），**其余三件并入本任务**——
> 它们在 18 个任务里原本一个都没有归属，而「趁表还空着」的窗口现在就开着
> （`fip_dev` 实测 `fund_manager_assignment` / `fund_fee` / `fund_status_history`
> 三张表均为 0 行）。

`src/fip/services/data_service/models/fund.py` —— 三处 `__table_args__` 同步声明
（G-16：迁移里建的每一个约束/索引，ORM 必须同时声明，否则 autogenerate 会把它
判成待删除对象；本仓库已被这个形状咬过三次）：

```python
# FundManagerAssignment.__table_args__ 追加
        # 04-database-design §6.3 明列的三件事：一条 EXCLUDE + 两个索引。
        #
        # 【Ruling PF-6 已裁定】排他键 = (fund_id, manager_id, daterange)，
        # 【不需要】role 列。理由（逐条抄自裁定）：01-postgresql §8.4 说
        # share_class_id、04-database-design §6.3 说 fund_id，ORM 是 fund_id ——
        # 随 ORM 与 §6.3，用 fund_id；该形态【允许共同管理】（同一基金同期
        # 多位经理各占一行），故不需要 role 列来豁免；2026-08-27 那条
        # 「EXCLUDE 限于 role='LEAD'」针对的是退化的「仅 fund_id + daterange」
        # 形态，不适用于此。
        #
        # ⚠️ 排他键必须【同时含 manager_id】。01-postgresql §8.4 的
        # 2026-08-27 已定案否掉的是退化形式
        # `EXCLUDE (fund_id WITH =, range WITH &&)` —— 那个形式只按基金排他，
        # 会直接拒绝合法的共管数据（同一基金同期多位经理）。带上 manager_id
        # 之后排他的是「同一经理对同一基金的任职区间重叠」，共管不受影响，
        # 这正是 §8.4 正文那一行与 §6.3 表格的写法。因此本仓库【不需要】
        # role='LEAD' 部分约束，也就不需要新增 role 列。
        #
        # ⚠️ 上游字段名不一致：01-postgresql §8.4 写的是 share_class_id，
        # 04-database-design §6.3 写的是 fund_id，而 ORM 的列是 fund_id
        # （任职挂在产品级）。以 ORM 现状 + §6.3 为准，如实登记该差异。
        ExcludeConstraint(
            ("fund_id", "="),
            ("manager_id", "="),
            (text("daterange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_fma_no_overlap",
            using="gist",
        ),
        Index("idx_fma_manager_valid_from", "manager_id", "valid_from"),
        Index("idx_fma_fund_valid_from", "fund_id", "valid_from"),

# FundFee.__table_args__ 追加
        # 「至多一条开放区间」的部分唯一索引。交接项四明写「唯一性键不一定
        # 只是外键，需逐表判断」：费率是【每种 fee_type 各有一条】开放区间，
        # 键必须是 (share_class_id, fee_type) —— 只用 share_class_id 会把
        # 「管理费 + 托管费同时开放」判成违规，那是正常数据。
        Index(
            "uq_fund_fee_open_interval",
            "share_class_id", "fee_type",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),

# FundStatusHistory.__table_args__ 追加
        # 状态历史每个份额类别只有一条「当前状态」，键就是 share_class_id。
        Index(
            "uq_fsh_open_interval",
            "share_class_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
```

新建 `db/migrations/versions/0016_handoff_interval_invariants.py`：

```python
"""Plan-1 交接项四：三张空表补齐设计文档要求的不变式。

Revision ID: 0016
Revises: 0015

为什么现在做：三张表在 fip_dev 实测均为 0 行。EXCLUDE USING gist 要建索引、
部分唯一索引要全表扫，空表上几乎免费；有数据之后成本高一个量级，而且
一旦已经存在重叠区间，迁移会直接失败并卡住整条链。

btree_gist：EXCLUDE 里的 `fund_id WITH =` / `manager_id WITH =` 用的是
btree 的等值操作符，而 GiST 索引默认不认识 bigint 的 `=`。缺这个扩展时
CREATE 会报 `data type bigint has no default operator class for access
method "gist"` —— 报得很响，不会静默，但必须先建。

daterange 的边界写成 '[)'：valid_to 是【开区间右端】（与 interval_check
的 valid_from < valid_to 一致），写成默认的 '[]' 会把「前一段 8-01~8-15、
后一段 8-15~9-01」这种首尾相接的合法交接判成重叠。valid_to IS NULL 时
daterange 得到无上界区间，正是「至今仍在任」的正确语义。
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        "ALTER TABLE fund.fund_manager_assignment "
        "ADD CONSTRAINT ex_fma_no_overlap EXCLUDE USING gist ("
        "fund_id WITH =, manager_id WITH =, "
        "daterange(valid_from, valid_to, '[)') WITH &&)"
    )
    op.execute(
        "CREATE INDEX idx_fma_manager_valid_from "
        "ON fund.fund_manager_assignment (manager_id, valid_from)"
    )
    op.execute(
        "CREATE INDEX idx_fma_fund_valid_from "
        "ON fund.fund_manager_assignment (fund_id, valid_from)"
    )

    # 与 0014 的 uq_pfi_open_interval 逐字同形（含 WHERE 子句），
    # ORM 侧 postgresql_where 必须一模一样。
    op.execute(
        "CREATE UNIQUE INDEX uq_fund_fee_open_interval "
        "ON fund.fund_fee (share_class_id, fee_type) "
        "WHERE valid_to IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_fsh_open_interval "
        "ON fund.fund_status_history (share_class_id) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_fsh_open_interval")
    op.execute("DROP INDEX fund.uq_fund_fee_open_interval")
    op.execute("DROP INDEX fund.idx_fma_fund_valid_from")
    op.execute("DROP INDEX fund.idx_fma_manager_valid_from")
    op.execute(
        "ALTER TABLE fund.fund_manager_assignment DROP CONSTRAINT ex_fma_no_overlap"
    )
    # 【不】DROP EXTENSION btree_gist：它是库级对象，别的迁移或将来的表
    # 可能已经依赖它，回滚一支迁移不该顺手拆掉共享地基。
```

`tests/integration/test_temporal_constraints.py` 追加三条行为测试
（先证伪，G-18 —— 每一条都要先在没有迁移的库上跑一遍看它绿，
证明「没有约束时这些非法写入会被接受」，再加迁移看它红转绿）：

```python
def test_same_manager_cannot_hold_overlapping_assignments(db_session):
    """共管允许（不同 manager 同期同基金），同一经理区间重叠不允许。"""
    # 1) 两位不同经理、同一基金、完全相同的区间 —— 必须【成功】
    # 2) 同一位经理、同一基金、区间重叠 —— 必须 raise IntegrityError
    # 3) 同一位经理、同一基金、首尾相接（前段 valid_to == 后段 valid_from）
    #    —— 必须【成功】：'[)' 边界的意义就在这里，写成 '[]' 这条会红


def test_fund_fee_allows_one_open_interval_per_fee_type(db_session):
    """每种 fee_type 各一条开放区间是合法的；同一 fee_type 两条则不合法。"""


def test_fund_status_history_allows_only_one_open_interval(db_session):
    """同一份额类别至多一条 valid_to IS NULL。"""
```

- [ ] **Step 8: G-16 的 autogenerate 闸门自动化（P2-10）**

G-16 把「收工时 `alembic revision --autogenerate` 报告零操作」列为可验收项，
但它至今**完全是手工的、CI 不跑**。按交接项六.1「只由阅读/推理保证的性质
等于没有保护」，这条目前**没有保护**——上面 Step 7 刚加的三个对象正是
最容易忘记同步到 ORM 的那一类。

新建 `tests/integration/test_autogenerate_gate.py`：

```python
"""G-16 的自动化闸门：Base.metadata 与真实数据库之间不得有差异。

与黄金快照（test_temporal_constraints.py 的 CHECK 快照）互补，两者都需要：

  黄金快照  管 CHECK 表达式 —— autogenerate 对 CHECK 完全失明
            （实测把 fund_nav 的时序 CHECK 换成 1=1，autogenerate 照报零操作）
  本测试    管表 / 列 / 索引 / 唯一键 —— 快照的 SQL 只查 contype='c'，看不见索引

单靠任何一个都留着一半的门开着。
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from fip.platform.db.base import Base


def test_orm_metadata_matches_the_migrated_database(db_session):
    """等价于手工跑 `alembic revision --autogenerate` 并检查它报告零操作。

    db_session 的库由 conftest 跑真实 `alembic upgrade head` 建起，所以
    比较的是【迁移的产出】与【ORM 声明】，而不是 ORM 与它自己。

    include_object 必须与 db/migrations/env.py 用同一份 —— 否则本测试会
    对 alembic 版本表、探针表之类报差异，然后被人加 xfail 关掉，
    比没有测试更糟。
    """
    from db.migrations.env import include_object  # 唯一权威，勿复制

    ctx = MigrationContext.configure(
        db_session.connection(),
        opts={
            "compare_type": True,
            "include_object": include_object,
            "include_schemas": True,
        },
    )
    diff = compare_metadata(ctx, Base.metadata)
    assert not diff, (
        "ORM metadata 与迁移建出的数据库不一致 —— `alembic revision "
        f"--autogenerate` 会生成非空迁移：{diff}\n"
        "常见原因：迁移里 CREATE 了索引/约束但 ORM __table_args__ 没声明"
        "（下一次 autogenerate 会把它误判成待删除对象），或反过来。"
    )
```

**先证伪（G-18）**：把 Step 7 里 `FundFee.__table_args__` 的
`uq_fund_fee_open_interval` 那一段注释掉再跑，本测试必须红并在消息里
点名该索引；恢复后转绿。**这一步不做的话，Step 7 的三个对象是否真的
双向声明了就仍然只由阅读保证。**

- [ ] **Step 9: D-22 —— `derive_eligibility` 的两个分支与上游语义互换（Plan-1 代码 bug）**

上游三处文档**完全一致**（`05-fund-selection.md:217-223` =
`02-business-requirements.md` §18.2 = `03-data/02-data-domain-model.md:400-406`）：

| 状态 | 含义 | 可持有 | 可加仓 | 可减仓 |
|---|---|:---:|:---:|:---:|
| `HOLD_ONLY` | **暂停申购** | ✓ | ✗ | ✓ |
| `NOT_TRADABLE` | 已清盘 / **暂停赎回** | — | ✗ | ✗ |
| `EXIT_ONLY` | **即将清盘 / 转型** | ✓ | ✗ | ✓ |

而 `src/fip/services/data_service/eligibility.py:56-61` **两个分支都反了**，
连同 `EligibilityStatus` 的两行行内注释也反了。Plan-1 里它没有消费方，
错了不显形；**Task 16 一旦按 §9.3 消费它**：暂停申购（常见、良性、期满即恢复）
被判 `EXIT_ONLY` → 不入池；暂停赎回（真正不可交易）被判 `HOLD_ONLY` →
入池并标注约束。**该排除的进了池，不该排除的被赶了出去**，而全部条件结果
照常落库，没有一条测试会红。

先写失败的测试 `tests/unit/test_eligibility.py`（新建）：

```python
def test_suspended_redemption_is_not_tradable():
    """暂停赎回 = 钱出不来 = 不可交易。上游三处文档一致。"""
    assert derive_eligibility(LifecycleStatus.NORMAL, True, False) \
        is EligibilityStatus.NOT_TRADABLE


def test_suspended_subscription_is_hold_only():
    """暂停申购 = 不可加仓，但可持有、可减仓。这是常见且良性的状态。"""
    assert derive_eligibility(LifecycleStatus.NORMAL, False, True) \
        is EligibilityStatus.HOLD_ONLY


def test_exit_only_is_never_derived_from_the_two_booleans():
    """EXIT_ONLY 是【生命周期】条件（即将清盘/转型），不是申赎标志的函数。

    穷举 lifecycle × subscription_open × redemption_open 的全部组合，
    断言 EXIT_ONLY 一次都不出现 —— 与既有的 LIMITED 缺口同类，
    把「本函数永不产出它」钉成机器可判定的事实而不是 docstring 里的一句话。
    """
    for lc in LifecycleStatus:
        for sub in (True, False):
            for red in (True, False):
                assert derive_eligibility(lc, sub, red) is not EligibilityStatus.EXIT_ONLY
```

Expected（修复前）：前两条 FAIL（实际得到 `HOLD_ONLY` / `EXIT_ONLY`），
第三条 FAIL。把红灯输出写进报告。

`src/fip/services/data_service/eligibility.py` —— 修正两个分支：

```python
    if subscription_open and not redemption_open:
        return EligibilityStatus.NOT_TRADABLE   # 暂停赎回：钱出不来
    if not subscription_open and redemption_open:
        return EligibilityStatus.HOLD_ONLY      # 暂停申购：不可加仓，可持有可减仓
```

同时修正 `EligibilityStatus` 里两行反了的行内注释，并**照既有 `LIMITED`
缺口的写法**在 `derive_eligibility` 的 docstring 里登记第二处缺口：

```python
    已知缺口二：本函数永远不会返回 EligibilityStatus.EXIT_ONLY（仅可减仓）。
    上游把 EXIT_ONLY 定义为「即将清盘 / 转型」—— 那是【生命周期】条件，
    根本不能由 subscription_open / redemption_open 这两个布尔推出：
    一只即将转型的基金完全可以申赎双开。要产出它，需要「清盘/转型公告已
    发布且生效日在未来」这一维输入，而 LifecycleStatus 只有 TRANSFORMED
    这个【已经发生】的终态，表达不了「即将」。该枚举值保留是因为它出现在
    外部 API 契约中 —— 与上面的 LIMITED 缺口同类，是已记录的已知空缺，
    不是被忽略的分支。
```

- [ ] **Step 10: 跑全量并提交**

Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `FIP_WRITE_CHECK_SNAPSHOT=1 .venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot`
  —— 本任务**不改任何 CHECK**（加的是 EXCLUDE 与索引，`contype` 分别是 `x` 与非约束），
  因此快照**应当无 diff**。若 `git diff` 显示快照变了，说明迁移动到了不该动的东西，
  停下来查清楚再继续。
Run: `.venv/bin/alembic -x db=dev revision --autogenerate -m "probe-0016"` →
  必须报告零操作（与 Step 8 的机器闸门互为交叉验证），验完删掉探针文件。

```bash
git add tests/unit/test_visible_until.py tests/fitness/test_temporal_mixin_pairing.py \
        tests/integration/test_autogenerate_gate.py tests/unit/test_eligibility.py \
        db/migrations/versions/0016_handoff_interval_invariants.py
git commit --only \
  src/fip/platform/decision_data/pit.py \
  src/fip/services/data_service/repositories/nav.py \
  src/fip/services/data_service/normalization/backfill.py \
  src/fip/services/data_service/models/fund.py \
  src/fip/services/data_service/eligibility.py \
  db/migrations/versions/0016_handoff_interval_invariants.py \
  tests/unit/test_visible_until.py \
  tests/unit/test_eligibility.py \
  tests/fitness/test_temporal_mixin_pairing.py \
  tests/integration/test_autogenerate_gate.py \
  tests/integration/test_temporal_constraints.py \
  -m "fix(pit): Plan-1 交接 H-1/H-2 + 交接项四 + autogenerate 闸门 + eligibility bug

H-1：decision_at → available_at 上界的翻译规则此前逐字拷贝在
repositories/nav.py 与 normalization/backfill.py 两层，无共同归属、无一致性
测试。提到 resolve_visible_until + PitDataContext.visible_until，两个消费方
改为取它；并加一条 AST 扫描断言 dt.time.max 全仓只有一处。

H-2：新增适应度测试，遍历 Base.registry 的全部 model，断言继承 IntervalMixin
的必须用三子句生成器、继承 VersionedMixin 的必须用五子句生成器，双向断言。
证伪记录：把 fund_fee 临时改用版本化生成器后测试转红。

交接项四（P2-3）：迁移 0016 趁三张表还空着补齐设计文档要求的不变式 ——
fund_manager_assignment 的 EXCLUDE USING gist（排他键含 manager_id，
共管不受影响）+ (manager_id, valid_from) / (fund_id, valid_from) 两个索引；
fund_fee 的开放区间唯一索引键取 (share_class_id, fee_type)（每种费率各一条
开放区间是合法的）；fund_status_history 取 share_class_id。

P2-10：G-16 的『autogenerate 报告零操作』此前完全是手工的、CI 不跑。
用 alembic.autogenerate.compare_metadata 写成集成测试，与 CHECK 黄金快照
互补 —— 快照管 CHECK 表达式（autogenerate 对它失明），它管表/列/索引/唯一键
（快照的 SQL 只查 contype='c'）。证伪记录：注释掉 uq_fund_fee_open_interval
的 ORM 声明后本测试转红并点名该索引。

D-22：derive_eligibility 的两个分支与上游语义互换 —— 暂停赎回本应
NOT_TRADABLE 却返回 HOLD_ONLY，暂停申购本应 HOLD_ONLY 却返回 EXIT_ONLY。
上游三处文档一致，且该函数自己的 docstring 与它的代码矛盾。Plan-1 里它
没有消费方所以不显形，Task 16 一消费就会『该排除的进池、不该排除的出池』
而没有一条测试会红。同时如实登记第二处缺口：EXIT_ONLY 是生命周期条件，
不能由两个申赎布尔推出，本函数永不返回它（写法照既有 LIMITED 缺口）。"
```

---

### Task 2: 收紧 PIT 数据契约 —— `NavPoint.adjusted_nav` 类型收窄 + 链路 quality 聚合

**Files:**
- Modify: `src/fip/platform/source/availability.py:1-8`（新增质量强弱序与 `weakest_quality`）
- Modify: `src/fip/platform/decision_data/pit.py:9-32`
  （`NavPoint.adjusted_nav` 收窄；新增 `NavSeries`；`NavPitRepository` Protocol 返回类型改为 `NavSeries`）
- Modify: `src/fip/services/data_service/repositories/nav.py:90-149`
  （聚合链路 quality，返回 `NavSeries`）
- Modify: `src/fip/platform/cli.py:186-212`（`cmd_pit_nav` 改取 `series.points`，并打印 `chain_quality`）
- Modify: `tests/integration/test_pit_nav_repository.py:69-71`（`_series` 辅助函数）
- Modify: `tests/integration/test_ingest_service.py:141-145`
- Test: `tests/unit/test_pit_contract.py`（新建）
- Test: `tests/integration/test_chain_quality.py`（新建）

**Interfaces:**
- Consumes（Task 1 产出）：
  - `SqlNavPitRepository.__init__(session: Session, visible_until: dt.datetime)`
  - `PitDataContext.visible_until -> dt.datetime`
- Produces（Task 9 的 `FactorInput` 与 Task 12/13 消费）：
  - `fip.platform.source.availability.weakest_quality(qualities: Iterable[str | AvailabilityQuality]) -> AvailabilityQuality`
  - `fip.platform.decision_data.pit.NavPoint`，其 `adjusted_nav: Decimal`（不再是 `Decimal | None`）
  - `fip.platform.decision_data.pit.NavSeries`：
    `points: tuple[NavPoint, ...]`、`chain_quality: str | None`
  - `NavPitRepository.adjusted_nav_series(share_class_id: int, date_from: dt.date,
    date_to: dt.date) -> NavSeries`
  - `NavSeries.chain_quality` 即接口契约里 `FactorInput.chain_quality` 的**唯一**来源，
    并经由它原样流进 `FactorResult.quality_flag`（P2-21）。
    ⚠️ 它**不再**参与 `FactorStatus` 判定 —— D-10 原本把「链路含 `INFERRED`」
    列为 `WARNING` 的第二触发条件，P2-21 已删除该条：AKShare 链路 100% 是
    `INFERRED`（G-15），留着它会让 `VALID` 在 M1 完全不可达。

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_pit_contract.py`：

```python
"""PIT 数据契约的形状本身（Plan-1 交接项二.1 / 二.2）。

这些断言不需要数据库：它们锁的是 dataclass 与 Protocol 的**类型契约**，
而类型契约一旦松掉，下游会长出永远不会被执行的 None 分支，或把逐行 quality
误当成链路 quality 使用。
"""

import datetime as dt
import typing
from decimal import Decimal

import pytest

from fip.platform.decision_data.pit import NavPitRepository, NavPoint, NavSeries
from fip.platform.source.availability import AvailabilityQuality, weakest_quality


def test_adjusted_nav_is_not_optional():
    """现算路径要么全有值、要么抛 AdjustedNavUnavailable，绝无 None。

    留着 `Decimal | None` 的后果不是「多一点保险」：它让下游每个消费方都
    必须写一个永远不会被执行的 `is None` 分支，而那个分支里最自然的写法
    恰恰是填 0 或沿用上期 —— 正是 C-6 / G-3 禁止的两件事。
    """
    hints = typing.get_type_hints(NavPoint)
    assert hints["adjusted_nav"] is Decimal


def test_nav_point_keeps_its_own_row_quality():
    """逐行 quality 保留：它是那一行自己的事实，不是链路的结论。"""
    hints = typing.get_type_hints(NavPoint)
    assert hints["availability_quality"] is str


def test_repository_returns_a_series_not_a_bare_list():
    """链路 quality 无处安放是 Plan-1 的结构性缺口，返回类型必须能装下它。"""
    hints = typing.get_type_hints(NavPitRepository.adjusted_nav_series)
    assert hints["return"] is NavSeries


def _point(day: int, quality: str) -> NavPoint:
    return NavPoint(
        effective_at=dt.date(2020, 1, day),
        adjusted_nav=Decimal("1.00000000"),
        unit_nav=Decimal("1.00000000"),
        version=1,
        availability_quality=quality,
    )


def test_empty_series_has_no_chain_quality():
    """没有任何行就没有链路 —— 不得凭空造一个 quality 值出来（G-3）。"""
    series = NavSeries(points=(), chain_quality=None)
    assert series.chain_quality is None


def test_non_empty_series_must_carry_a_chain_quality():
    """反向不变式：有点却没有链路结论，是把 quality 悄悄丢掉。"""
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(_point(2, "EXACT"),), chain_quality=None)


def test_empty_series_must_not_carry_a_chain_quality():
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(), chain_quality="EXACT")


@pytest.mark.parametrize(
    ("qualities", "expected"),
    [
        (["EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "DERIVED"], AvailabilityQuality.DERIVED),
        (["DERIVED", "EXACT"], AvailabilityQuality.DERIVED),
        (["EXACT", "DERIVED", "INFERRED"], AvailabilityQuality.INFERRED),
        (["INFERRED", "EXACT"], AvailabilityQuality.INFERRED),
        (["DERIVED", "DERIVED"], AvailabilityQuality.DERIVED),
        ([AvailabilityQuality.EXACT, "INFERRED"], AvailabilityQuality.INFERRED),
    ],
)
def test_weakest_quality_is_min_over_chain(qualities, expected):
    """EXACT > DERIVED > INFERRED，取最弱者（min-over-chain）。

    方向必须是「取最弱」而不是「取多数」或「取最后一行」：复权值是整条
    累乘链路的函数，链路上任何一行不可靠，产出的值就不可靠。
    """
    assert weakest_quality(qualities) is expected


def test_weakest_quality_rejects_an_empty_chain():
    """空链路没有结论 —— 返回一个默认值就是凭空发明可靠性。"""
    with pytest.raises(ValueError):
        weakest_quality([])


def test_weakest_quality_rejects_unknown_labels():
    with pytest.raises(ValueError):
        weakest_quality(["VERIFIED"])
```

新建 `tests/integration/test_chain_quality.py`：

```python
"""链路 quality 聚合：复权值依赖调用方在返回值里【根本看不到】的行。

Plan-1 交接项二.1：现算后一个点的复权值依赖 date_from 之前的全部历史。
逐行 quality 因此比以前更容易误导 —— 调用方看到窗口内每一行都是 EXACT，
却不知道窗口之前有一行是 INFERRED，而那一行参与了整条累乘链路。
"""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution, FundNav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-CQ", product_name="链路质量测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A",
                        display_name="链路质量测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _utc(y, m, d, hour=0):
    return dt.datetime(y, m, d, hour, tzinfo=dt.UTC)


def _add_nav(session, sc, day, value, quality, published_at=None,
             provider_available_at=None):
    """按 quality 如实填三个来源列 —— quality_source CHECK 会替我们把关。"""
    if quality == "EXACT":
        available_at = provider_available_at or _utc(day.year, day.month, day.day, 12)
        provider_available_at = available_at
        published_at = published_at or _utc(day.year, day.month, day.day, 9)
    elif quality == "DERIVED":
        published_at = published_at or _utc(day.year, day.month, day.day, 9)
        available_at = published_at
        provider_available_at = None
    else:
        available_at = _utc(day.year, day.month, day.day) + dt.timedelta(days=1)
        published_at = None
        provider_available_at = None
    session.add(FundNav(
        share_class_id=sc.id, effective_at=day, version=1,
        unit_nav=Decimal(value), available_at=available_at,
        availability_quality=quality, published_at=published_at,
        provider_available_at=provider_available_at,
        ingested_at=_utc(2026, 8, 31),
    ))


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-CQ", decision_at=decision_at, data_as_of=decision_at,
        strategy_version="sv-1", policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _series(db_session, sc, decision_at, date_from, date_to):
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to)


def test_chain_quality_reflects_rows_outside_the_requested_window(db_session, share_class):
    """窗口外的 INFERRED 行必须把整条链路的结论拉到 INFERRED。

    什么情况下它会红：如果实现只聚合【切片后】返回的那些点的 quality，
    窗口内两行都是 EXACT，结论会是 EXACT —— 而 2020-01-02 那行 INFERRED
    参与了每一个后续点的累乘。这正是本任务要堵的那个洞。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "INFERRED")
    _add_nav(db_session, share_class, dt.date(2020, 3, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 3, 3), "1.2", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 3, 1), dt.date(2020, 3, 31))

    assert [p.effective_at for p in series.points] == [
        dt.date(2020, 3, 2), dt.date(2020, 3, 3)
    ]
    assert {p.availability_quality for p in series.points} == {"EXACT"}
    assert series.chain_quality == "INFERRED"


def test_chain_quality_is_exact_when_every_row_on_the_chain_is_exact(
    db_session, share_class
):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.1", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.chain_quality == "EXACT"


def test_distribution_rows_are_part_of_the_chain(db_session, share_class):
    """分红/拆分行同样参与累乘 —— 它们的 quality 必须计入链路。

    什么情况下它会红：只聚合 fund_nav 而漏掉 fund_distribution。
    一条 INFERRED 的分红事件会改变每一个后续点的复权值，漏算它会让链路
    结论比事实更乐观。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0", "EXACT")
    db_session.add(FundDistribution(
        share_class_id=share_class.id, effective_at=dt.date(2020, 1, 3), version=1,
        dividend_per_unit=Decimal("0.1"), split_ratio=Decimal("1"),
        available_at=_utc(2020, 1, 4), availability_quality="INFERRED",
        published_at=None, provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert {p.availability_quality for p in series.points} == {"EXACT"}
    assert series.chain_quality == "INFERRED"


def test_empty_result_has_no_chain_quality(db_session, share_class):
    """没有任何可见行时不得凭空给出一个 quality（G-3）。"""
    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.points == ()
    assert series.chain_quality is None


def test_rows_after_date_to_do_not_join_the_chain(db_session, share_class):
    """上界之后的行对区间内的值毫无贡献，也就不该影响链路结论。

    与 _NAV_SQL 的「只设上界、不设下界」是同一条理由的两面：链路是
    effective_at <= t 的前向累乘，date_to 之后的行不在任何一条链路上。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2021, 6, 1), "1.5", "INFERRED")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.chain_quality == "EXACT"


_STORED = text("""
    SELECT effective_at, adjusted_nav FROM market.fund_nav
    WHERE share_class_id = :share_class_id ORDER BY effective_at
""")


def test_points_are_still_the_quantized_recomputed_values(db_session, share_class):
    """回归：包装成 NavSeries 之后，点本身的精度契约与值都不许变。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.1", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in series.points] == [
        Decimal("1.00000000"), Decimal("1.10000000")
    ]
    assert all(-p.adjusted_nav.as_tuple().exponent == 8 for p in series.points)
```

> 本文件里所有断言的对象都是**现算值**，不是 `market.fund_nav.adjusted_nav`
> 那个运维物化列 —— 后者自 Plan-1 Task 15 fix round 3 起已降级为运维物化值，
> 任何决策链路都不得读它。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_pit_contract.py -v`
Expected: FAIL —— `ImportError: cannot import name 'NavSeries' from
'fip.platform.decision_data.pit'`（同时 `weakest_quality` 也不存在）。
把 import 拆开逐条确认后，`test_adjusted_nav_is_not_optional` 的失败输出为
`assert typing.Optional[decimal.Decimal] is Decimal`。

Run: `.venv/bin/pytest tests/integration/test_chain_quality.py -v -m integration`
Expected: FAIL with `AttributeError: 'list' object has no attribute 'points'`。

- [ ] **Step 3: 最小实现**

`src/fip/platform/source/availability.py` —— 在 `AvailabilityQuality` 之后追加：

```python
# EXACT > DERIVED > INFERRED。数值只用于比较强弱，不落库、不进任何输出。
_QUALITY_STRENGTH: dict[AvailabilityQuality, int] = {
    AvailabilityQuality.EXACT: 3,
    AvailabilityQuality.DERIVED: 2,
    AvailabilityQuality.INFERRED: 1,
}


def weakest_quality(
    qualities: Iterable[str | AvailabilityQuality],
) -> AvailabilityQuality:
    """取一条链路上最弱的 availability_quality（min-over-chain）。

    ── 为什么是「最弱」──

    复权净值不是某一行的属性，而是整条前向累乘链路的函数：adj_t 依赖
    effective_at <= t 的【全部】净值行与分红/拆分行。链路上任何一行的
    available_at 是猜出来的（INFERRED），adj_t 的可见时点就同样是猜出来的。
    取平均、取多数、取最后一行都会让一条含 INFERRED 的链路对外呈现得比事实
    更可靠 —— 那是把不确定性藏起来，不是度量它。

    空链路【必须】抛错而不是返回一个默认值：没有行就没有结论，返回
    INFERRED 会让「一条都没有」与「有行但都靠猜」变得无法区分 —— 这正是
    Plan-1 在 grouping_status 上反复吃过亏的那一条（「没识别出」≠「确认没有」）。
    """
    strengths = []
    for quality in qualities:
        parsed = AvailabilityQuality(quality)  # 未知标签在此抛 ValueError
        strengths.append((_QUALITY_STRENGTH[parsed], parsed))
    if not strengths:
        raise ValueError("空链路没有 availability_quality 结论，不得返回默认值")
    return min(strengths, key=lambda pair: pair[0])[1]
```

顶部 import 补 `from collections.abc import Iterable`。

`src/fip/platform/decision_data/pit.py` —— `NavPoint` 收窄并加 `NavSeries`：

```python
@dataclass(frozen=True, slots=True)
class NavPoint:
    """PIT 解析出的单个净值点。

    adjusted_nav 是 Decimal 而【不是】Decimal | None：现算路径要么整条序列
    都有值、要么抛 AdjustedNavUnavailable（C-6 的 fail-closed 粒度已由
    Plan-1 提到整条序列）。留着 Optional 会让每个消费方都写一个永远不执行的
    None 分支，而那个分支里最自然的写法恰是填 0 或沿用上期。

    availability_quality 是【这一行自己】的质量，不是复权值的质量 ——
    后者看 NavSeries.chain_quality。两者容易混淆，且混淆的方向是危险的：
    逐行 EXACT 完全可能对应一条含 INFERRED 的链路。
    """

    effective_at: dt.date
    adjusted_nav: Decimal
    unit_nav: Decimal
    version: int
    availability_quality: str


@dataclass(frozen=True, slots=True)
class NavSeries:
    """一次 PIT 复权净值查询的完整结果：点 + 链路结论。

    chain_quality 是 points 之外【必须】随行的第二个事实：现算 adj_t 依赖
    date_from 之前的全部历史，那些行调用方在 points 里根本看不到
    （Plan-1 交接项二.1）。把它们的 availability_quality 按 min-over-chain
    聚合成一个值，是 Task 9 的 FactorInput.chain_quality 的唯一来源，
    并由 Task 9 原样传入 FactorResult.quality_flag（P2-21）。
    它【不】参与 FactorStatus 判定：AKShare 链路 100% INFERRED（G-15），
    塞进 WARNING 会让 VALID 在 M1 完全不可达。

    不变式：points 为空 ⟺ chain_quality 为 None。没有行就没有链路结论，
    有行却没有结论则说明聚合被漏掉了 —— 两个方向都在构造期拒绝。
    """

    points: tuple[NavPoint, ...]
    chain_quality: str | None

    def __post_init__(self) -> None:
        if bool(self.points) != (self.chain_quality is not None):
            raise ValueError(
                f"NavSeries 不变式被破坏：points={len(self.points)} 条，"
                f"chain_quality={self.chain_quality!r}。"
                "空序列不得携带 chain_quality，非空序列不得缺 chain_quality"
            )
```

`NavPitRepository` 的方法签名改返回类型：

```python
    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> NavSeries: ...
```

`src/fip/services/data_service/repositories/nav.py` —— 两条 SQL 各补一列
`availability_quality`（`_NAV_SQL` 已有；`_EVENT_SQL` 需新增），方法末尾改为：

```python
_EVENT_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, dividend_per_unit, split_ratio, availability_quality
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at <= :date_to
    ORDER BY effective_at, version DESC
""")
```

```python
        nav_rows = self._session.execute(_NAV_SQL, params).mappings().all()
        if not nav_rows:
            # 没有任何可见行 —— 没有链路，因此没有链路结论（不得填默认值）。
            return NavSeries(points=(), chain_quality=None)
        event_rows = self._session.execute(_EVENT_SQL, params).mappings().all()

        points = compute_adjusted_nav(...)   # 原样不动
        adjusted = {p.effective_at: _quantize_nav(p.adjusted_nav) for p in points}

        # 链路 = 参与累乘的【全部】行，而不是切片后返回的那些。
        # 两条 SQL 都只设上界不设下界，取回的正好就是整条链路（见文件顶部
        # 对「只设上界」的说明），所以这里直接对取回的全部行聚合。
        chain_quality = weakest_quality(
            [row["availability_quality"] for row in nav_rows]
            + [row["availability_quality"] for row in event_rows]
        ).value

        return NavSeries(
            points=tuple(
                NavPoint(
                    effective_at=row["effective_at"],
                    adjusted_nav=adjusted[row["effective_at"]],
                    unit_nav=row["unit_nav"],
                    version=row["version"],
                    availability_quality=row["availability_quality"],
                )
                for row in nav_rows
                if date_from <= row["effective_at"] <= date_to
            ),
            chain_quality=chain_quality,
        )
```

> ⚠️ 切片后 points 可能为空而 nav_rows 非空（请求窗口落在数据之前）。此时
> `NavSeries` 的不变式会拒绝 `points=() + chain_quality="..."`。这不是理论
> 情形：`test_rows_after_date_to_do_not_join_the_chain` 的镜像用例就会命中。
> 因此把不变式写成「chain_quality 随 **nav_rows** 而非 points」是错的 —— 正确
> 做法是切片为空时同样返回 `NavSeries(points=(), chain_quality=None)`：窗口内
> 没有任何点，调用方拿不到任何值，也就不需要（也不该拿到）链路结论。在
> `return` 之前先算出切片：

```python
        sliced = tuple(
            NavPoint(...)  # 同上
            for row in nav_rows
            if date_from <= row["effective_at"] <= date_to
        )
        if not sliced:
            return NavSeries(points=(), chain_quality=None)
        return NavSeries(points=sliced, chain_quality=chain_quality)
```

顶部 import 补：

```python
from fip.platform.decision_data.pit import NavPoint, NavSeries
from fip.platform.source.availability import weakest_quality
```

`src/fip/platform/cli.py` 的 `cmd_pit_nav`（第 186-212 行）：

```python
            series = PitDataContext(
                context=context, session=session
            ).navs().adjusted_nav_series(
                share_class.id,
                dt.date.fromisoformat(args.date_from),
                dt.date.fromisoformat(args.date_to),
            )
```

```python
    print(f"{share_class.display_name} @ decision_at={decision_at}  "
          f"共 {len(series.points)} 条  链路质量={series.chain_quality}")
    for point in series.points[:10]:
        print(f"  {point.effective_at}  unit={point.unit_nav}  "
              f"adj={point.adjusted_nav}  v{point.version}  {point.availability_quality}")
```

`tests/integration/test_pit_nav_repository.py` 的 `_series`（第 69-71 行）改为
返回点序列，18 处既有调用点不动：

```python
def _series(db_session, sc, decision_at, date_from, date_to):
    """既有用例断言的都是【点】；链路 quality 由 test_chain_quality.py 覆盖。"""
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to).points
```

`tests/integration/test_ingest_service.py:141-145`：

```python
    series = PitDataContext(context=ctx, session=db_session).navs().adjusted_nav_series(
        sc.id, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    # 1.10 → 除息 0.10 后 1.00：复权后收益为 0
    assert [p.adjusted_nav for p in series.points] == [Decimal("1.1"), Decimal("1.1")]
    # AKShare 链路恒 INFERRED（G-15），这里顺带钉住它
    assert series.chain_quality == "INFERRED"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_pit_contract.py -v`
Run: `.venv/bin/pytest tests/integration/test_chain_quality.py -v -m integration`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 17 条全绿；既有 281 条全绿（`_series` 与 `test_ingest_service`
的两处适配是唯一改动点）。`make typecheck` 必须干净 —— 类型收窄之后 mypy
会对任何残留的 `NavPoint.adjusted_nav is None` 分支报 unreachable 之外的错误；
当前 src 下没有这类分支（已确认），若有则一并删除，**不得**改成 `# type: ignore`。

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_pit_contract.py tests/integration/test_chain_quality.py
git commit --only \
  src/fip/platform/source/availability.py \
  src/fip/platform/decision_data/pit.py \
  src/fip/services/data_service/repositories/nav.py \
  src/fip/platform/cli.py \
  tests/unit/test_pit_contract.py \
  tests/integration/test_chain_quality.py \
  tests/integration/test_pit_nav_repository.py \
  tests/integration/test_ingest_service.py \
  -m "feat(pit): 收紧 PIT 数据契约 —— adjusted_nav 去 Optional，新增链路 quality 聚合

Plan-1 交接项二.1 / 二.2（打包项，改的是同一个 dataclass）：

· NavPoint.adjusted_nav 由 Decimal | None 收窄为 Decimal。现算路径要么全有值
  要么抛 AdjustedNavUnavailable，下游的 is None 分支是死代码，而那个分支里最
  自然的写法恰是 C-6 禁止的填 0 / 沿用上期。
· 新增 NavSeries(points, chain_quality)。现算 adj_t 依赖 date_from 之前的全部
  历史，调用方在 points 里看不到那些行；把链路上全部净值行与分红/拆分行的
  availability_quality 按 min-over-chain（EXACT > DERIVED > INFERRED）聚合成
  一个值随序列返回，作为 FactorInput.chain_quality 的唯一来源。
· 空链路不得返回默认 quality：weakest_quality([]) 抛错，NavSeries 用
  __post_init__ 双向锁死「空序列 ⟺ 无链路结论」。"
```

---

### Task 3: `quant_engine` —— 7 个数值函数 + QE-1 适应度测试

**Files:**
- Modify: `src/fip/quant_engine/__init__.py`（Plan-1 已建的空包，就地填实）
- Create: `src/fip/quant_engine/precision.py`
- Create: `src/fip/quant_engine/errors.py`
- Create: `src/fip/quant_engine/stats.py`
- Create: `src/fip/quant_engine/series.py`
- Create: `src/fip/quant_engine/correlation.py`
- Test: `tests/unit/test_quant_engine.py`（新建）
- Test: `tests/fitness/test_architecture.py`（新增 QE-1 两条）

> ✅ **【冲突 ⑤ 已按 Ruling PF-5 裁定解决】异常名统一为契约的
> `MathematicallyUndefined`。** 起草期本任务实现的是 `UndefinedResult`
> （另有 `QuantEngineError` 基类、`UnsupportedBasis`），与跨任务接口契约里的
> `MathematicallyUndefined` 分叉。裁定取契约的名字，本任务正文已全文改名 ——
> `QuantEngineError` / `UnsupportedBasis` / `InsufficientObservations` 三个名字不变。

> **P2-1【撤销 D-3】不搬迁包。** Plan-1 已经建好 `src/fip/quant_engine/` 与
> `src/fip/strategy_library/`（空包），且 `tests/unit/test_package_layout.py`、
> `tests/fitness/test_architecture.py` 的 `_py_files(...)` 与 `GUARDED_ROOTS`
> 都已经硬编码了这两个真实路径。再插一层 `libs` 中间目录是纯粹的 churn，还要改三处测试。
> spec §2.1 的目录树表达的是**分层关系**、不是文件系统路径。
> **本任务不做任何 `git mv`，也不改 `test_package_layout.py` 与
> `test_architecture.py` 的扫描根路径**——它们已经指向正确位置。

**Interfaces:**
- Consumes: 无（本任务不依赖 Task 1/2）
- Produces（跨任务接口契约原文，Task 9 / 12 / 13 消费）：
  - `fip.quant_engine.returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]`
  - `fip.quant_engine.stdev(xs: Sequence[Decimal], ddof: int) -> Decimal`
  - `fip.quant_engine.mean(xs: Sequence[Decimal]) -> Decimal`
  - `fip.quant_engine.median(xs: Sequence[Decimal]) -> Decimal`
  - `fip.quant_engine.running_max(xs: Sequence[Decimal]) -> list[Decimal]`
  - `fip.quant_engine.rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]`
  - `fip.quant_engine.spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal`
  - 异常：`QuantEngineError`（基类，`ValueError` 的子类）、`InsufficientObservations`、
    `MathematicallyUndefined`、`UnsupportedBasis` —— Task 9 据此把 `FactorStatus` 置为
    `UNAVAILABLE`（观测不足）或 `INVALID`（数学上无意义）
  - 精度契约常量：`QE_PRECISION = 60`、`QE_GUARD_DIGITS = 60`
  - 收益率口径字面量：`SIMPLE = "SIMPLE"`

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_quant_engine.py`：

```python
"""L1 数值层：无业务语义，全部 Decimal，精度契约显式（G-2 容差 1e-10）。

本文件的每一条断言都只关心【数值】。任何需要「因为它是净值 / 因为它是
Sharpe」才成立的性质都不属于这一层，属 strategy_library。
"""

from decimal import Decimal as D

import pytest

from fip.quant_engine import (
    QE_GUARD_DIGITS,
    QE_PRECISION,
    SIMPLE,
    InsufficientObservations,
    MathematicallyUndefined,
    UnsupportedBasis,
    mean,
    median,
    returns,
    rolling_windows,
    running_max,
    spearman,
    stdev,
)


# --- returns -----------------------------------------------------------

def test_returns_are_simple_and_one_shorter_than_the_input():
    assert returns([D("1.0"), D("1.1"), D("1.21")], SIMPLE) == [D("0.1"), D("0.1")]


def test_returns_of_a_single_price_is_empty_not_zero():
    """一个价格没有收益率 —— 返回 [0] 会凭空造出一个观测（G-3）。"""
    assert returns([D("1.0")], SIMPLE) == []
    assert returns([], SIMPLE) == []


def test_returns_rejects_an_unsupported_basis():
    """LOG 口径在 M1 明确不支持（D-9：return_basis = SIMPLE, PROVISIONAL）。

    静默按 SIMPLE 处理会让「配置里写了 LOG」这件事完全没有后果。
    """
    with pytest.raises(UnsupportedBasis):
        returns([D("1.0"), D("1.1")], "LOG")


@pytest.mark.parametrize("bad", [D("0"), D("-1.0")])
def test_returns_rejects_non_positive_denominator(bad):
    """价格为 0 / 负数时收益率无定义 —— 不得返回 inf 或 0。"""
    with pytest.raises(MathematicallyUndefined):
        returns([bad, D("1.0")], SIMPLE)


def test_returns_are_exact_for_values_representable_in_decimal():
    """用 Decimal 而非 float 的理由：0.1 在二进制下不可精确表示。"""
    assert returns([D("1"), D("1.1")], SIMPLE)[0] == D("0.1")


# --- stats -------------------------------------------------------------

def test_mean_of_empty_raises_rather_than_returning_zero():
    with pytest.raises(InsufficientObservations):
        mean([])


def test_mean_is_exact_on_a_terminating_quotient():
    assert mean([D("1"), D("2"), D("3")]) == D("2")


def test_median_odd_and_even():
    assert median([D("3"), D("1"), D("2")]) == D("2")
    assert median([D("4"), D("1"), D("3"), D("2")]) == D("2.5")


def test_median_of_empty_raises():
    with pytest.raises(InsufficientObservations):
        median([])


def test_stdev_sample_matches_the_hand_computed_value():
    """[1,2,3,4]：均值 2.5，偏差平方和 5，ddof=1 → sqrt(5/3)。"""
    expected = (D(5) / D(3)).sqrt()
    actual = stdev([D(1), D(2), D(3), D(4)], ddof=1)
    assert abs(actual - expected) < D("1e-40")


def test_stdev_population_differs_from_sample():
    """ddof 是【必填参数】而不是默认值：样本与总体在 n 小时差异不可忽略
    （D-9：volatility.ddof = 1，PROVISIONAL）。给默认值会让口径选择静默发生。
    """
    assert stdev([D(1), D(2), D(3), D(4)], ddof=0) != stdev(
        [D(1), D(2), D(3), D(4)], ddof=1
    )


def test_stdev_of_a_constant_series_is_zero():
    assert stdev([D(2), D(2), D(2)], ddof=1) == 0


def test_stdev_requires_more_observations_than_ddof():
    """n == ddof 时分母为 0 —— 抛错，不返回 0，也不返回 inf。

    返回 0 是这里最危险的错法：Sharpe = 超额收益 / 0 会变成除零，
    而返回 0 波动率的基金在任何排序里都是「零风险」。
    """
    with pytest.raises(InsufficientObservations):
        stdev([D(1)], ddof=1)
    with pytest.raises(InsufficientObservations):
        stdev([], ddof=0)


def test_stdev_rejects_negative_ddof():
    with pytest.raises(ValueError):
        stdev([D(1), D(2)], ddof=-1)


# --- series ------------------------------------------------------------

def test_running_max_is_non_decreasing_and_same_length():
    xs = [D(1), D(3), D(2), D(5), D(4)]
    out = running_max(xs)
    assert out == [D(1), D(3), D(3), D(5), D(5)]
    assert len(out) == len(xs)
    assert all(b >= a for a, b in zip(out, out[1:], strict=True))


def test_running_max_of_empty_is_empty():
    assert running_max([]) == []


def test_rolling_windows_are_full_windows_only():
    xs = [D(i) for i in range(10)]
    out = rolling_windows(xs, window=4, step=3)
    assert out == [xs[0:4], xs[3:7], xs[6:10]]
    assert all(len(w) == 4 for w in out)


def test_rolling_windows_returns_empty_when_the_input_is_shorter_than_the_window():
    """不得返回一个残缺窗口 —— 那会让 min_obs 的判定被悄悄绕过。"""
    assert rolling_windows([D(1), D(2)], window=4, step=1) == []


def test_rolling_windows_rejects_non_positive_window_or_step():
    with pytest.raises(ValueError):
        rolling_windows([D(1)], window=0, step=1)
    with pytest.raises(ValueError):
        rolling_windows([D(1)], window=1, step=0)


# --- correlation -------------------------------------------------------

def test_spearman_is_one_for_a_strictly_increasing_relation():
    xs = [D(1), D(2), D(3), D(4)]
    ys = [D(10), D(20), D(30), D(40)]
    assert spearman(xs, ys) == 1


def test_spearman_is_minus_one_for_a_strictly_decreasing_relation():
    xs = [D(1), D(2), D(3), D(4)]
    ys = [D(40), D(30), D(20), D(10)]
    assert spearman(xs, ys) == -1


def test_spearman_is_rank_based_not_value_based():
    """单调非线性变换不改变 Spearman —— 这正是 IC 选它而非 Pearson 的理由。"""
    xs = [D(1), D(2), D(3), D(4)]
    linear = [D(1), D(2), D(3), D(4)]
    convex = [D(1), D(4), D(9), D(16)]
    assert spearman(xs, linear) == spearman(xs, convex)


def test_spearman_uses_average_ranks_for_ties():
    """并列取【平均秩】，这是 Spearman 的标准并列处理。

    ⚠️ 这与 D-20 为基金排名裁定的 COMPETITION_RANK 【不是】同一件事：
    COMPETITION_RANK 用于对外呈现的名次（并列占用相同名次、后续跳号），
    平均秩用于相关系数的内部计算（跳号会让相关系数产生系统性偏差）。
    两者服务于不同目的，不得互相替换。
    [1,1,2] 的平均秩是 [1.5, 1.5, 3]。
    """
    assert spearman([D(1), D(1), D(2)], [D(5), D(5), D(9)]) == 1


def test_spearman_rejects_length_mismatch():
    with pytest.raises(ValueError):
        spearman([D(1), D(2)], [D(1)])


def test_spearman_needs_at_least_two_observations():
    with pytest.raises(InsufficientObservations):
        spearman([D(1)], [D(2)])


def test_spearman_is_undefined_when_one_side_is_all_ties():
    """全并列一侧的秩方差为 0 —— 相关系数无定义，抛错而不是返回 0。

    返回 0 会被下游读成「该因子与后续收益不相关」，而事实是
    「这个横截面上该因子没有区分度，算不出相关性」。两者结论完全不同。
    """
    with pytest.raises(MathematicallyUndefined):
        spearman([D(1), D(1), D(1)], [D(1), D(2), D(3)])


# --- 精度契约（G-2）----------------------------------------------------

def test_precision_contract_is_declared_and_generous():
    """内部计算位数 = 有效位 + 保护位，与 adjusted_nav.py 同一套做法。"""
    assert QE_PRECISION == 60
    assert QE_GUARD_DIGITS == 60


def test_results_are_bit_identical_on_recomputation():
    """G-2：同一输入重算必须【完全一致】，不是「在容差内一致」。"""
    xs = [D("1.0000001") ** i for i in range(1, 60)]
    assert stdev(xs, ddof=1) == stdev(xs, ddof=1)
    assert spearman(xs, list(reversed(xs))) == spearman(xs, list(reversed(xs)))


def test_long_chain_stays_well_inside_the_reproducibility_tolerance():
    """保护位真的起作用：1000 期链路上 mean 的相对误差远小于 1e-10。"""
    xs = [D(1)] * 1000
    assert mean(xs) == D(1)
    assert abs(stdev(xs, ddof=1)) < D("1e-50")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_quant_engine.py -v`
Expected: FAIL —— `ImportError: cannot import name 'QE_GUARD_DIGITS' from
'fip.quant_engine'`（收集阶段；包已由 Plan-1 建好但是空的）。

- [ ] **Step 3: 最小实现**

**不搬迁、不 `git mv`**（P2-1）：`src/fip/quant_engine/` 是 Plan-1 已建的空包，
直接往里加模块。

`src/fip/quant_engine/errors.py`：

```python
class QuantEngineError(ValueError):
    """数值层无法产出结果。

    继承 ValueError 而不是 RuntimeError：这些都是【输入不满足前提】，
    不是运行环境问题。调用方（strategy_library）据此把 FactorStatus 置为
    UNAVAILABLE 或 INVALID，【绝不】捕获后填 0 / 填 inf / 填组内均值（G-3）。
    """


class InsufficientObservations(QuantEngineError):
    """观测数不足以定义该统计量（如 n <= ddof、空序列）。

    映射到 FactorStatus.UNAVAILABLE（D-10：观测数 < min_obs）。
    """


class MathematicallyUndefined(QuantEngineError):
    """数学上无定义（分母为 0、负方差、非正的价格基数）。

    ⚠️ **映射到哪个 status 由调用方按情形判定，不是本层的事**（P2-20 修订 D-10）：

      · 分母为 0 这类【良性不可算】（零回撤、零波动）→ `UNAVAILABLE`
      · 负方差 / NaN / 序列自相矛盾这类【数值链路坏了】 → `INVALID`

    D-10 原本把「分母为 0」一律列在 INVALID 下。INVALID 会传导到
    `evaluation_status = FAILED` 并须告警 —— 照那样实现，**一只从未回撤的
    基金会触发告警**。因此本异常只说「算不出来」，不预判严重程度。
    """


class UnsupportedBasis(QuantEngineError):
    """请求的口径本层不实现。

    静默退回到默认口径会让配置里写下的口径选择完全没有后果 —— 这与
    Plan-1 在 config loader 上确立的「不阻断但不静默」是同一条原则的严格版：
    口径不是可以将就的东西。
    """
```

`src/fip/quant_engine/precision.py`：

```python
"""精度契约（G-2：可复现性容差 1e-10）。

做法与 services/data_service/normalization/adjusted_nav.py 一致，且是刻意
对齐的：内部滚动用「有效位 + 保护位」，只在产出时舍回有效位。先降精度再
累加会让舍入误差随序列长度累积 —— 因子序列可达数千期，那正是这一层最长的
链路。

60 位保护位是宽裕余量而非从误差增长公式推出的紧界（与 adjusted_nav.py 的
说明同源）。Decimal 的运算在给定 context 下是确定性的，因此「同一输入重算
必须完全一致」是构造性成立的，不是靠容差兜住的。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal, localcontext

QE_PRECISION = 60
QE_GUARD_DIGITS = 60
_COMPUTE_PRECISION = QE_PRECISION + QE_GUARD_DIGITS


@contextmanager
def computing() -> Iterator[None]:
    """在保护位精度下做中间运算。

    默认 context 的 traps 保留不动：DivisionByZero / InvalidOperation 必须
    抛出，不得静默产出 NaN 或 Infinity（G-3 的数值层对应物）。
    """
    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        yield


def finalize(value: Decimal) -> Decimal:
    """把中间结果舍回对外的有效位数。"""
    with localcontext() as ctx:
        ctx.prec = QE_PRECISION
        return +value
```

`src/fip/quant_engine/stats.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.quant_engine.errors import InsufficientObservations, MathematicallyUndefined
from fip.quant_engine.precision import computing, finalize


def mean(xs: Sequence[Decimal]) -> Decimal:
    values = list(xs)
    if not values:
        raise InsufficientObservations("mean 需要至少 1 个观测，实得 0")
    with computing():
        total = sum(values, Decimal(0))
        return finalize(total / Decimal(len(values)))


def median(xs: Sequence[Decimal]) -> Decimal:
    values = sorted(xs)
    n = len(values)
    if n == 0:
        raise InsufficientObservations("median 需要至少 1 个观测，实得 0")
    mid = n // 2
    if n % 2 == 1:
        return finalize(values[mid])
    with computing():
        return finalize((values[mid - 1] + values[mid]) / Decimal(2))


def stdev(xs: Sequence[Decimal], ddof: int) -> Decimal:
    """标准差。ddof 是【必填】的，没有默认值。

    D-9 把 volatility.ddof = 1 登记为 PROVISIONAL 口径选择。给这里一个默认值
    会让那条配置形同虚设：调用方忘记传时会静默拿到某一个口径，而样本与总体
    在 n 较小时差异不可忽略。
    """
    if ddof < 0:
        raise ValueError(f"ddof 不得为负，实得 {ddof}")
    values = list(xs)
    n = len(values)
    if n - ddof <= 0:
        raise InsufficientObservations(
            f"stdev(ddof={ddof}) 需要至少 {ddof + 1} 个观测，实得 {n}"
        )
    with computing():
        m = sum(values, Decimal(0)) / Decimal(n)
        ss = sum(((v - m) ** 2 for v in values), Decimal(0))
        variance = ss / Decimal(n - ddof)
        if variance < 0:
            raise MathematicallyUndefined(f"方差为负（{variance}），数值不稳定")
        return finalize(variance.sqrt())
```

`src/fip/quant_engine/series.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.quant_engine.errors import MathematicallyUndefined, UnsupportedBasis
from fip.quant_engine.precision import computing, finalize

SIMPLE = "SIMPLE"


def returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]:
    """相邻两点的收益率序列，长度为 len(prices) - 1。

    basis 只接受 SIMPLE（r_t = p_t / p_{t-1} - 1）。对数口径本层不实现：
    对数收益不可横截面相加，而本平台的因子标准化与 IC 全是横截面运算。
    传入其它口径【抛错】而不是退回 SIMPLE。
    """
    if basis != SIMPLE:
        raise UnsupportedBasis(f"本层只实现 {SIMPLE} 口径，收到 {basis!r}")
    values = list(prices)
    if len(values) < 2:
        return []
    out: list[Decimal] = []
    with computing():
        for previous, current in zip(values, values[1:], strict=True):
            if previous <= 0:
                raise MathematicallyUndefined(
                    f"基数 {previous} 非正，收益率无定义（不得返回 0 或 inf）"
                )
            out.append(finalize(current / previous - Decimal(1)))
    return out


def running_max(xs: Sequence[Decimal]) -> list[Decimal]:
    """前缀最大值序列，与输入等长、单调不减。"""
    out: list[Decimal] = []
    current: Decimal | None = None
    for value in xs:
        current = value if current is None or value > current else current
        out.append(current)
    return out


def rolling_windows(
    xs: Sequence[Decimal], window: int, step: int
) -> list[list[Decimal]]:
    """只产出【完整】窗口。

    残缺窗口必须被丢弃而不是补齐：补齐等于用更少的观测冒充一个窗口，
    会让 min_obs 的判定（D-10）被悄悄绕过。
    """
    if window < 1:
        raise ValueError(f"window 必须 >= 1，实得 {window}")
    if step < 1:
        raise ValueError(f"step 必须 >= 1，实得 {step}")
    values = list(xs)
    return [
        values[i : i + window]
        for i in range(0, len(values) - window + 1, step)
    ]
```

`src/fip/quant_engine/correlation.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.quant_engine.errors import InsufficientObservations, MathematicallyUndefined
from fip.quant_engine.precision import computing, finalize


def _average_ranks(values: list[Decimal]) -> list[Decimal]:
    """并列取平均秩（Spearman 的标准并列处理）。

    ⚠️ 与 D-20 裁定的 COMPETITION_RANK 是两回事：后者用于对外呈现的名次
    （并列占用相同名次、之后跳号），平均秩用于相关系数的内部计算 ——
    跳号会让秩序列的均值偏离 (n+1)/2，给相关系数引入系统性偏差。
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks: list[Decimal] = [Decimal(0)] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        with computing():
            average = (Decimal(i + 1) + Decimal(j + 1)) / Decimal(2)
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal:
    """秩相关系数。IC 用它而非 Pearson：因子与后续收益的关系未必线性。

    任一侧全并列时秩方差为 0，相关系数【无定义】—— 抛 MathematicallyUndefined 而不是
    返回 0。返回 0 会被下游读成「该因子与后续收益不相关」，而事实是
    「这个横截面上该因子没有区分度，算不出相关性」。
    """
    a = list(xs)
    b = list(ys)
    if len(a) != len(b):
        raise ValueError(f"两个序列长度不等：{len(a)} vs {len(b)}")
    if len(a) < 2:
        raise InsufficientObservations(f"spearman 需要至少 2 个观测，实得 {len(a)}")
    ra = _average_ranks(a)
    rb = _average_ranks(b)
    with computing():
        n = Decimal(len(a))
        ma = sum(ra, Decimal(0)) / n
        mb = sum(rb, Decimal(0)) / n
        cov = sum(((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True)), Decimal(0))
        va = sum(((x - ma) ** 2 for x in ra), Decimal(0))
        vb = sum(((y - mb) ** 2 for y in rb), Decimal(0))
        if va == 0 or vb == 0:
            raise MathematicallyUndefined(
                "至少一侧的秩全部并列，秩方差为 0，Spearman 无定义"
            )
        # 写成 (va * vb).sqrt() 而不是 va.sqrt() * vb.sqrt()：后者取两次
        # 无理数的近似再相乘，完全单调的输入也会得到 0.9999…9 而不是 1，
        # 让「完美秩相关 == 1」这条最基本的断言变得只能靠容差成立。
        # 前者在 va * vb 恰为完全平方（秩序列的常见情形）时是精确的。
        return finalize(cov / (va * vb).sqrt())
```

`src/fip/quant_engine/__init__.py`：

```python
"""L1 数值层：矩阵、统计、时序。【无任何业务语义】（QE-1）。

本包不得 import fip.strategy_library / fip.services / fip.platform，
标识符里也不得出现基金业务词汇 —— 两条都由
tests/fitness/test_architecture.py 断言。判据不是「用不用得上」，而是
「这段代码换到另一个完全不同的领域还成不成立」。
"""

from fip.quant_engine.correlation import spearman
from fip.quant_engine.errors import (
    InsufficientObservations,
    QuantEngineError,
    MathematicallyUndefined,
    UnsupportedBasis,
)
from fip.quant_engine.precision import QE_GUARD_DIGITS, QE_PRECISION
from fip.quant_engine.series import SIMPLE, returns, rolling_windows, running_max
from fip.quant_engine.stats import mean, median, stdev

__all__ = [
    "QE_GUARD_DIGITS",
    "QE_PRECISION",
    "SIMPLE",
    "InsufficientObservations",
    "QuantEngineError",
    "MathematicallyUndefined",
    "UnsupportedBasis",
    "mean",
    "median",
    "returns",
    "rolling_windows",
    "running_max",
    "spearman",
    "stdev",
]
```

> **不动测试的扫描根路径（P2-1）。** `tests/unit/test_package_layout.py:22-37`
> 已经列着 `"fip.quant_engine"` / `"fip.strategy_library"`，
> `tests/fitness/test_architecture.py` 已经在用 `_py_files("strategy_library")`、
> `_py_files("quant_engine")`，`GUARDED_ROOTS` 已经是
> `("strategy_library",)` / `("quant_engine",)`。**三处都已正确，不要改。**
> 本步骤只往 `src/fip/quant_engine/` 里加文件。

- [ ] **Step 4: 写 QE-1 适应度测试并确认它会红**

在 `tests/fitness/test_architecture.py` 末尾追加：

```python
# --- QE-1：Quant Engine 不含业务语义 -----------------------------------

QE_BANNED_PREFIXES = (
    "fip.strategy_library",
    "fip.services",
    "fip.platform",
)


def test_quant_engine_does_not_depend_on_upper_layers():
    """QE-1 前半：依赖方向单向 strategy_library → quant_engine。

    反向依赖不会报错（Python 允许），只会在下一次有人想把 quant_engine
    抽成独立库时才暴露 —— 那时它已经缠满了业务类型。
    """
    offenders = []
    for f in _py_files("quant_engine"):
        bad = [
            m for m in _dotted_imports(f)
            if any(_touches(m, prefix) for prefix in QE_BANNED_PREFIXES)
        ]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"quant_engine 依赖了上层：{offenders}"


# 基金业务词汇。判据是「这个词在一个与基金无关的领域里还讲不讲得通」：
# window / step / ddof / ranks 讲得通，nav / sharpe / peer 讲不通。
# 刻意【不】收录 price / return / correlation —— 它们是通用数值/统计词汇，
# 收录会让接口契约里已经定死的 returns(prices, basis) 无法落地。
FUND_VOCABULARY = {
    "fund", "nav", "sharpe", "sortino", "calmar", "drawdown", "peer",
    "factor", "score", "benchmark", "universe", "portfolio", "dividend",
    "eligibility", "tier", "profile", "volatility", "alpha", "backtest",
    "strategy", "fee", "share_class", "shareclass", "investment",
}


def _identifier_words(name: str) -> set[str]:
    """把标识符切成词。用词级相等而非裸子串匹配。

    裸子串会把 'navigate' 判成含 'nav'，而一条会误报的适应度测试的下场
    是被人直接关掉。词级匹配再额外容忍一个复数 s（drawdowns → drawdown）。
    """
    words = {w for w in name.lower().split("_") if w}
    return words | {w[:-1] for w in words if w.endswith("s") and len(w) > 1}


def _declared_identifiers(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {path.stem}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_quant_engine_identifiers_carry_no_fund_vocabulary():
    """QE-1 后半：标识符不得出现基金业务词汇。

    什么情况下它会红：有人在这一层写下 def annualized_nav_return(...)
    或 class SharpeInput —— 那意味着业务语义正在往数值层渗，而这一层的
    全部价值就是它对领域一无所知。
    """
    offenders = []
    for f in _py_files("quant_engine"):
        hits = sorted(
            name for name in _declared_identifiers(f)
            if _identifier_words(name) & FUND_VOCABULARY
        )
        if hits:
            offenders.append((f.relative_to(SRC), hits))
    assert not offenders, f"quant_engine 出现基金业务词汇：{offenders}"


def test_qe_vocabulary_scanner_actually_matches():
    """守卫：直接对扫描器断言，不依赖仓库当前状态。

    没有这条，上面那条在 FUND_VOCABULARY 拼错或 _identifier_words 退化成
    恒返回空集时会静默变成一条永远通过的测试。
    """
    assert _identifier_words("annualized_nav_return") & FUND_VOCABULARY == {"nav"}
    assert _identifier_words("rolling_windows") & FUND_VOCABULARY == set()
    assert _identifier_words("drawdowns") & FUND_VOCABULARY == {"drawdown"}
    assert _identifier_words("navigate") & FUND_VOCABULARY == set()
```

制造红灯以证伪（G-18）：

```bash
cat >> src/fip/quant_engine/stats.py <<'PY'


def annualized_nav_drawdown(xs):  # 临时：证伪 QE-1
    from fip.services.data_service.models.market import FundNav  # noqa: F401
    return xs
PY
.venv/bin/pytest tests/fitness/test_architecture.py -k quant_engine -v
```

Expected: 两条同时 FAIL ——
`AssertionError: quant_engine 依赖了上层：[(PosixPath('quant_engine/stats.py'),
['fip.services.data_service.models.market', ...])]` 与
`AssertionError: quant_engine 出现基金业务词汇：[(PosixPath('quant_engine/stats.py'),
['FundNav', 'annualized_nav_drawdown'])]`。把这段输出写进报告，然后还原：

Run: `git checkout -- src/fip/quant_engine/stats.py`

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_quant_engine.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 30 条全绿（`test_quant_engine.py` 26 条 + QE-1 3 条 + 扫描器守卫 1 条）；
既有 281 条全绿（本任务**不改任何既有测试**——P2-1 撤销了搬迁）。

- [ ] **Step 6: 提交**

```bash
git add src/fip/quant_engine tests/unit/test_quant_engine.py
git commit --only \
  src/fip/quant_engine \
  tests/unit/test_quant_engine.py \
  tests/fitness/test_architecture.py \
  -m "feat(quant-engine): 填实 src/fip/quant_engine 的 7 个函数 + QE-1

P2-1【撤销 D-3】：不再插一层 libs 中间目录。Plan-1 已建好 src/fip/quant_engine 空包，
且三处测试（test_package_layout.py、test_architecture.py 的 _py_files 与
GUARDED_ROOTS）已硬编码这个真实路径；搬迁是纯 churn。spec §2.1 的目录树
表达的是分层关系，不是文件系统路径。

7 个函数按跨任务接口契约逐字实现，全部 Decimal：
returns / stdev / mean / median / running_max / rolling_windows / spearman。
精度契约显式化（QE_PRECISION=60 + 60 位保护位，做法与 adjusted_nav.py 对齐），
G-2 的『同一输入重算一致』是构造性成立的而非靠容差。

四类失败一律抛错、绝不填值（G-3）：观测不足、数学无定义、口径不支持、
参数非法。Spearman 全并列时抛 MathematicallyUndefined 而不是返回 0 —— 后者会被
读成『不相关』，而事实是『算不出相关性』。

QE-1 两条适应度测试（依赖方向 + 标识符词汇），并附扫描器自身的守卫用例。
证伪记录：临时加入 annualized_nav_drawdown + import FundNav，两条同时转红。"
```

---

### Task 4: `strategy_library` 骨架 + SDL-1 / SDL-2 / SDL-3 适应度测试

**Files:**
- Create: `src/fip/strategy_library/factor/__init__.py`
- Create: `src/fip/strategy_library/factor/definitions.py`
- Create: `src/fip/strategy_library/factor/status.py`
- Create: `src/fip/strategy_library/peer_group/__init__.py`
- Create: `src/fip/strategy_library/score/__init__.py`
- Create: `src/fip/strategy_library/ranking/__init__.py`
- Create: `src/fip/strategy_library/universe/__init__.py`
- Modify: `src/fip/strategy_library/__init__.py`
- Create: `src/fip/platform/versioning.py`（SDL-3 的落点）
- Modify: `src/fip/platform/cli.py:169-181`（`cmd_pit_nav` 的 `code_version` 由常量改为实算）
- Modify: `tests/fitness/test_architecture.py`（SDL-1 补 `fip.services.*` 前缀禁令，D-27；新增 SDL-3 三条）
- Test: `tests/unit/test_factor_contract.py`（新建）
- Test: `tests/unit/test_code_version.py`（新建）

**Interfaces:**
- Consumes（Task 3 产出）：`fip.quant_engine` 已填实（Plan-1 建的空包，就地填，
  **不搬迁**——P2-1）；`src/fip/strategy_library/` 同样是 Plan-1 已建的空包，就地填
- Produces（跨任务接口契约原文，Task 9 起全线消费）：
  - `fip.strategy_library.factor.FactorStatus`（StrEnum：`VALID` / `WARNING` /
    `INVALID` / `UNAVAILABLE`）
  - `fip.strategy_library.factor.PreferenceDirection`（StrEnum：
    `HIGHER_IS_BETTER` / `LOWER_IS_BETTER`）
  - `fip.strategy_library.factor.FactorInput`（frozen slots dataclass：
    `effective_at: date`、`adjusted_navs: tuple[Decimal, ...]`、
    `nav_dates: tuple[date, ...]`、`chain_quality: str`、
    `risk_free_rate: Decimal | None`、
    **`mar_daily: tuple[Decimal, ...] | None`**（P2-22：逐期序列，与收益率
    序列 1:1 对齐；**不是**标量 `Decimal | None`））
  - `fip.strategy_library.factor.FactorResult`（frozen slots dataclass：
    `factor_id: str`、`value: Decimal | None`、`status: FactorStatus`、
    `reason: str`、`observation_count: int`、
    **`quality_flag: str`**（P2-21：`EXACT`/`DERIVED`/`INFERRED`，
    链路 quality 独立成字段，**不再**参与 `WARNING` 判定））
  - `fip.platform.versioning.compute_code_version(roots: Iterable[pathlib.Path] | None = None) -> str`
  - `fip.platform.versioning.CODE_VERSION_ROOTS: tuple[pathlib.Path, ...]`
- 明确**不**产出：`compute_factor`（Task 9）、`percentile_rank`（Task 12）、
  `PeerGroupKey`（Task 11）—— 本任务只建骨架与契约类型

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_factor_contract.py`：

```python
"""因子契约类型的形状（跨任务接口契约的唯一权威定义在实现计划里）。

Task 9 起有六个任务同时消费这些类型。任何一个字段名/类型漂移都会在
下游产生一个「看起来能跑但语义错了」的实现，因此在骨架阶段就锁死。
"""

import datetime as dt
import typing
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from fip.strategy_library.factor import (
    FactorInput,
    FactorResult,
    FactorStatus,
    PreferenceDirection,
)


def test_factor_status_has_exactly_four_values():
    """四值，不多不少。多一个值意味着下游的 match 出现未覆盖分支。"""
    assert {s.value for s in FactorStatus} == {
        "VALID", "WARNING", "INVALID", "UNAVAILABLE"
    }


def test_factor_status_is_a_string_enum():
    """StrEnum：直接落库、直接进 JSON，不需要在边界上再转一次。"""
    assert FactorStatus.VALID == "VALID"


def test_preference_direction_has_exactly_two_values():
    """『中性』方向【不实现】（D-11 第 3 点）：M1 无 Benchmark、TE 恒
    UNAVAILABLE。这是一个已知缺口，写在枚举注释里；这里锁住它没有被
    悄悄补上一个语义未定的第三值。
    """
    assert {d.value for d in PreferenceDirection} == {
        "HIGHER_IS_BETTER", "LOWER_IS_BETTER"
    }


def test_factor_input_fields_match_the_contract():
    hints = typing.get_type_hints(FactorInput)
    assert [f.name for f in fields(FactorInput)] == [
        "effective_at", "adjusted_navs", "nav_dates",
        "chain_quality", "risk_free_rate", "mar_daily",
    ]
    assert hints["effective_at"] is dt.date
    assert hints["chain_quality"] is str
    assert hints["risk_free_rate"] == Decimal | None
    # P2-22：序列，不是标量。这条断言就是防止有人「顺手」改回 Decimal | None ——
    # 那会让 RISK_FREE 模式的 MAR 只能取均值，即伪造一个从未被决策的标尺。
    assert hints["mar_daily"] == tuple[Decimal, ...] | None


def test_factor_input_rejects_mar_daily_misaligned_with_the_return_series():
    """P2-22：mar_daily 与【收益率】序列 1:1 对齐 —— 收益率比净值少一期。

    长度差一是最容易发生、最难发现的错位：Sortino 会照常算出一个数。"""
    with pytest.raises(ValueError, match="mar_daily"):
        FactorInput(
            effective_at=dt.date(2026, 8, 31),
            adjusted_navs=(Decimal("1.0"), Decimal("1.1"), Decimal("1.2")),
            nav_dates=(dt.date(2026, 8, 29), dt.date(2026, 8, 30), dt.date(2026, 8, 31)),
            chain_quality="INFERRED",
            risk_free_rate=None,
            mar_daily=(Decimal(0), Decimal(0), Decimal(0)),   # 3 期，应为 2 期
        )


def test_factor_input_is_frozen():
    """纯函数只吃它（SDL-1）。可变输入会让『同一输入重算一致』（G-2）失效。"""
    inp = FactorInput(
        effective_at=dt.date(2026, 8, 31),
        adjusted_navs=(Decimal("1.0"),),
        nav_dates=(dt.date(2026, 8, 31),),
        chain_quality="INFERRED",
        risk_free_rate=None,
        mar_daily=None,
    )
    with pytest.raises(FrozenInstanceError):
        inp.chain_quality = "EXACT"  # type: ignore[misc]


def test_factor_input_rejects_misaligned_navs_and_dates():
    """两个并行元组长度必须一致 —— 错位后每个因子都会静默算错。"""
    with pytest.raises(ValueError):
        FactorInput(
            effective_at=dt.date(2026, 8, 31),
            adjusted_navs=(Decimal("1.0"), Decimal("1.1")),
            nav_dates=(dt.date(2026, 8, 31),),
            chain_quality="INFERRED",
            risk_free_rate=None,
            mar_daily=None,
        )


def test_factor_result_value_is_none_for_every_non_valid_status():
    """G-3 的类型层落地：非 VALID 时 value 必须为 None，【绝不填 0】。"""
    for status in (FactorStatus.INVALID, FactorStatus.UNAVAILABLE):
        with pytest.raises(ValueError, match="value"):
            FactorResult(
                factor_id="F-RET-001", value=Decimal("0"), status=status,
                reason="观测不足", observation_count=3, quality_flag="INFERRED",
            )


def test_factor_result_requires_a_reason_when_not_valid():
    """status 非 VALID 时 reason 必填（接口契约原文）。

    空 reason 会让下游只知道『没有值』而不知道『为什么没有值』——
    UNAVAILABLE 与 INVALID 的处置方式完全不同（前者按缺失处理，后者要告警）。
    """
    with pytest.raises(ValueError, match="reason"):
        FactorResult(
            factor_id="F-RET-001", value=None,
            status=FactorStatus.UNAVAILABLE, reason="", observation_count=0,
            quality_flag="INFERRED",
        )


def test_factor_result_accepts_a_value_when_valid():
    result = FactorResult(
        factor_id="F-RET-001", value=Decimal("0.12"),
        status=FactorStatus.VALID, reason="", observation_count=252,
        quality_flag="INFERRED",
    )
    assert result.value == Decimal("0.12")


def test_m1_的常态是_VALID_加_INFERRED_而不是_WARNING():
    """P2-21：AKShare 链路 100% INFERRED（G-15）。链路 quality 若还留在
    WARNING 的触发条件里，VALID 在 M1 【完全不可达】，下游会把一切当异常。

    这条测试把「常态」钉住 —— 与 D-19『M1 常态是 PARTIAL』是同一类保护。"""
    result = FactorResult(
        factor_id="F-RET-001", value=Decimal("0.12"),
        status=FactorStatus.VALID, reason="", observation_count=252,
        quality_flag="INFERRED",
    )
    assert result.status is FactorStatus.VALID
    assert result.quality_flag == "INFERRED"


def test_factor_result_valid_must_carry_a_value():
    """反向：VALID 却没有值，说明产出方漏了一条分支。"""
    with pytest.raises(ValueError, match="value"):
        FactorResult(
            factor_id="F-RET-001", value=None,
            status=FactorStatus.VALID, reason="", observation_count=252,
            quality_flag="INFERRED",
        )
```

新建 `tests/unit/test_code_version.py`：

```python
"""SDL-3：strategy_library 的版本参与 Code Version 计算。

Code Version 是决策快照的复现入口之一（DEC-3）。若策略库改了而 Code Version
不变，两次跑出不同结果的决策会带着【同一个】版本号落库 —— 快照从此不能
证明任何事情。
"""

import pathlib

import pytest

from fip.platform.versioning import CODE_VERSION_ROOTS, compute_code_version


def test_strategy_library_is_one_of_the_roots():
    assert any(
        root.parts[-2:] == ("strategy_library",) for root in CODE_VERSION_ROOTS
    )


def test_quant_engine_is_one_of_the_roots():
    assert any(
        root.parts[-2:] == ("quant_engine",) for root in CODE_VERSION_ROOTS
    )


def test_every_declared_root_exists():
    """守卫：根目录被改名后哈希会静默算在一个空集合上。"""
    for root in CODE_VERSION_ROOTS:
        assert root.is_dir(), f"{root} 不存在，Code Version 会静默漏掉它"


def test_code_version_is_a_stable_hex_digest():
    first = compute_code_version()
    second = compute_code_version()
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def _root(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    root = tmp_path / name
    root.mkdir()
    (root / "m.py").write_text(body, encoding="utf-8")
    return root


def test_content_change_changes_the_version(tmp_path):
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "m.py").write_text("X = 2\n", encoding="utf-8")
    assert compute_code_version([root]) != before


def test_new_file_changes_the_version(tmp_path):
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "n.py").write_text("Y = 1\n", encoding="utf-8")
    assert compute_code_version([root]) != before


def test_rename_changes_the_version(tmp_path):
    """内容相同但文件名不同必须得到不同版本 —— 路径进哈希，不只哈希内容。"""
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "m.py").rename(root / "renamed.py")
    assert compute_code_version([root]) != before


def test_non_python_files_do_not_change_the_version(tmp_path):
    """只哈希 .py：__pycache__、编辑器临时文件不得让版本号无故变化。"""
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    assert compute_code_version([root]) == before


def test_missing_root_fails_loudly(tmp_path):
    """不存在的根【抛错】而不是跳过：跳过会让版本号在缺半个库时照常产出。"""
    with pytest.raises(FileNotFoundError):
        compute_code_version([tmp_path / "nope"])


def test_a_real_change_in_strategy_library_changes_the_real_version():
    """最强的一条：在真实的 strategy_library 里写一个文件，版本必须变。

    什么情况下它会红：CODE_VERSION_ROOTS 里漏了 strategy_library，或
    compute_code_version 只哈希了包名而没哈希内容。用 try/finally 保证
    临时文件一定被清掉。
    """
    root = next(
        r for r in CODE_VERSION_ROOTS if r.parts[-2:] == ("strategy_library",)
    )
    probe = root / "_code_version_probe.py"
    before = compute_code_version()
    try:
        probe.write_text("PROBE = 1\n", encoding="utf-8")
        assert compute_code_version() != before
    finally:
        probe.unlink(missing_ok=True)
    assert compute_code_version() == before
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_factor_contract.py tests/unit/test_code_version.py -v`

Expected: 两个文件都在收集阶段 FAIL ——
`ModuleNotFoundError: No module named 'fip.strategy_library.factor'` 与
`ModuleNotFoundError: No module named 'fip.platform.versioning'`。

- [ ] **Step 3: 最小实现**

`src/fip/strategy_library/factor/status.py`：

```python
from enum import StrEnum


class FactorStatus(StrEnum):
    """因子值的状态四值。

    上游 01-fund-evaluation §7.3 只给了【消费方】处理规则；【生产方】何时
    置哪个值在缺失的 08-factor-output 里，由设计定案 D-10 补齐：

      VALID        观测数 >= min_obs，全部依赖（R_f / MAR）可用，未触发降级
      WARNING      观测数落在 [min_obs, min_obs × 1.5)　——【唯一】触发条件
      INVALID      计算过程产生【数学上无意义】的结果：NaN、负方差、序列自相矛盾
      UNAVAILABLE  观测数 < min_obs；必需依赖缺失（无 MAR 配置、无 R_f）；
                   或分母为 0 这类【良性不可算】（ZERO_MAX_DRAWDOWN / ZERO_VOLATILITY）

    ── P2-21【修订 D-10】链路 quality 不进 status ──

    D-10 原本把「输入序列的链路含 INFERRED」列为 WARNING 的第二触发条件。
    **已裁定删除。** 理由：AKShare 链路 100% 是 INFERRED（G-15），两者相乘
    的结果是【每个因子、每只基金、每个时点都是 WARNING，VALID 在 M1 完全
    不可达】。下游若把 WARNING 当异常处理，M1 会表现为「什么都不正常」。

    `FactorStatus` 只反映**可计算性**，不反映**数据出处**。链路 quality 移到
    `FactorResult.quality_flag` 独立字段，随结果传递但不占用 status。

    ── P2-20【修订 D-10】分母为 0 是 UNAVAILABLE 不是 INVALID ──

    `ZERO_MAX_DRAWDOWN` / `ZERO_VOLATILITY` 是「好消息型不可用」。判成 INVALID
    会传导到 `evaluation_status = FAILED` 并须告警 —— 那意味着**一只从未回撤
    的基金会触发告警**。INVALID 只留给真正数学无意义的结果。

    消费方规则（上游原文）：VALID 参与；WARNING 参与但标记须【传递】；
    INVALID 不参与且告警；UNAVAILABLE 不参与、按缺失处理。
    四者都【不得】被任何填充值替代（G-3）。
    """

    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
```

`src/fip/strategy_library/factor/definitions.py`：

```python
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fip.strategy_library.factor.status import FactorStatus


class PreferenceDirection(StrEnum):
    """因子的偏好方向。

    ── 已知缺口（D-11 第 3 点，如实登记）──

    上游提到 Tracking Error 在 Active Equity 画像下方向为「中性」，而「中性」
    不属于这个枚举。M1 无 Benchmark、TE 恒 UNAVAILABLE，因此本 Plan
    【不实现】中性方向。补上它需要先定义「中性」在 Percentile Rank 下的
    语义（离目标值越近越好？那需要一个目标值，而上游没给），不是加一个
    枚举值就能了事的。
    """

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True, slots=True)
class FactorInput:
    """因子计算的全部输入。纯函数只吃它，不碰数据库（SDL-1）。

    adjusted_navs 与 nav_dates 是两个【并行】元组，按日期升序，已按 PIT 解析
    （available_at <= decision_at，G-1）。分成两个元组而不是一个 (date, value)
    序列，是为了让 quant_engine 直接吃 adjusted_navs 而不必先解包 —— 代价是
    错位风险，因此在构造期就断言等长。

    chain_quality 来自 NavSeries.chain_quality（Task 2）：它是整条累乘链路上
    全部行的 availability_quality 按 min-over-chain 聚合的结果，【不是】任何
    单行的 quality。**P2-21：它不再参与 status 判定**，而是原样传到
    `FactorResult.quality_flag`。

    risk_free_rate 与 mar_daily 都可以是 None，且两个 None 的含义不同：
      · risk_free_rate is None —— R_f 曲线在该 decision_at 解析不出来
      · mar_daily is None      —— mar_policy 未配置（G-6：必填无默认），
                                  或 RISK_FREE 模式下某一期的 R_f 缺失
    两者都会让依赖它的因子 UNAVAILABLE，【绝不】用 0 兜底。上游的理由是
    「Downside Volatility 与 Sortino 两者数值相同但含义相反 —— 设默认会让
    配置遗漏静默产出看起来正常的 Sortino」。

    **P2-22：`mar_daily` 是逐期序列，不是标量。** 与收益率序列 1:1 对齐
    （长度 = len(adjusted_navs) - 1）。三种 mar_policy（ZERO / CUSTOM /
    RISK_FREE）统一由 `threshold.mar.mar_daily_series()` 产出序列，
    **消费方不分支**。原契约的 `mar: Decimal | None` 装不下 RISK_FREE 模式的
    MAR 曲线，取均值/首值/末值都是在伪造一个从未被决策过的标尺 ——
    与 Plan-1 在 adjusted_nav 标量列上栽的是同一个跟头。
    """

    effective_at: dt.date
    adjusted_navs: tuple[Decimal, ...]
    nav_dates: tuple[dt.date, ...]
    chain_quality: str
    risk_free_rate: Decimal | None
    mar_daily: tuple[Decimal, ...] | None

    def __post_init__(self) -> None:
        if len(self.adjusted_navs) != len(self.nav_dates):
            raise ValueError(
                f"adjusted_navs（{len(self.adjusted_navs)} 条）与 nav_dates"
                f"（{len(self.nav_dates)} 条）长度不等，两个并行元组一旦错位，"
                "每个因子都会静默算错"
            )
        # P2-22：mar_daily 与【收益率】序列对齐，收益率比净值少一期。
        # 长度差一是最容易发生也最难发现的错位：Sortino 会照常算出一个数。
        expected = max(len(self.adjusted_navs) - 1, 0)
        if self.mar_daily is not None and len(self.mar_daily) != expected:
            raise ValueError(
                f"mar_daily（{len(self.mar_daily)} 期）必须与收益率序列"
                f"（{expected} 期）1:1 对齐"
            )


@dataclass(frozen=True, slots=True)
class FactorResult:
    """一个因子在一个时点的产出。

    value 与 status 的组合被构造期不变式锁死：
      · status 非 VALID ⇒ value 必须为 None。填 0 是 G-3 明令禁止的
        —— 0 波动率在任何排序里都是「零风险」，0 收益率是「持平」，
        两者都会被下游当成真实观测参与横截面统计。
      · status 为 VALID ⇒ value 必须有值。VALID 而无值说明产出方漏了分支。
      · status 非 VALID ⇒ reason 必填。只说「没有值」而不说「为什么」，
        会让 UNAVAILABLE（按缺失处理）与 INVALID（要告警）无法区分。

    quality_flag（P2-21【新增字段】）：输入链路的 availability_quality，
    取值即 `EXACT` / `DERIVED` / `INFERRED`，直接来自 `FactorInput.chain_quality`。

    **它与 status 是两个正交维度**，不得合并：status 说的是「这个数算不算得
    出来」，quality_flag 说的是「算它用的数据是怎么来的」。D-10 原本把
    「链路含 INFERRED」塞进 WARNING，而 AKShare 链路 100% 是 INFERRED（G-15）
    —— 结果是 VALID 在 M1 完全不可达、下游把一切都当异常。拆开之后
    M1 的常态是 `status=VALID, quality_flag=INFERRED`，两件事都说清楚了。

    quality_flag 【随结果传递】：Task 12 的标准化、Task 14 的归因都要带着它，
    Task 7 的 `factor_value` 有对应列。它不影响任何参与/不参与的判定。
    """

    factor_id: str
    value: Decimal | None
    status: FactorStatus
    reason: str
    observation_count: int
    quality_flag: str            # EXACT / DERIVED / INFERRED（P2-21）

    def __post_init__(self) -> None:
        if self.status is FactorStatus.VALID:
            if self.value is None:
                raise ValueError(
                    f"{self.factor_id}: status=VALID 却没有 value"
                )
        elif self.status is FactorStatus.WARNING:
            if self.value is None:
                raise ValueError(
                    f"{self.factor_id}: status=WARNING 仍然参与评分，必须有 value"
                )
            if not self.reason:
                raise ValueError(
                    f"{self.factor_id}: status=WARNING 时 reason 必填"
                )
        else:
            if self.value is not None:
                raise ValueError(
                    f"{self.factor_id}: status={self.status} 时 value 必须为 None，"
                    f"实得 {self.value!r} —— 不得填 0、上期值、inf 或组内均值（G-3）"
                )
            if not self.reason:
                raise ValueError(
                    f"{self.factor_id}: status={self.status} 时 reason 必填，"
                    "否则下游无法区分『按缺失处理』与『要告警』"
                )
```

`src/fip/strategy_library/factor/__init__.py`：

```python
"""因子域的策略逻辑。Task 9 在此补 compute.py，Task 12 补 normalize.py，
Task 13 补 effectiveness.py。本模块只做身份与契约类型。
"""

from fip.strategy_library.factor.definitions import (
    FactorInput,
    FactorResult,
    PreferenceDirection,
)
from fip.strategy_library.factor.status import FactorStatus

__all__ = [
    "FactorInput",
    "FactorResult",
    "FactorStatus",
    "PreferenceDirection",
]
```

其余四个子包各建一个说明性的空 `__init__.py`（内容为一行 docstring，
指明由哪个任务填充），例如
`src/fip/strategy_library/peer_group/__init__.py`：

```python
"""Peer Group 构建。Task 5 放分类编码约定，Task 11 放 build.py。

C-4 / G-5：本包【不得】import 评分 / 排名 / Universe 模块，否则形成
Score → Universe → Peer Group → Score 的循环依赖 —— 该循环不报错，
只让每次重算得到不同分数，直接破坏 NFR-REPRO-001。
"""
```

`src/fip/platform/versioning.py`：

```python
"""Code Version 的计算（SDL-3）。

Code Version 随决策快照落库（DEC-3），是复现该次决策的入口之一。因此它
必须覆盖【所有会改变计算结果的代码】：策略库与数值层。两者任一改动而
版本号不变，等于让两次跑出不同结果的决策带着同一个版本号落库。

本模块只读文件、不 import 被度量的包 —— 度量者不该被度量对象的 import
副作用影响，也不必承担 platform 层反向依赖 L1 层的问题。
"""

import hashlib
import pathlib
from collections.abc import Iterable

_FIP = pathlib.Path(__file__).resolve().parent.parent

# SDL-3：strategy_library 的版本参与 Code Version 计算。quant_engine 同理 ——
# 一个纯数值函数改了舍入方式，因子值就会变，而它同样不在任何 Strategy /
# Policy 版本里。
CODE_VERSION_ROOTS: tuple[pathlib.Path, ...] = (
    _FIP / "quant_engine",
    _FIP / "strategy_library",   # P2-1：真实路径直接挂在 fip 下，无中间层
)


def compute_code_version(roots: Iterable[pathlib.Path] | None = None) -> str:
    """对给定包根下全部 .py 文件的【路径 + 内容】做 SHA-256。

    路径也进哈希：两个内容相同、文件名不同的模块是不同的代码。

    只哈希 .py：__pycache__ 与编辑器临时文件不得让版本号无故变化 ——
    一个每次运行都变的版本号与没有版本号等价。

    根不存在时【抛错】而不是跳过：跳过会让版本号在缺半个库时照常产出，
    这正是「静默失效」最典型的形状。
    """
    digest = hashlib.sha256()
    for root in (CODE_VERSION_ROOTS if roots is None else tuple(roots)):
        if not root.is_dir():
            raise FileNotFoundError(
                f"Code Version 根目录不存在：{root}。"
                "缺失的根【不得】被跳过 —— 那会让版本号在代码缺失时照常产出"
            )
        for path in sorted(root.rglob("*.py")):
            digest.update(f"{root.name}/{path.relative_to(root)}".encode())
            digest.update(b"\x00")
            digest.update(path.read_bytes())
            digest.update(b"\x00")
    return digest.hexdigest()
```

`src/fip/platform/cli.py` 的 `cmd_pit_nav`（第 169-181 行）——
把占位的 `code_version="cli"` 换成实算，让 SDL-3 在生产装配路径上非空洞：

```python
from fip.platform.versioning import compute_code_version
```

```python
        code_version=compute_code_version(),
```

- [ ] **Step 4: 收紧 SDL-1 并补 SDL-3 适应度测试**

`tests/fitness/test_architecture.py` —— **D-27 修正**：SDL-1 的断言是
「`strategy_library` 不得 import `sqlalchemy` / `psycopg` **以及 `fip.services.*`
（含 repositories）**」。现有实现 `test_strategy_library_has_no_io_dependency`
只查 `IO_LIBS`（顶层包名，第 126-134 行），**`fip.services.*` 前缀这一半根本没实现**。
本步骤把缺的那一半补上——禁的是整个 `fip.services`，不是只禁 `*.repositories`
（禁子集会让 `from fip.services.fund_service.scoring import ...` 合法通过）：

```python
SDL_BANNED_PREFIXES = (
    "fip.services",     # D-27：整个 services 层，repositories 只是其中一部分
)


def test_strategy_library_does_not_import_any_service():
    """SDL-1 的第二半（D-27）：不含数据访问【实现】，也不 import services 层。

    只查 sqlalchemy 是不够的：一个 repository 模块可以自己 import sqlalchemy
    而策略库只 import 那个 repository —— 库清单扫描对这种两跳完全失明，
    而它恰恰是「策略库偷偷开始自己取数」最自然的第一步。

    禁整个 `fip.services` 而不是只禁 `fip.services.*.repositories`：
    策略库依赖任何 service（哪怕是它的 dataclass）都已经把依赖方向倒过来了，
    而窄禁令会让下一个人从 `from fip.services.fund_service.scoring import ...`
    开始，一路合法。
    """
    offenders = []
    for f in _py_files("strategy_library"):
        bad = [
            m for m in _dotted_imports(f)
            if any(_touches(m, prefix) for prefix in SDL_BANNED_PREFIXES)
        ]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"strategy_library import 了 services 层：{offenders}"


def test_strategy_library_participates_in_code_version():
    """SDL-3：该包的版本参与 Code Version 计算。

    这条放在 fitness 而不只是 unit：它约束的是【架构事实】——
    哪些目录被认为「会改变计算结果」。
    """
    from fip.platform.versioning import CODE_VERSION_ROOTS

    roots = {root.name for root in CODE_VERSION_ROOTS}
    assert "strategy_library" in roots
    assert "quant_engine" in roots
```

制造红灯以证伪（G-18）：

```bash
cat > src/fip/strategy_library/factor/_probe.py <<'PY'
from fip.services.data_service.repositories.nav import SqlNavPitRepository  # noqa: F401

RUNTIME_MODE_PROBE = "BACKTEST"
PY
.venv/bin/pytest tests/fitness/test_architecture.py -k strategy_library -v
```

Expected: 三条 FAIL ——
`test_strategy_library_has_no_io_dependency` 不会红（`_probe.py` 自身没 import
sqlalchemy，这正是上面 docstring 说的「两跳失明」），而
`test_strategy_library_does_not_import_any_service` 红：
`AssertionError: strategy_library import 了 services 层：[(PosixPath('strategy_library/factor/_probe.py'),
['fip.services.data_service.repositories.nav', ...])]`；
`test_strategy_library_has_no_runtime_mode_branch` 红：
`AssertionError: strategy_library 出现运行模式分支：[(PosixPath('strategy_library/factor/_probe.py'), ['BACKTEST'])]`。
把输出写进报告，然后：

Run: `rm src/fip/strategy_library/factor/_probe.py`

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_factor_contract.py tests/unit/test_code_version.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 22 条全绿（契约 10 条 + Code Version 10 条 + SDL 2 条）。

- [ ] **Step 6: 提交**

```bash
git add src/fip/strategy_library src/fip/platform/versioning.py \
        tests/unit/test_factor_contract.py tests/unit/test_code_version.py
git commit --only \
  src/fip/strategy_library \
  src/fip/platform/versioning.py \
  src/fip/platform/cli.py \
  tests/unit/test_factor_contract.py \
  tests/unit/test_code_version.py \
  tests/fitness/test_architecture.py \
  -m "feat(strategy-library): 骨架 + 契约类型，并补齐 SDL-1/2/3 适应度测试

骨架按实现计划的 File Structure 建出 factor / peer_group / score / ranking /
universe 五个子包，本任务只落契约类型：FactorStatus（D-10 的生产方触发条件
写进 docstring）、PreferenceDirection（『中性』方向作为已知缺口如实登记）、
FactorInput、FactorResult。

FactorResult 用 __post_init__ 把 G-3 锁进类型层：status 非 VALID 时 value
必须为 None 且 reason 必填 —— 填 0 会让『零波动率 = 零风险』这种结论静默
流进横截面统计。FactorInput 断言两个并行元组等长。

SDL-1 补第二半（D-27）：除 sqlalchemy/psycopg 之外，显式禁 import 整个
fip.services.*（含 repositories）。现有实现只查 IO_LIBS 顶层包名，
这一半此前根本不存在；库清单扫描对『策略库 → repository → sqlalchemy』
这条两跳路径失明。
SDL-3 首次有落点：新增 platform/versioning.py，把 quant_engine 与
strategy_library 纳入 Code Version；cli 的 code_version 由占位串 'cli'
改为实算，让这条约束在生产装配路径上非空洞。

证伪记录：临时放入 _probe.py（import repository + 字面量 'BACKTEST'），
SDL-1 第二条与 SDL-2 同时转红；SDL-1 的库清单那条【没有】红 —— 这正是
补第二条的理由。"
```

---

### Task 5: 基金分类灌入（D-5 / D-6）—— `基金类型` → `fund.fund_classification_history`

**Files:**
- Create: `src/fip/strategy_library/peer_group/classification.py`
- Modify: `src/fip/services/data_service/models/fund.py:179-195`
  （`FundClassificationHistory` 补「至多一条开放区间」的部分唯一索引）
- Create: `db/migrations/versions/0017_fund_classification_open_interval.py`
- Modify: `src/fip/services/data_service/ingest.py:53-68`（`FundListIngestResult` 加一个字段）
- Modify: `src/fip/services/data_service/ingest.py:235-323`（`ingest_fund_list` 不再丢弃 `基金类型`）
- Modify: `src/fip/platform/cli.py:124-142`（`cmd_ingest_funds` 报告分类冲突）
- Test: `tests/unit/test_classification_codes.py`（新建）
- Test: `tests/integration/test_fund_classification_ingest.py`（新建）

**Interfaces:**
- Consumes（Task 4 产出）：`fip.strategy_library.peer_group` 包已存在
- Produces（Task 11 消费，构造 `PeerGroupKey`）：
  - `fip.strategy_library.peer_group.classification.CLASSIFICATION_SCHEME: str = "AKSHARE_FUND_TYPE"`
  - `fip.strategy_library.peer_group.classification.UNCLASSIFIED_CODE: str = "UNCLASSIFIED"`
  - `normalize_classification_code(raw: str | None) -> str`
  - `level_1(code: str) -> str` —— `code.split("-")[0]`，**不落库、不另存列**
  - `is_groupable(code: str) -> bool` —— `UNCLASSIFIED` 恒 `False`（D-6）
  - `fip.services.data_service.ingest.ClassificationConflict`（frozen dataclass：
    `product_name: str`、`codes: tuple[str, ...]`，含 `describe() -> str`）
  - `FundListIngestResult.classification_conflicts: tuple[ClassificationConflict, ...]`
  - `fund.fund_classification_history` 里每个 `fund_id` 在 `AKSHARE_FUND_TYPE`
    scheme 下至多一条开放区间（数据库不变式 `uq_fch_open_interval`）

---

- [ ] **Step 1: 写失败的测试（纯函数部分）**

新建 `tests/unit/test_classification_codes.py`：

```python
"""Fund Classification 的编码约定（D-5 / D-6，均为【补齐】）。

⚠️ 这是【补齐】不是【裁定】：AKShare 的 `基金类型` 是数据供应商的商业分类，
不是投研定义的资产类别体系。一旦有正式分类体系，应整体替换 scheme 值
而非改代码 —— 这正是把 scheme 做成一个字段而不是硬编码的理由。
"""

import pytest

from fip.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
    is_groupable,
    level_1,
    normalize_classification_code,
)


def test_scheme_is_the_provider_scoped_label():
    assert CLASSIFICATION_SCHEME == "AKSHARE_FUND_TYPE"


@pytest.mark.parametrize(
    "raw",
    ["混合型-偏股", "指数型-股票", "债券型-混合二级", "股票型", "FOF-稳健型"],
)
def test_code_is_the_full_original_string(raw):
    """存【完整原串】（L2），不切、不映射、不翻译。

    切成 L1 存库会把「指数型-股票」与「指数型-固收」压成同一个码，
    而它们在真实数据里是 5589 只与 676 只两个完全不同的群体。
    """
    assert normalize_classification_code(raw) == raw


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_maps_to_unclassified_and_is_never_dropped(raw):
    """D-6：实测全市场 99 只基金的 `基金类型` 为空串。

    如实落库（不丢弃、不猜测），但它不是一个类别，是「我们不知道它属于
    哪个类别」—— 这两件事的区别正是 Plan-1 在 grouping_status 上反复吃过
    亏的那一条。
    """
    assert normalize_classification_code(raw) == UNCLASSIFIED_CODE


def test_whitespace_is_stripped_but_inner_text_is_untouched():
    assert normalize_classification_code("  混合型-偏股 ") == "混合型-偏股"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("混合型-偏股", "混合型"),
        ("指数型-股票", "指数型"),
        ("债券型-混合二级", "债券型"),
        ("股票型", "股票型"),          # 无连字符：L1 == L2
        ("FOF-稳健型", "FOF"),
        ("指数型-海外股票", "指数型"),
    ],
)
def test_level_1_is_derived_never_stored(code, expected):
    """L1 由 code.split("-")[0] 派生（D-5）。

    派生规则属 Strategy Library，不属数据 —— 所以【不另存一列】。
    存第二列意味着两份真值，两者一旦分叉无法判定谁对（与 D-15 对
    investment_eligibility 存引用而非副本是同一条理由）。
    """
    assert level_1(code) == expected


def test_unclassified_has_itself_as_level_1():
    """UNCLASSIFIED 无连字符，L1 就是它自己 —— 但它仍然不可分组。"""
    assert level_1(UNCLASSIFIED_CODE) == UNCLASSIFIED_CODE


def test_unclassified_is_not_groupable():
    """D-6：UNCLASSIFIED【不得】构成任何 Peer Group。

    落在这一类的基金：Evaluation Status = NOT_ELIGIBLE，理由 UNCLASSIFIED，
    不进入任何横截面计算。什么情况下这条会红：有人为了「让样本量够 30」
    把 UNCLASSIFIED 当成一个类别 —— 那会让一组彼此毫无可比性的基金
    互相排名，且排名看起来完全正常。
    """
    assert is_groupable(UNCLASSIFIED_CODE) is False


@pytest.mark.parametrize("code", ["混合型-偏股", "股票型", "FOF-稳健型"])
def test_real_codes_are_groupable(code):
    assert is_groupable(code) is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_classification_codes.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named
'fip.strategy_library.peer_group.classification'`。

- [ ] **Step 3: 实现纯函数**

`src/fip/strategy_library/peer_group/classification.py`：

```python
"""Fund Classification 的编码约定（设计定案 D-5 / D-6，两条都是【补齐】）。

── 为什么这段代码住在 strategy_library 而不是 data_service ──

它是【派生规则】而不是数据：L1 怎么从 code 切出来、哪些 code 可以构成
Peer Group，都是策略决定。放在 data_service 会让 Task 11 的 Peer Group
构建反过来依赖数据层。依赖方向 services → L1（strategy_library / quant_engine）
是允许的，反向不是。

── PROVISIONAL 的边界 ──

AKShare 的 `基金类型` 是数据供应商的商业分类，不是投研定义的资产类别体系。
拿到正式分类体系后应整体替换 CLASSIFICATION_SCHEME 的取值并重灌一遍
`fund_classification_history`，而不是改这里的切分逻辑 —— scheme 之所以是
一个字段，就是为了让「换一套分类体系」是一次数据操作而不是一次代码改造。
"""

CLASSIFICATION_SCHEME = "AKSHARE_FUND_TYPE"

# 「我们不知道它属于哪个类别」，不是「它属于一个叫 UNCLASSIFIED 的类别」。
# 这两件事的区别决定了它不可分组（见 is_groupable）。
UNCLASSIFIED_CODE = "UNCLASSIFIED"

_LEVEL_SEPARATOR = "-"


def normalize_classification_code(raw: str | None) -> str:
    """把上游的 `基金类型` 原串归一为 classification_code。

    只做两件事：去首尾空白、把空值映射为 UNCLASSIFIED。【不切分、不翻译、
    不归并】—— 存的是完整原串（L2），层级由 level_1 在读侧派生。
    """
    if raw is None:
        return UNCLASSIFIED_CODE
    code = raw.strip()
    return code if code else UNCLASSIFIED_CODE


def level_1(code: str) -> str:
    """大类（连字符之前）。无连字符时 L1 == L2（如「股票型」）。

    实测全市场取值分布（27718 只）：
      L1: 混合型 指数型 债券型 股票型 货币型 FOF QDII Reits 商品 其他
      L2: 混合型-偏股 5693 · 指数型-股票 5589 · 债券型-长债 2797 …

    【不另存一列】：多存一份就是多一份真值，两者分叉后无法判定谁对。
    """
    return code.split(_LEVEL_SEPARATOR)[0]


def is_groupable(code: str) -> bool:
    """该 code 是否可以构成 Peer Group（D-6）。

    UNCLASSIFIED 恒 False。把它当成一个类别会让一组彼此毫无可比性的基金
    互相排名，且排名看起来完全正常 —— 这是本文件里唯一一条会造成
    「静默错误结论」的规则，因此它必须是一个函数而不是散落各处的 if。
    """
    return code != UNCLASSIFIED_CODE
```

- [ ] **Step 4: 写失败的集成测试（灌入与区间语义）**

新建 `tests/integration/test_fund_classification_ingest.py`：

```python
"""`基金类型` 的灌入（D-5 / D-6）。

Plan-1 的 ingest_fund_list 读了 `基金类型` 却把它丢弃 —— 与 Plan-1 Task 19
修掉的「code 被丢弃」是同一个模式：数据契约里声明了、取回来了、然后在
解析时静默蒸发。
"""

import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import text

from fip.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
)
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import Fund, FundClassificationHistory

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 9, 10, 18, 0, tzinfo=dt.UTC)


def _service(session, frame: pd.DataFrame, now=FIXED_NOW) -> IngestService:
    adapter = AkShareSourceAdapter(
        clock=lambda: now, caller=lambda *_a, **_k: frame
    )
    return IngestService(session, adapter, disclosure_lag_days=1)


def _rows(session, product_name: str) -> list[FundClassificationHistory]:
    fund = session.query(Fund).filter_by(product_name=product_name).one()
    return (
        session.query(FundClassificationHistory)
        .filter_by(fund_id=fund.id)
        .order_by(FundClassificationHistory.valid_from)
        .all()
    )


SIMPLE = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["混合型-偏股", "混合型-偏股"],
})


def test_classification_is_persisted_with_the_full_original_string(db_session):
    """存完整原串（L2），scheme 记为 AKSHARE_FUND_TYPE。"""
    _service(db_session, SIMPLE).ingest_fund_list()
    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 1
    assert rows[0].classification_scheme == CLASSIFICATION_SCHEME
    assert rows[0].classification_code == "混合型-偏股"


def test_no_level_1_column_exists_on_the_table(db_session):
    """L1 是派生量，【不落库】（D-5）。

    什么情况下它会红：有人为了查询方便加一列 classification_level_1 —— 那
    就有了两份真值，转型时改一列忘一列，Peer Group 会静默按旧大类分组。
    """
    columns = {c.name for c in FundClassificationHistory.__table__.columns}
    assert not {c for c in columns if "level" in c or "l1" in c}


def test_the_interval_is_open_and_starts_at_the_ingest_date(db_session):
    """valid_from 取落库当日：我们【就是】在这一刻才知道这条分类。

    不去伪造一个更早的生效日 —— 那会让区间表宣称平台在看到分类之前它就
    已生效（C-12，与 _ensure_provider_identity 同一条理由）。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    row = _rows(db_session, "测试蓝筹混合")[0]
    assert row.valid_from == FIXED_NOW.date()
    assert row.valid_to is None
    assert row.availability_quality == "INFERRED"   # G-15：AKShare 链路恒 INFERRED
    assert row.published_at is None
    assert row.provider_available_at is None


def test_reingesting_the_same_classification_is_idempotent(db_session):
    svc = _service(db_session, SIMPLE)
    svc.ingest_fund_list()
    svc.ingest_fund_list()
    assert len(_rows(db_session, "测试蓝筹混合")) == 1


EMPTY = pd.DataFrame({
    "基金代码": ["000003"],
    "基金简称": ["测试无类型混合A"],
    "基金类型": [""],
})


def test_empty_type_is_stored_as_unclassified_not_dropped(db_session):
    """D-6：实测 99 只基金的 `基金类型` 为空串。如实落库，不丢弃、不猜测。"""
    _service(db_session, EMPTY).ingest_fund_list()
    rows = _rows(db_session, "测试无类型混合")
    assert len(rows) == 1
    assert rows[0].classification_code == UNCLASSIFIED_CODE


# 实测数据里真实存在的两类「同一产品主干、份额类别间类型不一致」：
#   兴全盈禧多元配置三个月持有混合(FOF)  A=FOF-稳健型  C=FOF-均衡型
#   中信建投民享稳健养老目标一年持有混合发起式(FOF)  A=FOF-稳健型  Y=''
# 全市场 15350 个产品主干中有 4 个命中，不是理论情形。
PARTIAL_BLANK = pd.DataFrame({
    "基金代码": ["000004", "000005"],
    "基金简称": ["测试养老FOFA", "测试养老FOFY"],
    "基金类型": ["FOF-稳健型", ""],
})

TRUE_CONFLICT = pd.DataFrame({
    "基金代码": ["000006", "000007"],
    "基金简称": ["测试多元FOFA", "测试多元FOFC"],
    "基金类型": ["FOF-稳健型", "FOF-均衡型"],
})


def test_a_blank_sibling_does_not_downgrade_a_known_classification(db_session):
    """一个份额类别没给类型，不等于这只基金没有类型。

    分类挂在 fund 上而上游按份额类别给值，两者粒度不同。「至多一个非空
    取值」时取那个非空值 —— 把它降级成 UNCLASSIFIED 会把一只本可分组的
    基金踢出全部横截面计算，那是用「不知道」覆盖「知道」。
    """
    _service(db_session, PARTIAL_BLANK).ingest_fund_list()
    rows = _rows(db_session, "测试养老FOF")
    assert len(rows) == 1
    assert rows[0].classification_code == "FOF-稳健型"


def test_two_different_non_empty_types_are_reported_and_nothing_is_written(db_session):
    """两个及以上不同的非空取值 = 冲突：不写、不猜、如实上报。

    与 _ensure_provider_identity 遇到重指派时的处理是同一条原则：绝不静默
    挑一个。挑错的后果是整只基金被排进错误的 Peer Group，而排名看起来
    完全正常。
    """
    result = _service(db_session, TRUE_CONFLICT).ingest_fund_list()
    assert len(result.classification_conflicts) == 1
    conflict = result.classification_conflicts[0]
    assert conflict.product_name == "测试多元FOF"
    assert set(conflict.codes) == {"FOF-稳健型", "FOF-均衡型"}
    assert _rows(db_session, "测试多元FOF") == []


RETYPED = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["债券型-混合二级", "债券型-混合二级"],
})


def test_a_changed_classification_closes_the_old_interval_and_opens_a_new_one(db_session):
    """基金转型会改变分类，回测必须使用【当时的】分类 —— 这正是这张表
    是区间型的理由（D-5 依据 2）。

    什么情况下它会红：实现用 UPDATE 原地改 classification_code。那样
    2026-09-01 的回测会看到 2026-09-10 才发生的转型结果，且没有任何痕迹
    表明它曾经是混合型。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    _service(db_session, RETYPED, now=LATER).ingest_fund_list()

    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 2
    assert rows[0].classification_code == "混合型-偏股"
    assert rows[0].valid_from == FIXED_NOW.date()
    assert rows[0].valid_to == LATER.date()
    assert rows[1].classification_code == "债券型-混合二级"
    assert rows[1].valid_from == LATER.date()
    assert rows[1].valid_to is None


def test_a_same_day_correction_does_not_create_a_zero_length_interval(db_session):
    """同日改口不得产生 valid_from == valid_to 的空区间。

    ck_fund_classification_history_interval 要求 valid_from < valid_to，
    因此「关旧开新」在同一天会被数据库直接拒收。同日改口按【原地更正】
    处理：该行的 available_at 就是今天，没有任何更早的决策可能看见过它，
    因此不存在被改写的历史。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    _service(db_session, RETYPED).ingest_fund_list()   # 同一个 FIXED_NOW

    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 1
    assert rows[0].classification_code == "债券型-混合二级"
    assert rows[0].valid_to is None


_DUPLICATE_OPEN = text("""
    INSERT INTO fund.fund_classification_history
        (fund_id, classification_scheme, classification_code,
         valid_from, valid_to, available_at, availability_quality,
         published_at, provider_available_at, ingested_at)
    VALUES (:fund_id, :scheme, :code, :valid_from, NULL,
            :available_at, 'INFERRED', NULL, NULL, :available_at)
""")


def test_database_rejects_a_second_open_interval_for_the_same_fund(db_session):
    """数据库不变式：每个 (fund_id, scheme) 至多一条开放区间。

    应用层的 read-then-write 守卫不是数据库不变式：它拦不住并发，也拦不住
    任何绕开 IngestService 的写入路径。两条开放区间共存时，读侧的
    `ORDER BY valid_from DESC LIMIT 1` 会静默挑一条 —— 挑错就是把基金
    排进错误的 Peer Group（与 uq_pfi_open_interval 同一条理由）。
    """
    from sqlalchemy.exc import IntegrityError

    _service(db_session, SIMPLE).ingest_fund_list()
    fund = db_session.query(Fund).filter_by(product_name="测试蓝筹混合").one()
    with pytest.raises(IntegrityError):
        db_session.execute(_DUPLICATE_OPEN, {
            "fund_id": fund.id, "scheme": CLASSIFICATION_SCHEME,
            "code": "股票型", "valid_from": dt.date(2026, 9, 1),
            "available_at": LATER,
        })
        db_session.flush()
```

- [ ] **Step 5: 跑测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_fund_classification_ingest.py -v -m integration`

Expected: 11 条全部 FAIL。典型输出：
`test_classification_is_persisted_with_the_full_original_string ...
sqlalchemy.exc.NoResultFound: No row was found when one was required`
（`fund_classification_history` 里一行都没有 —— `基金类型` 被丢弃）；
`test_database_rejects_a_second_open_interval_for_the_same_fund ...
Failed: DID NOT RAISE <class 'sqlalchemy.exc.IntegrityError'>`
（部分唯一索引尚不存在）。把输出写进报告。

- [ ] **Step 6: 实现（ORM + 迁移 + 灌数）**

`src/fip/services/data_service/models/fund.py` 的 `FundClassificationHistory`
（第 179-195 行）加索引，并补写为什么：

```python
class FundClassificationHistory(Base, IntervalMixin):
    """基金分类的历史 —— 【区间型表】。

    基金转型会改变分类，回测必须使用【当时的】分类，因此不能是一张
    「当前分类」的维度列。scheme 限定的编码（而非固定层级的列）正适合
    层级尚未由投研定案的分类体系：换一套体系是一次数据操作，不是一次
    代码改造（设计定案 D-5）。
    """

    __tablename__ = "fund_classification_history"
    __table_args__ = (
        *interval_temporal_check_constraints("fund_classification_history"),
        interval_check("fund_classification_history"),
        # 部分唯一索引，须与迁移 0017 里的 CREATE UNIQUE INDEX 逐字一致
        # （含 WHERE 子句），否则 autogenerate 会把它当成待删除对象（G-16）。
        # 唯一性键取 (fund_id, classification_scheme) 而不是只取 fund_id：
        # 同一只基金在两套分类体系下各有一条开放区间是合法的（这正是把
        # scheme 做成字段的意义），只有【同一套体系内】才至多一条。
        Index(
            "uq_fch_open_interval",
            "fund_id",
            "classification_scheme",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund.id", ondelete="RESTRICT"), nullable=False
    )
    classification_scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_code: Mapped[str] = mapped_column(String(32), nullable=False)
```

新建 `db/migrations/versions/0017_fund_classification_open_interval.py`：

```python
"""fund_classification_history 补「至多一条开放区间」的部分唯一索引

Plan-2 Task 5。本表在 Plan-1 建出后【从未被写入过】（fip_dev 实测 0 行），
Plan-2 的分类灌入是它的第一个写入方 —— Plan-1 交接项四「趁表还空着就做」
指的正是这个时刻：加约束的迁移在空表上很便宜，有数据之后成本高一个量级。

唯一性键是 (fund_id, classification_scheme) 而不是只有 fund_id：同一只基金
在两套分类体系下各有一条开放区间是合法的。这一条【必须逐表判断】，不可
一刀切照抄 provider_fund_identity（交接项四原文）。

本迁移只加索引，不动任何列、不动任何数据（C-12）。

Revision ID: 0017
Revises: 0016
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_fch_open_interval "
        "ON fund.fund_classification_history (fund_id, classification_scheme) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_fch_open_interval")
```

> ⚠️ **编号占用（已在计划正文统一，勿再顺延）**：Plan-2 的迁移链是
> `0016`（Task 1，交接项四的三处约束）→ `0017`（本任务）→ `0018`（Task 7，
> `factor` schema）→ `0019`（Task 8，`evaluation` schema）→ `0020`（Task 11,
> `fund_share_class.base_currency`）。本任务的 `down_revision` 是 **`0016`**，
> 不是 Plan-1 的 head `0015`——Task 1 先落地。

`src/fip/services/data_service/ingest.py` —— 新增冲突记录类型并扩展结果：

```python
@dataclass(frozen=True)
class ClassificationConflict:
    """同一产品主干下，各份额类别给出了两个及以上【不同的非空】基金类型。

    分类挂在 fund 上，而上游按份额类别给值 —— 两者粒度不同，实测全市场
    15350 个产品主干中有 4 个命中（如「兴全盈禧多元配置三个月持有混合(FOF)」
    A=FOF-稳健型、C=FOF-均衡型）。不是理论情形。

    与 IdentityReassignment 同一条原则：绝不静默挑一个。挑错的后果是整只
    基金被排进错误的 Peer Group，而排名看起来完全正常。
    """

    product_name: str
    codes: tuple[str, ...]

    def describe(self) -> str:
        return f"产品「{self.product_name}」的份额类别给出了不同的基金类型：{list(self.codes)}"


@dataclass(frozen=True)
class FundListIngestResult:
    created: int
    reassignments: tuple[IdentityReassignment, ...]
    classification_conflicts: tuple[ClassificationConflict, ...] = ()
```

`ingest_fund_list` 的循环体内累积、循环后统一写入：

```python
        provider = self._provider()
        created = 0
        reassignments: list[IdentityReassignment] = []
        # fund_id -> 该产品全部份额类别给出的【归一后】code 集合。
        # 必须在循环【之后】才写分类：分类挂在 fund 上而上游按份额类别给值，
        # 边循环边写会让「最后一条份额类别」静默决定整只基金的分类。
        observed: dict[int, set[str]] = {}
        names: dict[int, str] = {}
        for _, row in frame.iterrows():
            code = str(row["基金代码"]).strip()
            display_name = str(row["基金简称"]).strip()
            grouping = split_share_class_name(display_name)
            ...                     # Fund / FundShareClass 的既有逻辑不动
            observed.setdefault(fund.id, set()).add(
                normalize_classification_code(row.get("基金类型"))
            )
            names[fund.id] = grouping.product_name
            ...                     # _ensure_provider_identity 的既有逻辑不动

        conflicts = self._write_classifications(observed, names, record.ingested_at)
        return FundListIngestResult(
            created=created,
            reassignments=tuple(reassignments),
            classification_conflicts=tuple(conflicts),
        )
```

```python
    def _write_classifications(
        self,
        observed: dict[int, set[str]],
        names: dict[int, str],
        ingested_at: dt.datetime,
    ) -> list[ClassificationConflict]:
        """把本批观测到的基金类型落到 fund.fund_classification_history。

        ── 归并规则（D-6 的落地）──

        · 恰好一个非空取值 → 用它。一个份额类别没给类型，不等于这只基金
          没有类型；把它降级成 UNCLASSIFIED 是用「不知道」覆盖「知道」，
          会把一只本可分组的基金踢出全部横截面计算。
        · 全部为空       → UNCLASSIFIED。如实落库，不丢弃、不猜测。
        · 两个及以上不同的非空取值 → 冲突：【不写】，如实上报，由人裁定。

        ── 区间维护 ──

        · 无开放区间           → 新开一条，valid_from = 落库当日。
        · 开放区间的 code 未变 → 什么都不做（幂等）。
        · 开放区间的 code 变了：
            - 该区间的 valid_from < 今天 → 关旧（valid_to = 今天）、开新。
              基金转型会改变分类，回测必须使用当时的分类；原地 UPDATE 会让
              转型前的历史凭空消失。
            - 该区间的 valid_from == 今天 → 【原地更正】。关旧开新会产生
              valid_from == valid_to 的空区间，被 ck_*_interval 直接拒收；
              而这一行的 available_at 就是今天，没有任何更早的决策可能看见过
              它，因此不存在被改写的历史。
        """
        conflicts: list[ClassificationConflict] = []
        today = ingested_at.astimezone(dt.UTC).date()
        available_at, quality = resolve_availability(None, None, ingested_at)
        for fund_id, codes in observed.items():
            concrete = sorted(c for c in codes if c != UNCLASSIFIED_CODE)
            if len(concrete) > 1:
                conflicts.append(ClassificationConflict(
                    product_name=names[fund_id], codes=tuple(concrete)
                ))
                continue
            code = concrete[0] if concrete else UNCLASSIFIED_CODE

            existing = self._session.execute(
                select(FundClassificationHistory).where(
                    FundClassificationHistory.fund_id == fund_id,
                    FundClassificationHistory.classification_scheme
                    == CLASSIFICATION_SCHEME,
                    FundClassificationHistory.valid_to.is_(None),
                )
            ).scalars().first()

            if existing is not None:
                if existing.classification_code == code:
                    continue
                if existing.valid_from >= today:
                    existing.classification_code = code
                    existing.available_at = available_at
                    existing.ingested_at = ingested_at
                    self._session.flush()
                    continue
                existing.valid_to = today
                self._session.flush()

            self._session.add(FundClassificationHistory(
                fund_id=fund_id,
                classification_scheme=CLASSIFICATION_SCHEME,
                classification_code=code,
                valid_from=today,
                valid_to=None,
                available_at=available_at,
                availability_quality=quality.value,
                published_at=None,           # AKShare 给不出，如实留空（C-12）
                provider_available_at=None,  # 同上
                ingested_at=ingested_at,
            ))
            self._session.flush()
        return conflicts
```

顶部 import 追加：

```python
from fip.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
    normalize_classification_code,
)
from fip.services.data_service.models.fund import FundClassificationHistory
```

`src/fip/platform/cli.py` 的 `cmd_ingest_funds`（第 124-142 行）—— 冲突同样
以非零退出码响亮失败，与重指派并列：

```python
    problems: list[str] = []
    if result.reassignments:
        problems.append(
            f"检测到 {len(result.reassignments)} 处 provider 映射重指派，"
            "这些映射【未被改动】：\n"
            + "\n".join(f"  · {c.describe()}" for c in result.reassignments)
            + "\n请人工确认每一条历史的归属、关闭旧区间后再重跑。"
        )
    if result.classification_conflicts:
        problems.append(
            f"检测到 {len(result.classification_conflicts)} 处基金分类冲突，"
            "这些基金【未写入】任何分类，因而不会进入任何 Peer Group：\n"
            + "\n".join(
                f"  · {c.describe()}" for c in result.classification_conflicts
            )
            + "\n请人工裁定该产品的分类归属（不得由代码任选一个）。"
        )
    if problems:
        raise SystemExit("\n\n".join(problems))
```

- [ ] **Step 7: 跑测试确认通过**

Run: `.venv/bin/alembic -x db=test upgrade head`
Run: `.venv/bin/pytest tests/unit/test_classification_codes.py -v`
Run: `.venv/bin/pytest tests/integration/test_fund_classification_ingest.py -v -m integration`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

G-16 的闸门（autogenerate 必须报告零操作 —— 手工执行，CI 不跑）：

```bash
.venv/bin/python - <<'PY'
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
import db.migrations.env  # noqa: F401 —— 触发全部 model 模块的注册
from fip.platform.db.base import Base
from fip.settings import settings

engine = create_engine(settings.test_database_url, future=True)
with engine.connect() as conn:
    ctx = MigrationContext.configure(
        conn, opts={"include_object": db.migrations.env.include_object}
    )
    diff = compare_metadata(ctx, Base.metadata)
print("autogenerate 差异条数:", len(diff))
for d in diff:
    print(" ", d)
assert not diff, "ORM 声明与迁移产出不一致（G-16）"
PY
```

Expected: `autogenerate 差异条数: 0`。

G-17 的闸门（CHECK 黄金快照）：本任务只加索引、不改任何 CHECK，
`check_constraints.snapshot` 应当**不变**。

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot -v`
Expected: PASS，且 `git status` 显示 `check_constraints.snapshot` 未被修改。

- [ ] **Step 8: 提交**

```bash
git add src/fip/strategy_library/peer_group/classification.py \
        db/migrations/versions/0017_fund_classification_open_interval.py \
        tests/unit/test_classification_codes.py \
        tests/integration/test_fund_classification_ingest.py
git commit --only \
  src/fip/strategy_library/peer_group/classification.py \
  db/migrations/versions/0017_fund_classification_open_interval.py \
  src/fip/services/data_service/models/fund.py \
  src/fip/services/data_service/ingest.py \
  src/fip/platform/cli.py \
  tests/unit/test_classification_codes.py \
  tests/integration/test_fund_classification_ingest.py \
  -m "feat(classification): 灌入 AKShare 基金类型，解开 BLOCK-1

D-5 / D-6（均为【补齐】）：ingest_fund_list 此前读了 \`基金类型\` 却丢弃 ——
与 Task 19 修掉的『code 被丢弃』同一个模式。现写入 Plan-1 已建好的区间型表
fund.fund_classification_history，scheme = AKSHARE_FUND_TYPE，code 存完整原串
（L2）；L1 由 code.split('-')[0] 在 strategy_library 侧派生，【不另存列】。

空 \`基金类型\`（实测 99 只）映射为 UNCLASSIFIED，如实落库但 is_groupable()
恒 False —— 它不是一个类别，是『我们不知道它属于哪个类别』。

分类挂在 fund 上而上游按份额类别给值。实测 15350 个产品主干中有 4 个的份额
类别给出了不同类型。归并规则：恰好一个非空取值则取它（一个份额类别没给
类型不等于这只基金没有类型）；全空则 UNCLASSIFIED；两个及以上不同的非空
取值则【不写】并如实上报，由人裁定 —— 与遇到 provider 重指派时同一条原则。

迁移 0017 趁表还空着（fip_dev 实测 0 行）补上 uq_fch_open_interval：
(fund_id, classification_scheme) 至多一条开放区间。唯一性键带 scheme ——
同一只基金在两套体系下各有一条开放区间是合法的（交接项四要求逐表判断）。
⚠️ Plan-2 迁移链：0016(Task1) → 0017(本任务) → 0018(factor) → 0019(evaluation)
→ 0020(base_currency)。"
```

---

### Task 6: 批量灌数（D-2）—— ≥300 个份额类别，`AdjustedNavUnavailable` 保护下沉到 service

**Files:**
- Modify: `src/fip/services/data_service/ingest.py:424-425`
  （`rebuild_adjusted_nav` 之后新增单只与批量两个方法）
- Modify: `src/fip/platform/cli.py:145-166`（`cmd_ingest_nav` 改用 service 的单只方法）
- Modify: `src/fip/platform/cli.py:215-236`（新增 `ingest-nav-batch` 子命令）
- Test: `tests/integration/test_batch_ingest.py`（新建）
- Test: `tests/fitness/test_architecture.py`（新增一条：CLI 不得再自己捕获 `AdjustedNavUnavailable`）

**Interfaces:**
- Consumes（Task 5 产出）：`fund.provider_fund_identity` 已由 `ingest-funds` 登记
  ≥300 条开放区间；`FundListIngestResult.classification_conflicts`
- Produces（Task 9 / 11 / 13 的数据前提）：
  - `fip.services.data_service.ingest.ShareClassIngestStatus`（StrEnum：
    `INGESTED` / `ADJUSTED_NAV_UNAVAILABLE` / `FAILED` / `SKIPPED`）
  - `fip.services.data_service.ingest.ShareClassIngestOutcome`（frozen slots dataclass：
    `share_class_id: int`、`provider_fund_id: str`、`status: ShareClassIngestStatus`、
    `nav_rows: int`、`event_rows: int`、`rebuilt_rows: int`、`detail: str`）
  - `fip.services.data_service.ingest.BatchIngestReport`（frozen slots dataclass：
    `outcomes: tuple[ShareClassIngestOutcome, ...]`，方法
    `count(status: ShareClassIngestStatus) -> int`、
    `failures() -> tuple[ShareClassIngestOutcome, ...]`）
  - `IngestService.ingest_share_class(share_class_id: int, provider_fund_id: str,
    decision_at: dt.date) -> ShareClassIngestOutcome`
  - `IngestService.ingest_nav_batch(targets: Sequence[tuple[int, str]],
    decision_at: dt.date, skip_already_ingested: bool = False) -> BatchIngestReport`
  - `fip_dev` 中 `market.fund_nav` 覆盖 **≥ 300** 个不同的 `share_class_id`
    —— IC / ICIR 是横截面统计量，`MIN_PEER_GROUP_SIZE = 30` 在 3 只基金上
    根本达不到（D-2）

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/integration/test_batch_ingest.py`：

```python
"""批量灌数与 AdjustedNavUnavailable 的保护位置（D-2 / Plan-1 交接项三）。

交接项原文：「AdjustedNavUnavailable 只在 CLI 的单只调用点被捕获，
IngestService 自身无保护。Plan-1 没有批处理循环所以不构成缺陷，但 Plan-2
第一次写多只基金的批处理循环就会重新踩到：一只基金复权不可算会中断整个
循环。保护应下沉到 service 层。」
"""

import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import select

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import (
    IngestService,
    ShareClassIngestStatus,
)
from fip.services.data_service.models.fund import FundShareClass, ProviderFundIdentity
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
DECISION_AT = dt.date(2026, 8, 31)

FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000002", "000003"],
    "基金简称": ["测试甲混合A", "测试乙混合A", "测试丙混合A"],
    "基金类型": ["混合型-偏股", "混合型-偏股", "混合型-偏股"],
})

GOOD_NAV = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.0000", "1.1000"],
})

# 复权不可算：除息金额 >= 除息日净值 → shares 递推的分母非正。
BAD_NAV = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.0000", "0.5000"],
})
BAD_DIVIDEND = pd.DataFrame({
    "年份": ["2020"], "权益登记日": ["2020-01-02"],
    "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金9.0000元"],
})

EMPTY_DIVIDEND = pd.DataFrame({
    "年份": [], "权益登记日": [], "除息日": [], "每10份分红": [],
})
EMPTY_SPLIT = pd.DataFrame({"年份": [], "拆分折算日": [], "拆分折算比例": []})


def _caller_for(bad_symbols: set[str], exploding_symbols: set[str] = frozenset()):
    def caller(name, **params):
        if name == "fund_name_em":
            return FUND_LIST
        symbol = params.get("symbol", "")
        if symbol in exploding_symbols:
            raise RuntimeError(f"上游炸了：{symbol}")
        indicator = params.get("indicator")
        bad = symbol in bad_symbols
        if indicator == "单位净值走势":
            return BAD_NAV if bad else GOOD_NAV
        if indicator == "分红送配详情":
            return BAD_DIVIDEND if bad else EMPTY_DIVIDEND
        if indicator == "拆分详情":
            return EMPTY_SPLIT
        raise AssertionError(f"未预期的调用 {name} {params}")
    return caller


def _service(session, caller) -> IngestService:
    return IngestService(
        session,
        AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=caller),
        disclosure_lag_days=1,
    )


@pytest.fixture()
def targets(db_session) -> list[tuple[int, str]]:
    _service(db_session, _caller_for(set())).ingest_fund_list()
    rows = db_session.execute(
        select(ProviderFundIdentity.share_class_id, ProviderFundIdentity.provider_fund_id)
        .where(ProviderFundIdentity.valid_to.is_(None))
        .order_by(ProviderFundIdentity.provider_fund_id)
    ).all()
    return [(r[0], r[1]) for r in rows]


def _nav_count(session, share_class_id: int) -> int:
    return (
        session.query(FundNav).filter_by(share_class_id=share_class_id).count()
    )


def test_one_unadjustable_fund_does_not_abort_the_batch(db_session, targets):
    """一只基金复权不可算，其余两只必须照常灌完。

    什么情况下它会红：保护留在 CLI 而 service 直接把
    AdjustedNavUnavailable 抛出循环 —— 那正是 Plan-1 结束时的状态。
    """
    service = _service(db_session, _caller_for({"000002"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert len(report.outcomes) == 3
    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    assert report.count(ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE) == 1


def test_navs_of_the_unadjustable_fund_are_kept_not_discarded(db_session, targets):
    """净值与事件已成功灌入，不得因复权回填失败而把它们一并丢弃。

    复权是【读路径现算】的，物化列只是运维值；净值行本身完全有效。
    丢弃它们等于让一次回填失败抹掉真实的市场数据。
    """
    service = _service(db_session, _caller_for({"000002"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    bad = next(
        o for o in report.outcomes
        if o.status is ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE
    )
    assert bad.nav_rows == 2
    assert bad.rebuilt_rows == 0
    assert _nav_count(db_session, bad.share_class_id) == 2


def test_an_upstream_exception_is_isolated_to_one_share_class(db_session, targets):
    """网络/上游异常同样不得中断整批 —— 但必须逐只如实上报，不得吞掉。"""
    service = _service(db_session, _caller_for(set(), exploding_symbols={"000003"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    failures = report.failures()
    assert len(failures) == 1
    assert failures[0].provider_fund_id == "000003"
    assert "上游炸了" in failures[0].detail


def test_the_session_is_usable_after_a_failure(db_session, targets):
    """失败后必须 rollback，否则后续每一只都会撞上
    PendingRollbackError —— 「一只失败不中断整批」会退化成
    「第一只失败之后全部失败」，而报告里看起来是 N-1 个独立故障。
    """
    service = _service(db_session, _caller_for(set(), exploding_symbols={"000001"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert report.count(ShareClassIngestStatus.FAILED) == 1
    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    survivors = [
        o for o in report.outcomes if o.status is ShareClassIngestStatus.INGESTED
    ]
    for outcome in survivors:
        assert _nav_count(db_session, outcome.share_class_id) == 2


def test_every_target_gets_exactly_one_outcome_row(db_session, targets):
    """报告必须逐只 —— 只给「成功 N 只 / 失败 M 只」的汇总，
    运维就无法知道该重跑哪几只。
    """
    service = _service(db_session, _caller_for({"000002"}, {"000003"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    reported = {(o.share_class_id, o.provider_fund_id) for o in report.outcomes}
    assert reported == set(targets)
    assert {o.status for o in report.outcomes} == {
        ShareClassIngestStatus.INGESTED,
        ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE,
        ShareClassIngestStatus.FAILED,
    }


def test_resume_skips_share_classes_that_already_have_navs(db_session, targets):
    """断点续灌：已有净值的份额类别直接跳过，不再打一次上游。

    判据取【数据库里的真实状态】而不是一个游标文件：进度文件与数据库
    分叉时无法判定谁对，而『这只已经有净值行了』是可以直接观测的事实。
    """
    service = _service(db_session, _caller_for(set()))
    first = service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    assert first.count(ShareClassIngestStatus.INGESTED) == 1

    second = service.ingest_nav_batch(
        targets, decision_at=DECISION_AT, skip_already_ingested=True
    )
    assert second.count(ShareClassIngestStatus.SKIPPED) == 1
    assert second.count(ShareClassIngestStatus.INGESTED) == 2
    skipped = next(
        o for o in second.outcomes if o.status is ShareClassIngestStatus.SKIPPED
    )
    assert skipped.share_class_id == targets[0][0]


def test_resume_is_off_by_default(db_session, targets):
    """默认【不跳过】：日常增量灌数要的是重跑同一只以取回新净值。

    把续灌做成默认行为会让「每天跑一次」变成「只灌第一天」，且没有任何
    错误信号。
    """
    service = _service(db_session, _caller_for(set()))
    service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    again = service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    assert again.count(ShareClassIngestStatus.SKIPPED) == 0
    assert again.count(ShareClassIngestStatus.INGESTED) == 1


def test_single_share_class_entry_point_never_raises_adjusted_nav_unavailable(
    db_session, targets
):
    """保护【在 service 层】：单只入口自己就不会把该异常抛出去。

    什么情况下它会红：有人把 try/except 又搬回 CLI —— 那样任何绕过 CLI 的
    调用方（批处理、未来的 job worker）都会重新踩到同一个坑。
    """
    service = _service(db_session, _caller_for({"000002"}))
    share_class_id, symbol = next(t for t in targets if t[1] == "000002")
    outcome = service.ingest_share_class(share_class_id, symbol, DECISION_AT)
    assert outcome.status is ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE
    assert outcome.detail


EMPTY_NAV = pd.DataFrame({"净值日期": [], "单位净值": []})


def _empty_caller(name, **params):
    """上游对该基金一行净值都没有：列结构合法、行数为 0。

    刻意给出【有列名的空表】而不是 pd.DataFrame()：后者是 AKShare 对
    「无此类记录」的另一种表达（0 行 0 列），会被 _assert_columns 原样放行，
    但 parse_nav_frame 拿到它时行为不确定。这条测试要验的是「合法但空」，
    不是「无 schema」。
    """
    if name == "fund_name_em":
        return FUND_LIST
    indicator = params.get("indicator")
    if indicator == "单位净值走势":
        return EMPTY_NAV
    if indicator == "分红送配详情":
        return EMPTY_DIVIDEND
    if indicator == "拆分详情":
        return EMPTY_SPLIT
    raise AssertionError(f"未预期的调用 {name} {params}")


def test_zero_nav_rows_is_reported_as_zero_not_hidden(db_session):
    """上游一行净值都没有时，报告里必须看得出是 0 行。

    状态仍是 INGESTED（这一只确实跑完了、没有出错），但 nav_rows == 0 与
    「灌了 2 行」必须可区分 —— 只看状态的话运维会以为覆盖已经完成，而
    这只基金在后续的横截面计算里会一直缺席且没有任何线索。
    """
    service = _service(db_session, _empty_caller)
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).order_by(FundShareClass.id).first()
    outcome = service.ingest_share_class(sc.id, "000001", DECISION_AT)
    assert outcome.nav_rows == 0
    assert outcome.rebuilt_rows == 0
    assert outcome.status is ShareClassIngestStatus.INGESTED
    assert "0 行" in outcome.detail
```

同时在 `tests/fitness/test_architecture.py` 末尾追加一条，防止保护被搬回 CLI：

```python
CLI_PY = SRC / "platform" / "cli.py"


def test_cli_does_not_own_the_adjusted_nav_unavailable_guard():
    """D-2 / 交接项三：保护必须在 service 层，不得在 CLI 再包一层。

    CLI 只是众多调用方之一。把 try/except AdjustedNavUnavailable 放在这里，
    等于让每一个未来的调用方（批处理循环、job worker、API handler）各自
    重新发现同一个坑 —— Plan-1 交接项明确警告『第一次写批处理循环就会
    重新踩到』。

    什么情况下它会红：有人在 cli.py 里写下 `except AdjustedNavUnavailable`。
    """
    tree = ast.parse(CLI_PY.read_text(encoding="utf-8"), filename=str(CLI_PY))
    caught = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            for sub in ast.walk(node.type):
                if isinstance(sub, ast.Name):
                    caught.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    caught.add(sub.attr)
    assert "AdjustedNavUnavailable" not in caught, (
        "cli.py 又开始自己捕获 AdjustedNavUnavailable；该保护属 IngestService"
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_batch_ingest.py -v -m integration`
Expected: 全部 FAIL —— `ImportError: cannot import name 'ShareClassIngestStatus'
from 'fip.services.data_service.ingest'`。

Run: `.venv/bin/pytest tests/fitness/test_architecture.py -k adjusted_nav_unavailable -v`
Expected: FAIL with
`AssertionError: cli.py 又开始自己捕获 AdjustedNavUnavailable；该保护属 IngestService`
—— 这正是 Plan-1 结束时的状态（`cli.py:156` 与 `cli.py:195` 各一处）。

- [ ] **Step 3: 最小实现**

`src/fip/services/data_service/ingest.py` —— 顶部 import 补
`from enum import StrEnum` 与
`from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable`，
并新增：

```python
class ShareClassIngestStatus(StrEnum):
    INGESTED = "INGESTED"
    ADJUSTED_NAV_UNAVAILABLE = "ADJUSTED_NAV_UNAVAILABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class ShareClassIngestOutcome:
    """一只份额类别的灌数结果。逐只如实记录，不做汇总。

    ADJUSTED_NAV_UNAVAILABLE 与 FAILED 【必须】是两个状态而不是一个：
    前者是「净值与事件都灌进去了，只是这只基金的复权链路算不出来」——
    数据是好的，物化列留 NULL，读路径照样能现算它可算的部分；
    后者是「这一只整个没灌成」。把两者合并会让运维分不清该重跑哪些。
    """

    share_class_id: int
    provider_fund_id: str
    status: ShareClassIngestStatus
    nav_rows: int
    event_rows: int
    rebuilt_rows: int
    detail: str


@dataclass(frozen=True, slots=True)
class BatchIngestReport:
    outcomes: tuple[ShareClassIngestOutcome, ...]

    def count(self, status: ShareClassIngestStatus) -> int:
        return sum(1 for o in self.outcomes if o.status is status)

    def failures(self) -> tuple[ShareClassIngestOutcome, ...]:
        return tuple(
            o for o in self.outcomes if o.status is ShareClassIngestStatus.FAILED
        )
```

`IngestService` 内新增两个方法（接在 `rebuild_adjusted_nav` 之后）：

```python
    def ingest_share_class(
        self, share_class_id: int, provider_fund_id: str, decision_at: dt.date
    ) -> ShareClassIngestOutcome:
        """灌一只份额类别的净值 + 事件 + 复权回填，返回如实的结果。

        ── AdjustedNavUnavailable 的保护在这里，不在 CLI（交接项三）──

        Plan-1 只在 cmd_ingest_nav 的单只调用点捕获它，IngestService 自身
        无保护。CLI 只是众多调用方之一：批处理循环、未来的 job worker、
        API handler 都会重新踩到同一个坑，而后果是「一只基金复权不可算
        中断整个循环」。保护属于这一层。

        捕获【只覆盖复权回填】，不覆盖净值与事件的灌入：后者失败是真正的
        失败，必须抛给调用方。复权回填失败则不同 —— 净值行本身完全有效，
        复权值由读路径按 decision_at 现算（物化列只是运维值），因此这里
        如实记录并继续，【不】回滚已灌入的净值（C-6 禁止的是填 0 / 沿用
        上期，不是禁止保留真实的市场数据）。
        """
        navs = self.ingest_nav(share_class_id, provider_fund_id)
        events = self.ingest_distributions(share_class_id, provider_fund_id)
        try:
            rebuilt = self.rebuild_adjusted_nav(share_class_id, decision_at)
        except AdjustedNavUnavailable as exc:
            return ShareClassIngestOutcome(
                share_class_id=share_class_id,
                provider_fund_id=provider_fund_id,
                status=ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE,
                nav_rows=navs,
                event_rows=events,
                rebuilt_rows=0,
                detail=(
                    f"净值 {navs} 行、事件 {events} 行已灌入；"
                    f"复权回填跳过：{exc}。该份额类别的 adjusted_nav 物化列"
                    "保持 NULL，读路径仍按 decision_at 现算"
                ),
            )
        return ShareClassIngestOutcome(
            share_class_id=share_class_id,
            provider_fund_id=provider_fund_id,
            status=ShareClassIngestStatus.INGESTED,
            nav_rows=navs,
            event_rows=events,
            rebuilt_rows=rebuilt,
            detail=f"净值 {navs} 行、事件 {events} 行、复权回填 {rebuilt} 行",
        )

    def _has_navs(self, share_class_id: int) -> bool:
        return self._session.execute(
            select(func.count()).select_from(FundNav).where(
                FundNav.share_class_id == share_class_id
            )
        ).scalar_one() > 0

    def ingest_nav_batch(
        self,
        targets: Sequence[tuple[int, str]],
        decision_at: dt.date,
        skip_already_ingested: bool = False,
    ) -> BatchIngestReport:
        """按 (share_class_id, provider_fund_id) 逐只灌数。

        ── 三条硬性质（D-2）──

        1. **一只失败不得中断整批**：捕获 Exception（不含 BaseException，
           因此 KeyboardInterrupt / SystemExit 照常穿出 —— 运维按 Ctrl-C
           必须真的能停下）。
        2. **逐只报告成败**：每个 target 恰好产出一条 outcome。只给汇总数字
           会让运维无法知道该重跑哪几只。
        3. **断点续灌**：skip_already_ingested=True 时跳过已有净值行的份额
           类别。判据取数据库里的真实状态而不是一个进度文件 —— 进度文件与
           数据库分叉时无法判定谁对。默认为 False，因为日常增量灌数要的
           恰恰是重跑同一只以取回新净值。

        ── 为什么在这一层 commit ──

        本方法【逐只提交】。这是本仓库第一处在 service 层提交的地方，是
        刻意的：断点续灌要求「已灌完的那些必须真的落库」，而单一大事务下
        第 287 只失败会让前 286 只一起回滚 —— 那样「断点」根本不存在。
        每只失败后必须 rollback，否则后续每一只都会撞上 PendingRollbackError，
        「一只失败不中断整批」会退化成「第一只失败之后全部失败」。
        """
        outcomes: list[ShareClassIngestOutcome] = []
        for share_class_id, provider_fund_id in targets:
            if skip_already_ingested and self._has_navs(share_class_id):
                outcomes.append(ShareClassIngestOutcome(
                    share_class_id=share_class_id,
                    provider_fund_id=provider_fund_id,
                    status=ShareClassIngestStatus.SKIPPED,
                    nav_rows=0, event_rows=0, rebuilt_rows=0,
                    detail="已有净值行，断点续灌跳过",
                ))
                continue
            try:
                outcome = self.ingest_share_class(
                    share_class_id, provider_fund_id, decision_at
                )
                self._session.commit()
            except Exception as exc:  # noqa: BLE001 —— 见方法 docstring 第 1 条
                self._session.rollback()
                outcome = ShareClassIngestOutcome(
                    share_class_id=share_class_id,
                    provider_fund_id=provider_fund_id,
                    status=ShareClassIngestStatus.FAILED,
                    nav_rows=0, event_rows=0, rebuilt_rows=0,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            outcomes.append(outcome)
        return BatchIngestReport(outcomes=tuple(outcomes))
```

顶部 import 追加 `from collections.abc import Sequence`。

`src/fip/platform/cli.py` —— `cmd_ingest_nav`（第 145-166 行）改为调用 service，
CLI 里不再出现任何 `except AdjustedNavUnavailable`：

```python
def cmd_ingest_nav(args: argparse.Namespace) -> None:
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        outcome = _service(session).ingest_share_class(
            share_class.id, args.symbol, dt.date.today()
        )
        session.commit()
    print(f"{share_class.display_name}：{outcome.status} —— {outcome.detail}")
```

新增批量子命令与它的 handler：

```python
def cmd_ingest_nav_batch(args: argparse.Namespace) -> None:
    """批量灌入净值。ingest_nav_batch 自己逐只提交，这里不再包事务。"""
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.ingest import ShareClassIngestStatus
    from fip.services.data_service.models.fund import ProviderFundIdentity
    from fip.services.data_service.models.governance import DataProvider
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter

    with _session() as session:
        rows = session.execute(
            select(
                ProviderFundIdentity.share_class_id,
                ProviderFundIdentity.provider_fund_id,
            )
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                DataProvider.provider_code == AkShareSourceAdapter.provider_code,
                ProviderFundIdentity.valid_to.is_(None),
            )
            .order_by(ProviderFundIdentity.provider_fund_id)
            .limit(args.limit)
        ).all()
        targets = [(r[0], r[1]) for r in rows]
        report = _service(session).ingest_nav_batch(
            targets, dt.date.today(), skip_already_ingested=args.resume
        )

    for outcome in report.outcomes:
        print(f"{outcome.provider_fund_id}\t{outcome.status}\t{outcome.detail}")
    print(
        f"共 {len(report.outcomes)} 只："
        f"成功 {report.count(ShareClassIngestStatus.INGESTED)}、"
        f"复权不可算 {report.count(ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE)}、"
        f"跳过 {report.count(ShareClassIngestStatus.SKIPPED)}、"
        f"失败 {report.count(ShareClassIngestStatus.FAILED)}"
    )
    if report.failures():
        # 响亮失败：已灌入的部分照常保留（逐只提交），但退出码非零，
        # 否则批处理脚本会以为整批都成功了。
        raise SystemExit(
            f"{len(report.failures())} 只失败，可加 --resume 重跑（已成功的会被跳过）"
        )
```

`main()` 里注册：

```python
    p_batch = sub.add_parser(
        "ingest-nav-batch", help="批量灌入净值与事件（逐只提交，可断点续灌）"
    )
    p_batch.add_argument("--limit", type=int, default=None)
    p_batch.add_argument(
        "--resume", action="store_true",
        help="跳过已有净值行的份额类别（断点续灌）；默认不跳过，用于日常增量",
    )
    p_batch.set_defaults(func=cmd_ingest_nav_batch)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/integration/test_batch_ingest.py -v -m integration`
Run: `.venv/bin/pytest tests/fitness/test_architecture.py -k adjusted_nav_unavailable -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 10 条全绿。注意 `tests/integration/test_cli.py` 里断言
`cmd_ingest_nav` 输出文本的用例需要同步改成新的一行格式 —— 那是本任务
【预期内】的改动，不得为了让旧断言通过而保留 CLI 里的 try/except。

- [ ] **Step 5: 真实灌数（D-2 的验收，对 `fip_dev` 执行）**

净值/分红/拆分三个数据集各要打一次上游，约 300 只 ≈ 900 次请求，
实测节奏下需要 30~60 分钟。必须放后台跑，不要在前台阻塞：

```bash
.venv/bin/fip ingest-funds --limit 400 2>&1 | tail -20
nohup .venv/bin/fip ingest-nav-batch --limit 400 --resume \
  > /tmp/fip-batch.log 2>&1 &
```

中途或结束后查看进度与逐只结果：

```bash
tail -5 /tmp/fip-batch.log
grep -c INGESTED /tmp/fip-batch.log
grep -E "FAILED|ADJUSTED_NAV_UNAVAILABLE" /tmp/fip-batch.log
```

中断后直接重跑同一条命令即可（`--resume` 跳过已灌完的）。

- [ ] **Step 6: 验收 ≥300 个份额类别（D-2 的硬指标）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings
e = create_engine(settings.database_url, future=True)
with e.connect() as c:
    covered = c.execute(text(
        "SELECT count(DISTINCT share_class_id) FROM market.fund_nav")).scalar()
    rows = c.execute(text("SELECT count(*) FROM market.fund_nav")).scalar()
    classified = c.execute(text("""
        SELECT count(*) FROM fund.fund_classification_history
        WHERE valid_to IS NULL AND classification_code <> 'UNCLASSIFIED'""")).scalar()
    groups = c.execute(text("""
        SELECT split_part(classification_code, '-', 1) AS l1, count(*)
        FROM fund.fund_classification_history
        WHERE valid_to IS NULL AND classification_code <> 'UNCLASSIFIED'
        GROUP BY 1 ORDER BY 2 DESC""")).all()
print("覆盖份额类别:", covered, " 净值行:", rows, " 已分类基金:", classified)
print("L1 分组规模:", groups)
assert covered >= 300, f"D-2 要求 >= 300 个份额类别，实得 {covered}"
PY
```

Expected: `覆盖份额类别: >= 300`。同时把 `L1 分组规模` 抄进任务报告 ——
D-7 把 Peer Group 粒度默认定为 L1 的理由正是「L1 分组约 30~100 只才能让
横截面派生量真正产出」，这里是**第一次可以用真实数据检验那条假设**。
若某个 L1 分组不足 `MIN_PEER_GROUP_SIZE = 30`，如实记录，**不要**为了凑数
而扩大 `--limit` 之外的任何东西（G-7 的判定基数是 `n_effective`，不是组规模，
组规模不足本身是一个需要被 Task 11 如实呈现的事实）。

- [ ] **Step 7: 提交**

```bash
git add tests/integration/test_batch_ingest.py
git commit --only \
  src/fip/services/data_service/ingest.py \
  src/fip/platform/cli.py \
  tests/integration/test_batch_ingest.py \
  tests/fitness/test_architecture.py \
  tests/integration/test_cli.py \
  -m "feat(ingest): 批量灌数 + AdjustedNavUnavailable 保护下沉到 service 层

D-2 与 Plan-1 交接项三。交接项原文警告『第一次写多只基金的批处理循环就会
重新踩到』—— 本任务正是那个循环，因此保护必须在这里下沉，而不是在 CLI
再包一层：CLI 只是众多调用方之一，批处理、job worker、API handler 都会
各自重新发现同一个坑。

新增 IngestService.ingest_share_class（单只，自带保护）与 ingest_nav_batch
（逐只提交、逐只报告、一只失败不中断整批）。三个状态刻意分开：
· ADJUSTED_NAV_UNAVAILABLE —— 净值与事件都灌好了，只是复权链路算不出来。
  净值行完全有效（复权由读路径现算），不得因回填失败而丢弃真实市场数据。
· FAILED —— 这一只整个没灌成，已 rollback。
· SKIPPED —— 断点续灌跳过；判据取数据库里的真实状态而不是进度文件。
每只失败后 rollback：否则后续每只都撞 PendingRollbackError，『一只失败不
中断整批』会退化成『第一只失败之后全部失败』。

新增适应度测试：cli.py 里不得再出现 except AdjustedNavUnavailable。
新增 CLI 子命令 ingest-nav-batch --limit/--resume。

实测灌入结果（fip_dev）：把 Step 6 脚本打印的『覆盖份额类别 / 净值行 /
L1 分组规模』三个数字原样抄进本段 —— D-7 把 Peer Group 粒度默认定为 L1
的假设，到这里第一次得到真实数据的检验，数字必须留在提交历史里。"
```

> 提交前先跑一遍 Step 6 的脚本，把它打印的三个数字填进上面这条提交信息的
> 最后一段。**不要**留任何占位符 —— 一条写着「覆盖若干只」的提交信息在
> 半年后与没有这段话等价。


---

### Task 7: `factor` schema 五张表 + 迁移 0018

**Files:**

- Create: `src/fip/platform/db/enums.py`
- Create: `src/fip/services/factor_service/models/__init__.py`
- Create: `src/fip/services/factor_service/models/factor.py`
- Create: `db/migrations/versions/0018_factor_schema.py`
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
factor_status_reason_enum: postgresql.ENUM  # 八类 + MAR_SERIES_INCOMPLETE（补）
                                                 # + NEAR_MIN_OBS（PF-8：WARNING 的理由）
factor_run_status_enum: postgresql.ENUM          # RUNNING COMPLETED FAILED
factor_effectiveness_verdict_enum: postgresql.ENUM  # VALID INVALID
provenance_enum: postgresql.ENUM                 # DECIDED PROVISIONAL

# src/fip/services/factor_service/models/factor.py
class FactorDefinition(Base)                     # factor.factor_definition
class FactorVersion(Base)                        # factor.factor_version
class FactorRun(Base)                            # factor.factor_run
class FactorValue(Base, VersionedMixin)          # factor.factor_value
    #   P2-21 新增列 quality_flag（availability_quality_enum, NOT NULL）
    #   P2-30 新增列 risk_free_rate_curve_code（溯源第五字段）
class FactorEffectiveness(Base)                  # factor.factor_effectiveness
    #   P2-24 新增列 peer_group_key + segment，两者【进】Business Key
```

> **本任务受三条 Plan-2 追加裁定直接影响，实现前逐条核对：**
> **P2-21**（`factor_value.quality_flag`，链路 quality 移出 `status`）、
> **P2-24**（`factor_effectiveness` 补 `peer_group_key` / `segment`，
> 「只看 D-16 的实现者不会知道这一条」）、
> **P2-30**（R_f 溯源补第五字段 `curve_code`）。
> 三条都改建表，漏掉任何一条都要再发一支迁移。

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

枚举类型本体由迁移 0018 / 0019 用 op.execute("CREATE TYPE ...") 创建，
【不带 schema 限定】，因此落在 public —— 与 0001 建的
availability_quality_enum 一致，也是 tests/conftest.py 里
`DROP SCHEMA public CASCADE` 能把它们一次性清干净的前提。改成建在业务
schema 下会让测试库重置漏掉它们，第二次测试会话即失败。
"""
from sqlalchemy.dialects.postgresql import ENUM

# ---- factor schema（迁移 0018 创建）----

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

factor_status_reason_enum = ENUM(
    "INSUFFICIENT_HISTORY",
    "BENCHMARK_UNAVAILABLE",
    "RISK_FREE_RATE_UNAVAILABLE",
    "MAR_NOT_CONFIGURED",
    "ZERO_MAX_DRAWDOWN",
    "ZERO_DOWNSIDE_VOLATILITY",
    "ZERO_TRACKING_ERROR",
    "ZERO_VOLATILITY",
    # 第 9 值【补齐】：mar_policy = RISK_FREE 且窗口内某一期的 R_f 缺失。
    "MAR_SERIES_INCOMPLETE",
    # 第 10 值【Ruling PF-8】WARNING 的理由。它不属 UnavailableReason ——
    # 本列容纳 UNAVAILABLE 与 WARNING 两类理由，所以列名叫 status_reason
    # 而不是 unavailable_reason（见下方 docstring）。
    # 枚举分叉时落库会炸在 invalid input value for enum，由 Task 7 的
    # test_status_reason_enum_matches_the_strategy_library_enum 钉住 ——
    # 那条测试比对的是 UnavailableReason ∪ WarningReason。
    "NEAR_MIN_OBS",
    name="factor_status_reason_enum", create_type=False,
)
"""八类逐字抄自 10-api/03-factor-api.md §4.3.5，外加两条【补齐】。

── 为什么叫 status_reason 而不是 unavailable_reason（Ruling PF-8）──
P2-21 把 INFERRED_AVAILABILITY 从 WARNING 的触发条件里拿掉之后，
NEAR_MIN_OBS 成了 WARNING 的【唯一】理由。它是「算出来了，但观测数刚过线」，
【不是】「没法算」—— 装进一个名为 unavailable_reason 的列里，列名本身就在
说谎。改名为 status_reason 之后，这一列回答的是「status 为什么不是 VALID」，
UNAVAILABLE 与 WARNING 两类理由各归其位。

MAR_NOT_CONFIGURED 与「mar_policy = ZERO」是两回事：后者是【已配置】状态，
因子正常返回值。G-6 的「必填无默认」正是靠这个区分才有意义。
ZERO_MAX_DRAWDOWN / ZERO_DOWNSIDE_VOLATILITY / ZERO_VOLATILITY 是「好消息型」
不可用 —— 它们不是错误，不得告警，更不得填 inf（G-3）。
P2-20 明确修订 D-10：这三个值属 UNAVAILABLE 而【非】INVALID。判成 INVALID 会
传导到 evaluation_status = FAILED 并须告警，那意味着一只从未回撤的基金会告警。
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
        status="VALID", status_reason=None, observation_count=252,
        quality_flag="INFERRED",                    # P2-21
        peer_group_snapshot_id=None, peer_group_version=None,
        risk_free_rate_curve_code="CN_TREASURY",    # P2-30
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
        status_reason="ZERO_MAX_DRAWDOWN",
        raw_value=Decimal("0"), normalized_value=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unavailable_must_carry_a_reason(db_session, share_class, sharpe, run):
    """「没法算」必须说明为什么没法算，否则事后无法区分数据问题与业务常态。"""
    db_session.add(_value(
        share_class, sharpe, run, status="UNAVAILABLE",
        status_reason=None, raw_value=None, normalized_value=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_valid_must_not_carry_a_status_reason(db_session, share_class, sharpe, run):
    db_session.add(_value(
        share_class, sharpe, run, status_reason="ZERO_VOLATILITY"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_carries_no_value_and_no_reason(db_session, share_class, sharpe, run):
    """INVALID =「算了但算错了」，须告警；它不是 UNAVAILABLE，没有 reason 八类。"""
    db_session.add(_value(
        share_class, sharpe, run, status="INVALID",
        raw_value=None, normalized_value=None, status_reason=None,
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
    """【五个】必备字段（curve_code/currency/tenor/version/quality）缺一不可。

    缺 tenor 则无法验证期限匹配是否正确 —— 那正是这条溯源存在的理由。
    """
    db_session.add(_value(share_class, sharpe, run, risk_free_rate_tenor=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_risk_free_rate_ref_requires_the_curve_code(db_session, share_class, sharpe, run):
    """P2-30：curve_code 是补的【第五个】字段，上游 §9.2.1 只给了四个。

    中债同一天有国债 / 中短期票据AAA / 商业银行普通债AAA 三条曲线
    （实测信用债 10Y 高约 30bp）。没有这一列，溯源答不出「这个 Sharpe
    用的是哪条曲线」—— 而那正是 Plan-1 的 RiskFreeRate 主键第一列。
    """
    db_session.add(_value(share_class, sharpe, run, risk_free_rate_curve_code=None))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ------------------------------------------------- P2-21：quality_flag 与 status 正交

def test_m1_的常态是_VALID_加_INFERRED(db_session, share_class, sharpe, run):
    """P2-21：链路 quality 不进 status。

    AKShare 链路 100% 是 INFERRED（G-15）。D-10 原本把「链路含 INFERRED」
    列为 WARNING 的触发条件 —— 那会让 status 列在 M1 全表都是 WARNING、
    VALID 一行都没有。拆成两列之后两件事都说得清楚。
    """
    db_session.add(_value(share_class, sharpe, run,
                          status="VALID", quality_flag="INFERRED"))
    db_session.flush()          # 必须成功


def test_quality_flag_不可为空(db_session, share_class, sharpe, run):
    """「算不出来」不代表「不知道数据从哪来」—— UNAVAILABLE 的行也有链路。"""
    db_session.add(_value(
        share_class, sharpe, run, status="UNAVAILABLE",
        status_reason="ZERO_MAX_DRAWDOWN",
        raw_value=None, normalized_value=None, quality_flag=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_status_reason_enum_matches_the_strategy_library_enum(db_session):
    """库里的枚举必须等于 UnavailableReason ∪ WarningReason，逐值相同。

    【Ruling PF-8】本列同时容纳两类理由：UNAVAILABLE 的「没法算」八+一类，
    与 WARNING 的唯一理由 NEAR_MIN_OBS（P2-21 拿掉 INFERRED_AVAILABILITY 之后
    它就是唯一的）。只比对 UnavailableReason 会让 NEAR_MIN_OBS 悄悄漏掉，
    而那正是「列名叫 unavailable_reason 就装不下它」的同一个错误换了个位置。

    两处分叉时的表现是：因子算完、落库那一刻炸在
    `invalid input value for enum factor_status_reason_enum`，
    而且只在触发了那个 reason 的基金上炸 —— 可能几个月后才出现一次。
    """
    from fip.strategy_library.factor.status import UnavailableReason, WarningReason

    db_values = set(db_session.execute(text(
        "SELECT unnest(enum_range(NULL::factor_status_reason_enum))::text"
    )).scalars().all())
    assert db_values == (
        {r.value for r in UnavailableReason} | {r.value for r in WarningReason}
    )


def test_warning_carries_near_min_obs_as_its_reason(db_session, share_class, sharpe, run):
    """【Ruling PF-8】WARNING 是「算出来了，但观测数刚过线」——【有值】且带理由。

    改名之前这一行根本落不了库：列名是 unavailable_reason、枚举里也没有
    NEAR_MIN_OBS，于是 P2-21 之后唯一的 WARNING 理由无处安放。
    """
    db_session.add(_value(share_class, sharpe, run,
                          status="WARNING", status_reason="NEAR_MIN_OBS"))
    db_session.flush()          # 必须成功


def test_warning_must_not_borrow_an_unavailable_reason(db_session, share_class, sharpe, run):
    """WARNING 的触发条件 P2-21 明写只有一个。让它带 ZERO_VOLATILITY 之类的
    理由，等于允许「没法算」伪装成「算出来了但要打个折」。"""
    db_session.add(_value(share_class, sharpe, run,
                          status="WARNING", status_reason="ZERO_VOLATILITY"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unavailable_must_not_borrow_the_warning_reason(db_session, share_class, sharpe, run):
    """反向：UNAVAILABLE 不得拿 NEAR_MIN_OBS 当理由 —— 观测数刚过线的行
    是有值的，把它记成 UNAVAILABLE 就把一个能用的因子值丢掉了。"""
    db_session.add(_value(
        share_class, sharpe, run, status="UNAVAILABLE",
        status_reason="NEAR_MIN_OBS", raw_value=None, normalized_value=None,
    ))
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
        peer_group_key="AKSHARE_FUND_TYPE|混合型|CNY", segment="FULL",
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
        peer_group_key="AKSHARE_FUND_TYPE|混合型|CNY", segment="FULL",
        test_window_start=dt.date(2021, 1, 1), test_window_end=dt.date(2026, 1, 1),
        ic=None, icir=None, n_periods=0, verdict="INVALID",
        validation_policy_version="VP-v1",
    ))
    db_session.flush()


def test_test_window_must_be_ordered(db_session, sharpe, run):
    db_session.add(FactorEffectiveness(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT",
        peer_group_key="AKSHARE_FUND_TYPE|混合型|CNY", segment="FULL",
        test_window_start=dt.date(2026, 1, 1), test_window_end=dt.date(2021, 1, 1),
        ic=Decimal("0.05"), icir=Decimal("0.4"), n_periods=60, verdict="VALID",
        validation_policy_version="VP-v1",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_同一因子在两个_peer_group_上可以各有一条检验结论(db_session, sharpe, run):
    """P2-24：IC 是横截面统计量，横截面就是 Peer Group。

    同一因子在股票型有效、在债券型无效是**正常结果**。D-16 的字段清单漏了
    横截面，照它建表的话这两行会撞唯一键 —— 于是只剩两条出路：后写的覆盖
    先写的，或者被迫跨组池化（把不同收益分布放进同一条相关系数）。
    两者都会产出一个看起来完全正常的 IC。
    """
    common = dict(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT", segment="FULL",
        test_window_start=dt.date(2021, 1, 1), test_window_end=dt.date(2026, 1, 1),
        n_periods=60, verdict="VALID", validation_policy_version="VP-v1",
    )
    db_session.add(FactorEffectiveness(
        peer_group_key="AKSHARE_FUND_TYPE|混合型|CNY",
        ic=Decimal("0.05"), icir=Decimal("0.4"), **common,
    ))
    db_session.add(FactorEffectiveness(
        peer_group_key="AKSHARE_FUND_TYPE|债券型|CNY",
        ic=Decimal("0.01"), icir=Decimal("0.1"), **common,
    ))
    db_session.flush()      # 必须成功


def test_同一_peer_group_同一分段重复写入被唯一键拒绝(db_session, sharpe, run):
    """反向：peer_group_key + segment 【在】Business Key 里，重复即冲突。"""
    common = dict(
        factor_version_id=sharpe.id, factor_run_id=run.id,
        evaluation_profile="DEFAULT",
        peer_group_key="AKSHARE_FUND_TYPE|混合型|CNY", segment="FULL",
        test_window_start=dt.date(2021, 1, 1), test_window_end=dt.date(2026, 1, 1),
        ic=Decimal("0.05"), icir=Decimal("0.4"), n_periods=60, verdict="VALID",
        validation_policy_version="VP-v1",
    )
    db_session.add(FactorEffectiveness(**common))
    db_session.add(FactorEffectiveness(**common))
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
都必须在迁移 0018 里逐字出现，反之亦然**。本仓库已被「库里有而 metadata 里没有」
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
    factor_status_reason_enum,
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
# CHECK 的 SQL 字面量集中在这里，迁移 0018 里【逐字复制】同样的字符串。
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

# status 四值与 (raw_value, status_reason) 的联动。这是 G-3 的数据库防线：
#   VALID       → 有值，无 reason
#   WARNING     → 有值，且 reason 恰为 NEAR_MIN_OBS（P2-21：它是【唯一】的
#                 WARNING 触发条件。允许 WARNING 带别的 reason，等于允许
#                 「算不出来」伪装成「算出来了但要打个折」）
#   INVALID     → 算错了，无值，也没有 reason（八类 reason 全属「没法算」）
#   UNAVAILABLE → 无值，且必须说明为什么，且那个理由【不是】NEAR_MIN_OBS
#
# 【Ruling PF-8】WARNING 那一支是本次新增的：改名为 status_reason 之前，
# NEAR_MIN_OBS 在库里无处安放，WARNING 行只能把它丢掉。
FACTOR_VALUE_STATUS_SQL = (
    "(status = 'VALID' "
    " AND raw_value IS NOT NULL AND status_reason IS NULL) OR "
    "(status = 'WARNING' "
    " AND raw_value IS NOT NULL AND status_reason = 'NEAR_MIN_OBS') OR "
    "(status = 'INVALID' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND status_reason IS NULL) OR "
    "(status = 'UNAVAILABLE' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND status_reason IS NOT NULL AND status_reason <> 'NEAR_MIN_OBS')"
)

# R_f 溯源【五列】要么齐备要么全空。缺 tenor 则无法验证期限匹配，
# 那正是这几列存在的唯一理由。
#
# P2-30【补】上游 §9.2.1 的必备字段只有四个（currency / tenor / version /
# quality），**不含 curve_code**——而 Plan-1 的 RiskFreeRate 主键第一列就是它，
# 中债同一天有国债 / 中短期票据AAA / 商业银行普通债AAA 三条曲线（实测信用债
# 10Y 高约 30bp）。缺了它，溯源答不出「这个 Sharpe 用的是哪条曲线」。
# 上游的四字段清单成文时还没有 curve_code 这个维度。
RF_REF_SQL = (
    "num_nonnulls(risk_free_rate_curve_code, risk_free_rate_currency, "
    "risk_free_rate_tenor, risk_free_rate_version, risk_free_rate_quality) "
    "IN (0, 5)"
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
        #    两条 postgresql_where 必须与迁移 0018 逐字一致（含 WHERE 子句），
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
    # 【Ruling PF-8】列名是 status_reason 而不是 unavailable_reason：
    # P2-21 之后 NEAR_MIN_OBS 是 WARNING 的唯一理由，它是「算出来了但观测数
    # 刚过线」，不是「没法算」。本列回答的是「status 为什么不是 VALID」，
    # 两类理由各归其位，取值域 = UnavailableReason ∪ WarningReason。
    status_reason: Mapped[str | None] = mapped_column(
        factor_status_reason_enum, nullable=True
    )
    # D-10 的 WARNING / UNAVAILABLE 判据（观测数与 min_obs 的关系）在事后
    # 只有存下观测数才能复核，否则「为什么这条是 WARNING」无从回答。
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # P2-21【新增列】FactorResult.quality_flag —— 输入链路的
    # availability_quality（EXACT / DERIVED / INFERRED）。
    #
    # 它与 status 是【两个正交维度】：status 说「这个数算不算得出来」，
    # quality_flag 说「算它用的数据是怎么来的」。D-10 原本把「链路含 INFERRED」
    # 塞进 WARNING，而 AKShare 链路 100% 是 INFERRED（G-15）—— 那会让
    # status 列在 M1 全表都是 WARNING、VALID 一行都没有，这一列的信息量
    # 反而全部丢失。拆开之后 M1 的常态是 (VALID, INFERRED)。
    #
    # NOT NULL：每一个因子值都有确定的输入链路，包括 UNAVAILABLE 的那些
    # （「算不出来」不代表「不知道数据从哪来」）。
    quality_flag: Mapped[str] = mapped_column(
        availability_quality_enum, nullable=False
    )
    # ── 标准化上下文。03-erd §8.5：「Peer Group 与 Factor Value 的关系是
    #    『上下文』而非『归属』…这是一条弱关系（引用，非组合）」。
    #    FK 由迁移 0018 补上 —— evaluation.peer_group_snapshot 那时才存在。
    #    Task 8 Step 9 会同时改本文件与 0018，两处必须一起改。
    peer_group_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    peer_group_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ── R_f 溯源【五列】（§9.2.1 四列 + P2-30 补 curve_code）。
    #    BLOCK-14「JSONB 或列组」上游未裁决，
    #    本稿取【列组】：四个字段是固定的、要进 WHERE 的（「这只基金的 1Y 与
    #    3Y Sharpe 是不是用错了 tenor」是核对查询，不是展示），按
    #    01-postgresql §13.2 的判据必须结构化；JSONB 还会让键名拼错静默通过。
    #    「不进唯一约束」（:570）—— 它是溯源，与 evaluation_policy_version 相反。
    # P2-30【第五列，补】RiskFreeRate 主键的第一列，上游 §9.2.1 漏了它。
    risk_free_rate_curve_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
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

    ── P2-24【补 D-16】必须带 Peer Group 维度 ──

    D-16 给的字段清单是 (profile, factor_id, valid/invalid, IC, ICIR, 检验区间)
    ——**漏了横截面**。IC 是横截面统计量，而本平台的横截面【就是 Peer Group】。
    同一因子在股票型有效、在债券型无效是**正常结果**；不带 peer_group_key
    只有两条出路：要么后算的组覆盖先算的组，要么被迫跨组池化（把不同收益
    分布放进同一条相关系数）——两者都会产出一个看起来正常的 IC。

    因此增加两列并【进 Business Key】：
      · peer_group_key —— 与 PeerGroupKey.key_string() 同形
        （"{scheme}|{code}|{currency}"），指明这条 IC 是在哪个横截面上算的
      · segment        —— 检验分段（如 "FULL" / "2023H1"）。同一 Peer Group
        在不同子区间上的结论可以不同，没有这一列就只能覆盖

    ⚠️ 只看 D-16 的实现者不会知道这一条 —— 这正是它必须写进任务正文的原因。

    本表不设 updated_at：检验结果一经产出即不可变，重检产生新行
    （新的 factor_run_id / 检验区间），旧行保留。
    """

    __tablename__ = "factor_effectiveness"
    __table_args__ = (
        UniqueConstraint(
            # P2-24：peer_group_key 与 segment 必须【进】Business Key。
            # 不进的话，同一因子在两个 Peer Group 上的检验结论会撞唯一键，
            # 第二条写入直接失败 —— 而那是完全正常的数据。
            "factor_version_id", "evaluation_profile",
            "peer_group_key", "segment",
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
    # P2-24：IC 是横截面统计量，横截面就是 Peer Group。
    # 与 evaluation.peer_group_snapshot.classification_key 同形，
    # 但【不设 FK】—— 检验区间横跨多个决策日、对应多个快照行，
    # 指向其中任何一个都是在编造一个并不存在的一对一关系。
    peer_group_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # 检验分段。M1 只有 "FULL"，但列必须在：同一 Peer Group 在不同子区间上
    # 的结论可以不同，缺了它只能互相覆盖。
    segment: Mapped[str] = mapped_column(String(32), nullable=False)
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

- [ ] **Step 6: 写迁移 `db/migrations/versions/0018_factor_schema.py`**

用 `op.create_table` + `sa.Column` 而非 raw SQL：`window` 是 PostgreSQL
保留字，交给 SQLAlchemy 加引号比手写靠谱；且 0013 已立了这个先例。

```python
# db/migrations/versions/0018_factor_schema.py
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

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
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
# 五子句（clause 1..5），anchor = effective_at 且已钉 UTC —— 与迁移 0017
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
    "(status = 'VALID' "
    " AND raw_value IS NOT NULL AND status_reason IS NULL) OR "
    "(status = 'WARNING' "
    " AND raw_value IS NOT NULL AND status_reason = 'NEAR_MIN_OBS') OR "
    "(status = 'INVALID' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND status_reason IS NULL) OR "
    "(status = 'UNAVAILABLE' "
    " AND raw_value IS NULL AND normalized_value IS NULL "
    " AND status_reason IS NOT NULL AND status_reason <> 'NEAR_MIN_OBS')"
)
_RF_REF_SQL = (
    # P2-30：五列（含 curve_code），不是上游的四列。
    "num_nonnulls(risk_free_rate_curve_code, risk_free_rate_currency, "
    "risk_free_rate_tenor, risk_free_rate_version, risk_free_rate_quality) "
    "IN (0, 5)"
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
    ("factor_status_reason_enum", (
        "INSUFFICIENT_HISTORY", "BENCHMARK_UNAVAILABLE",
        "RISK_FREE_RATE_UNAVAILABLE", "MAR_NOT_CONFIGURED",
        "ZERO_MAX_DRAWDOWN", "ZERO_DOWNSIDE_VOLATILITY",
        "ZERO_TRACKING_ERROR", "ZERO_VOLATILITY",
        "MAR_SERIES_INCOMPLETE",        # 第 9 值【补齐】，见 platform/db/enums.py
        "NEAR_MIN_OBS")),               # 第 10 值【PF-8】WARNING 的唯一理由
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
            "status_reason",
            _enum("factor_status_reason_enum"), nullable=True,
        ),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        # P2-21：链路 quality 独立成列，不再挤进 status。
        sa.Column("quality_flag", _QUALITY_ENUM, nullable=False),
        # FK 由 0018 补（evaluation.peer_group_snapshot 此刻还不存在）。
        sa.Column("peer_group_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("peer_group_version", sa.Integer(), nullable=True),
        # P2-30：五列溯源，curve_code 是补的第五个。
        sa.Column("risk_free_rate_curve_code", sa.String(length=32), nullable=True),
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
        # P2-24：IC 是横截面统计量，横截面就是 Peer Group。无 FK（见 ORM 注释）。
        sa.Column("peer_group_key", sa.String(length=128), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
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
            # P2-24：peer_group_key / segment 必须进 Business Key，
            # 否则同一因子在两个 Peer Group 上的检验结论会撞唯一键。
            "factor_version_id", "evaluation_profile",
            "peer_group_key", "segment",
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
    c.execute("DROP DATABASE IF EXISTS fip_rt0018")
    c.execute("CREATE DATABASE fip_rt0018")
print("fip_rt0018 ready")
PY

export FIP_DATABASE_URL=postgresql+psycopg://localhost/fip_rt0018
.venv/bin/alembic -x db=dev upgrade head        # 0001 → 0018
.venv/bin/alembic -x db=dev downgrade 0017      # 0018 的 downgrade()
.venv/bin/alembic -x db=dev upgrade head        # 再上来一次
.venv/bin/alembic -x db=dev current             # 期望：0018 (head)
```

往返后必须验证「五张表 + 七个枚举都回来了、且 downgrade 时确实都走干净了」：

```bash
.venv/bin/python - <<'PY'
import psycopg
Q_T = """SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='factor' AND c.relkind IN ('r','p') ORDER BY 1"""
Q_E = """SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
         WHERE n.nspname='public' AND t.typtype='e' ORDER BY 1"""
with psycopg.connect("postgresql://localhost/fip_rt0018") as c:
    print("tables:", [r[0] for r in c.execute(Q_T)])
    print("enums :", [r[0] for r in c.execute(Q_E)])
PY
```

Expected:
```
tables: ['factor_definition', 'factor_effectiveness', 'factor_run', 'factor_value', 'factor_version']
enums : ['availability_quality_enum', 'factor_category_enum',
         'factor_effectiveness_verdict_enum', 'factor_run_status_enum',
         'factor_status_enum', 'factor_status_reason_enum',
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
    c.execute('DROP DATABASE IF EXISTS fip_rt0018')
print('dropped')"
unset FIP_DATABASE_URL
```

- [ ] **Step 8: G-16 闸门 —— autogenerate 必须报告零操作**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev revision --autogenerate -m "probe-0018" 2>&1 | tail -20
```

Expected: 生成的迁移文件里 `upgrade()` / `downgrade()` **都只有 `pass`**。
确认后立刻删掉探针文件：

```bash
rm db/migrations/versions/*probe-0018*.py
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
0018 里冻结的 `_TIME_ORDER_SQL` 与 mixins 的现状不一致，先查那个。

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

### Task 8: `evaluation` schema 九张表 + 迁移 0019

**Files:**

- Create: `src/fip/services/fund_service/models/__init__.py`
- Create: `src/fip/services/fund_service/models/evaluation.py`
- Create: `db/migrations/versions/0019_evaluation_schema.py`
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

# ---- evaluation schema（迁移 0019 创建）----

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
        classification_key="AKSHARE_FUND_TYPE|混合型|CNY",       # PF-7
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
        classification_key="AKSHARE_FUND_TYPE|UNCLASSIFIED|CNY",
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
        classification_key="AKSHARE_FUND_TYPE|混合型|CNY",
        classification_scheme=peer_group.classification_scheme,
        classification_level="L1", classification_code="混合型",
        base_currency="CNY", effective_at=EFF, version=1, member_count=9,
        classification_policy_version="CP-v2", peer_group_policy_version="PGP-v1",
        code_version="0.1.0+g1234567",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_classification_key_must_match_the_three_structured_columns(db_session):
    """【Ruling PF-7】classification_key 建了列，但它不是第二份真值。

    ck_peer_group_classification_key 断言它逐字等于三列的竖线拼接。
    没有这条 CHECK，这一列就真的会与三列分叉 —— 那正是 Task 8 起草期
    拒绝建这一列的理由（Plan-1 在 adjusted_nav 标量列上吃过的亏）。
    """
    db_session.add(PeerGroupSnapshot(
        classification_key="AKSHARE_FUND_TYPE|股票型|CNY",     # 与下面三列不符
        classification_scheme="AKSHARE_FUND_TYPE", classification_level="L1",
        classification_code="混合型", base_currency="CNY",
        effective_at=EFF, version=1, member_count=5,
        classification_policy_version="CP-v1", peer_group_policy_version="PGP-v1",
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


def test_两个_profile_可以对同一分数各出一份排名与分层(
    db_session, share_class, peer_group, run
):
    """D-28：唯一约束必须含 Profile。

    G-10 要求「同一 Peer Group 内多个 Profile 时按 Profile 拆分子排名」。
    唯一键若只有 (fund_score_id, ranking_metric)，第二个 Profile 的排名
    会撞唯一键 —— 而 **M1 全程不会显形**（M1 只有一个 Profile），
    直到 M2 加第二个 Profile 那天才炸。这条测试把它现在就钉住。
    """
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    r1 = _ranking(score, peer_group, evaluation_profile="DEFAULT")
    r2 = _ranking(score, peer_group, evaluation_profile="ACTIVE_EQUITY", rank=3,
                  percentile=Decimal("93.1818"))
    db_session.add_all([r1, r2])
    db_session.flush()          # 必须成功
    db_session.add_all([
        _tier(r1, evaluation_profile="DEFAULT"),
        _tier(r2, evaluation_profile="ACTIVE_EQUITY", tier="A+"),
    ])
    db_session.flush()          # 必须成功


def test_同一_profile_同一_metric_重复排名被唯一键拒绝(
    db_session, share_class, peer_group, run
):
    """反向：Profile 进了唯一键，同 Profile 重复仍然冲突。"""
    score = _score(share_class, peer_group, run)
    db_session.add(score)
    db_session.flush()
    db_session.add_all([
        _ranking(score, peer_group, evaluation_profile="DEFAULT"),
        _ranking(score, peer_group, evaluation_profile="DEFAULT"),
    ])
    with pytest.raises(IntegrityError):
        db_session.flush()


def _tier(ranking, **overrides):
    row = dict(
        fund_ranking_id=ranking.id, evaluation_profile="DEFAULT",   # D-28
        tier="A", classification_status="NORMAL",
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
from sqlalchemy.dialects.postgresql import ARRAY   # P2-25：classification_history_ids
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
# CHECK 的 SQL 字面量。迁移 0019 里【逐字复制】同样的字符串（不 import，
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

# 【Ruling PF-7】classification_key 必须建列（Peer Group 的身份，Task 11 的
# 写入方要传它，快照缺了它无法自解释）。但它确实与三个结构化列重复 ——
# 用这条 CHECK 把重复降级为「受约束的物化」：它只能是三列的竖线拼接，
# 想分叉数据库会先拒绝。分隔符与 PeerGroupKey.key_string() 逐字相同。
CLASSIFICATION_KEY_SQL = (
    "classification_key = classification_scheme || '|' "
    "|| classification_code || '|' || base_currency"
)


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

    ── classification_key 单独存一列（【Ruling PF-7】）──
    上游给了这个名字但「类型与构成 文档未给值」。它就是跨任务接口契约里的
    PeerGroupKey = (classification_scheme, classification_code, base_currency)
    的 key_string()。起草期本表【刻意不建】这一列，理由是「把三列再拼成一个
    字符串列存一遍，就是又一份可以与三列分叉的真值」（Plan-1 在 adjusted_nav
    标量列上花了三轮才想明白的那件事）—— 但 Task 11 的写入方要传它，
    照原样实现会立即 TypeError；而 classification_key 是 Peer Group 的
    【身份】，不存则快照无法自解释（下游拿到一行快照答不出它是哪个组）。

    裁定：**建这一列**，并用一条 CHECK 把「第二份真值」的风险按住 ——
    ck_peer_group_classification_key 断言它逐字等于三列的竖线拼接。
    于是它不是第二份真值，而是三列的一个受约束的物化视图：想让它分叉，
    数据库会先拒绝。唯一约束仍建在三列 + effective_at + version 上
    （加了 CHECK 之后两者等价，保留结构化的那一份作为权威）。

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

    ── classification_history_ids（P2-25【补】）──
    `FR-PEER-001` 的 Output 与架构文档都要求 B1 = 组成员 + **所用分类版本**，
    而 digest 明记「字段清单文档未给值」。缺了它，
    「只存构建规则不存结果则历史不可重建」（04-database-design §10.1.1）
    直接落空：分类被修订之后，同一个 effective_at 重跑会得到不同的成员集，
    而快照上没有任何东西能说明当时用的是哪一版分类。

    存的是**引用集合**（指向 `fund.fund_classification_history.id`），
    不是分类内容的副本 —— 与 D-15「引用而非复制」一致。
    用 `ARRAY(BigInteger)` 而不是 JSONB：它是同构的 id 列表，
    要能进 `WHERE ... = ANY(...)`（03-erd §9.3：进 WHERE / GROUP BY 的字段
    必须结构化）。
    ⚠️ 数组元素【无法】建外键（PG 不支持数组 FK）——因此额外由
    `peer_group_member.classification_history_id` 的逐行 FK 兜底：
    快照上的集合必须等于成员行上那些 id 的去重集合，由一条集成测试钉住。

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
        CheckConstraint(
            CLASSIFICATION_KEY_SQL, name="ck_peer_group_classification_key"
        ),
        {"schema": "evaluation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 【Ruling PF-7】Peer Group 的【身份】。取值 = PeerGroupKey.key_string()，
    # 由 ck_peer_group_classification_key 钉住它等于下面三列的竖线拼接。
    classification_key: Mapped[str] = mapped_column(String(96), nullable=False)
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
    # P2-25【补】FR-PEER-001 Output 的第三项：所用分类版本（引用集合）。
    # 无 FK（PG 不支持数组 FK），一致性由 peer_group_member 的逐行 FK
    # 与一条集成测试共同保证。
    classification_history_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False
    )
    # FR-PEER-001 Output 与 B1 边界都点名「所用分类版本」；上一列是【结果】
    # （具体用了哪几行），本列是【规则版本】（按哪一版分类政策选的行）。两者都要。
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
            # D-28：唯一约束【必须含 Profile】。本仓库的 Profile 标识列名是
            # evaluation_profile（无独立 profile 表，见跨任务接口契约的
            # EvaluationProfile 一节）。
            #
            # ⚠️ 起草稿的理由是「profile 经 fund_score_id 传导」—— 传导【不是】
            # 约束。G-10 要求按 Profile 拆分子排名；不含 Profile 的唯一键
            # 会在 M2 加第二个 Profile 那天变成主键冲突，而 M1 全程不会显形
            # （M1 只有一个 Profile，两种写法的行为完全一样）。
            # 这正是「只由阅读/推理保证的性质等于没有保护」的又一实例。
            "fund_score_id", "evaluation_profile", "ranking_metric",
            name="uq_fund_ranking_scope",
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
    # 不产出跨 Profile 统一排名。D-28：本列【进】唯一键，不靠 fund_score_id 传导。
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
        # D-28：唯一约束必须含 Profile。见 FundRanking 上同一条注释 ——
        # 不含它的唯一键在 M1 全程不会显形，M2 加第二个 Profile 那天才炸。
        UniqueConstraint(
            "fund_ranking_id", "evaluation_profile", name="uq_fund_tier_ranking"
        ),
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
    # D-28：Profile 必须在本表【自带】一列才能进唯一键。它与
    # fund_ranking.evaluation_profile 的一致性由写入方保证（同一次
    # 事务里从同一个 Profile 装配），这不是副本 —— 唯一键需要它在本表。
    evaluation_profile: Mapped[str] = mapped_column(String(32), nullable=False)
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
        # 迁移 0019 补上的 FK。03-erd §8.5 称 Peer Group 与 Factor Value 的
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

- [ ] **Step 8: 写迁移 `db/migrations/versions/0019_evaluation_schema.py`（枚举 + 前四张表）**

```python
# db/migrations/versions/0019_evaluation_schema.py
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

【已冻结的字面量】同 0018：不 import ORM 侧的 SQL 常量。

Revision ID: 0019
Revises: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
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
_CLASSIFICATION_KEY_SQL = (      # 【PF-7】与 models 里的 CLASSIFICATION_KEY_SQL 逐字相同
    "classification_key = classification_scheme || '|' "
    "|| classification_code || '|' || base_currency"
)
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
    """0018 已建的枚举，在本迁移里只引用不创建。"""
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
        # 【Ruling PF-7】Peer Group 的身份，由 CHECK 钉住 = 三列的竖线拼接。
        sa.Column("classification_key", sa.String(length=96), nullable=False),
        sa.Column("classification_scheme", sa.String(length=32), nullable=False),
        sa.Column("classification_level", sa.String(length=2), nullable=False),
        sa.Column("classification_code", sa.String(length=32), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("member_count", sa.Integer(), nullable=False),
        # P2-25【补】所用分类版本（引用集合）。数组无 FK —— 一致性由
        # peer_group_member.classification_history_id 的逐行 FK 兜底。
        sa.Column(
            "classification_history_ids",
            postgresql.ARRAY(sa.BigInteger()), nullable=False,
        ),
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
        sa.CheckConstraint(
            _CLASSIFICATION_KEY_SQL, name="ck_peer_group_classification_key"
        ),
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

- [ ] **Step 9: 续写 0019（后五张表 + `factor_value` 的 FK + `downgrade()`）**

```python
# db/migrations/versions/0019_evaluation_schema.py —— upgrade() 续

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
        # D-28：唯一约束必须含 Profile（本仓库的 Profile 标识列是
        # evaluation_profile）。不含它的唯一键在 M1 全程不会显形。
        sa.UniqueConstraint(
            "fund_score_id", "evaluation_profile", "ranking_metric",
            name="uq_fund_ranking_scope",
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
        # D-28：Profile 必须在本表自带一列才能进唯一键。
        sa.Column("evaluation_profile", sa.String(length=32), nullable=False),
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
        # D-28
        sa.UniqueConstraint(
            "fund_ranking_id", "evaluation_profile", name="uq_fund_tier_ranking"
        ),
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
    c.execute("DROP DATABASE IF EXISTS fip_rt0019")
    c.execute("CREATE DATABASE fip_rt0019")
print("fip_rt0019 ready")
PY

export FIP_DATABASE_URL=postgresql+psycopg://localhost/fip_rt0019
.venv/bin/alembic -x db=dev upgrade head        # 0001 → 0019
.venv/bin/alembic -x db=dev downgrade 0018      # 0019 的 downgrade()
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev current             # 期望：0019 (head)
```

`downgrade 0018` 这一步专门用来逼出两个最可能的错误：

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
with psycopg.connect("postgresql://localhost/fip_rt0019") as c:
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
    c.execute('DROP DATABASE IF EXISTS fip_rt0019')
print('dropped')"
unset FIP_DATABASE_URL
```

- [ ] **Step 11: G-16 闸门 —— autogenerate 必须报告零操作**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/alembic -x db=dev revision --autogenerate -m "probe-0019" 2>&1 | tail -30
```

Expected: `upgrade()` / `downgrade()` 里**只有 `pass`**。确认后删探针文件：

```bash
rm db/migrations/versions/*probe-0019*.py
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
| 6 | `evaluation.peer_group_snapshot` | 快照 | 否 | ❌ 无 | 含 `classification_key`（PF-7，由 CHECK 钉住 = 三列拼接）；无 `evaluation_profile` 列；UNCLASSIFIED 不成组 |
| 7 | `evaluation.peer_group_member` | 明细 | **否**（D-14） | ❌ 无 | 上游 PK 原样成立；分类版本存引用 |
| 8 | `evaluation.fund_score` | 版本化事实 | **否**（本稿裁定） | ❌ 无 | D-19 五值；G-4 `data_completeness` NOT NULL |
| 9 | `evaluation.fund_score_attribution` | 明细 | **否**（本稿裁定） | ❌ 无 | 独立表非 JSONB；三列权重恒等式 |
| 10 | `evaluation.fund_ranking` | 派生 `0..1` | 否 | ❌ 无 | 上游逐字联动 CHECK；G-8 三者落库 |
| 11 | `evaluation.fund_tier` | 派生 `0..1` | 否 | ❌ 无 | 联动 CHECK 为【补齐】；G-9 两个中位数；阈值不进 CHECK |
| 12 | `evaluation.fund_universe_snapshot` | 快照 | 否 | ❌ 无 | 策略 A 评分列可空；引用已提交的 B1 |
| 13 | `evaluation.fund_universe_member` | 明细 | 否 | ❌ 无 | D-15 复合 FK 版本引用；D-17 含 REJECTED |
| 14 | `evaluation.selection_condition_result` | 明细 | 否 | ❌ 无 | D-17 存全部条件；`NOT_EVALUABLE` 第三值 |

---


---

### Task 9: 10 个因子的纯函数 + Metric Version 登记

**Files:**

- Create: `src/fip/strategy_library/factor/__init__.py`
- Create: `src/fip/strategy_library/factor/definitions.py`
- Create: `src/fip/strategy_library/factor/status.py`
- Create: `src/fip/strategy_library/factor/compute.py`
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
from fip.quant_engine.series import returns, rolling_windows, running_max
from fip.quant_engine.stats import mean, stdev
# returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]
# rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]
# running_max(xs: Sequence[Decimal]) -> list[Decimal]
# mean(xs: Sequence[Decimal]) -> Decimal
# stdev(xs: Sequence[Decimal], ddof: int) -> Decimal
```

*Produces*（契约已定义的原样落地；kernel 为本任务新增）：

```python
# fip.strategy_library.factor.definitions
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

# fip.strategy_library.factor.status
class FactorStatus(StrEnum): VALID; WARNING; INVALID; UNAVAILABLE          # 契约
class UnavailableReason(StrEnum): INSUFFICIENT_HISTORY; BENCHMARK_UNAVAILABLE;
    RISK_FREE_RATE_UNAVAILABLE; MAR_NOT_CONFIGURED; ZERO_MAX_DRAWDOWN;
    ZERO_DOWNSIDE_VOLATILITY; ZERO_TRACKING_ERROR; ZERO_VOLATILITY;
    MAR_SERIES_INCOMPLETE             # 第 9 值【补齐】，见 Task 10 Step 4
    # ⚠️ ZERO_* 四值属 UNAVAILABLE 而【非】INVALID（P2-20 修订 D-10）
class WarningReason(StrEnum): NEAR_MIN_OBS
    # P2-21：INFERRED_AVAILABILITY 已删除，链路 quality 走 FactorResult.quality_flag
class InvalidReason(StrEnum): NON_FINITE; NEGATIVE_VARIANCE
INFERRED_QUALITY: str = "INFERRED"
WARNING_OBS_MULTIPLIER: Decimal = Decimal("1.5")

# fip.strategy_library.factor.compute —— kernel（纯数学，不量化、不判 status）
def annualized_return(navs, periods_per_year) -> Decimal
def volatility(rets, ddof, periods_per_year) -> Decimal
def downside_volatility(rets, mar_daily, ddof, periods_per_year) -> Decimal   # P2-22
def downside_deviations(rets, mar_daily) -> list[Decimal]                     # P2-22
def annualize_mar(mar_daily, periods_per_year) -> Decimal                     # P2-26
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

# fip.strategy_library.factor.compute —— 契约入口
@dataclass(frozen=True, slots=True)
class FactorInput: ...       # 契约原文，字段一字不改（含 mar_daily，P2-22）
@dataclass(frozen=True, slots=True)
class FactorResult: ...      # 契约原文，字段一字不改（含 quality_flag，P2-21）
def compute_factor(factor_id: str, inp: FactorInput) -> FactorResult
def observation_status(observation_count, min_obs) -> tuple[FactorStatus, str]
    # ⚠️ 【无】chain_quality 参数（P2-21）
```

---

- [ ] **Step 1: 写因子身份的失败测试**

10 个因子的 Factor ID / 类别 / 方向 / 依赖直接抄 D-8 的表。这条测试是「因子清单」的
唯一机器可读来源——写错方向的后果是分位整条翻转，而翻转后的分数看起来完全正常。

```python
# tests/unit/test_factor_definitions.py
from fip.strategy_library.factor.definitions import (
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
# 预期：ModuleNotFoundError: No module named 'fip.strategy_library.factor'
```

- [ ] **Step 2: 实现 `definitions.py`，跑通 Step 1**

```python
# src/fip/strategy_library/factor/definitions.py
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

# ---- D-24【补齐 C-3】声明 ≠ 可算，必须是【两个】常量 --------------------------
#
# FACTOR_IDS                  = 可算的 10 个（本模块 FACTORS 的键，有序）
# PROFILE_DECLARED_FACTOR_IDS = M1 Profile 声明的 13 个 = 10 + REL 三项
#
# 为什么必须都定义：data_completeness 的分母取【声明】数。若只定义前者，
# Task 14 的分母会静默变回 10，M1 的 data_completeness 恒为 1.0 ——
# 而 spec §6.2 与 M1.4 判据要求「Relative Performance Score 呈现为
# UNAVAILABLE 且 Data Completeness 反映之」，理由是「基于 4 个子分的 85 分
# 与基于 5 个子分的 85 分必须可区分」。分母取 10 会把这句话静默抹掉，
# M1 用来跑通 UNAVAILABLE 机制的唯一场景随之消失。
#
# 三个 REL ID 取自 D-8 点明的、从现存文档中【泄露出的真实 ID】。
# Tracking Error 与 Benchmark 超额收益不声明 —— 它们的真实 ID 未泄露，
# 凭空编号会在拿到正式文档时与真 ID 冲突，比少声明两个更难修。
FACTOR_IDS: tuple[str, ...] = tuple(FACTORS)

REL_DECLARED_ONLY_FACTOR_IDS: tuple[str, ...] = ("F-REL-002", "F-REL-003", "F-REL-004")

PROFILE_DECLARED_FACTOR_IDS: tuple[str, ...] = FACTOR_IDS + REL_DECLARED_ONLY_FACTOR_IDS


def preference_direction(factor_id: str) -> PreferenceDirection:
    """因子的偏好方向。Task 12 / 17 用它做方向转换。

    对声明但不可算的 REL 三项抛 KeyError —— 它们没有方向，因为它们没有值。
    """
    return FACTORS[factor_id].direction
```

追加两条测试（D-24 的机器可判定形式）：

```python
# tests/unit/test_factor_definitions.py（追加）
def test_可算与声明是两个不同的常量():
    """D-24：只定义 FACTOR_IDS 的话，Task 14 的分母会静默变回 10。"""
    from fip.strategy_library.factor.definitions import (
        FACTOR_IDS, PROFILE_DECLARED_FACTOR_IDS,
    )

    assert len(FACTOR_IDS) == 10
    assert len(PROFILE_DECLARED_FACTOR_IDS) == 13
    assert set(FACTOR_IDS) < set(PROFILE_DECLARED_FACTOR_IDS)
    assert set(PROFILE_DECLARED_FACTOR_IDS) - set(FACTOR_IDS) == {
        "F-REL-002", "F-REL-003", "F-REL-004"
    }


def test_M1_的_data_completeness_分母恒为_13():
    """把 D-29 的联动写成断言：Task 18 的判据 A-2 期望 0.76923077 = 10/13。

    若有人把分母改成「只算可算因子」，A-2 的期望值要变成 1.0，
    而那样它就退化成一条恒真的判据 —— M1.4 的完成判据
    「Data Completeness 反映之」随之失去被验证的对象。改一个必须改另一个。
    """
    from decimal import Decimal

    from fip.strategy_library.factor.definitions import (
        FACTOR_IDS, PROFILE_DECLARED_FACTOR_IDS,
    )

    completeness = (Decimal(len(FACTOR_IDS)) / Decimal(len(PROFILE_DECLARED_FACTOR_IDS))
                    ).quantize(Decimal("1e-8"))
    assert completeness == Decimal("0.76923077")
```

```bash
.venv/bin/pytest tests/unit/test_factor_definitions.py -q   # 预期 6 passed
```

- [ ] **Step 3: `status.py` —— Factor Status 四值的生产方触发条件（D-10）**

先写失败测试：

```python
# tests/unit/test_factor_compute.py（本文件后续步骤继续追加）
from decimal import Decimal

from fip.strategy_library.factor.status import (
    INFERRED_QUALITY,
    FactorStatus,
    UnavailableReason,
    WarningReason,
    observation_status,
)


def test_观测数低于_min_obs_是_UNAVAILABLE_不是_WARNING():
    status, reason = observation_status(251, 252)
    assert status is FactorStatus.UNAVAILABLE
    assert reason == UnavailableReason.INSUFFICIENT_HISTORY.value


def test_落在_min_obs_到_1_5_倍之间是_WARNING():
    assert observation_status(252, 252) == (
        FactorStatus.WARNING, WarningReason.NEAR_MIN_OBS.value
    )
    assert observation_status(377, 252) == (
        FactorStatus.WARNING, WarningReason.NEAR_MIN_OBS.value
    )
    assert observation_status(378, 252) == (FactorStatus.VALID, "")


def test_链路含_INFERRED_不影响_status():
    """P2-21【修订 D-10】：链路 quality 已移出 FactorStatus。

    D-10 原本把「链路含 INFERRED」列为 WARNING 的第二触发条件。而 AKShare
    链路 100% 是 INFERRED（G-15），两者相乘的结果是【每个因子、每只基金、
    每个时点都是 WARNING，VALID 在 M1 完全不可达】——下游若把 WARNING 当
    异常处理，M1 会表现为「什么都不正常」。

    status 只反映【可计算性】，quality 反映【数据出处】，两个正交维度。
    这条测试就是防止有人「按 D-10 原文」把它加回去。
    """
    assert observation_status(1000, 252) == (FactorStatus.VALID, "")


def test_observation_status_不接受_chain_quality_参数():
    """把 P2-21 钉成签名事实而不是注释里的一句话。"""
    import inspect

    assert list(inspect.signature(observation_status).parameters) == [
        "observation_count", "min_obs",
    ]


def test_INFERRED_字面量与平台枚举一致():
    """strategy_library 不得 import platform.source（SDL-1），因此这里写的是
    字面量。它现在的用途是 FactorResult.quality_flag 的取值域（P2-21），
    字面量与枚举分叉时 quality_flag 会静默变成一个平台不认识的字符串。"""
    from fip.platform.source.availability import AvailabilityQuality

    assert INFERRED_QUALITY == AvailabilityQuality.INFERRED.value
```

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q
# 预期：ModuleNotFoundError: ...factor.status
```

实现：

```python
# src/fip/strategy_library/factor/status.py
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

    ⚠️ **P2-20 已正式修订 D-10**：D-10 原文把「分母为 0」列在 INVALID 下，
    而 D-9 与本枚举（ZERO_MAX_DRAWDOWN / ZERO_VOLATILITY / ZERO_DOWNSIDE_VOLATILITY）
    把同一情形列在 UNAVAILABLE 下。**取 UNAVAILABLE** ——「窗口内无回撤」是好消息型
    不可用，不是算错了；把它标成 INVALID 会触发 evaluation_status = FAILED 并告警，
    对一只从未回撤的基金发告警是错的。INVALID 只留给真正的数学失效
    （NaN / 负方差 / 序列自相矛盾，见 InvalidReason）。
    """

    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"
    RISK_FREE_RATE_UNAVAILABLE = "RISK_FREE_RATE_UNAVAILABLE"
    MAR_NOT_CONFIGURED = "MAR_NOT_CONFIGURED"
    ZERO_MAX_DRAWDOWN = "ZERO_MAX_DRAWDOWN"
    ZERO_DOWNSIDE_VOLATILITY = "ZERO_DOWNSIDE_VOLATILITY"
    ZERO_TRACKING_ERROR = "ZERO_TRACKING_ERROR"
    ZERO_VOLATILITY = "ZERO_VOLATILITY"
    # 【补齐】mar_policy = RISK_FREE 且某一期的 R_f 缺失 —— MAR 序列不完整。
    # 缺一期就补 0 等于宣称那一天的门槛是零收益（G-3），因此整段 UNAVAILABLE。
    # ⚠️ 起草期这里曾是 MAR_SERIES_NOT_SUPPORTED（「标量装不下序列」），
    # P2-22 把 FactorInput.mar 改成逐期序列 mar_daily 之后，RISK_FREE 模式
    # 在 M1 【可用】，那个取值随之作废。
    MAR_SERIES_INCOMPLETE = "MAR_SERIES_INCOMPLETE"


class WarningReason(StrEnum):
    """P2-21：只剩一个取值。

    INFERRED_AVAILABILITY 已【删除】—— 链路 quality 移到
    FactorResult.quality_flag，不再占用 status。留着它会让 VALID 在 M1
    完全不可达（AKShare 链路 100% INFERRED，G-15）。
    """

    NEAR_MIN_OBS = "NEAR_MIN_OBS"


class InvalidReason(StrEnum):
    """「算了但算错了」—— 须告警。分母为 0 不在此列，见 UnavailableReason 的说明。"""

    NON_FINITE = "NON_FINITE"
    NEGATIVE_VARIANCE = "NEGATIVE_VARIANCE"


# 链路聚合后的 availability_quality（Task 2 产出）的取值之一。
# P2-21：它进 FactorResult.quality_flag，【不】参与 status 判定。
# 字面量而非 import：strategy_library 不得依赖 platform.source（SDL-1）。
# 与 AvailabilityQuality.INFERRED 的一致性由 tests/unit/test_factor_compute.py
# ::test_INFERRED_字面量与平台枚举一致 钉住。
INFERRED_QUALITY = "INFERRED"

WARNING_OBS_MULTIPLIER = Decimal("1.5")


def observation_status(
    observation_count: int, min_obs: int
) -> tuple[FactorStatus, str]:
    """按 D-10（经 P2-21 修订）判定「观测数」这一维的 status。

    ⚠️ 签名里【没有】chain_quality：P2-21 已把链路 quality 移出 status，
    它现在原样进 FactorResult.quality_flag。加回这个参数会让 M1 的每一个
    因子值都变成 WARNING（AKShare 链路 100% INFERRED，G-15）。

    依赖缺失（R_f / MAR）不在这里判 —— 那一维由 compute_factor 更早地短路，
    且【优先级更高】：见 compute_factor 的 docstring。

    返回 (status, reason)。VALID 时 reason 为空串 —— 契约规定 reason 只在
    status 非 VALID 时必填。
    """
    if observation_count < min_obs:
        return FactorStatus.UNAVAILABLE, UnavailableReason.INSUFFICIENT_HISTORY.value
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

from fip.strategy_library.factor import definitions as defs
from fip.strategy_library.factor.compute import (
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
    assert close(
        downside_volatility([D(1), D("-0.5"), D(1)], [D(0)] * 3, 1, 3), D("0.5")
    )


def test_下行波动_MAR每期0点1时等于0点6():
    """年化 0.3 经 SIMPLE_DIVISION 折算成每期 0.3/3 = 0.1（P2-26 的口径已在
    threshold.mar 里完成，kernel 只吃逐期序列）。√0.12 × √3 = √0.36 = 0.6。"""
    assert close(
        downside_volatility([D(1), D("-0.5"), D(1)], [D("0.1")] * 3, 1, 3), D("0.6")
    )


def test_下行波动接受逐期变动的_MAR():
    """P2-22 的核心动机：RISK_FREE 模式下 MAR 每期不同，标量装不下它。"""
    got = downside_volatility(
        [D(1), D("-0.5"), D(1)], [D("0.05"), D("0.1"), D("0.15")], 1, 3
    )
    assert got > D(0)


def test_MAR序列与收益率序列长度不等时响亮失败():
    """zip 截断会静默丢掉尾部，而 Sortino 照样算出一个数。"""
    with pytest.raises(ValueError, match="长度不等"):
        downside_volatility([D(1), D("-0.5"), D(1)], [D(0), D(0)], 1, 3)


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
#       'fip.strategy_library.factor.compute'（模块尚不存在）
```

- [ ] **Step 5: 实现 kernel（`compute.py` 上半部），跑通 Step 4**

```python
# src/fip/strategy_library/factor/compute.py
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

from fip.quant_engine.series import returns, rolling_windows, running_max
from fip.quant_engine.stats import mean, stdev
from fip.strategy_library.factor.definitions import (
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
from fip.strategy_library.factor.status import (
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
    rets: Sequence[Decimal], mar_daily: Sequence[Decimal]
) -> list[Decimal]:
    """min(r_t − MAR_t, 0)。

    P2-22：MAR 是【逐期序列】，与 rets 1:1 对齐。折算口径（年化 →
    逐期，SIMPLE_DIVISION）已在上游 threshold.mar.mar_daily_series() 完成，
    本函数不再做除法 —— 口径决策只应发生在一个地方。

    长度不等直接抛错而不是 zip 截断：zip 会静默丢掉尾部，
    Sortino 照样算出一个数。
    """
    if len(rets) != len(mar_daily):
        raise ValueError(
            f"收益率序列（{len(rets)} 期）与 mar_daily（{len(mar_daily)} 期）长度不等"
        )
    return [min(r - m, ZERO) for r, m in zip(rets, mar_daily, strict=True)]


def annualize_mar(mar_daily: Sequence[Decimal], periods_per_year: int) -> Decimal:
    """逐期 MAR 的年化回代（SIMPLE_DIVISION 的逆运算，P2-26）。

    Sortino 的分子是「年化收益率 − 年化 MAR」，分母是年化下行波动率；
    三者必须同一口径。逐期 MAR 在 ZERO / CUSTOM 模式下是常数序列，
    此时 mean × periods_per_year 恰好还原配置里那个年化值；
    RISK_FREE 模式下它是这段窗口的平均年化 R_f —— 这个平均【只用于分子】，
    分母的下行偏差仍然是逐期比对的，不存在「用均值当标尺」的问题。
    """
    return mean(mar_daily) * Decimal(periods_per_year)


def downside_volatility(
    rets: Sequence[Decimal], mar_daily: Sequence[Decimal],
    ddof: int, periods_per_year: int
) -> Decimal:
    """P2-22：mar_daily 是与 rets 1:1 对齐的逐期序列，不是年化标量。"""
    deviations = downside_deviations(rets, mar_daily)
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

from fip.strategy_library.factor.compute import (
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
    """mar 是【年化标量】，这里就地展开成逐期序列（P2-22）。

    夹具替调用方做这一步，是为了让每条用例还能用 `mar=D(0)` 这样的写法读；
    被测代码收到的是 `mar_daily` 序列，与生产路径完全一致 —— 生产路径由
    threshold.mar.mar_daily_series() 产出同样形状的序列。
    mar=None 表示 mar_policy 未配置，序列亦为 None，绝不退化成全零。
    """
    navs, dates = _series(n_returns, r)
    n_periods = len(navs) - 1
    # 与 threshold.mar 的 SIMPLE_DIVISION 口径一致（P2-26）。这里写成局部常量
    # 而不是 import 配置：strategy_library 的测试不读 YAML（SDL-1 的同一理由）。
    ppy = defs.TRADING_DAYS_PER_YEAR
    mar_daily = None if mar is None else (mar / ppy,) * n_periods
    return FactorInput(
        effective_at=dates[-1],
        adjusted_navs=navs,
        nav_dates=dates,
        chain_quality=quality,
        risk_free_rate=rf,
        mar_daily=mar_daily,
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
    """G-6 / P2-4：mar_policy 必填无默认。mar_daily=None 表示未配置，绝不当作全零。"""
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


def test_INFERRED_链路进_quality_flag_而不是_status():
    """P2-21：M1 的常态是 status=VALID + quality_flag=INFERRED。

    D-10 原本把链路 quality 塞进 WARNING，而 AKShare 链路恒 INFERRED（G-15）
    —— 那会让 M1 的每一个因子值都是 WARNING、VALID 完全不可达，下游把一切
    当异常。这条测试把「常态」钉住，与 D-19『M1 常态是 PARTIAL』同类。
    """
    result = compute_factor("F-RET-001", _input(400, "0.001", quality="INFERRED"))
    assert result.status is FactorStatus.VALID
    assert result.reason == ""
    assert result.quality_flag == "INFERRED"


def test_quality_flag_原样透传输入链路的三个取值():
    for quality in ("EXACT", "DERIVED", "INFERRED"):
        result = compute_factor("F-RET-001", _input(400, "0.001", quality=quality))
        assert result.quality_flag == quality


def test_未知_factor_id_响亮失败():
    with pytest.raises(KeyError):
        compute_factor("F-NOPE-999", _input())


def test_日期与净值长度不一致响亮失败():
    navs, dates = _series(10, "0.001")
    with pytest.raises(ValueError, match="长度"):
        compute_factor("F-RET-001", FactorInput(
            effective_at=dates[-1], adjusted_navs=navs, nav_dates=dates[:-1],
            chain_quality="EXACT", risk_free_rate=D("0.02"), mar_daily=None,
        ))


def test_日期未按升序响亮失败():
    navs, dates = _series(10, "0.001")
    with pytest.raises(ValueError, match="升序"):
        compute_factor("F-RET-001", FactorInput(
            effective_at=dates[-1], adjusted_navs=navs,
            nav_dates=tuple(reversed(dates)),
            chain_quality="EXACT", risk_free_rate=D("0.02"), mar_daily=None,
        ))
```

```bash
.venv/bin/pytest tests/unit/test_factor_compute.py -q
# 预期：ImportError: cannot import name 'compute_factor'
```

- [ ] **Step 7: 实现 `compute_factor`，跑通 Step 6**

```python
# src/fip/strategy_library/factor/compute.py（追加到文件末尾）

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
        assert inp.mar_daily is not None
        value = downside_volatility(rets, inp.mar_daily, VOLATILITY_DDOF, ppy)
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
        assert inp.mar_daily is not None
        dvol = downside_volatility(rets, inp.mar_daily, VOLATILITY_DDOF, ppy)
        # Sortino 的分子是「年化收益率 − 年化 MAR」。逐期 MAR 的年化回代同样
        # 走 SIMPLE_DIVISION 的逆运算（P2-26），与分母口径保持一致。
        value = sortino_ratio(annualized_return(navs, ppy),
                              dvol, annualize_mar(inp.mar_daily, ppy))
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
      ⑤ 数学失效（NaN / 负方差 / 序列自相矛盾）→ INVALID，须告警
      ⑥ 其余 → observation_status 判 VALID / WARNING

    ④ 与 ⑤ 的分界是 P2-20【修订 D-10】：分母为 0 属【良性不可算】，
    走 UNAVAILABLE 而不是 INVALID。INVALID 会传导到 evaluation_status =
    FAILED 并须告警 —— 按 D-10 原文实现的话，**一只从未回撤的基金会触发告警**。

    value 在 UNAVAILABLE / INVALID 时【恒为 None】—— 不填 0、不填上期值、
    不填 inf、不填组内均值（G-3）。

    quality_flag 一律原样取 inp.chain_quality（P2-21），与 status 无关：
    它说的是「算它用的数据是怎么来的」，不是「算不算得出来」。
    """
    definition = FACTORS[factor_id]
    _validate(inp)
    observations = _observation_count(inp, definition.observation_unit)

    # quality_flag 与 status 正交（P2-21）：每一条返回路径都要带上它。
    quality = inp.chain_quality

    if FactorDependency.MAR in definition.dependencies and inp.mar_daily is None:
        return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                            UnavailableReason.MAR_NOT_CONFIGURED.value,
                            observations, quality)
    if (
        FactorDependency.RISK_FREE_RATE in definition.dependencies
        and inp.risk_free_rate is None
    ):
        return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                            UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value,
                            observations, quality)

    status, reason = observation_status(observations, definition.min_obs)
    if status is FactorStatus.UNAVAILABLE:
        return FactorResult(factor_id, None, status, reason, observations, quality)

    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        try:
            value, unavailable_reason = _compute_value(factor_id, inp)
        except DecimalException:
            # 「算了但算错了」——须告警（10-api/03 §4.3.5）。与④的区别：
            # ④ 是「这个业务情形下本来就没有定义」，⑤ 是「数值链路坏了」。
            return FactorResult(factor_id, None, FactorStatus.INVALID,
                                InvalidReason.NON_FINITE.value, observations, quality)
        if value is None:
            # ④ 分母为 0 这类良性不可算 —— UNAVAILABLE，不是 INVALID（P2-20）。
            return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE,
                                unavailable_reason, observations, quality)
        if not value.is_finite():
            return FactorResult(factor_id, None, FactorStatus.INVALID,
                                InvalidReason.NON_FINITE.value, observations, quality)
        quantized = _quantize(value)

    return FactorResult(factor_id, quantized, status, reason, observations, quality)
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

from fip.strategy_library.factor.compute import compute_factor
from fip.strategy_library.factor.definitions import FACTORS

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

from fip.strategy_library.factor import definitions as defs
from fip.strategy_library.factor.status import WARNING_OBS_MULTIPLIER
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

- Create: `src/fip/strategy_library/threshold/__init__.py`
- Create: `src/fip/strategy_library/threshold/mar.py`
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
from fip.strategy_library.factor.status import UnavailableReason
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

# fip.services.data_service.adapters.akshare.parse（追加，P2-30）
CURVE_CURRENCIES: dict[str, str]      # {"CN_TREASURY": "CNY", "CN_MTN_AAA": "CNY",
                                      #  "CN_BANK_AAA": "CNY"} —— 中债三条曲线均为 CNY
RISK_FREE_CURVE_CODE: str = "CN_TREASURY"
# ⚠️ P2-30 的空档：RiskFreeRate 主键含 currency，而 ParsedYieldPoint【不带】它。
# 裁定是在【适配器层】用 CURVE_CURRENCIES 补上（「这条曲线以什么计价」属于
# 「这条曲线是什么」），**不给 ParsedYieldPoint 加字段、也不让 ingest 现编**。

# fip.strategy_library.threshold.mar（纯函数，不碰数据库）
class MarPolicy(StrEnum): ZERO = "ZERO"; CUSTOM = "CUSTOM"; RISK_FREE = "RISK_FREE"
    # P2-23：第三模式逐字取上游的 CUSTOM，【不是】FIXED
@dataclass(frozen=True, slots=True)
class MarResolution:
    policy: MarPolicy | None
    annualized: Decimal | None                       # ZERO / CUSTOM：配置给的标量口径值
    series: tuple[tuple[dt.date, Decimal], ...] | None  # RISK_FREE：R_f 逐期序列
    quotation_basis: str | None                      # P2-23：CUSTOM 必填
    unavailable_reason: str | None
def resolve_mar(policy_name: str | None, custom_value: Decimal | None,
                mar_quotation_basis: str | None,
                risk_free_series: Sequence[tuple[dt.date, Decimal]] | None) -> MarResolution
def mar_daily_series(res: MarResolution, period_dates: Sequence[dt.date],
                     periods_per_year: int = 252) -> tuple[Decimal, ...] | None
    # P2-22：三模式统一产出与收益率序列 1:1 对齐的逐期序列；
    # 起草期的 mar_for_factor_input（标量出口）已作废

# fip.services.factor_service.thresholds（装配层，可以碰数据库）
@dataclass(frozen=True, slots=True)
class RiskFreeRateRef:
    curve_code: str          # P2-30【第五字段，补】中债同一天三条曲线，
                             # 缺它则溯源答不出「用的是哪条曲线」（实测信用债 10Y 高约 30bp）
    currency: str; tenor: str; version: int; rate_source_quality: str
@dataclass(frozen=True, slots=True)
class ResolvedThresholds:
    risk_free_rate: Decimal | None
    risk_free_rate_ref: RiskFreeRateRef | None
    mar_daily: tuple[Decimal, ...] | None        # P2-22：直接就是 FactorInput.mar_daily
    mar_unavailable_reason: str | None
    mar_policy: MarPolicy | None
class ThresholdResolver:
    def __init__(self, rates: RiskFreeRatePitRepository, config: ConfigSet) -> None
    def resolve(self, base_currency: str, date_from: dt.date, date_to: dt.date,
                period_dates: Sequence[dt.date]) -> ResolvedThresholds
        # period_dates = 收益率序列每一期的日期，用于产出对齐的 mar_daily

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


def test_CUSTOM_模式的取值在_ZERO_模式下不得存在():
    """mar_value 仅 CUSTOM 模式必填（FE:454-460）。ZERO 模式下留着它，
    会让一次 mar_policy 的改动静默启用一个没人复核过的数值。

    P2-23：第三模式的名字是上游逐字的 `CUSTOM`，不是 `FIXED`。它会进
    evaluation_policy_version 的可复现链路，改名要带数据迁移，此处定死。
    """
    assert "mar.custom_value" not in _cfg().parameters
    assert "mar.mar_quotation_basis" not in _cfg().parameters


def test_MAR_逐期折算口径必须显式配置():
    """P2-26：年化 MAR → 逐期 MAR 的折算方式是一个【口径决策】。
    不写出来，下游就会各自除以 252 / 365 / 250，而三者的 Sortino 不同。"""
    assert _cfg().get("mar.daily_conversion") == "SIMPLE_DIVISION"
    assert _cfg().get("mar.periods_per_year") == 252


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
  # P2-26：年化 MAR → 逐期 MAR 的折算口径。三种模式最终都产出【逐期序列】
  # （P2-22），所以这个口径对 ZERO 以外的两种模式都生效。
  daily_conversion:
    value: SIMPLE_DIVISION
    status: PROVISIONAL
    source: "Plan-2 设计定案 P2-26 —— 年化值 / periods_per_year；上游未给口径"
  periods_per_year:
    value: 252
    status: PROVISIONAL
    source: "Plan-2 设计定案 P2-26 —— 交易日口径，与 quant_engine 的年化口径同源"
  # ⚠️ 【没有】custom_value / mar_quotation_basis —— 当前 mar_policy 是 ZERO。
  # 切到 CUSTOM 时【两项都必填】（P2-23），由 resolve_mar 响亮失败守住。
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

from fip.strategy_library.factor.status import UnavailableReason
from fip.strategy_library.factor.definitions import FactorInput
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.threshold.mar import (
    MarPolicy,
    mar_daily_series,
    resolve_mar,
)

D = Decimal
RF = [(dt.date(2024, 1, 2), D("0.023")), (dt.date(2024, 1, 3), D("0.0231"))]


def test_未配置时不解析出任何数值():
    res = resolve_mar(None, None, None, RF)
    assert res.policy is None
    assert res.annualized is None and res.series is None
    assert res.unavailable_reason == UnavailableReason.MAR_NOT_CONFIGURED.value


def test_空串同样视为未配置():
    assert resolve_mar("", None, None, RF).unavailable_reason == (
        UnavailableReason.MAR_NOT_CONFIGURED.value
    )


def test_ZERO_模式解析为标量0():
    res = resolve_mar("ZERO", None, None, RF)
    assert res.policy is MarPolicy.ZERO
    assert res.annualized == D(0)
    assert res.series is None


def test_ZERO_与未配置的差别不在数值而在_status():
    """两者算出来的 MAR 都是 0，但一个有决策、一个没有。
    这条测试是 FE:481 的机器可读形式。"""
    configured = resolve_mar("ZERO", None, None, RF)
    missing = resolve_mar(None, None, None, RF)
    assert configured.annualized == D(0)
    assert missing.annualized is None
    assert configured.unavailable_reason is None


def test_CUSTOM_模式必须给值否则响亮失败():
    """P2-23：上游 §16.3 逐字是 CUSTOM，不是 FIXED。"""
    with pytest.raises(ValueError, match="CUSTOM"):
        resolve_mar("CUSTOM", None, None, RF)


def test_CUSTOM_模式必须同时给出年化口径():
    """P2-23：CUSTOM 必填 mar_quotation_basis。

    「MAR = 3%」不说清是年化还是月度，折算到逐期时会差 12 倍，
    而 Sortino 照样算得出一个看起来正常的数。"""
    with pytest.raises(ValueError, match="mar_quotation_basis"):
        resolve_mar("CUSTOM", D("0.03"), None, RF)


def test_CUSTOM_模式解析为配置值():
    res = resolve_mar("CUSTOM", D("0.03"), "ANNUALIZED", RF)
    assert res.policy is MarPolicy.CUSTOM and res.annualized == D("0.03")
    assert res.quotation_basis == "ANNUALIZED"


def test_RISK_FREE_模式解析为序列而不是标量():
    res = resolve_mar("RISK_FREE", None, None, RF)
    assert res.policy is MarPolicy.RISK_FREE
    assert res.annualized is None
    assert res.series == tuple(RF)


def test_RISK_FREE_模式在_Rf_缺失时不可解析():
    res = resolve_mar("RISK_FREE", None, None, [])
    assert res.series is None
    assert res.unavailable_reason == UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value


def test_未登记的模式名响亮失败():
    with pytest.raises(ValueError, match="mar_policy"):
        resolve_mar("AVERAGE_OF_PEERS", None, None, RF)


# --- P2-22：三种模式统一产出【与收益率序列 1:1 对齐】的逐期序列 --------------

NAV_DATES = (dt.date(2024, 1, 2), dt.date(2024, 1, 3))   # 收益率序列长度 = 2


def test_三种模式产出的都是长度相同的逐期序列():
    """P2-22：契约是 `FactorInput.mar_daily: tuple[Decimal, ...] | None`，
    与收益率序列 1:1 对齐。消费方【不分支】—— 因子函数里不该出现
    `if mar is scalar ... else ...`，那种分支迟早会在一种模式下写错。"""
    z = mar_daily_series(resolve_mar("ZERO", None, None, RF), NAV_DATES)
    c = mar_daily_series(resolve_mar("CUSTOM", D("0.0252"), "ANNUALIZED", RF), NAV_DATES)
    r = mar_daily_series(resolve_mar("RISK_FREE", None, None, RF), NAV_DATES)
    assert len(z) == len(c) == len(r) == len(NAV_DATES)


def test_ZERO_模式是全零序列而不是_None():
    """全零序列不是「填充值」（G-3 禁的是拿数值冒充缺失）：
    mar_policy = ZERO 是一次【显式决策】，它的逐期取值就是 0。"""
    assert mar_daily_series(resolve_mar("ZERO", None, None, RF), NAV_DATES) == (D(0), D(0))


def test_CUSTOM_模式按声明的年化口径折算到逐期():
    """P2-26：SIMPLE_DIVISION —— 年化值 / periods_per_year(252)。"""
    res = resolve_mar("CUSTOM", D("0.0252"), "ANNUALIZED", RF)
    got = mar_daily_series(res, NAV_DATES, periods_per_year=252)
    assert all(x == D("0.0252") / 252 for x in got)


def test_RISK_FREE_模式逐日取当日_Rf_并按同一口径折算():
    """RISK_FREE 在 M1 【可用】—— 不再登记为缺口（P2-22）。"""
    got = mar_daily_series(resolve_mar("RISK_FREE", None, None, RF), NAV_DATES,
                           periods_per_year=252)
    assert got == (D("0.023") / 252, D("0.0231") / 252)


def test_RISK_FREE_模式缺某一天的_Rf_时整段不可用而不是补零():
    """G-3：缺一天就补 0，等于宣称那天的门槛是零收益。"""
    partial = [(dt.date(2024, 1, 2), D("0.023"))]      # 缺 1-03
    assert mar_daily_series(resolve_mar("RISK_FREE", None, None, partial),
                            NAV_DATES) is None


def test_未配置时逐期序列为_None():
    assert mar_daily_series(resolve_mar(None, None, None, RF), NAV_DATES) is None


def test_未配置_MAR_时两个依赖因子一律_UNAVAILABLE():
    """P2-4 / G-6 的端到端断言：这条是 G-6 唯一的机器可验形式。

    只断言 resolve_mar 返回 None 是不够的 —— 真正要防的是「某个因子函数
    自己给 mar 兜了个 0」，那要到 compute_factor 这一层才看得见。
    """
    from fip.strategy_library.factor.compute import compute_factor

    navs = tuple(D("1.0") * (D("1.001") ** i) for i in range(401))
    base = dt.date(2020, 1, 1)
    inp = FactorInput(
        effective_at=base + dt.timedelta(days=400),
        adjusted_navs=navs,
        nav_dates=tuple(base + dt.timedelta(days=i) for i in range(len(navs))),
        chain_quality="INFERRED",
        risk_free_rate=D("0.02"),
        mar_daily=None,                     # ← mar_policy 未配置的形状
    )
    for factor_id in ("F-RISK-002", "F-RAP-002"):
        result = compute_factor(factor_id, inp)
        assert result.status is FactorStatus.UNAVAILABLE
        assert result.value is None
        assert result.reason == UnavailableReason.MAR_NOT_CONFIGURED.value
```

```bash
.venv/bin/pytest tests/unit/test_mar_policy.py -q
# 预期：ModuleNotFoundError: No module named 'fip.strategy_library.threshold'
```

- [ ] **Step 4: 实现 MAR 三模式（P2-22 / P2-23 / P2-26）**

```python
# src/fip/strategy_library/threshold/mar.py
"""MAR（Minimum Acceptable Return）解析。

MAR 是【评价标准】不是市场数据（FE:429）：即使数值等于 R_f 也必须独立建模，
否则评价标准的变更会伪装成数据更新而绕过版本治理（FE:747 / C-7）。
因此本模块与 R_f 的解析【不共用任何字段】，只在 RISK_FREE 模式下把 R_f
序列作为入参接进来。

── P2-22：三模式统一产出逐期序列 ──

契约的出口是 `FactorInput.mar_daily: tuple[Decimal, ...] | None`，与收益率
序列 1:1 对齐。RISK_FREE 模式下 MAR 本来就是逐期变动的，用一个标量装它
只能取均值/首值/末值 —— 那是在伪造一个从未被决策过的标尺，与 Plan-1 在
adjusted_nav 标量列上栽的是同一个跟头（标量副本装不下二元函数）。
统一成序列之后，消费方【不分支】：因子函数里不该出现
`if mar is scalar ... else ...`，那种分支迟早会在某一种模式下写错，
而写错的表现是一个看起来完全正常的 Sortino。
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fip.strategy_library.factor.status import UnavailableReason

# P2-26：年化 → 逐期的折算口径。值本身来自 config/policy/evaluation/v1.yaml
# （strategy_library 不读 YAML，SDL-1），这里只是把默认参数写成具名常量，
# 生产装配路径一律由 ThresholdResolver 显式传入配置值。
SIMPLE_DIVISION = "SIMPLE_DIVISION"
DEFAULT_PERIODS_PER_YEAR = 252


class MarPolicy(StrEnum):
    """三模式（FE:464-468）。

    P2-23：第三种模式叫 **CUSTOM**，逐字取自上游 `01-fund-evaluation.md` §16.3。
    起草期曾写作 `FIXED`，**已裁定作废** —— 这个字符串会进
    evaluation_policy_version 的可复现链路，改名要带一次数据迁移，
    所以在第一次落库之前就定死。
    """

    ZERO = "ZERO"
    CUSTOM = "CUSTOM"
    RISK_FREE = "RISK_FREE"


@dataclass(frozen=True, slots=True)
class MarResolution:
    """解析结果 —— 【中间形态】，不是喂给因子的形状。

    annualized 与 series 互斥：ZERO / CUSTOM 下配置给的是一个标量口径值，
    RISK_FREE 下给的是一条随时间变化的曲线（FE:483-498）。保留这个区分是为了
    溯源（落 `risk_free_rate_ref` 时要答得出「用的是哪条曲线的哪一天」）；
    喂给因子之前一律经 `mar_daily_series()` 折算成逐期序列（P2-22）。

    quotation_basis 仅 CUSTOM 模式有值：它声明配置里那个数字是什么口径
    （年化 / 月度 / …）。「MAR = 3%」不说口径，折算到逐期会差 12 倍，
    而 Sortino 照样算得出一个看起来正常的数 —— 这正是必填它的理由（P2-23）。
    """

    policy: MarPolicy | None
    annualized: Decimal | None
    series: tuple[tuple[dt.date, Decimal], ...] | None
    quotation_basis: str | None
    unavailable_reason: str | None


def resolve_mar(
    policy_name: str | None,
    custom_value: Decimal | None,
    mar_quotation_basis: str | None,
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
        return MarResolution(None, None, None, None,
                             UnavailableReason.MAR_NOT_CONFIGURED.value)
    try:
        policy = MarPolicy(policy_name)
    except ValueError:
        raise ValueError(
            f"未登记的 mar_policy：{policy_name!r}；合法值为 "
            f"{[p.value for p in MarPolicy]}"
        ) from None

    if policy is MarPolicy.ZERO:
        return MarResolution(policy, Decimal(0), None, None, None)

    if policy is MarPolicy.CUSTOM:
        if custom_value is None:
            raise ValueError("mar_policy = CUSTOM 时 mar.custom_value 必填（FE:456）")
        if not mar_quotation_basis:
            raise ValueError(
                "mar_policy = CUSTOM 时 mar_quotation_basis 必填（P2-23）："
                "不声明口径就无法把它折算到逐期，而错了 12 倍的 MAR "
                "照样能算出一个看起来正常的 Sortino"
            )
        return MarResolution(policy, custom_value, None, mar_quotation_basis, None)

    if not risk_free_series:
        return MarResolution(policy, None, None, None,
                             UnavailableReason.RISK_FREE_RATE_UNAVAILABLE.value)
    return MarResolution(policy, None, tuple(risk_free_series), None, None)


def mar_daily_series(
    res: MarResolution,
    period_dates: Sequence[dt.date],
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> tuple[Decimal, ...] | None:
    """把解析结果折算成【与收益率序列 1:1 对齐】的逐期 MAR（P2-22 的出口）。

    period_dates 是收益率序列每一期对应的日期（长度 = len(returns)）。
    返回值要么长度与它完全相同，要么是 None —— 【没有第三种形态】。
    长度不等会被 FactorInput.__post_init__ 拒收。

    None 的两种来源都是「不知道」而非「是零」：mar_policy 未配置，
    或 RISK_FREE 模式下某一期的 R_f 缺失。**缺一期就补 0 等于宣称那一天的
    门槛是零收益**，而那正是 G-3 禁止的填充。

    ZERO 模式返回全零序列，这【不是】填充：mar_policy = ZERO 是一次显式决策，
    它的逐期取值本来就是 0。区别不在数值而在有没有人做过这个决策（FE:481）。
    """
    if res.unavailable_reason is not None:
        return None

    n = len(period_dates)

    if res.policy is MarPolicy.ZERO:
        return (Decimal(0),) * n

    if res.policy is MarPolicy.CUSTOM:
        # P2-26 SIMPLE_DIVISION：年化值 / periods_per_year。
        # quotation_basis 目前只登记 ANNUALIZED 一种；出现其它口径时
        # 必须在这里显式加分支，【不得】沉默地当成年化。
        if res.quotation_basis != "ANNUALIZED":
            raise ValueError(
                f"未登记的 mar_quotation_basis：{res.quotation_basis!r}"
            )
        per_period = res.annualized / periods_per_year
        return (per_period,) * n

    # RISK_FREE：逐日取当日 R_f，再按同一口径折算。
    by_date = dict(res.series or ())
    out: list[Decimal] = []
    for d in period_dates:
        rate = by_date.get(d)
        if rate is None:
            return None          # 缺一期则整段不可用，绝不补零
        out.append(rate / periods_per_year)
    return tuple(out)
```

```bash
.venv/bin/pytest tests/unit/test_mar_policy.py -q   # 预期 17 passed
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
住在 strategy_library/threshold/mar.py。两者【不共用字段】（C-7）。
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from collections.abc import Sequence

from fip.strategy_library.threshold.mar import (
    MarPolicy,
    mar_daily_series,
    resolve_mar,
)
from fip.platform.config.loader import ConfigSet
from fip.platform.decision_data.pit import RiskFreeRatePitRepository
from fip.strategy_library.factor.status import UnavailableReason


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
    # P2-22：mar_daily 是逐期序列，直接就是 FactorInput.mar_daily。
    # 起草期这里是标量 `mar: Decimal | None`，而那装不下 RISK_FREE 模式的
    # MAR 曲线 —— 取均值/首值/末值都是伪造一个从未被决策过的标尺。
    risk_free_rate: Decimal | None
    risk_free_rate_ref: RiskFreeRateRef | None
    mar_daily: tuple[Decimal, ...] | None
    mar_unavailable_reason: str | None
    mar_policy: MarPolicy | None


class ThresholdResolver:
    def __init__(self, rates: RiskFreeRatePitRepository, config: ConfigSet) -> None:
        self._rates = rates
        self._config = config

    def resolve(
        self, base_currency: str, date_from: dt.date, date_to: dt.date,
        period_dates: Sequence[dt.date],
    ) -> ResolvedThresholds:
        """解析某只基金在本次决策下的 R_f 与逐期 MAR。

        period_dates 是收益率序列每一期对应的日期（长度 = 净值点数 − 1）。
        产出的 mar_daily 与它 1:1 对齐（P2-22），消费方不分支。

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
            custom_value = Decimal(str(self._config.get("mar.custom_value")))
        except KeyError:
            custom_value = None
        try:
            quotation_basis = str(self._config.get("mar.mar_quotation_basis"))
        except KeyError:
            # P2-23：CUSTOM 模式下缺它会由 resolve_mar 响亮失败 —— 不在这里兜底。
            quotation_basis = None

        rf_series = (
            [(p.effective_at, p.rate)
             for p in self._rates.rate_series(
                 curve_code, base_currency, tenor, date_from, date_to)]
            if policy_name == MarPolicy.RISK_FREE.value else None
        )
        mar_resolution = resolve_mar(
            policy_name or None, custom_value, quotation_basis, rf_series
        )
        # P2-26：折算口径与期数取自配置，【不】用函数默认值 —— 默认值一旦与
        # 配置分叉，因子值会静默改变而 metric_version 不动。
        periods_per_year = int(self._config.get("mar.periods_per_year"))
        mar_daily = mar_daily_series(
            mar_resolution, period_dates, periods_per_year=periods_per_year
        )
        mar_reason = mar_resolution.unavailable_reason
        if mar_daily is None and mar_reason is None:
            # RISK_FREE 模式下窗口内某一期的 R_f 缺失。绝不补零（G-3）。
            mar_reason = UnavailableReason.MAR_SERIES_INCOMPLETE.value

        return ResolvedThresholds(
            risk_free_rate=rf, risk_free_rate_ref=ref,
            mar_daily=mar_daily, mar_unavailable_reason=mar_reason,
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
    period_dates = [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]
    resolved = resolver.resolve(
        "CNY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), period_dates
    )
    assert resolved.risk_free_rate == Decimal("0.02200000")
    assert resolved.mar_daily is None          # P2-22：序列，不是标量
    assert resolved.mar_unavailable_reason == "MAR_NOT_CONFIGURED"


def test_未配置_MAR_时两个依赖因子在端到端链路上_UNAVAILABLE(db_session, tmp_path):
    """P2-4 的验收断言：G-6 说的不只是「解析不出 MAR」，而是
    「F-RISK-002 / F-RAP-002 一律 UNAVAILABLE」。这条把后半句钉住。"""
    from fip.strategy_library.factor.compute import compute_factor
    from fip.strategy_library.factor.status import FactorStatus

    inp = _factor_input(mar_daily=None)        # 上一条测试解析出的形状
                                               # （夹具见 tests/unit/test_mar_policy.py，
                                               #   本文件里复用同一构造）
    for factor_id in ("F-RISK-002", "F-RAP-002"):
        result = compute_factor(factor_id, inp)
        assert result.status is FactorStatus.UNAVAILABLE
        assert result.value is None
        assert result.reason == "MAR_NOT_CONFIGURED"


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
    ref = resolver.resolve(
        "CNY", dt.date(2024, 1, 1), dt.date(2024, 1, 31),
        [dt.date(2024, 1, 2), dt.date(2024, 1, 3)],
    ).risk_free_rate_ref
    # P2-30：curve_code 是【第五个】必备字段。中债同一天三条曲线，
    # 缺它则溯源答不出「用的是哪条曲线」（实测信用债 10Y 高约 30bp）。
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
不回退 ZERO（G-6），并断言 F-RISK-002 / F-RAP-002 在端到端链路上一律
UNAVAILABLE（P2-4）。P2-22：三种模式统一产出与收益率序列 1:1 对齐的
逐期 mar_daily，消费方不分支，RISK_FREE 在 M1 因此【可用】而非缺口；
缺某一期的 R_f 时整段 MAR_SERIES_INCOMPLETE，绝不补零（G-3）。
P2-23：第三模式逐字取上游的 CUSTOM（不是 FIXED），且必填 mar_quotation_basis。
P2-30：risk_free_rate_ref 补第五字段 curve_code；适配器层补 CURVE_CURRENCIES
（中债三条曲线均为 CNY），补上 ParsedYieldPoint 不带 currency 的空档。
删除 config/policy/evaluation 里被禁止的 mar.default 兜底项（P2-4）。"
```

---

### Task 11: Peer Group 构建 + B1 快照原子写入

**Files:**

- Create: `db/migrations/versions/0020_share_class_base_currency.py`
- Create: `src/fip/strategy_library/peer_group/__init__.py`
- Create: `src/fip/strategy_library/peer_group/build.py`
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
# fip.strategy_library.peer_group.build（纯函数；G-5：不得 import 评分 / Universe）
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
    def __init__(self, session: Session, *, classification_level: str,
                 classification_policy_version: str, peer_group_policy_version: str,
                 code_version: str) -> None        # 【PF-7】四个 NOT NULL 列
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
    # P2-27 逐字钉死这个取值：它是【声明的推导规则】的名字，不是供应商给的事实。
    # 换成 "CNY" 之外的任何默认、或换掉这个 source 串，都必须先改设计定案。
    assert row.base_currency_source == "DECLARED_RULE_ALL_AKSHARE_CNY"
```

```bash
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration
# 预期：AttributeError: type object 'FundShareClass' has no attribute 'base_currency'
```

- [ ] **Step 2: 迁移 0020 + ORM + 灌数时如实写入来源**

```python
# db/migrations/versions/0020_share_class_base_currency.py
"""份额类别的计价币种

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"


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
# DECLARED_RULE_ALL_AKSHARE_CNY 而不是 PROVIDER_REPORTED（P2-27）。引入第二个 provider 或
# 第一只外币计价份额之前，必须把它换成真实字段。
BASE_CURRENCY_BY_PROVIDER_SCOPE = {"AKSHARE": ("CNY", "DECLARED_RULE_ALL_AKSHARE_CNY")}
...
currency, currency_source = BASE_CURRENCY_BY_PROVIDER_SCOPE[self._adapter.provider_code]
share_class = FundShareClass(
    ..., base_currency=currency, base_currency_source=currency_source
)
```

**G-14：这条推导规则必须在配置里标 `PROVISIONAL`。** 追加到
`config/policy/evaluation/v1.yaml`（与 `peer_group` 段同级）：

```yaml
base_currency:
  derivation_rule:
    value: DECLARED_RULE_ALL_AKSHARE_CNY
    status: PROVISIONAL
    source: "Plan-2 设计定案 P2-27 —— AKShare 的 fund_name_em 不提供币种；全部 AKShare 场外基金以 CNY 计价（QDII 投向海外但份额仍以 CNY 申赎）。这是【声明】不是【观测】，引入第二个 provider 或第一只外币份额前必须换成真实字段"
```

并加一条测试把「值 + 来源 + PROVISIONAL」三者绑在一起：

```python
def test_币种推导规则标为_PROVISIONAL_且与写入值一致():
    """G-14：【补齐】项必须标 PROVISIONAL 并指向设计定案文档。

    只断言 base_currency == "CNY" 是不够的 —— 那条断言在「有人把它改成
    从数据里读」之后依然为真，而 PROVISIONAL 标记会随之失效却没人发现。
    """
    cfg = _cfg()
    param = cfg.parameters["base_currency.derivation_rule"]
    assert param.status.value == "PROVISIONAL"
    assert "P2-27" in param.source
    assert cfg.get("base_currency.derivation_rule") == (
        BASE_CURRENCY_BY_PROVIDER_SCOPE["AKSHARE"][1]
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

from fip.strategy_library.peer_group.build import (
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
# 预期：ModuleNotFoundError: No module named 'fip.strategy_library.peer_group'
```

- [ ] **Step 4: 实现 Peer Group 构建**

```python
# src/fip/strategy_library/peer_group/build.py
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

- [ ] **Step 5: 改写 C-4 的两条适应度测试（P2-2，先证伪）——【不做这一步视为本任务未完成】**

**这是 P2-2 点名的必做项。** Plan-1 留下的两条 C-4 测试都建立在错误前提上：

| 现状（`tests/fitness/test_architecture.py`） | 问题 |
|---|---|
| `test_peer_group_module_does_not_depend_on_scoring_or_universe` 扫 `src/fip/services/fund_service/peer_group`，禁的前缀是 `fip.services.fund_service.{scoring,ranking,universe}` | 按分层，Peer Group 与 score / ranking / universe **全都属 Strategy Library**。扫的目录**永远不会存在** |
| `test_peer_group_guard_is_visible_not_silent`（第 515-541 行）写着「该模块要到 **Plan-3（M1.5）** 才会创建」 | **前提是错的**：spec §0.3 明定 M1.2 Peer Group 属 **Plan-2**，M1.5（组合与决策）才是 Plan-3 |

照原样做下去的后果：本任务建完 Peer Group 之后，C-4 仍扫一个空目录恒真、
守卫仍 `skip` —— **G-5 在整个 Plan-2 静默缺席**，与 D-4 指责 SB-1「静默缺席」
是同一种病。

```python
# tests/fitness/test_architecture.py（改）

# ① C-4 检查的扫描根改为【真实位置】，禁用前缀改为 strategy_library 下的三个包
def test_peer_group_module_does_not_depend_on_scoring_or_universe():
    """C-4 / G-5 / FR-PEER-001：Peer Group 的构成不得依赖 Fund Score 或
    Fund Universe。违反会形成 Score → Universe → Peer Group → Score 的循环
    依赖 —— 它不会报错，只会让每次重算得到不同的排名。

    ⚠️ P2-2：扫描根从 services/fund_service/peer_group 改为
    strategy_library/peer_group。按分层，Peer Group 与 score / ranking /
    universe 同属 Strategy Library；原来的路径永远不会存在，那条检查是
    100% vacuous 的。
    """
    forbidden = (
        "fip.strategy_library.score",
        "fip.strategy_library.ranking",
        "fip.strategy_library.universe",
        "fip.services.fund_service",
        "fip.services.factor_service",
    )
    offenders = []
    for f in _py_files("strategy_library", "peer_group"):
        for module in _dotted_imports(f):
            if any(_touches(module, prefix) for prefix in forbidden):
                offenders.append((f.name, module))
    assert not offenders, f"Peer Group 出现对评分/Universe 的依赖：{offenders}"


# ② 【被扫目录必须存在】——把上一条从「空洞成立」变成「真的在查东西」
def test_peer_group_scanned_root_exists():
    """P2-2 明确要求的一条断言。

    `_py_files` 对不存在的目录返回 `[]`，于是上一条的 `assert not []` 恒真。
    这正是 Plan-1 的教训之二：比没有测试更坏的，是一条自称 oracle、
    实际恒真的测试。

    它替代了被删除的 test_peer_group_guard_is_visible_not_silent ——
    那条守卫用「可见的 skip」表达「模块还没建」，而 M1.2 就在 Plan-2，
    模块【现在】就该存在，所以正确的形式是硬断言而不是 skip。
    """
    assert _py_files("strategy_library", "peer_group"), (
        "strategy_library/peer_group 不存在 —— C-4 检查会静默恒真"
    )


# ③ GUARDED_ROOTS 追加一项（现有为 ("strategy_library",) / ("quant_engine",) /
#    ("services","portfolio_service") / ("platform",)）：
#       ("strategy_library", "peer_group"),
#    并把 test_scanned_roots_exist 的 docstring 里「peer_group 除外，见下方
#    独立的可见 skip 占位测试」那句删掉 —— 占位测试已经不存在了。
#
# ④ 【删除】test_peer_group_guard_is_visible_not_silent（第 515-541 行）
#    连同它的 docstring。它的前提「该模块要到 Plan-3（M1.5）才会创建」是错的
#    （spec §0.3：M1.2 属 Plan-2），且它 pytest.fail 的条件是
#    services/fund_service/peer_group 出现 —— 一个本 Plan 永远不会创建的路径。
#    留着它等于留一条永远 skip 的测试假装 C-4 有人看着。
```

**先证伪（G-18，P2-2 逐字要求「Peer Group 建好后故意 import 评分模块，
确认 C-4 会红」）**：

第一步，在建 `peer_group` 之前先跑，确认新加的存在性断言是红的：

```bash
.venv/bin/pytest tests/fitness/test_architecture.py -k peer_group -v
# 预期：test_peer_group_scanned_root_exists FAILED
#       AssertionError: strategy_library/peer_group 不存在 —— C-4 检查会静默恒真
```

这一条恰好证明了改造前的 C-4 是恒真的。

第二步，建好 `peer_group/build.py` 之后，在文件末尾**临时**追加：

```python
def _probe():  # 临时：证伪 C-4
    from fip.strategy_library.score import subscore  # noqa: F401
```

再跑：

```bash
.venv/bin/pytest tests/fitness/test_architecture.py -k peer_group -v
# 预期：test_peer_group_module_does_not_depend_on_scoring_or_universe FAILED
#       AssertionError: Peer Group 出现对评分/Universe 的依赖：
#       [('build.py', 'fip.strategy_library.score.subscore')]
```

然后还原：`git checkout -- src/fip/strategy_library/peer_group/build.py`。

⚠️ 两段红灯输出**都要**进任务报告。只跑第二段不足以证明改造有效——
改造前那条检查即使被 import 命中也扫不到文件（根本没扫这个目录）。

- [ ] **Step 6: 分类的 PIT 读取 + B1 原子写入（失败测试先行）**

```python
# tests/integration/test_peer_group_snapshot.py（追加）
import datetime as dt

from fip.strategy_library.peer_group.build import (
    ClassificationLevel, build_peer_groups,
)
from fip.services.data_service.models.evaluation import (
    PeerGroupMember, PeerGroupSnapshot,
)
from fip.services.data_service.repositories.classification import (
    SqlClassificationPitRepository,
)
from fip.services.fund_service.peer_group_writer import PeerGroupSnapshotWriter


def _writer(session) -> PeerGroupSnapshotWriter:
    """【Ruling PF-7】四个「本次用了哪一版」的 NOT NULL 列在构造期注入。

    起草期的写入方一个都没传，flush 会 IntegrityError；同时
    `peer_group_size=` 已改为 Task 8 的列名 `member_count=`。
    """
    return PeerGroupSnapshotWriter(
        session,
        classification_level="L1",
        classification_policy_version="cls-v1",
        peer_group_policy_version="pgp-v1",
        code_version="0.1.0+gtest",
    )


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
    written = _writer(db_session).write_b1(dt.date(2026, 9, 1), build)
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
        _writer(db_session).write_b1(dt.date(2026, 9, 1), broken)
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
    writer = _writer(db_session)
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
    _writer(db_session).write_b1(dt.date(2026, 9, 1), build)
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

from fip.strategy_library.peer_group.build import PeerGroupCandidate

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

from fip.strategy_library.peer_group.build import PeerGroupBuild
from fip.services.data_service.models.evaluation import (
    PeerGroupMember,
    PeerGroupSnapshot,
)


class PeerGroupSnapshotWriter:
    def __init__(
        self,
        session: Session,
        *,
        classification_level: str,
        classification_policy_version: str,
        peer_group_policy_version: str,
        code_version: str,
    ) -> None:
        # 四个都是 peer_group_snapshot 的 NOT NULL 列，且都是「本次用了哪一版」
        # 的记录。构造期注入而不是写入时现编 —— D-7 明写 classification_level
        # 不得硬编码（它来自配置 peer_group.classification_level）。
        self._session = session
        self._classification_level = classification_level
        self._classification_policy_version = classification_policy_version
        self._peer_group_policy_version = peer_group_policy_version
        self._code_version = code_version

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
                    # 【Ruling PF-7】列名以 Task 8 建的表为准：member_count，
                    # 不是起草期的 peer_group_size。
                    member_count=len(member_ids),
                    # 以下三列 Task 8 建的都是 NOT NULL，起草期漏传 ——
                    # 「这个快照当时用的是哪一层 / 哪一版政策 / 哪一版代码」，
                    # 都是结果不是参数，由调用方从上下文传入，不得现编。
                    classification_level=self._classification_level,
                    classification_policy_version=self._classification_policy_version,
                    peer_group_policy_version=self._peer_group_policy_version,
                    code_version=self._code_version,
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

> ## ✅ 【冲突 ⑦ 已按 Ruling PF-7 裁定解决】本段写入代码与 Task 8 的建表已对齐
>
> `PeerGroupSnapshot` / `PeerGroupMember` 的列由 **Task 8** 建（迁移 0019）。
> 起草期两处对不上，写入会直接 `TypeError`。裁定与落实结果：
>
> | 起草期本段写的 | 裁定后 | 归属 |
> |---|---|---|
> | `classification_history_ids` | 不变（`ARRAY(BigInteger)`, NOT NULL） | ✅ P2-25 已补 |
> | `peer_group_size=` | **改为 `member_count=`**（统一用 Task 8 的列名） | 改写入方 |
> | `classification_key=` | **保留** —— 反过来给 Task 8 **加这一列** | 改建表 |
> | （缺 4 个 NOT NULL 列） | 补 `classification_level` / `classification_policy_version` / `peer_group_policy_version` / `code_version`，由构造期注入 | 改写入方 |
>
> `classification_key` 是 Peer Group 的【身份】，不存则快照无法自解释；
> Task 8 起草期担心的「第二份真值」由 Task 8 新增的
> `ck_peer_group_classification_key` 按住 —— 它断言该列逐字等于
> `classification_scheme || '|' || classification_code || '|' || base_currency`。
> 迁移 0019 与 CHECK 黄金快照（G-17）随之要重新生成。

```bash
.venv/bin/pytest tests/integration/test_peer_group_snapshot.py -q -m integration   # 预期 6 passed
.venv/bin/pytest tests/fitness -q
.venv/bin/ruff check src tests && make typecheck
git add -A && git commit -m "feat(peer-group): Fund Classification × Currency 分组与 B1 原子快照

新增 fund_share_class.base_currency + base_currency_source（迁移 0020）——
FR:116 要求分组维度与 R_f 解析键取自同一字段，Plan-1 未建该列。
币种由【声明的推导规则】填入并如实记录来源，不写 NOT NULL 兜底。
UNCLASSIFIED / 无分类 / 无币种三种排除原因分开登记（D-6）。
G-5 的适应度检查改扫 strategy_library/peer_group，并补一条
『被扫目录必须存在』断言 —— 原检查在目录不存在时恒真。"
```

---

### Task 12: 因子标准化（Peer Group 内 Percentile Rank + 方向转换）

> ✅ **【冲突 ①② 已按 Ruling PF-1 / PF-2 裁定解决】**
> - **① PF-1**：`normalize_peer_group` 的签名统一为
>   `(entries: Sequence[tuple[int, FactorResult]], direction, min_peer_group_size)
>   -> list[NormalizedFactorValue]` —— 输入取【最富的形态】（保留 `status` 与
>   `reason`），产出仍是横截面视图。入参若退化成 `Decimal | None` 就丢掉了
>   reason，下游便无法回答「为什么这只基金的这个因子没参与」，而那正是
>   D-23 / 归因链要求的。
>   **本函数是 G-8 三元组（rank / n_effective / percentile）的唯一权威产出点**，
>   Task 15 与 Task 17 一律消费它；Task 17 起草期那条直接调 `percentile_rank`
>   的路径已删除（三样都不产出，落库会是空的）。
> - **② PF-2**：`NormalizedFactorValue` 与 `NormalizedFactor` **两个都保留** ——
>   它们不是重复，是同一份计算的两个【视图】（横截面 vs 归因）。缺的不是
>   「合并」而是【转置】，因此本任务补一个 `transpose_to_fund_view`。
>   Task 17 **不得**自己构造 `NormalizedFactor`，必须消费转置结果。

**Files:**

- Create: `src/fip/strategy_library/factor/normalize.py`
- Modify: `src/fip/strategy_library/peer_group/build.py`（加一个配置路径常量）
- Modify: `tests/fitness/test_architecture.py`
- Test: `tests/unit/test_factor_normalize.py`
- Test: `tests/fitness/test_single_config_source.py`

**Interfaces:**

*Consumes*：

```python
from fip.strategy_library.factor.definitions import PreferenceDirection   # Task 9
from fip.strategy_library.factor.status import FactorStatus               # Task 9
from fip.strategy_library.factor.compute import FactorResult              # Task 9
from fip.strategy_library.score.attribution import NormalizedFactor       # Task 14
#   ⚠️ Task 14 依赖 Task 13 依赖本任务 —— 环由【运行顺序】而不是 import 打破：
#   NormalizedFactor 是一个无行为的 frozen dataclass，Task 14 的实现者先
#   把它单独落在 score/attribution.py 里（该模块本身只 import definitions /
#   status），本任务再 import 它。若实现时发现真的构成 import 环，
#   把 NormalizedFactor 上移到 strategy_library/factor/types.py，两边都从那里取。
```

*Produces*：

```python
# fip.strategy_library.factor.normalize
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
    """【横截面视图】。PF-1：status 与 reason 原样透传，不得在这一层丢掉。"""
    share_class_id: int
    factor_id: str
    raw_value: Decimal | None
    rank: int | None
    n_effective: int
    percentile: Decimal | None
    cross_section_status: CrossSectionStatus
    factor_status: FactorStatus
    reason: str
    direction: PreferenceDirection

def normalize_peer_group(
    entries: Sequence[tuple[int, FactorResult]],
    direction: PreferenceDirection,
    min_peer_group_size: int,
) -> list[NormalizedFactorValue]

def transpose_to_fund_view(
    by_factor: Mapping[str, Sequence[NormalizedFactorValue]],
    *,
    window: str,
) -> dict[int, dict[str, NormalizedFactor]]

# fip.strategy_library.peer_group.build（追加）
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

from fip.strategy_library.factor.compute import FactorResult
from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.normalize import (
    CrossSectionStatus,
    competition_ranks,
    normalize_peer_group,
    percentile_rank,
    transpose_to_fund_view,
)
from fip.strategy_library.factor.status import FactorStatus

D = Decimal
HIGH = PreferenceDirection.HIGHER_IS_BETTER
LOW = PreferenceDirection.LOWER_IS_BETTER
FID = "F-RAP-001"


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

def _ok(value: Decimal) -> FactorResult:
    return FactorResult(factor_id=FID, value=value, status=FactorStatus.VALID,
                        reason="", observation_count=252, quality_flag="INFERRED")


def _na(reason: str = "ZERO_VOLATILITY") -> FactorResult:
    """PF-1：入参是 FactorResult 而不是 `Decimal | None` —— 正是为了让这个
    reason 活到输出里。用 `Decimal | None` 的话它在函数入口就没了。"""
    return FactorResult(factor_id=FID, value=None, status=FactorStatus.UNAVAILABLE,
                        reason=reason, observation_count=0, quality_flag="INFERRED")


def _entries(n_valid: int, n_missing: int = 0):
    entries = [(i, _ok(D(1000 - i))) for i in range(n_valid)]
    entries += [(1000 + i, _na()) for i in range(n_missing)]
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
    assert all(o.cross_section_status is CrossSectionStatus.INSUFFICIENT_SAMPLE
               for o in out)
    assert all(o.percentile is None and o.rank is None for o in out)
    assert {o.n_effective for o in out} == {25}   # FR:356：仍须返回，调用方要知道差多少


def test_恰好达到阈值时正常产出():
    out = normalize_peer_group(_entries(30), HIGH, 30)
    assert all(o.cross_section_status is CrossSectionStatus.NORMAL for o in out)
    assert max(o.percentile for o in out) == D("100.00000000")


def test_INSUFFICIENT_SAMPLE_不是错误状态且每个成员都有一行():
    """FR:358 + BLOCK-12 的 CHECK：INSUFFICIENT_SAMPLE 的行仍然落库。
    不落库会让历史查询无法区分『当时样本不足』与『当时根本没算』。"""
    out = normalize_peer_group(_entries(3), HIGH, 30)
    assert len(out) == 3


def test_输出顺序与输入顺序一致():
    """G-2：调用方按 share_class_id 对齐结果，顺序漂移会静默错位。"""
    entries = [(9, _ok(D(1))), (3, _ok(D(3))), (7, _ok(D(2)))]
    assert [o.share_class_id for o in normalize_peer_group(entries, HIGH, 1)] == [9, 3, 7]


# ---- PF-1：status 与 reason 必须活到输出里 --------------------------------

def test_不可算成员的_reason_被原样透传():
    """Ruling PF-1 的判据。入参若是 `(share_class_id, Decimal | None)`，
    「为什么这只基金的这个因子没参与」在函数入口就丢了 —— 而 D-23 的归因链
    要求答得出这个问题。本条测试就是那条签名裁定的可执行形式。"""
    entries = [(1, _ok(D(10))), (2, _na("MAR_NOT_CONFIGURED"))]
    by_id = {o.share_class_id: o for o in normalize_peer_group(entries, HIGH, 1)}
    assert by_id[2].reason == "MAR_NOT_CONFIGURED"
    assert by_id[2].factor_status is FactorStatus.UNAVAILABLE
    assert by_id[2].percentile is None and by_id[2].rank is None
    # 可算的那只：reason 为空，raw_value 原样带出（归因要 raw 与 normalized 并列）
    assert by_id[1].reason == "" and by_id[1].raw_value == D(10)


def test_三元组由本函数产出_而不是调用方各自再算一遍():
    """G-8 + PF-1：rank / n_effective / percentile 三者的唯一权威产出点。"""
    out = normalize_peer_group(_entries(3), HIGH, 1)
    assert [(o.rank, o.n_effective) for o in out] == [(1, 3), (2, 3), (3, 3)]
    assert all(o.percentile is not None for o in out)


# ---- PF-2：转置 ------------------------------------------------------------

def test_转置把横截面视图翻成归因视图():
    """Ruling PF-2：两个类型都保留，缺的是转置。

    横截面视图按 factor_id 分桶（一个因子、多只基金），归因视图按
    share_class_id 分桶（一只基金、多个因子）。评分与归因需要后者。
    """
    a = normalize_peer_group([(1, _ok(D(10))), (2, _ok(D(20)))], HIGH, 1)
    b = normalize_peer_group([(1, _ok(D(5))), (2, _na("ZERO_VOLATILITY"))], LOW, 1)
    view = transpose_to_fund_view({"F-RET-001": a, "F-RISK-001": b}, window="3Y")

    assert set(view) == {1, 2}
    assert set(view[1]) == {"F-RET-001", "F-RISK-001"}
    assert view[1]["F-RET-001"].window == "3Y"
    assert view[1]["F-RET-001"].normalized_score == D("0.00000000")   # 10 < 20，HIGH
    assert view[2]["F-RISK-001"].normalized_score is None
    assert view[2]["F-RISK-001"].status is FactorStatus.UNAVAILABLE
    assert view[2]["F-RISK-001"].reason == "ZERO_VOLATILITY"
    assert view[2]["F-RISK-001"].direction is LOW


def test_转置不得凭空补齐缺失的基金():
    """某个因子只覆盖了一部分成员时，转置【不得】给其余成员编一个 0 或 50
    （G-3）。缺就是缺 —— 补齐是 Task 14 按 declared_factors 显式做的事，
    它在那里会带上 exclusion_reason，而不是在转置里静默发生。"""
    a = normalize_peer_group([(1, _ok(D(10)))], HIGH, 1)
    b = normalize_peer_group([(2, _ok(D(20)))], HIGH, 1)
    view = transpose_to_fund_view({"F-RET-001": a, "F-RET-002": b}, window="3Y")
    assert set(view[1]) == {"F-RET-001"}
    assert set(view[2]) == {"F-RET-002"}
```

```bash
.venv/bin/pytest tests/unit/test_factor_normalize.py -q
# 预期：ModuleNotFoundError: ...factor.normalize
```

- [ ] **Step 2: 实现 `normalize.py`**

```python
# src/fip/strategy_library/factor/normalize.py
"""Peer Group 内的 Percentile Rank 与方向转换（设计定案 D-11）。

方法已定案（FS:216 / BR:1016）：Percentile Rank / Peer Group 内排名。
「这不是 TBD」（FS:225）——未来若引入 Z-Score 或 Min-Max，属 Scoring Version 的
Major 变更。第一阶段【不做异常值处理】：Percentile Rank 对极值不敏感；
若改用 Z-Score，异常值处理会成为必需项，那是方法选择的连带后果，不可分开决策。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum

from fip.strategy_library.factor.compute import FactorResult
from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import NormalizedFactor

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


# 参与横截面计算的两个 status。INVALID / UNAVAILABLE 一律不参与（G-3）。
_PARTICIPATING = (FactorStatus.VALID, FactorStatus.WARNING)


@dataclass(frozen=True, slots=True)
class NormalizedFactorValue:
    """【横截面视图】一个因子、多只基金。G-8：Rank / n_effective / Percentile
    三者都必须落库 —— 只存 Rank 则历史分位不可还原；只存 Percentile 则
    「差多少」不可见。peer_group_size 由调用方另行落库（它是快照的属性，
    不是本函数的输入）。

    【Ruling PF-1】factor_status / reason / raw_value / direction 原样透传自
    入参的 FactorResult。它们不参与任何计算，只是不许在这一层丢掉 ——
    丢了下游就答不出「为什么这只基金的这个因子没参与」（D-23 归因链）。

    ⚠️ 横截面状态叫 cross_section_status，【不叫】status：本类型上同时有
    「这只基金在组里算不算得出分位」（CrossSectionStatus）与「这个因子本身
    算不算得出来」（FactorStatus）两个正交的状态，一个 status 装不下两件事。
    """

    share_class_id: int
    factor_id: str
    raw_value: Decimal | None
    rank: int | None
    n_effective: int
    percentile: Decimal | None
    cross_section_status: CrossSectionStatus
    factor_status: FactorStatus
    reason: str
    direction: PreferenceDirection


def normalize_peer_group(
    entries: Sequence[tuple[int, FactorResult]],
    direction: PreferenceDirection,
    min_peer_group_size: int,
) -> list[NormalizedFactorValue]:
    """对一个 Peer Group 内某一个因子做标准化。

    【本函数是 G-8 三元组（rank / n_effective / percentile）的唯一权威产出点】
    （Ruling PF-1）。Task 15 与 Task 17 一律消费它，不得各自再算一遍；
    尤其【不得】绕过它直接调 percentile_rank —— 那条路 rank 与 n_effective
    一个都不产出，落库会是空的，而 G-8 要求三者都落库。

    entries 是 (share_class_id, FactorResult)。status 不在 (VALID, WARNING)
    或 value 为 None 的成员【不参与】分位计算，也【不得】被当作最差值参与
    排名（FS:250）。把它当最差值等于宣称「数据不足 = 表现最差」。

    入参之所以是 FactorResult 而不是 `Decimal | None`：后者丢掉 reason，
    于是归因链答不出「为什么这只基金的这个因子没参与」（Ruling PF-1）。

    n_effective = 可算的成员数，判定基数就是它而不是组规模（G-7 / BR:542）。
    n_effective < min_peer_group_size 时不做任何横截面派生量，全体标
    INSUFFICIENT_SAMPLE，但 n_effective 仍如实返回 —— 返回 17 与返回 29
    对调用方的含义不同（FR:356）。这不是错误状态（FR:358）。

    返回顺序与 entries 一致。
    """

    def _row(sid: int, res: FactorResult, rank: int | None,
             n_effective: int, percentile: Decimal | None,
             cross: CrossSectionStatus) -> NormalizedFactorValue:
        return NormalizedFactorValue(
            share_class_id=sid,
            factor_id=res.factor_id,
            raw_value=res.value,
            rank=rank,
            n_effective=n_effective,
            percentile=percentile,
            cross_section_status=cross,
            factor_status=res.status,
            reason=res.reason,
            direction=direction,
        )

    participating = [
        (sid, res)
        for sid, res in entries
        if res.status in _PARTICIPATING and res.value is not None
    ]
    n_effective = len(participating)

    if n_effective < min_peer_group_size:
        return [
            _row(sid, res, None, n_effective, None,
                 CrossSectionStatus.INSUFFICIENT_SAMPLE)
            for sid, res in entries
        ]

    values = [res.value for _, res in participating]
    oriented = (
        [-value for value in values]
        if direction is PreferenceDirection.LOWER_IS_BETTER
        else list(values)
    )
    ranks = competition_ranks(oriented)
    percentiles = percentile_rank(values, direction)
    resolved = {
        sid: (rank, percentile)
        for (sid, _), rank, percentile in zip(
            participating, ranks, percentiles, strict=True
        )
    }
    out: list[NormalizedFactorValue] = []
    for sid, res in entries:
        rank, percentile = resolved.get(sid, (None, None))
        out.append(_row(sid, res, rank, n_effective, percentile,
                        CrossSectionStatus.NORMAL))
    return out


def transpose_to_fund_view(
    by_factor: Mapping[str, Sequence[NormalizedFactorValue]],
    *,
    window: str,
) -> dict[int, dict[str, NormalizedFactor]]:
    """【Ruling PF-2】横截面视图 → 归因视图的转置。

    NormalizedFactorValue 与 NormalizedFactor 不是重复，是同一份计算的两个
    【视图】：前者按 share_class_id 组织（一个因子、多只基金 → rank/percentile），
    后者按 factor_id 组织（一只基金、多个因子 → raw/normalized/reason）。
    标准化天然产出前者，评分与归因需要后者 —— 缺的不是「合并」而是转置。

    window 是关键字参数：window 进因子身份（D-13）但【不在】FactorResult 上，
    只有调用方知道本次算的是哪个窗口。

    本函数【不补齐】任何缺失的 (基金, 因子) 组合：某个因子没覆盖到的成员就是
    没有那一行。补齐是 Task 14 按 profile.declared_factors 显式做的事，
    它在那里会带上 exclusion_reason；在这里静默补一个 0 / 50 违反 G-3。
    """
    view: dict[int, dict[str, NormalizedFactor]] = {}
    for factor_id, rows in by_factor.items():
        for row in rows:
            view.setdefault(row.share_class_id, {})[factor_id] = NormalizedFactor(
                factor_id=factor_id,
                window=window,
                raw_value=row.raw_value,
                normalized_score=row.percentile,
                status=row.factor_status,
                direction=row.direction,
                reason=row.reason,
            )
    return view
```

```bash
.venv/bin/pytest tests/unit/test_factor_normalize.py -q   # 预期 15 passed
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
# src/fip/strategy_library/peer_group/build.py（追加）
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

- Create: `src/fip/strategy_library/factor/effectiveness.py`
- Create: `src/fip/services/factor_service/effectiveness_writer.py`
- Create: `config/policy/validation/v1.yaml`
- Test: `tests/unit/test_factor_effectiveness.py`
- Test: `tests/unit/test_validation_config.py`
- Test: `tests/integration/test_factor_effectiveness_writer.py`

**Interfaces:**

*Consumes*：

```python
from fip.quant_engine.correlation import spearman   # Task 3：spearman(xs, ys) -> Decimal
from fip.quant_engine.stats import mean, stdev      # Task 3
from fip.strategy_library.factor.normalize import NormalizedFactorValue   # Task 12
from fip.services.data_service.models.factor import FactorEffectiveness        # Task 7（迁移 0018）
```

*Produces*：

```python
# fip.strategy_library.factor.effectiveness
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

from fip.strategy_library.factor.effectiveness import (
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
# src/fip/strategy_library/factor/effectiveness.py
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

from fip.quant_engine.correlation import spearman
from fip.quant_engine.stats import mean, stdev

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

from fip.strategy_library.factor.effectiveness import (
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

⚠️ 本模块要求 factor_effectiveness 至少有这些列（由 Task 7 的迁移 0018 建）：
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

from fip.strategy_library.factor.effectiveness import EffectivenessResult
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


---

### Task 14: 五子分 + 归因 + Data Completeness

> 依赖 Task 13（因子有效性检验）。本任务全部落在 `strategy_library`，**纯函数**：
> 不碰数据库、不读配置文件、不含 `runtime_mode` 分支（SDL-1 / SDL-2）。
> Profile 与有效性结论都由调用方注入。

**Files:**
- Create: `src/fip/strategy_library/score/__init__.py`
- Create: `src/fip/strategy_library/score/attribution.py`
- Create: `src/fip/strategy_library/score/subscore.py`
- Create: `src/fip/strategy_library/score/completeness.py`
- Test: `tests/unit/test_sub_score.py`
- Test: `tests/unit/test_score_completeness.py`
- Modify: `config/strategy/factor/v1.yaml`（Profile 的因子声明与子分权重）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.factor.status.FactorStatus`（Task 9）
  - `fip.strategy_library.factor.definitions.PreferenceDirection`（Task 9）
- Produces:
  ```python
  # score/attribution.py
  WEIGHT_QUANTUM: Decimal      # Decimal("0.00000001")，与 RatioNumeric(12,8) 对齐
  SCORE_QUANTUM: Decimal       # Decimal("0.00000001")
  RATIO_QUANTUM: Decimal       # Decimal("0.00000001")

  @dataclass(frozen=True, slots=True)
  class NormalizedFactor:
      factor_id: str
      window: str
      raw_value: Decimal | None
      normalized_score: Decimal | None
      status: FactorStatus
      direction: PreferenceDirection
      reason: str

  @dataclass(frozen=True, slots=True)
  class FactorAttribution:
      factor_id: str
      window: str
      raw_value: Decimal | None
      normalized_score: Decimal | None
      direction: PreferenceDirection | None
      weight: Decimal
      weighted_contribution: Decimal | None
      participated: bool
      exclusion_reason: str | None
      effectiveness_verdict: str          # "VALID" / "INVALID" / "NOT_TESTED"
      redistributed_to: tuple[str, ...]

  # score/subscore.py
  class ScoreStatus(StrEnum): COMPLETED; PARTIAL; UNAVAILABLE;
                              VALIDATION_PENDING; INSUFFICIENT_FACTORS
  class SubScoreName(StrEnum): RETURN; RISK; RISK_ADJUSTED; STABILITY;
                               RELATIVE_PERFORMANCE
  class WeightSource(StrEnum): EQUAL_WITHIN_VALID; OPTIMIZED

  @dataclass(frozen=True, slots=True)
  class FactorEffectiveness:
      factor_id: str; profile_id: str; is_valid: bool
      ic: Decimal | None; icir: Decimal | None; reason: str

  @dataclass(frozen=True, slots=True)
  class EvaluationProfile:
      profile_id: str
      declared_factors: Mapping[SubScoreName, tuple[str, ...]]
      sub_score_weights: Mapping[SubScoreName, Decimal]
      min_valid_factors_per_sub_score: int

  @dataclass(frozen=True, slots=True)
  class SubScoreResult:
      name: SubScoreName; value: Decimal | None; status: ScoreStatus
      weight_source: WeightSource; applied_weight: Decimal | None
      attributions: tuple[FactorAttribution, ...]

  @dataclass(frozen=True, slots=True)
  class FundScoreResult:
      profile_id: str; total_score: Decimal | None; status: ScoreStatus
      data_completeness: Decimal; sub_scores: tuple[SubScoreResult, ...]

  def compute_sub_score(name: SubScoreName, declared: Sequence[str],
                        factors: Mapping[str, NormalizedFactor],
                        effectiveness: Mapping[str, FactorEffectiveness],
                        min_valid_factors: int) -> SubScoreResult: ...
  def compute_fund_score(profile: EvaluationProfile,
                         factors: Mapping[str, NormalizedFactor],
                         effectiveness: Mapping[str, FactorEffectiveness]
                         ) -> FundScoreResult: ...

  # score/completeness.py
  def data_completeness(profile: EvaluationProfile,
                        sub_scores: Sequence[SubScoreResult]) -> Decimal: ...
  ```

- [ ] **Step 1: 写失败的单元测试（先证伪，G-18）**

```python
# tests/unit/test_sub_score.py
"""五子分 / 归因 / score_status 的行为锁定。

本文件锁住的是最容易被「优化」掉的四件事：
  · invalid 因子的权重恰为 0，但【仍在归因链里】并带失效原因（FS §8.4.1 规则 2）
  · 检验未产出 → VALIDATION_PENDING，【不产出总分】（FS:342/346，D-1）
  · M1 的常态是 PARTIAL（REL 子分恒 UNAVAILABLE），不是异常（D-19）
  · UNAVAILABLE 不得被任何填充值替代（G-3）
"""
from decimal import Decimal

import pytest

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import NormalizedFactor
from fip.strategy_library.score.subscore import (
    FUND_SCORE_STATUS_PRIORITY,
    EvaluationProfile,
    FactorEffectiveness,
    ScoreStatus,
    SubScoreName,
    WeightSource,
    compute_fund_score,
    compute_sub_score,
)

HIGHER = PreferenceDirection.HIGHER_IS_BETTER
LOWER = PreferenceDirection.LOWER_IS_BETTER

# M1 的唯一 Profile：声明 13 个因子 —— 10 个可算 + 3 个 REL。
# REL 三个【必须声明】：data_completeness 的分母是「Profile 声明的因子数」，
# 若分母只算 10 个可算因子，M1 的 completeness 恒为 1.0，
# 「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须可区分」（spec §6.2）
# 这条就被静默抹掉了。三个 REL ID 取自 D-8 点明的、从现存文档中泄露出的真实 ID。
M1_DECLARED = {
    SubScoreName.RETURN: ("F-RET-001", "F-RET-002"),
    SubScoreName.RISK: ("F-RISK-001", "F-RISK-002", "F-RISK-003"),
    SubScoreName.RISK_ADJUSTED: ("F-RAP-001", "F-RAP-002", "F-RAP-003"),
    SubScoreName.STABILITY: ("F-STAB-001", "F-STAB-002"),
    SubScoreName.RELATIVE_PERFORMANCE: ("F-REL-002", "F-REL-003", "F-REL-004"),
}
M1_SUB_WEIGHTS = {name: Decimal("0.2") for name in SubScoreName}


def profile(min_valid: int = 2) -> EvaluationProfile:
    return EvaluationProfile(
        profile_id="M1-DEFAULT",
        declared_factors=M1_DECLARED,
        sub_score_weights=M1_SUB_WEIGHTS,
        min_valid_factors_per_sub_score=min_valid,
    )


def nf(factor_id: str, score: str | None, status: FactorStatus = FactorStatus.VALID,
       direction: PreferenceDirection = HIGHER, raw: str | None = "1.0",
       reason: str = "") -> NormalizedFactor:
    return NormalizedFactor(
        factor_id=factor_id,
        window="3Y",
        raw_value=None if raw is None else Decimal(raw),
        normalized_score=None if score is None else Decimal(score),
        status=status,
        direction=direction,
        reason=reason,
    )


def eff(factor_id: str, valid: bool = True, reason: str = "") -> FactorEffectiveness:
    return FactorEffectiveness(
        factor_id=factor_id, profile_id="M1-DEFAULT", is_valid=valid,
        ic=Decimal("0.05"), icir=Decimal("0.4"), reason=reason,
    )


def all_ten_valid() -> tuple[dict, dict]:
    """10 个可算因子全部 VALID 且检验通过；3 个 REL 声明了但不可算。"""
    computable = [f for name, ids in M1_DECLARED.items() for f in ids
                  if name is not SubScoreName.RELATIVE_PERFORMANCE]
    factors = {fid: nf(fid, "60.0") for fid in computable}
    for fid in M1_DECLARED[SubScoreName.RELATIVE_PERFORMANCE]:
        factors[fid] = nf(fid, None, FactorStatus.UNAVAILABLE, raw=None,
                          reason="Benchmark 四层建模推到 M2，REL 全类不可算")
    effectiveness = {fid: eff(fid) for fid in factors}
    return factors, effectiveness


# --- 权重 -----------------------------------------------------------------

def test_weights_are_equal_within_valid_and_sum_to_exactly_one():
    """FS §8.4.1 规则 1：权重在【有效因子内】归一，和恰为 1。

    1/3 在十进制下无法精确表示，naive quantize 会给出 0.99999999。
    """
    result = compute_sub_score(
        SubScoreName.RISK_ADJUSTED,
        M1_DECLARED[SubScoreName.RISK_ADJUSTED],
        {fid: nf(fid, "60.0") for fid in M1_DECLARED[SubScoreName.RISK_ADJUSTED]},
        {fid: eff(fid) for fid in M1_DECLARED[SubScoreName.RISK_ADJUSTED]},
        min_valid_factors=2,
    )
    assert result.weight_source is WeightSource.EQUAL_WITHIN_VALID
    assert sum(a.weight for a in result.attributions) == Decimal("1")
    assert result.value == Decimal("60.00000000")


def test_invalid_factor_has_zero_weight_but_stays_in_attribution():
    """FS §8.4.1 规则 2 / §10.4：Calmar 判 invalid → 权重恰为 0，

    但【必须出现在归因链中】并标注失效原因 —— 否则无法回答
    「为什么这只基金的 Calmar 没影响分数」。
    """
    ids = M1_DECLARED[SubScoreName.RISK_ADJUSTED]  # Sharpe / Sortino / Calmar
    effectiveness = {fid: eff(fid) for fid in ids}
    effectiveness["F-RAP-003"] = eff("F-RAP-003", valid=False, reason="IC 0.004 < 0.02")

    result = compute_sub_score(
        SubScoreName.RISK_ADJUSTED, ids,
        {fid: nf(fid, "60.0") for fid in ids}, effectiveness, min_valid_factors=2,
    )
    by_id = {a.factor_id: a for a in result.attributions}
    assert set(by_id) == set(ids), "被剔除的因子从归因中消失了"
    calmar = by_id["F-RAP-003"]
    assert calmar.weight == Decimal("0")
    assert calmar.participated is False
    assert calmar.effectiveness_verdict == "INVALID"
    assert "IC 0.004" in (calmar.exclusion_reason or "")
    assert calmar.weighted_contribution is None
    assert set(calmar.redistributed_to) == {"F-RAP-001", "F-RAP-002"}
    assert by_id["F-RAP-001"].weight == Decimal("0.5")
    assert by_id["F-RAP-002"].weight == Decimal("0.5")


def test_unavailable_factor_is_never_filled():
    """G-3：UNAVAILABLE 不得被 0 / 上期 / 组内均值替代。"""
    ids = M1_DECLARED[SubScoreName.RISK]
    factors = {fid: nf(fid, "60.0") for fid in ids}
    factors["F-RISK-002"] = nf("F-RISK-002", None, FactorStatus.UNAVAILABLE,
                               LOWER, raw=None, reason="mar_policy 未配置")
    result = compute_sub_score(SubScoreName.RISK, ids, factors,
                               {fid: eff(fid) for fid in ids}, min_valid_factors=2)
    dv = next(a for a in result.attributions if a.factor_id == "F-RISK-002")
    assert dv.normalized_score is None
    assert dv.raw_value is None
    assert dv.weight == Decimal("0")
    assert dv.weighted_contribution is None
    assert "mar_policy 未配置" in (dv.exclusion_reason or "")
    # 参与的两个因子照常等权，子分【不因缺一个而变成 0 或被拉低】
    assert result.value == Decimal("60.00000000")
    assert result.status is ScoreStatus.PARTIAL


def test_single_valid_factor_yields_insufficient_factors_without_redistribution():
    """FS §9.3 已定案：子分内有效指标数 < 2 → 该子分 UNAVAILABLE，

    且【不做权重重分配】——「单一指标构成的子分等于该指标本身」。
    """
    ids = M1_DECLARED[SubScoreName.STABILITY]
    factors = {ids[0]: nf(ids[0], "70.0"),
               ids[1]: nf(ids[1], None, FactorStatus.UNAVAILABLE, raw=None,
                          reason="观测数 300 < min_obs 504")}
    result = compute_sub_score(SubScoreName.STABILITY, ids, factors,
                               {fid: eff(fid) for fid in ids}, min_valid_factors=2)
    assert result.status is ScoreStatus.INSUFFICIENT_FACTORS
    assert result.value is None
    assert all(a.weight == Decimal("0") for a in result.attributions)
    survivor = next(a for a in result.attributions if a.factor_id == ids[0])
    assert survivor.participated is False
    assert "不做权重重分配" in (survivor.exclusion_reason or "")


# --- 总分与 score_status ---------------------------------------------------

def test_validation_pending_produces_no_total_score():
    """D-1 / FS:342/346：factor_effectiveness 未产出 → 不产出总分。

    「先按等权上线、等检验出来再调」与「未经检验就拍权重」上游明定为完全等价。
    """
    factors, _ = all_ten_valid()
    result = compute_fund_score(profile(), factors, effectiveness={})
    assert result.status is ScoreStatus.VALIDATION_PENDING
    assert result.total_score is None
    assert all(s.value is None for s in result.sub_scores)
    # G-4：即使不产出总分，data_completeness 仍是必备字段
    assert result.data_completeness == Decimal("0")
    verdicts = {a.effectiveness_verdict
                for s in result.sub_scores for a in s.attributions}
    assert verdicts == {"NOT_TESTED"}


def test_m1_normal_case_is_partial_not_an_error():
    """D-19：M1 的【常态】是 PARTIAL —— REL 子分恒 UNAVAILABLE。

    这条必须被显式断言：否则「PARTIAL 是正常的」这个事实会在下游被当成
    异常处理（告警、阻断、或干脆把 PARTIAL 的分数丢弃）。
    """
    factors, effectiveness = all_ten_valid()
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.PARTIAL
    assert result.total_score == Decimal("60.00000000")
    rel = next(s for s in result.sub_scores
               if s.name is SubScoreName.RELATIVE_PERFORMANCE)
    assert rel.status is ScoreStatus.UNAVAILABLE
    assert rel.value is None
    assert rel.applied_weight is None            # 不参与总分，且不留残余权重
    others = [s for s in result.sub_scores if s.name is not rel.name]
    assert all(s.status is ScoreStatus.COMPLETED for s in others)
    # 四个子分重归一后各占 0.25，和恰为 1
    assert sum(s.applied_weight for s in others) == Decimal("1")


def test_completed_requires_all_five_sub_scores():
    factors, effectiveness = all_ten_valid()
    for fid in M1_DECLARED[SubScoreName.RELATIVE_PERFORMANCE]:
        factors[fid] = nf(fid, "50.0")
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.COMPLETED
    assert result.data_completeness == Decimal("1")


def test_unavailable_when_no_sub_score_can_be_produced():
    factors, effectiveness = all_ten_valid()
    factors = {fid: nf(fid, None, FactorStatus.UNAVAILABLE, raw=None,
                       reason="观测数不足") for fid in factors}
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.UNAVAILABLE
    assert result.total_score is None


def test_insufficient_factors_outranks_partial_in_fund_status():
    """D-25【补齐 C-4】基金层优先级：

        VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS > PARTIAL > COMPLETED

    越靠前的状态越是「这个分数**不能按字面使用**」的强信号。多个条件同时
    成立时只能报一个，报弱的那个会让下游以为分数可用。上游未给优先级，
    D-25 钉死。
    """
    factors, effectiveness = all_ten_valid()
    factors["F-STAB-002"] = nf("F-STAB-002", None, FactorStatus.UNAVAILABLE,
                               raw=None, reason="观测数 300 < min_obs 504")
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.INSUFFICIENT_FACTORS
    assert result.total_score is not None, "子分不足不等于总分不可产出"


def test_基金层_score_status_优先级与声明一致():
    """把 D-25 从注释变成机器可判定的事实。

    只写一条「INSUFFICIENT_FACTORS 压过 PARTIAL」的用例，不足以锁住整条链：
    实现里的 if/elif 顺序被人调换后，另外三对关系无声地反过来。这里逐对
    构造「两个条件同时成立」的输入，断言产出的总是更靠前的那个。
    """
    assert FUND_SCORE_STATUS_PRIORITY == (
        ScoreStatus.VALIDATION_PENDING,
        ScoreStatus.UNAVAILABLE,
        ScoreStatus.INSUFFICIENT_FACTORS,
        ScoreStatus.PARTIAL,
        ScoreStatus.COMPLETED,
    )

    # ① VALIDATION_PENDING 压过 UNAVAILABLE：全部因子不可算【且】无检验结论
    factors, _ = all_ten_valid()
    factors = {fid: nf(fid, None, FactorStatus.UNAVAILABLE, raw=None,
                       reason="观测数不足") for fid in factors}
    assert compute_fund_score(profile(), factors, effectiveness={}).status \
        is ScoreStatus.VALIDATION_PENDING

    # ② UNAVAILABLE 压过 INSUFFICIENT_FACTORS：有检验结论，但一个子分都出不来
    _, effectiveness = all_ten_valid()
    assert compute_fund_score(profile(), factors, effectiveness).status \
        is ScoreStatus.UNAVAILABLE

    # ③ INSUFFICIENT_FACTORS 压过 PARTIAL —— 见上一条用例
    # ④ PARTIAL 压过 COMPLETED：M1 常态（REL 恒缺）由
    #    test_m1_normal_case_is_partial_not_an_error 覆盖


def test_reproducible_bitwise_on_recompute():
    """G-2：同一输入重算必须一致（容差 1e-10；这里要求逐位相同）。"""
    factors, effectiveness = all_ten_valid()
    first = compute_fund_score(profile(), factors, effectiveness)
    second = compute_fund_score(profile(), dict(reversed(list(factors.items()))),
                                effectiveness)
    assert first.total_score == second.total_score
    assert abs(first.total_score - second.total_score) < Decimal("1e-10")
    assert [a.weight for s in first.sub_scores for a in s.attributions] == \
           [a.weight for s in second.sub_scores for a in s.attributions]


def test_profile_declaring_no_factor_is_rejected_not_defaulted():
    """空 Profile 不得静默产出 completeness = 1.0 —— 0/0 是配置错误，不是「完整」。"""
    from fip.strategy_library.score.completeness import data_completeness

    empty = EvaluationProfile(profile_id="EMPTY", declared_factors={},
                              sub_score_weights=M1_SUB_WEIGHTS,
                              min_valid_factors_per_sub_score=2)
    with pytest.raises(ValueError, match="声明的因子数为 0"):
        data_completeness(empty, ())
```

```python
# tests/unit/test_score_completeness.py
"""Data Completeness —— G-4 的输出必备字段。

定义（【补齐 PROVISIONAL】，设计定案 §7 缺口 2）：
    data_completeness = 实际参与评分的因子数 / 该 Profile 声明的因子数

本文件【自带】全部夹具，不从 test_sub_score.py 导入：tests/unit 下没有
__init__.py，跨测试文件的 import 依赖 rootdir 注入，是一条会在别人改
pytest 配置时静默断掉的隐式依赖。
"""
from decimal import Decimal

import pytest

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import NormalizedFactor
from fip.strategy_library.score.completeness import data_completeness
from fip.strategy_library.score.subscore import (
    EvaluationProfile,
    FactorEffectiveness,
    ScoreStatus,
    SubScoreName,
    compute_fund_score,
)

DECLARED = {
    SubScoreName.RETURN: ("F-RET-001", "F-RET-002"),
    SubScoreName.RISK: ("F-RISK-001", "F-RISK-002", "F-RISK-003"),
    SubScoreName.RISK_ADJUSTED: ("F-RAP-001", "F-RAP-002", "F-RAP-003"),
    SubScoreName.STABILITY: ("F-STAB-001", "F-STAB-002"),
    SubScoreName.RELATIVE_PERFORMANCE: ("F-REL-002", "F-REL-003", "F-REL-004"),
}
PROFILE = EvaluationProfile(
    profile_id="M1-DEFAULT",
    declared_factors=DECLARED,
    sub_score_weights={name: Decimal("0.2") for name in SubScoreName},
    min_valid_factors_per_sub_score=2,
)


def _factor(fid: str, score: str | None, status: FactorStatus, reason: str = ""):
    return NormalizedFactor(
        factor_id=fid, window="3Y",
        raw_value=None if score is None else Decimal("1.0"),
        normalized_score=None if score is None else Decimal(score),
        status=status, direction=PreferenceDirection.HIGHER_IS_BETTER, reason=reason,
    )


def _effectiveness(fid: str, valid: bool = True, reason: str = ""):
    return FactorEffectiveness(
        factor_id=fid, profile_id="M1-DEFAULT", is_valid=valid,
        ic=Decimal("0.05"), icir=Decimal("0.4"), reason=reason,
    )


def _baseline() -> tuple[dict, dict]:
    """10 个可算因子全部 VALID；3 个 REL 声明了但恒 UNAVAILABLE。"""
    factors = {}
    for name, ids in DECLARED.items():
        for fid in ids:
            if name is SubScoreName.RELATIVE_PERFORMANCE:
                factors[fid] = _factor(fid, None, FactorStatus.UNAVAILABLE,
                                       "Benchmark 推到 M2，REL 全类不可算")
            else:
                factors[fid] = _factor(fid, "60.0", FactorStatus.VALID)
    return factors, {fid: _effectiveness(fid) for fid in factors}


def test_m1_completeness_is_ten_over_thirteen():
    """M1 的分母含 3 个声明但不可算的 REL 因子 —— 这正是 spec §6.2 要求的

    「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须可区分」的落地。
    若分母只算 10 个可算因子，completeness 恒为 1.0，该区分被静默抹掉。
    """
    factors, effectiveness = _baseline()
    result = compute_fund_score(PROFILE, factors, effectiveness)
    assert result.data_completeness == Decimal("0.76923077")
    assert result.data_completeness < Decimal("1")


def test_completeness_drops_when_a_factor_becomes_unavailable():
    factors, effectiveness = _baseline()
    factors["F-RAP-003"] = _factor(
        "F-RAP-003", None, FactorStatus.UNAVAILABLE,
        "Max Drawdown = 0，Calmar 不可算（不得填 inf）",
    )
    result = compute_fund_score(PROFILE, factors, effectiveness)
    assert result.data_completeness == Decimal("0.69230769")      # 9 / 13


def test_completeness_counts_participation_not_availability():
    """判 INVALID 的因子【有值】却不参与评分，分子里不得算它。

    分子取「有值」会让「基于 3 个指标的 85 分」看起来像
    「基于 4 个指标的 85 分」—— 而那正是本字段要防的那件事（FS:415）。
    """
    factors, effectiveness = _baseline()
    effectiveness["F-RET-002"] = _effectiveness("F-RET-002", valid=False,
                                                reason="IC 0.001 未过阈值")
    result = compute_fund_score(PROFILE, factors, effectiveness)
    # 8 / 13，不是 9 / 13：Return 子分只剩 1 个有效因子（< 2），按 FS §9.3
    # 该子分整体不产出【且不做权重重分配】，于是幸存的 F-RET-001 也不参与。
    assert result.data_completeness == Decimal("0.61538462")
    ret = next(s for s in result.sub_scores if s.name is SubScoreName.RETURN)
    assert ret.status is ScoreStatus.INSUFFICIENT_FACTORS         # 1 < 2
    assert ret.value is None


def test_zero_declared_factors_raises_instead_of_returning_one():
    empty = EvaluationProfile(
        profile_id="EMPTY", declared_factors={},
        sub_score_weights={name: Decimal("0.2") for name in SubScoreName},
        min_valid_factors_per_sub_score=2,
    )
    with pytest.raises(ValueError, match="声明的因子数为 0"):
        data_completeness(empty, ())
```

- [ ] **Step 2: 运行确认失败（G-18 先证伪）**

Run: `.venv/bin/pytest tests/unit/test_sub_score.py tests/unit/test_score_completeness.py -q`

Expected: 全部 collection error —
`ModuleNotFoundError: No module named 'fip.strategy_library.score'`。
把这段输出粘进执行报告；**没有先看到这条失败就不许往下写实现**。

- [ ] **Step 3: 实现归因数据结构**

```python
# src/fip/strategy_library/score/attribution.py
"""归因明细 —— FS §10.2 / §10.3 / §10.4。

归因链：Total Score → 五子分 + 权重 → 各 Factor 的 Normalized Score × Weight
→ Factor Raw Value + Direction + Peer Group 内分位。

FS:456：`raw_value` 不可省略 —— 只有标准化值时用户看不懂「0.83 分」从何而来。
FS §10.4：被排除的因子必须记录【为什么被排除】，而不是从归因中消失。
"""

from dataclasses import dataclass
from decimal import Decimal

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus

# 量化步长与存储精度对齐（platform/db/types.py）：
#   权重 / 比率 → RatioNumeric = Numeric(12, 8)
#   分数        → NavNumeric   = Numeric(18, 8)
# 在纯函数里就量化，而不是等到落库时才截断：G-2 要求「同一输入重算必须一致」，
# 若纯函数返回无限精度而由 ORM 静默取整，两次重算之间只要中间量的位数不同，
# 落库值就可能不同，而单元测试完全看不见。
WEIGHT_QUANTUM = Decimal("0.00000001")
SCORE_QUANTUM = Decimal("0.00000001")
RATIO_QUANTUM = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class NormalizedFactor:
    """一只基金、一个因子、一个窗口在 Peer Group 内标准化后的全部事实。

    normalized_score 为 None 表示【该因子在本组内没有分位】——
    可能是因子本身 UNAVAILABLE，也可能是 N == 1（percentile_rank 返回 None）。
    两种都【不得】被 0 / 50 / 组内均值替代（G-3）。
    """

    factor_id: str
    window: str
    raw_value: Decimal | None
    normalized_score: Decimal | None
    status: FactorStatus
    direction: PreferenceDirection
    reason: str


@dataclass(frozen=True, slots=True)
class FactorAttribution:
    """归因链最底层的一行。FS §10.3 的六项 + §10.4 的三类信息。

    §10.3 六项：factor_id + window / raw_value / normalized_score /
                direction / weight / weighted_contribution
    §10.4 三类：排除原因（exclusion_reason）、原权重（invalid 时恒为 0，
                见下）、重分配去向（redistributed_to）

    ⚠️「原权重」在 EQUAL_WITHIN_VALID 下【不存在】：权重是在有效因子内
    现算的 1/n，被排除的因子从来没有过一个「原本的权重」可供剥夺。
    FS §10.4 的示例格式（「原权重 X%、重分配至 Sharpe +X%」）描述的是
    第二版 OPTIMIZED 权重下的形态。此处如实记 weight = 0，并用
    redistributed_to 回答「那份权重去哪了」——即同子分内实际参与的因子集合。
    """

    factor_id: str
    window: str
    raw_value: Decimal | None
    normalized_score: Decimal | None
    direction: PreferenceDirection | None
    weight: Decimal
    weighted_contribution: Decimal | None
    participated: bool
    exclusion_reason: str | None
    effectiveness_verdict: str
    redistributed_to: tuple[str, ...]
```

- [ ] **Step 4: 实现五子分与总分**

```python
# src/fip/strategy_library/score/subscore.py
"""五子分合成 —— FS §8。

合成公式（FS:256-263，一字不差）：
    Weighted Contribution_i = Normalized Score_i × Weight_i
    Sub-Score_k             = Σ Weighted Contribution_i   (i ∈ 子分 k 的因子集合)
    Total Score             = Σ Sub-Score_k × Weight_k    (k = 五个子分)

因子层权重 = EQUAL_WITHIN_VALID（FS §8.4.1，已定案 2026-08-27）：
【有效因子内】等权，不是全体因子等权，也不是「先等权上线再调」。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import (
    SCORE_QUANTUM,
    WEIGHT_QUANTUM,
    FactorAttribution,
    NormalizedFactor,
)


class ScoreStatus(StrEnum):
    """D-19 裁定的五值。`NOT_AVAILABLE` 与 `UNAVAILABLE` 是同一概念的两种拼写，

    统一取 `UNAVAILABLE`（与 FactorStatus 的枚举一致）。
    同一枚举同时用于子分层与基金层，取值含义在两层上是一致的
    （D-25：`FS:344` 说的是「某**子分**标 INSUFFICIENT_FACTORS」，而 D-19
    把它列为**基金层** score_status 的取值 —— 两个层级用同一枚举，
    取值含义一致，冲突只在「基金层怎么由子分层聚合出来」，见下）。
    """

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    INSUFFICIENT_FACTORS = "INSUFFICIENT_FACTORS"


# D-25【补齐 C-4】基金层 score_status 的优先级 —— 越靠前越强。
#
#   VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS > PARTIAL > COMPLETED
#
# 理由：越靠前的状态越是「这个分数**不能按字面使用**」的强信号。
# 多个条件同时成立时只能报一个，报弱的那个会让下游以为分数可用。
#
# 它不是注释里的一句话 —— compute_fund_score 的分支顺序必须与本元组一致，
# 由 test_基金层_score_status_优先级与声明一致 逐对比较钉住。
FUND_SCORE_STATUS_PRIORITY: tuple[ScoreStatus, ...] = (
    ScoreStatus.VALIDATION_PENDING,
    ScoreStatus.UNAVAILABLE,
    ScoreStatus.INSUFFICIENT_FACTORS,
    ScoreStatus.PARTIAL,
    ScoreStatus.COMPLETED,
)


class SubScoreName(StrEnum):
    """FS §4.1：命名固定，不得增删改。枚举的声明顺序即输出顺序（确定性）。"""

    RETURN = "Return"
    RISK = "Risk"
    RISK_ADJUSTED = "Risk-Adjusted"
    STABILITY = "Stability"
    RELATIVE_PERFORMANCE = "Relative Performance"


class WeightSource(StrEnum):
    """FS §8.4.1 规则 3：权重来源须落库，与第二版的 OPTIMIZED 区分。"""

    EQUAL_WITHIN_VALID = "EQUAL_WITHIN_VALID"
    OPTIMIZED = "OPTIMIZED"          # 第二版；本 Plan 不实现，留作落库取值域


@dataclass(frozen=True, slots=True)
class FactorEffectiveness:
    """Task 13 的判定结论。本层【只消费判定结果】，不判定阈值（FS:350）。"""

    factor_id: str
    profile_id: str
    is_valid: bool
    ic: Decimal | None
    icir: Decimal | None
    reason: str


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """一个 Evaluation Profile 的评分结构。全部取自配置，不得硬编码。

    declared_factors 是【声明】不是【可算】：M1 的 REL 三项声明了但不可算，
    正因为声明了，data_completeness 的分母才含它们（spec §6.2）。
    """

    profile_id: str
    declared_factors: Mapping[SubScoreName, tuple[str, ...]]
    sub_score_weights: Mapping[SubScoreName, Decimal]
    min_valid_factors_per_sub_score: int


@dataclass(frozen=True, slots=True)
class SubScoreResult:
    name: SubScoreName
    value: Decimal | None
    status: ScoreStatus
    weight_source: WeightSource
    applied_weight: Decimal | None      # 在总分中实际使用的子分权重（重归一后）
    attributions: tuple[FactorAttribution, ...]


@dataclass(frozen=True, slots=True)
class FundScoreResult:
    profile_id: str
    total_score: Decimal | None
    status: ScoreStatus
    data_completeness: Decimal
    sub_scores: tuple[SubScoreResult, ...]


_PARTICIPATING_STATUSES = frozenset({FactorStatus.VALID, FactorStatus.WARNING})

# FS §7.3 消费方规则：WARNING「参与但标记须传递」——所以它在参与集合里，
# 而它的 reason 会原样落进归因行的 exclusion_reason 之外的 raw/normalized 列，
# 标记的传递由 Task 17 落库时携带 factor_status 完成。


def _equal_weights(n: int) -> list[Decimal]:
    """n 个有效因子的等权向量，Σ【恰为】1。

    1/3 在十进制下无法精确表示。直接对每一项 quantize 得到的是
    0.33333333 × 3 = 0.99999999 —— 差 1e-8，正好落在 RatioNumeric(12,8)
    能看见的一位上，于是「权重之和为 1」（FS:322）在落库后为假。
    因此最后一项吸收残差；调用方按 factor_id 升序传入，结果确定可复现。
    """
    if n <= 0:
        return []
    share = (Decimal(1) / Decimal(n)).quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)
    weights = [share] * (n - 1)
    weights.append(Decimal(1) - share * (n - 1))
    return weights


def compute_sub_score(
    name: SubScoreName,
    declared: Sequence[str],
    factors: Mapping[str, NormalizedFactor],
    effectiveness: Mapping[str, FactorEffectiveness],
    min_valid_factors: int,
) -> SubScoreResult:
    """一个子分。Scoring Process 的 ②③④⑤ 步（FS §13.2）。

    排除顺序固定，且【每一步都留痕】：
      1. 无有效性检验结论  → NOT_TESTED（D-1：检验是产出的前置条件）
      2. 检验判 INVALID    → 权重 0，留在归因链里（FS §8.4.1 规则 2）
      3. 本次未产出因子值  → 声明了却没算出来，如实记录
      4. factor_status ∉ {VALID, WARNING} → 按 FS §7.3 不参与
      5. 组内分位不可得（N == 1）→ 不得填 50 或 100（D-11）
    """
    ordered = sorted(declared)
    participating: list[str] = []
    verdicts: dict[str, str] = {}
    reasons: dict[str, str | None] = {}

    for fid in ordered:
        factor = factors.get(fid)
        verdict = effectiveness.get(fid)
        if verdict is None:
            verdicts[fid] = "NOT_TESTED"
            reasons[fid] = (
                "factor_effectiveness 未产出该因子的检验结论；"
                "未经检验的因子不得参与评分（FS:346）"
            )
            continue
        verdicts[fid] = "VALID" if verdict.is_valid else "INVALID"
        if not verdict.is_valid:
            reasons[fid] = f"有效性检验判定 INVALID：{verdict.reason}"
            continue
        if factor is None:
            reasons[fid] = "Profile 声明了本因子，但本次运行未产出因子值"
            continue
        if factor.status not in _PARTICIPATING_STATUSES:
            reasons[fid] = f"factor_status={factor.status}：{factor.reason}"
            continue
        if factor.normalized_score is None:
            reasons[fid] = (
                "Peer Group 内分位不可得（N == 1）；"
                "不得以 50 / 100 / 组内均值替代（G-3）"
            )
            continue
        participating.append(fid)
        reasons[fid] = None

    produced = len(participating) >= max(min_valid_factors, 1)
    if not produced and participating:
        # FS §9.3 已定案：有效指标数 < 2 → 该子分 UNAVAILABLE，
        # 且【不做权重重分配】。留下的那一个因子也不参与。
        for fid in participating:
            reasons[fid] = (
                f"子分内有效因子数 {len(participating)} < {min_valid_factors}，"
                "按 FS §9.3 该子分不产出且不做权重重分配"
            )

    weights = _equal_weights(len(participating)) if produced else []
    weight_by_id = dict(zip(participating, weights, strict=True)) if produced else {}
    redistributed = tuple(participating) if produced else ()

    rows: list[FactorAttribution] = []
    for fid in ordered:
        factor = factors.get(fid)
        weight = weight_by_id.get(fid, Decimal("0"))
        took_part = fid in weight_by_id
        contribution = None
        if took_part and factor is not None and factor.normalized_score is not None:
            contribution = (factor.normalized_score * weight).quantize(
                SCORE_QUANTUM, rounding=ROUND_HALF_UP
            )
        rows.append(
            FactorAttribution(
                factor_id=fid,
                window=factor.window if factor else "",
                raw_value=factor.raw_value if factor else None,
                normalized_score=factor.normalized_score if factor else None,
                direction=factor.direction if factor else None,
                weight=weight,
                weighted_contribution=contribution,
                participated=took_part,
                exclusion_reason=None if took_part else reasons[fid],
                effectiveness_verdict=verdicts[fid],
                redistributed_to=() if took_part else redistributed,
            )
        )

    if not participating:
        status = ScoreStatus.UNAVAILABLE
        value = None
    elif not produced:
        status = ScoreStatus.INSUFFICIENT_FACTORS
        value = None
    else:
        status = (
            ScoreStatus.COMPLETED
            if len(participating) == len(ordered)
            else ScoreStatus.PARTIAL
        )
        value = sum(
            (r.weighted_contribution for r in rows if r.weighted_contribution is not None),
            Decimal("0"),
        ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)

    return SubScoreResult(
        name=name,
        value=value,
        status=status,
        weight_source=WeightSource.EQUAL_WITHIN_VALID,
        applied_weight=None,          # 由 compute_fund_score 重归一后回填
        attributions=tuple(rows),
    )


def _renormalized(
    available: Sequence[SubScoreResult], declared: Mapping[SubScoreName, Decimal]
) -> list[Decimal]:
    """把 Profile 的子分权重在【可产出的子分内】重归一，Σ 恰为 1。

    FS:343：某子分 UNAVAILABLE → 总分「按剩余子分处理」，即
    EXCLUDE_AND_RENORMALIZE（FS §9.2 的推荐策略）。
    绝不把缺失子分按 0 分计入 —— 那是 §9.2 明令严禁的两种做法之一。
    """
    total = sum((declared[s.name] for s in available), Decimal("0"))
    if total <= 0:
        raise ValueError(f"可产出子分的权重之和为 {total}，Profile 配置有误")
    weights = [
        (declared[s.name] / total).quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)
        for s in available[:-1]
    ]
    weights.append(Decimal(1) - sum(weights, Decimal("0")))
    return weights


def compute_fund_score(
    profile: EvaluationProfile,
    factors: Mapping[str, NormalizedFactor],
    effectiveness: Mapping[str, FactorEffectiveness],
) -> FundScoreResult:
    """一只基金在一个 Profile 下的总分。FS §13.2 的八步。

    ⚠️ 状态优先级是【补齐】——上游给了五个取值却没给同时成立时的优先级：
        VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS
                           > PARTIAL > COMPLETED
    取这个顺序的理由：越靠前的状态越是「这个分数不能按字面使用」的强信号，
    下游按最强信号处置才不会误用。
    """
    from fip.strategy_library.score.completeness import data_completeness

    declared_ids = [fid for ids in profile.declared_factors.values() for fid in ids]
    subs = [
        compute_sub_score(
            name,
            profile.declared_factors.get(name, ()),
            factors,
            effectiveness,
            profile.min_valid_factors_per_sub_score,
        )
        for name in SubScoreName
    ]

    # D-1 的前置：没有【任何一个】声明因子拿到检验结论 → 检验尚未产出。
    # 部分因子有结论时不算「未产出」——那些没有结论的因子逐个被排除即可。
    if declared_ids and not any(fid in effectiveness for fid in declared_ids):
        return FundScoreResult(
            profile_id=profile.profile_id,
            total_score=None,
            status=ScoreStatus.VALIDATION_PENDING,
            data_completeness=data_completeness(profile, subs),
            sub_scores=tuple(subs),
        )

    available = [s for s in subs if s.value is not None]
    if not available:
        return FundScoreResult(
            profile_id=profile.profile_id,
            total_score=None,
            status=ScoreStatus.UNAVAILABLE,
            data_completeness=data_completeness(profile, subs),
            sub_scores=tuple(subs),
        )

    weights = _renormalized(available, profile.sub_score_weights)
    applied = {s.name: w for s, w in zip(available, weights, strict=True)}
    total = sum(
        (s.value * applied[s.name] for s in available), Decimal("0")
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)

    if any(s.status is ScoreStatus.INSUFFICIENT_FACTORS for s in subs):
        status = ScoreStatus.INSUFFICIENT_FACTORS
    elif len(available) < len(subs):
        status = ScoreStatus.PARTIAL
    else:
        status = ScoreStatus.COMPLETED

    resolved = tuple(
        SubScoreResult(
            name=s.name,
            value=s.value,
            status=s.status,
            weight_source=s.weight_source,
            applied_weight=applied.get(s.name),
            attributions=s.attributions,
        )
        for s in subs
    )
    return FundScoreResult(
        profile_id=profile.profile_id,
        total_score=total,
        status=status,
        data_completeness=data_completeness(profile, resolved),
        sub_scores=resolved,
    )
```

- [ ] **Step 5: 实现 Data Completeness**

```python
# src/fip/strategy_library/score/completeness.py
"""Data Completeness —— G-4 的输出必备字段。

上游只给了口径（FS:418「可用指标数 / 应有指标数」）没给确切计算式，
设计定案 §7 缺口 2 把它定义为：

    data_completeness = 实际参与评分的因子数 / 该 Profile 声明的因子数

标 PROVISIONAL：分子取「参与评分」而非「有值」是一个真正的口径选择 ——
一个算得出值但被有效性检验判 INVALID 的因子，对分数的贡献是 0，
把它算进分子会让「基于 3 个指标的 85 分」看起来像「基于 4 个指标的 85 分」，
而这正是本字段要防的那件事（FS:415）。
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from fip.strategy_library.score.attribution import RATIO_QUANTUM
from fip.strategy_library.score.subscore import EvaluationProfile, SubScoreResult


def data_completeness(
    profile: EvaluationProfile, sub_scores: Sequence[SubScoreResult]
) -> Decimal:
    declared = sum(len(ids) for ids in profile.declared_factors.values())
    if declared == 0:
        # 不返回 1.0：0/0 既不是「完整」也不是「不完整」，是配置错误。
        # 静默返回 1.0 会让一个什么都没声明的 Profile 报告「数据完整」。
        raise ValueError(
            f"Profile {profile.profile_id} 声明的因子数为 0，"
            "data_completeness 无定义（分母为 0）"
        )
    used = sum(1 for s in sub_scores for a in s.attributions if a.participated)
    return (Decimal(used) / Decimal(declared)).quantize(
        RATIO_QUANTUM, rounding=ROUND_HALF_UP
    )
```

```python
# src/fip/strategy_library/score/__init__.py
"""评分层。纯函数，不含数据访问与运行模式分支（SDL-1 / SDL-2）。"""
```

- [ ] **Step 6: 落配置——Profile 的因子声明与子分权重**

```yaml
# config/strategy/factor/v1.yaml
# Factor Version v1 —— 因子清单、Factor Usage 与 Evaluation Profile 的评分结构
# Owner: factor-service（因子身份与口径）/ fund-service（Profile 的权重结构）
#
# ⚠️ 本文件【整体】是设计定案 §3 的【补齐】：因子域的八份上游文档在仓库中
# 一份都不存在（docs/04-factor/ 实为 05-fund-evaluation/ 的逐字节副本）。
# 拿到正式的因子域文档后应整体替换，而不是逐项修改。
profile:
  m1_default:
    id:
      value: M1-DEFAULT
      status: PROVISIONAL
      source: "设计定案 §7 缺口 3：M1 只实现一个 Profile，四类画像推到 M2"
    min_valid_factors_per_sub_score:
      value: 2
      status: DECIDED
      source: "FS §9.3 已定案 2026-08-27：子分内有效指标数 < 2 → 该子分 UNAVAILABLE"
    declared_factors:
      Return:
        value: ["F-RET-001", "F-RET-002"]
        status: PROVISIONAL
        source: "设计定案 D-8 因子清单；D-21 裁定 Rolling Return 归 RET"
      Risk:
        value: ["F-RISK-001", "F-RISK-002", "F-RISK-003"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Risk-Adjusted:
        value: ["F-RAP-001", "F-RAP-002", "F-RAP-003"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Stability:
        value: ["F-STAB-001", "F-STAB-002"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Relative Performance:
        # 【声明但不可算】。三个 ID 是 D-8 点明的、从现存文档中泄露出的真实 ID。
        # 为什么必须声明：data_completeness 的分母是「Profile 声明的因子数」。
        # 若分母只算 10 个可算因子，M1 的 completeness 恒为 1.0，
        # spec §6.2 要求的「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须
        # 可区分」就被静默抹掉 —— 而那正是 M1 用来跑通 UNAVAILABLE 机制的
        # 唯一场景。Tracking Error 与 Benchmark 超额收益【不在此列】：
        # 它们的真实 Factor ID 未从任何现存文档泄露，凭空编号会在拿到正式
        # 文档时与真 ID 冲突，比少声明两个更难修。
        value: ["F-REL-002", "F-REL-003", "F-REL-004"]
        status: PROVISIONAL
        source: "设计定案 D-8：Benchmark 四层建模推到 M2，REL 全类恒 UNAVAILABLE"
    sub_score_weights:
      # ⚠️ 这是本 Plan 里【最需要被质疑】的一组值，如实登记其来源冲突：
      # BR:278 明确禁止「现在拍一个 25% / 25% / 25% / 25%」，FS:299 要求
      # 「不得事先拍板权重」；而 FS:301-304 只把【因子层】权重定案为
      # EQUAL_WITHIN_VALID，把【子分层】权重推给「由 Profile 定义」，
      # §8.5 又只定了个别因子在个别画像下的相对高低（费率 / MDD / Alpha /
      # TE），无一项在 M1 可算。也就是说：M1 的子分权重上游【既禁止拍板
      # 也没有给值】，而 Fund Tier 依赖总分、总分依赖子分权重（D-1 的同一
      # 条论证链）。取等权是被这条链逼出来的唯一可行值，不是判断。
      # 它与 EQUAL_WITHIN_VALID 的关键差别：因子层的等权【已定案】，
      # 子分层的等权【是占位】，因此标 PROVISIONAL —— 在 LIVE 模式下每次
      # 取用都会发出 ProvisionalParameterUsed 告警（platform/config/loader.py）。
      # 这正是 IMP-4 那套机制存在的理由。以上由【设计定案 D-23】正式裁定：
      # 五项各 0.2、status = PROVISIONAL、source 写明「上游禁止拍板但未给值」。
      # 两者不得混同：EQUAL_WITHIN_VALID 是已定案，本组是占位。
      Return:
        value: "0.2"
        status: PROVISIONAL
        source: "设计定案 D-23（§7 缺口 3 + FS §8.4）：上游禁止拍板但未给值，见本节说明"
      Risk:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Risk-Adjusted:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Stability:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Relative Performance:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
```

- [ ] **Step 7: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_sub_score.py tests/unit/test_score_completeness.py -v`

Expected: 全部通过。特别核对这三条出现在 PASSED 列表里 ——
`test_m1_normal_case_is_partial_not_an_error`、
`test_validation_pending_produces_no_total_score`、
`test_invalid_factor_has_zero_weight_but_stays_in_attribution`。

Run: `.venv/bin/pytest tests/fitness -q && .venv/bin/ruff check src tests && make typecheck`

Expected: 适应度测试全绿（新包不得引入 I/O 依赖与 runtime_mode 分支）、lint 与 typecheck 通过。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(score): 五子分、归因与 Data Completeness

因子层权重 EQUAL_WITHIN_VALID —— 有效因子内等权，不是全体等权；
invalid 因子权重恰为 0 但留在归因链中并带失效原因与重分配去向。
检验未产出 → VALIDATION_PENDING，不产出总分（D-1）。
M1 常态为 PARTIAL（REL 子分恒 UNAVAILABLE），由测试显式断言。
data_completeness 的分母含 3 个声明但不可算的 REL 因子，故 M1 恒为 10/13。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 15: 排名 / 分位 / Fund Tier

> ⚠️ **【Ruling PF-1 的残留，需 controller 确认】** PF-1 裁定
> 「`normalize_peer_group` 是 G-8 三元组的唯一权威产出点，Task 15 与 Task 17
> 一律消费它，不得各自再算一遍」。Task 17 那条绕过它的路径已删除。
> **但本任务的 `rank_within_peer_group` 目前【无法】消费它**，原因有三：
> 1. `normalize_peer_group` 的入参已裁定为 `(share_class_id, FactorResult)`，
>    而本任务排的是 **Fund Score 总分**（`RankingEntry.metric_value`），
>    不是因子值 —— 要消费它就得凭空造 `FactorResult`，那是伪造因子结果；
> 2. 本任务要按 **Profile 拆分子排名**（G-10），`normalize_peer_group` 无此概念；
> 3. 本任务的 `RankingResult` 还带 `peer_group_size` 与 `tie_method`，
>    `NormalizedFactorValue` 里都没有。
>
> 因此本任务**暂时保留** `_competition_ranks` / `_percentile` 两个私有实现，
> 并已在两处加注「公式必须与 `factor/normalize` 逐字相同」。
> **落实方未自行改动本任务的算法结构**，把这条残留原样上报：
> 若要真正做到「唯一权威产出点」，需要先把内核（`competition_ranks` /
> 分位公式）单独提取到一个两边都 import 的模块，那是一次结构调整，
> 不在本次落实的授权范围内。

> ✅ **【冲突 ③ 已按 Ruling PF-3 裁定解决】`FundTier` 三个含义拆名**：
> ORM 类保持 `FundTier`（对应 `evaluation.fund_tier`，与 Plan-1 的
> `FundNav` ↔ `market.fund_nav` 命名一致，由 Task 8 定义）；
> **档位枚举一律叫 `FundTierLevel`**（跨任务接口契约第 462 行已在用）；
> Task 17 的 `FundTierRow` 已删除，直接用 Task 8 的 ORM 类 `FundTier`。
> 本任务正文已全文改为 `FundTierLevel`。

> 依赖 Task 14。仍然全部落在 `strategy_library`，纯函数。
> 派生链（BR §16.1）：`Fund Score → Peer Group Ranking → Percentile → Fund Tier`，
> 「四者是同一条派生链上的不同表示，不是四个独立概念」。

**Files:**
- Create: `src/fip/strategy_library/ranking/__init__.py`
- Create: `src/fip/strategy_library/ranking/rank.py`
- Test: `tests/unit/test_ranking.py`
- Test: `tests/unit/test_fund_tier.py`
- Test: `tests/fitness/test_single_config_source.py`
- Modify: `config/policy/evaluation/v1.yaml`（`peer_group.min_sample_size` 与 Tier 阈值）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.score.subscore.ScoreStatus`（Task 14）
  - `fip.quant_engine.stats.median`（Task 3，用于组内绝对水平）
- Produces:
  ```python
  # ranking/rank.py
  class TieMethod(StrEnum): COMPETITION_RANK; DENSE_RANK; ORDINAL_RANK
  class CrossSectionStatus(StrEnum): NORMAL; INSUFFICIENT_SAMPLE
  class FundTierLevel(StrEnum): A_PLUS = "A+"; A = "A"; B = "B"; C = "C"; D = "D"

  @dataclass(frozen=True, slots=True)
  class RankingEntry:
      share_class_id: int; profile_id: str; metric_value: Decimal | None

  @dataclass(frozen=True, slots=True)
  class RankingResult:
      share_class_id: int; profile_id: str
      rank: int | None; percentile: Decimal | None
      n_effective: int; peer_group_size: int
      ranking_status: CrossSectionStatus; tie_method: TieMethod

  @dataclass(frozen=True, slots=True)
  class TierThresholds:
      a_plus: Decimal; a: Decimal; b: Decimal; c: Decimal

  @dataclass(frozen=True, slots=True)
  class PeerGroupAbsoluteLevel:
      sharpe_median: Decimal | None; max_drawdown_median: Decimal | None

  @dataclass(frozen=True, slots=True)
  class TierResult:
      share_class_id: int; profile_id: str
      tier: FundTierLevel | None; percentile: Decimal | None
      rank: int | None; n_effective: int; total_score: Decimal | None
      classification_status: CrossSectionStatus
      peer_group_level: PeerGroupAbsoluteLevel      # 无默认值，G-9 的结构化落地

  def rank_within_peer_group(entries: Sequence[RankingEntry], *,
                             peer_group_size: int,
                             min_peer_group_size: int) -> list[RankingResult]: ...
  def assign_tier(ranking: RankingResult, *, total_score: Decimal | None,
                  thresholds: TierThresholds,
                  peer_group_level: PeerGroupAbsoluteLevel,
                  min_peer_group_size: int) -> TierResult: ...
  def peer_group_absolute_level(sharpe_values: Sequence[Decimal],
                                mdd_values: Sequence[Decimal]
                                ) -> PeerGroupAbsoluteLevel: ...
  ```

- [ ] **Step 1: 写失败的排名测试**

```python
# tests/unit/test_ranking.py
"""COMPETITION_RANK + Percentile + 小样本 —— G-7 / G-8 / G-10 / D-20。"""
from decimal import Decimal

import pytest

from fip.strategy_library.ranking.rank import (
    CrossSectionStatus,
    RankingEntry,
    TieMethod,
    rank_within_peer_group,
)


def entries(*pairs: tuple[int, str | None], profile: str = "M1-DEFAULT"):
    return [
        RankingEntry(share_class_id=i, profile_id=profile,
                     metric_value=None if v is None else Decimal(v))
        for i, v in pairs
    ]


def test_competition_rank_skips_after_ties():
    """D-20：并列同名次，后续跳号 —— 1, 2, 2, 4。

    DENSE_RANK（1,2,2,3）会让「N 只基金的最大名次 < N」，于是
    Percentile 公式 (N − Rank)/(N − 1) 的分母与实际名次范围不匹配，
    「前 10%」实际包含的基金数随并列数量漂移（FR:277-285）。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, "85"), (3, "85"), (4, "80")),
        peer_group_size=4, min_peer_group_size=1,
    )
    assert [r.rank for r in results] == [1, 2, 2, 4]
    assert max(r.rank for r in results) == 4 == len(results)
    assert {r.tie_method for r in results} == {TieMethod.COMPETITION_RANK}


def test_percentile_endpoints_are_100_and_0():
    """FR:211-215：本项目采用 (N − Rank)/(N − 1) × 100，最优 100、最劣 0。"""
    results = rank_within_peer_group(
        entries(*[(i, str(100 - i)) for i in range(1, 6)]),
        peer_group_size=5, min_peer_group_size=1,
    )
    assert results[0].percentile == Decimal("100.00000000")
    assert results[-1].percentile == Decimal("0E-8")
    mid = results[2]
    assert mid.percentile == Decimal("50.00000000")


def test_percentile_matches_the_documented_example():
    """FR:218-220：Rank = 5，N = 120 → (120 − 5) / 119 × 100 ≈ 96.6%。"""
    results = rank_within_peer_group(
        entries(*[(i, str(1000 - i)) for i in range(1, 121)]),
        peer_group_size=120, min_peer_group_size=1,
    )
    fifth = next(r for r in results if r.rank == 5)
    assert fifth.n_effective == 120
    assert Decimal("96.63") < fifth.percentile < Decimal("96.65")


def test_rank_n_effective_and_percentile_are_all_present():
    """G-8：三者都必须落库 —— 只存 Rank 则历史分位不可还原。

    这里断言的是【纯函数就把三者一起产出】，落库测试在 Task 17。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, "80")), peer_group_size=2, min_peer_group_size=1,
    )
    for r in results:
        assert r.rank is not None
        assert r.n_effective == 2
        assert r.percentile is not None
        assert r.peer_group_size == 2


def test_unavailable_metric_yields_no_row_and_shrinks_n_effective():
    """FR:186-197：N 是【有效参与数】不是组规模。

    指标 UNAVAILABLE 的基金不产出排名行（ERD §9.4：Ranking 基数是 0..1），
    也不得计入 N —— 更不得按 0 分参与排名（G-3）。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, None), (3, "80")),
        peer_group_size=3, min_peer_group_size=1,
    )
    assert [r.share_class_id for r in results] == [1, 3]
    assert {r.n_effective for r in results} == {2}
    assert {r.peer_group_size for r in results} == {3}


def test_insufficient_sample_returns_rows_with_null_rank_and_percentile():
    """FR §9.3.1：n_effective < 30 → rank / percentile 为 null，

    n_effective 返回实际值，ranking_status = INSUFFICIENT_SAMPLE。
    FR:356：「n_effective 仍须返回 —— 调用方需要知道差多少」。
    FR:730：这一行【仍然落库】，不落库会让历史查询无法区分
    「当时样本不足」与「当时根本没算」。
    """
    results = rank_within_peer_group(
        entries(*[(i, str(100 - i)) for i in range(1, 18)]),
        peer_group_size=17, min_peer_group_size=30,
    )
    assert len(results) == 17
    for r in results:
        assert r.rank is None
        assert r.percentile is None
        assert r.n_effective == 17
        assert r.ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_single_member_group_has_no_percentile():
    """FR:234-240：N = 1 → 分母为 0 → Percentile = UNAVAILABLE。

    此时【不得】返回 ranking_status = NORMAL：数据库的联动 CHECK 是
    (NORMAL AND rank NOT NULL AND percentile NOT NULL) OR
    (INSUFFICIENT_SAMPLE AND rank IS NULL AND percentile IS NULL)，
    没有第三种形态可容纳「有名次但无分位」。生产配置下 1 < 30 恒成立，
    此分支只在 min_peer_group_size 被调低时可达，这里显式钉住。
    """
    results = rank_within_peer_group(
        entries((7, "90")), peer_group_size=1, min_peer_group_size=1,
    )
    assert len(results) == 1
    assert results[0].percentile is None
    assert results[0].rank is None
    assert results[0].n_effective == 1
    assert results[0].ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_sub_rankings_are_split_by_profile():
    """G-10：同一 Peer Group 内多个 Profile 时按 Profile 拆分子排名，

    不产出跨 Profile 统一排名。M1 只有一个 Profile，这条在生产中【空洞成立】
    —— 正因如此必须在这里用两个 Profile 把它钉住，否则 M2 加第二个 Profile
    时会静默产出一份把两个 Profile 混在一起的排名，而没有任何测试会红。
    """
    mixed = (
        entries((1, "90"), (2, "80"), profile="M1-DEFAULT")
        + entries((3, "95"), (4, "70"), profile="ACTIVE-EQUITY")
    )
    results = rank_within_peer_group(mixed, peer_group_size=4, min_peer_group_size=1)
    by_profile: dict[str, list] = {}
    for r in results:
        by_profile.setdefault(r.profile_id, []).append(r)
    assert set(by_profile) == {"M1-DEFAULT", "ACTIVE-EQUITY"}
    for rows in by_profile.values():
        assert sorted(r.rank for r in rows) == [1, 2]
        assert {r.n_effective for r in rows} == {2}      # 各自 2，不是 4


def test_output_order_is_deterministic_regardless_of_input_order():
    """FR §8.4：并列时不得依赖数据库返回顺序 —— 每次重算可能不同则违反可复现性。

    次级规则显式声明为 share_class_id 升序。
    """
    forward = entries((1, "85"), (2, "85"), (3, "85"))
    backward = list(reversed(forward))
    a = rank_within_peer_group(forward, peer_group_size=3, min_peer_group_size=1)
    b = rank_within_peer_group(backward, peer_group_size=3, min_peer_group_size=1)
    assert [(r.share_class_id, r.rank, r.percentile) for r in a] == \
           [(r.share_class_id, r.rank, r.percentile) for r in b]
    assert [r.rank for r in a] == [1, 1, 1]


def test_mixed_profile_and_unavailable_metric_do_not_interfere():
    mixed = (
        entries((1, "90"), (2, None), profile="M1-DEFAULT")
        + entries((3, "95"), (4, "70"), profile="ACTIVE-EQUITY")
    )
    results = rank_within_peer_group(mixed, peer_group_size=4, min_peer_group_size=1)
    m1 = [r for r in results if r.profile_id == "M1-DEFAULT"]
    assert len(m1) == 1
    assert m1[0].n_effective == 1
    assert m1[0].ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize("size", [0, -1])
def test_peer_group_size_must_be_positive(size: int):
    with pytest.raises(ValueError, match="peer_group_size"):
        rank_within_peer_group(entries((1, "90")), peer_group_size=size,
                               min_peer_group_size=1)
```

- [ ] **Step 2: 写失败的 Tier 测试**

```python
# tests/unit/test_fund_tier.py
"""Fund Tier 五档 —— 阈值 5/20/50/80、G-9 同屏、小样本不产出。"""
from decimal import Decimal

import pytest

from fip.strategy_library.ranking.rank import (
    CrossSectionStatus,
    FundTierLevel,
    PeerGroupAbsoluteLevel,
    RankingResult,
    TierResult,
    TierThresholds,
    assign_tier,
    peer_group_absolute_level,
)

# 已定案 · 2026-08-25（P0-2）：前 5% / 5–20% / 20–50% / 50–80% / 后 20%。
# 换算到 percentile 空间即 95 / 80 / 50 / 20（FC §8.3）——
# 「这是一处极易出错的换算：『前 5%』在 Rank 语义下是小序号，
#   在 Percentile 语义下是大数值」（FC:214）。
THRESHOLDS = TierThresholds(a_plus=Decimal("95"), a=Decimal("80"),
                            b=Decimal("50"), c=Decimal("20"))
LEVEL = PeerGroupAbsoluteLevel(sharpe_median=Decimal("0.62"),
                               max_drawdown_median=Decimal("0.183"))


def ranked(percentile: str | None, n_effective: int = 120,
           status: CrossSectionStatus = CrossSectionStatus.NORMAL) -> RankingResult:
    from fip.strategy_library.ranking.rank import TieMethod

    return RankingResult(
        share_class_id=1, profile_id="M1-DEFAULT",
        rank=None if percentile is None else 5,
        percentile=None if percentile is None else Decimal(percentile),
        n_effective=n_effective, peer_group_size=n_effective,
        ranking_status=status, tie_method=TieMethod.COMPETITION_RANK,
    )


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [
        ("100", FundTierLevel.A_PLUS),
        ("95", FundTierLevel.A_PLUS),      # 恰好等于阈值 → 归入较优档（FC §13）
        ("94.99999999", FundTierLevel.A),
        ("80", FundTierLevel.A),
        ("79.99999999", FundTierLevel.B),
        ("50", FundTierLevel.B),
        ("49.99999999", FundTierLevel.C),
        ("20", FundTierLevel.C),
        ("19.99999999", FundTierLevel.D),
        ("0", FundTierLevel.D),
    ],
)
def test_tier_boundaries_are_upper_closed(percentile: str, expected: FundTierLevel):
    result = assign_tier(ranked(percentile), total_score=Decimal("77"),
                         thresholds=THRESHOLDS, peer_group_level=LEVEL,
                         min_peer_group_size=30)
    assert result.tier is expected
    assert result.classification_status is CrossSectionStatus.NORMAL


def test_thresholds_cover_the_whole_range_exclusively_and_monotonically():
    """FC §8.4 的三项边界校验：完备性 / 互斥性 / 单调性。

    在 [0, 100] 上以 0.5 步长扫描：每个取值必须恰好落入一个档，
    且 percentile 越高档位越优。
    """
    order = [FundTierLevel.D, FundTierLevel.C, FundTierLevel.B, FundTierLevel.A, FundTierLevel.A_PLUS]
    previous = -1
    p = Decimal("0")
    while p <= Decimal("100"):
        tier = assign_tier(ranked(str(p)), total_score=Decimal("50"),
                           thresholds=THRESHOLDS, peer_group_level=LEVEL,
                           min_peer_group_size=30).tier
        assert tier is not None, f"percentile={p} 落在任何档之外（完备性失败）"
        index = order.index(tier)
        assert index >= previous, f"percentile={p} 处档位倒退（单调性失败）"
        previous = index
        p += Decimal("0.5")


def test_top_percent_and_percentile_thresholds_are_mutually_checkable():
    """FC:214 要求两种表述必须能互相校验：前 X% ⇔ percentile ≥ 100 − X。"""
    top_percent = {"a_plus": Decimal("5"), "a": Decimal("20"),
                   "b": Decimal("50"), "c": Decimal("80")}
    for field, top in top_percent.items():
        assert getattr(THRESHOLDS, field) == Decimal("100") - top


def test_small_sample_produces_no_tier_at_all():
    """FC §8.5 已定案 2026-08-27：n_effective < 30 → 【不产出】Tier，

    而不是「产出一个带低置信标记的 Tier」。FC:249 的理由：
    「Tier 值仍存在，下游会照常使用它……标记只在展示层可见，
      而消费 Tier 的是代码不是人」。
    """
    result = assign_tier(
        ranked(None, n_effective=17, status=CrossSectionStatus.INSUFFICIENT_SAMPLE),
        total_score=Decimal("77"), thresholds=THRESHOLDS,
        peer_group_level=LEVEL, min_peer_group_size=30,
    )
    assert result.tier is None
    assert result.classification_status is CrossSectionStatus.INSUFFICIENT_SAMPLE
    assert result.n_effective == 17          # 判定依据仍须返回
    assert result.percentile is None


def test_no_percentile_means_no_tier_not_the_lowest_tier():
    """FC §13 Edge Case：percentile = UNAVAILABLE → 无 Tier，

    【不得默认为最低档】。默认 D 会把「不知道」伪装成「很差」。
    """
    result = assign_tier(ranked(None, n_effective=120), total_score=None,
                         thresholds=THRESHOLDS, peer_group_level=LEVEL,
                         min_peer_group_size=30)
    assert result.tier is None
    assert result.classification_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_tier_cannot_be_constructed_without_peer_group_absolute_level():
    """G-9 的结构化落地：Tier 不得单独输出。

    上游把它写成「强制要求」而不是建议（BR:1094-1096、FC:157
    「仅展示 Tier 而不展示组内绝对水平，视为违反本条」）。
    口头要求会被违反，因此把它做成【类型上不可能】：
    peer_group_level 是 TierResult 的必填字段且无默认值 ——
    想只输出 Tier，得先造出一个 TierResult，而那需要组内绝对水平。
    """
    with pytest.raises(TypeError):
        TierResult(                                   # type: ignore[call-arg]
            share_class_id=1, profile_id="M1-DEFAULT", tier=FundTierLevel.A_PLUS,
            percentile=Decimal("96"), rank=5, n_effective=120,
            total_score=Decimal("88"),
            classification_status=CrossSectionStatus.NORMAL,
        )


def test_absolute_level_is_unavailable_not_zero_when_group_has_no_valid_factor():
    """G-3：组内没有任何有效 Sharpe 时中位数是 UNAVAILABLE，不是 0。"""
    level = peer_group_absolute_level(sharpe_values=[], mdd_values=[])
    assert level.sharpe_median is None
    assert level.max_drawdown_median is None


def test_absolute_level_uses_median_of_valid_values_only():
    level = peer_group_absolute_level(
        sharpe_values=[Decimal("0.1"), Decimal("0.5"), Decimal("0.9")],
        mdd_values=[Decimal("0.2"), Decimal("0.4")],
    )
    assert level.sharpe_median == Decimal("0.5")
    assert level.max_drawdown_median == Decimal("0.3")


def test_thresholds_must_be_strictly_descending():
    with pytest.raises(ValueError, match="必须严格递减"):
        TierThresholds(a_plus=Decimal("80"), a=Decimal("95"),
                       b=Decimal("50"), c=Decimal("20"))
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_ranking.py tests/unit/test_fund_tier.py -q`

Expected: collection error —
`ModuleNotFoundError: No module named 'fip.strategy_library.ranking'`。把输出粘进报告。

- [ ] **Step 4: 实现排名、分位与 Tier**

```python
# src/fip/strategy_library/ranking/rank.py
"""Peer Group 内排名、分位与五档分层。

派生链（BR §16.1）：Fund Score → Ranking → Percentile → Fund Tier。
「四者是同一条派生链上的不同表示，不是四个独立概念。
  任一环节的输入变化会沿链传导。」（BR:1061）

本模块是纯函数：阈值、最小样本量都由调用方注入，不读配置、不碰数据库。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from fip.quant_engine.stats import median
from fip.strategy_library.score.attribution import SCORE_QUANTUM


class TieMethod(StrEnum):
    """FR §8.1 的三种方法。D-20 裁定取 COMPETITION_RANK。

    另两个取值保留为落库取值域（ranking_policy 要能记录当时用的是哪一种），
    但本 Plan 只实现 COMPETITION_RANK —— 未实现的分支会显式抛错，
    不会静默退化成默认实现。
    """

    COMPETITION_RANK = "COMPETITION_RANK"
    DENSE_RANK = "DENSE_RANK"
    ORDINAL_RANK = "ORDINAL_RANK"


class CrossSectionStatus(StrEnum):
    """`cross_section_status_enum`（04-database-design §10.1.2 已定案）。"""

    NORMAL = "NORMAL"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


class FundTierLevel(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True, slots=True)
class RankingEntry:
    share_class_id: int
    profile_id: str
    metric_value: Decimal | None


@dataclass(frozen=True, slots=True)
class RankingResult:
    share_class_id: int
    profile_id: str
    rank: int | None
    percentile: Decimal | None
    n_effective: int
    peer_group_size: int
    ranking_status: CrossSectionStatus
    tie_method: TieMethod


@dataclass(frozen=True, slots=True)
class TierThresholds:
    """分位阈值。BR:1075「阈值配置化，严禁硬编码」，因此由调用方注入。"""

    a_plus: Decimal
    a: Decimal
    b: Decimal
    c: Decimal

    def __post_init__(self) -> None:
        values = (self.a_plus, self.a, self.b, self.c)
        if not all(a > b for a, b in zip(values, values[1:], strict=False)):
            raise ValueError(f"Tier 阈值必须严格递减，收到 {values}")
        if not (Decimal("0") <= self.c and self.a_plus <= Decimal("100")):
            raise ValueError(f"Tier 阈值必须落在 [0, 100]，收到 {values}")


@dataclass(frozen=True, slots=True)
class PeerGroupAbsoluteLevel:
    """组内绝对水平。G-9 要求至少含 Sharpe 中位数与 Maximum Drawdown 中位数。

    None 表示组内没有任何有效值 —— 按 G-3 如实呈现 UNAVAILABLE，不填 0。
    """

    sharpe_median: Decimal | None
    max_drawdown_median: Decimal | None


@dataclass(frozen=True, slots=True)
class TierResult:
    """G-9 的结构化落地。

    peer_group_level 是【必填且无默认值】的字段：BR:1094-1096 把
    「Tier 必须与组内绝对水平同屏展示」写成强制要求，FC:157 更明说
    「仅展示 Tier 而不展示组内绝对水平，视为违反本条」。
    把它做成 dataclass 的必填字段，等于让「只输出 Tier」在类型层面
    构造不出来 —— 口头约定会被违反，构造函数不会。

    ⚠️ 不要给它加默认值，也不要在这里放一个「空的」PeerGroupAbsoluteLevel
    做兜底：那会让本条约束一夜之间退回口头约定。
    """

    share_class_id: int
    profile_id: str
    tier: FundTierLevel | None
    percentile: Decimal | None
    rank: int | None
    n_effective: int
    total_score: Decimal | None
    classification_status: CrossSectionStatus
    peer_group_level: PeerGroupAbsoluteLevel


def _competition_ranks(values: Sequence[Decimal]) -> list[int]:
    """并列同名次、后续跳号：1, 2, 2, 4。输入必须已按降序排好。

    取 COMPETITION_RANK 而非 DENSE_RANK 的理由（FR:277-285）：
    DENSE_RANK 下 N 只基金的最大名次 < N，Percentile 公式
    (N − Rank)/(N − 1) 的分母与实际名次范围不匹配，
    「前 10%」实际包含的基金数会随并列数量漂移。
    """
    ranks: list[int] = []
    current = 0
    previous: Decimal | None = None
    for position, value in enumerate(values, start=1):
        if previous is None or value != previous:
            current = position
            previous = value
        ranks.append(current)
    return ranks


def _percentile(rank: int, n_effective: int) -> Decimal | None:
    """FR §7.1：Percentile = (N − Rank) / (N − 1) × 100。

    ⚠️【Ruling PF-1 的残留】本公式必须与
    `fip.strategy_library.factor.normalize.percentile_rank` 【逐字相同】。
    两处分叉不会报错，只会让「因子分位」与「排名分位」对同一只基金给出
    不同的数。见本任务开头登记的残留项：真正的修法是把内核提取到一个
    两边都 import 的模块，那是一次未获授权的结构调整。

    最优者 100、最劣者 0，与 Score 的 0–100 标尺方向一致，
    也使 Tier 阈值「前 5% ⇔ percentile ≥ 95」直观（FR:232）。
    N = 1 时分母为 0 → UNAVAILABLE（FR:234-240），不得返回 50 或 100。
    """
    if n_effective <= 1:
        return None
    return (
        Decimal(n_effective - rank) / Decimal(n_effective - 1) * Decimal(100)
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


def rank_within_peer_group(
    entries: Sequence[RankingEntry],
    *,
    peer_group_size: int,
    min_peer_group_size: int,
    tie_method: TieMethod = TieMethod.COMPETITION_RANK,
) -> list[RankingResult]:
    """一个 Peer Group 内、按 Profile 拆分的排名。

    G-10：同一 Peer Group 内多个 Evaluation Profile 时【按 Profile 拆分
    子排名】，不产出跨 Profile 统一排名 —— n_effective 因此是
    「本 Profile 内该指标的有效参与数」，不是全组的。

    metric_value 为 None 的成员【不产出排名行】（ERD §9.4：Ranking 对 Score
    的基数是 0..1，「评价合格 ≠ 排名合格」），也不计入 n_effective
    （FR:186-197：N 是有效参与数不是组规模）。它更不得按 0 参与排名（G-3）。

    n_effective < min_peer_group_size 时【仍然返回行】，只是 rank 与
    percentile 为 None、状态为 INSUFFICIENT_SAMPLE —— 「不落库会让历史查询
    无法区分『当时样本不足』与『当时根本没算』」（04-database-design:730）。
    """
    if tie_method is not TieMethod.COMPETITION_RANK:
        raise NotImplementedError(
            f"本 Plan 只实现 {TieMethod.COMPETITION_RANK}（D-20 裁定）；"
            f"收到 {tie_method}。另两个取值只是落库取值域。"
        )
    if peer_group_size <= 0:
        raise ValueError(f"peer_group_size 必须为正，收到 {peer_group_size}")

    # (metric_value, share_class_id) 的二元组：把 None 在这里就滤掉，
    # 之后的排序键里不再有 Optional —— 否则 -e.metric_value 在类型上是
    # 「可能对 None 取负」，mypy 会拦，而运行时也确实会在某天炸掉。
    by_profile: dict[str, list[tuple[Decimal, int]]] = {}
    for entry in entries:
        value = entry.metric_value
        if value is None:
            continue
        by_profile.setdefault(entry.profile_id, []).append((value, entry.share_class_id))

    results: list[RankingResult] = []
    for profile_id in sorted(by_profile):
        # 降序（越优越靠前，Rank = 1 最优，FR:201）；并列时按 share_class_id
        # 升序作为【显式声明的次级规则】，保证输出顺序确定（FR §8.4）。
        ordered = sorted(by_profile[profile_id], key=lambda pair: (-pair[0], pair[1]))
        n_effective = len(ordered)
        ranks = _competition_ranks([value for value, _ in ordered])
        insufficient = n_effective < min_peer_group_size or n_effective <= 1
        for (_, share_class_id), rank in zip(ordered, ranks, strict=True):
            percentile = None if insufficient else _percentile(rank, n_effective)
            results.append(
                RankingResult(
                    share_class_id=share_class_id,
                    profile_id=profile_id,
                    rank=None if insufficient else rank,
                    percentile=percentile,
                    n_effective=n_effective,
                    peer_group_size=peer_group_size,
                    ranking_status=(
                        CrossSectionStatus.INSUFFICIENT_SAMPLE
                        if insufficient
                        else CrossSectionStatus.NORMAL
                    ),
                    tie_method=tie_method,
                )
            )
    return results


def peer_group_absolute_level(
    sharpe_values: Sequence[Decimal], mdd_values: Sequence[Decimal]
) -> PeerGroupAbsoluteLevel:
    """组内绝对水平。调用方只传【有效】值，空序列 → None（不是 0）。"""
    return PeerGroupAbsoluteLevel(
        sharpe_median=median(sharpe_values) if sharpe_values else None,
        max_drawdown_median=median(mdd_values) if mdd_values else None,
    )


def assign_tier(
    ranking: RankingResult,
    *,
    total_score: Decimal | None,
    thresholds: TierThresholds,
    peer_group_level: PeerGroupAbsoluteLevel,
    min_peer_group_size: int,
) -> TierResult:
    """FC §12.1 的六步处理流程。

    ② percentile = UNAVAILABLE → 无 Tier（【不得默认为最低档】，FC §13）
    ③ n_effective < min → 不产出 Tier（FC §8.5 已定案，不是「低置信标记」）
    ④ 按分位区间判定，边界【上闭下开】：percentile >= 阈值归入较优档
    """
    insufficient = (
        ranking.percentile is None
        or ranking.n_effective < min_peer_group_size
        or ranking.ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE
    )
    if insufficient:
        tier = None
        status = CrossSectionStatus.INSUFFICIENT_SAMPLE
    else:
        percentile = ranking.percentile
        assert percentile is not None       # 已由 insufficient 分支排除
        if percentile >= thresholds.a_plus:
            tier = FundTierLevel.A_PLUS
        elif percentile >= thresholds.a:
            tier = FundTierLevel.A
        elif percentile >= thresholds.b:
            tier = FundTierLevel.B
        elif percentile >= thresholds.c:
            tier = FundTierLevel.C
        else:
            tier = FundTierLevel.D
        status = CrossSectionStatus.NORMAL

    return TierResult(
        share_class_id=ranking.share_class_id,
        profile_id=ranking.profile_id,
        tier=tier,
        percentile=ranking.percentile,
        rank=ranking.rank,
        n_effective=ranking.n_effective,
        total_score=total_score,
        classification_status=status,
        peer_group_level=peer_group_level,
    )
```

```python
# src/fip/strategy_library/ranking/__init__.py
"""排名 / 分位 / 分层。纯函数，阈值由调用方注入（BR:1075 严禁硬编码）。"""
```

- [ ] **Step 5: 落配置——三处共用同一配置源（G-7）**

```yaml
# config/policy/evaluation/v1.yaml —— 追加以下两节（保留既有的 mar / risk_free_rate）
peer_group:
  classification_level:
    value: L1
    status: PROVISIONAL
    source: "设计定案 D-7：IMP-TBD-2 的补齐，L2 分组会大量触发 INSUFFICIENT_SAMPLE"
  min_sample_size:
    # ⚠️ G-7：判定基数是 n_effective【不是】组规模，且标准化 / 排名 / 分层
    # 三处必须读【同一个】配置路径。三处各写一个 30 会在调参那天分叉，
    # 而分叉后的症状是「分位算出来了但 Tier 没产出」这种极难定位的不一致。
    # tests/fitness/test_single_config_source.py 断言全仓只有一处字面量。
    value: 30
    status: DECIDED
    source: "FR:340 已定案 2026-08-27：MIN_PEER_GROUP_SIZE = 30"
classification:
  tier_percentile_thresholds:
    # 已定案 · 2026-08-25（P0-2），FC §8.2 给出 >= / < 的明确边界。
    # 存的是 percentile 空间的阈值（95/80/50/20），不是「前 X%」（5/20/50/80）——
    # 两种表述互为补数，FC:214 称其为「一处极易出错的换算」，
    # tests/unit/test_fund_tier.py::test_top_percent_and_percentile_thresholds_
    # are_mutually_checkable 对这条换算做双向校验。
    a_plus:
      value: "95"
      status: DECIDED
      source: "BR:1084-1090 §16.3.1 已定案 2026-08-25；FC §8.2 边界 percentile >= 95"
    a:
      value: "80"
      status: DECIDED
      source: "同上：80 <= percentile < 95"
    b:
      value: "50"
      status: DECIDED
      source: "同上：50 <= percentile < 80"
    c:
      value: "20"
      status: DECIDED
      source: "同上：20 <= percentile < 50；percentile < 20 为 D"
```

```python
# tests/fitness/test_single_config_source.py
"""G-7：MIN_PEER_GROUP_SIZE 三处（标准化 / 排名 / 分层）必须同一配置源。

一条纯静态的检查：策略库里【不得】出现字面量 30 作为样本量阈值，
配置路径字符串在 src 中【只允许出现一次】（在 service 层解析配置的那一处）。
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
CONFIG_PATH_LITERAL = "peer_group.min_sample_size"


def test_min_sample_size_config_path_appears_exactly_once():
    hits = [
        f.relative_to(SRC)
        for f in SRC.rglob("*.py")
        if CONFIG_PATH_LITERAL in f.read_text(encoding="utf-8")
    ]
    assert len(hits) == 1, (
        f"配置路径 {CONFIG_PATH_LITERAL!r} 出现在 {hits} —— "
        "标准化 / 排名 / 分层三处必须经同一个解析点取值（G-7），"
        "各自 get 一次就是三个配置源，调参那天会分叉。"
    )


def test_strategy_library_contains_no_hardcoded_sample_threshold():
    """策略库是纯函数层：阈值只能【被注入】，不能自己知道。"""
    offenders = []
    for f in (SRC / "strategy_library").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == 30:
                offenders.append((f.relative_to(SRC), node.lineno))
    assert not offenders, (
        f"strategy_library 出现字面量 30：{offenders}。"
        "MIN_PEER_GROUP_SIZE 必须由调用方从配置注入（BR:1075 严禁硬编码）。"
    )
```

- [ ] **Step 6: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_ranking.py tests/unit/test_fund_tier.py tests/fitness -q`

Expected: 全部通过。`test_sub_rankings_are_split_by_profile`（G-10 的空洞成立锁）
与 `test_tier_cannot_be_constructed_without_peer_group_absolute_level`（G-9）必须在
PASSED 列表里。

Run: `.venv/bin/ruff check src tests && make typecheck`

Expected: 通过。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat(ranking): COMPETITION_RANK、分位与 Fund Tier 五档

Rank / n_effective / Percentile 三者一并产出（G-8）；n_effective 是有效参与数
不是组规模，指标 UNAVAILABLE 的成员不产出排名行也不计入 N。
样本不足仍落行但 rank/percentile 为 null（INSUFFICIENT_SAMPLE）。
Tier 阈值 95/80/50/20 上闭下开、由配置注入；n_effective < 30 不产出 Tier
而非给低置信标记。G-9 做成类型约束：TierResult 的组内绝对水平字段无默认值。
G-10 按 Profile 拆分子排名 —— M1 空洞成立，用双 Profile 测试锁住。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 16: Eligibility Rules + B2 候选池快照（含 REJECTED）

> ## ✅ 【冲突 ④ 已按 Ruling PF-4 裁定解决】`data_completeness_floor` 在 M1 取 **0.75**
>
> **冲突原样保留作记录**：两个数都有出处，且**都是本 Plan 里已定案的**：
>
> | 值 | 出处 | 状态 |
> |---|---|---|
> | `selection.data_completeness_floor = 0.8` | `05-fund-selection:121` 沿用 `03-data/03-data-quality` DQ-2 | 上游 **DECIDED** |
> | M1 `data_completeness = 10/13 = 0.76923077` | D-24（Profile 声明 13 个、可算 10 个） | **已定案** |
>
> `0.76923077 < 0.8` ⇒ `COND-COMPLETENESS` 对 M1 的每一只基金都判 FAIL，
> **B2 候选池恒为空** ⇒ M1.4 的验收标准（Universe 快照含 REJECTED 成员）
> 无从进行，Plan-2 交付不出东西。D-24 与 Task 16 分属两份草稿，谁都没看见对方。
>
> **裁定（Ruling PF-4）**：M1 的 floor 取 `0.75`，`status: PROVISIONAL`，
> `source` 逐字写明：
>
> > 上游的 0.8 是在【五子分齐全】的前提下定的；M1 刻意把 Benchmark 建模推到 M2
> > （spec §6.2），使 REL 三因子【结构性】不可算，data_completeness 恒为 10/13。
> > 把一个为完整系统设计的阈值套到一个【被刻意裁剪过】的系统上是范畴错误 ——
> > 它度量的本该是『数据缺失』，在 M1 却度量成了『范围裁剪』。
> > M2 恢复 REL 后必须改回 0.8。
>
> **裁定的代价**：若业务方认为「REL 不可算就不该入池」，本裁定是错的 ——
> 但那样 M1.4 的验收标准本身就无法满足，应先改 spec 而不是让候选池静默为空。
>
> **本任务仍须遵守的四条**：
> 1. **不得**再往下调 floor —— 0.75 是「刚好放行 10/13」的那条线，
>    它的正当性完全来自「M1 的缺口是范围裁剪不是数据缺失」这个理由；
>    继续下调就没有理由了。
> 2. **不得**为了让门槛通过而把分母改回 10 ——
>    D-29 明写这会让 Task 18 的 A-2 退化成恒真判据。
> 3. **必须**补一条测试把 floor 与分母的联动钉死（见下面 Step 1 的
>    `test_m1_data_completeness_clears_the_current_floor`）：M2 加回 REL 因子时，
>    若有人只改分母不改 floor，那条测试会红。
> 4. Task 18 的 A-3 / A-4 判据据此更新：B2 **不再是恒空**，
>    `SELECTED` 计数为 0 现在是一个需要排查的信号 —— 见该任务的说明。

> 依赖 Task 15。分两层：规则求值是纯函数（`strategy_library/universe`），
> B2 原子写入是编排（`services/fund_service`）。C-11：service 层只做编排与持久化，
> **不含投资策略规则** —— 条件怎么算、四种可投资性各自怎么处置，全在策略库里。

**Files:**
- Create: `src/fip/strategy_library/universe/__init__.py`
- Create: `src/fip/strategy_library/universe/rules.py`
- Create: `src/fip/services/fund_service/universe.py`
- Test: `tests/unit/test_eligibility_rules.py`
- Test: `tests/integration/test_universe_snapshot.py`
- Modify: `config/policy/evaluation/v1.yaml`（Selection Policy 的条件集与处理表）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.score.subscore.ScoreStatus`（Task 14）
  - `fip.strategy_library.ranking.rank.FundTierLevel`（Task 15）
  - `fip.services.fund_service.models.evaluation.{FundUniverseSnapshot, FundUniverseMember, SelectionConditionResult, PeerGroupSnapshot}`（Task 8）
  - `fip.services.data_service.eligibility.EligibilityStatus`（Plan-1；**只在 service 层消费**，策略库侧一律用 `str`，见 Step 4 说明）
- Produces:
  ```python
  # universe/rules.py
  class SelectionStatus(StrEnum): SELECTED; REJECTED
  class ConditionStatus(StrEnum): PASS; FAIL; UNAVAILABLE
  class Operator(StrEnum): GTE; LTE; IN; NOT_IN
  class EligibilityAction(StrEnum): ADMIT; ADMIT_WITH_CONSTRAINT; EXCLUDE

  SELECTABLE_FIELDS: frozenset[str]

  @dataclass(frozen=True, slots=True)
  class Condition:
      condition_id: str; field: str; operator: Operator
      threshold: Decimal | tuple[str, ...]

  @dataclass(frozen=True, slots=True)
  class CandidateFacts:
      share_class_id: int
      investment_eligibility: str | None
      evaluation_status: str | None
      data_completeness: Decimal | None
      total_score: Decimal | None
      percentile: Decimal | None
      fund_tier: str | None
      def value_of(self, field: str) -> object | None: ...

  @dataclass(frozen=True, slots=True)
  class ConditionResult:
      condition_id: str; condition_version: str; status: ConditionStatus
      actual_value: str | None; gap: Decimal | None

  @dataclass(frozen=True, slots=True)
  class SelectionOutcome:
      share_class_id: int; selection_status: SelectionStatus
      condition_results: tuple[ConditionResult, ...]
      constraint_note: str | None

  def evaluate_condition(condition: Condition, facts: CandidateFacts,
                         condition_version: str) -> ConditionResult: ...
  def evaluate_all(conditions: Sequence[Condition], facts: CandidateFacts,
                   condition_version: str) -> tuple[ConditionResult, ...]: ...
  def select(facts: CandidateFacts, conditions: Sequence[Condition],
             condition_version: str,
             eligibility_handling: Mapping[str, EligibilityAction]
             ) -> SelectionOutcome: ...

  # services/fund_service/universe.py
  class PeerGroupSnapshotMissing(RuntimeError): ...
  class UniverseSnapshotWriter:
      def __init__(self, session: Session) -> None: ...
      def write(self, *, decision_at: dt.date, peer_group_snapshot_id: int,
                selection_policy_version: str, condition_version: str,
                min_universe_size: int,
                outcomes: Sequence[SelectionOutcome],
                eligibility_refs: Mapping[int, tuple[dt.date, int] | None]
                ) -> int: ...
  ```

- [ ] **Step 1: 写失败的规则单元测试**

```python
# tests/unit/test_eligibility_rules.py
"""Eligibility Rules 求值 —— D-17 / G-11 的核心：【不得短路】。"""
from decimal import Decimal

import pytest

from fip.strategy_library.universe import rules
from fip.strategy_library.universe.rules import (
    CandidateFacts,
    Condition,
    ConditionStatus,
    EligibilityAction,
    Operator,
    SelectionStatus,
    evaluate_all,
    select,
)

# 与 config/policy/evaluation/v1.yaml 的 selection.data_completeness_floor 同值。
M1_COMPLETENESS_FLOOR = Decimal("0.75")
# D-24：Profile 声明 13 个因子，M1 可算 10 个。
M1_DATA_COMPLETENESS = (Decimal(10) / Decimal(13)).quantize(Decimal("0.00000001"))

CONDITIONS = (
    Condition("COND-ELIGIBILITY", "investment_eligibility", Operator.NOT_IN,
              ("EXIT_ONLY", "NOT_TRADABLE")),
    Condition("COND-EVAL-STATUS", "evaluation_status", Operator.IN,
              ("COMPLETED", "PARTIAL")),
    # 【Ruling PF-4】M1 的 floor 是 0.75（PROVISIONAL），见本任务开头。
    # 这里用的是真实的 M1 门槛，不再是「一个不与 M1 冲突的门槛」——
    # 端到端行为由 Task 18 的 A-3 覆盖。
    Condition("COND-COMPLETENESS", "data_completeness", Operator.GTE,
              M1_COMPLETENESS_FLOOR),
    Condition("COND-SCORE", "total_score", Operator.GTE, Decimal("60")),
)
HANDLING = {
    "FULLY_ELIGIBLE": EligibilityAction.ADMIT,
    "HOLD_ONLY": EligibilityAction.ADMIT_WITH_CONSTRAINT,
    "LIMITED": EligibilityAction.ADMIT_WITH_CONSTRAINT,
    "EXIT_ONLY": EligibilityAction.EXCLUDE,
    "NOT_TRADABLE": EligibilityAction.EXCLUDE,
}


def facts(**overrides) -> CandidateFacts:
    base = dict(
        share_class_id=1, investment_eligibility="FULLY_ELIGIBLE",
        evaluation_status="PARTIAL", data_completeness=Decimal("0.9"),
        total_score=Decimal("77"), percentile=Decimal("81"), fund_tier="A",
    )
    base.update(overrides)
    return CandidateFacts(**base)


# --- PF-4：floor 与分母的联动 ------------------------------------------------

def test_m1_data_completeness_clears_the_current_floor():
    """【Ruling PF-4】M1 的 data_completeness（10/13）必须【严格大于】当前 floor。

    ⚠️ M2 加回 REL 因子时，若有人只改分母不改 floor，本测试会红。
    这正是它存在的理由：0.75 这个值的全部正当性来自「M1 的缺口是【范围裁剪】
    不是【数据缺失】」；一旦 REL 可算，分母的含义就变了，
    floor 必须同步改回 0.8（见本任务开头 Ruling PF-4 的 source 原文）。
    反过来，若有人把分母从 13 改回 10（D-29 明令禁止），
    M1_DATA_COMPLETENESS 会变成 1.0，本测试仍绿 —— 那一侧由 Task 18 的 A-2 守。

    「严格大于」而不是「大于等于」：等号意味着 floor 恰好卡在 M1 的实际值上，
    任何一位精度调整都会让整个候选池翻面。
    """
    assert M1_DATA_COMPLETENESS > M1_COMPLETENESS_FLOOR
    assert M1_DATA_COMPLETENESS == Decimal("0.76923077")


def test_m1_completeness_passes_the_condition_so_b2_is_not_empty_by_construction():
    """裁定的直接后果：COND-COMPLETENESS 对一只典型 M1 基金判 PASS。

    裁定前它对【每一只】M1 基金判 FAIL，B2 候选池恒为空，
    M1.4 的验收标准（Universe 快照含 REJECTED 成员）根本无从进行。
    """
    results = evaluate_all(
        CONDITIONS, facts(data_completeness=M1_DATA_COMPLETENESS), "cv-1"
    )
    by_id = {r.condition_id: r for r in results}
    assert by_id["COND-COMPLETENESS"].status is ConditionStatus.PASS


# --- 不得短路 --------------------------------------------------------------

def test_all_conditions_are_evaluated_even_after_the_first_failure():
    """§14.4：短路求值会丢失信息 —— 无法回答「放宽某条件能新增多少基金」。

    第一个条件（可投资性）不通过时，其余三个【仍须求值】。
    """
    result = evaluate_all(
        CONDITIONS,
        facts(investment_eligibility="NOT_TRADABLE", total_score=Decimal("40")),
        condition_version="v1",
    )
    assert len(result) == len(CONDITIONS)
    by_id = {r.condition_id: r for r in result}
    assert by_id["COND-ELIGIBILITY"].status is ConditionStatus.FAIL
    # 后续条件不是占位符：它们各自反映了真实事实（两通过、一未通过）
    assert by_id["COND-EVAL-STATUS"].status is ConditionStatus.PASS
    assert by_id["COND-COMPLETENESS"].status is ConditionStatus.PASS
    assert by_id["COND-SCORE"].status is ConditionStatus.FAIL
    assert all(r.actual_value is not None for r in result)


def test_every_condition_is_actually_invoked_not_padded(monkeypatch):
    """比「结果条数对得上」更强的一条：证明每个条件都【真的被求值过】。

    只断言条数，一个「先短路、再用占位符补齐 K 行」的实现照样能通过。
    这里用 spy 记录实际调用序列。
    """
    calls: list[str] = []
    original = rules.evaluate_condition

    def spy(condition, facts_, condition_version):
        calls.append(condition.condition_id)
        return original(condition, facts_, condition_version)

    monkeypatch.setattr(rules, "evaluate_condition", spy)
    rules.evaluate_all(CONDITIONS, facts(investment_eligibility="NOT_TRADABLE"),
                       condition_version="v1")
    assert calls == [c.condition_id for c in CONDITIONS]


def test_gap_is_recorded_for_numeric_failures():
    """§14.2：不得只保存布尔值 —— 未通过时要记「实际值」与「差多少」。"""
    result = evaluate_all(CONDITIONS, facts(total_score=Decimal("52.5")),
                          condition_version="v1")
    score = next(r for r in result if r.condition_id == "COND-SCORE")
    assert score.status is ConditionStatus.FAIL
    assert score.actual_value == "52.5"
    assert score.gap == Decimal("7.5")


def test_missing_input_is_unavailable_not_a_silent_failure():
    """G-3：输入不可得 ≠ 输入为 0。两者必须在落库上可区分。"""
    result = evaluate_all(CONDITIONS, facts(total_score=None),
                          condition_version="v1")
    score = next(r for r in result if r.condition_id == "COND-SCORE")
    assert score.status is ConditionStatus.UNAVAILABLE
    assert score.actual_value is None
    assert score.gap is None


def test_unknown_field_raises_instead_of_evaluating_to_false():
    bad = (Condition("COND-X", "fund_size", Operator.GTE, Decimal("1")),)
    with pytest.raises(KeyError, match="fund_size"):
        evaluate_all(bad, facts(), condition_version="v1")


# --- 四种可投资性的四种动作 -------------------------------------------------

def test_fully_eligible_is_admitted_without_constraint():
    outcome = select(facts(), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.SELECTED
    assert outcome.constraint_note is None


@pytest.mark.parametrize("status", ["HOLD_ONLY", "LIMITED"])
def test_hold_only_and_limited_are_admitted_with_a_constraint_note(status: str):
    """§9.2：不可建仓 ≠ 移出 Universe。

    直接移出会让组合中已持有的该基金被优化器判定为「不在可选集合」，
    可能导致被强制清仓。正确做法是保留在池内并标注不可建仓。
    """
    outcome = select(facts(investment_eligibility=status), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.SELECTED
    assert outcome.constraint_note is not None
    assert status in outcome.constraint_note


def test_exit_only_does_not_enter_the_pool():
    """§9.3 定案 2026-08-27 推翻了原表格：EXIT_ONLY 基金【不入池】，

    但已持仓的不强制卖出（那是 portfolio 域的事，不在这里表达）。
    """
    outcome = select(facts(investment_eligibility="EXIT_ONLY"),
                     CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    assert len(outcome.condition_results) == len(CONDITIONS)


def test_not_tradable_is_excluded_but_leaves_a_trace():
    """§19 Edge Case：高分基金 NOT_TRADABLE → 排除，但【在被拒清单中记录】，

    「避免消失得无声无息」。
    """
    outcome = select(facts(investment_eligibility="NOT_TRADABLE",
                           total_score=Decimal("99")),
                     CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    reason = next(r for r in outcome.condition_results
                  if r.condition_id == "COND-ELIGIBILITY")
    assert reason.status is ConditionStatus.FAIL
    assert reason.actual_value == "NOT_TRADABLE"


def test_unknown_eligibility_value_raises_rather_than_defaulting_to_admit():
    """处理表缺一个取值时必须炸，不得默认放行。

    默认放行会让一个新增的可投资性状态静默地全部入池。
    """
    with pytest.raises(KeyError, match="SUSPENDED"):
        select(facts(investment_eligibility="SUSPENDED"), CONDITIONS, "v1", HANDLING)


def test_missing_eligibility_row_is_rejected_and_recorded():
    """PIT 下 available_at <= decision_at 取不到任何一版可投资性时。"""
    outcome = select(facts(investment_eligibility=None), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    reason = next(r for r in outcome.condition_results
                  if r.condition_id == "COND-ELIGIBILITY")
    assert reason.status is ConditionStatus.UNAVAILABLE
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_eligibility_rules.py -q`

Expected: `ModuleNotFoundError: No module named 'fip.strategy_library.universe'`。

- [ ] **Step 3: 实现规则求值（纯函数）**

```python
# src/fip/strategy_library/universe/rules.py
"""Eligibility Rules 求值。

⚠️ 与 `Investment Eligibility` 严格区分（03-data/02 §14 用「严格分离」四个字点名）：
  · `Investment Eligibility` 是【数据域的客观事实】——这只份额此刻能不能建仓，
    由 data-service 从 Lifecycle + 申赎 + 流动性派生，不含任何策略配置。
  · `Eligibility Rules` 是【版本化的策略配置】，属 Strategy Version 第 3 项。
  前者是后者【七个筛选维度之一】，不是它的同义词。

本模块只做后者，且【不 import 前者的枚举】：EligibilityStatus 定义在
fip.services.data_service.eligibility 里，而依赖方向是 services → strategy_library
单向，反向 import 是设计错误。因此这里一律用 str，取值域由调用方给的
eligibility_handling 映射表钉住（缺键即抛 KeyError，不默认放行），
并由 Task 17 的一条 service 层测试断言该映射的键集恰好等于 EligibilityStatus
的全部取值 —— 枚举与配置的漂移在【允许 import 枚举的那一层】被抓住。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class SelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class ConditionStatus(StrEnum):
    """PASS / FAIL 之外必须有第三个值。

    只有 PASS / FAIL 就无法区分「评估了，不通过」与「根本没法评估」——
    后者在输入缺失（如策略 A 下没有 total_score）时大量出现，
    把它记成 FAIL 等于宣称「我们量过了，它不达标」，那是编造证据。
    UNAVAILABLE 【不算通过】（无法证实达标就不得入池），但如实留痕。
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


class Operator(StrEnum):
    GTE = "GTE"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"


class EligibilityAction(StrEnum):
    ADMIT = "ADMIT"
    ADMIT_WITH_CONSTRAINT = "ADMIT_WITH_CONSTRAINT"
    EXCLUDE = "EXCLUDE"


# 可作为条件左值的字段白名单。不用裸 getattr：配置里写错一个字段名会
# 悄悄取到方法对象或抛 AttributeError，而这里要的是一条明确的错误。
SELECTABLE_FIELDS = frozenset({
    "investment_eligibility",
    "evaluation_status",
    "data_completeness",
    "total_score",
    "percentile",
    "fund_tier",
})


@dataclass(frozen=True, slots=True)
class Condition:
    condition_id: str
    field: str
    operator: Operator
    threshold: Decimal | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    """一只候选份额在 decision_at 的全部可筛字段。None 一律表示【不可得】。"""

    share_class_id: int
    investment_eligibility: str | None
    evaluation_status: str | None
    data_completeness: Decimal | None
    total_score: Decimal | None
    percentile: Decimal | None
    fund_tier: str | None

    def value_of(self, field: str) -> object | None:
        if field not in SELECTABLE_FIELDS:
            raise KeyError(
                f"条件引用了不可筛字段 {field!r}；可用字段：{sorted(SELECTABLE_FIELDS)}"
            )
        return getattr(self, field)


@dataclass(frozen=True, slots=True)
class ConditionResult:
    """§14.2：不得只保存布尔值。至少要有条件标识 + 通过与否 + 实际值 +

    （未通过时）差距。condition_version 一并存 —— 条件集本身会变更，
    不记录版本则历史结果无法解释（04-database-design:801）。
    """

    condition_id: str
    condition_version: str
    status: ConditionStatus
    actual_value: str | None
    gap: Decimal | None


@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    share_class_id: int
    selection_status: SelectionStatus
    condition_results: tuple[ConditionResult, ...]
    constraint_note: str | None


def evaluate_condition(
    condition: Condition, facts: CandidateFacts, condition_version: str
) -> ConditionResult:
    """单个条件。输入不可得 → UNAVAILABLE（不是 FAIL，也不是 PASS）。"""
    value = facts.value_of(condition.field)
    if value is None:
        return ConditionResult(condition.condition_id, condition_version,
                               ConditionStatus.UNAVAILABLE, None, None)

    if condition.operator in (Operator.IN, Operator.NOT_IN):
        if not isinstance(condition.threshold, tuple):
            raise TypeError(
                f"{condition.condition_id}：{condition.operator} 的阈值必须是取值元组"
            )
        member = str(value) in condition.threshold
        ok = member if condition.operator is Operator.IN else not member
        return ConditionResult(condition.condition_id, condition_version,
                               ConditionStatus.PASS if ok else ConditionStatus.FAIL,
                               str(value), None)

    if not isinstance(value, Decimal) or not isinstance(condition.threshold, Decimal):
        raise TypeError(
            f"{condition.condition_id}：{condition.operator} 要求 Decimal 左值与阈值，"
            f"收到 {type(value).__name__} / {type(condition.threshold).__name__}"
        )
    ok = (
        value >= condition.threshold
        if condition.operator is Operator.GTE
        else value <= condition.threshold
    )
    gap = None if ok else abs(condition.threshold - value)
    return ConditionResult(condition.condition_id, condition_version,
                           ConditionStatus.PASS if ok else ConditionStatus.FAIL,
                           str(value), gap)


def evaluate_all(
    conditions: Sequence[Condition], facts: CandidateFacts, condition_version: str
) -> tuple[ConditionResult, ...]:
    """全部条件【一律求值】，不得短路（D-17 / G-11 / §14.4）。

    ⚠️ 这是本 Plan 最容易被「优化」掉的一处：加一行
    `if result.status is ConditionStatus.FAIL: break` 能省下几次比较，
    代价是永远无法回答「放宽某条件能新增多少基金」，且无法区分
    「通过了」与「根本没评估」——后者会在条件集变更时大量出现。
    这里刻意写成对全集的推导式，不留插入 break 的位置；
    tests/unit/test_eligibility_rules.py 用 spy 断言每个条件都真的被调用过。

    通过模块级函数 evaluate_condition 调用（而不是内联），是为了让那条
    spy 测试能挂上去 —— 这不是多余的间接层，它是可测性的一部分。
    """
    return tuple(
        evaluate_condition(condition, facts, condition_version)
        for condition in conditions
    )


def select(
    facts: CandidateFacts,
    conditions: Sequence[Condition],
    condition_version: str,
    eligibility_handling: Mapping[str, EligibilityAction],
) -> SelectionOutcome:
    """一只候选的入池判定。§18.1 的 ③⑤ 两步。

    可投资性【本身就是一个条件】（§8.1 七个 Hard Filter 维度的最后一行），
    因此它走与其他条件相同的求值路径、留同样的痕；处理表只额外决定
    「入池的那些要不要带约束标注」。这样 EXIT_ONLY / NOT_TRADABLE
    的排除原因会出现在 selection_condition_result 里，而不是变成一个
    没有条件行支撑的、凭空的 REJECTED。
    """
    results = evaluate_all(conditions, facts, condition_version)
    passed = all(r.status is ConditionStatus.PASS for r in results)

    note: str | None = None
    status = facts.investment_eligibility
    if status is not None:
        try:
            action = eligibility_handling[status]
        except KeyError:
            raise KeyError(
                f"investment_eligibility={status!r} 不在处理表中："
                f"{sorted(eligibility_handling)}。新增取值必须显式登记处理方式，"
                "默认放行会让它静默全部入池。"
            ) from None
        if action is EligibilityAction.ADMIT_WITH_CONSTRAINT:
            note = f"{status}：入池并标注约束，建仓/加仓限制由 portfolio 域施加"

    return SelectionOutcome(
        share_class_id=facts.share_class_id,
        selection_status=SelectionStatus.SELECTED if passed else SelectionStatus.REJECTED,
        condition_results=results,
        constraint_note=note if passed else None,
    )
```

```python
# src/fip/strategy_library/universe/__init__.py
"""候选池准入规则。纯函数：不读配置、不碰数据库、不 import services。"""
```

- [ ] **Step 4: 写失败的 B2 原子性集成测试**

```python
# tests/integration/test_universe_snapshot.py
"""B2 快照原子写入 —— D-18 / D-17 / D-15。"""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select as sa_select

from fip.strategy_library.universe.rules import (
    ConditionResult,
    ConditionStatus,
    SelectionOutcome,
    SelectionStatus,
)
from fip.services.fund_service.models.evaluation import (
    FundUniverseMember,
    FundUniverseSnapshot,
    SelectionConditionResult,
)
from fip.services.fund_service.universe import (
    PeerGroupSnapshotMissing,
    UniverseSnapshotWriter,
)

pytestmark = pytest.mark.integration

DECISION_AT = dt.date(2026, 8, 31)
CONDITION_IDS = ("COND-ELIGIBILITY", "COND-EVAL-STATUS", "COND-COMPLETENESS",
                 "COND-SCORE")


def outcome(share_class_id: int, status: SelectionStatus) -> SelectionOutcome:
    """每只候选【一律】带全部 4 个条件结果，含被拒的那些。"""
    return SelectionOutcome(
        share_class_id=share_class_id,
        selection_status=status,
        condition_results=tuple(
            ConditionResult(
                condition_id=cid, condition_version="v1",
                status=(ConditionStatus.FAIL
                        if status is SelectionStatus.REJECTED and cid == CONDITION_IDS[0]
                        else ConditionStatus.PASS),
                actual_value="X", gap=None,
            )
            for cid in CONDITION_IDS
        ),
        constraint_note=None,
    )


def test_rejected_members_and_all_conditions_are_persisted(
    db_session, committed_peer_group_snapshot, share_class_ids
):
    """D-17：REJECTED 成员与【全部】条件结果落库。

    「若只存入池成员 → 无法验证是否有基金被错误排除 →
      而错误排除正是幸存者偏差的表现形式」（03-erd §9.2）。
    """
    selected, rejected = share_class_ids[0], share_class_ids[1]
    writer = UniverseSnapshotWriter(db_session)
    snapshot_id = writer.write(
        decision_at=DECISION_AT,
        peer_group_snapshot_id=committed_peer_group_snapshot,
        selection_policy_version="sel-v1", condition_version="v1",
        min_universe_size=1,
        outcomes=[outcome(selected, SelectionStatus.SELECTED),
                  outcome(rejected, SelectionStatus.REJECTED)],
        eligibility_refs={selected: None, rejected: None},
    )
    members = db_session.execute(
        sa_select(FundUniverseMember).where(
            FundUniverseMember.fund_universe_snapshot_id == snapshot_id)
    ).scalars().all()
    assert {m.selection_status for m in members} == {"SELECTED", "REJECTED"}

    per_member = db_session.execute(
        sa_select(SelectionConditionResult.fund_universe_member_id,
                  func.count()).group_by(SelectionConditionResult.fund_universe_member_id)
    ).all()
    assert {count for _, count in per_member} == {len(CONDITION_IDS)}, (
        "有成员的条件结果行数不等于条件集大小 —— 求值被短路，或只存了未通过项"
    )


def test_b2_is_atomic_nothing_survives_a_partial_write(
    db_session, committed_peer_group_snapshot, share_class_ids, monkeypatch
):
    """D-18 / spec §3.2：B2 写入不完整 → 整体回滚，本次决策视为未产生。"""
    from fip.services.fund_service import universe as universe_module

    original = universe_module.UniverseSnapshotWriter._write_condition_results
    calls = {"n": 0}

    def explode(self, member_id, results):
        calls["n"] += 1
        if calls["n"] == 2:                      # 第二个成员写到一半炸
            raise RuntimeError("模拟写入中断")
        return original(self, member_id, results)

    monkeypatch.setattr(
        universe_module.UniverseSnapshotWriter, "_write_condition_results", explode
    )
    writer = UniverseSnapshotWriter(db_session)
    with pytest.raises(RuntimeError, match="模拟写入中断"):
        writer.write(
            decision_at=DECISION_AT,
            peer_group_snapshot_id=committed_peer_group_snapshot,
            selection_policy_version="sel-v1", condition_version="v1",
            min_universe_size=1,
            outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED),
                      outcome(share_class_ids[1], SelectionStatus.REJECTED)],
            eligibility_refs={i: None for i in share_class_ids[:2]},
        )
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseSnapshot)
    ).scalar_one() == 0
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseMember)
    ).scalar_one() == 0
    assert db_session.execute(
        sa_select(func.count()).select_from(SelectionConditionResult)
    ).scalar_one() == 0


def test_b2_requires_a_committed_b1_snapshot_id(db_session, share_class_ids):
    """B1 → B2 的顺序依赖：B2 只能引用一个【已提交的】 B1 快照 ID。

    「三个边界各自原子，且按顺序依赖。任一边界写入失败，
      其下游边界不会产生」（01-system-architecture:855）。
    """
    writer = UniverseSnapshotWriter(db_session)
    with pytest.raises(PeerGroupSnapshotMissing):
        writer.write(
            decision_at=DECISION_AT, peer_group_snapshot_id=987654321,
            selection_policy_version="sel-v1", condition_version="v1",
            min_universe_size=1,
            outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED)],
            eligibility_refs={share_class_ids[0]: None},
        )
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseSnapshot)
    ).scalar_one() == 0


def test_member_stores_a_version_reference_not_a_value_copy():
    """D-15：fund_universe_member.investment_eligibility 存【版本引用】。

    存取值副本会引入第二份真值，两者一旦分叉无法判定谁对 ——
    这正是 Plan-1 在 adjusted_nav 标量列上花三轮才想明白的教训。
    本测试对着表结构断言，因此它在任何实现改动下都不会失真。
    """
    columns = set(FundUniverseMember.__table__.columns.keys())
    assert "investment_eligibility" not in columns, (
        "出现了取值副本列。可投资性必须以 "
        "(share_class_id, eligibility_effective_at, eligibility_version) "
        "三元组引用 fund.investment_eligibility（D-15）"
    )
    assert {"eligibility_effective_at", "eligibility_version"} <= columns


def test_undersized_universe_is_recorded_then_blocked(
    db_session, committed_peer_group_snapshot, share_class_ids
):
    """规模不足：快照【照常留痕】并标 INSUFFICIENT_UNIVERSE，由调用方阻断。

    与 fund_ranking 的 INSUFFICIENT_SAMPLE 同理 ——「当时池子太小」
    本身是需要留存的事实；不落库会让历史查询无法区分它与「当时没跑」。
    但它【不得】被当作一个可用的 Universe 继续下发（§19：显式失败并阻断）。
    """
    writer = UniverseSnapshotWriter(db_session)
    snapshot_id = writer.write(
        decision_at=DECISION_AT,
        peer_group_snapshot_id=committed_peer_group_snapshot,
        selection_policy_version="sel-v1", condition_version="v1",
        min_universe_size=30,
        outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED)],
        eligibility_refs={share_class_ids[0]: None},
    )
    snapshot = db_session.get(FundUniverseSnapshot, snapshot_id)
    assert snapshot.universe_status == "INSUFFICIENT_UNIVERSE"
    assert snapshot.selected_count == 1
```

```python
# tests/integration/conftest.py —— 追加两个夹具（本任务新增）
import datetime as dt

import pytest

from fip.services.data_service.models.fund import Fund, FundShareClass


@pytest.fixture()
def share_class_ids(db_session) -> list[int]:
    """三只可引用的份额类别。FK 目标必须真实存在，不能用假 id。"""
    fund = Fund(product_name="测试产品")
    db_session.add(fund)
    db_session.flush()
    ids = []
    for code in ("A", "C", "E"):
        share_class = FundShareClass(fund_id=fund.id, share_class_code=code,
                                     display_name=f"测试产品{code}")
        db_session.add(share_class)
        db_session.flush()
        ids.append(share_class.id)
    return ids


@pytest.fixture()
def committed_peer_group_snapshot(db_session) -> int:
    """一个【已提交】的 B1 快照 id。

    db_session 以 join_transaction_mode="create_savepoint" 运行，
    这里的 commit 只释放/重开一个 SAVEPOINT，外层事务仍由 fixture 兜底回滚
    （见 tests/conftest.py 的说明）—— 因此对被测代码而言它是「已提交的」，
    而测试之间仍互不污染。
    """
    from fip.services.fund_service.models.evaluation import PeerGroupSnapshot

    snapshot = PeerGroupSnapshot(
        classification_key="AKSHARE_FUND_TYPE|混合型|CNY",       # PF-7
        classification_scheme="AKSHARE_FUND_TYPE", classification_level="L1",
        classification_code="混合型",
        base_currency="CNY", effective_at=dt.date(2026, 8, 31), version=1,
        member_count=3, classification_policy_version="cls-v1",
    )
    db_session.add(snapshot)
    db_session.commit()
    return snapshot.id
```

- [ ] **Step 5: 运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_universe_snapshot.py -q -m integration`

Expected: `ModuleNotFoundError: No module named 'fip.services.fund_service.universe'`。
若 Task 8 的建表已完成而 `fund_universe_member` 上没有
`eligibility_effective_at` / `eligibility_version` 两列，
`test_member_stores_a_version_reference_not_a_value_copy` 会以 AssertionError 失败 ——
那说明 Task 8 漏了 D-15 的落地形态，回去补迁移，**不要在这里改测试**。

- [ ] **Step 6: 实现 B2 原子写入**

```python
# src/fip/services/fund_service/universe.py
"""B2 · Universe Snapshot 的原子写入。

一致性边界（01-system-architecture §10.3）：
    B1 (Peer Group Snapshot)  ← 原子写入，产生快照 ID
            ↓ 被引用
    B2 (Universe Snapshot)    ← 原子写入，引用【已提交的】 B1 快照 ID

B1 与 B2 【不要求同一事务】——文档说的是「三个边界各自原子，且按顺序依赖」。
B2 只需在自己的事务内引用一个已提交的 B1 快照 ID。

本模块只做编排与持久化：入池与否、条件怎么算，全部在
strategy_library/universe/rules.py 里（C-11）。
"""

import datetime as dt
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.strategy_library.universe.rules import (
    ConditionResult,
    SelectionOutcome,
    SelectionStatus,
)
from fip.services.fund_service.models.evaluation import (
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
    SelectionConditionResult,
)


class PeerGroupSnapshotMissing(RuntimeError):
    """引用了一个不存在的 B1 快照 ID。

    响亮失败而不是建一个悬空引用：FR-PEER-002 要求「未留存快照的时点，
    系统必须拒绝提供推算结果」，一个引用不到 B1 的 B2 正是那种时点。
    """


class UniverseSnapshotWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        *,
        decision_at: dt.date,
        peer_group_snapshot_id: int,
        selection_policy_version: str,
        condition_version: str,
        min_universe_size: int,
        outcomes: Sequence[SelectionOutcome],
        eligibility_refs: Mapping[int, tuple[dt.date, int] | None],
    ) -> int:
        """写一次 B2。返回快照 id。

        事务范围（digest §4.3）：`fund_universe_snapshot` 1 行
        + `fund_universe_member` M 行（【含 REJECTED】，M ≈ 候选集规模而非入池数）
        + `selection_condition_result` M × K 行（K = 条件数，【存全部条件】），
        一并提交。任一步失败则整体回滚，本次决策视为未产生。

        eligibility_refs 传的是【版本引用】而不是取值副本（D-15）：
        (effective_at, version) 二元组，与成员自己的 share_class_id 组成
        指向 fund.investment_eligibility 的复合外键。None 表示该时点
        按 available_at <= decision_at 取不到任何一版 —— 如实留空，
        不得回填一个「最近的」版本（那是前视偏差）。
        """
        if self._session.execute(
            select(PeerGroupSnapshot.id).where(
                PeerGroupSnapshot.id == peer_group_snapshot_id)
        ).scalar_one_or_none() is None:
            raise PeerGroupSnapshotMissing(
                f"B1 快照 id={peer_group_snapshot_id} 不存在或尚未提交；"
                "B2 必须引用一个已提交的 B1 快照（01-system-architecture §10.3）"
            )

        selected = sum(
            1 for o in outcomes if o.selection_status is SelectionStatus.SELECTED
        )
        with self._session.begin_nested():
            snapshot = FundUniverseSnapshot(
                decision_at=decision_at,
                peer_group_snapshot_id=peer_group_snapshot_id,
                selection_policy_version=selection_policy_version,
                condition_version=condition_version,
                candidate_count=len(outcomes),
                selected_count=selected,
                universe_status=(
                    "NORMAL" if selected >= min_universe_size
                    else "INSUFFICIENT_UNIVERSE"
                ),
            )
            self._session.add(snapshot)
            self._session.flush()

            # 排序钉死写入顺序：同一批 outcomes 无论以什么顺序传进来，
            # 落库的行顺序都相同，便于逐行比对两次运行的结果（G-2）。
            for outcome in sorted(outcomes, key=lambda o: o.share_class_id):
                ref = eligibility_refs.get(outcome.share_class_id)
                member = FundUniverseMember(
                    fund_universe_snapshot_id=snapshot.id,
                    share_class_id=outcome.share_class_id,
                    selection_status=outcome.selection_status.value,
                    constraint_note=outcome.constraint_note,
                    eligibility_effective_at=None if ref is None else ref[0],
                    eligibility_version=None if ref is None else ref[1],
                )
                self._session.add(member)
                self._session.flush()
                self._write_condition_results(member.id, outcome.condition_results)
        return snapshot.id

    def _write_condition_results(
        self, member_id: int, results: Sequence[ConditionResult]
    ) -> None:
        """逐条件明细。【全部条件】都写，不只写未通过项（D-17）。

        「只存未通过项 → 无法回答『这只基金通过了哪些条件』，
          也无法区分『通过了』与『根本没评估』，
          而后者会在条件集变更时大量出现」（04-database-design §10.3.1）。
        """
        for result in results:
            self._session.add(
                SelectionConditionResult(
                    fund_universe_member_id=member_id,
                    condition_id=result.condition_id,
                    condition_version=result.condition_version,
                    condition_status=result.status.value,
                    actual_value=result.actual_value,
                    gap=result.gap,
                )
            )
        self._session.flush()
```

- [ ] **Step 7: 落 Selection Policy 配置**

```yaml
# config/policy/evaluation/v1.yaml —— 继续追加
selection:
  universe_strategy:
    # digest §2.6：spec 说了「三种构成策略」推到 M2，但【全仓没有一处写下
    # 「策略 A」三个字】。M1 做的是「仅 Eligibility Rules」= 策略 A，
    # 这是推断不是引用，故标 PROVISIONAL。策略 A 下评分字段为空是正常情况，
    # 不构成留痕缺失（05-fund-selection:147）。
    value: A
    status: PROVISIONAL
    source: "digest §2.6 / BLOCK-3：spec 未点名 M1 用哪种构成策略"
  min_universe_size:
    value: 30
    status: PROVISIONAL
    source: "05-fund-selection §11.1 推荐默认（与 MIN_PEER_GROUP_SIZE 同值），业务方可改"
  data_completeness_floor:
    # 【Ruling PF-4】M1 取 0.75，PROVISIONAL。M2 恢复 REL 后必须改回 0.8。
    value: "0.75"
    status: PROVISIONAL
    source: |
      上游的 0.8 是在【五子分齐全】的前提下定的；M1 刻意把 Benchmark 建模推到 M2
      （spec §6.2），使 REL 三因子【结构性】不可算，data_completeness 恒为 10/13。
      把一个为完整系统设计的阈值套到一个【被刻意裁剪过】的系统上是范畴错误 ——
      它度量的本该是『数据缺失』，在 M1 却度量成了『范围裁剪』。
      M2 恢复 REL 后必须改回 0.8。
  investment_eligibility_handling:
    FULLY_ELIGIBLE:
      value: ADMIT
      status: DECIDED
      source: "05-fund-selection §9.3"
    HOLD_ONLY:
      value: ADMIT_WITH_CONSTRAINT
      status: DECIDED
      source: "§9.2：不可建仓 ≠ 移出 Universe，否则已持仓可能被优化器强制清仓"
    LIMITED:
      value: ADMIT_WITH_CONSTRAINT
      status: DECIDED
      source: "§9.3"
    EXIT_ONLY:
      value: EXCLUDE
      status: DECIDED
      source: "§9.3 已定案 2026-08-27：EXIT_ONLY 不入池（推翻了 §9.3 表格原值）"
    NOT_TRADABLE:
      value: EXCLUDE
      status: DECIDED
      source: "§9.3；§19 Edge Case 要求排除但在被拒清单留痕"
```

- [ ] **Step 8: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_eligibility_rules.py tests/integration/test_universe_snapshot.py -v -m "integration or not integration"`

Expected: 全部通过。特别核对
`test_every_condition_is_actually_invoked_not_padded`（不短路的强证据）与
`test_b2_is_atomic_nothing_survives_a_partial_write`（D-18）在 PASSED 列表里。

Run: `.venv/bin/alembic -x db=dev revision --autogenerate -m "probe" --sql | head -40`

Expected: 报告零操作（G-16）。本任务不建表，若这里出现任何 ADD/DROP，
说明 Task 8 的 ORM 与迁移不一致，回 Task 8 修，**不要在本任务加迁移**。
探针产生的临时 revision 文件用完即删。

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "feat(universe): Eligibility Rules 求值与 B2 候选池快照

条件求值不得短路：全部条件一律求值并落库，含 REJECTED 成员（D-17/G-11），
由 spy 测试证明每个条件都真的被调用过，而不是短路后补齐占位行。
四种可投资性四种动作：FULLY_ELIGIBLE 入池、HOLD_ONLY/LIMITED 入池并标注约束、
EXIT_ONLY 不入池、NOT_TRADABLE 排除但在被拒清单留痕。
投资性以 (share_class_id, effective_at, version) 版本引用而非取值副本（D-15）。
B2 原子写入并引用已提交的 B1 快照 ID，写入不完整整体回滚（D-18）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 17: `factor_service` / `fund_service` 装配 + SB-1 适应度测试

> 依赖 Task 16。本任务把 Task 9–16 的纯函数接到 Plan-1 的 PIT 端口与数据库上，
> 并补上 Plan-1 最终评审点名「静默缺席」的 SB-1。
>
> **SB-1 在 M1 是空洞的**：只有一个写入方（`IngestService`）时，「每个 schema
> 写入权唯一」永远成立。Plan-2 引入 `factor_service`（写 `factor`）与
> `fund_service`（写 `evaluation`）之后，它**第一次有真实约束力** ——
> 而恰恰在这一刻，最省事的写法（fund_service 顺手把因子值补写一行）
> 会永久地把两个 schema 的写入权搅在一起。

**Files:**
- Create: `src/fip/platform/config/evaluation_policy.py`
- Create: `src/fip/services/factor_service/compute.py`
- Create: `src/fip/services/factor_service/repositories/__init__.py`
- Create: `src/fip/services/factor_service/repositories/factor_value.py`
- Create: `src/fip/services/fund_service/evaluate.py`
- Test: `tests/fitness/test_schema_write_ownership.py`
- Test: `tests/integration/test_schema_write_ownership.py`
- Test: `tests/integration/test_evaluation_pipeline.py`

**Interfaces:**

- Consumes:
  - `fip.platform.decision_data.pit.PitDataContext`、`fip.platform.decision_data.context.DecisionExecutionContext`（Plan-1）
  - `fip.platform.config.loader.load_config_file` / `ConfigSet`（Plan-1）
  - `fip.strategy_library.factor.compute.compute_factor`、`FactorInput`、`FactorResult`（Task 9）
  - `fip.strategy_library.factor.normalize.percentile_rank`（Task 12）
  - `fip.strategy_library.score.subscore.*`（Task 14）
  - `fip.strategy_library.ranking.rank.*`（Task 15）
  - `fip.strategy_library.universe.rules.*`、`fip.services.fund_service.universe.UniverseSnapshotWriter`（Task 16）
  - `fip.services.data_service.eligibility.EligibilityStatus`（Plan-1，仅用于配置校验）
- Produces:
  ```python
  # platform/config/evaluation_policy.py
  @dataclass(frozen=True, slots=True)
  class EvaluationPolicy:
      min_peer_group_size: int
      classification_level: str
      tier_thresholds: TierThresholds
      min_universe_size: int
      data_completeness_floor: Decimal
      investment_eligibility_handling: Mapping[str, EligibilityAction]
      provisional_used: tuple[str, ...]
      @classmethod
      def load(cls, config: ConfigSet) -> "EvaluationPolicy": ...

  # services/factor_service/compute.py
  WRITES_SCHEMAS: frozenset[str]          # frozenset({"factor"})
  @dataclass(frozen=True, slots=True)
  class FactorRunResult:
      run_id: int; computed: int; unavailable: int
  class FactorComputeService:
      def __init__(self, session: Session, policy: EvaluationPolicy) -> None: ...
      def run(self, context: DecisionExecutionContext,
              peer_group_snapshot_id: int, window: str) -> FactorRunResult: ...

  # services/factor_service/repositories/factor_value.py
  class FactorValueReader:
      def __init__(self, session: Session) -> None: ...
      def normalized_factors(self, run_id: int
                             ) -> dict[int, dict[str, NormalizedFactor]]: ...
      # 【Ruling PF-2】本方法【不得】自己 new NormalizedFactor。
      # 实现形态：把 factor_value 的行按 factor_id 分桶还原成
      # list[NormalizedFactorValue]（横截面视图），再交给
      # fip.strategy_library.factor.normalize.transpose_to_fund_view 转置。
      # NormalizedFactor 的构造点全仓只有转置函数一处 —— 多一处就会出现
      # 「归因视图里的字段与横截面视图对不上」，而那种错不会报错。

  # services/fund_service/evaluate.py
  WRITES_SCHEMAS: frozenset[str]          # frozenset({"evaluation"})
  @dataclass(frozen=True, slots=True)
  class EvaluationRunResult:
      scored: int; ranked: int; tiered: int; universe_snapshot_id: int | None
  class FundEvaluationService:
      def __init__(self, session: Session, policy: EvaluationPolicy,
                   profile: EvaluationProfile) -> None: ...
      def run(self, context: DecisionExecutionContext, factor_run_id: int,
              peer_group_snapshot_id: int) -> EvaluationRunResult: ...
  ```

- [ ] **Step 1: 写失败的 SB-1 静态适应度测试**

```python
# tests/fitness/test_schema_write_ownership.py
"""SB-1：每个 schema 的写入权唯一。

Plan-1 的最终评审点名这条约束「既没有实现，也没有出现在『明确不覆盖』
清单里 —— 它是静默缺席的」。M1 只有一个写入方时它空洞；Plan-2 引入
factor_service 与 fund_service 之后第一次有真实约束力。

本文件是【静态】那一半：谁定义了哪个 schema 的 ORM 模型。
【动态】那一半在 tests/integration/test_schema_write_ownership.py ——
它挂 before_flush 事件监听器，记录每个 service 实际 flush 了哪些 schema
的对象。两条缺一不可：静态检查抓不到「fund_service import 了
factor 的 model 并往里写」，动态检查抓不到「今天没走到那条代码路径」。
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
SERVICES = SRC / "services"

# spec §2.3 / G-13 的写入权分配。左边是 schema，右边是【唯一】写入方。
EXPECTED_OWNERS = {
    "raw": "data_service",
    "fund": "data_service",
    "market": "data_service",
    "governance": "data_service",
    "factor": "factor_service",
    "evaluation": "fund_service",
}


def _declared_schemas(path: pathlib.Path) -> set[str]:
    """从模块里所有 __table_args__ 的 {"schema": "..."} 字面量取 schema 名。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    schemas: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "schema"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                schemas.add(value.value)
    return schemas


def _owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for service_dir in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        for module in service_dir.rglob("*.py"):
            for schema in _declared_schemas(module):
                owners.setdefault(schema, set()).add(service_dir.name)
    return owners


def test_each_schema_has_exactly_one_declaring_service():
    shared = {s: sorted(o) for s, o in _owners().items() if len(o) > 1}
    assert not shared, (
        f"以下 schema 的 ORM 模型分散在多个 service 包中：{shared}。"
        "SB-1 要求每个 schema 的写入权唯一（G-13）。"
    )


def test_schema_owners_match_the_architecture():
    actual = {s: next(iter(o)) for s, o in _owners().items() if len(o) == 1}
    for schema, owner in EXPECTED_OWNERS.items():
        assert actual.get(schema) == owner, (
            f"schema {schema!r} 的模型定义在 {actual.get(schema)!r}，"
            f"按 spec §2.3 应属 {owner!r}"
        )


def test_expected_owner_table_is_not_stale():
    """守卫：新增 schema 却忘了登记写入权时，本条会红。

    没有它，一个新 schema 可以在两个 service 里各定义一半而两条检查全绿
    （第一条只看「是否分散」，第二条只遍历表里已有的键）。
    """
    declared = set(_owners())
    unregistered = declared - set(EXPECTED_OWNERS)
    assert not unregistered, (
        f"schema {sorted(unregistered)} 出现了 ORM 模型但未在 EXPECTED_OWNERS "
        "中登记写入权。新增 schema 必须先决定它归谁写。"
    )
```

- [ ] **Step 2: 写失败的 SB-1 运行时测试与流水线集成测试**

```python
# tests/integration/test_schema_write_ownership.py
"""SB-1 的【动态】一半：每个 service 实际写了哪些 schema。

静态检查只能证明「模型定义在哪」，证明不了「谁往里写」——
fund_service 完全可以 import factor 的 model 再 add() 一行，
静态检查对此全绿。这里挂 before_flush 监听器，记录真实的写入面。
"""
import datetime as dt
from contextlib import contextmanager

import pytest
from sqlalchemy import event

pytestmark = pytest.mark.integration


@contextmanager
def recording_written_schemas(session):
    """记录本 session 在 flush 时触碰到的全部 schema。"""
    written: set[str] = set()

    def _before_flush(sess, flush_context, instances):
        for obj in list(sess.new) + list(sess.dirty) + list(sess.deleted):
            table = getattr(type(obj), "__table__", None)
            if table is not None:
                written.add(table.schema or "public")

    event.listen(session, "before_flush", _before_flush)
    try:
        yield written
    finally:
        event.remove(session, "before_flush", _before_flush)


def test_factor_service_writes_only_the_factor_schema(
    db_session, evaluation_context, seeded_peer_group
):
    from fip.services.factor_service.compute import FactorComputeService

    with recording_written_schemas(db_session) as written:
        FactorComputeService(db_session, seeded_peer_group.policy).run(
            evaluation_context, seeded_peer_group.snapshot_id, window="3Y"
        )
    assert written == {"factor"}, (
        f"factor_service 写入了 {sorted(written)}；SB-1 要求它只写 factor schema"
    )


def test_fund_service_writes_only_the_evaluation_schema(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    from fip.services.fund_service.evaluate import FundEvaluationService

    with recording_written_schemas(db_session) as written:
        FundEvaluationService(
            db_session, seeded_peer_group.policy, seeded_peer_group.profile
        ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    assert written == {"evaluation"}, (
        f"fund_service 写入了 {sorted(written)}；SB-1 要求它只写 evaluation schema。"
        "读 factor / fund / market 是允许的，写不是。"
    )


def test_the_listener_would_actually_catch_a_violation(db_session):
    """守卫：证明监听器【看得见】违规，而不是永远返回空集合。

    一条永远为空的记录器会让上面两条测试永久为真 —— 那正是 SB-1
    在 Plan-1 里「静默缺席」的同一种失败方式，只是换了个形态。
    """
    from fip.services.data_service.models.fund import Fund

    with recording_written_schemas(db_session) as written:
        db_session.add(Fund(product_name="监听器自检"))
        db_session.flush()
    assert written == {"fund"}
```

```python
# tests/integration/test_evaluation_pipeline.py
"""因子 → 标准化 → 评分 → 排名 → 分层 → 候选池 的端到端落库。"""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from fip.services.fund_service.models.evaluation import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTier,
)

pytestmark = pytest.mark.integration


def test_pipeline_persists_score_attribution_ranking_and_tier(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    from fip.services.fund_service.evaluate import FundEvaluationService

    result = FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    assert result.scored > 0

    scores = db_session.execute(select(FundScore)).scalars().all()
    # D-19：M1 的常态是 PARTIAL（REL 子分恒 UNAVAILABLE）——
    # 落库之后这一点仍须成立，否则下游会把 PARTIAL 当异常处理。
    assert {s.score_status for s in scores} == {"PARTIAL"}
    assert all(s.relative_performance_score is None for s in scores)
    assert all(s.data_completeness == Decimal("0.76923077") for s in scores)


def test_excluded_factors_are_persisted_in_attribution_with_zero_weight(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-3 + FS §10.4：被排除的因子不得从归因中消失。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    rel_rows = db_session.execute(
        select(FundScoreAttribution).where(
            FundScoreAttribution.factor_id.like("F-REL-%"))
    ).scalars().all()
    assert rel_rows, "声明但不可算的 REL 因子在归因里消失了"
    for row in rel_rows:
        assert row.weight == Decimal("0")
        assert row.normalized_score is None
        assert row.weighted_contribution is None
        assert row.exclusion_reason


def test_ranking_persists_rank_n_effective_and_percentile_together(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-8：三者都必须落库 —— 只存 Rank 则历史分位不可还原。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    rows = db_session.execute(select(FundRanking)).scalars().all()
    assert rows
    for row in rows:
        assert row.n_effective is not None
        assert row.peer_group_size is not None
        if row.ranking_status == "NORMAL":
            assert row.rank is not None and row.percentile is not None
        else:
            assert row.rank is None and row.percentile is None


def test_tier_row_carries_the_peer_group_absolute_level(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-9：Tier 不得单独输出 —— 落库时就必须带组内 Sharpe / MDD 中位数。

    在纯函数层它是 TierResult 的必填字段；这里断言那两列真的到了库里，
    否则 API 仍然可以只查出一个孤零零的 "A+"。
    """
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    columns = set(FundTier.__table__.columns.keys())
    assert {"peer_sharpe_median", "peer_max_drawdown_median",
            "percentile", "total_score", "n_effective"} <= columns


def test_pipeline_is_reproducible_within_tolerance(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-2：同一输入重算必须一致，容差 1e-10。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    service = FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    )
    service.run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    first = {s.share_class_id: s.total_score
             for s in db_session.execute(select(FundScore)).scalars()}
    db_session.execute(FundScore.__table__.delete())
    service.run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    second = {s.share_class_id: s.total_score
              for s in db_session.execute(select(FundScore)).scalars()}
    assert set(first) == set(second)
    for key in first:
        assert abs(first[key] - second[key]) < Decimal("1e-10")


def test_eligibility_handling_config_covers_every_enum_value(seeded_peer_group):
    """配置与枚举的漂移检查。

    策略库侧刻意用 str 表达可投资性（依赖方向单向，不得 import services），
    所以「处理表是否覆盖了全部取值」只能在【允许 import 枚举的这一层】断言。
    少一个取值不会在策略库里报错，只会在运行到那只基金时抛 KeyError ——
    那时已经是生产。
    """
    from fip.services.data_service.eligibility import EligibilityStatus

    handled = set(seeded_peer_group.policy.investment_eligibility_handling)
    assert handled == {s.value for s in EligibilityStatus}
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/fitness/test_schema_write_ownership.py tests/integration/test_schema_write_ownership.py tests/integration/test_evaluation_pipeline.py -q`

Expected: 静态那一条以 AssertionError 失败（`factor` / `evaluation` 尚无 ORM 模型或
未落在对应 service 包下），另两个文件以 `ModuleNotFoundError` 失败。
两类失败都要粘进报告 —— 静态测试的失败信息尤其重要，它直接告诉你
Task 7/8 的模型放对位置了没有。

- [ ] **Step 4: 实现单一配置源**

```python
# src/fip/platform/config/evaluation_policy.py
"""Evaluation Policy 的解析点 —— G-7 的「同一配置源」就是这一个类。

标准化（Task 12）、排名（Task 15）、分层（Task 15）三处都需要
MIN_PEER_GROUP_SIZE。若三处各自 config.get("peer_group.min_sample_size")，
那就是三个配置源：调参那天只要漏改一处就会分叉，而分叉后的症状
（分位算出来了但 Tier 没产出）极难定位。因此配置路径字符串在全仓
【只出现在本文件】，tests/fitness/test_single_config_source.py 对此断言。

本模块住在 platform 层而不是某个 service 里：两个 service 都要用它，
放进任一个都会制造出一条 service → service 的依赖。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from fip.strategy_library.ranking.rank import TierThresholds
from fip.strategy_library.universe.rules import EligibilityAction
from fip.platform.config.loader import ConfigSet

_ELIGIBILITY_STATUSES = (
    "FULLY_ELIGIBLE", "HOLD_ONLY", "LIMITED", "EXIT_ONLY", "NOT_TRADABLE",
)


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    """⚠️ 这里【没有】mar 字段。

    P2-4：`config/policy/evaluation/v1.yaml` 里原有的 `mar.default: 0.0`
    直接违反 G-6（「mar_policy 必填无默认」「不得给 MAR 设兜底值」），
    由 Task 10 删除。MAR 改由 Task 10 的 Threshold Resolver 按三模式解析，
    未配置即 None —— 于是 F-RISK-002 / F-RAP-002 一律 UNAVAILABLE。
    在这里加一个 `mar: Decimal | None = Decimal("0")` 之类的兜底，
    等于把那条已经拆掉的地雷重新埋回去：「两者数值相同但含义相反，
    设默认会让配置遗漏静默产出看起来正常的 Sortino」（FE:472-481）。
    """

    min_peer_group_size: int
    classification_level: str
    tier_thresholds: TierThresholds
    min_universe_size: int
    data_completeness_floor: Decimal
    investment_eligibility_handling: Mapping[str, EligibilityAction]
    provisional_used: tuple[str, ...]

    @classmethod
    def load(cls, config: ConfigSet) -> "EvaluationPolicy":
        thresholds = TierThresholds(
            a_plus=Decimal(config.get("classification.tier_percentile_thresholds.a_plus")),
            a=Decimal(config.get("classification.tier_percentile_thresholds.a")),
            b=Decimal(config.get("classification.tier_percentile_thresholds.b")),
            c=Decimal(config.get("classification.tier_percentile_thresholds.c")),
        )
        handling = {
            status: EligibilityAction(
                config.get(f"selection.investment_eligibility_handling.{status}")
            )
            for status in _ELIGIBILITY_STATUSES
        }
        return cls(
            min_peer_group_size=int(config.get("peer_group.min_sample_size")),
            classification_level=str(config.get("peer_group.classification_level")),
            tier_thresholds=thresholds,
            min_universe_size=int(config.get("selection.min_universe_size")),
            data_completeness_floor=Decimal(
                config.get("selection.data_completeness_floor")
            ),
            investment_eligibility_handling=handling,
            # 本次装载消费到的 PROVISIONAL 参数清单，随决策快照落库
            # （spec §5.3：两种运行模式下都不阻断，但都不静默）。
            provisional_used=config.provisional_parameters_used,
        )
```

- [ ] **Step 5: 实现 factor_service（只写 factor schema）**

```python
# src/fip/services/factor_service/compute.py
"""因子计算与 Peer Group 内标准化的编排。

SB-1：本 service 是 `factor` schema 的【唯一】写入方。
它【读】fund / market（经 Plan-1 的 PIT 端口）与 evaluation.peer_group_member，
但一行都不往那些 schema 里写 —— tests/integration/test_schema_write_ownership.py
的 before_flush 监听器对此断言。

C-11：本模块只做编排与持久化。因子公式在 strategy_library/factor/compute.py，
分位公式在 factor/normalize.py，阈值判定在 factor/effectiveness.py。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.strategy_library.factor.compute import compute_factor
from fip.strategy_library.factor.definitions import (
    FACTOR_IDS,
    preference_direction,
)
# 【Ruling PF-1】只从 normalize_peer_group 取 G-8 三元组。
# 【不得】直接 import percentile_rank —— 它是纯内核，rank 与 n_effective
# 一个都不产出，绕过 normalize_peer_group 会让这两列静默落空。
from fip.strategy_library.factor.normalize import normalize_peer_group
from fip.strategy_library.factor.status import FactorStatus
from fip.platform.config.evaluation_policy import EvaluationPolicy
from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import PitDataContext
from fip.services.factor_service.models.factor import FactorRun, FactorValue

WRITES_SCHEMAS = frozenset({"factor"})


@dataclass(frozen=True, slots=True)
class FactorRunResult:
    run_id: int
    computed: int
    unavailable: int


class FactorComputeService:
    def __init__(self, session: Session, policy: EvaluationPolicy) -> None:
        self._session = session
        self._policy = policy

    def run(
        self,
        context: DecisionExecutionContext,
        peer_group_snapshot_id: int,
        window: str,
    ) -> FactorRunResult:
        """一次因子批次：逐成员算 10 个因子，再在组内做分位标准化。

        window（评价周期，如 "3Y"）是显式参数而不是从 context 里取：
        DecisionExecutionContext（Plan-1 Task 4）没有这个字段，
        而排名必须显式声明周期（FR §4.1「一次排名必须完整声明五项，
        缺一则结果无法解释」）。窗口不进 Factor ID，所以它必须进
        factor_value 的唯一键（D-13）—— 由调用方显式传入是最不容易漏的形式。

        标准化必须在 Peer Group 内进行且 Peer Group 独立于 Score 产生
        （FS §7.2 规则 1 / C-4）—— 因此这里读的是【已提交的 B1 快照成员】，
        而不是现场重新分组。
        """
        run = FactorRun(
            decision_at=context.decision_at,
            # ⚠️ strategy_version / data_version / started_at 也是 Task 7 建的
            # NOT NULL 列 —— 与 factor_value 那批漏列（Ruling PF-8）是同一形态，
            # 一并补上。data_version 来自 Plan-1 的数据版本解析（本次跑用了
            # 哪一批数据），不得用 code_version 或常量顶替。
            strategy_version=context.strategy_version,
            code_version=context.code_version,
            evaluation_policy_version=context.policy_version,
            data_version=self._data_version(context),
            peer_group_snapshot_id=peer_group_snapshot_id,
            window=window,
            status="RUNNING",
            started_at=self._now(),
        )
        self._session.add(run)
        self._session.flush()

        members = self._members(peer_group_snapshot_id)
        pit = PitDataContext(context=context, session=self._session)

        results: dict[int, dict[str, object]] = {}
        for share_class_id in members:
            inp = self._factor_input(pit, share_class_id, context)
            results[share_class_id] = {
                factor_id: compute_factor(factor_id, inp) for factor_id in FACTOR_IDS
            }

        computed = 0
        unavailable = 0
        for factor_id in FACTOR_IDS:
            # 【Ruling PF-1】标准化整组交给 normalize_peer_group —— 它是
            # G-8 三元组（rank / n_effective / percentile）的唯一权威产出点。
            # 入参是【全体成员】的 FactorResult，不是先筛过的可算子集：
            # 谁参与、谁不参与由它按 status 判定，UNAVAILABLE / INVALID
            # 的成员不参与分位计算（FS §7.4）也不得以任何值补位（G-3），
            # 但仍然逐行返回、逐行落库（reason 随之保留）。
            entries = [
                (share_class_id, per_factor[factor_id])
                for share_class_id, per_factor in sorted(results.items())
            ]
            normalized = normalize_peer_group(
                entries,
                preference_direction(factor_id),
                self._policy.min_peer_group_size,
            )
            for row in normalized:
                result = results[row.share_class_id][factor_id]
                self._session.add(
                    FactorValue(
                        factor_run_id=run.id,
                        # NOT NULL：这一行是哪一版因子定义算出来的。
                        # 漏传它 flush 直接 IntegrityError。
                        factor_version_id=self._factor_version_id(factor_id),
                        share_class_id=row.share_class_id,
                        factor_id=factor_id,
                        window=window,
                        effective_at=context.decision_at,
                        version=1,
                        raw_value=result.value,
                        # 列名以 Task 7 建表为准（Ruling PF-8）。
                        normalized_value=row.percentile,
                        status=result.status.value,
                        # status_reason 容纳 UNAVAILABLE 与 WARNING 两类理由；
                        # VALID 时必须是 None（CHECK ck_factor_value_status）。
                        status_reason=result.reason or None,
                        observation_count=result.observation_count,
                        # P2-21：链路 quality 独立成列，与 status 正交。
                        # M1 的常态是 (VALID, INFERRED)，不是 WARNING。
                        quality_flag=result.quality_flag,
                        peer_group_snapshot_id=peer_group_snapshot_id,
                        # normalized_value 非空时 peer_group 上下文必须齐备
                        # （CHECK ck_factor_value_peer_ctx / _normalized_needs_ctx）。
                        peer_group_version=self._peer_group_version(
                            peer_group_snapshot_id
                        ),
                        # R_f 溯源五列（P2-30）：要么齐备要么全空，由
                        # ThresholdResolver 的 ResolvedThresholds.risk_free_rate_ref
                        # 原样搬运，不在这里现编。
                        **self._risk_free_ref_columns(share_class_id=row.share_class_id),
                        evaluation_policy_version=context.policy_version,
                        # NOT NULL。取自本次 run，而不是现编一个 ——
                        # 「这批因子值是在哪一版数据上算的」与 factor_run
                        # 必须是同一个答案。
                        data_version=run.data_version,
                        available_at=self._available_at(context),
                        # 【Ruling PF-8】G-15：AKShare 链路一律 INFERRED。
                        # 起草期写死的 "DERIVED" 直接违反 C-12，且 DERIVED 还要求
                        # published_at IS NOT NULL（QUALITY_SOURCE_SQL），
                        # 本行根本不传 published_at —— 那条 CHECK 也会拒绝它。
                        availability_quality="INFERRED",
                        ingested_at=self._now(),
                    )
                )
                if result.status is FactorStatus.VALID:
                    computed += 1
                else:
                    unavailable += 1

        run.status = "COMPLETED"
        self._session.flush()
        return FactorRunResult(run_id=run.id, computed=computed, unavailable=unavailable)
```

> 上面的 `_members` / `_factor_input` / `_available_at` / `_now` /
> `_factor_version_id` / `_peer_group_version` / `_risk_free_ref_columns` /
> `_data_version` 八个私有方法属于 Task 7–12 已定的读取路径
> （`peer_group_member` 读取、`NavPoint` → `FactorInput` 组装、
> `factor_version` 的 PIT 解析、快照版本回读、`ResolvedThresholds`
> 的 R_f 溯源五列搬运、派生时点的 `available_at`）。它们不在本任务新增语义，
> 实现时照那几个任务的产出直接调用；若签名与此处不符，
> 以那几个任务为准并回改本节，**不得在这里另造一份读取逻辑**。
>
> `_risk_free_ref_columns` 返回的是
> `{"risk_free_rate_curve_code", "risk_free_rate_currency", "risk_free_rate_tenor",
> "risk_free_rate_version", "risk_free_rate_quality"}` 五个键，**要么五个都有值、
> 要么五个都是 None**（Task 7 的 `_RF_REF_SQL` 是 `num_nonnulls(...) IN (0, 5)`）。
>
> `_factor_input` 必须调用 `ThresholdResolver.resolve(...)` 拿到
> `mar_daily` 与 `risk_free_rate`（P2-22），并把 `NavSeries.chain_quality`
> 原样传进 `FactorInput.chain_quality`（P2-21）。

> ## ✅ 【冲突 ⑧ 已按 Ruling PF-8 裁定解决】`factor_value` 一律以 **Task 7 建表**为准
>
> 起草期本段与 Task 7 的建表对不上，照原样实现会在第一次 flush 直接
> `TypeError` / `IntegrityError`。裁定：**Task 17 无条件对齐 Task 7**，
> 上面的代码已按下表改完，冲突描述保留作记录：
>
> | 起草期本段写的 | 裁定后（= Task 7 建的列） |
> |---|---|
> | `factor_status=` | **`status`** |
> | `status_reason=`（自由文本） | **`status_reason`**（枚举列，见下） |
> | `normalized_score=` | **`normalized_value`** |
> | `availability_quality="DERIVED"` | **`availability_quality="INFERRED"`** —— 由 `VersionedMixin` 提供，G-15 要求 AKShare 链路一律 `INFERRED`；写死 `"DERIVED"` **直接违反 C-12**，且 `QUALITY_SOURCE_SQL` 要求 DERIVED 必须有 `published_at`，本段根本不传 |
> | （缺） | 已补 `factor_version_id`、`data_version`、`peer_group_version`、`risk_free_rate_*` 五列 |
>
> **列改名不只是改名**：P2-21 把 INFERRED_AVAILABILITY 从 WARNING 拿掉之后，
> `NEAR_MIN_OBS` 成了唯一的 WARNING 理由，而它**装不进**名为
> `unavailable_reason` 的枚举。因此裁定把 **Task 7 那一列改名为 `status_reason`**，
> 枚举**加入 `NEAR_MIN_OBS`**，同时容纳 UNAVAILABLE 与 WARNING 两类理由 ——
> 这是本条里唯一一处**反向**改 Task 7 的地方，其余一律 Task 17 让步。
>
> **同一段绕开 `normalize_peer_group` 的那条路径已删除**（Ruling PF-1）：
> 它直接调 `percentile_rank`，于是 `rank` / `n_effective` / `CrossSectionStatus`
> 三者一个都没算、也没落库，而 G-8 要求三者都落库。

- [ ] **Step 6: 实现 fund_service（只写 evaluation schema）**

```python
# src/fip/services/fund_service/evaluate.py
"""评分 → 排名 → 分层 → 候选池的编排。

SB-1：本 service 是 `evaluation` schema 的【唯一】写入方。
它经 FactorValueReader 【读】factor schema —— 读是允许的，写不是。
两者的区别由 tests/integration/test_schema_write_ownership.py 的
before_flush 监听器在运行时裁定，而不是靠 code review 记得。
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from fip.quant_engine.stats import median
from fip.strategy_library.ranking.rank import (
    RankingEntry,
    assign_tier,
    peer_group_absolute_level,
    rank_within_peer_group,
)
from fip.strategy_library.score.subscore import (
    EvaluationProfile,
    compute_fund_score,
)
from fip.platform.config.evaluation_policy import EvaluationPolicy
from fip.platform.decision_data.context import DecisionExecutionContext
from fip.services.factor_service.repositories.factor_value import FactorValueReader
from fip.services.fund_service.models.evaluation import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTier,
)

WRITES_SCHEMAS = frozenset({"evaluation"})

# M1 声明了但不可算的因子及其原因。这些因子【必须】出现在归因里
# （FS §10.4），因此这里为它们构造 UNAVAILABLE 的 NormalizedFactor，
# 而不是干脆不产出 —— 「从归因中消失」正是本条要防的事。
#
# 【Ruling PF-2 的唯一例外】PF-2 规定本 service 不得自己构造 NormalizedFactor。
# 这三条是例外，且理由必须写清楚：它们在 factor_value 里【一行都没有】
# （Benchmark 建模推到 M2，REL 三因子结构性不可算），因此不可能来自转置 ——
# 转置只翻转已经算过的东西，它不补齐从未存在的行（见 transpose_to_fund_view
# 的 test_转置不得凭空补齐缺失的基金）。补齐在这里发生，并且带着
# exclusion_reason，是显式的、有留痕的。
UNCOMPUTABLE_IN_M1 = {
    "F-REL-002": "Benchmark 四层建模推到 M2（spec §6.2），Alpha 不可算",
    "F-REL-003": "Benchmark 四层建模推到 M2（spec §6.2），Beta 不可算",
    "F-REL-004": "Benchmark 四层建模推到 M2（spec §6.2），Information Ratio 不可算",
}


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    scored: int
    ranked: int
    tiered: int
    universe_snapshot_id: int | None


class FundEvaluationService:
    def __init__(
        self, session: Session, policy: EvaluationPolicy, profile: EvaluationProfile
    ) -> None:
        self._session = session
        self._policy = policy
        self._profile = profile

    def run(
        self,
        context: DecisionExecutionContext,
        factor_run_id: int,
        peer_group_snapshot_id: int,
    ) -> EvaluationRunResult:
        reader = FactorValueReader(self._session)
        # 【Ruling PF-2】归因视图来自 Task 12 的 transpose_to_fund_view
        # （由 FactorValueReader 在内部调用）。本 service【不得】自己
        # 构造 NormalizedFactor —— UNCOMPUTABLE_IN_M1 那几条是唯一例外，
        # 它们是【库里根本没有的行】（REL 因子结构性不可算），不是转置的产物，
        # 见下面 _unavailable_factor 的说明。
        per_fund = reader.normalized_factors(factor_run_id)
        effectiveness = reader.effectiveness(self._profile.profile_id)

        scores = {}
        for share_class_id, factors in sorted(per_fund.items()):
            for factor_id, reason in UNCOMPUTABLE_IN_M1.items():
                factors.setdefault(factor_id, _unavailable_factor(factor_id, reason))
            scores[share_class_id] = compute_fund_score(
                self._profile, factors, effectiveness
            )
            self._write_score(context, peer_group_snapshot_id, share_class_id,
                              scores[share_class_id])

        rankings = rank_within_peer_group(
            [
                RankingEntry(share_class_id=i, profile_id=self._profile.profile_id,
                             metric_value=s.total_score)
                for i, s in sorted(scores.items())
            ],
            peer_group_size=len(per_fund),
            min_peer_group_size=self._policy.min_peer_group_size,
        )

        # G-9：组内绝对水平必须与 Tier 一同产出。取【有效】的 Sharpe 与 MDD
        # 原始值算中位数；一个都没有时是 None（UNAVAILABLE），不是 0。
        level = peer_group_absolute_level(
            sharpe_values=reader.valid_raw_values(factor_run_id, "F-RAP-001"),
            mdd_values=reader.valid_raw_values(factor_run_id, "F-RISK-003"),
        )

        tiered = 0
        for ranking in rankings:
            self._write_ranking(context, peer_group_snapshot_id, ranking)
            tier = assign_tier(
                ranking,
                total_score=scores[ranking.share_class_id].total_score,
                thresholds=self._policy.tier_thresholds,
                peer_group_level=level,
                min_peer_group_size=self._policy.min_peer_group_size,
            )
            self._write_tier(context, peer_group_snapshot_id, tier)
            tiered += 1 if tier.tier is not None else 0

        self._session.flush()
        return EvaluationRunResult(
            scored=len(scores), ranked=len(rankings), tiered=tiered,
            universe_snapshot_id=None,     # B2 由 CLI 在 Task 18 单独触发
        )

    def _write_score(self, context, peer_group_snapshot_id, share_class_id, result):
        """五子分 + 总分 + data_completeness + 逐因子归因。

        G-4：data_completeness 与分数【一起】落库、一起呈现 ——
        「基于 3 个指标的 85 分与基于 12 个指标的 85 分，可信度完全不同」。
        """
        by_name = {s.name: s for s in result.sub_scores}
        score = FundScore(
            share_class_id=share_class_id,
            effective_at=context.decision_at,
            version=1,
            profile_id=result.profile_id,
            total_score=result.total_score,
            return_score=_value(by_name, "Return"),
            risk_score=_value(by_name, "Risk"),
            risk_adjusted_score=_value(by_name, "Risk-Adjusted"),
            stability_score=_value(by_name, "Stability"),
            relative_performance_score=_value(by_name, "Relative Performance"),
            score_status=result.status.value,
            data_completeness=result.data_completeness,
            weight_source="EQUAL_WITHIN_VALID",
            peer_group_snapshot_id=peer_group_snapshot_id,
            evaluation_policy_version=context.policy_version,
            scoring_policy_version=context.strategy_version,
            available_at=context.decision_at,
            # 【Ruling PF-8 的同一条】G-15：AKShare 链路一律 INFERRED。
            # 起草期这里也写死了 "DERIVED"，与 factor_value 那处同错 ——
            # 且 QUALITY_SOURCE_SQL 要求 DERIVED 必须带 published_at，
            # 本行不传，那条 CHECK 也会拒绝它。
            availability_quality="INFERRED",
        )
        self._session.add(score)
        self._session.flush()
        for sub in result.sub_scores:
            for row in sub.attributions:
                self._session.add(
                    FundScoreAttribution(
                        fund_score_id=score.id,
                        sub_score_name=sub.name.value,
                        factor_id=row.factor_id,
                        window=row.window,
                        raw_value=row.raw_value,
                        normalized_score=row.normalized_score,
                        direction=None if row.direction is None else row.direction.value,
                        weight=row.weight,
                        weighted_contribution=row.weighted_contribution,
                        participated=row.participated,
                        exclusion_reason=row.exclusion_reason,
                        effectiveness_verdict=row.effectiveness_verdict,
                        redistributed_to=",".join(row.redistributed_to) or None,
                    )
                )
```

> `_write_ranking` / `_write_tier` / `_value` / `_unavailable_factor` 四个辅助
> 与 `_write_score` 同构：逐字段搬运，无判断逻辑。
> `_write_tier` 必须写入 `peer_sharpe_median` 与 `peer_max_drawdown_median`
> 两列 —— 它们不是可选的展示字段，是 G-9 的落库形态
> （`tests/integration/test_evaluation_pipeline.py::test_tier_row_carries_the_
> peer_group_absolute_level` 对此断言）。

- [ ] **Step 7: 运行确认通过**

Run: `.venv/bin/pytest tests/fitness tests/integration/test_schema_write_ownership.py tests/integration/test_evaluation_pipeline.py -v -m "integration or not integration"`

Expected: 全部通过。三条必须出现在 PASSED 里：
`test_each_schema_has_exactly_one_declaring_service`（SB-1 静态）、
`test_fund_service_writes_only_the_evaluation_schema`（SB-1 动态）、
`test_the_listener_would_actually_catch_a_violation`（监听器自检）。

Run: `make check`

Expected: lint、typecheck 与全部 281+ 条既有测试仍然通过（不得有回归）。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(services): factor_service / fund_service 装配与 SB-1

SB-1 在 Plan-1 里是静默缺席的（只有一个写入方时它空洞）；Plan-2 引入两个
新 service 后第一次有真实约束力，因此补两条检查：静态查 ORM 模型定义在
哪个 service 包，动态用 before_flush 监听器查每个 service 实际 flush 了
哪些 schema，并配一条自检证明监听器看得见违规。
MIN_PEER_GROUP_SIZE 的配置路径全仓只出现在 EvaluationPolicy 一处（G-7）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 18: CLI 与端到端验收

> Plan-2 的收尾。完成后可用 `fip_dev` 里的真实数据端到端验证 M1.2–M1.4 的核心能力。
>
> **环境事实**：`psql` / `createdb` **不在 PATH**，因此本任务的全部核对
> 一律走 `.venv/bin/python`（Plan-1 Task 19 的核对用的是 `psql`，照抄会得到
> `command not found`）。

**Files:**
- Modify: `src/fip/platform/cli.py`
- Test: `tests/integration/test_cli_plan2.py`

**Interfaces:**

- Consumes: `EvaluationPolicy.load`、`FactorComputeService.run`、
  `FundEvaluationService.run`、`UniverseSnapshotWriter.write`、
  `PeerGroupBuilder`（Task 11）
- Produces: CLI 子命令
  ```
  fip build-peer-groups --decision-at YYYY-MM-DD
  fip compute-factors   --decision-at YYYY-MM-DD --window 3Y
  fip evaluate          --decision-at YYYY-MM-DD --window 3Y
  fip build-universe    --decision-at YYYY-MM-DD
  fip show-evaluation   --symbol 000001 --decision-at YYYY-MM-DD
  ```

- [ ] **Step 1: 写失败的 CLI 集成测试**

```python
# tests/integration/test_cli_plan2.py
"""Plan-2 的 CLI —— 重点是 G-9 与 G-4 的【输出结构】约束。

G-9 与 G-4 不是「建议这么展示」，是可验收项：
「仅展示 Tier 而不展示组内绝对水平，视为违反本条」（FC:157）。
因此它们必须落在输出结构上，由测试断言，而不是靠写代码的人记得。
"""
import datetime as dt

import pytest

from fip.platform import cli

pytestmark = pytest.mark.integration


def test_show_evaluation_prints_tier_with_peer_group_absolute_level(
    capsys, seeded_evaluation, monkeypatch
):
    """G-9：Tier 不得单独输出，必须与组内 Sharpe 中位数 + MDD 中位数同屏。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Fund Tier" in out
    assert "组内 Sharpe 中位数" in out
    assert "组内 Maximum Drawdown 中位数" in out


def test_show_evaluation_prints_data_completeness_with_the_score(
    capsys, seeded_evaluation, monkeypatch
):
    """G-4：data_completeness 是输出必备字段，必须随 Score 一起呈现。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Total Score" in out
    assert "Data Completeness" in out
    assert "0.76923077" in out


def test_show_evaluation_renders_unavailable_not_zero(
    capsys, seeded_evaluation, monkeypatch
):
    """G-3：REL 子分必须显示为 UNAVAILABLE，不得渲染成 0 或空白。

    「0 分」与「没有这个分」在屏幕上必须能分开 —— 渲染成 0.00 会让
    读者以为这只基金相对 Benchmark 表现最差。
    """
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Relative Performance" in out
    line = next(l for l in out.splitlines() if "Relative Performance" in l)
    assert "UNAVAILABLE" in line
    assert "0.00" not in line


def test_show_evaluation_reports_missing_tier_without_inventing_one(
    capsys, seeded_small_group, monkeypatch
):
    """小样本：必须显式说「样本不足，未产出 Tier」，不得留白也不得给 D。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_small_group.session)
    cli.main(["show-evaluation", "--symbol", seeded_small_group.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "INSUFFICIENT_SAMPLE" in out
    assert "n_effective" in out


def test_build_universe_exits_nonzero_when_pool_is_undersized(
    seeded_evaluation, monkeypatch
):
    """§19：Universe 规模低于下限 → 显式失败并阻断，不得静默产出过小的池子。

    快照仍然落库（标 INSUFFICIENT_UNIVERSE，留痕），但 CLI 必须以非零
    退出码结束 —— 否则批处理脚本会把一个不合格的池子当成成功继续用。
    """
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["build-universe", "--decision-at", "2026-08-31"])
    assert excinfo.value.code != 0
    assert "INSUFFICIENT_UNIVERSE" in str(excinfo.value)
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_cli_plan2.py -q -m integration`

Expected: `AttributeError` / `argparse` 报未知子命令 `show-evaluation`。粘进报告。

- [ ] **Step 3: 实现 CLI 子命令**

```python
# src/fip/platform/cli.py —— 追加（保留 Plan-1 的三个子命令与文件顶部的
# TYPE_CHECKING 说明；platform 层【不得】在模块级 import services，
# 下面每个函数体内的延迟 import 是有意为之，见文件顶部注释）

import pathlib

CONFIG_ROOT = pathlib.Path(__file__).resolve().parents[3] / "config"


def _policy():
    """装载 Evaluation Policy。PROVISIONAL 参数的使用会被如实记录/告警。"""
    from fip.platform.config.evaluation_policy import EvaluationPolicy
    from fip.platform.config.loader import load_config_file

    config = load_config_file(
        CONFIG_ROOT / "policy" / "evaluation" / "v1.yaml", RuntimeMode.BACKTEST
    )
    return EvaluationPolicy.load(config)


def _context(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id=f"CLI-{decision_at}",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="cli",
        policy_version="cli",
        code_version="cli",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def cmd_compute_factors(args: argparse.Namespace) -> None:
    from fip.services.factor_service.compute import FactorComputeService

    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        result = FactorComputeService(session, _policy()).run(
            _context(decision_at), snapshot_id, window=args.window
        )
        session.commit()
    print(f"因子批次 {result.run_id}：VALID {result.computed} 条、"
          f"非 VALID {result.unavailable} 条（后者【不是】0，是如实的不可用）")


def cmd_evaluate(args: argparse.Namespace) -> None:
    from fip.services.fund_service.evaluate import FundEvaluationService

    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        run_id = _latest_factor_run(session, decision_at, args.window)
        result = FundEvaluationService(session, _policy(), _profile()).run(
            _context(decision_at), run_id, snapshot_id
        )
        session.commit()
    print(f"评分 {result.scored} 只、排名 {result.ranked} 条、产出 Tier {result.tiered} 只")
    if result.tiered == 0:
        # 不是错误：新成立的细分类别天然样本少（FR:358）。但必须说出来，
        # 否则「一个 Tier 都没有」看起来像跑失败了。
        print("  未产出任何 Tier —— n_effective < MIN_PEER_GROUP_SIZE，"
              "按 FC §8.5 不产出而非给低置信标记")


def cmd_build_universe(args: argparse.Namespace) -> None:
    from fip.services.fund_service.universe import UniverseSnapshotWriter

    decision_at = dt.date.fromisoformat(args.decision_at)
    policy = _policy()
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        outcomes, refs = _select_candidates(session, decision_at, policy)
        universe_id = UniverseSnapshotWriter(session).write(
            decision_at=decision_at,
            peer_group_snapshot_id=snapshot_id,
            selection_policy_version="cli",
            condition_version="v1",
            min_universe_size=policy.min_universe_size,
            outcomes=outcomes,
            eligibility_refs=refs,
        )
        session.commit()
        selected = sum(1 for o in outcomes
                       if o.selection_status.value == "SELECTED")
    rejected = len(outcomes) - selected
    print(f"Universe 快照 {universe_id}：入池 {selected} 只、"
          f"被拒 {rejected} 只（被拒成员与全部条件结果均已落库）")
    if selected < policy.min_universe_size:
        # 快照已留痕（universe_status = INSUFFICIENT_UNIVERSE），但本期
        # 组合构建必须被阻断：不得降级为「用更少的基金优化」。
        raise SystemExit(
            f"INSUFFICIENT_UNIVERSE：入池 {selected} 只 < 下限 "
            f"{policy.min_universe_size} 只。快照已落库留痕，但本期决策阻断 —— "
            "不得静默产出过小的池子，也不得降级为用更少的基金优化。"
        )


def cmd_show_evaluation(args: argparse.Namespace) -> None:
    """一只基金的评价全貌。

    ⚠️ 这个函数的【输出结构】本身是可验收项，不是展示偏好：
      · G-9：Tier 必须与组内 Sharpe 中位数 + MDD 中位数同屏，
        「仅展示 Tier 而不展示组内绝对水平，视为违反本条」（FC:157）
      · G-4：data_completeness 必须随 Score 呈现
      · G-3：UNAVAILABLE 渲染成 "UNAVAILABLE"，不得渲染成 0.00 或空白
    删掉其中任何一行都会让 tests/integration/test_cli_plan2.py 变红。
    """
    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        view = _evaluation_view(session, share_class.id, decision_at)

    if view is None:
        raise SystemExit(
            f"{args.symbol} 在 decision_at={decision_at} 没有评价结果。"
            "未留存快照的时点系统必须拒绝提供推算结果（FR-PEER-002），"
            "不会现场重算一个『今天的值』充数。"
        )

    print(f"{share_class.display_name}  @ decision_at={decision_at}")
    print(f"  Profile            {view.profile_id}")
    print(f"  Total Score        {_render(view.total_score)}   "
          f"score_status={view.score_status}")
    print(f"  Data Completeness  {_render(view.data_completeness)}"
          f"   （分母 = Profile 声明的因子数，含声明但不可算的 REL 三项）")
    for name, value in view.sub_scores:
        print(f"    {name:<22} {_render(value)}")
    print(f"  Rank / N           {_render(view.rank)} / {view.n_effective}"
          f"   （组规模 {view.peer_group_size}）")
    print(f"  Percentile         {_render(view.percentile)}")
    print(f"  Fund Tier          {_render(view.tier)}   "
          f"classification_status={view.classification_status}")
    # ↓ 这两行是 G-9 的强制缓解措施，不得删除、不得折叠到 --verbose 之后。
    print(f"    组内 Sharpe 中位数            {_render(view.peer_sharpe_median)}")
    print(f"    组内 Maximum Drawdown 中位数  {_render(view.peer_mdd_median)}")
    print("  归因（逐因子，含被排除项）：")
    for row in view.attributions:
        mark = " " if row.participated else "×"
        print(f"    {mark} {row.factor_id:<12} raw={_render(row.raw_value):>14}  "
              f"norm={_render(row.normalized_score):>14}  "
              f"w={row.weight}  contrib={_render(row.weighted_contribution)}"
              + (f"  ← {row.exclusion_reason}" if row.exclusion_reason else ""))


def _render(value: object | None) -> str:
    """None 一律渲染成 UNAVAILABLE。

    这是 G-3 在展示层的落地：把 None 渲染成 "0.00" 或 "" 会让
    「不可得」冒充「等于 0」或「等于空」。C-6 的同一条原则。
    """
    return "UNAVAILABLE" if value is None else str(value)
```

```python
# src/fip/platform/cli.py —— main() 中追加子命令注册
    p_pg = sub.add_parser("build-peer-groups", help="按分类与币种构建 Peer Group（B1）")
    p_pg.add_argument("--decision-at", required=True, dest="decision_at")
    p_pg.set_defaults(func=cmd_build_peer_groups)

    p_factor = sub.add_parser("compute-factors", help="计算 10 个因子并在组内标准化")
    p_factor.add_argument("--decision-at", required=True, dest="decision_at")
    p_factor.add_argument("--window", required=True,
                          help="评价周期，如 3Y。排名必须显式声明周期（FR §4.1）")
    p_factor.set_defaults(func=cmd_compute_factors)

    p_eval = sub.add_parser("evaluate", help="五子分 / 归因 / 排名 / 分层")
    p_eval.add_argument("--decision-at", required=True, dest="decision_at")
    p_eval.add_argument("--window", required=True)
    p_eval.set_defaults(func=cmd_evaluate)

    p_universe = sub.add_parser("build-universe", help="Eligibility Rules 与候选池快照（B2）")
    p_universe.add_argument("--decision-at", required=True, dest="decision_at")
    p_universe.set_defaults(func=cmd_build_universe)

    p_show = sub.add_parser("show-evaluation", help="一只基金的评价全貌")
    p_show.add_argument("--symbol", required=True)
    p_show.add_argument("--decision-at", required=True, dest="decision_at")
    p_show.set_defaults(func=cmd_show_evaluation)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/pytest tests/integration/test_cli_plan2.py -v -m integration`

Expected: 五条全部通过。

- [ ] **Step 5: 端到端跑一遍真实数据**

前置：Task 6 的批量灌数已完成（目标 ≥ 300 只份额类别，D-2）。
若尚未完成，本步仍要跑 —— 它会走到小样本分支，那本身是判据 **A-3** 的一半。

```bash
.venv/bin/fip build-peer-groups --decision-at 2026-08-31
.venv/bin/fip compute-factors   --decision-at 2026-08-31 --window 3Y
.venv/bin/fip evaluate          --decision-at 2026-08-31 --window 3Y
.venv/bin/fip build-universe    --decision-at 2026-08-31 || echo "退出码 $? —— 见判据 A-4"
.venv/bin/fip show-evaluation   --symbol 000001 --decision-at 2026-08-31
```

- [ ] **Step 6: 五条可验收判据（真实数据，全部用 python 核对——psql 不在 PATH）**

**A-1 · `UNAVAILABLE` 未被任何填充值替代（G-3）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    filled = conn.execute(text("""
        SELECT count(*) FROM evaluation.fund_score_attribution
        WHERE participated IS FALSE
          AND (normalized_score IS NOT NULL
               OR weighted_contribution IS NOT NULL
               OR weight <> 0
               OR exclusion_reason IS NULL)
    """)).scalar_one()
    rel_scored = conn.execute(text("""
        SELECT count(*) FROM evaluation.fund_score
        WHERE relative_performance_score IS NOT NULL
    """)).scalar_one()
    ghost = conn.execute(text("""
        SELECT count(*) FROM factor.factor_value
        WHERE factor_status <> 'VALID' AND raw_value IS NOT NULL
    """)).scalar_one()
    print(f"被排除却带值/带权重/无原因的归因行 = {filled}（必须为 0）")
    print(f"REL 子分被填了值的 fund_score 行 = {rel_scored}（必须为 0）")
    print(f"非 VALID 却带 raw_value 的因子值 = {ghost}（必须为 0）")
PY
```

Expected: 三个数**全为 0**。任何一个非 0 都意味着某处用值补了「不可得」——
这正是 G-3 与 C-6 要防的静默污染。

**A-2 · M1 的常态是 `PARTIAL`，且 `data_completeness` 反映缺失的 REL 子分（D-19 / G-4）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    for row in conn.execute(text("""
        SELECT score_status, data_completeness, count(*)
        FROM evaluation.fund_score GROUP BY 1, 2 ORDER BY 3 DESC
    """)):
        print(row)
PY
```

Expected: 只有一行 `('PARTIAL', Decimal('0.76923077'), N)`（N = 参与评分的份额类别数）。
`COMPLETED` 出现即错误（M1 没有 Benchmark，五子分不可能齐全）；
`data_completeness = 1.0` 出现即错误（分母漏算了声明但不可算的 REL 三项，
「基于 4 个子分的 85 分与基于 5 个子分的 85 分」就此不可区分）；
`VALIDATION_PENDING` 出现说明 Task 13 的 `factor_effectiveness` 没跑出来。

**A-3 · `Rank` / `n_effective` / `Percentile` 三者落库且分位可反算（G-8）**

```bash
.venv/bin/python - <<'PY'
from decimal import Decimal
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT rank, n_effective, percentile, ranking_status
        FROM evaluation.fund_ranking
    """)).all()
    assert rows, "fund_ranking 一行都没有 —— 排名根本没落库"
    bad = []
    for rank, n, percentile, status in rows:
        if status == 'INSUFFICIENT_SAMPLE':
            if rank is not None or percentile is not None or n is None:
                bad.append(("样本不足行的形态不对", rank, n, percentile))
            continue
        expected = (Decimal(n - rank) / Decimal(n - 1) * 100)
        if abs(expected - percentile) > Decimal("1e-8"):
            bad.append(("分位反算不上", rank, n, percentile, expected))
    print(f"总行数 {len(rows)}，异常 {len(bad)}：{bad[:5]}")
PY
```

Expected: 异常数 **0**。这条判据的意义在于：只存 Rank 而不存 `N` 与 Percentile 时，
历史分位【不可还原】（FR:433）——反算能对上，证明三者是一致地落了库，
而不是其中某一个被事后重算出来的。

**A-4 · `REJECTED` 留痕，且条件求值未被短路（D-17 / G-11）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    print("成员状态分布：", conn.execute(text("""
        SELECT selection_status, count(*) FROM evaluation.fund_universe_member
        GROUP BY 1
    """)).all())
    uneven = conn.execute(text("""
        SELECT count(*) FROM (
            SELECT m.id, count(r.id) AS k
            FROM evaluation.fund_universe_member m
            LEFT JOIN evaluation.selection_condition_result r
                   ON r.fund_universe_member_id = m.id
            GROUP BY m.id
        ) t
        WHERE t.k <> (SELECT max(k) FROM (
            SELECT count(*) AS k FROM evaluation.selection_condition_result
            GROUP BY fund_universe_member_id) x)
    """)).scalar_one()
    copies = conn.execute(text("""
        SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'evaluation'
          AND table_name = 'fund_universe_member'
          AND column_name = 'investment_eligibility'
    """)).scalar_one()
    print(f"条件结果行数与其他成员不一致的成员数 = {uneven}（必须为 0）")
    print(f"可投资性取值副本列 = {copies}（必须为 0，D-15 只存版本引用）")
PY
```

Expected: `REJECTED` 计数 **> 0**（一只被拒的都没有，说明规则形同虚设或被拒的没落库）；
条件行数不一致的成员数 **0**（每只候选的条件行数都等于条件集大小 K ——
短路求值会让被拒基金只有 1 行）；取值副本列 **0**。

> ✅ **【已按 Ruling PF-4 更新】`SELECTED` 计数【不再】恒为 0。**
>
> 起草期这里登记的是：`data_completeness_floor = 0.8`（上游 DECIDED）> M1 的
> `data_completeness = 10/13 = 0.76923077`（D-24），于是 `COND-COMPLETENESS`
> 对**每一只**基金都判 FAIL、B2 候选池**恒为空**。PF-4 裁定 M1 的 floor 取
> `0.75`（PROVISIONAL），`0.76923077 > 0.75`，该条件对完备度正常的基金判 PASS。
>
> **因此本判据的期望值变了**：`SELECTED` 计数 **> 0**。
> 若仍为 0，那**是**一个需要排查的信号，不再是「已知的完备度问题」。
> 排查方法不变：
>
> ```sql
> SELECT r.condition_id, r.status, count(*)
> FROM evaluation.selection_condition_result r
> GROUP BY 1, 2 ORDER BY 1, 2;
> ```
>
> - `COND-COMPLETENESS` 仍然全 `FAIL` → **先查 floor 的实际装载值**：
>   `config/policy/evaluation/v1.yaml` 的 `selection.data_completeness_floor`
>   必须是 `0.75` / `PROVISIONAL`（PF-4）。若那里已经是 0.75 而条件仍全 FAIL，
>   说明 `data_completeness` 的分母出了问题，回查 D-24 与判据 A-2。
> - **链路故障**：多条条件同时全 `FAIL`，或出现 `NOT_EVALUABLE` 泛滥
>   （输入 `UNAVAILABLE` 所以判不了）→ 判据**不通过**，去查上游。
>
> ⚠️ **报告里仍须写明** floor 是 PROVISIONAL 的 0.75 而非上游的 0.8，
> 并附 PF-4 的理由原文 —— M2 恢复 REL 之后必须改回 0.8。

**A-5 · CLI 端到端 + G-9 同屏 + 可复现性（G-2）**

```bash
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2026-08-31 | tee /tmp/eval-1.txt
.venv/bin/fip evaluate --decision-at 2026-08-31 --window 3Y
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2026-08-31 | tee /tmp/eval-2.txt
diff /tmp/eval-1.txt /tmp/eval-2.txt && echo "重算逐字一致"
```

Expected:
1. 输出中同时出现 `Fund Tier`、`组内 Sharpe 中位数`、`组内 Maximum Drawdown 中位数`
   三行 —— 缺任一行即违反 G-9（`FC:157`「仅展示 Tier 而不展示组内绝对水平，
   视为违反本条」）；
2. `Relative Performance` 那一行显示 `UNAVAILABLE` 而**不是** `0.00`；
3. `Data Completeness` 与 `Total Score` 同屏出现；
4. 两次输出 `diff` 为空 —— 同一 `decision_at` 重算逐字一致（G-2 的容差 1e-10
   在这里被收紧成逐位相同，因为输入完全未变）。

再把 `--decision-at` 往前挪一年重跑，核对**时点单调性**：

```bash
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2025-08-31
```

Expected: 要么给出一份**不同**的评价（当时可见的数据更少，
`n_effective` 与 `data_completeness` 都不应更大），要么明确报
「该时点没有评价结果」并以非零退出码结束 —— **不得**返回与 2026 相同的结果
（那意味着评价没有按 `available_at <= decision_at` 解析，是前视偏差），
也**不得**现场重算一个「今天的值」冒充当时的快照（FR-PEER-002）。

- [ ] **Step 7: 全量检查**

Run: `make check && .venv/bin/pytest tests/contract -v -m contract`

Expected: lint、typecheck、全部单元/集成/适应度/契约测试通过，
既有 281 条一条不少。

Run: `.venv/bin/alembic -x db=dev revision --autogenerate -m "final-probe" --sql | head -60`

Expected: 报告零操作（G-16）。探针文件用完即删。

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot -q`

Expected: 通过。若 Task 7/8 改动过 CHECK 约束而没重新生成黄金快照，这里会红
（G-17：autogenerate 对 CHECK 表达式失明，这条快照才是防线）。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(cli): Plan-2 端到端 —— 因子、评分、排名、分层与候选池

show-evaluation 的输出结构本身是可验收项：Tier 与组内 Sharpe / MDD 中位数
同屏（G-9），Data Completeness 与 Score 同屏（G-4），UNAVAILABLE 渲染为
UNAVAILABLE 而非 0.00（G-3），三者均由测试断言。
Universe 规模不足时快照留痕但 CLI 以非零退出码阻断。
全部核对改用 python 而非 psql（本机 psql 不在 PATH）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

