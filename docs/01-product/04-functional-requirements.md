# 功能需求 · Functional Requirements

> **上游文档**：docs/01-product/01-product-overview.md（v2.5）｜docs/01-product/02-business-requirements.md（v2.3）｜docs/01-product/03-user-stories.md（v1.0）
> **本文细化阶段**：全链路（Stage ① – ⑩）
> **文档版本**：v1.0
> **产品阶段**：第一阶段 —— 纯 Quant 基金投资组合决策支持系统（不引入 ML / AI）

---

## 1. Overview

### 1.1 本文档回答什么

> **系统具体必须提供哪些功能？**

`03-user-stories` 回答"为什么需要"，本文档回答"系统必须做什么"。本文档比 User Story 更精确、可验证。

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 这些功能要达到什么质量 | `05-non-functional-requirements` |
| 系统如何组织与部署 | `02-architecture` |
| 各 Factor 的数学公式 | `04-factor` |
| 收益与风险的估计算法 | `07-return-risk` |
| 优化算法与求解器 | `06-portfolio` |
| 回测引擎实现与统计检验方法 | `08-backtest` |
| 表结构、接口协议、存储引擎 | `11-database`、`10-api`、`02-architecture` |

> **本文档不出现**：数据库、消息队列、缓存、编排系统、接口协议、编程语言、框架、建表语句、接口路径、类与方法、索引与分区、UI 组件。

---

## 2. Scope

### 2.1 In Scope

覆盖上游 10 个 Stage 的全部系统能力，共 **23 个功能域**（见 §4）。

### 2.2 Out of Scope

以下能力**不作为第一阶段的任何功能需求**（上游 §6.2）：

```
✗  ML 基金收益预测        ✗  AI 基金推荐          ✗  LLM 生成投资决策
✗  AI 自动调整组合        ✗  强化学习 / 深度学习   ✗  自动新闻情绪交易
✗  自动交易执行           ✗  券商交易接口         ✗  自动下单
✗  日内 / 高频交易策略
```

上述能力仅可作为 **Future Extension** 记录，**不得**出现在任何 `FR-*` 条目中。

---

## 3. 编号、模板与优先级

### 3.1 编号规则

```
FR-<域>-<序号>
```

每条 Functional Requirement 具有全局唯一 ID。ID 一经分配不再复用——即使需求被删除，其编号也不回收。

### 3.2 两级模板

| 级别 | 适用 | 格式 |
|---|---|---|
| **完整模板** | 核心需求（多为 P0） | Description / Input / Processing / Output / Business Rules / Acceptance Criteria / Priority |
| **紧凑条目** | 支持性需求 | 表格形式：ID / 需求陈述 / 关键业务规则 / 优先级 |

两级的**规范性等同**——紧凑条目同样是必须实现的需求，只是无需展开为完整模板。

### 3.3 优先级

| 级别 | 定义 |
|---|---|
| **P0** | 第一阶段核心链路，缺失则无法完成核心投资分析 |
| **P1** | 重要但不阻塞核心链路 |
| **P2** | 增强能力，后续迭代 |

### 3.4 需求陈述用语

| 用语 | 含义 |
|---|---|
| **必须**（shall / must） | 强制要求，不满足即不符合需求 |
| **应当**（should） | 推荐要求，偏离须说明理由 |
| **可以**（may） | 可选能力 |

> **禁止模糊表述**：不使用"快速""智能""合理""良好地""尽可能"等无法验证的措辞。

---

## 4. 功能域总览

| # | 域 | 前缀 | Stage | FR 数 |
|---|---|---|---|---|
| 1 | 基金数据管理 | `FR-DATA` | ① | 6 |
| 2 | 基金分析 | `FR-FUND` | ② | 5 |
| 3 | Benchmark 管理 | `FR-BM` | ① | 5 |
| 4 | 因子计算与验证 | `FR-FACTOR` | ② | 5 |
| 5 | Peer Group 管理 | `FR-PEER` | ③ | 4 |
| 6 | 基金评分 | `FR-SCORE` | ③ | 5 |
| 7 | 排名与分层 | `FR-RANK` | ③ | 4 |
| 8 | 可投资性 | `FR-ELIG` | ①/④ | 4 |
| 9 | 候选基金池 | `FR-UNIV` | ④ | 5 |
| 10 | 收益估计 | `FR-RET` | ⑤-A | 4 |
| 11 | 风险与相关性 | `FR-RISK` | ⑤-B | 4 |
| 12 | 组合构建 | `FR-CONS` | ⑥ | 5 |
| 13 | 组合优化 | `FR-OPT` | ⑦ | 5 |
| 14 | 组合风险分析 | `FR-PRISK` | ⑦-R | 4 |
| 15 | 回测执行 | `FR-BT` | ⑧ | 5 |
| 16 | 回测偏差控制 | `FR-BIAS` | ⑧ | 4 |
| 17 | 回测结果与评价 | `FR-BTR` | ⑧ | 5 |
| 18 | 投资决策 | `FR-DEC` | ⑦ Output | 5 |
| 19 | 决策可解释性 | `FR-EXPL` | 贯穿 | 4 |
| 20 | 实盘组合 | `FR-LIVE` | ⑨ | 4 |
| 21 | 再平衡 | `FR-REBAL` | ⑩ | 5 |
| 22 | 数据质量 | `FR-DQ` | 支撑 | 5 |
| 23 | 策略版本管理 | `FR-STRAT` | 支撑 | 5 |
| | | | **合计** | **107** |

---

## 5. Requirements

### 5.1 基金数据管理 · `FR-DATA`

---

#### FR-DATA-001 基金主数据管理

**Description**

系统必须维护基金的基础信息，并保证每条事实可还原至任一历史时点的可见状态。

**Input**

外部数据源提供的基金基础信息：代码、名称、Fund Classification、成立日、规模、费率结构、基金经理及任职记录、Fund Lifecycle Status。

**Processing**

对每条事实记录三元时点属性 `effective_at`、`available_at`、`version`；数据修订生成新版本，不覆盖旧版本。

**Output**

带三元时点标记的标准化基金主数据。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 每条事实必须携带 `effective_at`、`available_at`、`version` |
| BR-2 | 数据修订必须产生新 `version`，**严禁原地覆盖** |
| BR-3 | `available_at` 为该事实首次对平台可见的时刻，是 Point-in-Time 判定的唯一依据 |
| BR-4 | 基金清盘、合并、转型后，其历史数据必须完整保留 |

**Acceptance Criteria**

```
Given  某基金的规模数据于 2026-08-25 被修订，修订所属期间为 2026-06-30
When   系统接收该修订
Then   生成新 version，effective_at = 2026-06-30，available_at = 2026-08-25
And    原 version 保留可查
And    以 decision_at = 2026-07-15 查询时，返回修订前的版本
```

**Priority** · P0

---

#### FR-DATA-002 净值序列管理

**Description**

系统必须维护基金的净值序列，并提供统一口径的复权净值。

**Input**

原始净值、分红记录、份额拆分记录。

**Processing**

按全平台统一的复权规则计算复权净值；复权规则显式声明并版本化。

**Output**

复权净值序列，带三元时点标记。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 收益计算一律基于**复权净值** |
| BR-2 | 复权规则全平台统一，且必须显式声明，不得隐含在计算逻辑中 |
| BR-3 | 净值修订按 `version` 管理，回测取 `available_at ≤ decision_at` 中 `version` 序号最大者 |
| BR-4 | 基金净值**已扣除管理费与托管费**，下游计算不得重复扣除 |

**Acceptance Criteria**

```
Given  某基金在区间内有一次分红
When   计算该区间收益率
Then   使用复权净值计算，收益率不因分红出现虚假下跌
And    所用复权规则版本随结果一并返回
```

**Priority** · P0

---

#### FR-DATA-003 ~ FR-DATA-006 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-DATA-003** | 系统必须维护基金分类（`Fund Classification`）及其变更历史 | 分类变更按三元时点记录；回测使用当时分类；分类变更同时触发 Peer Group 与 Benchmark 变更 | P0 |
| **FR-DATA-004** | 系统必须维护 `Fund Lifecycle Status`，取值为 `NORMAL` / `SUSPENDED_SUBSCRIPTION` / `LIQUIDATED` / `MERGED` / `TRANSFORMED` | 状态变更按三元时点记录；公告发布时刻为 `available_at`，生效日为 `effective_at` | P0 |
| **FR-DATA-005** | 系统必须支持按任一历史 `decision_at` 查询当时可见的数据视图 | 筛选条件为 `available_at ≤ decision_at`，取 `version` 最大的合格版本 | P0 |
| **FR-DATA-006** | 系统必须维护基金经理任职记录与变更事件 | `Manager Tenure` 为 Factor 与准入条件；`Manager Change` 为事件，可触发观察期规则 | P1 |

---

