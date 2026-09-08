# fund-investment-platform · M1 实施设计（Design Spec）

> **上游文档**：`docs/01-product/01-product-overview.md`（v2.6）｜本文定位：**实施层设计**，不定义任何业务概念
> **同层依赖**：`docs/02-architecture/01~06`、`docs/10-api/01`、`docs/11-database/03~04`、`docs/01-product/04~05`
> **文档版本**：v1.1 ｜ **日期**：2026-09-08 ｜ **阶段**：第一阶段 · 里程碑 M1

---

## 0. 本文档的定位

### 0.1 回答什么

> **`docs/` 已经定义了「要建什么」。本文档回答「第一个可交付里程碑建到哪里、怎么建」。**

具体是四件事：

1. 代码仓库如何分层，才能让上游那些不可让步的约束在结构上成立而非靠自觉
2. M1 的精确边界 —— 做什么、刻意不做什么、为什么
3. 四项实施期选择的定案与理由（交付切法、前端形态、数据源、待定参数承载）
4. M1 之后的加宽路线

### 0.2 不回答什么

| 不回答 | 归属 |
|---|---|
| 任何业务概念的定义 | `docs/01-product` 及各业务域 |
| 因子公式、优化算法、回测方法论 | `04-factor` / `06-portfolio` / `07-return-risk` / `08-backtest` |
| 接口路径与请求响应结构 | `10-api` |
| 列级 DDL | `db/migrations/`（迁移脚本是权威来源） |
| 逐任务的实施步骤与验收 | 后续的 Implementation Plan |

### 0.3 Implementation Plan 的编写粒度

M1 体量较大（8 个子阶段、51 张表）。**Implementation Plan 不一次覆盖整个 M1**，而是分批编写：

| 批次 | 覆盖 | 理由 |
|---|---|---|
| **Plan-1** | M1.0 地基 + M1.1 数据接入 | 两个承重机制与复权净值都在这里；它们做对之前，后续任务的具体形态无法确定 |
| Plan-2 | M1.2 Peer Group + M1.3 因子 + M1.4 评价与候选池 | 计算流，依赖 Plan-1 的 PIT 接口定形 |
| Plan-3 | M1.5 组合与决策 + M1.6 回测 | 决策流，依赖快照闭包定形 |
| Plan-4 | M1.7 前端 | 依赖 API 契约冻结，可与 Plan-3 并行 |

每批 Plan 完成后回看本文档，若实现过程中发现设计缺口，先修订本文档再继续。

### 0.4 严格遵守上游协议

本文档**只细化，不重定义**（上游 §1.2 第二条）。文中出现 `Fund Data`、`Factor`、`Fund Score`、`Fund Universe`、`Return Estimate`、`Portfolio Construction`、`Portfolio Optimization`、`Investment Decision`、`Peer Group` 等术语时**一律为引用**，含义以上游 §11 术语表为准。

本文档**不引入任何未登记的核心概念**。文中新出现的名词（如 `PitDataContext`、`SourceAdapter`、`JobSubmitter`）均为**实施构件**，不是业务概念，不进入上游术语表。

---

## 1. 四项实施期定案

> 上游与架构层留下的实施期选择，在此定案并记录理由。它们不改变任何架构结论。

| # | 事项 | 定案 | 关联的上游待定项 |
|---|---|---|---|
| **IMP-1** | 交付切法 | **纵向走通骨架** —— 先端到端跑通最窄链路，再按域加宽 | —— |
| **IMP-2** | 前端形态 | **React + TypeScript SPA** | `TECH-3` / `ARCH-2` |
| **IMP-3** | 数据源 | **AKShare**（Python 库），`SourceAdapter` 端口预留商业数据源 | —— |
| **IMP-4** | 待定参数承载 | **外置为带 `PROVISIONAL` 标记的版本化配置** | `04-functional-requirements` 的 24 项 P1 |

### IMP-1 · 为什么是纵向而非横向

横向逐域完成（先做完 `data-service` 再做 `factor-service`）的问题在于：**PIT 强制访问、决策快照闭包、单一策略实现这三条约束是跨域的**，它们是否真的成立，只有在链路端到端跑通时才能被验证。若到 M4 才第一次端到端运行，届时发现某条约束不成立，返工范围是全部已完成的域。

纵向骨架把这三条约束在第一个里程碑就置于压力之下：一次真实的决策必须从 AKShare 原始数据一路走到带完整闭包的决策快照，并能被回测重放。

**代价**：M1 的每个域都只做很窄的一条，看起来"哪个域都没做完"。这是有意的。

### IMP-2 · 为什么是 React + TS

`06-technology-stack` §7.2 已给出倾向理由，此处采纳：核心界面是**上千行的 Peer Group 排名表 + 多序列时间图 + 相关性热力图 + 可逐级下钻的两条解释链**，这类数据密集型交互需要虚拟滚动与复杂状态管理，Streamlit 类框架在这个量级会遇到交互深度的天花板。

### IMP-3 · 为什么是 AKShare 而非直连数据源

| 维度 | AKShare | 直连（爬取天天基金等） | 商业数据源 |
|---|---|---|---|
| Adapter 实现 | 库调用 | HTTP + HTML/JSON 解析 + 限速 | 供应商 SDK/文件 |
| 覆盖广度 | 净值/分红拆分/费率/经理/规模/**中债收益率曲线**/指数 | 同源但需逐个实现 | 最广 |
| PIT 能力 | **无披露时刻、无修订历史** | **同样没有** | 通常有 |
| 起步成本 | 低 | 中 | 高（需采购与凭据） |

结论：M1 用 AKShare 起步，`SourceAdapter` 端口保证 M2+ 换商业数据源时下游零改动。**PIT 能力的缺失不由数据源选择造成，换直连也不会改善** —— 见 §4.3。

### IMP-4 · 为什么不直接填默认值也不直接阻断

上游明确「下游文档不得自行填充」这 24 项参数。但代码运行必须有取值。两个极端都不可取：

- **直接填默认值** → 占位值伪装成已定案，投研看到的回测结果建立在无人认可的参数上
- **一律阻断** → M1 无法端到端运行，IMP-1 的全部价值消失

