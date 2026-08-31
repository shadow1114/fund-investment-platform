# 业务需求 · Business Requirements

> **上游文档**：docs/01-product/01-product-overview.md（v2.5）｜**本文细化阶段**：全链路（Stage ① – ⑩）
> **文档版本**：v2.8
> **产品阶段**：第一阶段 —— 纯 Quant 基金投资组合决策系统（不引入 ML / AI）

---

## 0. 上游对齐说明

本章不是业务需求，而是**本文档与上游文档的概念对照**。先读本章再读后续内容。

### 0.1 术语映射：业务语言 → 上游正式术语

**本文档统一使用上游正式术语**，业务说法仅作括注保留。

| 业务常用说法 | 上游正式术语 | 说明 |
|---|---|---|
| 候选基金池 / Candidate Pool | **`Fund Universe`**（Stage ④） | **同一概念**，不是两个阶段 |
| Universe（指全市场基金） | **`Fund Coverage`** | 数据覆盖范围，属 Stage ①，**不是** Fund Universe |
| 同类基金 | **`Peer Group`** | 评分标准化与排名的样本集，见 §7 |
| 收益/风险/风险收益/稳定性指标 | **`Factor`**（Stage ②） | Sharpe、Max Drawdown、Rolling Sharpe 全都是 Factor |
| 基金综合评分 | **`Fund Score`**（Stage ③） | 含五个固定子分 |
| 基金筛选 / Screening | **`Eligibility Rules`**（正式）/ 探索性筛选（非正式） | 两者不同，见 §17.1 |
| 收益预期 / 预期收益 | **`Return Estimate`**（Stage ⑤-A） | 量化历史估计，**不含 ML** |
| 组合风险约束 | **`Constraint Set` + `Risk Budget`**（Stage ⑥） | Risk Budget 须含六要素 |
| 目标组合 / 投资建议 | **`Proposed Investment Decision`**（Stage ⑦ Output） | 经复核成为 `Approved` |
| 基金能不能买 | **`Investment Eligibility`** | 与 `Fund Lifecycle Status` 分离，见 §18 |
| 数据截止日期 | **`available_at` / `decision_at`** | 两者语义不同，见 §24.2 |

> **强制要求**：`01-product/04-functional-requirements` 及之后的所有下游文档必须使用右列正式术语。

### 0.2 Stage 定义表（正式）

上游 §4.0 定义了三个层级，**必须严格区分**——混用会导致下游对"到底有几个阶段"产生分歧：

| 层级 | 含义 | 数量 | 是否占 Stage 编号 |
|---|---|---|---|
| **Stage** | 主干链路阶段，顺序固定 | **恰好 10 个** | 是 |
| **Concept** | Stage 内部的组成部分 | 不固定 | **否** |
| **Output** | Stage 产出的业务对象 | 不固定 | **否** |

**10 个 Stage 的正式定义**：

| Stage | 正式名称 | 输入 | 输出 | 归属 Service |
|---|---|---|---|---|
| ① | Fund Data | 外部数据源 | 标准化基金数据（含 PIT 三元时点） | `data-service` |
| ② | Factor | Fund Data | 因子值矩阵 + 标准化暴露 | `factor-service` |
| ③ | Fund Score | Factor + 评分方案 + Peer Group | 综合得分 + 五个子分 + 归因 | `fund-service` |
| ④ | Fund Universe | Eligibility Rules（+ Score 可选） | 候选基金集合 + 快照 | `fund-service` |
| ⑤ | Risk / Correlation Analysis | Universe + PIT Data | Return Estimate（⑤-A）、σ/ρ/Σ/回撤（⑤-B） | `portfolio-service` |
| ⑥ | Portfolio Construction | ⑤ + 投资目标 + 风险偏好 | Objective + Constraint Set + Risk Budget | `portfolio-service` |
| ⑦ | Portfolio Optimization | ⑤ + ⑥ | Target Weights + 求解诊断 | `portfolio-service` |
| ⑧ | Backtest | Strategy + 历史数据 | 回测结果与归因 | `backtest-service` |
| ⑨ | Live Portfolio | Approved Decision + 外部成交回报 | 实际持仓状态 | `portfolio-service` |
| ⑩ | Rebalancing | 当前权重 + Rebalance Trigger | Rebalancing Recommendation | `portfolio-service` |

**Stage ⑦ 内部的 Concept 与 Output**（这是最容易被误读的一处）：

```
Stage ⑦  Portfolio Optimization
   ├── 主体计算            求解 Target Weights
   ├── Concept ⑦-R        Post-Optimization Risk（σ_p · MRC · TRC · HHI · 因子暴露）
   └── Output             Proposed Investment Decision
```

> **⑦-R 是 Concept，不是 Stage**；`Proposed Investment Decision` 是 Output，同样不占 Stage 编号。**不存在 "⑦-O"**。文中出现 `Stage ⑦-R` 的标注一律指 Concept 层。

同理，Stage ⑤ 含 Concept ⑤-A（Return Estimate）与 ⑤-B（Risk / Correlation）；Stage ① 含 Concept ①-PIT（时点判定）与 ①-B（Benchmark Selection）。

### 0.3 业务流程 → Stage 映射

| 业务视角的步骤 | Stage |
|---|---|
| 基金数据 → 清洗标准化 → 基础分类 | ① |
| 收益/风险/风险收益/稳定性分析 | ② |
| 基金综合评分 | ③ |
| 基金筛选 → 候选基金池 | ④ |
| 收益与风险估计 | ⑤ |
| 组合构建 + 风险约束 | ⑥ |
| 权重求解 + 事后风险分析 | ⑦（含 ⑦-R） |
| 历史回测 → 策略评价 | ⑧ |
| 输出决策参考 → 人工复核 → 实盘 | ⑦ Output → ⑨ |
| 再平衡 | ⑩ |

### 0.4 与业务侧初始设想的三处差异

按上游 §1.2 第四条（冲突以上游为准）处理：

| # | 业务侧初始表述 | 上游规定 | 处理 |
|---|---|---|---|
| 1 | Portfolio Optimization 属 Phase 2 | Stage ⑦ 是第一阶段核心 | **按上游**。见 §19.1——"规则化"与"优化求解"不在同一维度 |
| 2 | 面向个人投资者 | 上游 §2.3 不做 C 端投顾 | **按上游**。目标用户是**使用工具做研究的人**，不是接受推荐的人。见 §4.1 |
| 3 | Data Date / Calculation Date / Analysis Date | 上游 `effective_at` / `available_at` / `version` + `decision_at` | **按上游**，业务三日期已废弃。见 §24.2 |

> 若业务侧认为应以业务表述为准，须**先修改上游并升版本**，不得在本文档就地推翻。

---

## 1. Overview

### 1.1 本文档定义什么

定义第一阶段的**业务需求**：解决什么业务问题、为谁解决、按什么业务规则解决、交付什么结果、以什么标准验收。

### 1.2 本文档不定义什么

| 不定义 | 归属 |
|---|---|
| 技术架构、服务划分、部署 | `02-architecture` |
| 表结构、字段、ERD | `11-database` |
| API 契约 | `10-api` |
| 因子计算公式 | `04-factor` |
| 收益/风险估计算法 | `07-return-risk` |
| 优化算法、约束求解 | `06-portfolio` |
| 回测引擎实现、统计检验方法 | `08-backtest` |

本文档只回答**业务上要什么**，不回答**技术上怎么做**。

### 1.3 第一阶段的技术立场

沿用上游 §2.1.1 与 §9 原则九至十四：不引入 ML / AI / LLM / RAG，不依赖黑盒模型，全部采用确定性指标、规则、评分与组合约束，所有结论可追溯到具体指标与规则。

---

## 2. Business Background

### 2.1 业务问题

| # | 问题 | 后果 |
|---|---|---|
| 1 | 基金数量巨大，人工筛选成本高 | 覆盖不全 |
| 2 | 单纯依赖历史收益率 | 忽略风险 |
| 3 | 投资风格与风险水平不同 | 直接比较绝对收益无意义 |
| 4 | 经理更换、规模变化、回撤影响质量 | 只看净值曲线无法识别 |
| 5 | 不同周期表现可能相反 | 单周期结论不稳健 |
| 6 | 单一指标无法全面评价 | 评价片面 |
| 7 | 缺少统一、可解释、可回测的评分体系 | 结论无法复现 |
| 8 | 筛选与组合构建缺乏规则衔接 | 选出好基金后不知如何配权重 |

### 2.2 系统要回答的问题

目标**不是**"哪个基金收益最高"，而是：

> "在给定投资目标、风险偏好和投资期限下，哪些基金更值得关注？为什么？历史上这种筛选方法是否有效？"

这决定了三件事：评价必须是**风险调整后**的；结论必须**可解释**；规则必须**可回测**。

---

## 3. Product Goals

### 3.1 第一阶段目标

建成**完整、可解释、可复现、可回测的纯量化基金投资组合决策支持系统**。

### 3.2 可判定标准

| 目标 | 判定标准 | 上游原则 |
|---|---|---|
| 完整 | 10 个 Stage 全部有业务规则支撑，无断点 | — |
| 可解释 | 任一权重可回答 §27.5 的四个问题 | 原则十二 |
| 可复现 | 相同数据版本 + 相同策略版本 → 相同结果 | 原则六 |
| 可回测 | 无前视偏差、无幸存者偏差 | 原则二、十三 |
| 可追溯 | 可沿 §27.3 的审计链回溯至原始数据 | 原则七 |

### 3.3 非目标

- 不追求预测精度最大化——第一阶段不做预测
- 不追求回测收益最大化——反复调参属过拟合
- 不追求全自动决策——最终放行由人完成

---

## 4. Target Users

### 4.1 用户定位

> **目标用户是"使用工具做基金研究的人"，不是"接受投资推荐的人"。**

系统交付**分析能力与决策依据**，不交付**投资建议**。

### 4.2 三类角色

| 角色 | 关注 Stage | 核心诉求 | 典型问题 |
|---|---|---|---|
| **基金研究人员**（上游"投研分析师"） | ① → ④ | 指标计算、评分构成、同类比较、多周期表现 | 这只基金 86 分是怎么来的？哪些指标拉高、哪些拉低？ |
| **组合构建者**（上游"组合经理"） | ④ → ⑦、⑩ | 构建满足约束的组合、理解风险来源、判断调仓价值 | 组合风险主要来自哪几只基金？限制单类别 40% 后组合会怎样？ |
| **平台维护者**（上游"运维与治理"） | 贯穿全链路 | 数据质量、策略版本、可追溯 | 昨天的决策能否完整重建？ |

### 4.3 用户可执行的操作

| 类别 | 操作 |
|---|---|
| 查看 | 基本信息、历史表现、风险特征、评分与构成、同类排名与变化、历史回撤 |
| 比较 | 多基金横向、同类分位、与 Benchmark |
| 筛选 | 探索性筛选（见 §17.1）；配置正式 Eligibility Rules |
| 构建 | 构建 Universe、构建组合、配置约束与风险预算 |
| 验证 | 历史回测、样本外验证、查看归因 |
| 追溯 | 查看任一结论的构成、规则版本与数据版本 |

---

## 5. Business Scope

### 5.1 基金覆盖范围（Fund Coverage）

第一阶段支持**中国公募基金**：

| 基金类型 | 第一阶段 | 评价重点 |
|---|---|---|
| 股票型 | 是 | 收益、波动、回撤、风险调整收益 |
| 混合型 | 是 | 同上 + 仓位漂移 |
| 债券型 | 是 | 回撤、波动、收益稳定性、信用风险 |
| 指数型 | 是 | 跟踪误差、超额收益、费用 |
| ETF / ETF 联接 | 是 | 同指数型 + **流动性准入**（见 §18.4） |
| QDII | **后续扩展** | 需处理汇率、时区、交易日历差异 |

### 5.2 Fund Classification 与 Evaluation Profile

两个概念必须区分：

| 概念 | 回答的问题 | 用途 |
|---|---|---|
| **`Fund Classification`** | 这是一只什么类型的基金 | 分组、Peer Group 构成、Benchmark 默认映射 |
| **`Evaluation Profile`** | 这只基金该用哪套评价标准 | 指标集合、权重、Preference Direction |

**为什么不能只用 Fund Classification**：主动股票型与被动指数型都属"股票类"，但 Tracking Error 对前者是中性甚至正面（主动偏离是收益来源），对后者是纯负面（偏离即失职）。用同一套方向定义会得出错误评分。

第一阶段至少区分四个 Evaluation Profile：

```
Active Equity  ·  Passive Equity  ·  Bond  ·  Hybrid
```

#### 5.2.1 四类画像的指标集合与方向（已定案 · 2026-08-25）

**基础指标集**——四类画像**共用**，方向一致：

| 类别 | 指标 | 方向 |
|---|---|---|
| 收益 | 年化收益率、累计收益率、分周期收益率、Rolling Return | `HIGHER_IS_BETTER` |
| 风险 | Volatility、Downside Volatility、VaR 95%、CVaR 95%、Drawdown / Recovery Duration | `LOWER_IS_BETTER` |
| 风险调整 | Sharpe、Sortino、Calmar | `HIGHER_IS_BETTER` |
| 稳定性 | Win Rate、Rolling Sharpe / Volatility / MDD | 见 §13.2 |
| 分布 | Skewness、Kurtosis | 仅 `DISPLAY`，不入评分 |

**差异矩阵**——以下指标在四类画像下的方向或权重**不同**：

| 指标 | Active Equity | Passive Equity | Bond | Hybrid |
|---|---|---|---|---|
| **Tracking Error** | 中性 · 配合 IR 判读 | **`LOWER_IS_BETTER` · 核心** | 不适用 | `STRATEGY_DEPENDENT` |
| **Alpha** | **`HIGHER_IS_BETTER` · 核心** | **不进评分** | `HIGHER_IS_BETTER` | `HIGHER_IS_BETTER` |
| **Information Ratio** | **`HIGHER_IS_BETTER` · 核心** | 不适用 | 中等权重 | 中等权重 |
| **Beta** | `TARGET_RANGE` | `TARGET_RANGE` ≈ 1 | `TARGET_RANGE` | `TARGET_RANGE` |
| **Maximum Drawdown** | 高权重 | 中 · 随指数波动 | **最高权重** | 高权重 |
| **费率** | 中等权重 | **高权重** | 中等权重 | 中等权重 |
| **R²** | 仅 `DISPLAY` | 仅 `DISPLAY` · 高即跟踪良好 | 仅 `DISPLAY` | 仅 `DISPLAY` |

##### 三处反直觉之处（必须理解，否则容易在下游被"修正"回错误做法）

**① 被动型基金的 Alpha 不进入评分。**
指数基金的目标是**复制**指数。出现显著正 Alpha 恰恰说明跟踪偏离——可能来自成分调整时点差异、现金拖累或申赎冲击。把 Alpha 当作正向指标，等于**奖励跟踪不好的指数基金**。被动型的主动管理能力评价应完全由 Tracking Error 承担。

**② 被动型基金的费率是高权重项。**
跟踪同一指数的多只 ETF 高度同质，长期业绩差异主要来自**费率与跟踪误差**，而非选股能力。在被动型评价中，费率不是次要项，而是主要区分度来源。

**③ 债券型基金的 Maximum Drawdown 权重最高。**
债券基金持有人的风险偏好显著更低，一次超预期回撤对持有体验的破坏远大于收益略低。若沿用股票型的收益/风险权重比例，评分会系统性偏好**高信用下沉**的产品——这类产品在平稳期收益领先，尾部风险却集中释放。

##### 待补参数

`<TBD-P1-22: Active Equity / Bond / Hybrid 的 Beta 目标区间取值待投研确认>`
##### 5.2.1.1 权重的产生流程（已定案 · 2026-08-27）

> **`TBD-P1-23` 关闭 —— 定案的是流程，不是取值。** 见 `TBD-resolution.md` Policy ⑥。

**明确禁止**：现在拍一个 25% / 25% / 25% / 25%。

```
❌ 反向流程
Profile → 人工给 25% → 找因子证明合理

✅ 正确流程
Factor → 有效性检验 → 因子筛选 → 剔除冗余 → 权重优化 → 版本化
```

**完整链路**：

```
Factor
   ↓  数据质量与可得性
Factor Quality
   ↓  IC / ICIR / 分层单调性
Factor Effectiveness
   ↓  剔除无效因子
Factor Selection
   ↓  剔除高相关冗余
Factor Redundancy
   ↓  数据驱动
Factor Weight Optimization
   ↓
Profile Weight
   ↓
Fund Score
```

**第一版方案：有效因子内等权**

```
某 Profile 的候选因子经有效性检验后：
    Sharpe        valid
    Sortino       valid
    Max Drawdown  valid
    Calmar        invalid

→ Sharpe 33.33% / Sortino 33.33% / Max Drawdown 33.33% / Calmar 0%
```

> **「有效因子内等权」与「未经检验就等权」数值上可能完全相同，性质却相反** —— 前者是检验之后的结论（这几个因子都有效，无证据表明谁更重要），后者是回避检验。**区分两者的唯一凭据是检验结果是否存在**，因此：

| 情形 | 处置 |
|---|---|
| 有效性检验已产出 | 按有效因子内等权计算 Score |
| **有效性检验尚未产出** | **Score 不可投产** —— 不得用等权临时上线 |

**第二版**（不在第一阶段硬编码）：

```
Factor Effectiveness Score = f(IC, ICIR, Rank IC, t-stat, stability, redundancy)
Weight ∝ effectiveness
```

**检验本身必须满足 PIT**：

```
IC 检验：T 时点的因子值 vs T 之后的收益
    → 因子值必须是 T 时点可得的
    → 否则 IC 被系统性高估
    → 这正是「因子看起来有效但实盘失效」的成因
```

