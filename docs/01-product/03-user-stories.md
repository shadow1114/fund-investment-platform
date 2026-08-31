# 用户故事 · User Stories

> **上游文档**：docs/01-product/01-product-overview.md（v2.5）｜docs/01-product/02-business-requirements.md（v2.3）
> **本文细化阶段**：全链路（Stage ① – ⑩）
> **文档版本**：v1.0
> **产品阶段**：第一阶段 —— 纯 Quant 基金投资组合决策支持系统（不引入 ML / AI）

---

## 1. Overview

### 1.1 本文档回答什么

> **谁使用系统？他们希望完成什么任务？为什么需要这些能力？**

本文档从**使用者视角**描述需求，是 `04-functional-requirements` 的输入。

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 系统必须提供哪些功能 | `04-functional-requirements` |
| 这些功能要达到什么质量 | `05-non-functional-requirements` |
| 系统如何实现 | `02-architecture` 及技术域文档 |
| 指标如何计算 | `04-factor` |

**本文档不出现任何技术实现描述**——不写数据库、消息队列、接口协议、框架、UI 组件。

### 1.3 与上游的关系

本文档**不重新定义**上游已确定的任何概念。全部术语沿用 `01-product-overview.md` §11 术语表与 `02-business-requirements.md` §0.1 映射表。

---

## 2. 与撰写规范的差异说明

撰写规范（`promots/01-product-03-04-05.md`）中若干表述与上游 v2.2 存在差异。按上游 §1.2 第四条（**冲突以上游为准**）处理，差异记录如下：

| # | 规范中的表述 | 上游 v2.2 的定义 | 本文采用 |
|---|---|---|---|
| 1 | Score Breakdown 含 4 个子分 | **5 个**：Return / Risk / Risk-Adjusted / Stability / **Relative Performance** | 上游 5 个（§4.2 ③-S） |
| 2 | Return Estimate 与 Risk/Correlation 为两个独立链路环节 | 同属 **Stage ⑤**，为两条支路 ⑤-A / ⑤-B | 上游 Stage 结构 |
| 3 | 生命周期状态：Fund / Active / Suspended / Merged / Liquidated | `NORMAL` / `SUSPENDED_SUBSCRIPTION` / `LIQUIDATED` / `MERGED` / **`TRANSFORMED`** | 上游 5 态（含转型） |
| 4 | 未提及 `Peer Group` | v2.2 核心概念——评分标准化与排名的样本集，**必须独立于 Score** | 纳入 Epic 4 |
| 5 | 未提及 `Investment Eligibility` | v2.2 核心概念——与 `Fund Lifecycle Status` 分离 | 纳入 Epic 5、Epic 12 |
| 6 | 未提及 `Evaluation Profile` | v2.2 核心概念——决定适用哪套评价标准 | 纳入 Epic 2、Epic 4 |
| 7 | Portfolio Risk 未区分事前 / 事后 | 事前 = Stage ⑥ Risk Budget；事后 = Stage ⑦-R Risk Contribution | 分别纳入 Epic 6、Epic 8 |
| 8 | Bias Control 含 2 类偏差 | **3 类**：Look-ahead / Survivorship / **Tradability** | 纳入 Epic 9（02 §26.3） |

> 上述差异均为**上游更完整**，不构成业务冲突，无需回改上游。

---

## 3. Scope

### 3.1 In Scope

覆盖上游 10 个 Stage 的完整链路：基金数据查看、因子与评分分析、候选池构建、收益与风险估计、组合构建与优化、回测验证、投资决策复核、实盘监控与再平衡、数据质量与策略管理。

### 3.2 Out of Scope

以下能力**不出现在本文档的任何 User Story 中**（上游 §6.2）：

```
✗  ML 基金收益预测          ✗  AI 基金推荐
✗  LLM 生成投资决策         ✗  AI 自动调整组合
✗  自动交易执行 / 自动下单   ✗  券商交易接口
✗  日内 / 高频交易策略
```

> **系统定位**：Investment Decision Support，**不是** Autonomous Investment Advisor。最终投资决策必须经人工 Review / Approval。

---

## 4. 用户角色

### 4.1 四类角色与上游三类的映射

上游 §3 定义了三类角色。本文档细分为四类，以区分"看基金的人"与"设计策略的人"——两者关注点差异显著。这是**细化**，不是重新定义。

| 本文角色 | 上游角色 | 关注 Stage | 一句话职责 |
|---|---|---|---|
| **Fund Researcher**（基金研究员） | 投研分析师 | ① – ④ | 研究单只/一组基金，判断好坏 |
| **Quant Researcher**（策略研究员） | 投研分析师 | ② – ⑧ | 设计与验证策略规则，跑回测 |
| **Portfolio Manager**（组合经理） | 组合经理 | ④ – ⑩ | 构建组合、复核决策、管理实盘 |
| **Operations User**（平台运维） | 平台运维与治理 | 贯穿全链路 | 保障数据与计算的可用与可追溯 |

### 4.2 角色关注点

| 角色 | 核心关注 |
|---|---|
| Fund Researcher | 基金基础信息、历史表现、风险特征、Factor 值、Fund Score 与其构成、Peer Group 排名、是否进入 Universe |
| Quant Researcher | Factor 有效性、评分方案配置、Eligibility Rules、策略参数、回测执行与结果、策略版本对比 |
| Portfolio Manager | Fund Universe、Return Estimate、Risk / Correlation、组合构建与优化结果、Portfolio Risk、Proposed Decision 复核、实盘偏离与再平衡 |
| Operations User | 数据到达与质量、计算任务状态、失败与重试、策略与配置版本、决策快照完整性 |

---

## 5. 编号与优先级

### 5.1 编号规则

```
US-<域>-<序号>
```