采取的中间路径：参数外置为配置、显式标记 `PROVISIONAL`、**被 `LIVE` 运行时消费即告警并写入决策快照**。这样占位值可用于开发与回测，但永远不会伪装成定案值。

---

## 2. 仓库结构与分层

### 2.1 目录结构

```
fund-investment-platform/
├── docs/                          # 已有，唯一上游
├── libs/
│   ├── quant_engine/              # L1 数值层
│   └── strategy_library/          # L1 策略领域逻辑（SDL）
├── platform/
│   ├── decision_data/             # Decision Data Layer（抽象）
│   │   ├── context.py             #   DecisionExecutionContext
│   │   ├── pit/                   #   PIT-aware Data Access Interface
│   │   ├── snapshot/              #   PeerGroup / Universe / Decision / Backtest 快照
│   │   ├── versioning/            #   9 Strategy + 5 Policy + Code Version
│   │   ├── lineage/
│   │   └── audit/
│   ├── source/                    # SourceAdapter 端口定义
│   ├── jobs/                      # Calculation Job：幂等键 / 状态 / 进度
│   ├── config/                    # 配置装载与 PROVISIONAL 校验
│   └── api/                       # FastAPI：路由挂载、鉴权、统一响应/错误信封
├── services/
│   ├── data_service/
│   │   └── adapters/akshare/      # AkShareSourceAdapter
│   ├── factor_service/
│   ├── fund_service/
│   ├── portfolio_service/
│   └── backtest_service/
├── db/migrations/                 # Alembic —— DDL 的权威来源
├── config/                        # 9 Strategy Version + 5 Policy Version（YAML）
├── frontend/                      # Vite + React + TS
└── tests/
    ├── unit/  integration/
    ├── fitness/                   # 架构适应度测试
    ├── repro/                     # 可复现性回归
    └── contract/                  # 数据源契约测试
```

### 2.2 三层技术分层的落地

沿用 `06-technology-stack` §5.0：

| 层 | 目录 | 内容 | 硬约束 |
|---|---|---|---|
| **Backend Service** | `platform/api`、`services/*` | API 承载、用例编排、权限、任务提交、持久化实现 | **不得包含任何投资策略规则**（C-11） |
| **Strategy Library** | `libs/strategy_library` | Factor · Peer Group · Score · Universe · Return Estimation · Risk · Construction · Optimization | 不含数据访问实现（SDL-1）；无 `runtime_mode` 分支（SDL-2）；纳入 Code Version（SDL-3） |
| **Quant Engine** | `libs/quant_engine` | 矩阵、统计、时序、求解器封装 | 不含任何业务语义 |

**依赖方向单向**：

```
platform/api → services/* → libs/strategy_library → libs/quant_engine
services/*, libs/strategy_library → platform/decision_data（接口）
platform/decision_data ← 由基础设施实现
```

反向依赖（如 `quant_engine` 引用业务概念、`strategy_library` import SQLAlchemy）视为设计错误，由 §9.2 的适应度测试在 CI 中拦截。

### 2.3 5 个 Domain Service 是逻辑边界

M1 部署形态：**单个 FastAPI 进程 + 一个 worker 池 + 一个 PostgreSQL 实例**。

5 个 `services/*` 是 Python 包，不是 5 个进程，也不是 5 个数据库 —— 这正是 `01-system-architecture` §3.2 与 §10.3（决策快照单事务写入）成立的前提。

即使不独立部署，三条仍然强制（§3.4 SB-1~3）：

| # | 约束 | 落地方式 |
|---|---|---|
| SB-1 | 写入权唯一 | 每个 schema 只有一个 service 持有写入 Repository；数据库层按角色 `GRANT` |
| SB-2 | 职责不重叠 | 同一业务规则只有一处实现；由 code review 与适应度测试保证 |
| SB-3 | 依赖方向单向 | 适应度测试断言 `portfolio_service` 不 import `factor_service` 等 |

---

## 3. 两个承重机制

> **这两条必须在 M1.0 就建对。后续所有域都躺在它们上面，返工代价随时间指数上升。**

### 3.1 PIT 强制访问

上游原则二与 `01-system-architecture` §7.4 要求：领域服务**不得**直接访问时点敏感数据，全部经 PIT-aware 接口，每次调用必须携带 `decision_at`，不存在"取最新一条"的无约束路径。

**关键设计决定：做成类型上无法绕过的接口，而不是编码规范。**

```
DecisionExecutionContext
    decision_id · decision_at · data_as_of
    strategy_version · policy_version · code_version
    trigger_type · recompute_scope · runtime_mode
        │
        │ 唯一构造入口
        ▼
PitDataContext
    每个 Repository 在【构造期】即绑定 decision_at
    方法签名中不存在可选的时点参数
    不提供 get_latest() / get_current() 路径

CurrentViewContext        ← 独立接口，命名上无法与 PIT 接口混用
    仅供 Live Portfolio 当前状态展示使用（PIT-A4）
```

| # | 要求 | 落地 |
|---|---|---|
| PIT-A1 | 领域服务不得直接访问原始数据 | SDL 只接受注入的 `PitDataContext`；适应度测试断言 SDL 不 import 任何 DB 驱动 |
| PIT-A2 | 每次调用必须携带 `decision_at`，缺失则拒绝 | `PitDataContext` 无默认构造；缺 `decision_at` 在构造期即失败，而非查询期 |
| PIT-A3 | 不存在无约束的"取最新"路径 | PIT Repository 接口中不定义此类方法 |
| PIT-A4 | 实时视图与历史视图接口层面区分 | 两个独立的 Context 类型，互不兼容 |

> **为什么必须是接口约束**：若只写「记得加时点条件」，任何一处遗漏都会造成**静默前视偏差** —— 它不报错、不影响流程、在净值曲线上完全看不出来。这是回测失真最隐蔽的来源。

### 3.2 决策快照闭包与一致性边界

沿用 `01-system-architecture` §10.3 的三级边界：

```
B1  Peer Group Snapshot   原子写入 → 产生快照 ID
        ↓ 被引用
B2  Universe Snapshot     原子写入，引用 B1 的 ID
        ↓ 被引用
B3  Decision Snapshot     原子写入，引用 B2 的 ID + 本阶段全部产出
```

**B3 引用而非复制 B1/B2 的内容** —— 这使「单一事务」在实践中既可行又轻量。