### 5.2 基金分析 · `FR-FUND`

---

#### FR-FUND-001 多周期业绩计算

**Description**

系统必须按标准分析周期计算基金业绩，并在数据不足时明确标记，而非填充。

**Input**

复权净值序列、`Analysis Period`（1M / 3M / 6M / 1Y / 3Y / 5Y）、`decision_at`。

**Processing**

按 Trading-day Period 口径计算各周期收益，年化因子 252。

**Output**

各周期收益率、累计收益率、Rolling Return 序列；数据不足的周期返回 `UNAVAILABLE`。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 全部周期指标采用 **Trading-day Period，年化因子 252** |
| BR-2 | 起止规则 `(start, end]`；端点落非交易日时**向前取最近交易日** |
| BR-3 | 成立日净值作为序列起点，成立日当日不计入收益区间 |
| BR-4 | 基金成立时长不足该周期时，返回 `UNAVAILABLE`，**严禁**以均值、零、同类值或起始日至今年化等任何方式填充 |
| BR-5 | 系统必须额外提供日历口径收益，**仅供与官方披露核对，不参与评分、筛选、组合构建或回测** |

**Acceptance Criteria**

```
Given  某基金成立于 2 年前
When   请求 1M / 3M / 6M / 1Y / 3Y / 5Y 收益
Then   1M / 3M / 6M / 1Y 返回数值
And    3Y / 5Y 返回 UNAVAILABLE
And    返回结果中不存在任何填充值
And    同时返回一份日历口径收益，并标注其用途限制
```

**Priority** · P0

---

#### FR-FUND-002 ~ FR-FUND-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-FUND-002** | 系统必须计算并提供风险指标：Volatility、Downside Volatility、Maximum Drawdown、VaR 95%、CVaR 95%、Drawdown Duration、Recovery Duration | Maximum Drawdown 必须与 Drawdown / Recovery Duration 联合返回；VaR 与 CVaR 成对返回 | P0 |
| **FR-FUND-003** | 系统必须计算并提供风险调整指标：Sharpe、Sortino、Calmar、Alpha、Beta、Information Ratio、Tracking Error | Benchmark 为 `UNAVAILABLE` 时，Alpha / Beta / IR / TE 一并返回 `UNAVAILABLE`（见 FR-BM-004） | P0 |
| **FR-FUND-004** | 系统必须计算并提供稳定性指标：Win Rate、R²、Skewness、Kurtosis，以及 12M Rolling Return / Sharpe / Volatility / Maximum Drawdown | 必须提供 Rolling **序列**而非仅最新值；Win Rate 默认统计周期为月度且可配置；R² 标注为描述性指标 | P0 |
| **FR-FUND-005** | 系统必须支持多基金横向比较，以统一口径并列展示各类指标 | 跨 `Peer Group` 比较时必须提示可比性限制；`UNAVAILABLE` 指标以明确标记呈现，不留空、不补零 | P0 |

---

### 5.3 Benchmark 管理 · `FR-BM`

---

#### FR-BM-001 Fund Benchmark 确定

**Description**

系统必须在给定 `decision_at` 下为每只基金确定唯一的 Fund Benchmark Definition。

**Input**

基金官方业绩比较基准、策略指定基准、分类默认基准映射、系统兜底基准、`decision_at`。

**Processing**

按五级优先级顺序执行，命中即止。

**Output**

该基金在该时点的 Fund Benchmark Definition，含全部 Component 及权重、来源优先级、映射规则版本。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 选取优先级：① 基金官方业绩比较基准 → ② 官方基准的组成指数及权重 → ③ Strategy-specific Benchmark → ④ Fund Classification Default Benchmark → ⑤ System Default Benchmark |
| BR-2 | 每条映射必须记录 `effective_at`、`available_at`、`source`、`mapping_rule_version` |
| BR-3 | Benchmark Mapping 必须满足 PIT——回测在 `T` 时点使用 `available_at ≤ T` 的映射版本 |
| BR-4 | **Composite Benchmark 不得简化为单一指数**，必须保留各 Component 及其权重 |
| BR-5 | 无法确定有效 Benchmark 时，依赖 Benchmark 的全部指标标记 `UNAVAILABLE` |
| BR-6 | **严禁**使用未来信息确定 Benchmark；**严禁**使用未经声明的替代 Benchmark 填补缺口 |

**Acceptance Criteria**

```
Given  某基金官方业绩比较基准为「沪深300收益率×80% + 中债综合×20%」
When   系统确定该基金的 Fund Benchmark
Then   按优先级 2 保留两个 Component 及其权重
And    不简化为单一指数
And    记录 source = 官方基准组成、mapping_rule_version 与三元时点

Given  某基金于 2024-06-01 转型，转型公告于 2024-05-20 发布
When   回测在 2024-05-25 计算该基金超额收益
Then   使用转型前的 Benchmark（因 effective_at > decision_at）
And    2024-06-01 之后使用转型后的 Benchmark
```

**Priority** · P0

---

#### FR-BM-002 ~ FR-BM-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-BM-002** | 系统必须支持 Benchmark 映射规则的配置与版本化 | 映射规则不得硬编码；变更产生新 `Benchmark Version` | P0 |
| **FR-BM-003** | 系统必须支持 `Portfolio Benchmark` 的定义，与 `Fund Benchmark` 分离管理 | 组合基准按**策略目标配置比例**加权构成，而非实际持仓比例；属 Strategy Version 组成 | P0 |
| **FR-BM-004** | 系统必须在 Benchmark 数据缺失或无法确定时，将 Alpha、Beta、Information Ratio、Tracking Error、超额收益、R²、Relative Performance Score 标记为 `UNAVAILABLE` | 不得使用任何替代基准填补 | P0 |
| **FR-BM-005** | 系统必须提供 Benchmark 数据完整性检查 | 缺失须可告警、可追溯 | P1 |

---

### 5.4 因子计算与验证 · `FR-FACTOR`

---

#### FR-FACTOR-001 因子计算

**Description**

系统必须基于时点对齐的基金数据计算 Factor，并保证结果可复现。

**Input**

`Fund Data`（按 `available_at ≤ decision_at` 筛选）、Factor 定义、`Metric Version`。

**Processing**

按 Factor 定义计算原始值，并在 `Peer Group` 内执行标准化。

**Output**

因子值矩阵（基金 × 因子 × 时间）、标准化后的因子暴露、所用 `Metric Version`。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 相同输入数据版本与参数，任意时刻重算结果必须完全一致 |
| BR-2 | 标准化方法必须显式声明并版本化，不得隐含在计算逻辑中 |
| BR-3 | 标准化必须在 `Peer Group` 内进行 |
| BR-4 | Factor 层**不做多因子加权合成**——任何"综合因子""因子总分"属于 `Fund Score` |
| BR-5 | 每个 Factor 必须声明 `Preference Direction` 与 `Factor Usage` |

**Acceptance Criteria**

```
Given  相同的数据版本、Peer Group 版本与 Metric Version
When   在不同时刻重复计算同一 Factor
Then   两次结果完全一致
And    结果携带所用的 Metric Version
```

**Priority** · P0

---

#### FR-FACTOR-002 因子有效性检验

**Description**

系统必须提供因子有效性检验能力，用于判断因子与未来收益之间是否存在稳定的统计关系。

**Input**

Factor 值序列、未来收益序列、检验区间、`Peer Group`。

**Processing**

计算 IC、ICIR、分层单调性、因子稳定性、与既有因子的相关性。

**Output**

因子有效性检验报告。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 全部计算仅使用 `available_at ≤ decision_at` 的数据 |
| BR-2 | 因子有效性检验属因子研究的固有内容，**与系统是否使用 ML 无关**——第一阶段保留该能力，但不引入任何 ML 预测 |
| BR-3 | 分层检验必须在 `Peer Group` 内进行 |

**Acceptance Criteria**

```
Given  某 Factor 与历史检验区间
When   执行有效性检验
Then   输出 IC、ICIR、分层单调性、稳定性、与既有因子的相关性
And    检验过程未使用任何机器学习模型
```

**Priority** · P0

---

#### FR-FACTOR-003 ~ FR-FACTOR-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-FACTOR-003** | 系统必须保存因子历史值，支持按任一历史时点查询 | 历史值不可覆盖；查询遵循 PIT | P0 |
| **FR-FACTOR-004** | 系统必须支持因子的版本管理（`Metric Version`） | 计算逻辑变更产生新版本；历史结果关联其产出版本 | P0 |
| **FR-FACTOR-005** | 系统必须支持新因子的接入与下线，且不影响既有因子的历史值 | 因子集合可配置；新增因子须通过因子层与组合层两道验证方可进入评分 | P1 |

---
### 5.5 Peer Group 管理 · `FR-PEER`

---

#### FR-PEER-001 Peer Group 构成

**Description**