| 域 | 含义 | 对应 Epic |
|---|---|---|
| `FUND` | 基金发现与分析 | 1, 2 |
| `FACTOR` | 因子分析 | 3 |
| `SCORE` | 基金评价 | 4 |
| `UNIV` | 候选池 | 5 |
| `PORT` | 组合构建与优化 | 6, 7 |
| `RISK` | 风险分析 | 8 |
| `BT` | 回测 | 9 |
| `DEC` | 投资决策复核 | 10 |
| `LIVE` | 实盘组合 | 11 |
| `REBAL` | 再平衡 | 12 |
| `DQ` | 数据质量 | 13 |
| `STRAT` | 策略管理 | 14 |

### 5.2 优先级

| 级别 | 定义 |
|---|---|
| **P0** | 第一阶段核心链路。缺失则系统无法完成核心投资分析 |
| **P1** | 重要但不阻塞核心链路 |
| **P2** | 增强能力，后续迭代 |

### 5.3 Acceptance Criteria 格式

关键 User Story 使用 Given / When / Then，可被 `04-functional-requirements` 与测试直接继承。

---

## 6. Epic 总览

| Epic | 名称 | Stage | 主要角色 | US 数 |
|---|---|---|---|---|
| 1 | Fund Discovery | ① | Fund Researcher | 4 |
| 2 | Fund Analysis | ② | Fund Researcher | 6 |
| 3 | Factor Analysis | ② | Quant Researcher | 5 |
| 4 | Fund Evaluation | ③ | Fund Researcher / Quant | 6 |
| 5 | Candidate Universe | ④ | PM / Quant | 5 |
| 6 | Portfolio Construction | ⑥ | Portfolio Manager | 5 |
| 7 | Portfolio Optimization | ⑦ | Portfolio Manager | 5 |
| 8 | Risk Analysis | ⑤ / ⑦-R | PM / Fund Researcher | 6 |
| 9 | Backtesting | ⑧ | Quant Researcher | 7 |
| 10 | Investment Decision Review | ⑦ Output | Portfolio Manager | 5 |
| 11 | Live Portfolio | ⑨ | Portfolio Manager | 4 |
| 12 | Rebalancing | ⑩ | Portfolio Manager | 5 |
| 13 | Data Quality | 支撑 | Operations User | 5 |
| 14 | Strategy Management | 支撑 | Quant Researcher | 5 |
| | | | **合计** | **73** |

---

## 7. Requirements

### Epic 1 · Fund Discovery

> **Stage ①**｜主要角色：Fund Researcher

---

#### US-FUND-001 · 按条件检索基金 · P0

```
As a Fund Researcher,
I want to search funds by classification, size, inception date and manager tenure,
so that I can narrow a large fund population down to a workable set.
```

**Acceptance Criteria**

```
Given  平台已收录基金基础信息
When   研究员按分类 + 规模区间 + 成立年限组合检索
Then   系统返回匹配的基金列表
And    每只基金显示分类、规模、成立日、当前基金经理及任职时长
And    结果标注数据截止时点（decision_at）
```

---

#### US-FUND-002 · 查看基金概览 · P0

```
As a Fund Researcher,
I want to view a fund's profile in one place,
so that I can understand what the fund is before analysing its performance.
```

**Acceptance Criteria**

```
Given  一只已收录的基金
When   研究员打开该基金概览
Then   系统展示：代码、名称、Fund Classification、Evaluation Profile、成立日、规模、
       费率、基金经理及任职时长、Fund Lifecycle Status、Investment Eligibility
And    同时展示该基金当前适用的 Fund Benchmark 及其来源优先级
```

---

#### US-FUND-003 · 查看基金生命周期与可投资状态 · P0

```
As a Fund Researcher,
I want to see whether a fund is currently investable and why,
so that I do not analyse a fund that cannot actually be bought.
```

**Acceptance Criteria**

```
Given  某基金处于暂停申购状态
When   研究员查看该基金
Then   Fund Lifecycle Status 显示 SUSPENDED_SUBSCRIPTION
And    Investment Eligibility 显示 HOLD_ONLY
And    系统明确区分"不可建仓"与"不可持有"——暂停申购不影响持有与减仓
```

---

#### US-FUND-004 · 查看已清盘基金的历史 · P1

```
As a Fund Researcher,
I want to access the full history of liquidated funds,
so that historical analysis is not distorted by survivorship bias.
```

**Acceptance Criteria**

```
Given  某基金已于历史某时点清盘
When   研究员查询该基金
Then   系统保留并展示其完整历史数据
And    标注清盘的 effective_at 与 available_at
And    该基金不因清盘而从历史 Peer Group 或历史 Universe 快照中移除
```

---

### Epic 2 · Fund Analysis

> **Stage ②**｜主要角色：Fund Researcher

---

#### US-FUND-005 · 查看多周期业绩 · P0

```
As a Fund Researcher,
I want to view a fund's return across 1M / 3M / 6M / 1Y / 3Y / 5Y,
so that I can tell whether good performance persists across horizons.
```

**Acceptance Criteria**

```
Given  某基金成立不足 3 年
When   研究员查看该基金各周期收益
Then   1M / 3M / 6M / 1Y 正常显示
And    3Y / 5Y 显示为 UNAVAILABLE
And    系统不进行任何数据填充（均值、零、同类值均不允许）
And    全部周期指标按 Trading-day Period 计算，年化因子 252
```

---

#### US-FUND-006 · 对照官方披露口径核对收益 · P1

```
As a Fund Researcher,
I want to see a calendar-basis return alongside the trading-day figure,
so that I can reconcile our numbers with the fund company's published data.
```

**Acceptance Criteria**

```
Given  平台计算口径为 Trading-day Period（年化 252）
When   研究员查看基金业绩
Then   系统额外提供一份日历口径收益
And    明确标注该口径"仅供核对，不参与评分、筛选、组合构建或回测"
```

---

#### US-FUND-007 · 查看风险特征 · P0

```
As a Fund Researcher,
I want to view volatility, drawdown and tail risk metrics together,
so that I can judge a fund's risk profile rather than only its return.
```

**Acceptance Criteria**