**M1 的闭包必须包含**（§10.4）：执行上下文 · 九项 Strategy Version + 五项 Policy Version + Data Version + **Code Version** · 上游快照 ID · Return Estimate（含三项口径）· Risk Metrics · 协方差矩阵 · Constraint Set · Risk Budget · Optimization Objective · Optimization Run（输入/状态/输出/诊断）· Post-Optimization Risk · Target Weight · Decision Status · Human Review 记录。

**闭包判定**：给定该快照，不依赖任何当前系统状态，即可完整回答「这个决策是如何得出的」，并在相同版本下重跑得到一致结果。

**M1 追加一个字段**：`provisional_parameters_used` —— 记录本次决策消费到的全部 `PROVISIONAL` 参数清单（见 §5.3）。

失败处理：快照写入不完整 → **整体回滚**，本次决策视为未产生，指令不下发。

### 3.3 两类状态必须分开

沿用 §10.5，M1 即实现：

- **Decision Status**（业务）：`PROPOSED` / `APPROVED` / `OVERRIDDEN` / `REJECTED` / `INFEASIBLE` / `EXPIRED` / `SUPERSEDED`
- **Execution Status**（技术）：`RUNNING` / `COMPLETED` / `BLOCKED` / `FAILED` / `CANCELLED`

`INFEASIBLE` 是 Execution `COMPLETED` + Decision `INFEASIBLE`，**不重试**；`FAILED` 无 Decision，**幂等重试**。把前者当后者自动重试会掩盖「约束设置过紧」这一真实问题。

---

## 4. 数据接入 · AKShare

### 4.1 Adapter 端口

```
platform/source/SourceAdapter          （端口）
    ├── AkShareSourceAdapter           ← M1 实现
    └── VendorSourceAdapter            ← M2+ 预留
```

保留端口的理由：`04-integration-architecture` §2 要求外部格式不得穿透领域层。Adapter 只负责**协议与格式转换、字段映射到规范模型、打上三个时间来源字段**，不负责业务规则判断与数据质量分级（后者属 `data-service` 本体）。

### 4.2 M1 覆盖的数据集

> **函数名与列名须在实现时对 pinned 版本逐一核对** —— AKShare 跨版本改签名与改列名是常态。下表为候选接口，不是已验证契约。

| 数据 | 候选接口 | 落表 |
|---|---|---|
| 基金代码与名称全表 | `fund_name_em` | `fund.fund` / `fund.fund_share_class` |
| 历史净值（单位/累计） | `fund_open_fund_info_em(indicator="单位净值走势" / "累计净值走势")` | `market.fund_nav` |
| **分红送配 / 拆分** | `fund_open_fund_info_em(indicator="分红送配详情" / "拆分详情")` | `market.fund_distribution` |
| 基础信息 / 费率 / 成立日 | `fund_individual_basic_info_xq`、`fund_individual_detail_info_xq` | `fund.fund_fee` 等 |
| 规模 | `fund_aum_em` 等 | `fund.*` |
| 基金经理任职 | `fund_manager_em` | `fund.fund_manager` / `fund_manager_assignment` |
| **中债国债收益率曲线** | `bond_china_yield` | `market.risk_free_rate`（**带 tenor 的曲线**） |
| 指数历史序列 | `index_zh_a_hist` / `stock_zh_index_daily` | M2 Benchmark |

**收益**：`bond_china_yield` 提供带期限的曲线，正好对上 `03-erd` §6.5「Risk-free Rate 是曲线，不是单值」。因此 **Sharpe / Risk-Adjusted Score 在 M1 即可正常计算**，无需手工 CSV 兜底。

### 4.3 PIT 诚实性 ⚠️

> **AKShare 底层是天天基金 / 新浪 / 中债等公开源，没有披露时刻，也没有净值修订历史。换直连数据源不会改善这一点。**

| 数据 | `available_at` 解析规则 | `availability_quality` |
|---|---|---|
| 基金基础信息 / 分类 / 经理 / 费率 / 规模 | `ingested_at` | `INFERRED` |
| 净值序列（历史回补） | `effective_at + 声明的披露时滞` | `INFERRED` |
| 净值序列（每日增量） | 实际抓取时刻 | `INFERRED`（具真实日粒度） |
| 无风险利率 | `effective_at + 声明的披露时滞` | `INFERRED` |

**四条硬规则**：

| # | 规则 | 依据 |
|---|---|---|
| DS-1 | **Adapter 如实留空** —— `provider_available_at` / `published_at` 拿不到就是 NULL，**绝不用 `ingested_at` 回填** | `04-integration-architecture` §2.5；`04-database-design` §4.4.1 的 CHECK 约束会在存储层直接拦下 |
| DS-2 | **披露时滞是声明的推导规则，不是猜测** —— 写入 `governance.data_source_priority` 并版本化，回测报告必须复述 | `03-data/01-data-source` §11 |
| DS-3 | **`backtest_bias_check` 必须报告 `INFERRED` 占比**；占比超阈值判 `WARNING`，结果标注「前视偏差防护为推导级，非精确级」 | `10-api/01` §10.3.1；`08-backtest/03` |
| DS-4 | **`raw.raw_payload` 全量留存原始返回**（DataFrame 序列化为 parquet），键上带 AKShare 函数名 + 参数 + 版本号 | `03-erd` §7.1（`raw_payload : canonical_raw = 1:N`，Adapter 修 bug 后可重解析而不重抓） |

> **这不是缺陷掩盖，而是缺陷暴露。** 上游的 `availability_quality` 枚举与 `backtest_bias_check` 一等实体设计，正是为这种情形准备的。M1 的义务是把真实的质量等级如实呈现，而不是让回测看起来比它实际更严谨。

### 4.4 复权净值必须由平台自己计算 ⚠️

> **这是一个容易被漏掉但承重的 M1 工作项。**

术语表规定「平台内统一使用**复权净值**做收益计算」。而 AKShare 提供的是单位净值与累计净值：

```
累计净值 ≠ 复权净值
    累计净值不处理拆分
    累计净值不做分红再投资的乘法复利
```

因此 `03-data/05-data-normalization` 的复权算法必须在 M1 用 `分红送配 + 拆分` 序列自行实现，并版本化为 `Metric Version` 的组成部分。