系统必须为每个决策时点构建 `Peer Group`，作为评分标准化、排名、分位与分层的样本集。

**Input**

`Fund Coverage`、`Fund Classification`（按 `available_at ≤ decision_at` 的版本）、参与规则、`decision_at`。

**Processing**

按分类与参与规则确定组成员，不引用 `Fund Score` 或 `Fund Universe`。

**Output**

该时点的 Peer Group 成员列表、组规模、所用分类版本。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | **`Peer Group` 的构成不得依赖 `Fund Score` 或 `Fund Universe`**——否则形成 `Score → Universe → Peer Group → Score` 的循环依赖，结果既不唯一也不可复现 |
| BR-2 | Peer Group 必须满足 PIT——使用 `available_at ≤ decision_at` 的分类版本 |
| BR-3 | 历史 Peer Group 必须包含当时存续的全部基金，**含此后清盘的基金** |
| BR-4 | 可投资性不影响入组——暂停申购的基金仍参与评价 |
| BR-5 | 某指标为 `UNAVAILABLE` 的基金，不参与该指标的排名，但仍属于该组 |

**Acceptance Criteria**

```
Given  某基金于 2023 年清盘
When   构建 2022-06-30 的 Peer Group
Then   该基金包含在组内
And    组构成基于 available_at ≤ 2022-06-30 的分类版本
And    组构成过程未读取任何 Fund Score 或 Fund Universe 数据
```

**Priority** · P0

---

#### FR-PEER-002 ~ FR-PEER-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-PEER-002** | 系统必须保存每个决策时点的 Peer Group 快照，支持按历史时点查询 | 未留存快照的时点，系统必须拒绝提供推算结果 | P0 |
| **FR-PEER-003** | 系统必须在 Peer Group 样本量低于阈值时标记该组评分为低置信 | 分位排名在小样本下不具统计意义 | P1 |
| **FR-PEER-004** | 系统必须维护 `Evaluation Profile`，至少区分 Active Equity / Passive Equity / Bond / Hybrid | Evaluation Profile 决定适用的指标集合、权重与 Preference Direction，与 Peer Group 是不同维度 | P0 |

---

### 5.6 基金评分 · `FR-SCORE`

---

#### FR-SCORE-001 综合评分计算

**Description**

系统必须基于给定的 Fund、`decision_at` 与 `Scoring Version` 计算 `Fund Score`，并返回完整的 Score Breakdown。

**Input**

标准化后的 Factor 暴露、`Scoring Version`（指标集合 + 权重 + 标准化方式 + Preference Direction + 缺失处理规则）、`Peer Group`、`Evaluation Profile`。

**Processing**

按 Preference Direction 转换各 Factor 得分，按权重合成五个子分，再合成总分。

**Output**

Total Score、五个子分、各 Factor 的贡献、`Data Completeness`、Peer Group 规模、所用版本号。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 评分必须可拆解为五个子分：**Return / Risk / Risk-Adjusted / Stability / Relative Performance Score** |
| BR-2 | 标准化必须在 `Peer Group` 内进行，且 Peer Group 独立于 Score 产生 |
| BR-3 | 转换后**分数越高一律代表越优秀**；`TARGET_RANGE` 与 `STRATEGY_DEPENDENT` 方向的 Factor 由 `Evaluation Profile` 定义转换规则 |
| BR-4 | `Fund Score` **不具有收益预测语义**——不得作为 `Return Estimate`，不得作为 `μ` 输入优化器，不得换算为收益率 |
| BR-5 | 评分方案（指标、权重、标准化、方向、缺失处理）必须可配置且版本化，**不得硬编码** |
| BR-6 | 单一维度排名不构成评分——**严禁** `收益率排名 = Fund Score` |

**Acceptance Criteria**

```
Given  某基金、某决策时点与某 Scoring Version
When   请求评分
Then   返回 Total Score 与五个子分
And    每个子分可下钻至参与计算的 Factor、权重与标准化后得分
And    同时返回 Data Completeness 与 Peer Group 规模
And    相同输入重算得到完全一致的结果
```

**Priority** · P0

---

#### FR-SCORE-002 缺失指标处理

**Description**

系统必须在指标为 `UNAVAILABLE` 时按既定规则处理，且不得引入任何填充值。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 该指标不参与评分，其权重按比例重分配给同组其他可用指标；或该子分标记 `UNAVAILABLE` |
| BR-2 | **严禁**用同类均值 / 中位数填充 |
| BR-3 | **严禁**按 0 分参与评分——这会把"数据不足"错误等同于"表现最差" |
| BR-4 | `Data Completeness` 必须随评分一同返回 |

**Acceptance Criteria**

```
Given  某基金 12 个应有指标中有 3 个为 UNAVAILABLE
When   计算评分
Then   3 个指标不参与计算，其权重按规则重分配
And    Data Completeness 返回 9/12
And    结果中不存在任何填充值
```

**Priority** · P0

---

#### FR-SCORE-003 ~ FR-SCORE-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-SCORE-003** | 系统必须按 `Evaluation Profile` 应用不同的指标集合与权重 | 被动型：TE 越低越好且为核心项、费率高权重、**Alpha 不进评分**；主动型：Alpha 与 IR 为核心项、TE 中性；债券型：Maximum Drawdown 最高权重 | P0 |
| **FR-SCORE-004** | 系统必须保存历史评分及其所用版本，支持按历史时点重算 | 历史评分不可覆盖；重算结果须与当时一致 | P0 |
| **FR-SCORE-005** | 系统必须提供评分变化归因：两个时点之间哪些 Factor 导致了分数变化 | 归因须可下钻至 Factor 级 | P1 |

---

### 5.7 排名与分层 · `FR-RANK`

---

#### FR-RANK-001 排名、分位与分层

**Description**

系统必须在 `Peer Group` 内计算排名、分位与 `Fund Tier`。

**Input**

`Fund Score`、`Peer Group`、分层阈值配置。

**Processing**

按派生链计算：`Fund Score → Peer Group Ranking → Percentile → Fund Tier`。

**Output**

排名、分位、Tier、Peer Group 规模与组内绝对水平指标。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 排名与分位必须在 `Peer Group` 内计算，**不得跨基金类型直接排名** |
| BR-2 | `Fund Tier` 按分位划分：**A+ 前 5% / A 5–20% / B 20–50% / C 50–80% / D 后 20%** |
| BR-3 | 分层阈值必须可配置，**严禁硬编码** |
| BR-4 | **`Fund Tier` 必须与该 Peer Group 的绝对水平同屏返回**，至少含组内 Sharpe 中位数与 Maximum Drawdown 中位数 |
| BR-5 | 分层结果必须记录当时的阈值配置版本 |

**Acceptance Criteria**

```
Given  某 Peer Group 含 1,240 只基金，某基金 Score 排名第 40
When   请求该基金的排名信息
Then   返回排名 40 / 1240、分位约前 3.2%、Tier = A+
And    同时返回该组的 Sharpe 中位数与 Maximum Drawdown 中位数
And    仅返回 Tier 而不返回组内绝对水平，视为不满足本需求
```

**Priority** · P0

---

#### FR-RANK-002 ~ FR-RANK-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-RANK-002** | 系统必须保存排名历史，支持查看排名随时间的变化趋势 | 排名历史关联当时的 Peer Group 与 Scoring Version | P1 |
| **FR-RANK-003** | 系统必须支持按不同 `Analysis Period` 分别排名 | 各周期排名独立计算；`UNAVAILABLE` 的基金不参与该周期排名 | P1 |
| **FR-RANK-004** | 系统应当支持在分层中追加绝对门槛（未达标者不得进入 A+ / A） | 门槛值可配置；启用后须在分层结果中标注 | P2 |

---

### 5.8 可投资性 · `FR-ELIG`

---

#### FR-ELIG-001 Investment Eligibility 判定

**Description**

系统必须在给定 `decision_at` 下判定每只基金的可投资性，且与 `Fund Lifecycle Status` 分离管理。

**Input**

`Fund Lifecycle Status`、申赎限制公告、最低申购金额、大额申购限制、ETF 流动性指标、`decision_at`。

**Processing**

综合上述因素判定可建仓 / 可加仓 / 可持有 / 可减仓四个维度。

**Output**

`Investment Eligibility` 状态。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 取值至少区分：`FULLY_ELIGIBLE` / `HOLD_ONLY` / `LIMITED` / `EXIT_ONLY` / `NOT_TRADABLE` |
| BR-2 | **必须与 `Fund Lifecycle Status` 分离**——"暂停申购"意味着不可建仓、不可加仓，但**仍可持有与减仓** |
| BR-3 | 判定必须满足 PIT——依据 `available_at ≤ decision_at` 的最新状态 |
| BR-4 | 回测的每次建仓与加仓必须校验 Investment Eligibility |

**Acceptance Criteria**