```
Given  某基金具备足够的历史数据
When   研究员查看风险视图
Then   系统展示 Volatility、Downside Volatility、Maximum Drawdown、
       Drawdown Duration、Recovery Duration、VaR 95%、CVaR 95%
And    Maximum Drawdown 必须与 Drawdown Duration、Recovery Duration 联合呈现
And    VaR 与 CVaR 成对呈现
```

---

#### US-FUND-008 · 查看风险调整后表现与四象限定位 · P0

```
As a Fund Researcher,
I want to see where a fund sits on the risk-return quadrant within its peer group,
so that I can distinguish genuinely efficient funds from merely high-return ones.
```

**Acceptance Criteria**

```
Given  某基金及其 Peer Group
When   研究员查看风险调整视图
Then   系统展示 Sharpe、Sortino、Calmar、Alpha、Beta、Information Ratio、Tracking Error
And    展示该基金在四象限中的位置（X 轴风险 / Y 轴收益，Peer Group 内中位数分界）
And    若 Fund Benchmark 为 UNAVAILABLE，则 Alpha、Beta、IR、TE 一并标记 UNAVAILABLE
```

---

#### US-FUND-009 · 查看表现稳定性 · P0

```
As a Fund Researcher,
I want to inspect rolling metric series rather than a single snapshot,
so that I can tell a persistent skill from a one-off lucky period.
```

**Acceptance Criteria**

```
Given  某基金具备至少 12 个月以上历史
When   研究员查看稳定性视图
Then   系统展示 Win Rate、R²、Skewness、Kurtosis
And    展示 12M Rolling Return / Sharpe / Volatility / Maximum Drawdown 的完整序列，
       而非仅最新值
And    R² 标注为描述性指标，不作为基金优劣判断依据
```

---

#### US-FUND-010 · 横向比较多只基金 · P0

```
As a Fund Researcher,
I want to compare several funds side by side on risk-adjusted metrics,
so that I can identify which ones have better risk-return characteristics.
```

**Acceptance Criteria**

```
Given  研究员选定 2 只以上基金
When   发起横向比较
Then   系统以统一口径展示各基金的收益、风险、风险调整、稳定性指标
And    若被比较基金分属不同 Peer Group，系统显式提示跨组比较的可比性限制
And    任一基金的 UNAVAILABLE 指标以明确标记呈现，不留空或补零
```

---

### Epic 3 · Factor Analysis

> **Stage ②**｜主要角色：Quant Researcher

---

#### US-FACTOR-001 · 查看基金的因子值 · P0

```
As a Quant Researcher,
I want to view the raw and standardised factor values for a fund,
so that I can understand what drives its evaluation.
```

**Acceptance Criteria**

```
Given  某基金与某决策时点
When   研究员查询该基金的因子值
Then   系统返回各 Factor 的原始值与在 Peer Group 内标准化后的值
And    每个 Factor 标注其 Preference Direction 与 Factor Usage
```

---

#### US-FACTOR-002 · 查看因子的时间序列 · P1

```
As a Quant Researcher,
I want to see how a factor value evolves over time for a fund,
so that I can judge whether the characteristic is stable.
```

---

#### US-FACTOR-003 · 检验因子有效性 · P0

```
As a Quant Researcher,
I want to test whether a factor has predictive relationship with future returns,
so that I can decide whether to include it in the scoring scheme.
```

**Acceptance Criteria**

```
Given  某 Factor 与指定历史区间
When   研究员发起有效性检验
Then   系统输出 IC、ICIR、分层单调性、因子稳定性、与既有因子的相关性
And    全部计算仅使用 available_at ≤ decision_at 的数据
And    检验结果不构成"该因子应当使用 ML 预测"的依据——第一阶段不引入 ML
```

---

#### US-FACTOR-004 · 检查因子间相关性 · P1

```
As a Quant Researcher,
I want to see how correlated a new factor is with existing ones,
so that I do not add a factor that carries no incremental information.
```

---

#### US-FACTOR-005 · 查看因子版本与变更历史 · P1

```
As a Quant Researcher,
I want to know which Metric Version produced a factor value,
so that historical results remain reproducible after calculation logic changes.
```

---

### Epic 4 · Fund Evaluation

> **Stage ③**｜主要角色：Fund Researcher / Quant Researcher

---

#### US-SCORE-001 · 查看基金综合评分及其构成 · P0

```
As a Fund Researcher,
I want to see not only a fund's score but how that score was composed,
so that I can judge whether I agree with the evaluation.
```

**Acceptance Criteria**

```
Given  某基金已完成评分
When   研究员查看评分
Then   系统展示 Total Score 及五个子分：
       Return / Risk / Risk-Adjusted / Stability / Relative Performance Score
And    每个子分可下钻至参与计算的 Factor、各自权重与标准化后的得分
And    同时展示 Data Completeness 与所属 Peer Group 的规模
```

---

#### US-SCORE-002 · 理解评分为何变化 · P1

```
As a Fund Researcher,
I want to see which factors drove a change in a fund's score between two dates,
so that I can explain the change rather than merely observe it.
```

---

#### US-SCORE-003 · 查看 Peer Group 构成 · P0

```
As a Quant Researcher,
I want to inspect which funds constitute a peer group at a given date,
so that I can verify that ranking and standardisation are done on a sound sample.
```

**Acceptance Criteria**

```
Given  某 Peer Group 与某历史决策时点
When   研究员查询该时点的组构成
Then   系统返回当时属于该组的全部基金
And    组构成基于 available_at ≤ decision_at 的 Fund Classification 版本
And    组构成不依赖 Fund Score 或 Fund Universe——不存在循环依赖
And    包含当时存续但现已清盘的基金
```

---

#### US-SCORE-004 · 查看同类排名与分层 · P0

```
As a Fund Researcher,
I want to see a fund's rank, percentile and tier within its peer group,
so that I can position it relative to comparable funds.
```

**Acceptance Criteria**