> **检验样本须划分 IS/OOS** —— 在全历史上做一次检验就定权重，等于把权重拟合到了历史上，与直接拍权重的差别只是多了一层数据包装。

> **推荐默认 · 2026-08-27**：因子有效性入选下限 —— **IC 均值 ≥ 0.02** 且 **|ICIR| ≥ 0.3**；检验区间 = **全历史滚动 + 最近 3 年双段均须通过**。业务方可改。
>
> **双段检验的理由**：只看全历史会让早已失效的因子凭历史表现留存；只看最近 3 年则样本量不足且易受单一市场环境影响。
>
> ⚠️ **本项列入首次实证后必须复核的三项之一**：**基金层因子的横截面区分度通常弱于股票层**，0.02 / 0.3 源自股票因子的常用区间，可能偏严。若实证后有效因子数不足以支撑评分，须调整本值而非降低对 Score 的要求。
> **推荐默认 · 2026-08-27**：因子间**相关系数 > 0.8** 视为冗余，保留 **|ICIR| 较高者**。业务方可改。
>
> **保留 ICIR 而非 IC 较高者**：两个高度相关的因子提供近乎相同的信息，此时该保留「更可靠地提供这个信息」的那个。
>
> ⚠️ **同样列入首次实证后必须复核**：**基金因子之间的相关性天然高于股票因子** —— Sharpe 与 Sortino、波动率与最大回撤都源自同一批净值序列。0.8 可能剔除过多。若有效因子数不足，应**先放松本阈值**（冗余因子只是信息重复，不是无效）**再考虑放松 `OPEN-11`**（那会引入真正无效的因子）。
> **已定案 · 2026-08-27**：第一阶段**不实现第二版权重优化**（`Weight ∝ effectiveness`）。
>
> **依据**：①第一版为**有效因子内等权**，其前提（因子有效性检验）本身尚未产出数据；②第二版需要 `Factor Effectiveness Score = f(IC, ICIR, Rank IC, t-stat, stability, redundancy)` 的合成方式，而**六个分量如何加权本身又是一个待定问题** —— 若不加论证地设定，等于把「权重待定」推迟成了「权重的权重待定」。
>
> **推进路径**：先让第一版运行并积累数据，再用实证结果（等权 vs 各种加权方案的 OOS 表现对比）来决定第二版的形式。这是 `OPEN-13` 原文「待第一版运行数据积累后确定」的落实。

> **关于权重**：本节定案的是**指标集合与方向**（结构性、不可逆）。**权重属于 `Scoring Version` 的配置项**（§15.6），应由因子有效性检验结果决定，而非事先拍板。这是正确的定序——先有验证数据，再定权重。

##### 画像划分的覆盖检查

若实际基金池中存在四类画像都套不上的产品（如 FOF、打新策略基金、可转债基金）且占比显著，须回本节追加第五类画像，不得强行归入现有四类。

### 5.3 分类差异化评价原则

> **不同 Evaluation Profile 不得使用同一套评价标准。**

- 指标集合可不同（被动型必须含 Tracking Error，主动型可选）
- 权重按 Profile 分别配置
- 标准化必须在 **`Peer Group`** 内进行（见 §7）
- Benchmark 按 §8 的五级规则分别确定

### 5.4 分类的时点属性

`Fund Classification` 本身带 PIT 属性：

- 分类可能随时间变化（基金转型）
- 变更必须按 `effective_at` / `available_at` 记录
- **回测必须使用当时的分类**，不得用当前分类回溯历史
- 分类变更同时触发 `Peer Group` 与 `Benchmark` 变更（见 §7.4、§8.5）

---

## 6. Core Business Workflow

### 6.1 全链路业务对象关系图

```
                        Fund Coverage
                              │
                              ▼
              Fund Classification / Peer Group
                              │
                              ▼
                           Factors
                              │
                              ▼
                         Fund Score
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
           Ranking / Tier            Eligibility Rules
                                          │
                                          ▼
                                    Fund Universe
                                          │
                            ┌─────────────┴─────────────┐
                            ▼                           ▼
                     Return Estimate            Risk / Correlation
                            │                           │
                            └─────────────┬─────────────┘
                                          ▼
                              Portfolio Construction
                            （Objective + Constraints
                                + Risk Budget）
                                          ▼
                              Portfolio Optimization
                                          ▼
                            Post-Optimization Risk（⑦-R）
                                          ▼
                        Proposed Investment Decision
                                          │
                                   Human Review
                                          │
                      ┌───────────────────┼───────────────────┐
                      ▼                   ▼                   ▼
                  APPROVED           OVERRIDDEN           REJECTED
                      │                   │                   │
                      └─────────┬─────────┘             本期不调仓
                                ▼
                  Approved Investment Decision
                                ▼
                    Rebalancing Recommendation
                                ▼
                     External Execution System
                                │  成交/持仓回报
                                ▼
                          Live Portfolio
                                ▼
                        Rebalance Trigger
                                ▼
                      Strategy Re-evaluation
                    （重算范围由触发类型决定）
```

> `Backtest` 不在这条链上——它与 `Live` 是同一套策略逻辑的**两种运行模式**（见 §21.3）。

### 6.2 五条流程约束

**① 评分不是最终投资决策的唯一依据**
`Fund Score` 决定谁进 `Fund Universe`，最终决策由 Universe、Return Estimate、风险、相关性、约束与风险预算**共同**产生（上游原则十四）。

**② `Fund Score` 不具有收益预测语义**
Score 是无量纲的相对排序量，**不得作为 `Return Estimate` 输入优化器**，也不得换算为收益率（上游 §5.2）。

> **与 Score-based Weighting 的关系见 §19.2**——Score 可以作为**显式的权重映射规则**参与组合构建，这与"Score 不是收益估计"并不冲突，因为前者是确定性权重规则，后者是关于语义的约束。

**③ 筛选、组合构建、风险控制是三个不同阶段**

| 阶段 | 回答的问题 | Stage |
|---|---|---|
| 筛选 | 哪些基金**可以**被选 | ④ |
| 组合构建 | 在什么目标与约束下做选择 | ⑥ |
| 风险控制 | 承担的风险是否可接受 | ⑥ 事前 + ⑦-R 事后 |

混在一起会导致"用筛选条件代替风险控制"——筛掉高波动基金不等于组合波动可控，因为相关性未被考虑。

**④ 回测用于验证规则体系，不用于证明未来收益**

**⑤ 可投资性独立于评价**
一只基金评分很高但当前暂停申购，它**不应进入可建仓集合**。评价与可投资性是两个正交维度（见 §18）。

---
## 7. Peer Group

> 本章是评分体系的地基。全文的标准化、排名、分位、分层都依赖"同类基金"，此前该词从未被定义。

### 7.1 定义

`Peer Group` 是 `Fund Score` 的**标准化、排名、分位与分层的计算样本集**。

```
Peer Group = Fund Classification  +  effective_at  +  参与规则
```

### 7.2 最关键的约束：Peer Group 必须独立于 Fund Score

> **`Peer Group` 的构成不得依赖 `Fund Score` 或 `Fund Universe`。**

**如果违反会发生什么**——形成循环依赖：

```
Fund Score  →  Fund Universe  →  Peer Group  →  Fund Score
     ▲                                              │
     └──────────────────────────────────────────────┘
```

分数依赖样本集，样本集又依赖分数，结果既不唯一也不可复现。这是评分体系最隐蔽的一类设计错误——它不会报错，只会让每次重算得到不同的分数。

**正确的顺序**：

```
Fund Coverage
     ↓  Fund Classification（客观属性，不依赖 Score）
Peer Group
     ↓  Factor 在 Peer Group 内标准化
Fund Score
     ↓  Eligibility Rules（可选叠加 Score 排序）
Fund Universe
```

### 7.3 Peer Group 的参与规则

需要明确"哪些基金参与排名"。第一阶段规则：

| 规则 | 内容 |
|---|---|
| **基础集合** | `Fund Coverage` 中属于该分类的全部基金 |
| **最低数据要求** | 该周期指标可计算（非 `UNAVAILABLE`）的基金才参与该指标的排名 |
| **是否包含已清盘基金** | **历史时点包含**——回测在 `T` 时点的 Peer Group 必须含当时存续的全部基金，包括后来清盘的（见 §26.2） |
| **是否包含不可投资基金** | **包含**——可投资性不影响评价。暂停申购的基金仍应被评分，只是不进入可建仓集合（见 §18） |
| **最小样本量** | **`MIN_PEER_GROUP_SIZE = 30`**（已定案 2026-08-27）。样本数低于该值时**不产出横截面派生量**（标准化值、分位、Tier），标 `INSUFFICIENT_SAMPLE`；原始因子值不受影响。详见 §7.3.1 |


#### 7.3.1 最小样本量定案（2026-08-27）

> 见 `TBD-resolution.md` Policy ⑤。

**定案**：`MIN_PEER_GROUP_SIZE = 30`，**不足时降级而非报错**。

| 条件 | 处理 |
|---|---|
| `n_effective ≥ 30` | 正常标准化 → 排名 → 分层 |
| **`n_effective < 30`** | **不做横截面标准化、不做 Ranking、不做 Percentile Classification**，输出 `INSUFFICIENT_SAMPLE` |
| `n_effective = 1` | `percentile = null` |

**为什么是 30**：10 太小、20 仍易产生极端排名；30 是横截面分析的合理最低规模，也与统计上的小样本/大样本习惯边界一致、便于向业务解释。

> **判定基数是 `n_effective`（该指标的有效参与数）而非 `peer_group_size`**（`05-fund-evaluation/03-fund-ranking` §6.2）—— 一个 50 只基金的组里若某指标只有 25 只可算，该指标仍属小样本。

> **Raw Value 不受影响** —— 样本不足只影响**横截面派生量**（标准化值、分位、Tier），单基金的原始因子值照常产出。这是「降级而非报错」的具体含义：不是整组不可用，而是横截面那一层不可用。

**三处必须使用同一个值**：`04-factor/05-factor-normalization` §5.2、`05-fund-evaluation/03-fund-ranking` §9.3、`05-fund-evaluation/04-fund-classification` §8.5。**配置来源唯一**，不得三处各自定义。

`<OPEN-9: 30 的实证验证 —— 历史上有多少比例的 (Peer Group, 期) 组合会被降级，待数据回溯>`
`<OPEN-10: 长期低于 30 的分类是否应合并或采用更粗粒度的 Peer Group，待投研确认>`

### 7.4 Peer Group 的时点属性

> **`Peer Group` 本身必须满足 PIT。**

- 基金转型会改变其分类，进而改变它所属的 Peer Group
- 回测在 `T` 时点必须使用 `available_at ≤ T` 的分类版本构成 Peer Group
- 每个决策时点的 Peer Group 构成必须可重建

### 7.5 Peer Group 与 Evaluation Profile 的关系

| | Peer Group | Evaluation Profile |
|---|---|---|
| 作用 | 决定**跟谁比** | 决定**用什么标准比** |
| 粒度 | 基金分类 | 主动/被动/资产类别 |
| 典型用途 | 分位排名的样本集 | 指标集合、权重、Preference Direction |

两者通常一致但不必然相同——同一 Peer Group 内可能存在不同 Evaluation Profile 的基金（如某些指数增强型基金）。

##### 两者不一致时的处理（已定案 · 2026-08-27）

> **定案**：同一 Peer Group 内出现多个 Evaluation Profile 时，该组**不产出跨 Profile 的统一排名**，按 Profile 拆分为子排名集。

```
Peer Group「主动股票型」内含：
    Profile = Active Equity   的基金 120 只
    Profile = Passive Equity  的基金  15 只（指数增强型被归入该组）
        ↓
不产出 135 只的统一排名
        ↓
产出两个子排名：Active 120 只、Passive 15 只（后者 n < 30 → INSUFFICIENT_SAMPLE）
```

**依据**：Evaluation Profile 决定**用什么指标、什么权重、什么方向**评价。不同 Profile 的 Score 由不同指标集合加权而成 —— 它们是**不同量纲的两个数**，放进同一分位排名等于比较两个不同的东西。

> **这与 §16.2 的 MAR 一致性约束同源**：那里要求同组同一 MAR，否则 Sortino 不可比；这里要求同组同一 Profile，否则 Score 不可比。**两者是同一原则在不同层次的表现** —— 横截面比较要求被比较的量出自同一口径。

> **子排名的样本量按 §7.3.1 判定** —— 拆分后某个子集不足 30 只时该子集 `INSUFFICIENT_SAMPLE`，这是正确结果而非缺陷：15 只指数增强型基金之间的分位排名本就没有统计意义。

**替代方案为何不可行**：

| 方案 | 问题 |
|---|---|
| 强制同组同一 Profile | Peer Group 由 Fund Classification 构建，Profile 由投资方式决定，两者的划分依据不同，无法强制对齐 |
| 按主导 Profile 统一评价 | 少数派基金会被用不适合它的标准评价（如用主动型标准评价指数增强型，其 Tracking Error 会被误判为缺点） |
| 归一化后合并排名 | 归一化不解决量纲问题 —— 两个 Profile 的 Score 各自在组内归一后，合并排名比较的仍是「A 在 A 类中的位置」与「B 在 B 类中的位置」 |

详见 `TBD-resolution-2.md` §3.1。

---

## 8. Benchmark Rules

### 8.1 Fund Benchmark 与 Portfolio Benchmark

**两个不同概念，不得混用**：

| | Fund Benchmark | Portfolio Benchmark |
|---|---|---|
| 对象 | 单只基金 | 整个组合 |
| 用途 | 计算该基金的 Alpha、Beta、超额收益、IR、TE | 评价组合整体表现 |
| 确定方式 | §8.2 五级优先级 | §8.6 组合基准规则 |

**严禁**直接借用某只成分基金的 Fund Benchmark 作为组合基准。

### 8.2 Benchmark Selection（Fund Benchmark 的确定规则）

> **每只基金必须在指定 `decision_at` 下确定唯一的 Fund Benchmark Definition。**

**按以下优先级执行，命中即止**：

| 优先级 | 来源 | 说明 |
|---|---|---|
| **1** | **基金官方业绩比较基准** | 招募说明书 / 基金合同声明的基准，最权威 |
| **2** | **官方业绩比较基准的组成指数及权重** | 官方基准为复合形式时，取其 Component 及权重 |
| **3** | **Strategy-specific Benchmark** | 策略层为特定用途显式指定的基准 |
| **4** | **Fund Classification Default Benchmark** | 按基金分类的默认映射 |
| **5** | **System Default Benchmark** | 系统兜底基准 |

> **这条规则使 Benchmark 从"待拍板的配置"变成"确定性算法"**：优先级 1–2 从基金官方文件客观可得，无需人工判断。只有优先级 4 的分类默认映射需要配置。因此 Benchmark **不构成** `04-factor` / `05-fund-evaluation` 的启动阻塞项。

### 8.3 Composite Benchmark 不得简化

> **由多个指数构成的业绩比较基准，必须保留各 Component 及其权重，不得简化为单一指数。**

```
官方基准：沪深300指数收益率 × 80%  +  中债综合指数收益率 × 20%

✅ 保留：[{index: 沪深300, weight: 0.8}, {index: 中债综合, weight: 0.2}]
❌ 简化为"沪深300"
```

**为什么**：把上例简化为沪深 300，会使该基金的 Beta 被系统性低估、Alpha 被系统性高估（因为基准少算了 20% 的债券部分）。Alpha、Beta、超额收益、IR、TE **五个指标同时失真**。

### 8.4 Benchmark Mapping 的 PIT 属性

> **Benchmark Mapping 必须具备 PIT 属性。**

每条映射必须记录四个字段：

| 字段 | 含义 |
|---|---|
| `effective_at` | 该基准在业务上生效的日期 |
| `available_at` | 该映射关系首次对平台可见的时刻 |
| `source` | 来源（官方文件 / 策略指定 / 分类默认 / 系统兜底，即优先级 1–5） |
| `mapping_rule_version` | 映射规则的版本 |

回测在 `T` 时点必须使用 `available_at ≤ T` 的映射版本。基金转型导致基准变更时尤其要注意——不得用转型后的基准回算转型前的超额收益。

### 8.5 无法确定 Benchmark 时的处理

> **如果在 `decision_at` 下无法确定有效 Benchmark，则相关依赖 Benchmark 的指标应标记为 `UNAVAILABLE`。**

受影响的指标：

```
Alpha · Beta · Information Ratio · Tracking Error
Benchmark 超额收益 · R² · Relative Performance Score
```

**两条禁令**：

- **严禁**使用未来信息确定 Benchmark（如用今天才知道的基准回算历史）
- **严禁**使用未经声明的替代 Benchmark 填补缺口（如"债券基准缺失就临时用沪深300"）

标记 `UNAVAILABLE` 后，按 §15.5 的缺失数据规则处理，**不得填充**。

### 8.6 Portfolio Benchmark

组合基准通常需要 **Composite Benchmark**：

```
Portfolio Benchmark
  = 60% × Equity Benchmark  +  40% × Bond Benchmark
```

**规则**：

| 规则 | 内容 |
|---|---|
| 构成方式 | 按组合的目标资产配置比例加权组合各类别基准 |
| 权重基准 | 使用**策略目标配置比例**，而非实际持仓比例——否则基准会随组合漂移，失去比较意义 |
| 版本化 | Portfolio Benchmark 属于 Strategy Version 的一部分（见 §23.1） |
| PIT | 同 §8.4 |

`<TBD-P1-3: 各策略的 Portfolio Benchmark 构成比例待组合管理确认>`

---

## 9. Analysis Periods

### 9.1 支持的周期

```
1M · 3M · 6M · 1Y · 3Y · 5Y
```

| 层次 | 周期 | 参考价值 |
|---|---|---|
| 短期 | 1M / 3M | 低——易受单次市场波动影响 |
| 中期 | 6M / 1Y | 中 |
| 长期 | 3Y / 5Y | 高——更能反映持续能力 |