```
Given  某基金于 T 时点处于暂停申购状态
When   查询该基金的 Investment Eligibility
Then   返回 HOLD_ONLY
And    可建仓 = 否，可加仓 = 否，可持有 = 是，可减仓 = 是
And    该基金不因暂停申购被从持仓中强制清出
```

**Priority** · P0

---

#### FR-ELIG-002 ~ FR-ELIG-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-ELIG-002** | 系统必须支持 ETF / 场内基金的流动性准入判定 | 至少含日均成交额、换手率、买卖价差、规模、申赎机制状态；不满足则可投资性降级 | P1 |
| **FR-ELIG-003** | 系统必须保存可投资性状态的历史，支持按历史时点查询 | 状态变更按三元时点记录 | P0 |
| **FR-ELIG-004** | 系统必须支持将可投资性作为 `Eligibility Rules` 的条件之一 | 可配置为准入条件；与评价维度正交 | P0 |

---

### 5.9 候选基金池 · `FR-UNIV`

---

#### FR-UNIV-001 Fund Universe 生成

**Description**

系统必须根据已配置的 `Eligibility Rules` 与（可选的）`Fund Score` 生成 `Fund Universe`。

**Input**

`Fund Coverage`、`Eligibility Rules` 版本、`Fund Score`（可选）、`decision_at`。

**Processing**

先按准入规则过滤，再按所选构成策略叠加 Score 阈值或 Top-N。

**Output**

候选基金集合及完整快照。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | Universe 的**必要定义**是 `Eligibility Rules`；`Fund Score` 排序是**可选**机制 |
| BR-2 | 必须支持三种构成策略：① 仅准入 ② 准入 + Score 阈值 ③ 准入 + Score Top-N |
| BR-3 | 采用策略 ① 时，快照中评分字段为空属正常，不构成留痕缺失 |
| BR-4 | **入池 ≠ 持有**——入池仅代表可被选，实际权重由 Stage ⑦ 求解 |
| BR-5 | 系统必须区分**探索性筛选**与**正式准入规则**——前者不产生 Fund Universe，不版本化，不可回测 |

**Acceptance Criteria**

```
Given  一个 Eligibility Rules 版本与决策时点，构成策略为"仅准入"
When   生成 Fund Universe
Then   返回全部满足准入条件的基金
And    快照中评分版本与评分字段为空，系统不报错、不视为缺失
And    该 Universe 可用于 Equal Weight 与 Minimum Volatility 策略
```

**Priority** · P0

---

#### FR-UNIV-002 Universe 快照与留痕

**Description**

系统必须为每个决策时点留存完整的 Universe 快照。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 快照必须含：`decision_at`、成员列表、Eligibility Rules 版本、Scoring 版本、评分与子分、入池原因、出池原因、`Data Completeness`、`Investment Eligibility` 状态 |
| BR-2 | 对上期在池、本期出池的基金，必须记录出池原因 |
| BR-3 | **未留存快照的时点，其回测结果无效**——系统必须拒绝以推算方式提供历史 Universe |

**Acceptance Criteria**

```
Given  某历史决策时点已留存 Universe 快照
When   请求当时的 Universe
Then   返回留存的快照，而非用当前数据重新推算

Given  某历史时点未留存快照
When   请求当时的 Universe
Then   系统明确返回"快照缺失"，不提供推算结果
```

**Priority** · P0

---

#### FR-UNIV-003 ~ FR-UNIV-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-UNIV-003** | 系统必须为每只基金提供入池 / 未入池的条件级明细 | 记录通过与未通过的具体条件；被排除基金同样记录 | P0 |
| **FR-UNIV-004** | 系统必须支持 `Eligibility Rules` 的配置与版本化 | 规则不得硬编码；变更产生新版本；属 Strategy Version 组成 | P0 |
| **FR-UNIV-005** | 系统应当在 Universe 规模异常变动时告警 | 骤增骤减通常意味着规则或数据问题 | P1 |

---
### 5.10 收益估计 · `FR-RET`

---

#### FR-RET-001 Quantitative Return Estimate

**Description**

系统必须基于历史数据、通过预先定义的量化估计方法，为 `Fund Universe` 内每只基金产出收益估计。

**Input**

`Fund Universe`、复权净值序列（按 `available_at ≤ decision_at` 筛选）、估计方法配置、`Return Estimate Version`。

**Processing**

按配置的量化方法计算收益估计。

**Output**

收益估计向量 `μ`、所用方法、三项口径声明、`Return Estimate Version`。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 第一阶段允许的方法：Historical Mean、Historical CAGR、Rolling Mean、Benchmark-relative Return、Shrinkage Estimate |
| BR-2 | **严禁**使用 ML / AI / LLM 预测——`Return Estimate` 必须能仅由量化方法独立产出 |
| BR-3 | 必须显式声明三项口径：**Estimation Window**、**Estimation Horizon**、**Return Basis**（绝对 or 超额） |
| BR-4 | 必须与 `Fund Score` **逻辑独立**——不得由 Score 换算、映射或缩放得到 |
| BR-5 | 仅使用 `available_at ≤ decision_at` 的数据 |
| BR-6 | Historical CAGR 为已实现收益率，作为估计使用时必须显式声明外推假设 |
| BR-7 | Benchmark-relative 产出的是超额收益，若优化目标使用绝对收益，必须显式还原 `μ = benchmark + excess` |
| BR-8 | `Return Basis` 必须与优化器目标函数一致，绝对与超额不可混用 |

**Acceptance Criteria**

```
Given  Fund Universe 与决策时点 T
When   计算 Return Estimate
Then   返回每只基金的估计值、所用方法与三项口径声明
And    计算过程未使用任何机器学习模型
And    计算过程未读取 Fund Score
And    全部输入满足 available_at ≤ T
```

**Priority** · P0

---

#### FR-RET-002 ~ FR-RET-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-RET-002** | 系统必须支持估计方法的配置与版本化（`Return Estimate Version`） | 方法与参数不得硬编码；属 Strategy Version 组成 | P0 |
| **FR-RET-003** | 系统必须保存历史 Return Estimate，支持按历史时点查询与重算 | 重算结果须与当时一致 | P0 |
| **FR-RET-004** | 系统应当提供 Return Estimate 的稳定性度量（相邻时点间的变动幅度） | 估计值剧烈跳动会导致组合频繁换手 | P1 |

---

### 5.11 风险与相关性 · `FR-RISK`

---

#### FR-RISK-001 事前风险与相关性计算

**Description**

系统必须为 `Fund Universe` 计算不依赖权重的事前风险量与相关性结构。

**Input**

`Fund Universe`、复权净值序列（PIT 筛选）、`Risk Model Version`。

**Processing**

基于历史收益序列计算各风险量与矩阵。

**Output**

Historical Return Matrix、Volatility Vector、Downside Risk、Drawdown Metrics、Correlation Matrix、Covariance Matrix `Σ`。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 全部为**事前风险**——只依赖历史收益序列，**不依赖权重** |
| BR-2 | 本阶段**不产出** Risk Contribution 与 Concentration——两者依赖权重 `w`，属 Stage ⑦-R |
| BR-3 | **严禁**使用 ML Risk Prediction |
| BR-4 | `μ` 与 `Σ` 必须**时间尺度与年化口径一致**（注：两者本非相同量纲，要求的是口径一致） |
| BR-5 | 估计方法必须显式声明并版本化 |
| BR-6 | 仅使用 `available_at ≤ decision_at` 的数据 |

**Acceptance Criteria**

```
Given  某 Fund Universe 与决策时点
When   计算风险与相关性
Then   返回 Volatility、Downside Risk、Drawdown、Correlation Matrix、Covariance Matrix
And    返回结果中不含 Risk Contribution 与 Concentration
And    μ 与 Σ 采用相同的持有期与年化口径
```

**Priority** · P0

---

#### FR-RISK-002 ~ FR-RISK-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-RISK-002** | 系统必须支持协方差矩阵的可用性检查（正定性、样本充足度） | 不可用时按既定规则收缩或阻断，规则须预先定义 | P0 |
| **FR-RISK-003** | 系统必须保存历史风险与相关性结果，支持按历史时点查询 | 结果关联 `Risk Model Version` | P0 |
| **FR-RISK-004** | 系统应当提供协方差矩阵的稳定性度量 | 相邻时点变动幅度与条件数 | P1 |

---

### 5.12 组合构建 · `FR-CONS`

---

#### FR-CONS-001 Portfolio Strategy 定义

**Description**

系统必须支持将组合策略定义为完整、可被优化器直接消费的形式化问题描述。

**Input**

`Eligibility Rules`、目标函数或权重规则、约束集、风险预算。

**Processing**

校验四要素完整性，装配为形式化优化问题。

**Output**

