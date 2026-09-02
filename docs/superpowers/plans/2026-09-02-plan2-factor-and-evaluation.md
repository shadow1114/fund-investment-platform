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

db/migrations/versions/      # 0016（分类表开放区间索引）、0017（factor）、0018（evaluation）
config/strategy/metric/v1.yaml       # 因子口径（追加）
config/strategy/factor/v1.yaml       # 因子清单与 Factor Usage（新建）
config/policy/evaluation/v1.yaml     # MAR / peer_group 粒度 / 阈值（追加）
config/policy/validation/v1.yaml     # IC/ICIR 阈值（新建）
```

## 任务总览与接口契约

> **接口契约由本计划统一给定。** 每个任务的实现者只看到自己那一节，
> 因此凡跨任务使用的名字、签名与类型，一律在此定义，任务内不得另行发明。

| # | 任务 | 依赖 |
|---|---|---|
| 1 | Plan-1 交接：`visible_until` 归位 + IntervalMixin 生成器适应度测试 + 交接项四的三处约束 + autogenerate 闸门自动化 | — |
| 2 | 收紧 PIT 数据契约：`NavPoint` 类型收窄 + 链路 quality 聚合 | 1 |
| 3 | `quant_engine` 填实 + QE-1 适应度测试 | — |
| 4 | `strategy_library` 骨架 + SDL-1/2/3 适应度测试 + Code Version 计算 | 3 |
| 5 | 基金分类灌入（`基金类型` → `fund_classification_history`）+ 迁移 0016 | 4 |
| 6 | 批量灌数 ≥300 份额类别；`AdjustedNavUnavailable` 保护下沉到 service | 5 |
| 7 | `factor` schema 五张表 + 迁移 0017 | — |
| 8 | `evaluation` schema 九张表 + 迁移 0018 | 7 |
| 9 | 10 个因子的纯函数 + Metric Version 登记 | 3, 4 |
| 10 | Threshold Resolver（R_f 灌数 + PIT 解析 + MAR 三模式）+ 删除 `mar.default` | 4, 7 |
| 11 | Peer Group 构建与 B1 快照原子写入 + **改写 C-4 两条测试**（P2-2） | 5, 8 |
| 12 | 因子标准化（Percentile Rank + 方向转换） | 9, 11 |
| 13 | 因子有效性检验（IC / ICIR） | 12 |
| 14 | 五子分 + 归因 + Data Completeness | 13 |
| 15 | 排名 / 分位 / Fund Tier | 14 |
| 16 | Eligibility Rules + B2 候选池快照（含 REJECTED） | 15 |
| 17 | `factor_service` / `fund_service` 装配 + SB-1 适应度测试 | 16 |
| 18 | CLI 与端到端验收 | 17 |

### 跨任务接口契约（**唯一权威定义**）

```python
# ---- quant_engine（Task 3 产出，Task 9/12/13 消费）----
def returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]: ...
def stdev(xs: Sequence[Decimal], ddof: int) -> Decimal: ...
def mean(xs: Sequence[Decimal]) -> Decimal: ...
def median(xs: Sequence[Decimal]) -> Decimal: ...
def running_max(xs: Sequence[Decimal]) -> list[Decimal]: ...
def rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]: ...
def spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal: ...

# ---- strategy_library/factor（Task 9 产出）----
class FactorStatus(StrEnum):
    VALID = "VALID"; WARNING = "WARNING"; INVALID = "INVALID"; UNAVAILABLE = "UNAVAILABLE"

class PreferenceDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"; LOWER_IS_BETTER = "LOWER_IS_BETTER"

@dataclass(frozen=True, slots=True)
class FactorInput:
    """因子计算的全部输入。纯函数只吃它，不碰数据库（SDL-1）。"""
    effective_at: date              # = decision_at
    adjusted_navs: tuple[Decimal, ...]   # 按日期升序，已按 PIT 解析
    nav_dates: tuple[date, ...]
    chain_quality: str              # 链路聚合后的 availability_quality（Task 2 产出）
    risk_free_rate: Decimal | None  # None 表示不可解析
    mar: Decimal | None             # None 表示 mar_policy 未配置

@dataclass(frozen=True, slots=True)
class FactorResult:
    factor_id: str
    value: Decimal | None           # UNAVAILABLE / INVALID 时为 None，【绝不填 0】
    status: FactorStatus
    reason: str                     # status 非 VALID 时必填，说明为什么
    observation_count: int

def compute_factor(factor_id: str, inp: FactorInput) -> FactorResult: ...

# ---- strategy_library/peer_group（Task 11）----
@dataclass(frozen=True, slots=True)
class PeerGroupKey:
    classification_scheme: str      # "AKSHARE_FUND_TYPE"
    classification_code: str        # L1 或 L2，由 peer_group.classification_level 决定
    base_currency: str              # 与 R_f 解析用的是【同一字段】

# ---- strategy_library/factor/normalize.py（Task 12）----
def percentile_rank(values: Sequence[Decimal], direction: PreferenceDirection) -> list[Decimal | None]:
    """Peer Group 内分位。公式与 ranking 统一：p = (N - Rank) / (N - 1) * 100。
    N == 1 时返回 None（不是 50、不是 100）。LOWER_IS_BETTER 先取负再排。"""

# ---- strategy_library/score（Task 14）----
class ScoreStatus(StrEnum):
    COMPLETED = "COMPLETED"; PARTIAL = "PARTIAL"; UNAVAILABLE = "UNAVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"; INSUFFICIENT_FACTORS = "INSUFFICIENT_FACTORS"

class SubScoreName(StrEnum):
    RETURN = "Return"; RISK = "Risk"; RISK_ADJUSTED = "Risk-Adjusted"
    STABILITY = "Stability"; RELATIVE_PERFORMANCE = "Relative Performance"

# ---- Task 2 产出（Task 9 消费）----
@dataclass(frozen=True, slots=True)
class NavSeries:
    points: tuple[NavPoint, ...]
    chain_quality: str | None       # 空序列 ⟺ None（__post_init__ 双向锁死，见 P2-6）
def weakest_quality(qs: Iterable[str]) -> str | None: ...
    # EXACT > DERIVED > INFERRED，取最弱者；空输入返回 None

# ---- Task 4 产出（SDL-3）----
CODE_VERSION_ROOTS: tuple[str, ...]          # 参与 Code Version 计算的包根
def compute_code_version() -> str: ...        # 全仓 code_version 此前只是字面量 "cli"

# ---- Task 4 产出，Task 5/11 消费（住 strategy_library/peer_group，见 P2-5）----
CLASSIFICATION_SCHEME: str = "AKSHARE_FUND_TYPE"
UNCLASSIFIED_CODE: str = "UNCLASSIFIED"
def level_1(classification_code: str) -> str: ...     # "混合型-偏股" -> "混合型"
def is_groupable(classification_code: str) -> bool: ...  # UNCLASSIFIED 返回 False

# ---- Task 3 产出（Task 9 消费）----
class InsufficientObservations(ValueError): ...   # → FactorStatus.UNAVAILABLE
class MathematicallyUndefined(ValueError): ...    # → FactorStatus.INVALID（分母 0、负方差、NaN）
```

---