### 9.2 周期语义必须精确定义

> "1M" 是自然月还是约 21 个交易日？这不是细节，两者会给出不同的指标值。

每个 `Analysis Period` 必须显式声明五项语义：

| 语义项 | 需要定义的内容 |
|---|---|
| **周期类型** | Calendar Period（自然日历）还是 Trading-day Period（交易日计数） |
| **起止日包含规则** | 区间是 `[start, end]`、`(start, end]` 还是其他 |
| **年化规则** | 年化因子取值（252 交易日 / 365 自然日 / 12 月），必须全平台统一 |
| **非交易日处理** | 区间端点落在非交易日时，前移还是后移 |
| **基金成立日处理** | 成立日当天是否计入；成立日净值是否作为起点 |

#### 9.2.1 第一阶段口径（已定案 · 2026-08-25）

> **全部指标统一采用 Trading-day Period，年化因子 `252`。**

| 项 | 取值 |
|---|---|
| 周期类型 | **Trading-day Period**（交易日计数） |
| 年化因子 | **252** |
| 起止日包含规则 | `(start, end]`——区间收益不含起始日当日 |
| 非交易日处理 | 区间端点落在非交易日时**向前取最近交易日** |
| 基金成立日 | 成立日净值作为序列起点，成立日当日不计入收益区间 |

**为什么不采用"收益按日历、风险按交易日"的混合口径**：Sharpe 的分子是超额收益、分母是波动率。若收益按 365 年化、波动率按 252 年化，两者年化基准不同，Sharpe 会产生约 `√(365/252) ≈ 1.20` 倍的系统性错配，Sortino、Calmar、Information Ratio 同理。混合口径必须再补一条"风险调整类指标统一到哪个口径"的规则，反而更复杂。

**对外可比性由展示层解决**：系统必须在展示层**额外提供一份日历口径收益**（自然月/自然年），专用于与基金公司公布数据核对。该口径**仅用于展示与核对，不参与任何评分、筛选、组合构建或回测计算**（见 §29.1）。

> **不可逆性提示**：口径变更会使全部历史回测结果与新口径不可比。变更须按 §23.2 的 **Major** 级处理——重新完整回测并重走 Approval。

### 9.3 长期与短期的权重关系

> **默认评分方案应体现长期表现的重要性。**

**但不要求**所有长期指标的权重逐项高于短期指标——不同策略中，短期指标可能承担不同作用（如短期动量因子）。具体权重由 `Strategy Version` 配置，这与 §32 的可配置性要求一致。

### 9.4 成立时间不足的处理

> **绝对禁止补齐数据。**

| 做法 | 是否允许 |
|---|---|
| 标记该周期指标为 `UNAVAILABLE` | ✅ 必须 |
| 该指标不参与依赖它的评分项 | ✅ 必须 |
| 用起始日至今的数据"年化"当作 3Y 指标 | ❌ 严禁 |
| 用同类平均值 / 零 / 行业均值填充 | ❌ 严禁 |

**理由**：人为填充会让新基金在长期指标上获得虚假数值，且这类失真**在回测中完全不可见**——因为填充逻辑在历史和当下是一致的，回测无法暴露它。

---
## 10. Performance Requirements（收益类 Factor）

> §10 – §13 定义的全部指标在上游术语体系中均属 **`Factor`（Stage ②）**。计算公式由 `04-factor` 定义；本章只定义业务需求与 **Preference Direction**。

### 10.1 核心收益指标

| 指标 | 业务含义 | Preference Direction |
|---|---|---|
| 年化收益率 | 按年化口径的收益水平 | `HIGHER_IS_BETTER` |
| 累计收益率 | 区间总收益 | `HIGHER_IS_BETTER` |
| Benchmark 超额收益 | 相对 Fund Benchmark 的超额部分 | `HIGHER_IS_BETTER` |
| 分周期收益率 | 1M / 3M / 6M / 1Y / 3Y / 5Y | `HIGHER_IS_BETTER` |
| Rolling Return | 滚动窗口收益 | `HIGHER_IS_BETTER` |

### 10.2 使用规则

| # | 规则 |
|---|---|
| 1 | **收益不得作为唯一评价标准**——必须与风险指标联合使用 |
| 2 | **同 `Peer Group` 内比较优先于跨组比较** |
| 3 | 收益必须基于**统一口径**（复权方式、费用处理、年化规则全平台一致） |
| 4 | 收益计算基于**复权净值**，复权规则须显式声明 |
| 5 | 基金净值**已扣除管理费与托管费**——回测计算收益时不得重复扣除（见 §21.7） |

---

## 11. Risk Requirements（风险类 Factor）

### 11.1 核心风险指标与方向

| 指标 | 业务含义 | Preference Direction |
|---|---|---|
| **Volatility** | 收益波动程度 | `LOWER_IS_BETTER` |
| **Downside Volatility** | 只衡量负收益方向的波动 | `LOWER_IS_BETTER` |
| **Maximum Drawdown** | 历史最大峰谷亏损，**核心风险指标** | `LOWER_IS_BETTER` |
| **VaR 95%** | 95% 置信下的潜在损失上界 | `LOWER_IS_BETTER` |
| **CVaR 95%** | 超过 VaR 后的尾部平均损失 | `LOWER_IS_BETTER` |
| **Drawdown Duration** | 处于回撤状态的持续时长 | `LOWER_IS_BETTER` |
| **Recovery Duration** | 从谷底恢复至前高所需时长 | `LOWER_IS_BETTER` |

### 11.2 业务重点

- **Maximum Drawdown 是第一阶段的核心风险指标**——它比波动率更贴近实际体验：投资者感受到的是亏了多少，不是波动了多少
- `Drawdown Duration` 与 `Recovery Duration` 必须与 `Maximum Drawdown` **联合呈现**。回撤 20% 但 3 个月恢复，与回撤 20% 但 3 年未恢复，是完全不同的风险
- VaR 与 CVaR 必须**成对使用**——单看 VaR 会低估尾部风险

### 11.3 方向不得一刀切

> **不得默认"所有风险类指标越低越好"。**

上表七项确实都是 `LOWER_IS_BETTER`，但以下指标虽与风险相关，方向**不是**单调的：

| 指标 | Preference Direction | 说明 |
|---|---|---|
| **Beta** | `TARGET_RANGE` / `STRATEGY_DEPENDENT` | Beta = 0.5 不必然优于 1.0。防御型策略希望低 Beta，市场中性策略希望接近 0，进取型策略可能允许高 Beta。必须由 `Evaluation Profile` 与策略目标共同决定目标区间 |
| **Tracking Error** | `STRATEGY_DEPENDENT` | **被动型（Passive Equity）**：`LOWER_IS_BETTER`，偏离即失职。**主动型（Active Equity）**：中性或需配合 IR 判断——TE 是主动收益的来源，TE=0 的主动基金等于收了主动管理费做指数 |

**因此**：每个 `Factor` 必须在 `Evaluation Profile` 下**显式声明** Preference Direction，不得依赖"风险类=越低越好"这类默认推断。

---

## 12. Risk-adjusted Performance（风险收益类 Factor）

### 12.1 核心指标与方向

| 指标 | 业务含义 | Preference Direction |
|---|---|---|
| **Sharpe Ratio** | 单位总风险的超额收益 | `HIGHER_IS_BETTER` |
| **Sortino Ratio** | 单位下行风险的超额收益 | `HIGHER_IS_BETTER` |
| **Calmar Ratio** | 收益与最大回撤之比 | `HIGHER_IS_BETTER` |
| **Alpha** | 无法由 Benchmark 解释的超额收益 | `HIGHER_IS_BETTER` |
| **Beta** | 对 Benchmark 的敏感度 | `TARGET_RANGE`（见 §11.3） |
| **Information Ratio** | 单位跟踪误差的超额收益 | `HIGHER_IS_BETTER` |
| **Tracking Error** | 相对 Benchmark 的偏离程度 | `STRATEGY_DEPENDENT`（见 §11.3） |

### 12.2 核心业务要求

> **不得只按收益排序。** 评价必须同时满足：收益高 + 风险低 + 回撤可控 + 长期稳定。

### 12.3 四象限定位

四象限是可解释性的基本呈现方式，**必须明确定义坐标轴**：

| 轴 | 默认指标 | 分界方式 |
|---|---|---|
| **X 轴（风险）** | Maximum Drawdown | Peer Group 内中位数分界 |
| **Y 轴（收益）** | 年化收益率 | Peer Group 内中位数分界 |

| | 低风险 | 高风险 |
|---|---|---|
| **高收益** | ★ 重点关注 | 需甄别：能力还是运气？看 Rolling 稳定性 |
| **低收益** | 可作为组合稳定器 | ✗ 应排除 |

**可配置项**：X/Y 轴指标、分界方式（中位数 / 指定分位 / 绝对阈值 / 相对 Benchmark）均可配置。> **推荐默认 · 2026-08-27**：默认坐标轴 = **(年化波动率, 年化收益)**；分界 = **Peer Group 中位数**。业务方可改。
>
> **中位数分界的理由**：不依赖绝对阈值，因此**跨期可比** —— 绝对阈值（如「收益 > 8%」）会让同一只基金在牛熊市中落入不同象限，反映的是市场而非基金自身（同 `05-fund-evaluation/04` `FC-1` 拒绝绝对门槛的理由）。
>
> **坐标轴用原始值而非分位**：象限图的价值在于呈现「差距有多大」，而分位会把这个信息压平。

系统必须**明确呈现**每只基金所处象限，而不是只给一个综合分数。

### 12.4 Alpha / Beta 的使用限制

- Alpha 与 Beta 强依赖 Benchmark，Benchmark 不当会使两者失真（§8.3）
- Benchmark 为 `UNAVAILABLE` 时，Alpha、Beta、IR、TE 一律 `UNAVAILABLE`（§8.5）
- Composite Benchmark 被简化会使 Beta 系统性偏低、Alpha 系统性偏高（§8.3）

---

## 13. Stability Analysis（稳定性类 Factor）

### 13.1 业务动机

> **基金优秀的表现是长期持续存在，还是只发生在某一个阶段？**

稳定性分析的目的是把"持续的能力"与"一次的运气"区分开。

### 13.2 核心指标与方向

| 指标 | 业务含义 | Preference Direction |
|---|---|---|
| **Win Rate** | 正收益区间占比 | `HIGHER_IS_BETTER` |
| **R²** | 收益对 Benchmark 的线性解释程度 | `STRATEGY_DEPENDENT`（见 §13.5） |
| **Rolling Return** | 滚动窗口收益 | `HIGHER_IS_BETTER` |
| **Rolling Sharpe** | 滚动窗口风险调整收益 | `HIGHER_IS_BETTER`；其**波动**为 `LOWER_IS_BETTER` |
| **Rolling Volatility** | 滚动窗口波动率 | `LOWER_IS_BETTER` |
| **Rolling Maximum Drawdown** | 滚动窗口最大回撤 | `LOWER_IS_BETTER` |
| **Skewness** | 收益分布偏度 | `HIGHER_IS_BETTER`（正偏优于负偏）|
| **Kurtosis** | 收益分布峰度 | `LOWER_IS_BETTER`（高峰度意味极端事件更频繁）|

### 13.3 Win Rate 的周期必须定义

> "正收益区间占比"中的"区间"必须明确，否则 `04-factor` 会自行解释。

| 项 | 定义 |
|---|---|
| 统计周期 | **可配置**：日 / 周 / 月 / 滚动窗口 / 持有期 |
| 第一阶段默认 | **月度（monthly）** |
| 基准 | 可配置：绝对正收益 或 跑赢 Benchmark |

> **已定案 · 2026-08-27**：Win Rate 默认基准 = **绝对正收益**（基准可配置为跑赢 Benchmark）。
>
> **依据**：①**不依赖 Benchmark 可得性** —— Benchmark 缺失或口径存疑（见 Policy B）时 Win Rate 仍可算，而相对基准版本会随之 `UNAVAILABLE`；②与 Win Rate 的直觉含义一致 —— 「多少期没亏钱」是持有人的第一层关切；③相对 Benchmark 的胜率信息已由 Information Ratio 与跑赢概率承载，不必在此重复。详见 `TBD-resolution-2.md` §3.1。

### 13.4 滚动窗口要求

第一阶段至少支持 **12 个月滚动窗口**。系统必须支持**观察滚动序列本身**，而不只是最新值，用以回答：

- Rolling Sharpe 是长期稳定在高位，还是最近才冲上去？
- 有没有某个阶段表现显著恶化？
- 滚动指标的波动幅度有多大？

### 13.5 R² 的业务用途必须限定

> **R² 高不代表基金"稳定"或"优秀"。**

R² 只说明基金收益与 Benchmark 收益之间**线性关系的解释程度**：

- 指数型基金 R² 应当接近 1——这是跟踪质量的体现
- 主动型基金 R² 低可能意味着独立的选股能力，也可能意味着风格漂移
- **R² 不得直接作为基金优劣的判断指标**，只作为描述性指标与风格分析的辅助

因此 R² 的 `Factor Usage` 第一阶段建议为 `DISPLAY` + `SCREENING`，**不建议**直接进入 `SCORING`（见 §14）。

### 13.6 稳定性指标在评分中的作用

稳定性指标的作用是**惩罚不稳定**，而非奖励高收益。两只基金 3Y Sharpe 相同，但一只 Rolling Sharpe 平稳、另一只剧烈波动，前者应得分更高。

---

## 14. Factor Usage Matrix

> 本章解决一个此前未被定义的问题：**Factor 存在 ≠ Factor 参与评分**。

### 14.1 五种用途

每个 `Factor` 必须声明至少一种用途：

| 用途 | 含义 |
|---|---|
| `DISPLAY` | 仅展示给用户，不参与任何计算决策 |
| `SCORING` | 参与 `Fund Score` 计算 |
| `SCREENING` | 可作为 `Eligibility Rules` 或探索性筛选的条件 |
| `PORTFOLIO` | 作为组合构建/优化的输入（Stage ⑤/⑥/⑦） |
| `BACKTEST` | 参与回测结果评价 |

### 14.2 用途矩阵（第一阶段默认）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST |
|---|:---:|:---:|:---:|:---:|:---:|
| 年化收益率 | ✓ | ✓ | ✓ | — | ✓ |
| 累计收益率 | ✓ | — | ✓ | — | ✓ |
| Benchmark 超额收益 | ✓ | ✓ | ✓ | — | ✓ |
| Rolling Return | ✓ | ✓ | ✓ | — | ✓ |
| Volatility | ✓ | ✓ | ✓ | ✓ | ✓ |
| Downside Volatility | ✓ | ✓ | ✓ | — | ✓ |
| Maximum Drawdown | ✓ | ✓ | ✓ | — | ✓ |
| VaR 95% / CVaR 95% | ✓ | ✓ | ✓ | — | ✓ |
| Drawdown / Recovery Duration | ✓ | — | ✓ | — | ✓ |
| Sharpe / Sortino / Calmar | ✓ | ✓ | ✓ | — | ✓ |
| Alpha | ✓ | ✓ | ✓ | — | ✓ |
| Beta | ✓ | ✓ | ✓ | ✓ | ✓ |
| Information Ratio | ✓ | ✓ | ✓ | — | ✓ |
| Tracking Error | ✓ | ✓ | ✓ | — | ✓ |
| Win Rate | ✓ | ✓ | ✓ | — | ✓ |
| **R²** | ✓ | **—** | ✓ | — | ✓ |
| Rolling Sharpe / Volatility / MDD | ✓ | ✓ | ✓ | — | ✓ |
| **Skewness / Kurtosis** | ✓ | **—** | ✓ | — | ✓ |
| **Correlation / Covariance** | ✓ | **—** | — | **✓** | ✓ |
| **费率**（管理费 + 托管费 + 销售服务费） | ✓ | ✓ | ✓ | — | ✓ |
| **Fund Score** | ✓ | — | ✓ | **权重映射规则**（§19.2） | ✓ |

> **已定案 · 2026-08-27**：Skewness / Kurtosis **第一阶段不纳入 SCORING**，仅 `DISPLAY`。
>
> **依据**：上表两者的 SCORING 列已标「—」，本条与表格是同一结论的两次表述。**分布类指标进入评分的前提是先确定其 Preference Direction**，而偏度的方向依策略而异（正偏对进取型是优点、对稳健型未必），峰度则几乎总是「越低越好」但其区分度在基金层面很弱。在方向未定之前纳入评分，等于给一个方向不明的量赋权重。详见 `TBD-resolution-2.md` §3.1。

### 14.3 三条读表规则

1. **`Correlation` / `Covariance` 不参与 SCORING**——它们是基金**之间**的关系，不是单只基金的属性，无法进入单基金评分。它们的用途在 `PORTFOLIO`。
2. **`Fund Score` 自身不是 Factor**，但可作为 SCREENING 条件与组合层的权重映射规则输入。它在 SCORING 列为空——Score 不能参与计算自己。
3. **`PORTFOLIO` 列极少打勾是正常的**——组合构建消费的主要是 `Return Estimate` 与 `Σ`，而非单基金评分类指标。
4. **费率不是计算得出的 Factor**，而是 `Fund Data`（Stage ①）的基金属性，但它参与评分与筛选，因此纳入本矩阵管理。其 Preference Direction 为 `LOWER_IS_BETTER`，在 Passive Equity 画像下为高权重项（§5.2.1）。

---
## 15. Fund Scoring

### 15.1 六项要求

`Fund Score`（Stage ③）必须同时满足：可解释、可重复、可配置、可回测、可比较、可追溯。

### 15.2 评分不能是什么

> **严禁：`收益率排名 = 基金评分`**

### 15.3 评分结构

按上游 §4.2 ③-S，五个子分命名固定：