一个完整定义的优化问题：目标函数形式、约束集、风险预算分配。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 策略必须四要素齐备：**Eligibility Rules + Objective / Weighting Rule + Constraint Set + Risk Budget**，缺一系统必须拒绝保存 |
| BR-2 | 本阶段**不产出权重数值**——权重求解属 Stage ⑦ |
| BR-3 | 约束集必须显式、可校验，且能判断问题是否可行 |
| BR-4 | 产出必须是形式化问题描述，而非自然语言表述的投资理念 |

**Acceptance Criteria**

```
Given  用户配置策略时仅指定了目标函数
When   保存该策略
Then   系统拒绝保存并指出缺少约束集与风险预算
```

**Priority** · P0

---

#### FR-CONS-002 权重生成方式配置

**Description**

系统必须支持两类权重生成路径，并在配置时明确区分。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | **路径一 · 确定性权重规则**：Equal Weight、Score Weight、类别固定配比——直接映射后施加约束，不求解优化问题 |
| BR-2 | **路径二 · 优化目标**：Minimum Volatility、Maximum Sharpe——求解优化问题 |
| BR-3 | 选择 `Score Weight` 时，系统必须明确标注：该规则是**显式的确定性权重映射**，**不意味着 `Fund Score` 是收益估计** |
| BR-4 | **`Fund Score` 在任何情况下都不得作为 `μ` 输入优化器** |
| BR-5 | 所选路径与规则必须记入 `Portfolio Rule Version` |

**Acceptance Criteria**

```
Given  用户选择 Score Weight 作为权重生成方式
When   保存配置
Then   系统标注该规则属于确定性权重规则路径
And    系统不将 Fund Score 传入优化器的收益输入
And    该规则记入 Portfolio Rule Version 并可回测
```

**Priority** · P0

---

#### FR-CONS-003 Risk Budget 定义

**Description**

系统必须要求每条 Risk Budget 完整定义六要素。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 六要素：① 风险指标 ② 预算值 ③ 适用范围 ④ 计算方式 ⑤ 超预算处理方式 ⑥ 硬约束或软目标 |
| BR-2 | **六要素不全的 Risk Budget 不得进入优化问题** |
| BR-3 | Risk Budget 是**事前目标**，与 Stage ⑦-R 的事后 Risk Contribution 分属不同概念，两者必须同时留存 |

**Acceptance Criteria**

```
Given  用户新增一条 Risk Budget 但未指定"超预算处理方式"
When   保存
Then   系统拒绝保存并指出缺失要素
```

**Priority** · P0

---

#### FR-CONS-004 ~ FR-CONS-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-CONS-004** | 系统必须支持配置约束集：单基金权重上限、类别权重上限、集中度上限、换手率上限、组合波动率上限、相关性约束 | **最大回撤不作为事前约束提供**——未来回撤路径未知，非建仓时可直接计算的量；如需事前控制须先配置可计算的代理约束 | P0 |
| **FR-CONS-005** | 系统必须支持配置类别目标配置比例（资产配置结构） | 配置比例用于构成 `Portfolio Benchmark`；属 Portfolio Rule Version | P1 |

---

### 5.13 组合优化 · `FR-OPT`

---

#### FR-OPT-001 目标权重求解

**Description**

系统必须在给定形式化问题下求解目标权重向量，并保证可复现。

**Input**

`Return Estimate`、`Risk Estimate`、`Covariance Matrix`、`Constraint Set`、`Risk Budget`、`Optimization Objective`。

**Processing**

在既定目标与约束下求解。

**Output**

`Optimization Run` 记录：目标权重向量 `w`、求解状态（是否收敛 / 是否可行）、影子价格与敏感性等诊断信息。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 相同输入必须得到完全相同的输出（固定随机种子与求解器版本） |
| BR-2 | 优化器**不定义**约束与目标——只求解已定义好的问题 |
| BR-3 | 优化器**不得自行放松约束** |
| BR-4 | 求解产出的是目标权重，非实际持仓 |

**Acceptance Criteria**

```
Given  相同的 μ、Σ、约束集、风险预算与目标函数
When   重复执行优化
Then   两次得到完全相同的权重向量
And    返回求解状态与诊断信息
```

**Priority** · P0

---

#### FR-OPT-002 不可行与不收敛处理

**Description**

系统必须在优化问题不可行或不收敛时显式失败并阻断，且提供人工处理闭环。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 不可行 / 不收敛时，`Decision Status` 置为 `INFEASIBLE`，**不产出 Proposed Investment Decision** |
| BR-2 | **严禁**自动放松约束、退化为等权、沿用上期权重等任何静默降级 |
| BR-3 | 必须记录不可行原因并上报，进入人工处理流程 |
| BR-4 | 人工可选择：调整约束 / 调整 Universe / 沿用上期 / 中止本期 |
| BR-5 | 调整约束或 Universe 必须**升级对应规则版本并留痕** |
| BR-6 | 选择"沿用上期权重"必须**显式声明并记录**，不得作为静默降级 |
| BR-7 | 不可行事件必须记入决策快照，供事后分析约束是否过紧 |

**Acceptance Criteria**

```
Given  约束集互相冲突导致无解
When   执行优化
Then   Decision Status = INFEASIBLE
And    未产出 Proposed Investment Decision
And    未修改任何约束
And    不可行原因被记录并上报
```

**Priority** · P0

---

#### FR-OPT-003 ~ FR-OPT-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-OPT-003** | 系统必须记录每次 `Optimization Run` 的完整输入、状态、输出与诊断 | Optimization Run 是审计链上的一环 | P0 |
| **FR-OPT-004** | 系统必须支持配置优化目标：Equal Weight、Score Weight、Minimum Volatility、Maximum Sharpe | Risk Parity、Minimum CVaR 为后续能力 | P0 |
| **FR-OPT-005** | 系统应当支持在同一 Universe 上比较不同优化目标产出的组合 | 用于评估复杂度是否物有所值 | P1 |

---

### 5.14 组合风险分析 · `FR-PRISK`

---

#### FR-PRISK-001 事后组合风险计算

**Description**

系统必须在权重确定后计算依赖权重的组合层风险量。

**Input**

目标权重 `w`、协方差矩阵 `Σ`、类别归属、Factor 暴露。

**Processing**

计算组合层风险分解。

**Output**

Portfolio Volatility、Marginal Risk Contribution、Total Risk Contribution、Concentration（HHI / 前 N 大权重）、Factor Exposure、类别暴露。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 本阶段全部指标**依赖权重 `w`**——在 Stage ⑦ 求出 `w` 之前，最终组合的风险贡献在数学上不存在 |
| BR-2 | 必须同时返回事前 `Risk Budget` 与事后实际值的对照，标明各条预算是否达成 |
| BR-3 | 事前 Risk Budget 与事后 Risk Contribution **必须同时留存于决策快照** |

**Acceptance Criteria**

```
Given  优化已产出目标权重
When   计算组合风险
Then   返回 Portfolio Volatility、MRC、TRC、Concentration、Factor Exposure
And    同时返回各条 Risk Budget 的目标值与实际值对照
And    标明每条预算是否达成
```

**Priority** · P0

---

#### FR-PRISK-002 ~ FR-PRISK-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-PRISK-002** | 系统必须校验组合是否满足全部约束，并标识哪些约束为 binding | binding 信息用于解释权重来源（见 FR-EXPL-001） | P0 |
| **FR-PRISK-003** | 系统必须输出 `Risk Alert Level`：`NORMAL` / `WARNING` / `CRITICAL` | `CRITICAL` 必须阻断调仓流程，需人工确认后方可继续 | P0 |
| **FR-PRISK-004** | 系统必须支持识别并提示高相关持仓 | 相关性集中会使"名义分散"的组合仍承担集中风险 | P0 |

---
### 5.15 回测执行 · `FR-BT`

---

#### FR-BT-001 回测执行

**Description**

系统必须按历史时间轴重放完整策略链路，并复用与实盘相同的策略领域逻辑。

**Input**

`Strategy Version`（九项组成）、历史区间、初始资金、调仓频率配置、`Portfolio Benchmark`、交易成本配置。

**Processing**

在每个 Rebalance Decision Point 重放：Factor → Peer Group → Score → Universe → Return Estimate → Risk / Correlation → Construction → Optimization。

**Output**

回测净值序列、逐期持仓与权重、逐期决策快照、绩效与归因结果。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 回测必须复用与实盘**同一套策略领域逻辑**，差异仅允许存在于数据源与时间轴 |
| BR-2 | **不允许存在两套策略规则实现** |
| BR-3 | 时间推进以 **Rebalance Decision Point** 为单位，`T+n` 中的 `n` 由触发类型决定，**不是固定时间单位** |
| BR-4 | 回测必须记录所使用的全部九项版本号 |
| BR-5 | 回测**不产生任何实盘指令** |

**Acceptance Criteria**