```
Given  某基金及其 Peer Group
When   研究员查看排名
Then   系统展示 Peer Group Ranking、Percentile 与 Fund Tier（A+ / A / B / C / D）
And    Tier 按分位划分：A+ 前 5%、A 5–20%、B 20–50%、C 50–80%、D 后 20%
And    Tier 必须与该 Peer Group 的绝对水平同屏展示
       （至少含组内 Sharpe 中位数与 Maximum Drawdown 中位数）
```

---

#### US-SCORE-005 · 查看排名变化趋势 · P1

```
As a Fund Researcher,
I want to track how a fund's rank has moved over time,
so that I can spot deterioration before it shows up in the current score.
```

---

#### US-SCORE-006 · 按评价画像使用不同评价标准 · P0

```
As a Quant Researcher,
I want passive and active funds evaluated under different standards,
so that a tracking-oriented fund is not judged by active-management criteria.
```

**Acceptance Criteria**

```
Given  一只被动指数基金与一只主动股票基金
When   系统对两者评分
Then   被动型按 Passive Equity 画像：Tracking Error 越低越好且为核心项、
       费率为高权重项、Alpha 不进入评分
And    主动型按 Active Equity 画像：Alpha 与 Information Ratio 为核心项、
       Tracking Error 中性并配合 IR 判读
And    两者的标准化分别在各自 Peer Group 内进行
```

---
### Epic 5 · Candidate Universe

> **Stage ④**｜主要角色：Portfolio Manager / Quant Researcher

---

#### US-UNIV-001 · 配置准入规则 · P0

```
As a Quant Researcher,
I want to define versioned eligibility rules for a strategy,
so that universe construction is reproducible and back-testable.
```

**Acceptance Criteria**

```
Given  研究员配置准入规则（规模区间、成立年限、经理任职、流动性、可投资性等）
When   保存该规则集
Then   系统生成一个带版本号的 Eligibility Rules 版本
And    系统区分"探索性筛选"与"正式准入规则"——前者不产生 Fund Universe
```

---

#### US-UNIV-002 · 生成候选基金池 · P0

```
As a Portfolio Manager,
I want the system to produce a candidate universe from eligibility rules,
so that I have a defensible starting set for portfolio construction.
```

**Acceptance Criteria**

```
Given  一个 Eligibility Rules 版本与一个决策时点
When   生成 Fund Universe
Then   系统返回合格基金集合
And    支持三种构成策略：仅准入 / 准入+Score 阈值 / 准入+Score Top-N
And    采用"仅准入"策略时，快照中的评分字段为空属正常，不构成留痕缺失
```

---

#### US-UNIV-003 · 理解入池与出池原因 · P0

```
As a Portfolio Manager,
I want to know why each fund entered or left the universe,
so that I can validate the rules rather than trust the output blindly.
```

**Acceptance Criteria**

```
Given  某次 Universe 生成结果
When   PM 查看某只基金
Then   系统展示该基金通过了哪些条件、未通过哪些条件
And    对上期在池、本期出池的基金，展示出池原因
       （不再满足准入 / 清盘 / 转型 / 评分跌出 Top-N / 失去可投资性）
```

---

#### US-UNIV-004 · 查看历史时点的候选池 · P0

```
As a Quant Researcher,
I want to retrieve the universe snapshot as it was at a historical date,
so that back-tests use the pool that actually existed then.
```

**Acceptance Criteria**

```
Given  某历史决策时点
When   研究员请求当时的 Universe
Then   系统返回当时留存的完整快照，而非用当前数据重新推算
And    快照含成员列表、规则版本、评分版本、入出池原因、Data Completeness、
       Investment Eligibility 状态
And    未留存快照的时点，系统明确拒绝提供推算结果
```

---

#### US-UNIV-005 · 监控候选池规模变化 · P1

```
As an Operations User,
I want to be alerted when the universe size changes abnormally,
so that I can catch rule or data problems early.
```

---

### Epic 6 · Portfolio Construction

> **Stage ⑥**｜主要角色：Portfolio Manager

---

#### US-PORT-001 · 定义组合策略 · P0

```
As a Portfolio Manager,
I want to define a portfolio strategy as a complete, executable specification,
so that the optimiser receives a well-posed problem rather than an intention.
```

**Acceptance Criteria**

```
Given  PM 配置一个组合策略
When   保存该策略
Then   系统要求四要素齐备：Eligibility Rules、Objective / Weighting Rule、
       Constraint Set、Risk Budget
And    仅指定目标函数而缺少约束与风险预算的配置，系统拒绝保存
```

---

#### US-PORT-002 · 配置权重生成方式 · P0

```
As a Portfolio Manager,
I want to choose between deterministic weighting rules and optimisation objectives,
so that I can start from a simple, explainable baseline.
```

**Acceptance Criteria**

```
Given  PM 选择权重生成方式
When   配置策略
Then   系统提供两类路径：
       ① 确定性权重规则：Equal Weight、Score Weight、类别固定配比
       ② 优化目标：Minimum Volatility、Maximum Sharpe
And    选择 Score Weight 时，系统明确提示该规则不意味着 Fund Score 是收益估计
And    Fund Score 在任何情况下都不得作为 μ 输入优化器
```

---

#### US-PORT-003 · 配置约束集 · P0

```
As a Portfolio Manager,
I want to set position, category and concentration limits,
so that the resulting portfolio respects mandate and operational constraints.
```

**Acceptance Criteria**

```
Given  PM 配置约束
When   保存约束集
Then   系统支持单基金权重上限、类别权重上限、集中度上限、换手率上限、
       组合波动率上限、相关性约束
And    最大回撤不作为事前约束提供——若需事前控制，须先配置可计算的代理约束
```

---

#### US-PORT-004 · 配置风险预算 · P0

```
As a Portfolio Manager,
I want each risk budget entry to be fully specified,
so that the optimiser and the post-trade check interpret it identically.
```

**Acceptance Criteria**