```
Total Score
 ├── Return Score                 收益表现
 ├── Risk Score                   风险水平
 ├── Risk-Adjusted Score          风险调整后收益
 ├── Stability Score              表现稳定性
 └── Relative Performance Score   相对 Benchmark 表现
```

每个子分必须能回答六个问题：使用了哪些指标、各自权重、如何标准化、Preference Direction 是什么、缺失数据如何处理、如何汇总。**无法回答任一问题的评分方案不得上线。**

### 15.4 标准化

**方式**：第一阶段优先使用 **Percentile Rank / Peer Group 内排名**——理由是可解释性，分位排名可直接用自然语言表述，Z-Score 不能。

```
某基金 3Y Sharpe 在 Peer Group 内位于前 10%  →  Sharpe Score = 90 / 100
```

**三条强制规则**：

| # | 规则 |
|---|---|
| 1 | **标准化必须在 `Peer Group` 内进行**（§7），且 Peer Group 独立于 Score 产生 |
| 2 | 标准化必须按各 Factor 声明的 **`Preference Direction`** 转换，使**分数越高一律代表越优秀**（§11.3、§12.1、§13.2） |
| 3 | `TARGET_RANGE` 与 `STRATEGY_DEPENDENT` 方向的 Factor（Beta、Tracking Error），其转换规则必须由 `Evaluation Profile` 显式定义，不得套用单调方向 |

### 15.5 缺失数据处理

| 处理方式 | 是否允许 |
|---|---|
| 该指标不参与评分，权重按比例重分配给同组其他可用指标 | ✅ 推荐 |
| 该子分标记 `UNAVAILABLE`，总分标注 `Data Completeness` | ✅ 允许 |
| 用同类均值/中位数填充 | ❌ 严禁 |
| 按 0 分参与评分 | ❌ 严禁——这把"数据不足"错误地等同于"表现最差" |

> **`Data Completeness` 必须随评分一同呈现**：基于 3 个指标的 85 分与基于 12 个指标的 85 分，可信度完全不同。

### 15.6 评分方案的版本化

评分方案（指标集合 + 权重 + 标准化方式 + Preference Direction + 缺失处理规则）构成 **Scoring Version**，是 `Strategy Version` 的组成部分（§23.1）。

---

## 16. Fund Ranking & Tiering

### 16.1 派生链

```
Fund Score
    ↓  在 Peer Group 内排序
Peer Group Ranking
    ↓  转换为分位
Percentile
    ↓  按阈值分层
Fund Tier
```

四者是**同一条派生链上的不同表示**，不是四个独立概念。任一环节的输入变化会沿链传导。

### 16.2 同类排名

必须提供 `Peer Group` 内的排名与分位，并支持查看**排名随时间的变化**——排名持续下滑的基金即使当前分数仍高，也值得警惕。

### 16.3 基金分层

```
A+  Excellent  ·  A  Very Good  ·  B  Good  ·  C  Neutral  ·  D  Weak
```

| 要求 | 说明 |
|---|---|
| 阈值配置化 | **严禁硬编码** |
| 阈值方式明确 | 须声明按绝对分数还是按分位分层 |
| Peer Group 内分层 | 与排名同一样本集 |
| 可追溯 | 记录当时的阈值配置版本 |

#### 16.3.1 第一阶段分层方案（已定案 · 2026-08-25）

> **按 `Peer Group` 内分位分层。**

| Tier | 分位区间 | 含义 |
|---|---|---|
| **A+** | 前 5% | Excellent |
| **A** | 5% – 20% | Very Good |
| **B** | 20% – 50% | Good |
| **C** | 50% – 80% | Neutral |
| **D** | 后 20% | Weak |

**为什么不按绝对分数分层**：`Fund Score` 本身就是各 Factor 在 `Peer Group` 内做分位标准化后合成的——它已经是相对量。在相对量上再切绝对阈值，切出来仍然是分位，只是把这一事实隐藏起来，并引入各层人数随组内分布漂移的副作用。

**已知局限与强制缓解措施**：分位分层意味着无论该 Peer Group 整体质量如何，**永远有 5% 被评为 A+**。缓解手段不在分层规则内，而是强制要求：

> **`Fund Tier` 必须与该 `Peer Group` 的绝对水平同屏展示**（至少含组内 Sharpe 中位数与 Maximum Drawdown 中位数），使读者能判断"A+ 在这一组意味着什么"。仅展示 Tier 而不展示组内绝对水平，视为违反本条。

若后续需要绝对门槛（未达标者不得进入 A+/A），作为 P1 项追加，不改变分位分层的基础方案。

### 16.4 分层的用途与边界

用途：快速发现优秀基金、排除弱势基金、作为 Eligibility Rules 的可选输入、支持组合角色划分。

> **分层不等于投资建议。** A+ 不意味着"应该买"，D 也不意味着"应该卖"（§27.4）。

---

## 17. Fund Screening & Fund Universe

> 本章合并了筛选与候选池——两者是同一件事的规则与产出。

### 17.1 Screening 与 Eligibility Rules 的区别

**这是两个不同的东西**，此前容易被混为一谈：

| | 探索性筛选（Screening） | 正式准入规则（Eligibility Rules） |
|---|---|---|
| 使用者 | 研究人员在界面上临时筛选 | 策略配置的一部分 |
| 是否版本化 | 否 | **是**，属 Strategy Version |
| 是否可回测 | 否 | **是** |
| 是否产生 Universe | **否** | **是** |
| 典型形态 | "规模 > 10 亿" 点几下看看 | `Eligibility Rules v1.2` |

> UI 上的一次筛选**不构成** `Fund Universe`。只有正式的、版本化的 `Eligibility Rules` 才产生 Universe。

### 17.2 Fund Universe 的定义与构成

`Fund Universe`（业务称"候选基金池"）= 通过 `Eligibility Rules` 后允许进入组合构建的基金集合。

```
Fund Coverage
     ↓  Eligibility Rules（必要）
合格基金集合
     ↓  Fund Score 排序（可选）
Fund Universe
```

**三种 Universe 构成策略**（`Fund Score` 是**可选输入**，不是 Universe 的固有属性）：

| 策略 | 构成方式 | 是否需要 Score |
|---|---|---|
| **A：Eligibility only** | 仅硬性准入规则 | 否 |
| **B：Eligibility + Score Threshold** | 准入 + Score ≥ 阈值 | 是 |
| **C：Eligibility + Score Top-N** | 准入 + Score 排名前 N | 是 |

采用策略 A 时，Universe 快照中的评分字段为空，这是**正常情况**，不构成留痕缺失。

`Equal Weight`、`Minimum Volatility`、`Risk Parity` 等策略适用 A，无需 Score。

### 17.3 入池 ≠ 持有 ≠ 可买入

三个概念必须区分：

| 概念 | 含义 |
|---|---|
| 进入 `Fund Universe` | **可以**被选（评价维度） |
| 组合持仓 | 优化器实际给予正权重 |
| **`Investment Eligibility`** | 在该时点**能否实际建仓**（可投资性维度，见 §18） |

> 一只基金可以同时是"高分入池"且"当前不可买入"——两个维度正交。

### 17.4 筛选维度

| 类别 | 条件 |
|---|---|
| 基础 | 基金类型、成立时间、基金规模、经理任职时间 |
| 收益 | 1Y / 3Y / 5Y Return 阈值或分位 |
| 风险 | Maximum Drawdown、Volatility、VaR / CVaR 上限 |
| 风险收益 | Sharpe / Sortino / Calmar 下限、Alpha 下限、IR 下限 |
| 稳定性 | Win Rate 下限、Rolling 指标稳定性 |
| **可投资性** | `Investment Eligibility` 状态（见 §18） |

**基金规模的双向约束**：规模需上下限双向约束——过小面临清盘风险与流动性问题；过大则策略容量受限、超额收益被稀释。

> 但**不在业务需求层假设具体上界**。规模上限是 **Strategy-specific Capacity Rule**，随策略类型而变（中小盘策略容量远低于大盘策略），必须可配置。`<TBD-P1-7: 各策略类型的容量规则待投研确认>`

### 17.5 筛选结果的可解释性

> **每条结果必须能回答：为什么该基金进入/未进入候选池？**

必须记录每只基金**通过了哪些条件**、**未通过哪些条件**。对被排除的基金同样记录——如果 90% 的基金因同一条件被排除，说明该条件可能设置不当。

### 17.6 Universe 快照

> **每个历史时点的 `Fund Universe` 必须留存完整快照。**

| 字段 | 说明 |
|---|---|
| `decision_at` | 时点 |
| 成员列表 | 该时点全部入池基金 |
| Eligibility Rules 版本 | 可追溯 |
| Scoring 版本 | 策略 B/C 时必填；策略 A 时为空 |
| 评分与子分 | 同上 |
| 入池 / 出池原因 | 通过或未通过哪些条件 |
| `Data Completeness` | 评分可信度 |
| `Investment Eligibility` 状态 | 该时点可投资性 |

**未完整留痕的时点，其回测结果无效**——否则回测不可复现，且无法避免幸存者偏差（§26.2）。

### 17.7 Universe 的变动监控

业务上需要能回答：本期新入池/出池了哪些基金及原因；Universe 规模变化是否正常（骤增骤减通常意味着规则或数据出了问题）。

---

## 18. Investment Eligibility

> 本章新增。此前"基金处于什么状态"与"基金能不能买"被混为一谈，会导致回测在暂停申购期照常建仓。

### 18.1 与 Fund Lifecycle Status 的分离

| | `Fund Lifecycle Status` | `Investment Eligibility` |
|---|---|---|
| 回答 | 基金**处于什么状态** | 在 `decision_at` 时点**能否交易** |
| 取值 | NORMAL / SUSPENDED_SUBSCRIPTION / LIQUIDATED / MERGED / TRANSFORMED | 见 §18.2 |
| 用途 | 描述性、事件记录 | **回测与实盘的建仓判断依据** |

**为什么必须分离**：

```
基金状态 = 暂停申购
  → 不可建仓 ✓
  → 不可加仓 ✓
  → 仍可持有 ✓   ← 单一 Lifecycle Status 无法表达
  → 仍可减仓 ✓   ← 单一 Lifecycle Status 无法表达
```

**"暂停申购 ≠ 不可持有"**。若用 Lifecycle Status 直接判断可投资性，会错误地把暂停申购的持仓强制清仓。

### 18.2 Investment Eligibility 取值

| 状态 | 可建仓 | 可加仓 | 可持有 | 可减仓 |
|---|:---:|:---:|:---:|:---:|
| `FULLY_ELIGIBLE` | ✓ | ✓ | ✓ | ✓ |
| `HOLD_ONLY`（暂停申购） | ✗ | ✗ | ✓ | ✓ |
| `LIMITED`（限制大额申购） | 受限 | 受限 | ✓ | ✓ |
| `EXIT_ONLY`（即将清盘/转型） | ✗ | ✗ | ✓ | ✓ |
| `NOT_TRADABLE`（已清盘/暂停赎回） | ✗ | ✗ | — | ✗ |

### 18.3 影响可投资性的因素

| 因素 | 影响 |
|---|---|
| 暂停申购 / 暂停大额申购 | `HOLD_ONLY` / `LIMITED` |
| 暂停赎回 | 影响可减仓 |
| 基金清盘 / 合并 / 转型 | `EXIT_ONLY` → `NOT_TRADABLE` |
| 最低申购金额 | 影响小额建仓可行性 |
| 限制大额申购的金额上限 | 影响单只基金的最大可配置金额 |
| 申赎费率与持有期惩罚 | 影响调仓成本，见 §21.7 |
| **ETF 流动性**（见 §18.4） | 影响实际可成交规模 |

### 18.4 ETF / 场内基金的流动性准入

若第一阶段支持 ETF，"关注流动性"必须升级为**正式准入规则**：

| 指标 | 用途 |
|---|---|
| Average Daily Volume | 日均成交额下限 |
| Turnover | 换手活跃度 |
| Bid-Ask Spread | 交易成本与冲击成本估计 |
| AUM | 规模下限 |
| Creation/Redemption Status | 申赎机制是否正常运作 |

上述指标进入 `Eligibility Rules`，不满足则 `Investment Eligibility` 降级。`<TBD-P1-8: ETF 流动性各项阈值待投研确认>`

### 18.5 可投资性的 PIT 属性

> `Investment Eligibility` 必须按 `available_at ≤ decision_at` 判定。

暂停申购公告的**发布时刻**是 `available_at`，暂停**生效日**是 `effective_at`。回测在 `T` 时点判断能否建仓，依据的是 `available_at ≤ T` 的最新状态——不得使用尚未公告的信息。

### 18.6 基金经理与规模的角色定位

两个此前未明确归属的因素：

| 因素 | 角色 | 说明 |
|---|---|---|
| **Manager Tenure**（任职时长） | `Factor` + `Eligibility` | 可作为筛选条件与评分输入 |
| **Manager Change**（变更事件） | **`Event`** | 是事件不是指标。触发重新评估，可作为 `Eligibility Rules` 的观察期条件（如变更后 N 个月内不入池） |
| **AUM Level**（规模水平） | `Eligibility` | 上下限双向约束（§17.4） |
| **AUM Trend**（规模变化） | `Factor` / 风险指标 | 规模骤降可能预示清盘风险，是风险信号而非准入条件 |

> **推荐默认 · 2026-08-27**：Manager Change 观察期 = **12 个月**。业务方可改。
>
> **依据**：与最短评价窗口 1Y 对齐，使观察期结束时**至少有一个完整评价周期**由新任经理产生。短于此则新经理的表现无法与历史分离。
>
> **观察期内的处理**：基金**不移出 Universe**，但在评价结果中标注 `MANAGER_CHANGED_WITHIN_OBSERVATION`。**不自动降级评分** —— 更换经理不必然是负面事件，标注的作用是提示使用者「这段历史的归属需要重新判断」。
>
> **须与 `08-backtest/04` `SB-3` 的数据完整性问题联动**：经理变更历史本身的记录质量参差（这正是 `06-portfolio/05` `CS-1` 不启用经理层集中度约束的理由），因此本机制的有效性取决于该数据的可得性。

---
## 19. Portfolio Construction

### 19.1 "规则化"与"优化"不是对立关系

> `Portfolio Construction`（Stage ⑥）**定义问题**，`Portfolio Optimization`（Stage ⑦）**求解问题**。"Rule-based"与"Optimization"不在同一维度上。

第一阶段的实际含义是**优先采用简单、可解释的目标与规则**，而不是"不做优化"。

### 19.2 权重生成的两条路径

这是本文档此前自相矛盾的一处，现明确区分：

```
路径一：确定性权重规则（Deterministic Weighting Rule）
  Fund Score / 等权 / 类别配置
        ↓  Weighting Rule
     Raw Weight
        ↓  Constraint Enforcement
    Target Weight

路径二：优化目标（Optimization Objective）
  Return Estimate + Covariance
        ↓  Objective Function + Constraint Set
     Optimization Solve
        ↓
    Target Weight
```

| | 确定性权重规则 | 优化目标 |
|---|---|---|
| 举例 | Equal Weight、**Score Weight**、类别固定配比 | Minimum Volatility、Maximum Sharpe、Risk Parity |
| 是否求解优化问题 | 否——直接映射后施加约束 | 是 |
| 是否需要 `Σ` | 否 | 是 |
| 是否需要 `Return Estimate` | 否 | Max Sharpe 需要；Min Vol 不需要 |

> **`Score Weight` 属于路径一，不是"优化目标"。** 此前把它称作"规则化的优化目标"是不准确的表述。

### 19.3 Score-based Weighting 与"Score 不决定持有多少"的关系

两条规则并存且不冲突，因为它们约束的是**不同的东西**：

| 规则 | 约束的内容 |
|---|---|
| **`Fund Score` 不具有收益预测语义** | 语义约束——Score 不得作为 `μ` 输入优化器，不得换算为收益率 |
| **允许 Score-based Weighting Rule** | 机制许可——Score 可作为**显式声明的确定性权重映射规则**参与组合构建 |

**判定标准**：

```
✅ 允许：Score 排名前 10 的基金，按 Score 归一化分配权重，再施加约束
        （这是一条显式的、可回测的权重规则）

❌ 禁止：把 Score 当作年化收益率代入 μ'w - λ/2·w'Σw 求解
        （这是把无量纲排序量当成有量纲收益率）
```

**因此 §6.2 的表述精确化为**：`Fund Score` 不通过"收益预测"的方式决定权重，但可以通过"显式权重规则"的方式决定权重——后者必须在 `Portfolio Rule Version` 中声明，且承担全部可解释性要求。

### 19.4 Portfolio Strategy 的完整定义

一个可执行的组合策略必须由**四要素**共同定义，缺一不可：

```
Portfolio Strategy
  = Eligibility Rules        （谁可以被选）
  + Objective / Weighting Rule（按什么原则配权重）
  + Constraint Set           （不可逾越的硬性限制）
  + Risk Budget              （风险如何分配）
```

**仅指定目标函数不构成策略**——"Maximum Sharpe" 没有说明约束与风险预算，无法执行。

第一阶段策略组合示例：

| 策略 | Eligibility | 权重生成 | 主要约束 |
|---|---|---|---|
| Baseline-EW | 基础准入 | Equal Weight（路径一） | 单基金上限 |
| Baseline-SW | 准入 + Score Top-N | Score Weight（路径一） | 单基金/类别上限 |
| MinVol | 基础准入 | Minimum Volatility（路径二） | 单基金上限 + 类别上限 |
| MaxSharpe | 准入 + Score Top-N | Maximum Sharpe（路径二） | 全约束 + 风险预算 |

`<TBD-P1-10: 各策略的上线顺序与默认参数待投研确认>`

### 19.5 组合构建必须考虑的因素

基金评分（作为准入/权重规则，非收益估计）、基金类别、风险水平、**基金之间相关性**、资产配置、单基金/单类别权重上限、组合风险上限。