```
Given  一个完整 Strategy Version 与历史区间
When   执行回测
Then   系统在每个 Rebalance Decision Point 重放完整链路
And    每期留存决策快照
And    结果记录九项版本号
And    未产生任何实盘指令
```

**Priority** · P0

---

#### FR-BT-002 样本外与滚动验证

**Description**

系统必须支持 In-Sample / Out-of-Sample 划分与 Walk-forward 验证。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | **In-Sample** 用于规则设计与参数选择 |
| BR-2 | **Parameter Freeze 时点必须显式记录**并纳入 `Strategy Version` |
| BR-3 | **Out-of-Sample 仅用于验证**——OOS 结果**不得**用于反向调参 |
| BR-4 | **Walk-forward 为第一阶段必须支持**——滚动重复 IS → Freeze → OOS |
| BR-5 | 若因 OOS 不通过而修改规则，必须升 `Strategy Version` 并**重新划分 IS/OOS** |
| BR-6 | 策略批准必须以 OOS 结果为依据，仅 IS 表现良好不足以批准 |

**Acceptance Criteria**

```
Given  策略已在 IS 区间完成参数选择
When   进入 OOS 验证
Then   Parameter Freeze 时点已记录并纳入 Strategy Version
And    系统不允许基于 OOS 结果修改参数后复用同一 OOS 区间
And    支持配置 Walk-forward 的窗口与步长并输出各期结果
```

**Priority** · P0

---

#### FR-BT-003 ~ FR-BT-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-BT-003** | 系统必须支持配置回测区间、初始资金与调仓频率 | 回测区间应覆盖不同市场环境（上涨 / 下跌 / 震荡），否则无法判断环境依赖性 | P0 |
| **FR-BT-004** | 系统必须按既定组成计入交易成本 | 扣除申购费、赎回费、买卖价差、冲击成本；**不扣除管理费与托管费**（已含于基金净值），重复扣除会系统性低估表现 | P0 |
| **FR-BT-005** | 系统必须持久化回测结果与逐期快照，支持事后追溯与重算 | 相同版本重跑须得到完全一致的结果 | P0 |

---

### 5.16 回测偏差控制 · `FR-BIAS`

---

#### FR-BIAS-001 Look-ahead Bias 防护

**Description**

系统必须保证历史决策仅使用当时可获得的数据。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 判定标准为 **`available_at ≤ decision_at`**——依据是**可获得时点**，不是生效日期 |
| BR-2 | 同一 `effective_at` 存在多个 `version` 时，取 `available_at ≤ decision_at` 中 `version` 序号最大者 |
| BR-3 | 适用于**全部派生量与映射关系**：Factor、Peer Group、Fund Score、Fund Universe、Return Estimate、Correlation、Covariance、Benchmark Mapping、Investment Eligibility |
| BR-4 | 系统必须提供 PIT 校验，任一输入违反即阻断该期决策 |

**Acceptance Criteria**

```
Given  某基金经理变更 effective_at = 2026-08-20、available_at = 2026-08-25
When   回测在 decision_at = 2026-08-22 读取该基金信息
Then   该变更不参与本次决策（因 available_at > decision_at）
And    使用变更前的经理记录
```

**Priority** · P0

---

#### FR-BIAS-002 Survivorship Bias 防护

**Description**

系统必须保证历史样本包含当时真实存在的基金。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 历史 `Peer Group` 与 `Fund Universe` 必须包含当时存续的全部合格基金，**含此后清盘的基金** |
| BR-2 | 回测必须使用当时留存的快照，**不得**用当前数据重新推算历史样本 |
| BR-3 | 清盘基金的历史数据必须完整保留 |
| BR-4 | 组合成分在回测期内清盘时，按事先定义的退出规则处理 |

**Acceptance Criteria**

```
Given  某基金于 2023 年清盘
When   回测 2022 年的 Peer Group 与 Universe
Then   该基金包含在内
And    使用当时留存的快照
```

**Priority** · P0

---

#### FR-BIAS-003 Tradability Bias 防护

**Description**

系统必须保证回测不产生现实中无法成交的交易。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 每次建仓与加仓必须校验 `Investment Eligibility` |
| BR-2 | `HOLD_ONLY` 的基金不得出现在买入清单，但可出现在卖出清单 |
| BR-3 | `NOT_TRADABLE` 的基金既不可买也不可卖，持仓视为冻结并单独标注 |
| BR-4 | 因可投资性限制无法达成目标权重时，必须**显式报告差异**，不得静默用其他基金补足 |

**Acceptance Criteria**

```
Given  某基金在 T 时点为 HOLD_ONLY
When   回测在 T 生成建仓指令
Then   该基金不出现在买入清单
And    已有持仓不被强制清仓
And    因此产生的目标权重差异被显式报告
```

**Priority** · P0

---

#### FR-BIAS-004 偏差处理声明

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-BIAS-004** | 回测报告必须显式声明三类偏差的处理方式 | 未声明处理方式的回测结果不得作为决策依据 | P0 |

---

### 5.17 回测结果与评价 · `FR-BTR`

---

#### FR-BTR-001 回测绩效输出

**Description**

系统必须输出标准绩效指标集合，并与两类基线对比。

**Output**

| 类别 | 指标 |
|---|---|
| 收益 | Cumulative Return、Annualized Return |
| 风险 | Volatility、Maximum Drawdown、VaR、CVaR |
| 风险调整 | Sharpe、Sortino、Calmar |
| 稳定性 | Win Rate |
| 交易 | Turnover、Number of Rebalances、成本侵蚀比例 |

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 必须同时呈现**三方对比**：Strategy / `Portfolio Benchmark` / **Equal Weight Baseline** |
| BR-2 | Equal Weight Baseline 必须建立在**同一 `Fund Universe`** 上 |
| BR-3 | 缺少 Equal Weight 基线的回测报告不满足本需求——无法判断复杂优化相对简单等权是否物有所值 |

**Acceptance Criteria**

```
Given  回测已完成
When   生成对比报告
Then   同时呈现 Strategy、Portfolio Benchmark、Equal Weight Baseline 三条净值曲线
And    Equal Weight Baseline 使用与 Strategy 相同的 Fund Universe
```

**Priority** · P0

---

#### FR-BTR-002 策略评价报告

**Description**

回测报告必须回答稳健性相关的结构性问题，而非仅呈现最终收益。

**Business Rules**

报告必须回答八个问题：

| # | 问题 | 判断依据 |
|---|---|---|
| 1 | 策略是否长期有效 | 分年度 / 分阶段收益 |
| 2 | 收益是否稳定 | 滚动收益与滚动 Sharpe 的波动 |
| 3 | 最大回撤是否可接受 | MaxDD、Drawdown Duration |
| 4 | 是否存在明显失效阶段 | 分阶段超额收益 |
| 5 | 是否过度依赖某些基金 | 收益归因至个基的集中度 |
| 6 | 是否过度依赖某些市场环境 | 分市场环境的表现 |
| 7 | 换手率是否过高 | Turnover、成本侵蚀比例 |
| 8 | 是否优于 Benchmark **与 Equal Weight 基线** | 三方对比 |

**Priority** · P0

---

#### FR-BTR-003 ~ FR-BTR-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-BTR-003** | 系统必须提供收益归因，可下钻至个基与类别 | 用于识别过度依赖 | P0 |
| **FR-BTR-004** | 系统必须按既定统计方法判定策略是否优于基线：IR 阈值 + 跑赢概率 + Block Bootstrap 置信区间下界为正，三条全过 | **不采用 t 检验**——60 个月样本下检出功效不足（漏判），且自相关与肥尾使 iid 正态假设不成立（误判）。三个阈值确定前，报告**不得使用"显著优于"** | P0 |
| **FR-BTR-005** | 系统必须支持比较不同 `Strategy Version` 在同一区间的回测结果 | Major 级版本变更前后的结果**不可直接比较**，系统须在对比时标注 | P1 |

---

### 5.18 投资决策 · `FR-DEC`

---

#### FR-DEC-001 决策状态机

**Description**

系统必须以显式状态管理投资决策的完整生命周期。

**Business Rules**

| 状态 | 含义 | 后续 |
|---|---|---|
| `PROPOSED` | 系统产出，待复核 | → APPROVED / REJECTED / OVERRIDDEN / EXPIRED |
| `APPROVED` | 原样批准 | → 生成 Rebalancing Recommendation |
| `REJECTED` | 拒绝，本期不调仓 | 终止，记录拒绝理由 |
| `OVERRIDDEN` | 人工修改权重后批准 | → 生成 Recommendation，**必须完整留痕** |
| `EXPIRED` | 超时未处理而失效 | 终止，记录超时原因 |
| `SUPERSEDED` | 被更新的决策取代 | 终止，记录取代关系 |
| `INFEASIBLE` | 优化不可行，未产出决策 | 进入 FR-OPT-002 处理流程 |

**补充规则**