```
Given  PM 新增一条 Risk Budget
When   保存该条目
Then   系统要求六要素齐备：风险指标、预算值、适用范围、计算方式、
       超预算处理方式、硬约束或软目标
And    六要素不全的 Risk Budget 不得进入优化问题
```

---

#### US-PORT-005 · 查看资产配置结构 · P1

```
As a Portfolio Manager,
I want to see the intended category allocation before optimisation runs,
so that I can confirm the structure matches the investment thesis.
```

---

### Epic 7 · Portfolio Optimization

> **Stage ⑦**｜主要角色：Portfolio Manager

---

#### US-PORT-006 · 求解目标权重 · P0

```
As a Portfolio Manager,
I want the system to solve for target weights under my objective and constraints,
so that allocation is derived rather than guessed.
```

**Acceptance Criteria**

```
Given  一个完整定义的组合策略与当期的 Return Estimate 与 Covariance Matrix
When   执行优化
Then   系统返回目标权重向量、求解状态与诊断信息
And    相同输入重跑得到完全一致的结果
```

---

#### US-PORT-007 · 理解每一个权重的来源 · P0

```
As a Portfolio Manager,
I want to know why a specific fund received a specific weight,
so that I can defend the allocation to an investment committee.
```

**Acceptance Criteria**

```
Given  组合中某基金的目标权重为 12%
When   PM 查询该权重的解释
Then   系统回答四个问题：
       ① 为什么进入 Universe（通过的准入条件 + Fund Score）
       ② 为什么被选中（Return Estimate + 风险特征 + 相关性）
       ③ 为什么是 12%（目标函数 + 哪些约束 binding + 风险预算）
       ④ 承担了什么风险（TRC + 集中度 + 类别暴露）
```

---

#### US-PORT-008 · 处理优化不可行 · P0

```
As a Portfolio Manager,
I want the system to fail loudly when the problem is infeasible,
so that constraints are never silently relaxed behind my back.
```

**Acceptance Criteria**

```
Given  约束集互相冲突导致无解
When   执行优化
Then   Decision Status = INFEASIBLE
And    系统不产出 Proposed Investment Decision
And    系统不自动放松任何约束、不退化为等权、不沿用上期权重
And    不可行原因被记录并上报，进入人工处理流程
```

---

#### US-PORT-009 · 调整约束后重新求解 · P0

```
As a Portfolio Manager,
I want to adjust constraints and re-run after an infeasible result,
so that the loop closes instead of ending at an error.
```

**Acceptance Criteria**

```
Given  上一次优化返回 INFEASIBLE
When   PM 选择调整约束、调整 Universe、沿用上期或中止本期
Then   调整约束或 Universe 时，系统要求升级对应的规则版本并留痕
And    选择"沿用上期权重"时，系统要求显式声明并记录，不得作为静默降级
```

---

#### US-PORT-010 · 比较多个优化目标的结果 · P1

```
As a Portfolio Manager,
I want to compare portfolios produced by different objectives on the same universe,
so that I can see what the added complexity actually buys.
```

---

### Epic 8 · Risk Analysis

> **Stage ⑤ / ⑦-R**｜主要角色：Portfolio Manager / Fund Researcher

---

#### US-RISK-001 · 查看收益估计 · P0

```
As a Portfolio Manager,
I want to see the return estimate for each candidate fund and how it was derived,
so that I know what the optimiser is being fed.
```

**Acceptance Criteria**

```
Given  某 Fund Universe 与决策时点
When   PM 查看 Return Estimate
Then   系统展示每只基金的估计值及所用的量化估计方法
And    明确标注三项口径：Estimation Window、Estimation Horizon、Return Basis
And    Return Estimate 由历史收益序列独立计算，与 Fund Score 逻辑独立
And    系统不使用任何 ML / AI 方法产出该估计
```

---

#### US-RISK-002 · 查看事前风险与相关性 · P0

```
As a Portfolio Manager,
I want to inspect volatility, correlation and covariance across the universe,
so that I can anticipate concentration risk before optimisation.
```

**Acceptance Criteria**

```
Given  某 Fund Universe
When   PM 查看风险视图
Then   系统展示 Volatility Vector、Downside Risk、Drawdown Metrics、
       Correlation Matrix、Covariance Matrix
And    以上均为事前风险——不依赖权重，不含 Risk Contribution 与 Concentration
```

---

#### US-RISK-003 · 查看事后组合风险 · P0

```
As a Portfolio Manager,
I want to see where the portfolio's risk actually comes from once weights are set,
so that I can verify the risk budget was met.
```

**Acceptance Criteria**

```
Given  优化已产出目标权重
When   PM 查看组合风险
Then   系统展示 Portfolio Volatility、Marginal Risk Contribution、
       Total Risk Contribution、Concentration（HHI / 前 N 大）、类别暴露
And    以上均依赖权重，属 Stage ⑦-R
And    系统同时展示事前 Risk Budget 与事后实际值的对照，标明是否达成
```

---

#### US-RISK-004 · 识别高相关持仓 · P0

```
As a Portfolio Manager,
I want to be warned when several holdings are highly correlated,
so that I do not hold a portfolio that is diversified in name only.
```

---

#### US-RISK-005 · 监控风险限额 · P0

```
As a Portfolio Manager,
I want risk limit breaches surfaced with severity,
so that I can act on what matters.
```

**Acceptance Criteria**

```
Given  组合各项风险指标已计算
When   与配置的阈值比对
Then   系统输出 Risk Alert Level：NORMAL / WARNING / CRITICAL
And    CRITICAL 级告警阻断调仓流程，需人工确认后方可继续
```

---

#### US-RISK-006 · 查看组合回撤 · P1

```
As a Portfolio Manager,
I want to monitor realised portfolio drawdown over time,
so that I can assess whether the risk profile matches expectations.
```

> **注**：组合最大回撤为**事后监控指标**。若需事前控制，须先定义可计算的代理约束（见 US-PORT-003）。

---
### Epic 9 · Backtesting

> **Stage ⑧**｜主要角色：Quant Researcher

---