**它是承重的** —— 每一个 Factor、每一份 `μ` 与 `Σ`、每一条回测净值曲线都建在它上面。M1 必须为它编写独立的、带已知案例的单元测试（含分红、拆分、分红+拆分同日三类场景）。

### 4.5 Fund ↔ Share Class 归组

AKShare 的 6 位基金代码对应的是**份额类别**（`fund_share_class`），不是基金产品（`fund`）。而 `03-erd` §5.2 要求两者分离。

M1 的处置：按「名称主干 + 管理人」建立一条明确的归组规则，并**保留人工修正入口**。归组关系本身版本化。**不猜** —— 归组不确定的份额类别单独成一个 `fund`，并标记待人工确认，而不是强行合并。

---

## 5. 配置与版本模型

### 5.1 配置目录

```
config/
├── strategy/                       # 九项 Strategy Version
│   ├── metric/                     #  1 Metric Version
│   ├── peer_group/                 #  2 Peer Group / Classification Version
│   ├── eligibility/                #  3 Eligibility / Universe Version
│   ├── scoring/                    #  4 Scoring Version
│   ├── return_estimate/            #  5 Return Estimate Version
│   ├── risk_model/                 #  6 Risk Model Version
│   ├── portfolio_rule/             #  7 Portfolio Rule Version（含约束集与风险预算）
│   ├── rebalance_rule/             #  8 Rebalance Rule Version（M2）
│   └── benchmark/                  #  9 Benchmark Version（M1 人工配置，M2 自动解析）
└── policy/                         # 五项 Policy Version
    ├── evaluation/                 #  MAR、评价周期、评价准入
    ├── ranking/                    #  Percentile 约定、Tie Method
    ├── classification/             #  Fund Tier 阈值
    ├── estimation/                 #  估计框架与方法参数
    └── validation/                 #  各类 Gate 阈值
```

沿用 `NFR-MAINT-001`：这些内容以配置而非代码存在，变更不需要重新发布。

### 5.2 参数的三元组

每个叶子参数：

```yaml
scoring:
  weights:
    return_score:
      value: 0.30
      status: PROVISIONAL          # PROVISIONAL | DECIDED
      source: "P1-6 待投研定案"
    risk_adjusted_score:
      value: 0.30
      status: PROVISIONAL
      source: "P1-6"
```

24 项 P1 参数全部以 `PROVISIONAL` 起步。取值改为 `DECIDED` 属 Strategy / Policy 版本变更，走版本治理并触发可复现性回归（§9.3）。

> **约束：叶子的 `value` 不得是映射。** 装载器用「键集合恰好等于 `{value, status, source}`」
> 判定参数叶子。若某个叶子的 `value` 本身又是一个映射，就无法区分「一个值为字典的标量参数」
> 与「一个恰好用了这三个字段名的嵌套配置段」—— 二者形状完全相同。此时装载器**显式报错**
> 而非任选一种解释，因为静默塌陷会让整段嵌套结构无声消失。
>
> 列表值参数不受此限，可正常使用。若未来确需字典值参数，须先为叶子引入显式判别字段，
> 不可放宽本判定。

### 5.3 PROVISIONAL 的运行时语义

| 运行时 | 行为 |
|---|---|
| `runtime_mode = BACKTEST` | 允许使用；占位标记落入回测报告的配置章节 |
| `runtime_mode = LIVE` | 允许使用，但**必须**：① 发出结构化告警事件 `ProvisionalParameterUsed`；② 将参数清单写入决策快照的 `provisional_parameters_used` 字段 |

> **不阻断，但绝不静默。** 阻断会让 M1 无法端到端运行；静默则让占位值伪装成定案值 —— 后者更危险。

### 5.4 配置装载

部署时将 YAML 装载进 `governance.policy_version` 与 Strategy Version 相关表，产生版本 ID。**决策快照必须以 FK 引用版本 ID**，不能只存 YAML 内容的哈希 —— 后者无法参与关系查询，也无法保证「用于生产决策的配置版本不得删除」。

---

## 6. M1 的精确边界

### 6.1 Stage 覆盖

| Stage | M1 做 | M1 刻意不做（→ M2+） |
|---|---|---|
| **① Fund Data** | fund / share_class / nav（含复权）/ classification / manager / fee / eligibility 事实 / raw / risk_free_rate；基础质量闸门与三级阻断粒度 | 完整质量五维、公告类数据、多 Provider 冲裁、完整血缘 |
| **② Factor** | 15 个因子；Peer Group 内标准化；Threshold Resolver；OOS IC / ICIR / 分层单调性 / 冗余检查；`factor_effectiveness` | 完整 Walk-forward、市场状态分段、Rolling 因子全家族 |
| **③ Fund Score** | 五子分 + 归因明细表 + `Data Completeness` + 排名 / 分位 / `Fund Tier` | 评分变化归因、多 `Evaluation Profile` |
| **④ Fund Universe** | `Eligibility Rules` + 快照（含 `REJECTED` 成员与逐条件结果） | 三种构成策略、容量规则、探索性筛选路径 |
| **⑤-A Return Estimate** | Historical Mean，显式声明 Estimation Window / Horizon / Return Basis | CAGR / Rolling Mean / Benchmark-relative / Shrinkage |
| **⑤-B Risk / Correlation** | 波动率、下行风险、最大回撤；`Σ` = 样本协方差 + Ledoit-Wolf 收缩；PSD 与条件数诊断 | 其余风险模型、估计稳定性监控 |
| **⑥ Construction** | 目标函数装配；约束集（权重上下限、`sum(w)=1`、类别上限）；Risk Budget 六要素校验 | 完整约束库、事前回撤约束 |
| **⑦ Optimization** | **Equal Weight + Minimum Volatility（凸 QP）**；`INFEASIBLE` 显式失败 + `binding_constraint` 诊断 | Maximum Sharpe（需先声明 Charnes-Cooper 求解路径）、Risk Parity、Minimum CVaR |
| **⑦-R Post-Opt Risk** | `σ_p`、MRC、TRC、集中度 HHI、因子暴露、Risk Budget 达成校验 | —— |
| **⑦ Output** | Proposed → PM Review（`APPROVED` / `REJECTED` / `OVERRIDDEN` 五字段留痕）→ Approved；完整快照闭包 | 决策有效期与 `EXPIRED` 流转 |
| **⑧ Backtest** | 编排循环、快照优先原则、逐期决策快照、逐日净值、绩效指标、三方对比、`bias_check` | Walk-forward / IS-OOS 编排、交易成本模型细化 |
| **⑨ Live Portfolio** | ❌ 不做 | M2 |
| **⑩ Rebalancing** | ❌ 不做 | M2 |