| # | 规则 |
|---|---|
| BR-1 | 系统产出的是 `Proposed Investment Decision`，**不是** `Approved Investment Decision` |
| BR-2 | **系统推荐 ≠ 投资决策**——仅经人工复核放行后方成为生效决策 |
| BR-3 | 每次状态流转必须记录操作人与时刻 |

**Priority** · P0

---

#### FR-DEC-002 Override 留痕

**Description**

系统必须在人工修改目标权重时强制完整留痕。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 必须记录五个字段：`original_target_weight`、`approved_target_weight`、`override_reason`、`operator`、`timestamp` |
| BR-2 | `override_reason` 为空或为占位符时，**系统必须拒绝放行** |
| BR-3 | 五字段缺任一项，不得生成 Rebalancing Recommendation |
| BR-4 | Override 频率本身必须可统计——频繁 override 说明策略与判断存在系统性分歧 |

**Acceptance Criteria**

```
Given  系统提出某基金权重 12%，操作人改为 7% 但未填写理由
When   提交
Then   系统拒绝放行并指出 override_reason 缺失

Given  五字段齐备
When   提交
Then   Decision Status = OVERRIDDEN
And    修改后的权重成为 Approved Investment Decision
And    原始权重与修改权重同时保留
```

**Priority** · P0

---

#### FR-DEC-003 ~ FR-DEC-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-DEC-003** | 系统必须为每次决策留存完整快照 | 快照含：Universe、Score、Return Estimate、Risk Metrics、Correlation、Covariance、Constraint Set、Risk Budget、Optimization Objective、Optimization Run、Target Weight、Human Review 记录、九项版本号 | P0 |
| **FR-DEC-004** | 系统必须支持以相同版本重建任一历史决策，且结果完全一致 | 快照不完整则指令不得下发 | P0 |
| **FR-DEC-005** | 系统必须支持配置 `PROPOSED` 决策的有效期，超期自动转 `EXPIRED` | 有效期可配置 | P1 |

---

### 5.19 决策可解释性 · `FR-EXPL`

---

#### FR-EXPL-001 权重来源解释

**Description**

系统必须能够解释组合中每一个权重的来源。

**Business Rules**

必须回答四个问题：

| # | 问题 | 依据 |
|---|---|---|
| 1 | 为什么进入 Universe | 通过的 Eligibility 条件 + Fund Score |
| 2 | 为什么被选中 | Return Estimate + 风险特征 + 相关性 |
| 3 | 为什么是这个权重 | 目标 / 权重规则 + 哪些约束 binding + 风险预算 |
| 4 | 承担了什么风险 | TRC + 集中度 + 类别暴露 |

**补充规则**

| # | 规则 |
|---|---|
| BR-1 | 每个答案必须可追溯至：Rule → Metric → Factor → Data |
| BR-2 | **禁止**输出无法拆解到指标与规则的结论 |

**Acceptance Criteria**

```
Given  组合中某基金目标权重为 12%
When   请求解释
Then   系统返回上述四个问题的完整答案
And    每个答案可下钻至具体规则、指标、因子与原始数据
```

**Priority** · P0

---

#### FR-EXPL-002 ~ FR-EXPL-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-EXPL-002** | 系统必须能解释基金被排除的原因 | 记录未通过的具体条件 | P0 |
| **FR-EXPL-003** | 系统必须能解释一次调仓建议的成因 | 触发类型、重算范围、成本收益判据计算过程 | P0 |
| **FR-EXPL-004** | 系统输出必须区分五个层级：Analysis / Score / Screening / Candidate / Portfolio，**不得跨级解释** | **严禁**将 `Score = 90` 表述为"应该购买"；禁止出现"AI 认为""模型认为""综合评估为推荐"等表述 | P0 |

---

### 5.20 实盘组合 · `FR-LIVE`

---

#### FR-LIVE-001 实盘持仓状态维护

**Description**

系统必须维护实盘组合状态，其实际持仓来自外部执行系统的回报。

**Input**

`Approved Investment Decision`、外部交易 / 清算系统回报的成交（Fill）或持仓状态。

**Output**

当前持仓、实际权重、目标权重、权重偏离、组合绩效与风险指标。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 实际持仓来自**外部执行 / 清算系统的回报**，非平台自行推算 |
| BR-2 | 平台**不负责**下单、成交与清算，但必须**消费执行结果**以维护正确状态 |
| BR-3 | 实际权重因净值波动持续漂移，与目标权重的偏离是再平衡触发依据 |
| BR-4 | 系统**不得**提供任何自动下单、券商对接或自动交易能力 |

**Acceptance Criteria**

```
Given  外部系统回报了一笔成交
When   系统更新实盘组合
Then   当前持仓与实际权重据此更新
And    系统未发起任何下单动作
```

**Priority** · P0

---

#### FR-LIVE-002 ~ FR-LIVE-004 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-LIVE-002** | 系统必须持续计算并展示权重漂移 | 漂移超阈值触发 Drift 类型再平衡 | P0 |
| **FR-LIVE-003** | 系统必须基于实际权重计算实盘组合风险 | 与目标组合风险分别呈现 | P0 |
| **FR-LIVE-004** | 系统必须支持计算 Backtest-Live Deviation | 存在 Override 时，归因中须单独区分其影响——否则无法区分偏离来自策略失效还是人工干预 | P1 |

---

### 5.21 再平衡 · `FR-REBAL`

---

#### FR-REBAL-001 触发类型与重算范围

**Description**

系统必须按触发类型确定 Strategy Re-evaluation 的重算范围。

**Business Rules**

| 触发类型 | 触发条件 | 重算范围 |
|---|---|---|
| **Periodic** | 调仓周期到期 | 全链路：Factor → Score → Universe → ⑤ → ⑥ → ⑦ |
| **Drift** | 权重偏离超阈值 | ⑤ → ⑥ → ⑦（Universe 与 Score 不重算） |
| **Eligibility Event** | 成分基金失去可投资性 | Universe → ⑤ → ⑥ → ⑦ |
| **Constraint Breach** | 触碰约束上限 | ⑥ → ⑦ |

**补充规则**

| # | 规则 |
|---|---|
| BR-1 | 触发条件与重算范围必须**事先定义、可回测** |
| BR-2 | 重算深度**不得**在运行时动态调整 |
| BR-3 | 再平衡**不是**简单的比例复原——重算范围内的上游结果可能已经变化 |

**Priority** · P0

---

#### FR-REBAL-002 调仓成本收益判据

**Description**

系统必须在生成调仓建议前评估调仓是否值得。

**Business Rules**

| # | 规则 |
|---|---|
| BR-1 | 判据：**预期改善 > 交易成本 + 最小改善阈值** |
| BR-2 | 四个可配置阈值：Weight Drift Threshold、Minimum Trade Threshold、Turnover Threshold、Cost-Benefit Threshold |
| BR-3 | 低于 Minimum Trade Threshold 的单笔调整不执行，并须在报告中说明被过滤的调整及原因 |
| BR-4 | 必须输出判据的**计算过程**，而非仅给结论 |
| BR-5 | 四个阈值构成 `Rebalance Rule Version` |

**Acceptance Criteria**

```
Given  预期改善未超过「交易成本 + 最小改善阈值」
When   评估是否调仓
Then   系统建议不调仓
And    输出判据的完整计算过程

Given  某基金建议调整量低于 Minimum Trade Threshold
When   生成调仓建议
Then   该笔调整被过滤
And    报告中说明被过滤的调整及原因
```

**Priority** · P0

---

#### FR-REBAL-003 ~ FR-REBAL-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-REBAL-003** | 系统必须生成 `Rebalancing Recommendation`，含买卖清单、目标与当前权重、权重偏离、预计换手率、预计交易成本、触发类型与重算范围、风险影响 | 建议须经人工确认后方可交付执行 | P0 |
| **FR-REBAL-004** | 调仓建议必须尊重 `Investment Eligibility` | `HOLD_ONLY` 不出现在买入清单；`NOT_TRADABLE` 持仓冻结并单独标注；无法达成目标权重时显式报告差异 | P0 |
| **FR-REBAL-005** | 系统必须支持调仓阈值的配置与版本化 | 触发策略本身必须可回测 | P1 |

---

### 5.22 数据质量 · `FR-DQ`

---

#### FR-DQ-001 数据质量状态与阻断粒度

**Description**

系统必须对数据质量分级，并按粒度确定影响范围。

**Business Rules**

**状态**：`VALID` / `WARNING` / `INVALID`

**阻断粒度**（独立于状态的第二个维度）：

| 级别 | 影响范围 | 举例 |
|---|---|---|
| **Fund-level** | 仅该基金 | 某基金规模缺失 → 该基金相关条件 `UNAVAILABLE`，其余基金正常计算 |
| **Metric-level** | 仅依赖该指标的结果 | 某基金 Benchmark 缺失 → Alpha/Beta/IR/TE 为 `UNAVAILABLE`，其他指标正常 |
| **Global-level** | **阻断整个决策周期** | 全市场净值未到位、数据日期整体错位、数据源批次缺失 |