### 19.6 相关性为什么必须纳入

> **一组各自优秀但高度相关的基金，组合起来是一个糟糕的组合。**

这是"单基金评价 ≠ 组合决策"的根本原因。筛选阶段筛掉高波动基金**不等于**组合波动可控——若留下的基金彼此高度相关，组合风险仍然很高。因此 `Correlation Matrix` 与 `Covariance Matrix` 是**必需输入**。

### 19.7 第一阶段明确不引入

AI Portfolio Manager、ML Portfolio Optimization、LLM 自动决策。

---

## 20. Risk Control

### 20.1 事前约束 vs 事后监控：可计算性边界

> **不是所有风险指标都能作为事前约束。** 这取决于该指标在建仓时是否可计算。

| 控制项 | 事前约束 | 事后监控 | 说明 |
|---|:---:|:---:|---|
| 单基金权重上限 | ✅ | ✅ | 权重直接可约束 |
| 类别权重上限 | ✅ | ✅ | 同上 |
| **组合波动率上限** | ✅ | ✅ | `σ_p = sqrt(w'Σw)` 在给定 `Σ` 下**可直接计算**，可作为优化约束 |
| **最大组合回撤** | **❌ 见下** | ✅ | **未来回撤路径未知，不是建仓时可直接计算的量** |
| 组合集中度（HHI / 前 N 大） | ✅ | ✅ | 权重的函数，可约束 |
| 相关性约束 | ✅ | ✅ | 基于 `Σ` |
| 换手率上限 | ✅ | ✅ | 当前权重与目标权重之差 |

### 20.2 最大回撤为什么不能直接作为事前约束

```
Volatility 事前约束：  σ_p = sqrt(w'Σw) ≤ X       ✅ 给定 w 与 Σ 即可计算
最大回撤事前约束：     Future MaxDD(w) ≤ X        ❌ 依赖未来价格路径，建仓时未知
```

最大回撤是**路径依赖**的量。同样的权重与协方差，不同的价格路径会产生完全不同的回撤。

**因此**：

- **默认**：最大回撤为**事后监控指标**（对历史/实盘净值序列计算）
- **如需事前控制**，必须先定义一个**可计算的代理约束**，例如：
  - 基于历史情景重演（Historical Scenario）的回撤估计
  - 基于蒙特卡洛模拟路径的回撤分位数
  - 用波动率与相关性构造的回撤代理指标

  具体方法由 `06-portfolio` 定义。

##### 已定案 · 2026-08-27：不设事前回撤约束，用 CVaR 替代

> **定案**：第一阶段**不实现事前回撤约束**；下行风险的事前控制由 **CVaR 约束**承担，最大回撤保持为**事后监控指标**。

**依据 —— 这是数学性质而非偏好**：

| 量 | 性质 | 能否进优化 |
|---|---|---|
| **最大回撤** | **路径依赖的历史极值统计量**，不是权重 `w` 的凸函数，甚至不是连续函数 | ❌ 无法作为凸优化的约束 |
| **CVaR** | 凸函数，且可由 Rockafellar-Uryasev 表示为**线性约束** | ✅ 可直接进 LP |

```
两只基金各自最大回撤 10%
    → 组合的最大回撤【不能】由两者的回撤加权得出
    → 它取决于两者回撤【是否发生在同一时间】
    → 而这是路径信息，不在 (μ, Σ) 中
```

**三个代理方案为何都不采用**：

| 代理 | 问题 |
|---|---|
| 历史情景重演 | 只覆盖历史上真实发生过的路径，对未出现过的组合形态无约束力 |
| 蒙特卡洛路径分位数 | 引入随机性 —— 须固定种子，且回撤分位数对路径模型（是否含波动率聚集、厚尾）高度敏感，模型选择本身又是一组待定参数 |
| 波动率与相关性构造的代理 | 本质上就是在用二阶矩近似路径极值，与直接用 CVaR 相比没有增加信息，却多了一层不可解释的映射 |

> **CVaR 不是「回撤的近似」，而是一个不同但同样有意义的下行风险度量** —— 它回答「最坏 5% 的期间平均亏多少」，回撤回答「历史上从峰到谷最多亏多少」。**用 CVaR 约束不等于控制住了回撤**，报告中不得如此表述。

**回撤仍须监控**：事后计算、进入风险指标体系与回测报告、超阈值触发告警（阈值属 `TBD-P1-13`）。

详见 `TBD-resolution-2.md` §3.1。

> **不得**在业务需求层写下一个无法落地的约束——那会让 `06-portfolio` 面对一个无解的要求。

### 20.3 Risk Budget 的六要素

> **每条 Risk Budget 必须完整定义六要素，缺一不得进入优化问题**（上游 §11.2）。

| 要素 | 内容 | 示例 |
|---|---|---|
| **① 风险指标** | 对哪个量做预算 | 组合波动率 / 风险贡献占比 / Tracking Error |
| **② 预算值** | 数值上限或目标 | ≤ 15% |
| **③ 适用范围** | 整体 / 类别 / 单基金 / 风险因子 | 权益类整体 |
| **④ 计算方式** | 如何计算该风险量 | `TRC_i / σ_p` |
| **⑤ 超预算处理** | 硬性拒绝 / 告警 / 自动收缩 | 触发 `WARNING`，超 120% 触发 `CRITICAL` |
| **⑥ 硬约束 or 软目标** | 是否可被违反 | 硬约束 |

**Risk Budget 类型示例**：

```
组合波动率预算       Portfolio Volatility ≤ 15%
类别风险贡献预算     Equity Risk Contribution ≤ 60%
单基金风险贡献预算   Single Fund Risk Contribution ≤ 20%
跟踪误差预算         Tracking Error ≤ 4%
```

`<TBD-P1-12: 各项 Risk Budget 的具体预算值待投研与风控确认>`

### 20.4 风险告警分级

```
NORMAL  ──  各项风险指标在阈值内
WARNING ──  接近阈值，需关注
CRITICAL ── 突破阈值，需处置并阻断调仓流程
```

阈值可配置。`<TBD-P1-13: 各风险指标的 WARNING / CRITICAL 阈值待投研与风控确认>`

### 20.5 优化不可行时的处理流程

> **风险控制优先级高于收益最大化。** 优化器不得自行放松约束——但"不许自动放松"之后必须有闭环。

```
Optimization Infeasible / Not Converged
            ↓
   Decision Status = INFEASIBLE（不产出 Proposed Decision）
            ↓
        上报并进入 Human Review
            ↓
   ┌────────┼────────┬─────────┐
   ▼        ▼        ▼         ▼
调整约束  调整Universe  沿用上期  中止本期
   │        │          │         │
   ▼        ▼          ▼         ▼
必须升级 Portfolio    必须显式   记录原因
Rule Version 或      声明并留痕  本期不调仓
Eligibility Version
```

**四条规则**：

| # | 规则 |
|---|---|
| 1 | 优化器**返回不可行**，不得自行放松约束求"差不多的解" |
| 2 | 放松约束是 `Portfolio Construction` 层的**显式决策**，必须**升版本并留痕** |
| 3 | "沿用上期权重"是一种**主动选择**，必须显式声明并记录，**不得作为静默降级** |
| 4 | 不可行事件本身必须记录到决策快照，供事后分析约束是否设置过紧 |

---

## 21. Backtesting

### 21.1 业务目的

> **验证基金筛选、评分与组合构建规则在历史数据上的有效性。**

回测**不是**证明未来收益能复制，**不是**参数搜索工具。

### 21.2 回测的时间推进：Rebalance Decision Point

> "持有一个周期"中的"周期"**不是固定时间单位**，而是**下一个 Rebalance Decision Point**。

```
Decision Date T
     ↓  只使用 available_at ≤ T 的数据
执行完整策略链路（Factor → Score → Universe → ⑤ → ⑥ → ⑦）
     ↓
Portfolio Held
     ↓
Next Rebalance Decision Point  T+n
     ↓  n 由 Rebalance Trigger 决定，不是固定值
重新执行策略
```

`T+n` 的确定方式：

| 触发类型 | n 的确定 |
|---|---|
| Periodic | 由配置的调仓频率决定（月/季/半年） |
| Drift | 权重偏离超阈值的那一天 |
| Eligibility Event | 成分基金失去可投资性的那一天 |
| Constraint Breach | 触碰约束上限的那一天 |

因此回测中的持有期**长度不均等**，这与 §21.9 的"调仓频率可配置"一致。

### 21.3 回测与实盘的关系

按上游 §5.4，两者是同一套 **Strategy Domain Logic** 的两种运行模式，差异**只允许存在于数据源与时间轴**。**不允许存在两套策略规则。**

### 21.4 回测输出指标

| 类别 | 指标 |
|---|---|
| 收益 | Cumulative Return、Annualized Return |
| 风险 | Volatility、Maximum Drawdown、VaR、CVaR |
| 风险调整 | Sharpe、Sortino、Calmar |
| 稳定性 | Win Rate |
| 交易 | Turnover、Number of Rebalances、成本侵蚀比例 |

### 21.5 In-Sample / Out-of-Sample / Walk-forward

> 此前的缺口：`§23.3` 要求 Validation Gate 包含"样本外验证"，但回测章节从未定义 OOS。

```
In-Sample (IS)
    ↓  规则设计与参数选择在此完成
Parameter Freeze  ← 参数冻结时点，此后不得再调
    ↓
Out-of-Sample (OOS)
    ↓  仅用于验证，不得据其反向调参
Walk-forward Validation
    滚动重复 IS→Freeze→OOS，检验规则在时间上的稳健性
```

**业务规则**：

| # | 规则 |
|---|---|
| 1 | **In-Sample 用于**规则设计与参数选择 |
| 2 | **Out-of-Sample 仅用于验证**——OOS 结果不得用于反向调整参数。一旦据 OOS 调参，该段数据即失去样本外性质 |
| 3 | **Parameter Freeze 时点必须显式记录**，并纳入 Strategy Version |
| 4 | **策略批准必须以 OOS 结果为依据**，仅 IS 表现良好不足以批准上线 |
| 5 | **Walk-forward 第一阶段为必须支持**——单次 IS/OOS 划分可能恰好落在有利区间，滚动验证才能暴露时间稳健性问题 |
| 6 | 若因 OOS 不通过而修改规则，必须**升 Strategy Version 并重新划分 IS/OOS**，不得在同一份数据上反复试错 |

> **推荐默认 · 2026-08-27**：IS : OOS = **70 : 30**，**按时间先后切分，不随机抽样**。业务方可改比例，**但「不随机抽样」是硬性要求**。
>
> **「不随机抽样」为何不可改**：时序数据随机切分会引入**前视** —— 用 2024 年的数据训练、用 2020 年的数据验证，等于用未来预测过去。这不是偏好问题。
>
> **70:30 与其它约束的联动**：OOS 段须满足 `08-backtest/02` `BM-5` 的最小 1 年，因此总有效区间须 ≥ 3.3 年。改比例后须重新核对该下限。

### 21.6 对比基准：三方比较

> 只与 Benchmark 比较不够——**必须同时与简单基线策略比较**。

```
Strategy          待验证的策略
    vs
Benchmark         Portfolio Benchmark（§8.6）
    vs
Equal Weight Baseline   同一 Universe 上的等权组合
```

**为什么必须有 Equal Weight 基线**：`Maximum Sharpe` 即使跑赢 Benchmark，也可能跑不赢同一批基金的**简单等权组合**。若如此，说明超额收益来自选基（Universe），而非来自复杂的权重优化——那么优化环节的复杂度就不值得。

**这是判断"策略复杂度是否物有所值"的唯一方式。**

### 21.7 交易成本模型

回测必须计入成本。**成本组成必须逐项明确，尤其要避免重复计费**：

| 成本项 | 是否在回测中扣除 | 说明 |
|---|:---:|---|
| 申购费（Subscription Fee） | ✅ 扣除 | 交易时发生 |
| 赎回费（Redemption Fee） | ✅ 扣除 | 交易时发生，可能含持有期惩罚 |
| **管理费（Management Fee）** | **❌ 不扣除** | **已反映在基金净值中**——再扣一次即重复计费 |
| **托管费（Custody Fee）** | **❌ 不扣除** | **已反映在基金净值中** |
| 销售服务费（Sales Service Fee） | **由 `included_in_nav` 决定** | 见 §21.7.1 |
| ETF 买卖价差（Bid-Ask Spread） | ✅ 扣除 | 场内交易成本 |
| 市场冲击成本（Market Impact） | ✅ 扣除 | 大额交易时显著 |

> **管理费与托管费已内含于基金净值**是基金产品的基本事实。回测若在净值收益之上再扣一次管理费，会系统性低估策略表现约 1–2% 年化——这是一个方向相反但同样严重的错误。

具体成本模型由 `08-backtest/05-transaction-cost` 定义。

#### 21.7.1 从「费率定义」升级为「费用包含关系」（已定案 · 2026-08-27）

> **定案**：`TBD-P1-15` 关闭。**每种费用必须显式声明它是否已含于净值**，而不是逐项讨论「扣不扣」。详见 `TBD-resolution.md` Policy ⑩。

**为什么这不只是措辞变化**：上表的「是否扣除」是**结论**，而结论依赖一个未被记录的前提 —— 该费用是否已在净值里。前提不记录，就只能靠人记住「管理费已含、申购费未含」；一旦遇到边界情形（销售服务费因份额类别而异），无从判断。把前提显式化，结论就可推导：

```
included_in_backtest  =  NOT included_in_nav  AND  该费用在交易时发生
```

**每种费用的必备元数据**：

| 字段 | 含义 |
|---|---|
| `expense_type` | 费用类型 |
| `expense_rate` | 费率（**受 PIT 约束**，见下） |
| **`included_in_nav`** | **是否已扣于净值 —— 关键字段** |
| `included_in_return` | 是否已反映在收益序列中 |
| `included_in_backtest` | 由前两者**推导**，不独立配置 |
| `inclusion_source` | 该判定的依据（数据源文档 / 招募说明书 / 人工核定） |

**包含关系清单**：

| 费用 | `included_in_nav` | `included_in_backtest` |
|---|:---:|:---:|
| Management Fee | ✅ | ❌ |
| Custody Fee | ✅ | ❌ |
| **Sales Service Fee** | **待核**（`OPEN-19`） | 由左列推导 |
| Subscription Fee | ❌ | ✅ |
| Redemption Fee | ❌ | ✅ |
| Transaction Cost（价差、冲击） | ❌ | ✅ |

**`UNKNOWN` 的处理**：

| 情形 | 处理 |
|---|---|
| 数据源未声明净值是否含某费用 | 标 **`UNKNOWN`**，回测中**不扣除**，但**必须在 `unmodeled_costs` 中列出并在报告披露** |
| 费率数据缺失 | 该基金标 `INSUFFICIENT_DATA`，**不得默认为 0** |

> **`UNKNOWN` 时不扣除是不保守的方向** —— 它使成本被低估、表现被高估。之所以仍选它，是因为另一个方向（默认扣除）会在费用其实已含于净值时造成重复扣费，那是**双重错误**（既低估表现又无法察觉）。不扣除至少是**单一且已披露**的偏差。这是在两个坏选项中选可控的那个，不是最优解。

**费率受 PIT 约束**：

```
2022 年申购费 1.5%，2024 年降至 1.0%
    → 回测 2022 年的交易必须用 1.5%
    → 用今天的 1.0% 是【费率的版本前视】
```

`<OPEN-19: 数据源的净值是否已扣销售服务费 —— 本项的唯一阻塞点，待数据侧核实>`
`<OPEN-20: 不同份额类别（A/C/I）的销售服务费包含关系是否一致，待逐类确认>`

### 21.8 交易可得性

回测的每次建仓/加仓必须检查 `Investment Eligibility`（§18）——不得在暂停申购期建仓。这是与 PIT 同等重要的回测真实性要求。

### 21.9 回测周期与市场环境覆盖

必须支持配置回测区间与调仓频率，且回测区间应覆盖**不同市场环境**（上涨、下跌、震荡），否则无法判断策略的环境依赖性。

> **推荐默认 · 2026-08-27**：默认回测区间 = **近 8 年**，默认调仓频率 = **季度**。业务方可改。
>
> **8 年的依据**：覆盖至少一轮完整市场周期，且在 70:30 划分下留出约 2.4 年 OOS，满足最小 1 年的要求。
>
> **季度频率的依据**：在成本与响应之间取平衡 —— 月度调仓的成本在基金申赎费率下显著（单边 0.15% + 赎回费阶梯），而基金相对表现的变化通常不会在一个月内产生足以覆盖该成本的改善。
>
> ⚠️ **配置回测区间时须倒推 Warm-up**：`有效区间 = 区间长度 − Warm-up`，而有效区间须 ≥ 3.3 年。若因子最长窗口为 5Y，Warm-up 会吃掉 5 年 —— **8 年区间下有效区间仅 3 年，已不满足**。此时须延长区间而非缩短窗口。

---

## 22. Strategy Evaluation

### 22.1 必须回答的八个问题

仅给出一条净值曲线不满足业务要求：

| # | 问题 | 判断依据 |
|---|---|---|
| 1 | 策略是否长期有效 | 分年度/分阶段收益 |
| 2 | 收益是否稳定 | 滚动收益、滚动 Sharpe 的波动 |
| 3 | 最大回撤是否可接受 | MaxDD、Drawdown Duration |
| 4 | 是否存在明显失效阶段 | 分阶段超额收益 |
| 5 | 是否过度依赖某些基金 | 收益归因至个基的集中度 |
| 6 | 是否过度依赖某些市场环境 | 分市场环境的表现 |
| 7 | 换手率是否过高 | Turnover、成本侵蚀比例 |
| 8 | 是否优于 Benchmark **与 Equal Weight 基线** | 三方对比（§21.6） |