### 6.2 两个刻意的缺省

| 缺省 | 理由 |
|---|---|
| **官方 Benchmark 文档自动解析推到 M2** | M1 使用版本化人工基金级配置与内部分类默认映射，保证 REL 因子闭环；招募说明书自动解析仍需独立的数据质量设计。 |
| **Live Portfolio 与 Rebalancing 推到 M2** | 二者依赖外部执行系统的成交回报，而 M1 没有对接方。强行实现只能靠平台自行推算 `Actual`，直接违反上游 ⑨-S「`Actual` 来自外部回报，非平台推算」。 |

### 6.3 落表范围

M1 落约 **51 张表**，M2+ 补齐约 19 张。

> **表数量不是主要工作量。** 51 张中约半数是结构简单的维度表与明细表（`fund_management_company`、`fund_manager`、`covariance_instrument`、`selection_condition_result` 等），建表成本很低。真正的工作量集中在三处：§3 的两个承重机制、§4.4 的复权净值算法、以及 §3.2 的快照闭包与单事务写入。
>
> 之所以 M1 就要落这么多表，是纵向骨架的直接结果 —— 端到端跑通一次决策，必然触及每一个 Stage 的持久化。**但 8 个 schema 与全部时间列标准一次建对，M2+ 只加表不改既有结构。**

| Schema | M1 落表 | M2+ 补齐 |
|---|---|---|
| `raw` | `raw_payload`、`canonical_raw` | —— |
| `fund` | `fund`、`fund_share_class`、`provider_fund_identity`、`fund_management_company`、`fund_manager`、`fund_manager_assignment`、`fund_classification_history`、`fund_status_history`、`fund_fee`、`investment_eligibility` | `fund_subscription_status` |
| `market` | `fund_nav`、`fund_distribution`、`risk_free_rate` | benchmark 四表 + `benchmark_index_value` |
| `factor` | `factor_definition`、`factor_version`、`factor_run`、`factor_value` | `factor_effectiveness` |
| `evaluation` | `peer_group_snapshot`、`peer_group_member`、`fund_score`、`fund_score_attribution`、`fund_ranking`、`fund_tier`、`fund_universe_snapshot`、`fund_universe_member`、`selection_condition_result` | `fund_evaluation` |
| `portfolio` | `portfolio`、`estimation_method`、`estimation_run`、`return_estimate`、`risk_estimate`、`covariance_estimate`、`covariance_instrument`、`optimization_result`、`binding_constraint`、`investment_decision`、`decision_review` | 三态三表 + `portfolio_position` + `rebalance` + `rebalance_trade` |
| `backtest` | `backtest`、`backtest_run`、`backtest_period`、`backtest_position`、`backtest_nav`、`backtest_metric`、`backtest_bias_check` | `backtest_trade`、`backtest_report` |
| `governance` | `policy_version`、`audit_log`、`data_provider`、`data_provider_dataset`、`data_source_priority` | `lineage_node`、`lineage_edge`、`data_quality_result` |

**全部版本化表在 M1 即采用 `04-database-design` §4.4 的标准列**（`effective_at` / `available_at` / `availability_quality` / `version` / `published_at` / `provider_available_at` / `ingested_at`）**及其两组 CHECK 约束**。区间型表同理采用 §4.5 标准列。

### 6.4 API 范围

沿用 `10-api` 的全部契约约定（统一响应信封、`meta` 必带版本引用、`null` + `status` + `reason`、百分比用小数、`page`/`page_size` 默认 50 上限 500、确定性排序、`as_of_date` 为 PIT 语义、URL 路径版本 `/api/v1/`、`Idempotency-Key` 24 小时）。

M1 端点范围：

```
Fund      GET  /funds · /funds/{id} · /funds/{id}/nav-series
               /funds/{id}/scores · /funds/{id}/tier · /funds/{id}/evaluations
               /fund-rankings · /peer-groups/{id}
Factor    GET  /factors · /factors/{id} · /funds/{id}/factors
               /funds/{id}/factors/{fid} · /funds/{id}/factors/{fid}/series
               POST /factors/batch-query
Portfolio GET  /portfolios · /portfolios/{id} · /portfolios/{id}/constraints
               /portfolios/{id}/risk-budget · /portfolios/{id}/risk
          POST /portfolios/{id}/optimizations         （异步 → 202）
          POST /decisions/{id}/review                 （Approve/Reject/Override）
Backtest  POST /backtests · /backtests/{id}/runs · /backtests/{id}/validate-configuration
          GET  /backtests/{id}/status · /result · /performance
               /portfolio-history · /bias-check
Common    GET  /operations/{operation_id}             （异步任务统一查询）
```

M1 不做：`/portfolios/{id}/holdings`、`/rebalances/*`、`/allocations`（依赖 M2 的 Live 与 Rebalancing）。

### 6.5 前端范围

**技术栈**：Vite + React 18 + TypeScript；TanStack Query（服务端状态）+ TanStack Table（虚拟滚动）+ ECharts（净值曲线、滚动指标、四象限散点、相关性热力图）。

**API client 由 FastAPI 的 OpenAPI 自动生成**（`openapi-typescript` + `orval`）—— 让 `10-api` 契约与实现的一致性由工具保证，而非人工同步。契约漂移在构建期即失败。

**四个横切组件**（做成全局能力，不允许各页面自行处理）：

| 要求 | 组件 | 依据 |
|---|---|---|
| 每个数据视图展示 `meta.versions` / `is_point_in_time` / `availability_quality_distribution` | 常驻「口径条」`<ProvenanceBar>` | `10-api/01` §5.2、§11.3 |
| `null` + `status` + `reason` 渲染为「不可用（原因）」，**永不显示 0 或 `-`** | `<MetricValue>` | `10-api/01` §12.4 |
| 传输层一律小数，展示层统一乘 100 | `formatters` 单一出口 | `10-api/01` §12.1 |
| 两条解释链可逐级下钻 | `<ScoreExplainChain>` / `<WeightExplainChain>` | `NFR-EXPL-001` |