**状态与粒度的组合规则**

| # | 规则 |
|---|---|
| BR-1 | `VALID` 正常参与计算 |
| BR-2 | **`WARNING` 可以继续参与计算**，但结果必须携带质量标记并逐级向上传递至最终输出 |
| BR-3 | `INVALID` 不得参与计算，受影响对象按粒度处理 |
| BR-4 | `INVALID` 且属 Global-level 时，阻断整个决策周期，人工确认后方可继续 |
| BR-5 | 任何级别的异常都必须**显式暴露、可告警、可追溯**——禁止的是静默降级，不是局部处理 |

**Acceptance Criteria**

```
Given  1000 只基金中 1 只规模数据为 INVALID
When   执行当期决策流程
Then   仅该基金相关条件标记 UNAVAILABLE
And    其余 999 只正常计算，决策周期不被阻断

Given  全市场净值数据未到位
When   执行当期决策流程
Then   阻断整个决策周期并告警
```

**Priority** · P0

---

#### FR-DQ-002 ~ FR-DQ-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-DQ-002** | 系统必须检测并分级以下问题：缺失数据、异常收益、成立时间不足、清盘、暂停申购、合并、拆分、分红、复权异常、Benchmark 缺失、多源日期不一致 | 异常收益须区分数据错误与真实事件（如大额分红） | P0 |
| **FR-DQ-003** | 系统必须提供计算任务状态视图：成功 / 失败 / 待执行 / 重试中 | 失败任务须可定位、可重试 | P0 |
| **FR-DQ-004** | 系统必须支持数据血缘追溯：任一派生值可回溯至源记录 | 血缘链需覆盖 Factor、Score、Universe、Return Estimate、组合结果 | P1 |
| **FR-DQ-005** | 系统必须提供数据到达时效监控 | 未按约定时点到达须告警 | P0 |

---

### 5.23 策略版本管理 · `FR-STRAT`

---

#### FR-STRAT-001 Strategy Version 组成

**Description**

系统必须以 `Strategy Version` 完整刻画影响策略输出的全部配置。

**Business Rules**

Strategy Version 必须包含**九项**：

```
① Metric Version                        指标计算口径
② Peer Group / Classification Version    分组规则
③ Eligibility / Universe Version         准入规则
④ Scoring Version                        评分方案
⑤ Return Estimate Version                收益估计方法与口径
⑥ Risk Model Version                     风险与协方差估计方法
⑦ Portfolio Rule Version                 目标/权重规则 + 约束集 + 风险预算
⑧ Rebalance Rule Version                 触发条件 + 重算范围 + 调仓阈值
⑨ Benchmark Version                      Fund / Portfolio Benchmark 映射规则
```

| # | 规则 |
|---|---|
| BR-1 | **判定标准**：任何一项变化会导致相同输入产生不同输出的配置，都必须属于 Strategy Version |
| BR-2 | 回测结果必须关联完整的 Strategy Version |
| BR-3 | 相同 Strategy Version + 相同数据版本 → **必然**相同结果 |

**Acceptance Criteria**

```
Given  两次回测使用相同的九项版本号与相同数据版本
When   比较结果
Then   两次结果完全一致
```

**Priority** · P0

---

#### FR-STRAT-002 版本号语义

**Description**

系统必须为 `Strategy Version` 定义具有治理意义的版本号语义。

**Business Rules**

| 级别 | 含义 | 历史结果可比性 | 是否需重新回测与审批 |
|---|---|---|---|
| **Major** | 业务逻辑变化（改评分维度、改优化目标、改准入逻辑） | **不可直接比较** | 必须重新完整回测 + 重走 Approval |
| **Minor** | 新增可选能力，不改变既有行为 | 可比较 | 需回归验证 |
| **Patch** | 文档、配置说明、非业务性修复 | 可比较 | 无需重新回测 |

| # | 规则 |
|---|---|
| BR-1 | Major 变更前后的回测结果**不得**在同一图上直接对比而不加说明 |
| BR-2 | 系统必须在跨 Major 版本对比时显式标注不可比性 |

**Priority** · P0

---

#### FR-STRAT-003 ~ FR-STRAT-005 · 紧凑条目

| ID | 需求 | 关键业务规则 | 优先级 |
|---|---|---|---|
| **FR-STRAT-003** | 系统必须支持 `Strategy Lifecycle` 状态管理：`DRAFT` → `VALIDATING` → `APPROVED` → `ACTIVE` → `SUSPENDED` | 进入 `APPROVED` 前须通过八个维度：数据质量、偏差检查、样本外、稳健性、风险、成本、基线对比、运营就绪；具体阈值由 `13-governance` 定义 | P0 |
| **FR-STRAT-004** | 系统必须支持全部策略配置的版本化管理，且配置不得硬编码 | 涵盖：评分指标与权重、标准化方式、Preference Direction、分层阈值、筛选条件、组合约束、风险预算、告警阈值、调仓阈值、Benchmark 映射 | P0 |
| **FR-STRAT-005** | 系统必须记录每次配置变更的操作人、时刻与变更内容 | 变更历史不可篡改 | P0 |

---

## 6. Acceptance Criteria 总则

| 原则 | 说明 |
|---|---|
| 可验证 | 每条 AC 描述可观测的系统行为；不含"合理""智能""良好"等模糊措辞 |
| 可继承 | AC 可被测试用例直接继承 |
| 无技术实现 | 不出现存储、协议、框架、UI 组件名称 |
| 概念一致 | 全部术语取自上游 §11 术语表 |
| 覆盖负例 | 关键需求同时给出正例与负例（如"缺失理由时拒绝放行"） |

---

## 7. TBD

本文档不引入新的待确认项。相关事项已登记于 `02-business-requirements.md` §35.2：

| 影响的 FR | 待确认项 |
|---|---|
| FR-PEER-003 | P1-1 Peer Group 最小样本量阈值 |
| FR-PEER-004 | P1-2 Peer Group 与 Evaluation Profile 不一致时的处理 |
| FR-BM-003 | P1-3 各策略的 Portfolio Benchmark 构成比例 |
| FR-FUND-003 | P1-4 四象限默认坐标轴与分界方式 |
| FR-FUND-004 | P1-5 Win Rate 默认基准 |
| FR-SCORE-001 | P1-6 Skewness / Kurtosis 是否纳入 SCORING；P1-23 各画像权重 |
| FR-UNIV-004 | P1-7 各策略类型的容量规则 |
| FR-ELIG-002 | P1-8 ETF 流动性各项阈值 |
| FR-DATA-006 | P1-9 Manager Change 后的观察期长度 |
| FR-OPT-004 | P1-10 各组合策略的上线顺序与默认参数 |
| FR-CONS-004 | P1-11 是否需要事前回撤约束及代理方法 |
| FR-CONS-003 | P1-12 各项 Risk Budget 预算值 |
| FR-PRISK-003 | P1-13 风险指标 WARNING / CRITICAL 阈值 |
| FR-BT-002 | P1-14 IS/OOS 划分比例与 Walk-forward 步长 |
| FR-BT-004 | P1-15 销售服务费按份额类别的处理 |
| FR-BT-003 | P1-16 默认回测区间与调仓频率 |
| FR-STRAT-003 | P1-17 各 Approval Gate 的具体阈值 |
| FR-DEC-005 | P1-18 PROPOSED 决策的有效期 |
| FR-REBAL-002 | P1-19 四个调仓阈值取值 |
| FR-BM-001 | P1-20 Fund Classification Default Benchmark 映射表 |
| FR-BTR-004 | P1-21 IR 下限、跑赢概率下限、Bootstrap 参数 |
| FR-SCORE-003 | P1-22 Beta 目标区间 |
| FR-RANK-004 | P1-24 Fund Tier 是否追加绝对门槛 |

---

## 8. Related Documents

| 文档 | 关系 |
|---|---|
| `01-product-overview.md` v2.4 | 上游——概念与 Stage 定义 |
| `02-business-requirements.md` v2.3 | 上游——业务规则与决策登记 |
| `03-user-stories.md` v1.0 | 上游——本文每条 FR 至少支撑一条 US |
| `05-non-functional-requirements.md` | 下游——本文每条 FR 的质量要求 |
| `02-architecture` 及技术域文档 | 下游——实现方式 |

---

## 9. 变更记录

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| v1.0 | 2026-08-25 | 初始版本。定义 23 个功能域共 107 条 Functional Requirement，采用完整模板与紧凑条目两级规范（规范性等同）。核心需求含 Given/When/Then 验收标准 | `01-product-overview.md` v2.4、`02-business-requirements.md` v2.3、`03-user-stories.md` v1.0 |