### 22.2 "显著优于"必须有统计定义

> "显著"是统计学术语，不得作为形容词使用。

本文档规定：**"显著优于"必须由 `08-backtest` 定义具体的统计检验方法与最低标准**，业务层要求其至少包含：

- 检验方法（t 检验 / Bootstrap / 其他）
- 置信水平
- 最小样本期要求
- 判定阈值（如 IR 下限、跑赢概率下限）

#### 22.2.1 判定方法（已定案 · 2026-08-25）

> **采用三重证据，不依赖单一 p 值。** 三条全部通过才可称"显著优于"：

| # | 证据 | 说明 |
|---|---|---|
| 1 | **Information Ratio 达阈值** | 单位跟踪误差的超额收益达标 |
| 2 | **跑赢概率达阈值** | 滚动窗口内跑赢对比基准的比例达标 |
| 3 | **Block Bootstrap 置信区间下界为正** | 重采样构造超额收益分布，区间下界须大于 0 |

**为什么不用 t 检验**——它在两个方向上同时失真：

- **样本量不足会漏判**：5 年月度数据仅 60 个观测。即使策略真实 IR 达到 0.5，t 检验在该样本量下的检出功效也只有五成左右，追求 `p < 0.05` 会拒绝掉大量真实有效的策略。
- **自相关与肥尾会误判**：基金收益存在自相关与厚尾，标准 t 检验的独立同分布正态假设不成立，会**高估**显著性。

两个方向的偏差同时存在，使单一 p 值在本场景下既不敏感也不可靠。Block Bootstrap 通过分块重采样保留自相关结构，不依赖分布假设。

**三个阈值**（IR 下限、跑赢概率下限、Bootstrap 重采样次数与置信水平）作为 P1 项与 `08-backtest` 一并确定（见 §35.2 P1-21）。

在上述阈值确定前，**回测报告不得使用"显著优于"的表述**，只能陈述观测到的数值差异。

#### 22.2.2 第四层：经济显著性（已定案 · 2026-08-27）

> **统计显著不代表投资意义显著。** 三重证据解决的是"差异是否真实"，但没有回答"差异是否值得"。

```
A 的 Sharpe 比 B 高 0.03，Bootstrap 区间下界为正
    → 差异是真实的
    → 但 0.03 的 Sharpe 差异在投资上没有意义
    → 【不能】称 A 显著优于 B
```

**定案**：在原三重证据之上追加**第四道门槛**，四条全部通过才可称"显著优于"：

| 层 | 判据 | 来源 |
|---|---|---|
| **① 统计显著性** | Block Bootstrap 置信区间下界为正 | 原证据三 |
| **② 效应量** | Information Ratio ≥ 阈值 **且** ΔSharpe ≥ 阈值 | 原证据一 + 本次补充 |
| **③ 稳健性** | 跑赢概率 ≥ 阈值 | 原证据二 |
| **④ 经济显著性** | **年化收益改善 ≥ 阈值** 或 **最大回撤改善 ≥ 阈值** | **本次新增** |

**两条说明**：

| # | 说明 |
|---|---|
| 1 | **第四层不替代前三层** —— 经济显著但统计不显著同样不能称"优于"，那可能只是运气 |
| 2 | **ΔSharpe 并入第②层**是因为它衡量的是标准化后的效应量，与 IR 同类；而年化收益/回撤的改善是**未标准化的经济量**，属独立维度 |

具体阈值随 P1-21 一并确定（`08-backtest/02-backtest-methodology` §9）。详见 `TBD-resolution.md` Policy ⑨。

> **仍待裁决**：是否改用「统计显著性 + 效应量 + 经济显著性」的三层构成（取消"跑赢概率"、引入 `p < 0.05`）。本次采用的是**保留原三重 + 追加第四层**的方案 —— `p < 0.05` 与 §22.2.1 的 t 检验论证冲突，"跑赢概率"衡量的时间稳健性亦不可由效应量替代。见 `TBD-resolution.md` §3.1。

`<OPEN-1: 「显著优于」的最终构成 —— 是否改为「统计显著性 + 效应量 + 经济显著性」三层（取消跑赢概率、引入 p < 0.05），还是保留本次采用的「上游三重 + 追加第四层」，待业务与治理裁决>`

### 22.3 过度依赖的识别

两类必须显式检查：**过度依赖某些基金**（收益集中于一两只基金 = 在押注个基而非依靠规则）与**过度依赖某些市场环境**（超额收益全部产生于某一段行情）。

### 22.4 策略上线的评估维度

> 业务层定义**维度**，具体阈值由 `13-governance` 定义。

一个策略进入 `APPROVED` 状态前，必须在以下维度全部通过：

| 维度 | 检查内容 |
|---|---|
| **Data Quality Gate** | 回测期数据质量达标，无 Global 级异常 |
| **Bias Check Gate** | 无前视偏差、无幸存者偏差、交易可得性已校验 |
| **Out-of-Sample Gate** | OOS 表现达标（§21.5） |
| **Robustness Gate** | Walk-forward 结果稳健，不依赖单一区间 |
| **Risk Gate** | 最大回撤、波动率在可接受范围 |
| **Cost Gate** | 成本后仍有超额收益，换手率合理 |
| **Baseline Gate** | 优于 Benchmark **且**优于 Equal Weight 基线 |
| **Operational Gate** | 运行时延、数据依赖、异常处理就绪 |

`<TBD-P1-17: 各 Gate 的具体阈值待治理与投研确认>`

---
## 23. Strategy Versioning

### 23.1 Strategy Version 的完整组成

> 此前的问题：`Strategy Version` 只含评分/筛选/组合三类规则，但回测又单独记录 `Metric Version` 与 `Benchmark Version`——说明 Strategy Version 并不构成完整的策略定义。同一个 Strategy Version 可能因 Metric Version 不同而产出不同结果。

**Strategy Version 必须包含九个组成部分**：

```
Strategy Version
├── Metric Version              指标（Factor）计算口径
├── Peer Group / Classification Version   分组规则
├── Eligibility / Universe Version        准入规则
├── Scoring Version             评分方案（指标·权重·标准化·方向·缺失处理）
├── Return Estimate Version     收益估计方法与口径
├── Risk Model Version          风险与协方差估计方法
├── Portfolio Rule Version      目标/权重规则 + 约束集 + 风险预算
├── Rebalance Rule Version      触发条件 + 重算范围 + 调仓阈值
└── Benchmark Version           Fund / Portfolio Benchmark 映射规则
```

> **判定标准**：任何一项变化会导致相同输入产生不同输出的配置，都必须属于 Strategy Version。`Metric Version` 与 `Benchmark Version` 因此**属于** Strategy Version，而非并列项。

#### 23.1.1 Policy Version：第 10 类（已定案 · 2026-08-27）

> **此前的缺口**：`Evaluation` / `Ranking` / `Classification` / `Estimation` / `Validation` 等 Policy 都会改变结果，但**都不在九项之内** —— 它们的变更不进决策快照，依赖它们的结果无法复现。

**定案**：新增统一的**第 10 类 `Policy Version`**，而非把各类 Policy 逐个追加为第 10、11、12 项。

```
Decision Snapshot
├── Strategy Version   （九项，见上）
├── Policy Version     （第 10 类，以下五个子项）
│   ├── evaluation_policy       含 MAR、评价周期、准入
│   ├── ranking_policy          含 Percentile 约定、Tie Method
│   ├── classification_policy   含 Tier 阈值与边界约定
│   ├── estimation_policy       含估计框架与方法参数
│   └── validation_policy       含各类 Gate 阈值
├── Data Snapshot
└── Code Version
```

**三条规则**：

| # | 规则 |
|---|---|
| 1 | **`Policy Version` 是五个子项的组合引用** —— 与 `Strategy Version` 是九项组合引用同理 |
| 2 | 五个子项**各自独立版本化**，便于定位是哪一部分变更 |
| 3 | **决策快照必须同时引用 `Strategy Version` 与 `Policy Version`** —— 缺任一则不可复现 |

> **为什么归为一类而非逐项追加**：五者性质相同（都是"评价与判定的规则配置"），逐项追加会使 Strategy Version 无限膨胀。详见 `TBD-resolution.md` Policy ⑧。

### 23.2 版本号语义

`Strategy Version` 采用 `Major.Minor.Patch`，语义必须明确——否则版本号只是展示，不具备治理意义：

| 级别 | 含义 | 历史结果可比性 | 是否需重新回测与审批 |
|---|---|---|---|
| **Major** | 业务逻辑变化（改评分维度、改优化目标、改准入逻辑） | **不可直接比较** | 必须重新完整回测 + 重新走 Approval |
| **Minor** | 新增可选能力，不改变既有策略行为（新增一个可选因子、新增一种可选策略） | 可比较 | 需回归验证 |
| **Patch** | 文档、配置说明、非业务性错误修复 | 可比较 | 无需重新回测 |

**关键推论**：Major 变更后的回测结果与变更前**不具可比性**，不得放在同一张净值图上直接对比而不加说明。

### 23.3 每次回测必须记录

Strategy Version（含上述八项）、`decision_at` 序列、Rebalance Frequency 配置、IS/OOS 划分与 Parameter Freeze 时点、当次生效的 Constraint Set 与 Risk Budget。

**缺少任一字段，该次回测结果不得作为决策依据。**

### 23.4 Strategy Lifecycle

```
DRAFT → VALIDATING → APPROVED → ACTIVE → SUSPENDED
```

各状态的准入门槛见 §22.4；具体阈值由 `13-governance` 定义。

---

## 24. Data Quality Requirements

### 24.1 必须处理的数据问题

缺失数据、异常收益、成立时间不足、清盘、暂停申购、合并、拆分、分红、净值复权、Benchmark 缺失、多源日期不一致。

### 24.2 时点语义：decision_at 与 data_as_of

> 此前的错误：`decision_at` 在输出章节被写成"数据截止时点"，而其定义是"决策发生时点"。**这是两个概念。**

| 字段 | 含义 |
|---|---|
| `effective_at` | 数据事实在业务上生效/所属的日期 |
| `available_at` | 该事实首次对平台可见的时刻——**PIT 判定的唯一依据** |
| `version` | 修订版本，旧版本保留 |
| **`decision_at`** | **执行本次决策的时点** |
| **`data_as_of`** | **本次决策所采用的数据截止时点** |

**第一阶段约定**：`data_as_of = decision_at`——即决策只使用截至决策时刻可获得的数据。

> 保留两个字段而非合并，是为未来可能出现的场景预留：如决策发生在 T+1 早晨但明确只使用 T 日收盘数据。届时 `data_as_of ≠ decision_at`，两者不可混用。

**业务侧的 Data Date / Calculation Date / Analysis Date 三日期方案已废弃**——Calculation Date 与 Analysis Date 实为同一概念，且该方案缺少 `available_at`，无法防止前视偏差。

### 24.3 数据版本选择规则

同一 `effective_at` 存在多个 `version` 时（如净值多次修订）：

```
候选版本集 = { v | v.available_at ≤ decision_at }
选取       = 候选集中 version 序号最大者
```

**判定依据是 `version` 序号（修订序列），不是 `available_at` 的最大值**——两者通常一致，但在数据回补场景下可能不一致（较晚落库的可能是较早的修订版本）。具体规则由 `03-data` 固化。

### 24.4 数据质量状态与阻断粒度

> 此前的问题："数据质量不达标必须阻断"过于笼统。1000 只基金里 1 只有问题，不应停掉整个决策周期。

**状态**：`VALID` / `WARNING` / `INVALID`

**阻断粒度分三级**——这是状态之外的独立维度：

| 级别 | 影响范围 | 举例 |
|---|---|---|
| **Fund-level** | 只影响该基金 | 某基金规模数据缺失 → 该基金相关筛选条件 `UNAVAILABLE`，可能退出 Universe，**其余基金正常计算** |
| **Metric-level** | 只影响依赖该指标的结果 | 某基金 Benchmark 缺失 → 该基金的 Alpha/Beta/IR/TE 全部 `UNAVAILABLE`，其他指标正常 |
| **Global-level** | **阻断整个决策周期** | 全市场净值数据未到位、数据日期整体错位、数据源批次缺失 |

**状态与粒度的组合规则**：

| 状态 | 处理 |
|---|---|
| `VALID` | 正常参与计算 |
| `WARNING` | **可以继续参与计算**，但结果必须携带质量标记并向上传递至最终输出 |
| `INVALID` | **不得参与计算**，受影响对象按上表粒度处理 |
| `INVALID` 且属 Global-level | **阻断整个决策周期**，人工确认后方可继续 |

> **`WARNING` 明确可以继续**——此前"数据质量不达标必须阻断"的表述与 `WARNING = 存在问题但可用` 自相矛盾，现予澄清：只有 `INVALID` 触发阻断，且阻断范围由粒度决定。

### 24.5 异常不得静默忽略

无论哪一级，数据质量异常都必须**显式暴露、可告警、可追溯**。禁止的是"静默降级"，不是"局部处理"。

---

## 25. Fund Lifecycle

### 25.1 生命周期状态

| 状态 | 说明 |
|---|---|
| `NORMAL` | 正常运行 |
| `SUSPENDED_SUBSCRIPTION` | 暂停申购 |
| `LIQUIDATED` | 清盘 |
| `MERGED` | 合并 |
| `TRANSFORMED` | 转型 |

> **生命周期状态描述"基金处于什么状态"，不直接决定"能否买入"**——后者由 `Investment Eligibility` 表达（§18.1）。

### 25.2 生命周期事件的时点属性

清盘公告的**发布时刻**是 `available_at`，清盘**生效日**是 `effective_at`。回测判断某基金在 `T` 时点的状态，依据 `available_at ≤ T` 的最新记录。

### 25.3 转型的连锁影响

基金转型（`TRANSFORMED`）会同时触发三项变更，且三者都必须 PIT：

```
Fund Classification 变更
        ↓
Peer Group 变更（§7.4）
        ↓
Fund Benchmark 变更（§8.4）
```

回测跨越转型时点时，转型前后必须使用各自当时的分类、分组与基准。

### 25.4 清盘基金的处理

> **历史回测中不得因基金当前已清盘就删除其历史数据。** 这是幸存者偏差的最常见来源（§26.2）。

---

## 26. Bias Control

### 26.1 Look-ahead Bias

**判定标准**（上游 §4.2 ①-PIT）：

> 对任意数据事实，当且仅当 **`available_at ≤ decision_at`** 时才允许参与该次决策。

**为什么不能用"数据日期 ≤ 决策日期"**：

```
基金经理变更   effective_at = 2026-08-20   （生效日）
               available_at = 2026-08-25   （公告发布）
决策日         decision_at  = 2026-08-22

按 effective_at 判断 → 通过 ✗   系统在 8/22 根本不知道这件事
按 available_at 判断 → 拒绝 ✓
```

基金数据中**生效日早于披露日是常态**。按生效日筛选会稳定地使用当时不可能知道的信息，且这类偏差在净值曲线上完全看不出来。

**适用范围**：Factor、Peer Group、Fund Score、Fund Universe、Return Estimate、Correlation、Covariance、Benchmark Mapping、Investment Eligibility——**全部派生量与全部映射关系**。

### 26.2 Survivorship Bias

```
2022-01-01 的 Peer Group 与 Universe
  ✓ 应为：当时实际存在且符合条件的全部基金
  ✗ 不得为：2026 年仍存续的基金中符合条件的那些
```

**为什么会高估收益**：清盘的往往是表现差的基金，剔除它们相当于事先知道哪些会失败并提前避开。

**防范手段**：保留清盘基金完整历史数据、留存每个时点的 Peer Group 与 Universe 快照、回测使用当时快照、组合成分清盘时按事先定义的规则处理退出。

### 26.3 Tradability Bias（交易可得性偏差）

> 第三类偏差，此前未被覆盖。

即使数据 PIT 正确、样本无幸存者偏差，若回测在**基金暂停申购期**照常建仓，结果同样失真——那笔交易在现实中根本无法成交。

**要求**：回测每次建仓/加仓必须校验 `Investment Eligibility`（§18、§21.8）。

### 26.4 声明要求

回测报告必须**显式声明**上述三类偏差的处理方式。未声明的回测结果不得作为决策依据。

---

## 27. Decision Lifecycle & Explainability

### 27.1 Decision Status

一次决策的完整状态机：

| 状态 | 含义 | 后续 |
|---|---|---|
| `PROPOSED` | 系统产出，待复核 | → APPROVED / REJECTED / OVERRIDDEN / EXPIRED |
| `APPROVED` | 原样批准 | → 生成 Rebalancing Recommendation |
| `REJECTED` | 拒绝，本期不调仓 | 终止，记录拒绝理由 |
| `OVERRIDDEN` | 人工修改权重后批准 | → 生成 Recommendation，**必须完整留痕** |
| `EXPIRED` | 超时未处理而失效 | 终止，记录超时原因 |
| `SUPERSEDED` | 被更新的决策取代 | 终止，记录取代关系 |
| `INFEASIBLE` | 优化不可行，未产出决策 | 进入 §20.5 处理流程 |

> **推荐默认 · 2026-08-27**：`PROPOSED` 有效期 = **5 个交易日**，超期转 `EXPIRED`。业务方可改。
>
> **依据**：超过一周未处理的建议，其输入数据（净值、评分、估计）已显著变化，**继续执行等于用过时的决策交易**。重算的成本远低于执行一个失效决策的代价。
>
> **`EXPIRED` 不是失败状态** —— 它表示「该决策的有效期已过」，须在下一决策周期重新产出。区别于 `FAILED`（执行出错）。两者在状态机中不可混用。

### 27.2 Override 的五个留痕字段

> 上游 §7.1.1 已定义，此处引用并明确为验收依据。**缺一不得放行**：