**M1 四个页面**：

1. **基金检索与详情** —— 检索/筛选、多周期业绩、风险特征、因子值、评分五子分 + 归因下钻
2. **候选池快照** —— Universe 成员，含 `REJECTED` 成员与逐条件通过/未通过结果
3. **组合决策** —— 优化结果、目标权重、`σ_p`/MRC/TRC/HHI、权重解释链、PM 复核（Approve / Reject / Override）、`INFEASIBLE` 的紧约束诊断呈现
4. **回测** —— 提交、进度轮询、净值曲线、绩效指标、三方对比、`bias_check` 结果

**RBAC**：`Approve` / `Reject` / `Override` 仅限 `Portfolio Manager`（SEC-1）；同一 token 不得同时具备策略配置权与决策放行权（SEC-2）。**服务端强制**，前端只做呈现与按钮可见性。

---

## 7. M1 的八个子阶段

> 依赖顺序由 `02-service-architecture` §4.6 的实际执行序确定：
> `data-service（分类 + R_f） → fund-service（Peer Group + Evaluation Policy） → factor-service（计算 + 标准化） → fund-service（评分）`

| 子阶段 | 内容 | 完成判据 |
|---|---|---|
| **M1.0 地基** | 仓库骨架与三层分离；8 个 schema + 时间列标准 + Alembic；`DecisionExecutionContext` 与 `PitDataContext` 接口；`SourceAdapter` 端口；Job 表与幂等键；配置装载与 `PROVISIONAL` 校验；CI 含架构适应度测试 | 适应度测试全绿；一个空的决策上下文可贯穿创建与落库 |
| **M1.1 数据接入** | `AkShareSourceAdapter`；`raw_payload` 留存；fund / share_class / nav；复权净值计算；基础模型与质量闸门 | **已完成（Plan-1）**：可按历史 `decision_at` 取到当时可见的复权净值序列 |
| **M1.2 Peer Group + Benchmark** | 分类/费率/Rf 数据链路；版本化人工 Benchmark；`peer_group_snapshot/member`；Evaluation Policy | Peer Group 不读取 Score/Universe；Benchmark 与快照可按时点复现 |
| **M1.3 因子** | Factor 四表；15 个因子；Threshold Resolver；标准化；最小 OOS 有效性闭环 | 重算误差不超过 1e-10；无 OOS 结论不得进入 Score |
| **M1.4 评价与候选池** | 五子分 + 固定 Profile 权重归因 + `Data Completeness`；排名 / 分位 / Tier；`Eligibility Rules`；Universe 快照（含 `REJECTED`） | Benchmark 可用且 OOS 检验通过时产出正式 Score；B1→B2 边界原子性验证通过 |
| **M1.5 组合与决策** | `μ` / `σ` / `Σ`（含收缩与诊断）；Construction；Optimization（EW + MinVol）；Post-Opt Risk；Proposed → Review → Approved；**快照闭包** | 快照闭包判定通过（脱离当前系统状态可完整重建）；`INFEASIBLE` 显式失败且不重试；Override 五字段缺一即拒绝放行 |
| **M1.6 回测** | 编排循环；快照优先原则；逐期快照；逐日净值；绩效与三方对比；`bias_check`（含 `INFERRED` 占比） | 回测与实盘走同一套 SDL（全仓无 `is_backtest`）；可复现性回归通过 |
| **M1.7 前端** | 四个页面 + 四个横切组件 + 生成式 API client + RBAC 呈现 | 契约漂移在构建期失败；`null` 场景无一处渲染为 0 或 `-` |

> **M1.7 可在 M1.5 的 API 契约冻结后并行启动**，不必串行等待 M1.6。

---

## 8. 任务编排

### 8.1 M1：自建 Job + worker

M1 使用自建的 `Calculation Job` 机制：

| 要素 | 设计 |
|---|---|
| `execution_id` | 任务唯一标识，关联 `decision_id` |
| **幂等键** | `(decision_at, strategy_version, recompute_scope)` —— 重复投递不产生重复快照 |
| 状态与进度 | 可查询；长任务（回测）必须上报进度 |
| 重试策略 | `FAILED` 幂等重试；`INFEASIBLE` / `BLOCKED` **不重试** |
| 失败定位 | 部分失败可定位到具体对象（基金 × 指标 × 阶段） |

提交与编排藏在 `JobSubmitter` / `PipelineDefinition` 接口后面，业务代码不感知底层实现。

### 8.2 M2：引入 Prefect 落 `TECH-1`

推荐 **Prefect 3**：Python 原生、状态持久化、DAG 依赖保证、work pool 可分池（回测与批量计算隔离）。一个组件同时覆盖 `06-technology-stack` §5.3.1 的 Scheduler 与 §5.3.2 的 Task Queue 两项能力需求，比 Airflow + Celery 双组件更符合「不为技术先进引入没有业务价值的技术」。

| 候选 | 取舍 |
|---|---|
| **Prefect 3**（推荐） | 单组件覆盖两项能力；Python 原生；状态持久化与续跑 |
| Airflow + Celery | 成熟但两个组件、两套运维；DAG 定义偏静态 |
| Dagster | 资产血缘能力强，但对本阶段是过剩能力 |

**约束 D-8 照旧**：编排层只负责触发与顺序，**不得承载任何业务判断**。调度配置里写 `if` 条件会让策略规则逃离版本化范围，破坏可复现性。

---

## 9. 测试策略

### 9.1 TDD

全程 TDD。业务规则必须可独立测试，不依赖外部数据源（`NFR-MAINT-003`）—— 这要求 SDL 的纯函数设计（§2.2）在测试中直接兑现：注入构造好的 `PitDataContext` 测试替身即可。

### 9.2 架构适应度测试（`tests/fitness/`）

在 CI 中强制，把架构约束变成可执行断言：