#### US-BT-001 · 配置并执行回测 · P0

```
As a Quant Researcher,
I want to run a back-test of a complete strategy over a historical period,
so that I can assess whether the rule set worked in the past.
```

**Acceptance Criteria**

```
Given  一个完整的 Strategy Version 与历史区间
When   执行回测
Then   系统按历史时间轴逐个决策时点重放完整链路
And    回测使用与实盘完全相同的策略领域逻辑，差异仅在数据源与时间轴
And    回测结果记录所使用的全部版本号
```

---

#### US-BT-002 · 保证无前视偏差 · P0

```
As a Quant Researcher,
I want every historical decision to use only data knowable at that time,
so that back-test results are not silently inflated.
```

**Acceptance Criteria**

```
Given  回测在时点 T 执行决策
When   读取任何数据
Then   全部满足 available_at ≤ T——判定依据是可获得时点，不是生效日期
And    同一 effective_at 存在多个 version 时，取 version 序号最大的合格版本
And    该约束适用于 Factor、Peer Group、Score、Universe、Return Estimate、
       Correlation、Covariance、Benchmark Mapping、Investment Eligibility
```

---

#### US-BT-003 · 保证无幸存者偏差 · P0

```
As a Quant Researcher,
I want historical universes to contain funds that existed at the time,
so that the back-test is not implicitly avoiding funds that later failed.
```

**Acceptance Criteria**

```
Given  某基金于 2023 年清盘
When   回测 2022 年的 Peer Group 与 Fund Universe
Then   该基金包含在内
And    使用当时留存的快照，而非用当前数据重新推算
And    组合成分在回测期内清盘时，按事先定义的退出规则处理
```

---

#### US-BT-004 · 保证交易可得性 · P0

```
As a Quant Researcher,
I want the back-test to respect whether a fund could actually be bought,
so that it does not book trades that were impossible in reality.
```

**Acceptance Criteria**

```
Given  某基金在时点 T 为 HOLD_ONLY（暂停申购）
When   回测在 T 生成建仓或加仓指令
Then   该基金不出现在买入清单中
And    已有持仓不被强制清仓
And    因可投资性限制无法达成目标权重时，系统显式报告差异
```

---

#### US-BT-005 · 进行样本外与滚动验证 · P0

```
As a Quant Researcher,
I want to validate a strategy out-of-sample and via walk-forward,
so that I do not mistake curve-fitting for skill.
```

**Acceptance Criteria**

```
Given  策略已在 In-Sample 区间完成参数选择
When   进入验证阶段
Then   系统记录 Parameter Freeze 时点并纳入 Strategy Version
And    Out-of-Sample 结果不得用于反向调参
And    支持 Walk-forward：滚动重复 IS → Freeze → OOS
And    若因 OOS 不通过而修改规则，须升 Strategy Version 并重新划分 IS/OOS
```

---

#### US-BT-006 · 对比策略与基线 · P0

```
As a Quant Researcher,
I want to compare the strategy against both a benchmark and an equal-weight baseline,
so that I can tell whether the added complexity is worth it.
```

**Acceptance Criteria**

```
Given  回测已完成
When   生成对比报告
Then   系统同时呈现三方：Strategy / Portfolio Benchmark / Equal Weight Baseline
And    Equal Weight Baseline 建立在同一 Fund Universe 上
And    在统计判定阈值确定前，报告不使用"显著优于"的表述
```

---

#### US-BT-007 · 分析回测结果的稳健性 · P0

```
As a Quant Researcher,
I want the report to answer whether performance was broad-based and persistent,
so that I do not deploy a strategy that worked only in one regime.
```

**Acceptance Criteria**

```
Given  回测已完成
When   查看策略评价报告
Then   报告回答八个问题：长期有效性、收益稳定性、回撤可接受性、是否存在失效阶段、
       是否过度依赖某些基金、是否过度依赖某些市场环境、换手率、是否优于两类基线
And    报告显式声明三类偏差（前视 / 幸存者 / 交易可得性）的处理方式
And    交易成本按既定组成扣除——申购费、赎回费、买卖价差、冲击成本；
       管理费与托管费不重复扣除（已含于基金净值）
```

---

### Epic 10 · Investment Decision Review

> **Stage ⑦ Output**｜主要角色：Portfolio Manager

---

#### US-DEC-001 · 查看待复核的决策 · P0

```
As a Portfolio Manager,
I want to review the proposed decision with its full supporting evidence,
so that I can approve it on an informed basis.
```

**Acceptance Criteria**

```
Given  优化已产出 Proposed Investment Decision
When   PM 打开复核视图
Then   系统展示目标权重、当前权重、权重偏离、预计换手率、预计交易成本、
       风险归因、约束满足情况
And    Decision Status 显示为 PROPOSED
```

---

#### US-DEC-002 · 批准决策 · P0

```
As a Portfolio Manager,
I want to approve a proposal as-is,
so that it becomes the decision of record.
```

**Acceptance Criteria**

```
Given  一个 PROPOSED 状态的决策
When   PM 选择批准
Then   Decision Status 变为 APPROVED
And    Proposed 的权重原样成为 Approved Investment Decision
And    系统据此生成 Rebalancing Recommendation
```

---

#### US-DEC-003 · 拒绝决策 · P0

```
As a Portfolio Manager,
I want to reject a proposal and record why,
so that the rationale survives for later review.
```

**Acceptance Criteria**

```
Given  一个 PROPOSED 状态的决策
When   PM 选择拒绝
Then   Decision Status 变为 REJECTED
And    本期不调仓，维持现有持仓
And    系统要求记录拒绝理由
```

---

#### US-DEC-004 · 人工调整权重并留痕 · P0

```
As a Portfolio Manager,
I want to override a proposed weight when I disagree,
so that judgement can enter the process without breaking traceability.
```

**Acceptance Criteria**