| 字段 | 含义 |
|---|---|
| `original_target_weight` | 系统提出的原始权重 |
| `approved_target_weight` | PM 批准生效的权重 |
| `override_reason` | 修改理由（必填，不接受空值或占位符） |
| `operator` | 操作人身份 |
| `timestamp` | 操作时刻 |

**为什么强制**：若可无记录修改权重，则原则六（可复现）、原则七（可追溯）同时失效，且**回测-实盘偏离度失去意义**——偏离来自策略失效还是人工干预将无法区分。

**Override 频率本身是监控指标**：频繁 override 说明策略与 PM 判断存在系统性分歧，应回到策略设计层排查，而非持续以人工修正掩盖。

### 27.3 完整审计链

> 上游原则七要求"任一持仓可回溯到原始数据"。完整链条为：

```
Approved Investment Decision
      ↓  （含 Human Review 记录：Status + Override 五字段）
Proposed Investment Decision
      ↓
Post-Optimization Risk（⑦-R）
      ↓
Optimization Run（输入 · 求解状态 · 输出 · 诊断）
      ↓
Constraint Set + Risk Budget + Objective
      ↓
Return Estimate + Covariance / Correlation
      ↓
Fund Universe（+ Eligibility Rules 版本）
      ↓
Fund Score（+ 五个子分 + Scoring 版本）
      ↓
Peer Group（+ Classification 版本）
      ↓
Factor（+ Metric 版本）
      ↓
Data Snapshot（available_at / effective_at / version）
      ↓
Raw Data
```

> **Human Review 环节必须在链上**——否则无法回答"系统算出来 10%，为什么最后是 7%"。

### 27.4 输出等级：评分不等于买卖建议

```
Analysis → Score → Screening → Candidate → Portfolio
```

**严禁**把 `Score = 90` 直接解释为 `应该购买`。系统定位为 **Investment Decision Support**，不是 **Autonomous Investment Advisor**。

### 27.5 可解释性的四个必答问题

任一最终权重必须能回答（上游原则十二）：

| # | 问题 | 依据 |
|---|---|---|
| 1 | 为什么进入 Universe | Eligibility Rules 通过项 + Fund Score |
| 2 | 为什么被选中 | Return Estimate + 风险特征 + 相关性 |
| 3 | 为什么是这个权重 | 目标/权重规则 + 约束集 + 风险预算 + 约束是否 binding |
| 4 | 承担了什么风险 | TRC、集中度、类别暴露（⑦-R） |

### 27.6 禁止的表述

```
✗  AI 认为该基金很好
✗  模型认为该基金值得买
✗  综合评估结果为推荐
✗  显著优于基准（在 08-backtest 定义统计检验之前，见 §22.2）
```

---
## 28. Rebalancing

### 28.1 触发类型与重算范围

按上游 §4.2 ⑩-T，**再平衡触发 ≠ 必然重算整条链路**：

| 触发类型 | 条件 | 重算范围 |
|---|---|---|
| **Periodic** | 调仓周期到期 | Full Pipeline：Factor → Score → Universe → ⑤ → ⑥ → ⑦ |
| **Drift** | 实际权重偏离目标超阈值 | ⑤ → ⑥ → ⑦（Universe 与 Score 不变） |
| **Eligibility Event** | 成分基金失去可投资性 | Universe → ⑤ → ⑥ → ⑦ |
| **Constraint Breach** | 触碰约束上限 | ⑥ → ⑦（仅重新求解） |

**为什么分级**：全链路重跑代价高，且会在无必要时改变基金池，引入非预期换手。权重漂移只需重新优化，不应顺带换掉一批基金。

### 28.2 调仓决策的成本收益判据

> 没有这条规则，理论最优组合会产生大量无意义的微小交易。

**核心判据**：

```
建议调仓  ⟺  预期改善  >  交易成本  +  最小改善阈值
```

**四个阈值**（全部可配置，构成 `Rebalance Rule Version`）：

| 阈值 | 作用 |
|---|---|
| **Weight Drift Threshold** | 单只基金权重偏离超过此值才触发 Drift 类型再平衡 |
| **Minimum Trade Threshold** | 单笔调整低于此值不执行——避免产生成本高于收益的碎片交易 |
| **Turnover Threshold** | 单次调仓总换手上限，超过则需人工确认 |
| **Cost-Benefit Threshold** | 预期改善需超过成本的倍数才建议调仓 |

`<TBD-P1-19: 四个阈值的具体取值待组合管理与投研确认>`

### 28.3 调仓建议的输出

`Rebalancing Recommendation` 至少包含：目标权重、当前权重、权重偏离、买卖清单、预计换手率、预计交易成本、成本收益判据的计算结果、触发类型与重算范围。

### 28.4 可投资性对调仓的约束

调仓建议必须尊重 `Investment Eligibility`（§18.2）：

- `HOLD_ONLY` 的基金**不得出现在买入清单**中，但可出现在卖出清单
- `NOT_TRADABLE` 的基金既不可买也不可卖，其持仓视为冻结，需在组合风险分析中单独标注
- 因可投资性限制而无法达成目标权重时，必须**显式报告差异**，不得静默用其他基金补足

### 28.5 触发条件必须可回测

触发条件与对应的重算范围必须**事先定义**，不得由人工临时决定，也不得在运行时动态调整重算深度。

---

## 29. Output Requirements

### 29.1 基金级输出视图

| 视图 | 内容 | Stage |
|---|---|---|
| **Fund Overview** | 代码、名称、分类、Evaluation Profile、成立日、规模、费率、经理及任职时间、Lifecycle Status、**Investment Eligibility** | ① |
| **Fund Performance** | 各周期收益、累计收益、超额收益、Rolling Return（**交易日口径，年化 252**）<br/>**另附日历口径收益**——仅供与基金公司公布数据核对，不参与任何计算（§9.2.1） | ② |
| **Fund Risk** | Volatility、Downside Vol、MaxDD、Drawdown/Recovery Duration、VaR、CVaR | ② |
| **Risk-adjusted Performance** | Sharpe、Sortino、Calmar、Alpha、Beta、IR、TE、**四象限定位** | ② |
| **Stability** | Win Rate、R²、Skewness、Kurtosis、各 Rolling 序列 | ② |
| **Score** | 综合评分 + 五个子分 + 各指标贡献 + **Data Completeness** + **Peer Group 信息** | ③ |
| **Ranking** | Peer Group 内排名、分位、Tier、排名变化趋势 | ③ |
| **Screening Result** | 是否进入 Universe、通过/未通过条件明细 | ④ |
| **Portfolio Role** | 目标权重、风险贡献、类别角色 | ⑦-R |
| **Backtest** | 所属策略的历史表现 | ⑧ |

### 29.2 组合级输出视图

| 视图 | 内容 |
|---|---|
| **Portfolio Composition** | **三态并列**：`Target Portfolio`（目标权重）· `Pending Execution`（已交付未回报）· `Actual Portfolio`（实际权重）+ 权重偏离。回报延迟时 `Actual` 标注待确认，不得以 `Target` 冒充（上游 §4.2 ⑨-S） |
| **Portfolio Risk** | 组合波动率、MRC/TRC、集中度、类别暴露、Risk Budget 达成情况 |
| **Constraint Compliance** | 各约束满足情况、哪些约束 binding、Risk Alert Level |
| **Rebalancing Recommendation** | §28.3 全部内容 |
| **Decision Trace** | 完整决策快照与全部版本号（§33.4） |

### 29.3 每个输出必须携带的元信息

`decision_at`、`data_as_of`、Strategy Version（八项组成）、Data Quality Status、Data Completeness、Decision Status（组合级输出）。

---

## 30. Out of Scope

### 30.1 ML / AI 相关

ML 基金收益预测、AI 基金推荐、LLM 自动生成投资决策、AI 自动调整组合、强化学习、深度学习、自动新闻情绪交易。

**理由**：第一阶段先建立完全可解释的量化基线，否则无法判断复杂方法是否带来增量，失效时也无法回退。

### 30.2 交易执行相关

自动交易执行、券商交易接口、自动下单、**日内 / 高频交易策略**、实时交易策略。

**理由**：平台产出决策，不产出执行；平台按日频运行，不构建实时行情基础设施（上游 §6.2）。

### 30.3 与上游的一致性

本章与上游 §6.2 / §6.2.1 完全一致，未新增排除项，亦未放宽任何排除项。

---

## 31. Future Extensions

| 阶段 | 内容 |
|---|---|
| **Phase 2** | Portfolio Optimization 高级目标（Risk Parity、Minimum CVaR）、Factor Model、Advanced Risk Model |
| **Phase 3** | ML Return Prediction、Regime Detection、ML Ranking |
| **Phase 4** | LLM Research Assistant、研报分析、经理访谈分析、公告/新闻分析 |

### 31.1 扩展路径不预设单一插入点

按上游 §6.2.1（v2.2 修订），第一阶段**保留 ML 插入点，但不预设 ML 未来只作用于某一个环节**。可能的插入位置包括 `Return Estimate`、`Factor`、`Fund Score`（ML Ranking）、`Risk / Correlation`（ML Risk Model）以及全链路条件层（Regime Detection）。

**共同约束**：无论插入哪一点，都必须作为既有 Stage 的**增强项**接入，不得新增绕过主干的旁路，且必须保留一条不依赖 ML 的量化基线路径作为对照与回退。

---

## 32. Non-functional Business Constraints

| 约束 | 要求 |
|---|---|
| **Explainability** | 所有评分、筛选与权重可拆解到指标与规则（§27.5） |
| **Reproducibility** | 相同数据版本 + 相同 Strategy Version → **必然**相同结果 |
| **Auditability** | 支持 §27.3 的完整审计链，含 Human Review 环节 |
| **Configurability** | 评分指标与权重、标准化方式、Preference Direction、分层阈值、筛选条件、组合约束、风险预算、告警阈值、调仓阈值、Benchmark 映射——全部可配置，**严禁硬编码**；配置变更必须版本化并留痕 |
| **Historical Consistency** | 历史回测严格按 `available_at ≤ decision_at` 计算（§26.1） |

---

## 33. Acceptance Criteria

> 采用 Given / When / Then 形式，使 `01-product/04-functional-requirements` 可直接继承为测试用例。

### 33.1 指标与周期

```
AC-1  Given  基金成立不足 3 年
      When   计算 3Y 相关 Factor
      Then   结果 = UNAVAILABLE
      And    该 Factor 不参与 Fund Score 计算
      And    不进行任何数据填充（均值/零/同类值）
      And    该基金的 Data Completeness 相应下降并随评分呈现

AC-2  Given  某 Analysis Period 已配置为 Trading-day Period
      When   计算该周期指标
      Then   使用交易日计数而非自然日
      And    年化因子与配置声明一致
```

### 33.2 Benchmark

```
AC-3  Given  基金官方业绩比较基准为「沪深300×80% + 中债综合×20%」
      When   确定该基金的 Fund Benchmark
      Then   按优先级 2 保留两个 Component 及其权重
      And    不得简化为单一指数
      And    记录 effective_at / available_at / source / mapping_rule_version

AC-4  Given  在 decision_at 下无法确定有效 Benchmark
      When   计算 Alpha / Beta / IR / TE / 超额收益 / Relative Performance Score
      Then   全部标记为 UNAVAILABLE
      And    不使用任何未经声明的替代 Benchmark

AC-5  Given  基金于 2024-06-01 转型且公告于 2024-05-20 发布
      When   回测在 2024-05-25 计算该基金超额收益
      Then   使用转型前的 Benchmark（因 effective_at > decision_at）
      And    2024-06-01 之后使用转型后的 Benchmark
```

### 33.3 Peer Group 与评分

```
AC-6  Given  计算某基金的 Sharpe 分位得分
      When   执行标准化
      Then   分位在该基金的 Peer Group 内计算
      And    Peer Group 的构成不依赖 Fund Score 或 Fund Universe
      And    Peer Group 按 available_at ≤ decision_at 的分类版本确定

AC-7  Given  某 Factor 的 Preference Direction 为 TARGET_RANGE（如 Beta）
      When   将其转换为分数
      Then   使用该 Evaluation Profile 定义的目标区间转换规则
      And    不套用单调的「越高/越低越好」

AC-8  Given  被动型与主动型基金同时计算 Tracking Error 得分
      When   执行标准化
      Then   被动型按 LOWER_IS_BETTER
      And    主动型按其 Evaluation Profile 声明的方向
```

### 33.4 决策与可解释性

```
AC-9  Given  组合中 Fund A 的目标权重 = 12%
      When   用户查询该权重的解释
      Then   系统展示：
             ① 进入 Universe 的原因（通过的 Eligibility 条件 + Score）
             ② 被选中的原因（Return Estimate + 风险特征 + 相关性）
             ③ 权重为 12% 的原因（目标/权重规则 + 哪些约束 binding + 风险预算）
             ④ 承担的风险（TRC + 集中度 + 类别暴露）

AC-10 Given  PM 将系统提出的 12% 修改为 7%
      When   提交复核结果
      Then   Decision Status = OVERRIDDEN
      And    记录 original_target_weight=12% / approved_target_weight=7%
      And    记录 override_reason（非空且非占位符）/ operator / timestamp
      And    五字段缺任一项时拒绝放行

AC-11 Given  一次已完成的历史决策
      When   请求重建该决策
      Then   快照包含：Metric / Peer Group / Eligibility / Scoring /
             Return Estimate / Risk Model / Portfolio Rule / Rebalance Rule /
             Benchmark 九类版本号
      And    包含 Constraint Set + Risk Budget + Optimization Run + Human Review
      And    以相同版本重跑得到完全一致的结果
```

### 33.5 风险与优化

```
AC-12 Given  约束集互相冲突导致优化无解
      When   执行 Portfolio Optimization
      Then   Decision Status = INFEASIBLE
      And    不产出 Proposed Investment Decision
      And    不自动放松任何约束
      And    上报进入 Human Review，记录不可行原因

AC-13 Given  策略配置了「组合波动率 ≤ 15%」
      When   执行优化
      Then   该约束作为事前约束进入优化问题
      And    Post-Optimization Risk 校验实际 σ_p 是否满足

AC-14 Given  策略配置了最大回撤限制
      Then   该限制作为事后监控指标
      And    若需事前控制，必须已定义可计算的代理约束（情景/模拟/代理指标）
```

### 33.6 回测

```
AC-15 Given  回测在 T 时点执行决策
      When   读取任何数据
      Then   全部满足 available_at ≤ T
      And    同一 effective_at 多版本时取 version 序号最大的合格版本

AC-16 Given  某基金在 2023 年清盘
      When   回测 2022 年的 Peer Group 与 Universe
      Then   该基金包含在内
      And    使用当时留存的快照，而非用当前数据重新推算

AC-17 Given  某基金在 T 时点为 HOLD_ONLY（暂停申购）
      When   回测在 T 时点生成建仓/加仓指令
      Then   该基金不出现在买入清单
      And    已有持仓不被强制清仓

AC-18 Given  策略完成 In-Sample 参数选择
      When   进入 Out-of-Sample 验证
      Then   Parameter Freeze 时点已记录并纳入 Strategy Version
      And    OOS 结果不用于反向调参
      And    若据 OOS 修改规则，则升 Strategy Version 并重新划分 IS/OOS

AC-19 Given  回测计算组合收益
      When   扣除成本
      Then   扣除申购费/赎回费/买卖价差/冲击成本
      And    不扣除管理费与托管费（已含于基金净值）

AC-20 Given  回测完成
      When   生成对比报告
      Then   同时呈现 Strategy / Portfolio Benchmark / Equal Weight Baseline 三方
      And    在 08-backtest 定义统计检验前，不使用「显著优于」表述
```

### 33.7 再平衡

```
AC-21 Given  Rebalance Trigger 类型为 Drift
      When   执行 Strategy Re-evaluation
      Then   重算范围为 ⑤ → ⑥ → ⑦
      And    Fund Universe 与 Fund Score 不重算

AC-22 Given  某基金的建议调整量低于 Minimum Trade Threshold
      When   生成 Rebalancing Recommendation
      Then   该笔调整不执行
      And    在报告中说明被过滤的调整及原因

AC-23 Given  预期改善未超过「交易成本 + 最小改善阈值」
      When   评估是否调仓
      Then   建议不调仓
      And    输出成本收益判据的计算过程
```

### 33.8 数据质量

```
AC-24 Given  1000 只基金中 1 只的规模数据为 INVALID
      When   执行当期决策流程
      Then   仅该基金相关条件标记 UNAVAILABLE（Fund-level）
      And    其余 999 只基金正常计算
      And    整个决策周期不被阻断

AC-25 Given  全市场净值数据未到位（Global-level INVALID）
      When   执行当期决策流程
      Then   阻断整个决策周期
      And    告警并要求人工确认后方可继续

AC-26 Given  某数据项状态为 WARNING
      When   参与计算
      Then   允许继续计算
      And    结果携带质量标记并向上传递至最终输出
```

### 33.9 系统定位

```
AC-27 Given  某基金 Fund Score = 90
      When   系统输出该基金信息
      Then   不出现「应该购买」「推荐买入」等表述
      And    输出严格区分 Analysis / Score / Screening / Candidate / Portfolio 五级
```

---

## 34. Business Decision Register

> 关键业务决策的集中登记处。已定的决策在此固化，未定的在 §35 追踪。