| 断言 | 保护的约束 |
|---|---|
| `libs/strategy_library` 不 import 任何 DB / HTTP 库 | SDL-1、PIT-A1 |
| 全仓不存在 `is_backtest` / `runtime_mode` 分支于 SDL 内 | SDL-2、SEI-3、上游原则一 |
| PIT Repository 接口无 `get_latest` 类方法 | PIT-A3 |
| Peer Group 构建模块不 import 评分 / Universe 模块 | C-4、`FR-PEER-001` |
| `portfolio_service` 不 import `factor_service` | DEP-3、上游原则四 |
| `platform/api` 与 `services/*` 不含策略常量与阈值 | C-11、`NFR-MAINT-001` |
| 各 schema 的写入 Repository 唯一 | SB-1 |

### 9.3 可复现性回归（`tests/repro/`）

CI 发布前强制执行（`D-7`）：固定 `Data Version + Strategy Version + Policy Version + Code Version + Execution Context`，重跑一次已存的历史决策，按 `06-technology-stack` §5.4.3 的容差比对。

| 对象 | 容差 |
|---|---|
| Factor 值 / Score | 相对误差 1e-10 |
| 协方差矩阵 | 相对误差 1e-8 |
| **优化权重 `w`** | 相对误差 1e-6，**且排序与非零集合必须完全一致** |
| 绩效指标 | 相对误差 1e-8 |

`TOL-3`（非零集合必须一致）是权重层真正的硬约束 —— 不一致说明求解路径分叉，属缺陷而非数值噪声。

### 9.4 数据源契约测试（`tests/contract/`）

针对 pinned AKShare 版本，断言各数据集的预期列存在且类型符合预期。**升级 AKShare 时该测试失败，而不是静默错映字段。**

### 9.5 负载基线（`tests/perf/`）

M1 即搭建 `06-technology-stack` §4.6 的 W2 / W5 / W7 压测夹具，测出 X / Y / Z 的**基线值** —— `OPEN-14` 目前为空，L1 存储选型因此仍是「待验证的选择」而非既成事实。M1 的义务是把它变成已验证。

| 负载 | 判据 |
|---|---|
| W2 单时点全市场因子横截面 | P95 latency 基线 |
| W5 决策快照单事务写入 | 单事务完整写入且 P95 基线；**不可通过放弃一致性来解决** |
| W7 回测逐期读取 | 总耗时基线，且随「基金数 × 期数」近似线性 |
| 资源余量 | CPU < 70%、Memory < 75% |

---

## 10. 风险与处置

| # | 风险 | 影响 | 处置 |
|---|---|---|---|
| R-1 | **AKShare 无 PIT 历史** —— 回补数据的前视偏差防护只能是推导级 | 直接削弱系统的核心价值主张（无偏回测） | 在 `bias_check` 中量化并显式声明（DS-3）；日增量开始后逐步积累真实 PIT；换商业数据源时可回补精确时点 |
| R-2 | **AKShare 跨版本改函数名 / 列名** —— 静默改列导致错误映射而不报错 | 因子值静默错误，极难发现 | 精确 pin 版本；`raw_payload` 与 `data_provider_dataset` 记录 `akshare_version`；数据源契约测试（§9.4） |
| R-3 | **复权净值算法出错** | 全链路承重，错则一切错 | 独立单元测试 + 已知案例；纳入 `Metric Version` 并触发可复现性回归 |
| R-4 | Fund ↔ Share Class 归组规则不确定 | 影响 Peer Group 构成与评分可比性 | 明确规则 + 人工修正入口；不确定者单独成 `fund` 并标记待确认，**不强行合并** |
| R-5 | AKShare 上游不稳定 / 限流，长回补易中断 | 灌数无法完成 | Job 按 `(dataset, fund, date_range)` 幂等且可断点续跑 |
| R-6 | **24 项 `PROVISIONAL` 参数** | 回测结论建立在未定案参数上 | 配置外置 + `LIVE` 使用即告警 + 决策快照打标（§5.3） |
| R-7 | M1 落 51 张表、8 个子阶段，体量不小 | 进度风险 | 八个子阶段各有独立完成判据，可单独验证与调整；Implementation Plan 按子阶段分批编写（§0.4） |
| R-8 | `OPEN-14` 性能门槛未测，L1 选型仍待验证 | 若不达标须触发 §4.4 重评估 | M1 内建负载基线（§9.5），把「待验证」变为「已验证」 |

---

## 11. 未决项

> **本文档不填充上游明确禁止下游填充的内容。** 以下为 M1 实施期需要澄清、但不阻塞 M1.0~M1.2 启动的事项。

| # | 事项 | 需要时点 | 责任方 |
|---|---|---|---|
| ~~IMP-TBD-1~~ | ~~M1 因子清单与 Usage~~ —— 已冻结 15 项 | ✅ 2026-09-08 | 投研 + 技术 |
| ~~IMP-TBD-2~~ | ~~Peer Group 粒度与最小样本~~ —— 内部二级分类 × 币种，`n >= 30` | ✅ 2026-09-08 | 投研 |
| ~~IMP-TBD-3~~ | ~~MAR~~ —— M1 显式 `ZERO` | ✅ 2026-09-08 | 投研 |
| ~~IMP-TBD-4~~ | ~~Risk-free Rate~~ —— 基础币种 × 评价周期，缺期限线性插值 | ✅ 2026-09-08 | 投研 + 数据 |
| IMP-TBD-5 | 各数据集的**声明式披露时滞**取值 | M1.1 前 | 数据 + 投研 |
| IMP-TBD-6 | Fund ↔ Share Class 归组规则的具体判据 | M1.1 前 | 技术（可先定后调） |
| IMP-TBD-7 | M1 回测的默认区间与调仓频率（`P1-16`） | M1.6 前 | 投研 |
| IMP-TBD-8 | `bias_check` 中 `INFERRED` 占比的 `WARNING` 阈值 | M1.6 前 | 投研 + 治理 |
| IMP-TBD-9 | W2 / W5 / W7 的 SLO 数值 X / Y / Z（`OPEN-14`） | M1 收尾 | 压测产出 + 产品确认 |

其余 24 项 P1 参数以 `PROVISIONAL` 配置承载，不阻塞 M1。

---

## 12. M1 之后的路线