```
Given  系统提出某基金权重为 12%，PM 认为应为 7%
When   PM 提交修改
Then   Decision Status 变为 OVERRIDDEN
And    系统记录五个字段：original_target_weight、approved_target_weight、
       override_reason、operator、timestamp
And    override_reason 为空或为占位符时，系统拒绝放行
And    修改后的权重成为 Approved Investment Decision
```

---

#### US-DEC-005 · 追溯任一历史决策 · P0

```
As a Portfolio Manager,
I want to reconstruct any past decision completely,
so that I can answer why a holding was taken months later.
```

**Acceptance Criteria**

```
Given  一次已完成的历史决策
When   请求重建
Then   系统返回完整审计链：Approved Decision → Human Review 记录 →
       Proposed Decision → Post-Optimization Risk → Optimization Run →
       Constraint Set + Risk Budget → Return Estimate + Covariance →
       Fund Universe → Fund Score → Peer Group → Factor → Data Snapshot → Raw Data
And    以相同版本重跑得到完全一致的结果
```

---

### Epic 11 · Live Portfolio

> **Stage ⑨**｜主要角色：Portfolio Manager

---

#### US-LIVE-001 · 查看当前持仓 · P0

```
As a Portfolio Manager,
I want to see the portfolio's actual holdings and weights,
so that I know what I am currently exposed to.
```

**Acceptance Criteria**

```
Given  组合已建仓且已收到外部执行系统的成交或持仓回报
When   PM 查看实盘组合
Then   系统展示当前持仓、实际权重、目标权重、权重偏离
And    实际持仓来自外部交易 / 清算系统的回报，非平台自行推算
```

---

#### US-LIVE-002 · 监控权重漂移 · P0

```
As a Portfolio Manager,
I want to track how far actual weights have drifted from target,
so that I know when action is needed.
```

---

#### US-LIVE-003 · 查看实盘组合风险 · P0

```
As a Portfolio Manager,
I want current portfolio risk metrics based on actual weights,
so that I monitor the risk I am actually running.
```

---

#### US-LIVE-004 · 比较实盘与回测预期 · P1

```
As a Quant Researcher,
I want to compare live performance against the back-tested expectation,
so that I can detect implementation drift early.
```

**Acceptance Criteria**

```
Given  策略已实盘运行一段时间
When   对比同期回测预期
Then   系统输出 Backtest-Live Deviation
And    若存在人工 Override，系统在归因中单独区分其影响——
       否则无法判断偏离来自策略失效还是人工干预
```

---

### Epic 12 · Rebalancing

> **Stage ⑩**｜主要角色：Portfolio Manager

---

#### US-REBAL-001 · 按触发类型发起重评估 · P0

```
As a Portfolio Manager,
I want the recalculation scope to match what actually triggered the rebalance,
so that a drift event does not needlessly churn the whole fund pool.
```

**Acceptance Criteria**

```
Given  某个 Rebalance Trigger 被触发
When   发起 Strategy Re-evaluation
Then   重算范围按触发类型确定：
       Periodic          → 全链路（Factor → Score → Universe → ⑤ → ⑥ → ⑦）
       Drift             → ⑤ → ⑥ → ⑦（Universe 与 Score 不重算）
       Eligibility Event → Universe → ⑤ → ⑥ → ⑦
       Constraint Breach → ⑥ → ⑦
And    重算深度不得在运行时动态调整
```

---

#### US-REBAL-002 · 判断调仓是否值得 · P0

```
As a Portfolio Manager,
I want the system to tell me whether rebalancing is worth the cost,
so that the portfolio is not churned for marginal improvements.
```

**Acceptance Criteria**

```
Given  已产出目标权重与当前权重
When   评估是否调仓
Then   系统按判据计算：预期改善 > 交易成本 + 最小改善阈值
And    低于 Minimum Trade Threshold 的单笔调整被过滤，并在报告中说明
And    输出成本收益判据的计算过程，而非仅给结论
```

---

#### US-REBAL-003 · 查看调仓建议 · P0

```
As a Portfolio Manager,
I want a concrete buy/sell list with its cost and risk impact,
so that I can hand it to execution with confidence.
```

**Acceptance Criteria**

```
Given  调仓判据通过
When   生成 Rebalancing Recommendation
Then   系统输出买卖清单、目标权重、当前权重、权重偏离、预计换手率、
       预计交易成本、触发类型与重算范围、风险影响
```

---

#### US-REBAL-004 · 尊重可投资性限制 · P0

```
As a Portfolio Manager,
I want rebalancing to respect what can actually be traded,
so that the recommendation is executable.
```

**Acceptance Criteria**

```
Given  组合中某基金为 HOLD_ONLY，另一只为 NOT_TRADABLE
When   生成调仓建议
Then   HOLD_ONLY 的基金不出现在买入清单，可出现在卖出清单
And    NOT_TRADABLE 的基金既不买也不卖，持仓视为冻结并单独标注
And    因限制无法达成目标权重时，系统显式报告差异，不静默用其他基金补足
```

---

#### US-REBAL-005 · 配置调仓阈值 · P1

```
As a Portfolio Manager,
I want rebalance thresholds to be configurable and versioned,
so that the triggering policy itself can be back-tested.
```

---

### Epic 13 · Data Quality

> **支撑层**｜主要角色：Operations User

---

#### US-DQ-001 · 查看数据到达与质量状态 · P0

```
As an Operations User,
I want to see whether today's data arrived complete and on time,
so that I can decide if downstream calculation should proceed.
```

**Acceptance Criteria**

```
Given  当日数据批次
When   运维查看数据状态
Then   系统展示各数据类型的到达时间、完整性、Data Quality Status
And    状态取值为 VALID / WARNING / INVALID
```

---

#### US-DQ-002 · 按粒度处理数据异常 · P0

```
As an Operations User,
I want a single bad fund not to halt the entire cycle,
so that data issues are contained rather than amplified.
```

**Acceptance Criteria**