| # | 决策事项 | 决策 | 责任方 | 日期 | 版本 |
|---|---|---|---|---|---|
| 1 | 第一阶段是否引入 ML / AI | **否** | 产品 | 2026-08-24 | 上游 v2.0 |
| 2 | Portfolio Optimization 是否属第一阶段 | **是**（Stage ⑦ 核心） | 产品 | 2026-08-24 | 上游 v2.0 |
| 3 | 目标用户定位 | **研究工具使用者**，非 C 端投顾对象 | 产品 | 2026-08-24 | 本文 v1.0 |
| 4 | PIT 判定标准 | **`available_at ≤ decision_at`** | 产品 | 2026-08-24 | 上游 v2.1 |
| 5 | Score 标准化方式 | **Percentile Rank / Peer Group 内排名** | 投研 | 2026-08-24 | 本文 v1.0 |
| 6 | Fund Score 是否为 Universe 必需 | **可选**（三种构成策略见 §17.2） | 产品 | 2026-08-24 | 上游 v2.1 |
| 7 | Peer Group 是否可依赖 Score | **否**（避免循环依赖） | 产品 | 2026-08-25 | 上游 v2.2 |
| 8 | Benchmark 确定方式 | **五级优先级算法**（§8.2） | 投研 | 2026-08-25 | 上游 v2.2 |
| 9 | Composite Benchmark 是否可简化 | **否**，必须保留 Component 与权重 | 投研 | 2026-08-25 | 上游 v2.2 |
| 10 | Score 能否用于权重生成 | **可以**，作为确定性权重规则；**不可**作为收益估计 | 产品 | 2026-08-25 | 本文 v2.0 |
| 11 | 最大回撤能否作事前约束 | **默认否**，为事后监控；如需事前须定义代理约束 | 投研 | 2026-08-25 | 本文 v2.0 |
| 12 | 管理费是否在回测中扣除 | **否**，已含于基金净值 | 投研 | 2026-08-25 | 本文 v2.0 |
| 13 | 回测是否必须含 Equal Weight 基线 | **是**（三方对比） | 投研 | 2026-08-25 | 本文 v2.0 |
| 14 | Walk-forward 是否第一阶段必须 | **是** | 投研 | 2026-08-25 | 本文 v2.0 |
| 15 | Investment Eligibility 是否独立于 Lifecycle | **是**，必须分离 | 产品 | 2026-08-25 | 上游 v2.2 |
| 16 | WARNING 状态能否参与计算 | **能**，仅 INVALID 触发阻断 | 产品 | 2026-08-25 | 本文 v2.0 |
| 17 | Win Rate 默认统计周期 | **月度** | 投研 | 2026-08-25 | 本文 v2.0 |
| 18 | R² 是否进入 SCORING | **否**，仅 DISPLAY + SCREENING | 投研 | 2026-08-25 | 本文 v2.0 |
| 19 | 长期指标权重是否须逐项高于短期 | **否**，由 Strategy Version 配置 | 投研 | 2026-08-25 | 本文 v2.0 |
| 20 | 基金规模上限是否在业务层设定 | **否**，为 Strategy-specific Capacity Rule | 投研 | 2026-08-25 | 本文 v2.0 |
| **21** | **分析周期口径与年化因子**（原 P0-1） | **全部 Trading-day Period，年化因子 252**；展示层另附日历口径收益仅供核对 | 投研 | 2026-08-25 | 本文 v2.1 |
| **22** | **Fund Tier 分层方式**（原 P0-2） | **按 Peer Group 内分位**：5 / 20 / 50 / 80；Tier 必须与组内绝对水平同屏展示 | 投研 | 2026-08-25 | 本文 v2.1 |
| **23** | **四类 Evaluation Profile 的指标集合与方向**（原 P0-3） | **采纳 §5.2.1 建议矩阵**；被动型 Alpha 不入评分、费率高权重；债券型回撤最高权重 | 投研 | 2026-08-25 | 本文 v2.1 |
| **24** | **"显著优于"的判定方法**（原 P0-4） | **三重证据**：IR 阈值 + 跑赢概率 + Block Bootstrap 区间下界为正；不用 t 检验 | 投研 | 2026-08-25 | 本文 v2.1 |
| **26** | **「显著优于」追加第四层经济显著性** | 四层判定：统计显著性 + 效应量（含 ΔSharpe）+ 稳健性 + **经济显著性**；统计显著不代表投资意义显著 | 投研 + 治理 | 2026-08-27 | 本文 v2.4 §22.2.2 |
| **30** | **因子权重由检验产出，第一版有效因子内等权** | 禁止先拍权重再找因子佐证；检验未产出前 Score 不可投产 | 投研 | 2026-08-27 | 本文 v2.7 §5.2.1.1 |
| **29** | **Peer Group 最小样本量 = 30** | 不足时不产出横截面派生量（标 `INSUFFICIENT_SAMPLE`），原始因子值不受影响；判定基数是 `n_effective` | 投研 | 2026-08-27 | 本文 v2.6 §7.3.1 |
| **28** | **费率定义升级为费用包含关系** | 每种费用显式声明 `included_in_nav`，`included_in_backtest` 由其推导；`UNKNOWN` 时不扣除但必须披露 | 投研 + 数据 | 2026-08-27 | 本文 v2.5 §21.7.1 |
| **27** | **新增第 10 类 `Policy Version`** | Evaluation / Ranking / Classification / Estimation / Validation 五个 Policy 归为一类，而非逐项追加为第 10、11、12 项 | 架构 + 业务 | 2026-08-27 | 本文 v2.4 §23.1.1 |
| **25** | 评分权重何时确定 | **待 04-factor 有效性检验产出后再定**，不在业务需求阶段拍板 | 投研 | 2026-08-25 | 本文 v2.1 |

---

## 35. 待确认项（按优先级与阻塞关系）

### 35.1 P0 —— 已全部关闭 ✅

| 原编号 | 事项 | 决策 | 定案位置 |
|---|---|---|---|
| ~~P0-1~~ | 分析周期口径与年化规则 | 全部 Trading-day，年化 252 | §9.2.1 |
| ~~P0-2~~ | Fund Tier 分层方式与阈值 | 分位分层 5 / 20 / 50 / 80 | §16.3.1 |
| ~~P0-3~~ | 四类画像的指标集合与方向 | 采纳建议矩阵 | §5.2.1 |
| ~~P0-4~~ | "显著优于"的判定方法 | 三重证据 | §22.2.1 |

> **Benchmark Mapping 未成为 P0** —— §8.2 的五级优先级算法使其可确定性执行，仅优先级 4 的分类默认映射需配置（见 P1-20）。

**下游文档已解除阻塞**：`04-factor` 与 `05-fund-evaluation` 可以开始编写；`08-backtest` 的验收标准已确定判定方法，仅余阈值取值（P1-21）。

### 35.2 P1 —— 下游文档编写中必须确认

| # | 事项 | 位置 | 相关文档 | 责任方 |
|---|---|---|---|---|
| ~~P1-1~~ | ~~Peer Group 最小样本量阈值~~ —— **已定案 30**（§7.3.1）；剩余为实证验证（`OPEN-9`/`OPEN-10`） | §7.3.1 | — | ✅ 已定案 2026-08-27 |
| ~~P1-2~~ | ~~Peer Group 与 Evaluation Profile 不一致时的处理~~ —— **已定案**：同组多 Profile 时按 Profile 拆分子排名，不产出跨 Profile 统一排名 | — | — | ✅ 已定案 2026-08-27 |
| P1-3 | 各策略的 Portfolio Benchmark 构成比例 | §8.6 | `07` | 组合管理 |
| P1-4 | 四象限默认坐标轴与分界方式 | §12.3 | `05` | 投研 |
| ~~P1-5~~ | ~~Win Rate 默认基准（绝对/相对）~~ —— **已定案**：Win Rate 默认基准 = 绝对正收益 | — | — | ✅ 已定案 2026-08-27 |
| ~~P1-6~~ | ~~Skewness / Kurtosis 是否纳入 SCORING~~ —— **已定案**：Skewness / Kurtosis 第一阶段不纳入 SCORING | — | — | ✅ 已定案 2026-08-27 |
| P1-7 | 各策略类型的容量规则（规模上限） | §17.4 | `07` | 投研 |
| P1-8 | ETF 流动性各项准入阈值 | §18.4 | `07` | 投研 |
| P1-9 | Manager Change 后的观察期长度 | §18.6 | `07` | 投研 |
| P1-10 | 各组合策略的上线顺序与默认参数 | §19.4 | `07` | 投研 |
| ~~P1-11~~ | ~~是否需要事前回撤约束及代理方法~~ —— **已定案**：不设事前回撤约束，用 CVaR 替代；回撤保持事后监控 | — | — | ✅ 已定案 2026-08-27 |
| P1-12 | 各项 Risk Budget 的预算值 | §20.3 | `07` | 投研 + 风控 |
| P1-13 | 风险指标的 WARNING / CRITICAL 阈值 | §20.4 | `07` | 投研 + 风控 |
| P1-14 | IS/OOS 划分比例与 Walk-forward 窗口步长 | §21.5 | `08` | 投研 |
| ~~P1-15~~ | ~~销售服务费按份额类别的处理~~ —— **已定案**：升级为「费用包含关系」，由 `included_in_nav` 推导（§21.7.1）；剩余为数据核实（`OPEN-19`/`OPEN-20`） | §21.7.1 | — | ✅ 已定案 2026-08-27 |
| P1-16 | 默认回测区间与调仓频率 | §21.9 | `08` | 投研 |
| P1-17 | 各 Approval Gate 的具体阈值 | §22.4 | `13-governance` | 治理 + 投研 |
| P1-18 | PROPOSED 决策的有效期 | §27.1 | `07` | 组合管理 |
| P1-19 | 四个调仓阈值的取值 | §28.2 | `07` | 组合管理 |
| P1-20 | Fund Classification Default Benchmark 映射表（优先级 4） | §8.2 | `05` | 投研 |
| P1-21 | 三重证据的阈值：IR 下限、跑赢概率下限、Bootstrap 重采样次数与置信水平 | §22.2.1 | `08` | 投研 |
| P1-22 | Active Equity / Bond / Hybrid 的 Beta 目标区间 | §5.2.1 | `06` | 投研 |
| ~~P1-23~~ | ~~各 Evaluation Profile 内部的具体权重分配~~ —— **已定案流程**：有效因子内等权，权重由检验产出（§5.2.1.1）；剩余为检验阈值（`OPEN-11`~`OPEN-13`） | §5.2.1.1 | — | ✅ 已定案 2026-08-27 |
| P1-24 | Fund Tier 是否追加绝对门槛（未达标不得进 A+/A） | §16.3.1 | `06` | 投研 |

> **P1-23 的定序说明（已落实）**：权重由 `04-factor` 的因子有效性检验结果决定而非事先拍板 —— 该定序已于 2026-08-27 在 §5.2.1.1 正式定案，第一版方案为**有效因子内等权**。**关闭的是流程，取值仍待检验产出** —— 但这不再是 TBD，因为取值不需要人来决定，它是检验的输出。

---

## 36. 变更记录

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v2.8** | 2026-08-27 | **第二批定案（4 项）**。`P1-2` 同组多 Evaluation Profile 时**按 Profile 拆分子排名**（与 §16.2 的 MAR 一致性同源：横截面比较要求被比较的量出自同一口径）；`P1-5` Win Rate 默认基准 = **绝对正收益**；`P1-6` Skewness / Kurtosis **不纳入 SCORING**（方向未定的量不应赋权重）；`P1-11` **不设事前回撤约束**，改用 CVaR —— 最大回撤是路径依赖的极值统计量、非权重的凸函数，三个代理方案各有不可解的问题；并明确**用 CVaR 约束不等于控制住了回撤**，报告不得如此表述。详见 `TBD-resolution-2.md` §3.1 | `TBD-resolution-2.md` v1.0 |
| **v2.7** | 2026-08-27 | **`TBD-P1-23` 关闭**。新增 §5.2.1.1 —— 定案的是**流程而非取值**：完整链路（Quality → Effectiveness → Selection → Redundancy → Optimization → Profile Weight），第一版为**有效因子内等权**；明确「有效因子内等权」与「未经检验就等权」数值可能相同但性质相反，**检验未产出前 Score 不可投产**；检验须满足 PIT 且须划分 IS/OOS。§34 新增决策登记 1 条。详见 `TBD-resolution.md` Policy ⑥ | `01-product-overview.md` v2.6 |
| **v2.6** | 2026-08-27 | **`TBD-P1-1` 关闭**。§7.3 最小样本量定为 **30**，新增 §7.3.1 —— 不足时**降级而非报错**（不产出横截面派生量，原始因子值照常）；判定基数是 `n_effective` 而非 `peer_group_size`；三处（标准化 / 排名 / 分层）配置来源唯一。§34 新增决策登记 1 条。详见 `TBD-resolution.md` Policy ⑤ | `01-product-overview.md` v2.6 |
| **v2.5** | 2026-08-27 | **`TBD-P1-15` 关闭**。新增 §21.7.1 —— 从「逐项讨论扣不扣」升级为「每种费用显式声明 `included_in_nav`」，`included_in_backtest = NOT included_in_nav AND 交易时发生`；给出六项费用的包含关系清单与六个必备元数据字段；明确 `UNKNOWN` 时不扣除**是不保守的方向**，选它是因为反方向会造成重复扣费这一双重错误。§34 新增决策登记 1 条。详见 `TBD-resolution.md` Policy ⑩ | `01-product-overview.md` v2.6 |
| **v2.4** | 2026-08-27 | **待决项定案版**。①新增 §22.2.2 —— 「显著优于」在原三重证据之上**追加第四层经济显著性**，并把 ΔSharpe 并入效应量层；明确第四层不替代前三层（经济显著但统计不显著同样不能称「优于」）。②新增 §23.1.1 —— **新增第 10 类 `Policy Version`**（evaluation / ranking / classification / estimation / validation 五子项），取代此前各域各自登记的「某某 Policy 不在九项之内」缺口；决策快照须同时引用 Strategy Version 与 Policy Version。③§23.1 标题「八个组成部分」修正为「九个」（原为笔误，列表本就是九项）。④§34 新增决策登记 2 条。详见 `TBD-resolution.md` Policy ⑧⑨ | `01-product-overview.md` v2.6 |
| **v2.3** | 2026-08-25 | **组合状态同步版**。§29.2 Portfolio Composition 明确 `Target` / `Pending Execution` / `Actual` 三态并列呈现，回报延迟时不得以 Target 冒充 Actual。同步上游 v2.4 的 §4.2 ⑨-S | `01-product-overview.md` **v2.4** |
| **v2.2** | 2026-08-25 | **路径修正版**。将正文中沿用自业务侧草案的 6 个虚构文档名映射到实际目录：`03-functional-requirements`→`01-product/04-functional-requirements`、`04-data-requirements`→`03-data`、`05-metric-specification`→`04-factor`、`06-scoring-model`→`05-fund-evaluation`、`07-portfolio-rules`→`06-portfolio`、`08-backtesting-specification`→`08-backtest`；重写文末下游声明 | `01-product-overview.md` v2.4 |
| **v2.1** | 2026-08-25 | **P0 决策落案版**。四项 P0 全部关闭：①§9.2.1 分析周期统一为 Trading-day Period + 年化 252，展示层另附日历口径收益（含混合口径导致 Sharpe 错配 1.20 倍的论证）；②§16.3.1 Fund Tier 按 Peer Group 分位分层 5/20/50/80，并强制 Tier 与组内绝对水平同屏展示；③§5.2.1 写入四类 Evaluation Profile 的基础指标集与差异矩阵，含三处反直觉说明（被动型 Alpha 不入评分、被动型费率高权重、债券型回撤最高权重）；④§22.2.1 "显著优于"采用三重证据取代 t 检验（含 t 检验双向失真的论证）。附带：费率补入 §14.2 Factor Usage Matrix；§29.1 增加日历口径收益的展示要求；§34 新增 5 条决策登记；§35.1 P0 全部关闭，新增 P1-21 至 P1-24 | `01-product-overview.md` v2.4 |
| **v2.0** | 2026-08-25 | **概念闭合版**。①新增 §0.2 Stage 正式定义表并澄清 Concept/Output 层级（⑦-R 是 Concept，不存在 ⑦-O）；②新增 §7 `Peer Group` 并禁止其依赖 Score（消除循环依赖）；③§8 按五级优先级重写 Benchmark Selection，拆分 Fund/Portfolio Benchmark，Composite 不得简化；④新增 §14 Factor Usage Matrix 与各 Factor 的 `Preference Direction`，修正"所有风险指标越低越好"；⑤§19.2 区分确定性权重规则与优化目标，解决 Score Weight 冲突；⑥§20.2 修正最大回撤不可作事前约束；⑦§20.3 Risk Budget 六要素；⑧§20.5 优化不可行的人工处理闭环；⑨新增 §18 `Investment Eligibility` 并与 Lifecycle 分离；⑩§21 新增 Rebalance Decision Point、IS/OOS/Walk-forward、三方对比基线、成本组成（管理费不重复扣除）；⑪§23.1 Strategy Version 九项组成与版本号语义；⑫§24.4 数据质量三级阻断粒度，澄清 WARNING 可继续；⑬§27 Decision Status 状态机、Override 五字段、完整审计链含 Human Review；⑭新增 §28 Rebalancing 与成本收益判据；⑮§33 验收改 Given/When/Then 共 27 条；⑯新增 §34 Business Decision Register；⑰§35 TBD 按 P0/P1 分级并标注阻塞文档 | `01-product-overview.md` **v2.2** |
| v1.0 | 2026-08-24 | 初始版本 | `01-product-overview.md` v2.1 |

**变更规则**：上游升版本时必须复查本文档并更新依赖声明；与上游冲突以上游为准；本文档业务需求变更须同步通知下游。

---

> **本文档的下游**：`docs/01-product/03-user-stories.md`、`docs/01-product/04-functional-requirements.md`、`docs/01-product/05-non-functional-requirements.md`，以及 `docs/02-architecture` 起的全部技术域文档。
> 编写这些文档前，请先阅读 `docs/01-product/01-product-overview.md`（v2.4）与本文档，特别是 §0 上游对齐说明、§7 Peer Group、§14 Factor Usage Matrix 与 §35 的待确认项。