| 里程碑 | 内容 |
|---|---|
| **M2 · 实盘与再平衡** | Benchmark 官方文档自动解析与五级优先级选取增强；Live Portfolio 三态；Rebalancing 四类触发与分级重算；外部成交回报接收；Prefect 落地 |
| **M3 · 研究能力加宽** | 有效性检验扩展（市场状态分段、完整 Walk-forward 与稳定性研究）；Rolling 因子全家族；Maximum Sharpe（含 Charnes-Cooper 路径声明）与 Risk Parity |
| **M4 · 治理与运维** | 完整数据质量五维；血缘图；`12-operations` 的四层可观测性与业务事件观测；`13-governance` 的策略生命周期与 Approval Gate |
| **M5+** | 完整约束库、CVaR、多 `Evaluation Profile`、商业数据源接入（精确 PIT）、性能优化（列存旁路只读副本，若 `OPEN-14` 触发 §4.4） |

> **第一阶段全程不引入任何 ML / AI 组件、依赖或数据通道**（上游 §6.2.1、原则九至十一）。

---

## 13. Decisions

| # | 决策 | 关键理由 |
|---|---|---|
| D-1 | 纵向走通骨架，而非横向逐域完成 | PIT / 快照闭包 / 单一策略实现是跨域约束，只有端到端跑通才能验证其成立 |
| D-2 | Strategy Library 独立于 Backend Service | 它是 Live 与 Backtest 共用的那一套；混入服务代码会使回测复用退化为「调用实时服务」 |
| D-3 | PIT 做成类型上无法绕过的接口，而非编码规范 | 静默前视偏差不报错、不影响流程、在净值曲线上看不出来 |
| D-4 | M1 单进程 + 单库部署 | 5 个 Domain Service 是逻辑边界；单库是决策快照单事务写入成立的前提 |
| D-5 | 采用 AKShare，但保留 `SourceAdapter` 端口 | 起步成本低且覆盖广；端口保证换商业数据源时下游零改动 |
| D-6 | 回补数据的 `available_at` 统一为 `INFERRED` 并在 bias-check 中暴露 | 如实呈现质量等级，而非让回测看起来比实际更严谨 |
| D-7 | 复权净值由平台自行计算并纳入 `Metric Version` | 累计净值不等于复权净值；它是全链路承重项 |
| D-8 | 待定参数外置为 `PROVISIONAL` 配置，`LIVE` 消费即告警 | 直接填默认值会让占位值伪装成定案；一律阻断则 M1 无法运行 |
| D-9 | M1 纳入版本化人工 Benchmark；官方文档自动解析推到 M2 | 先闭合正式评分，同时不伪装 AKShare 能提供官方复合基准 |
| D-10 | M1 纳入 REL 因子和最小 OOS 有效性检验 | 正式 Score 必须同时具备 Benchmark 与有效性证据 |
| D-11 | M1 自建 Job，M2 引入 Prefect | M1 需求可由轻量实现满足；接口隔离使后续替换不触碰业务代码 |
| D-12 | 前端 API client 由 OpenAPI 生成 | 让 `10-api` 契约与实现的一致性由工具在构建期保证，而非人工同步 |
| D-13 | M1 内建 W2 / W5 / W7 负载基线 | `OPEN-14` 未测则 L1 存储选型仍是「待验证的选择」 |

---

## 14. Constraints

> 全部继承自上游与架构层，此处列出对实施有直接约束力的部分。

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 决策快照必须在单一事务内完整写入；不完整则整体回滚，指令不下发 | 上游 §8.4 |
| C-2 | Strategy Library 中不得出现「是否回测」的分支 | 上游 §5.4、SEI-3 |
| C-3 | Backend Service Layer 不得包含投资策略规则 | `06-technology-stack` C-11 |
| C-4 | Peer Group 构建不得读取 Score / Universe | `FR-PEER-001` |
| C-5 | Return Estimate 不得读取 Fund Score 及任何评分派生量 | `FR-RET-001`、上游原则四 |
| C-6 | 各服务不得对 `UNAVAILABLE` 数据做任何填充（0 / 均值 / 上期值） | `FR-FUND-001`、`FR-SCORE-002` |
| C-7 | 优化不可行必须显式失败并上报，不得放松约束、退化等权或沿用上期 | 上游原则五、`FR-OPT-002` |
| C-8 | `Approve` / `Reject` / `Override` 仅限 `Portfolio Manager`；策略配置权与决策放行权必须分离 | `NFR-SEC-001` SEC-1 / SEC-2 |
| C-9 | `OVERRIDDEN` 五字段缺一不得放行 | 上游 §7.1.1 |
| C-10 | Strategy Library / 求解器 / 数值库版本必须显式记录于决策快照 | `06-technology-stack` C-9 |
| C-11 | 求解器与数值库版本必须锁定，升级视为影响输出的变更 | `NFR-REPRO-001` |
| C-12 | Adapter 须如实留空 `provider_available_at` / `published_at`，不得回填 | `04-integration-architecture` §2.5 |
| C-13 | 调度器不得承载业务判断逻辑 | `06-technology-stack` C-8 |
| C-14 | 不引入任何 ML / AI 相关技术栈、依赖或数据通道 | 上游 §6.2.1 |
| C-15 | 不得使用本地文件系统作为跨实例共享存储 | `06-technology-stack` OS-2 |

---

## 15. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md`（v2.6）、`02-business-requirements.md`、`04-functional-requirements.md`、`05-non-functional-requirements.md` |
| **架构依据** | `02-architecture/01~06` |
| **业务依据** | `03-data`、`04-factor`、`05-fund-evaluation`、`06-portfolio`、`07-return-risk`、`08-backtest` |
| **契约依据** | `10-api/01~05`、`11-database/01`、`03`、`04` |
| **下游** | 本文档的 Implementation Plan |

---

## 16. 变更记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| v1.1 | 2026-09-08 | 记录 Plan-1 完成状态；Plan-2 扩展 Benchmark 最小闭环与 15 因子；纳入 OOS 有效性检验；冻结 Peer Group、MAR、Rf 与正式 Profile 权重 |
| v1.0 | 2026-08-31 | 初始版本。定案四项实施期选择（纵向骨架 / React+TS / AKShare / PROVISIONAL 配置）；确立仓库三层分离与两个承重机制；界定 M1 边界（32 张表、8 个子阶段、三个刻意缺省）；登记 8 项风险与 9 项实施期待决项 |