```
Given  1000 只基金中 1 只的规模数据为 INVALID
When   执行当期决策流程
Then   仅该基金相关条件标记 UNAVAILABLE（Fund-level）
And    其余基金正常计算，整个决策周期不被阻断

Given  全市场净值数据未到位（Global-level INVALID）
When   执行当期决策流程
Then   阻断整个决策周期，告警并要求人工确认
```

---

#### US-DQ-003 · WARNING 数据继续参与但携带标记 · P0

```
As an Operations User,
I want warning-level data to flow through with its flag intact,
so that consumers can judge the reliability of the result.
```

**Acceptance Criteria**

```
Given  某数据项状态为 WARNING
When   参与计算
Then   允许继续计算
And    结果携带质量标记，并逐级向上传递至最终输出
```

---

#### US-DQ-004 · 查看计算任务状态 · P0

```
As an Operations User,
I want to see which calculation jobs succeeded, failed or are pending,
so that I can act on failures before they block the decision cycle.
```

---

#### US-DQ-005 · 追溯数据血缘 · P1

```
As an Operations User,
I want to trace any derived value back to its source records,
so that I can investigate anomalies to their origin.
```

---

### Epic 14 · Strategy Management

> **支撑层**｜主要角色：Quant Researcher

---

#### US-STRAT-001 · 管理策略版本 · P0

```
As a Quant Researcher,
I want a strategy version to capture everything that affects its output,
so that the same version always reproduces the same result.
```

**Acceptance Criteria**

```
Given  一个 Strategy Version
When   查看其构成
Then   包含九项：Metric、Peer Group / Classification、Eligibility / Universe、
       Scoring、Return Estimate、Risk Model、Portfolio Rule、Rebalance Rule、Benchmark
And    任何影响输出的配置变化都必须体现为版本变化
```

---

#### US-STRAT-002 · 理解版本号的含义 · P0

```
As a Quant Researcher,
I want version numbering to carry governance meaning,
so that I know when results are comparable and when they are not.
```

**Acceptance Criteria**

```
Given  策略版本号采用 Major.Minor.Patch
When   发生变更
Then   Major = 业务逻辑变化，历史结果不可直接比较，须重新完整回测并重走审批
And    Minor = 新增可选能力，不改变既有行为，需回归验证
And    Patch = 文档 / 说明 / 非业务性修复，无需重新回测
And    Major 变更前后的回测结果不得在同一图上直接对比而不加说明
```

---

#### US-STRAT-003 · 比较策略版本 · P1

```
As a Quant Researcher,
I want to compare two strategy versions on the same period,
so that I can quantify what a rule change actually did.
```

---

#### US-STRAT-004 · 跟踪策略生命周期 · P0

```
As a Quant Researcher,
I want a strategy to move through explicit lifecycle states,
so that nothing reaches live use without passing validation.
```

**Acceptance Criteria**

```
Given  一个策略
When   查看其状态
Then   状态取值为 DRAFT / VALIDATING / APPROVED / ACTIVE / SUSPENDED
And    进入 APPROVED 前须通过八个维度：数据质量、偏差检查、样本外、稳健性、
       风险、成本、基线对比、运营就绪
```

---

#### US-STRAT-005 · 配置评分方案 · P0

```
As a Quant Researcher,
I want scoring schemes to be configuration rather than code,
so that investment views can change without a release.
```

**Acceptance Criteria**

```
Given  研究员调整评分方案
When   保存
Then   系统支持配置指标集合、权重、标准化方式、Preference Direction、缺失处理规则
And    生成新的 Scoring Version 并记录变更
And    权重配置不得硬编码
```

---

## 8. Acceptance Criteria 汇总原则

| 原则 | 说明 |
|---|---|
| 可继承 | 全部 GWT 条目可被 `04-functional-requirements` 与测试用例直接继承 |
| 可验证 | 每条 Then 描述可观测的系统行为，不含"应该合理""智能地"等模糊表述 |
| 无技术实现 | 不出现任何存储、协议、框架、UI 组件名称 |
| 概念一致 | 全部术语取自上游 §11 术语表 |

---

## 9. TBD

本文档不引入新的待确认项。相关待确认事项已登记于 `02-business-requirements.md` §35：

| 影响的 User Story | 待确认项 |
|---|---|
| US-SCORE-004 | P1-24 Fund Tier 是否追加绝对门槛 |
| US-SCORE-006 | P1-22 Beta 目标区间；P1-23 各画像权重 |
| US-UNIV-001 | P1-7 各策略类型的容量规则；P1-8 ETF 流动性阈值 |
| US-PORT-003 | P1-11 是否需要事前回撤约束及代理方法 |
| US-PORT-004 | P1-12 各项 Risk Budget 预算值 |
| US-RISK-005 | P1-13 风险指标 WARNING / CRITICAL 阈值 |
| US-BT-005 | P1-14 IS/OOS 划分比例与 Walk-forward 步长 |
| US-BT-006 | P1-21 IR 下限、跑赢概率下限、Bootstrap 参数 |
| US-DEC-001 | P1-18 PROPOSED 决策的有效期 |
| US-REBAL-002 | P1-19 四个调仓阈值取值 |
| US-STRAT-004 | P1-17 各 Approval Gate 的具体阈值 |

---

## 10. Related Documents

| 文档 | 关系 |
|---|---|
| `01-product-overview.md` v2.4 | 上游——概念与 Stage 定义 |
| `02-business-requirements.md` v2.3 | 上游——业务规则与决策登记 |
| `04-functional-requirements.md` | 下游——本文每条 US 至少对应一条 FR |
| `05-non-functional-requirements.md` | 下游——质量要求 |
| `02-architecture` 及技术域文档 | 下游——实现方式 |

---

## 11. 变更记录

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| v1.0 | 2026-08-25 | 初始版本。定义 4 类用户角色、14 个 Epic、73 条 User Story，其中 P0 条目均含 Given/When/Then 验收标准。记录与撰写规范的 8 处术语差异（均按上游 v2.2 处理） | `01-product-overview.md` v2.4、`02-business-requirements.md` v2.3 |