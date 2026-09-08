# 因子定义 · Factor Definition

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：② Factor
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§10–§13
> 本域上游：docs/04-factor/01-factor-overview.md、02-factor-taxonomy.md（v1.0）
>
> **文档版本**：v1.4 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **每一个 Factor 到底是什么意思？如何计算？边界条件是什么？**

这是 `04-factor` 域**最重要**的文档。下游的评分、筛选、组合与回测全部建立在此处的定义之上。

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 计算管线、批次、失败处理 | `04-factor-calculation` |
| 标准化方法与横截面处理 | `05-factor-normalization` |
| 版本管理 | `06-factor-versioning` |
| 校验规则 | `07-factor-validation` |
| 评分权重 | `05-fund-evaluation` |

### 1.3 全域统一前提

> 以下前提适用于本文档全部 Factor，各 Factor 定义中不再重复。

| 前提 | 取值 | 来源 |
|---|---|---|
| **收益计算基础** | **复权净值** | `03-data/05-data-normalization` §5 |
| **周期口径** | **Trading-day Period** | `02-business-requirements` §9.2.1 |
| **年化因子** | **252** | 同上 |
| **起止规则** | `(start, end]`，不含起始日 | 同上 |
| **非交易日** | 端点落非交易日时向前取最近交易日 | 同上 |
| **收益频率** | **日频简单收益** `r_t = NAV_t / NAV_{t−1} − 1`（不用对数收益，理由见来源文档） | `04-factor/04-factor-calculation` §5.1 |
| **PIT 约束** | 全部输入满足 `available_at ≤ decision_at` | 上游 §4.2 ①-PIT |
| **缺失处理** | 输入不足 → Factor = `UNAVAILABLE`，**不填充** | `02-business-requirements` §9.4 |

---

## 2. 两个共同依赖：Risk-free Rate 与 MAR

> **v1.1 重写**（上游 v2.5 §5.5）。此前本节把两者并列为"待确认项"，未区分性质——这会诱导下游按"数值相同即可共用"实现。

### 2.0 两者性质不同

| | **Risk-free Rate** | **MAR** |
|---|---|---|
| 本质 | **市场数据**（观测所得） | **评价标准**（配置而来） |
| 归属 | `03-data`（§10 实体） | `05-fund-evaluation`（Evaluation Policy） |
| 解析依据 | `available_at ≤ decision_at` 的最大 `version` | `Evaluation Policy Version` + `Effective Date` |
| 变更含义 | 市场变了（数据更新） | **我们改变了评价标准**（策略变更，须版本治理） |
| 消费方 | `F-RAP-001` Sharpe、`F-REL-002` Alpha、`F-REL-003` Beta（Beta 的依赖是形式上的，见 §F-REL-002/003） | `F-RISK-002`、`F-RAP-002` 及其 Rolling 变体 |

> **即使某个 `Evaluation Policy` 声明 `MAR = R_f` 使两者数值完全相同，也必须在数据模型、配置模型与计算语义上保持独立**（上游 §5.5.1）。

### 2.1 Risk-free Rate

**本文档的使用方式**：全部相关 Factor 的公式中以 `R_f` 表示，**不假定具体取值**。

| # | 使用约束 |
|---|---|
| 1 | **`R_f` 不得作为常量写死在 Factor 计算逻辑中**（上游 §11.2 术语表） |
| 2 | 取值须按 `(currency, tenor)` 解析——币种取自基金的计价币种，`tenor` 由 `Evaluation Policy` 或平台默认指定 |
| 3 | **必须满足 PIT**：取 `available_at ≤ decision_at` 中 `version` 最大者（`03-data/02-data-domain-model` §10.3） |
| 4 | **年化口径必须与 `R_p`、`σ_p` 一致**（252 交易日）。口径统一的责任在数据层，Factor 层消费的应已是统一口径的值（`03-data/01-data-source` §3.1.5.3） |
| 5 | **缺失时 `UNAVAILABLE`，不得默认为 0** |

#### 2.1.1 期限匹配规则（v1.2 定案）

> **定案 · 2026-08-27**：`TBD-FD-1` 关闭。见 `03-data/01-data-source` §3.1.5.5、`TBD-resolution.md` Policy ①。

**`tenor` 由 Factor 的 Evaluation Period 决定**，不由平台默认指定：

| Factor 周期 | 匹配 Tenor |
|---|---|
| 1M | `1M` |
| 3M | `3M` |
| 6M | `6M` |
| 1Y | `1Y` |
| 3Y | `3Y` |
| 5Y | `5Y` |

> **因此同一只基金的 1Y Sharpe 与 3Y Sharpe 使用的是不同的 `R_f`** —— 这不是不一致，而是期限匹配的必然结果。用同一个 `R_f` 评价不同周期的收益，在利率曲线陡峭时会系统性扭曲短周期或长周期指标之一。

**`currency`** 取自基金计价币种 `fund_share_class.base_currency`。

#### 2.1.2 `R_f` 的正确用法：逐期超额，不是年化相减 ⚠️

> **这是本节最容易实现错的地方。**

```
① 取与收益序列【同频率】的无风险收益
      月频收益序列 → R_f 换算为月度无风险收益 Rf_t
② 逐期计算超额收益
      excess_t = R_t − Rf_t
③ 对超额收益序列做年化与风险调整
      Sharpe = annualize(mean(excess)) / annualize_vol(R)
```

**错误做法**：

```
❌ Sharpe = (年化收益 − 年化 R_f) / 年化波动率，R_f 取窗口末值
   → 忽略了窗口内 R_f 的变化
   → 在利率变动期产生系统性偏差
```

> **两种算法在利率平稳期几乎无差异**，这正是它危险的原因 —— 错误实现能通过大部分测试，只在利率快速变动的区间才显现，而那恰恰是风险调整指标最需要准确的时候。

**换算规则由 `quotation_basis` 决定，不得默认单利或复利**（`03-data/01-data-source` §3.1.5.5）。

#### 2.1.3 `rate_source_quality` 必须随因子结果落库

| Quality | 含义 | 对因子的影响 |
|---|---|---|
| `EXACT` | 精确 tenor 可得 | 无 |
| **`INTERPOLATED`** | 由相邻 tenor 插值 | 因子值含插值误差，**跨基金比较时须同档** |
| `UNAVAILABLE` | 该币种曲线不可得 | 因子 `UNAVAILABLE` |

> **同一 Peer Group 内混用 `EXACT` 与 `INTERPOLATED` 的 Sharpe 仍可比** —— 插值误差远小于基金间的真实差异。但**须在因子结果中可查**，否则无法在异常排查时区分「这只基金确实差」与「它的 `R_f` 是插出来的」。

`<OPEN-2: CNY 国债收益率曲线的具体数据源与发布时点，待数据侧确认>`
> **已定案 · 2026-08-27**：相邻 tenor 采用**线性插值**。
>
> **依据**：①第一阶段只需 1M / 3M / 6M / 1Y / 3Y / 5Y 六个标准期限，**插值仅发生在少数缺失点**；②在如此稀疏的网格上，样条相对线性的差异**远小于 `R_f` 本身的估计噪声与其修订幅度**；③线性插值**不会过冲** —— 样条在端点附近可能产生高于两端点的插值结果，而利率曲线的插值结果高于其两侧观测值是没有经济含义的。
>
> **须落 `rate_source_quality = INTERPOLATED`**（`03-data/01-data-source` §3.1.5.5），使插值来源在因子结果中可查。

### 2.2 MAR（Minimum Acceptable Return）

> `Sortino Ratio` 与 `Downside Volatility` 需要一个"可接受收益下限"。**它是评价标准，不是市场数据。**

| 常见取法 | 说明 |
|---|---|
| `MAR = 0` | 只惩罚绝对亏损 |
| `MAR = R_f` | 惩罚跑输无风险利率 |
| `MAR = 目标收益` | 惩罚跑输特定目标 |

**三者结果差异显著**，不可混用。

#### 2.2.1 本域消费的 MAR Policy 契约

> **`MAR` 的定义与治理属 `05-fund-evaluation`，本域只消费。** 以下是本域计算 Factor 时所需的最小契约——不是 MAR 的完整设计。

| 契约项 | 说明 |
|---|---|
| **`fund_category`** | MAR 可按基金类别差异化（股票型与货币型的"可接受"显然不同） |
| **`currency`** | MAR 随计价币种不同 |
| **`mar_value`** | 阈值，年化口径须与 Factor 侧一致 |
| **`effective_date`** | 该取值的生效日 |
| **`evaluation_policy_version`** | 所属评价政策版本 |

**解析键**：`(fund_category, currency, decision_at, evaluation_policy_version)` → `mar_value`

> 统一由 **Threshold Resolver** 解析，Factor 计算逻辑不直接读取配置表（`02-architecture/01-system-architecture` §13）。

#### 2.2.2 MAR 使两个 Factor 的值不再唯一 ⚠️

> **这是 MAR 属评价配置的直接后果，必须落实到 Factor Result 结构。**

```
R_f 是市场数据 → 全平台唯一
    → (Fund, F-RAP-001, 1Y, 2026-06-30) 确定唯一 Sharpe 值

MAR 是评价配置 → 随 Evaluation Policy 不同
    → (Fund, F-RAP-002, 1Y, 2026-06-30) 不足以确定唯一 Sortino 值
    → 必须再加上 Evaluation Policy Version
```

| 受影响的 Factor | 说明 |
|---|---|
| `F-RISK-002` Downside Volatility | 直接依赖 MAR |
| `F-RAP-002` Sortino Ratio | 分子分母均依赖 MAR |
| 上述两者的 Rolling 变体 | 同上 |

**约束**：这两个 Factor 的 Factor Result **必须携带 `Evaluation Policy Version`**，否则无法解释、无法复现（`08-factor-output` §2.5）。依赖 `R_f` 的 Factor 不受此约束。

#### 2.2.3 同一 Peer Group 内必须使用同一 MAR

> **否则组内 `Sortino` 不可比，分位排名失去意义**（上游 §5.5.3）。

```
Peer Group 基于 Fund Classification 构建
MAR       按 Fund Category 配置

若两者粒度不一致 → 同组内出现多个 MAR
    → 基金 A 的 Sortino 用 MAR=0，基金 B 用 MAR=2%
    → 两者的 Sortino 不在同一标尺上，却被放在一起排分位
```

该约束由 `05-fund-evaluation` 在构建 `Evaluation Policy` 时保证；本域在标准化前**应校验同组 MAR 一致**，不一致时该 Factor 在该组 `UNAVAILABLE`（`05-factor-normalization` §5）。

#### 2.2.4 MAR Policy 定案：默认 `ZERO` + Policy Override（v1.2）

> **定案 · 2026-08-27**：`TBD-FD-2` 关闭。见 `05-fund-evaluation/01-fund-evaluation` §16、`TBD-resolution.md` Policy ②。

```
MAR Policy
├── ZERO       ← 第一版默认
├── RISK_FREE
└── CUSTOM
```

| 模式 | `MAR_t` |
|---|---|
| `ZERO` | `0` |
| `RISK_FREE` | `Rf_t`（按 §2.1.1 的期限匹配，逐期取值） |
| `CUSTOM` | 配置值，按 `fund_category × currency` |

**选 `ZERO` 作为第一版默认的五条理由**：

| # | 理由 |
|---|---|
| 1 | **最容易解释** —— 「只惩罚绝对亏损」是投资者的直觉 |
| 2 | **不依赖外部数据** —— 不引入新的数据源与可得性问题 |
| 3 | **不产生额外 PIT 问题** —— 常数没有时点 |
| 4 | **跨资产类别一致** —— 股票型与债券型用同一标尺 |
| 5 | 避免 `Sortino → Risk-free → Currency → Tenor` 的耦合链 |

> **为什么不默认 `MAR = R_f`**：理论上更合理（惩罚跑输无风险利率），但会使 Sortino 与 `R_f` 的曲线选择耦合 —— 不同计价币种的基金 MAR 随之不同，且 `R_f` 的插值档位会传导到 Sortino。第一版不值得引入这层复杂度。**这是一个可随时切换的 Policy 配置，不是不可逆的建模决定。**

**关键区分：`ZERO` 不等于「缺失时补 0」**

| 状态 | 含义 | 处置 |
|---|---|---|
| `mar_policy = ZERO` | **已配置**，明确选择了 0 | 正常计算 |
| `mar_policy` 未配置 | **缺失** | 依赖 MAR 的 Factor **`UNAVAILABLE`**，**不得默认为 0** |

> **两者数值上都是 0，但语义完全相反** —— 前者是有人决定用 0，后者是没人配过。若把后者当前者，一个配置遗漏会静默产出看起来正常的 Sortino，而无人知道它用的标尺从未被确认过。

**MAR 与收益序列同频率**：若 MAR 以年化表示，须按 `quotation_basis` 换算（同 §2.1.2 对 `R_f` 的要求）。

**MAR 变更升 `evaluation_policy` 版本，不升 Factor Version**（`06-factor-versioning` §4.3）。

> **已定案 · 2026-08-27**：`CUSTOM` MAR 的配置粒度**保持 `fund_category × currency`，不再细分**。
>
> **依据**：①第一版默认 `ZERO`，`CUSTOM` 暂无使用场景，为一个未启用的模式设计更细粒度是过早优化；②**细化粒度会与 §16.2 的 Peer Group 对齐约束直接冲突** —— 该约束要求同一 Peer Group 内解析出同一 MAR，而 Peer Group 由 Fund Classification 构建，粒度细于它必然导致组内多 MAR，进而使 Sortino 不可比。
>
> **`FN-4` 是同一约束的因子侧表述**：MAR 粒度必须**等于或粗于** Peer Group 粒度。

> **本文档的处理**：公式中一律以 `MAR` 表示，具体取值由 Evaluation Policy 解析。此前 v1.0 的「默认假设 `MAR = 0`」曾被撤销（因为那是因子文档的自行假定）；现在的 `ZERO` 默认**是业务定案的 Policy 取值**，两者性质不同 —— 前者写在因子文档里且不可追溯，后者写在 Evaluation Policy 里且随版本可查。

---

## 3. 定义模板

每个核心 Factor 按以下结构定义；紧凑条目覆盖其中标 ★ 的必需项。

```
★ Factor ID · Name · Category
★ Definition          业务定义
★ Business Meaning    在基金筛选中的含义
★ Input Data          依赖的 Dataset
★ Formula             数学定义
  Parameters          可配置参数
★ Time Window         支持的窗口
★ Calculation Frequency
★ Unit
★ Direction           Preference Direction
★ Minimum Observations
★ Missing Data Rule
  Benchmark Dependency
  PIT Requirement
  Boundary Conditions  边界条件
  Normalization        标准化提示
★ Version
  Example
```

---

## 4. 符号约定

| 符号 | 含义 |
|---|---|
| `NAV_t` | t 日的**复权**净值 |
| `r_t` | t 日的日收益率 |
| `N` | 窗口内的有效观测数（交易日） |
| `R_p` | 组合/基金的**年化**收益率 |
| `R_b` | 基准的**年化**收益率 |
| `R_f` | **年化**无风险利率（见 §2.1） |
| `r_b,t` | t 日的基准日收益率 |
| `σ_p` | 年化波动率 |
| `MAR` | 最低可接受收益（见 §2.2） |
| `A` | 年化因子 = **252** |

---

## 5. RET · Performance Factors

### F-RET-001 · Annualized Return

**Category**：RET（Primary）

**Definition**
窗口区间内基金的**年化几何收益率**。

**Business Meaning**
衡量基金在该周期内的收益水平，是最基础的表现指标。**但不得单独用于评价**——必须与风险指标联合使用（`02-business-requirements` §10.2）。

**Input Data**
`Fund NAV / Adjusted NAV`（`03-data` Dataset）

**Formula**

```
总收益   R_total = NAV_end / NAV_start − 1
年化收益 R_p = (1 + R_total)^(A / N) − 1
```

其中 `N` 为窗口内交易日数，`A = 252`。

**Time Window**：1M · 3M · 6M · 1Y · 3Y · 5Y

**Calculation Frequency**：Daily

**Unit**：百分比

**Direction**：`HIGHER_IS_BETTER`

**Minimum Observations**：不低于窗口理论交易日数的 **90%**。

**Missing Data Rule**
窗口内有效观测数低于最小要求 → `UNAVAILABLE`。**区间端点净值缺失时，按 §4 的非交易日规则向前取最近交易日；若仍缺失则 `UNAVAILABLE`。**

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| `NAV_start ≤ 0` | `INVALID`——净值不应为零或负（`03-data/06-data-validation` §5.1） |
| 窗口短于 1 年（1M/3M/6M） | **仍做年化**，但须标注短周期年化的放大效应 |
| 基金成立时长不足窗口 | `UNAVAILABLE`，**不得**用成立至今年化冒充 |

> **短周期年化的警示**：1M 收益年化会把单月波动放大约 12 倍。该 Factor 在 1M/3M 窗口下**建议仅用于 DISPLAY**，不进入 SCORING（`02-business-requirements` §9.1：长期指标参考价值更高）。

**PIT Requirement**：窗口内全部 NAV 满足 `available_at ≤ decision_at`

**Version**：由 `Metric Version` 管理（`06-factor-versioning`）

**Example**

```
窗口 1Y，N = 244 交易日
NAV_start = 1.2000，NAV_end = 1.3800
R_total = 0.1500
R_p = (1.15)^(252/244) − 1 ≈ 0.1551  →  15.51%
```

---

### F-RET-002 ~ F-RET-004 · 紧凑条目

| 项 | **F-RET-002 Cumulative Return** | **F-RET-003 Period Return** | **F-RET-004 Rolling Return** |
|---|---|---|---|
| **Definition** | 窗口内累计收益，不年化 | 指定自然区间的收益 | 滚动窗口内的收益序列 |
| **Business Meaning** | 直观展示总收益 | 对齐官方披露口径的展示 | 观察收益的持续性 |
| **Input** | Adjusted NAV | Adjusted NAV | Adjusted NAV |
| **Formula** | `NAV_end / NAV_start − 1` | 同上，区间按配置 | 对每个 t：`NAV_t / NAV_{t−W} − 1` |
| **Window** | 1M~5Y | 按配置 | **Rolling 12M**（W = 252） |
| **Frequency** | Daily | Daily | Daily |
| **Unit** | 百分比 | 百分比 | 百分比**序列** |
| **Direction** | `HIGHER_IS_BETTER` | `HIGHER_IS_BETTER` | `HIGHER_IS_BETTER` |
| **Min Obs** | 窗口理论交易日数的 90% | 窗口理论交易日数的 90% | 每个滚动点需完整 W 个观测 |
| **Missing Rule** | 同 F-RET-001 | 同上 | 观测不足的滚动点标记 `UNAVAILABLE`，**不中断整个序列** |
| **Usage** | D·SR·B | D·SC·SR·B | D·SC·SR·B |

> **`F-RET-003` 的特殊用途**：它是 `02-business-requirements` §9.2.1 要求的**日历口径收益**的载体——**仅供与基金公司公布数据核对，不参与评分、筛选、组合构建或回测计算**。

---

## 6. RISK · Risk Factors

### F-RISK-001 · Volatility

**Category**：RISK（Primary）

**Definition**
基金日收益率的**年化标准差**，衡量收益的波动程度。

**Business Meaning**
最基础的风险度量。波动率高意味着收益不确定性大，但**不区分上涨波动与下跌波动**——这是它与 `Downside Volatility` 的核心区别。

**Input Data**：`Fund NAV / Adjusted NAV`

**Formula**

```
日收益  r_t = NAV_t / NAV_{t−1} − 1
均值    r̄ = Σ r_t / N
σ_daily = sqrt( Σ (r_t − r̄)² / (N − 1) )
σ_p     = σ_daily × sqrt(A)
```

> **使用样本标准差（分母 N−1）**，非总体标准差。窗口内观测是样本而非总体。

**Time Window**：3M · 6M · 1Y · 3Y · 5Y（**不支持 1M**）

**Calculation Frequency**：Daily

**Unit**：百分比（年化）

**Direction**：`LOWER_IS_BETTER`

**Minimum Observations**：不低于窗口理论交易日数的 **90%**。

**Missing Data Rule**
- 中间缺失日：**跳过该日收益计算，不插值**（`03-data/05-data-normalization` §4.4）
- 有效观测数不足 → `UNAVAILABLE`

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| `N < 2` | `UNAVAILABLE`——无法计算标准差 |
| 全部收益相同（σ = 0） | 返回 0，但标记 `WARNING`——可能是数据问题（如净值长期未更新） |
| 存在极端收益 | **不自动剔除**——异常判定属 `03-data-quality`；本层如实计算 |

> **为什么不支持 1M 窗口**：约 21 个交易日的样本标准差置信区间极宽，年化后误差被放大 √252 倍，统计意义不足（`02-factor-taxonomy` §7 W-1）。

**PIT Requirement**：窗口内全部 NAV 满足 `available_at ≤ decision_at`

**Usage**：`DISPLAY · SCORING · SCREENING · BACKTEST`

> Portfolio 与 `07-return-risk` 不消费该 Factor。它们直接基于 PIT 收益序列独立计算波动率与协方差，避免评分链影响风险估计链。

**Example**

```
窗口 1Y，N = 244
σ_daily = 0.0085
σ_p = 0.0085 × sqrt(252) ≈ 0.1349  →  13.49%
```

---

### F-RISK-003 · Maximum Drawdown

**Category**：RISK（Primary）

**Definition**
窗口内净值从**历史峰值**到后续**谷值**的最大跌幅。

**Business Meaning**
**第一阶段的核心风险指标**（`02-business-requirements` §11.2）。它比波动率更贴近投资者的实际体验——投资者感受到的是"亏了多少"，不是"波动了多少"。

**Input Data**：`Fund NAV / Adjusted NAV`

**Formula**

```
对窗口内每个 t：
    peak_t = max( NAV_1, ..., NAV_t )        运行中的历史峰值
    dd_t   = (peak_t − NAV_t) / peak_t       该点回撤

MDD = max( dd_t )   for t in window
```

**路径依赖性**：MDD 依赖净值的**完整路径**，不能由起止点或统计矩推出。这是它与波动率的根本区别，也是它**不能作为组合优化的事前约束**的原因（`02-business-requirements` §20.2）。

**Time Window**：3M · 6M · 1Y · 3Y · 5Y

**Calculation Frequency**：Daily

**Unit**：百分比（**正值表示跌幅**）

**Direction**：`LOWER_IS_BETTER`

**Minimum Observations**：不低于窗口理论交易日数的 **90%**。

**Missing Data Rule**
中间缺失日**跳过**，但须标注——缺失可能恰好掩盖了真实的谷值，导致 MDD 被低估。缺失比例超阈值 → `WARNING`。

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| 窗口内净值单调上升 | MDD = 0，**正常结果**，非异常 |
| `N < 2` | `UNAVAILABLE` |
| 峰值出现在窗口首日 | 正常——峰值可以是起点 |

> **一个常见误解**：MDD = 0 不代表"无风险"，只代表**在该窗口内**未出现回撤。换窗口可能完全不同。因此 MDD 必须与窗口一同呈现。

**联合呈现要求**

> `Maximum Drawdown` 必须与 `Drawdown Duration`、`Recovery Duration` **联合呈现**（`02-business-requirements` §11.2）。

```
回撤 20% 但 3 个月恢复
回撤 20% 但 3 年未恢复
        ↑ 完全不同的风险
```

**Usage**：`DISPLAY · SCORING · SCREENING · BACKTEST`

---

### F-RISK-002 / 004 / 005 / 006 / 007 · 紧凑条目

| 项 | **F-RISK-002 Downside Volatility** | **F-RISK-004 VaR 95%** | **F-RISK-005 CVaR 95%** |
|---|---|---|---|
| **Definition** | 只计负向偏离的年化标准差 | 95% 置信下的单日潜在损失 | 超过 VaR 后的尾部平均损失 |
| **Business Meaning** | 投资者厌恶的是下跌而非上涨波动 | 常规风险下的损失边界 | **尾部风险**——VaR 之外的平均损失 |
| **Input** | Adjusted NAV（+ MAR） | Adjusted NAV | Adjusted NAV |
| **Formula** | `sqrt( Σ min(r_t − MAR/A, 0)² / (N−1) ) × sqrt(A)` | 历史模拟法：`−percentile(r, 5%)` | `−mean( r_t \| r_t ≤ percentile(r, 5%) )` |
| **Window** | 3M~5Y | 3M~5Y | 3M~5Y |
| **Unit** | 百分比（年化） | 百分比（**正值表示损失**） | 百分比（正值表示损失） |
| **Direction** | `LOWER_IS_BETTER` | `LOWER_IS_BETTER` | `LOWER_IS_BETTER` |
| **Min Obs** | 窗口理论交易日数的 90% | **≥100**（5% 分位需足够样本） | **≥100** |
| **Missing Rule** | 同 Volatility | 同上 | 同上 |
| **边界条件** | 窗口内无负偏离 → 返回 0 并标 `WARNING` | 采用历史模拟法，**不假设正态分布** | 尾部样本数 < 5 → `WARNING`（估计不稳定） |
| **Usage** | D·SC·SR·B | D·SC·SR·B | D·SC·SR·B |

> **`F-RISK-002` 依赖 `MAR`，其值随 `Evaluation Policy` 变化**——Factor Result 必须携带 `Evaluation Policy Version`（§2.2.2）。`F-RISK-004` / `005` 不依赖 MAR，不受此约束。

> **分母用 `N−1` 而非负偏离个数**：这是标准 Sortino 框架的取法。用负偏离个数会使下行波动率被系统性高估，且不同基金间不可比。

> **VaR 与 CVaR 必须成对使用**（`02-business-requirements` §11.2）——单看 VaR 会低估尾部风险。

| 项 | **F-RISK-006 Drawdown Duration** | **F-RISK-007 Recovery Duration** |
|---|---|---|
| **Definition** | 处于回撤状态的最长持续交易日数 | 从最大回撤谷底恢复至前高所需交易日数 |
| **Business Meaning** | 衡量"套牢多久" | 衡量修复能力 |
| **Formula** | 最长的连续 `NAV_t < peak_t` 区间长度 | 从 MDD 谷值点到首次 `NAV_t ≥ peak` 的交易日数 |
| **Window** | 3M~5Y | 3M~5Y |
| **Unit** | 交易日数 | 交易日数 |
| **Direction** | `LOWER_IS_BETTER` | `LOWER_IS_BETTER` |
| **边界条件** | 无回撤 → 0 | **窗口末仍未恢复 → 标记"未恢复"，不返回数值** |
| **Usage** | D·SR·B | D·SR·B |

> **`F-RISK-007` 的关键边界**：若窗口结束时仍未恢复，**不得**返回窗口长度作为恢复期——那会把"仍在亏损"误表达为"已恢复且用时较长"。应返回特殊状态"未恢复"，并附当前已持续天数。

---
## 7. RAP · Risk-adjusted Performance Factors

### F-RAP-001 · Sharpe Ratio

**Category**：RAP（Primary）｜Secondary：RET · RISK

**Definition**
单位总风险所获得的超额收益。

**Business Meaning**
回答"这个风险值不值得"。**在基金筛选中，两只基金收益相同时，Sharpe 高者意味着用更小的波动取得了同样的收益。**

**Input Data**：`Fund NAV / Adjusted NAV` + **无风险利率 `R_f`（见 §2.1）**

**Formula**

```
R_p = 年化收益率（F-RET-001）
σ_p = 年化波动率（F-RISK-001）

Sharpe = (R_p − R_f) / σ_p
```

> **口径一致性要求**：`R_p`、`R_f`、`σ_p` 三者必须采用**相同的年化基准**（本系统统一为 252 交易日）。若收益按 365 日历日年化而波动率按 252 交易日年化，Sharpe 会产生约 `√(365/252) ≈ 1.20` 倍的系统性错配（`02-business-requirements` §9.2.1）。

**Parameters**

| 参数 | 说明 |
|---|---|
| `R_f` | 无风险利率 —— 按 `(计价币种, 评价周期对应 tenor)` 解析，须满足 PIT，**不得写死为常量**；用法见 §2.1.1~§2.1.3 |

**Time Window**：6M · 1Y · 3Y · 5Y（**不支持 1M / 3M**）

**Calculation Frequency**：Daily

**Unit**：比率（无量纲）

**Direction**：`HIGHER_IS_BETTER`

**Minimum Observations**：不低于窗口理论交易日数的 **90%**。

**Missing Data Rule**
`R_p` 或 `σ_p` 任一为 `UNAVAILABLE` → Sharpe = `UNAVAILABLE`；`R_f` 缺失 → `UNAVAILABLE`（**不得默认 `R_f = 0`**）。

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| **`σ_p = 0`** | **`UNAVAILABLE`** —— 除零。零波动通常意味着数据问题（净值未更新），不应返回无穷大 |
| `σ_p` 极小但非零 | 正常计算，但标记 `WARNING` —— Sharpe 会被放大至失真 |
| `R_p < R_f` | Sharpe 为负，**正常结果**，不做截断 |

> **不得对 `σ_p = 0` 返回 0 或极大值**。返回 0 会让该基金在评分中排到最差；返回极大值会让它排到最好。两者都是错的——正确处理是 `UNAVAILABLE`。

**Usage**：`DISPLAY · SCORING · SCREENING · BACKTEST`

**Example**

```
R_p = 15.51%，R_f = 2.20%，σ_p = 13.49%
Sharpe = (0.1551 − 0.0220) / 0.1349 ≈ 0.987
```

---

### F-RAP-002 / F-RAP-003 · 紧凑条目

| 项 | **F-RAP-002 Sortino Ratio** | **F-RAP-003 Calmar Ratio** |
|---|---|---|
| **Definition** | 单位**下行风险**的超额收益 | 收益与最大回撤之比 |
| **Business Meaning** | 比 Sharpe 更贴近投资者感受——只惩罚下跌波动 | 衡量"收益/回撤"效率，回答"承受这样的最大亏损换来多少收益" |
| **Input** | Adjusted NAV + `MAR` | Adjusted NAV |
| **Formula** | `(R_p − MAR) / σ_d`，`σ_d` = F-RISK-002 | `R_p / \|MDD\|`，`MDD` = F-RISK-003 |
| **Window** | 6M~5Y | 6M~5Y |
| **Unit** | 比率 | 比率 |
| **Direction** | `HIGHER_IS_BETTER` | `HIGHER_IS_BETTER` |
| **Min Obs** | 窗口理论交易日数的 90% | 窗口理论交易日数的 90% |
| **Missing Rule** | `σ_d` 或 `MAR` 不可得 → `UNAVAILABLE` | `MDD` 不可得 → `UNAVAILABLE` |
| **边界条件** | **`σ_d = 0`（窗口内无负偏离）→ `UNAVAILABLE`** 并标注"窗口内无下行"；不返回无穷大 | **`MDD = 0`（窗口内无回撤）→ `UNAVAILABLE`** 并标注"窗口内无回撤"；不返回无穷大 |
| **Usage** | D·SC·SR·B | D·SC·SR·B |

> **`F-RAP-002` 依赖 `MAR`，`F-RAP-003` 不依赖**——因此同为 RAP 类，Sortino 的 Factor Result 必须携带 `Evaluation Policy Version` 而 Calmar 不必（§2.2.2）。`MAR` 须由 Threshold Resolver 按 `(fund_category, currency, decision_at, evaluation_policy_version)` 解析，**不得写死**。

> **两者的除零情形是"好消息"，但仍须 `UNAVAILABLE`**：`σ_d = 0` 意味着从未下跌，`MDD = 0` 意味着从未回撤——这在业务上是优秀表现，但在数学上无法计算比率。返回极大值会让该基金在分位排名中占据榜首，形成**"没跌过 = 最好"的错误激励**，且短窗口下极易出现。正确处理是标记不可用并在展示层说明原因。

---

## 8. STAB · Stability Factors

### F-STAB-005 · Rolling Sharpe

**Category**：STAB（Primary）｜Secondary：RAP

**Definition**
在**滚动窗口**内逐点计算 Sharpe，产出**时间序列**而非单一标量。

**Business Meaning**
回答核心问题：**"基金优秀的表现是长期持续存在，还是只发生在某一个阶段？"**（`02-business-requirements` §13.1）

单点 Sharpe 高可能来自一次押注成功；Rolling Sharpe 的**序列形态**才能区分持续能力与运气。

**Input Data**：`Fund NAV / Adjusted NAV` + `R_f`

**Formula**

```
对窗口内每个时点 t（t ≥ W）：
    Sharpe_t = Sharpe( r_{t−W+1} ... r_t )    使用 F-RAP-001 的公式

输出：{ Sharpe_t } 时间序列
```

其中 `W` = 滚动窗口长度 = **252 交易日（12M）**。

**Parameters**

| 参数 | 默认 | 说明 |
|---|---|---|
| `W` | **252**（12M） | 滚动窗口长度 |
| 步长 | 1 交易日 | 每日产出一个滚动点 |

**Time Window**：Rolling 12M

**Calculation Frequency**：Daily

**Unit**：比率**序列**

**Direction**：`HIGHER_IS_BETTER`（序列值）；其**波动**为 `LOWER_IS_BETTER`

**Minimum Observations**
每个滚动点需完整 `W=252` 个观测；序列本身需至少 **12 个有效滚动点**才具分析意义。

**Missing Data Rule**
- 某滚动点观测不足 → **该点** `UNAVAILABLE`，**不中断整个序列**
- 序列中 `UNAVAILABLE` 比例超阈值 → 整个序列标 `WARNING`

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| 基金历史长度 < `W` | 整个序列 `UNAVAILABLE` |
| 历史长度 = `W` | 仅产出 1 个点——**标注序列长度不足** |
| 某点 `σ_p = 0` | 该点 `UNAVAILABLE`（同 F-RAP-001） |

**输出结构的特殊性**

> **Rolling 类 Factor 的输出是序列，不是标量**。下游消费时需明确使用哪个统计量：

| 统计量 | 含义 |
|---|---|
| 序列最新值 | 当前状态 |
| 序列均值 | 平均水平 |
| **序列标准差** | **稳定性——这是 STAB 分类的核心用途** |
| 序列最小值 | 最差阶段表现 |
| 正值占比 | 多少时间处于正 Sharpe |

> **已定案 · 2026-08-27**：评分使用 Rolling 序列的**均值**与**标准差**两个统计量，二者分别进入 **Stability 子分**。
>
> **依据**：Rolling 因子的价值在于**稳定性**而非水平 ——
>
> ```
> 只取 Rolling 序列的末值
>     → 等同于一个普通的非 Rolling 因子
>     → Rolling 计算的全部成本都白付了
>
> 取均值 + 标准差
>     → 均值回答「长期处在什么水平」
>     → 标准差回答「这个水平稳不稳」
> ```
>
> **标准差的 Preference Direction 是 `LOWER_IS_BETTER`** —— Rolling Sharpe 波动大意味着表现依赖特定市场环境。这是 Stability 子分的核心含义。

**Usage**：`DISPLAY · SCORING · SCREENING · BACKTEST`

---

### F-STAB-001 ~ F-STAB-004 / 006 / 007 · 紧凑条目

| 项 | **F-STAB-001 Win Rate** | **F-STAB-002 R²** |
|---|---|---|
| **Definition** | 正收益区间占比 | 收益对基准的线性解释程度 |
| **Business Meaning** | 衡量盈利的频率 | **描述性指标**——高 R² 不代表优秀 |
| **Input** | Adjusted NAV | Adjusted NAV + Benchmark |
| **Formula** | `count(r_period > 0) / count(r_period)` | 回归 `r_p ~ r_b` 的决定系数 |
| **Parameters** | **统计周期：默认月度**（`02-business-requirements` §13.3）；基准可配置为绝对正收益或跑赢 Benchmark | —— |
| **Window** | 6M~5Y | 6M~5Y |
| **Unit** | 百分比 | 比率（0~1） |
| **Direction** | `HIGHER_IS_BETTER` | **`STRATEGY_DEPENDENT`** |
| **Min Obs** | ≥12 个统计周期 | 窗口理论交易日数的 90% |
| **边界条件** | 周期数不足 → `UNAVAILABLE` | Benchmark 不可得 → `UNAVAILABLE`；`Var(r_b) = 0` → `UNAVAILABLE` |
| **Usage** | D·SC·SR·B | **D·SR**（不进 SCORING） |

> **`F-STAB-002` 的方向为什么是 `STRATEGY_DEPENDENT`**：指数型基金 R² 应接近 1（跟踪质量好）；主动型基金 R² 低可能意味着独立选股能力，**也可能意味着风格漂移**。它不构成优劣判断，因此**不进 SCORING**（`02-business-requirements` §13.5）。

| 项 | **F-STAB-003 Skewness** | **F-STAB-004 Kurtosis** |
|---|---|---|
| **Definition** | 收益分布的偏度 | 收益分布的**超额峰度** |
| **Business Meaning** | 正偏=偶有大涨，负偏=偶有大跌 | 高峰度=极端事件更频繁 |
| **Formula** | `Σ(r_t − r̄)³ / (N·σ³)` | `Σ(r_t − r̄)⁴ / (N·σ⁴) − 3` |
| **Window** | 6M~5Y | 6M~5Y |
| **Unit** | 无量纲 | 无量纲 |
| **Direction** | `HIGHER_IS_BETTER` | `LOWER_IS_BETTER` |
| **Min Obs** | **≥120**（高阶矩需大样本） | **≥120** |
| **边界条件** | `σ = 0` → `UNAVAILABLE` | 同左 |
| **Usage** | **D·SR**（不进 SCORING，待 P1-6 确认） | **D·SR**（同左） |

> **`F-STAB-004` 采用超额峰度（减 3）**：正态分布的超额峰度为 0，便于直接判读"比正态更厚尾"。若采用原始峰度，需以 3 为基准判读，容易误读。**此约定必须在下游一致**。

| 项 | **F-STAB-006 Rolling Volatility** | **F-STAB-007 Rolling Maximum Drawdown** |
|---|---|---|
| **Definition** | 滚动窗口内的年化波动率序列 | 滚动窗口内的最大回撤序列 |
| **Formula** | 逐点应用 F-RISK-001 | 逐点应用 F-RISK-003 |
| **Parameters** | `W = 252`，步长 1 交易日 | 同左 |
| **Unit** | 百分比**序列** | 百分比**序列** |
| **Direction** | `LOWER_IS_BETTER` | `LOWER_IS_BETTER` |
| **边界条件** | 同 F-STAB-005 的序列规则 | 同左 |
| **Usage** | D·SC·SR·B | D·SC·SR·B |

---

## 9. REL · Relative Performance Factors

> **本类全部 5 个 Factor 依赖 Benchmark。** Benchmark 不可得时**整类 `UNAVAILABLE`**（`03-data/01-data-source` §5.5）。

### 9.1 共同前提

| 前提 | 说明 |
|---|---|
| **Benchmark 来源** | 按上游 §4.2 ①-B 的五级优先级确定（`03-data/01-data-source` §5） |
| **Composite Benchmark** | 按各 Component 权重加权后再比较，**不得简化为单一指数** |
| **口径一致** | 基准收益与基金收益同交易日历、同年化规则 |
| **指数类型** | 权益 Benchmark 使用 `TOTAL_RETURN`；债券 M1 使用中债综合全价指数 `FULL_PRICE`；Hybrid 保留两类 Component 及权重 |

### F-REL-002 / F-REL-003 · Alpha 与 Beta

> 两者由**同一个回归**产出，因此合并定义。

**Category**：REL（Primary）｜F-REL-002 Secondary：RET

**Definition**
以基金超额收益对基准超额收益做线性回归，截距为 `Alpha`，斜率为 `Beta`。

**Business Meaning**

| Factor | 含义 |
|---|---|
| **Alpha** | 无法由基准解释的收益部分——代表**主动管理能力** |
| **Beta** | 对基准变动的敏感度——代表**系统性风险暴露** |

**Input Data**：`Fund NAV` + `Benchmark Time Series` + `R_f`

**Formula**

```
基金超额日收益   x_t = r_t − R_f/A
基准超额日收益   y_t = r_b,t − R_f/A

回归：x_t = α_daily + β · y_t + ε_t

β = Cov(x, y) / Var(y)
α_daily = x̄ − β · ȳ
Alpha（年化）= α_daily × A
```

> **`R_f/A` 中的 `A` 是年化因子（252）**，且 `R_f` 是**逐期取值**而非窗口末值固定 —— 时变的 `R_f` 下 `R_f,t/A` 逐日不同（§2.1.2）。

#### Beta 对 `R_f` 的依赖是形式上的（v1.2 精确化）

> **此前多处表述为「Beta 依赖 `R_f`」，这在时变 `R_f` 下正确，但会让人高估其敏感度。**

```
若 R_f 在窗口内【恒定】：
    Cov(r − Rf, rb − Rf) / Var(rb − Rf) ≡ Cov(r, rb) / Var(rb)
    → Beta 与 R_f 完全无关（同一常数从两边减去，协方差与方差都不变）

Policy ① 采用【时变的期限匹配曲线】，R_f 不恒定
    → Beta 形式上仍依赖 R_f，但敏感度显著低于 Alpha
```

| Factor | 对 `R_f` 的敏感度 |
|---|---|
| **Sharpe** | **高** —— `R_f` 直接进入分子 |
| **Alpha** | **高** —— `α = x̄ − β·ȳ`，`R_f` 的均值直接平移截距 |
| **Beta** | **低** —— 只有 `R_f` 的**波动**影响它，`R_f` 的水平不影响 |

> **实践含义**：`R_f` 数据源切换或插值档位变化时，Sharpe 与 Alpha 须重新审视，Beta 通常可沿用。但这**不构成放松 Beta 的 `R_f` PIT 约束的理由** —— 敏感度低不等于无关，且放松会让同一回归的 Alpha 与 Beta 用上不同的 `R_f`。

**Time Window**：3M · 6M · 1Y · 3Y · 5Y

**Calculation Frequency**：Daily

**Unit**：Alpha = 百分比（年化）；Beta = 无量纲

**Direction**

| Factor | Direction |
|---|---|
| Alpha | `HIGHER_IS_BETTER` |
| **Beta** | **`TARGET_RANGE`** |

> **Beta 为什么不是单调方向**：`Beta = 0.5` 不必然优于 `1.0`。防御型策略希望低 Beta，市场中性策略希望接近 0，进取型策略可能允许高 Beta。目标区间由 `Evaluation Profile` 与策略目标共同决定（`02-business-requirements` §11.3，`<TBD-P1-22>`）。

**Minimum Observations**：不低于窗口理论交易日数的 **90%**，且不少于 **60 个共同日期配对观测**。

**Missing Data Rule**
Benchmark 或 `R_f` 不可得 → 两者均 `UNAVAILABLE`。基金与基准的**交易日历错位**导致可配对观测不足 → `UNAVAILABLE`。

**Boundary Conditions**

| 情形 | 处理 |
|---|---|
| **`Var(y) = 0`**（基准无波动） | **`UNAVAILABLE`** —— Beta 除零 |
| 可配对观测数不足 | `UNAVAILABLE` |
| 交易日历长期错位 | 计算但标 `WARNING`——相对指标可信度下降（`03-data/05-data-normalization` §8.2） |
| R² 极低 | 正常计算，但 **Alpha 的解释力弱**——建议与 `F-STAB-002` 联合呈现 |

> **Composite Benchmark 被简化的后果**：若把"沪深300×80% + 中债×20%"简化为"沪深300"，该基金的 **Beta 被系统性低估、Alpha 被系统性高估**（`03-data/02-data-domain-model` §7.2）。

**Usage**

| Factor | Usage |
|---|---|
| Alpha | `D·SC·SR·B` |
| Beta | `D·SC·SR·B` |

> **被动型基金的 Alpha 不进入评分**：指数基金的目标是复制指数，出现显著正 Alpha 恰恰说明跟踪偏离。把 Alpha 当正向指标等于奖励跟踪不好的指数基金（`02-business-requirements` §5.2.1）。**该规则在评分方案层实施**（`05-fund-evaluation`），本层照常计算并输出。

---

### F-REL-001 / F-REL-004 / F-REL-005 · 紧凑条目

| 项 | **F-REL-001 Excess Return** | **F-REL-005 Tracking Error** | **F-REL-004 Information Ratio** |
|---|---|---|---|
| **Definition** | 相对基准的超额收益 | 相对基准偏离的年化标准差 | 单位跟踪误差的超额收益 |
| **Business Meaning** | 最直接的相对表现 | 主动偏离的程度 | 主动管理的**效率** |
| **Input** | NAV + Benchmark | NAV + Benchmark | NAV + Benchmark |
| **Formula** | `R_p − R_b` | `std(r_t − r_b,t) × sqrt(A)` | `(R_p − R_b) / TE` |
| **Window** | 3M~5Y | 3M~5Y | 3M~5Y |
| **Unit** | 百分比 | 百分比（年化） | 比率 |
| **Direction** | `HIGHER_IS_BETTER` | **`STRATEGY_DEPENDENT`** | `HIGHER_IS_BETTER` |
| **Min Obs** | 窗口理论交易日数的 90% | 窗口理论交易日数的 90%，且至少 60 个配对观测 | 同左 |
| **Missing Rule** | Benchmark 不可得 → `UNAVAILABLE` | 同左 | 同左 |
| **边界条件** | 交易日历错位 → `WARNING` | 完全复制基准时 TE≈0，正常 | **`TE = 0` → `UNAVAILABLE`**（除零）；TE 极小 → `WARNING`（IR 被放大失真） |
| **Usage** | D·SC·SR·B | D·SC·SR·B | D·SC·SR·B |

> **`F-REL-005` 的方向为什么是 `STRATEGY_DEPENDENT`**：
> - **被动型（Passive Equity）**：`LOWER_IS_BETTER` —— 偏离即失职，是核心考核项
> - **主动型（Active Equity）**：**中性** —— TE 是主动收益的来源；TE=0 的主动基金等于收了主动管理费做指数，须配合 IR 判读
>
> （`02-business-requirements` §11.3、§5.2.1）

> **`F-REL-004` 的 `TE = 0` 边界**：完全复制基准的指数基金 TE 接近 0，此时 IR 分母趋零。**不得返回极大值**——那会让跟踪最紧的指数基金在 IR 排名中占据榜首，而 IR 对被动型本就不适用（`02-factor-taxonomy` §5.5）。

---

## 10. 边界条件汇总

> **本域最容易出错的一类问题：除零与"好消息"的错误编码。**

| Factor | 除零情形 | 业务含义 | **必须的处理** | 错误处理的后果 |
|---|---|---|---|---|
| `F-RAP-001` Sharpe | `σ_p = 0` | 净值无波动（多为数据问题） | `UNAVAILABLE` | 返回极大值 → 排名榜首 |
| `F-RAP-002` Sortino | `σ_d = 0` | **窗口内从未下跌** | `UNAVAILABLE` + 标注 | 返回极大值 → "没跌过=最好" |
| `F-RAP-003` Calmar | `MDD = 0` | **窗口内从未回撤** | `UNAVAILABLE` + 标注 | 同上 |
| `F-REL-003` Beta | `Var(r_b) = 0` | 基准无波动 | `UNAVAILABLE` | 返回 0 或极大值均错误 |
| `F-REL-004` IR | `TE = 0` | **完全复制基准** | `UNAVAILABLE` | 指数基金占据 IR 榜首 |
| `F-STAB-002` R² | `Var(r_b) = 0` | 基准无波动 | `UNAVAILABLE` | —— |
| `F-STAB-003/004` | `σ = 0` | 净值无波动 | `UNAVAILABLE` | —— |

### 10.1 统一原则

| # | 原则 |
|---|---|
| B-1 | **除零一律 `UNAVAILABLE`**，不返回 0、不返回极大值、不做截断 |
| B-2 | 当除零对应"好消息"（从未下跌、从未回撤、完全跟踪）时，**须在输出中标注原因**，供展示层解释 |
| B-3 | 分母极小但非零时**正常计算并标 `WARNING`** —— 结果虽可算但已失真 |
| B-4 | **短窗口下除零概率显著更高**（3M 内无回撤很常见），这是风险与风险调整类不支持 1M 窗口的另一个理由 |

### 10.2 为什么 B-1 如此重要

```
若 Calmar 在 MDD = 0 时返回极大值：
    → 该基金 Calmar 排名第一
    → Risk-Adjusted Score 接近满分
    → 进入 Fund Universe 甚至获得高权重
    → 而它可能只是成立 3 个月、恰好赶上单边上涨

这个错误在净值曲线上完全看不出来。
```

---
## 11. Summary

本文档定义 26 个 Factor 的完整语义。四个要点：

- **两个共同依赖性质不同，不可合并处理** —— **`R_f` 是市场数据**（`03-data` 实体，按 PIT 解析，全平台唯一）；**`MAR` 是评价标准**（`05-fund-evaluation` 配置，按 Evaluation Policy Version 解析）。即使数值相同也必须独立。其直接后果是 **`Sortino` 与 `Downside Volatility` 的值不再由 (Fund, Factor, Window, Date) 唯一确定**，必须携带 `Evaluation Policy Version`；两者取值未确认前相关 Factor 无法投产
- **除零一律 `UNAVAILABLE`** —— 尤其当除零对应"好消息"（从未下跌、从未回撤、完全跟踪）时。返回极大值会让"没跌过 = 最好"，且短窗口下极易出现
- **两个非单调方向** —— `Beta` 是 `TARGET_RANGE`，`Tracking Error` 是 `STRATEGY_DEPENDENT`。不得默认"风险类越低越好"
- **Rolling 类产出序列而非标量** —— 下游需明确使用哪个统计量；其**序列标准差**才是 STAB 分类的核心用途

> **口径一致性是贯穿全篇的隐形要求**：`R_p`、`R_f`、`σ_p` 必须同年化基准，否则 Sharpe 会有 1.20 倍的系统性错配。

---

## 12. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | 波动率使用**样本标准差**（分母 `N−1`） | 窗口内观测是样本而非总体 |
| D-2 | Downside Volatility 分母用 `N−1` 而非负偏离个数 | 用负偏离个数会系统性高估下行波动，且基金间不可比 |
| D-3 | VaR / CVaR 采用**历史模拟法**，不假设正态分布 | 基金收益有肥尾，正态假设会低估尾部风险 |
| D-4 | Kurtosis 采用**超额峰度**（减 3） | 正态基准为 0，便于直接判读厚尾程度 |
| D-5 | **除零一律 `UNAVAILABLE`**，不返回 0 或极大值 | 两种返回都会污染分位排名，且方向相反 |
| D-6 | 除零对应"好消息"时须标注原因 | 供展示层解释"为什么这只基金没有 Calmar" |
| D-7 | `Recovery Duration` 窗口末未恢复时返回"未恢复"状态而非数值 | 返回窗口长度会把"仍在亏损"误表达为"已恢复" |
| D-8 | Rolling 类某点不可用时**不中断整个序列** | 序列的价值在于形态，单点缺失不应作废全部 |
| D-9 | 风险与风险调整类**不支持 1M 窗口** | 21 个观测的统计意义不足；且短窗口下除零概率显著更高 |
| D-10 | `F-RET-003` Period Return 承载日历口径收益 | 满足 `02-business-requirements` §9.2.1 的对外核对需求，且与计算口径隔离 |
| D-11 | 被动型 Alpha 不进评分的规则在**评分层**实施，本层照常计算 | Factor 层保持中立，画像差异属 `05-fund-evaluation` |

---

## 13. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 全部收益基于**复权净值**，按 Trading-day 口径，年化 252 | `02-business-requirements` §9.2.1、`03-data/05-data-normalization` |
| C-2 | 缺失输入 → `UNAVAILABLE`，**严禁以 0 或任何值填充** | `02-business-requirements` §9.4 |
| C-3 | 除零 → `UNAVAILABLE`，不返回 0、极大值或截断值 | 本文档 §10.1 B-1 |
| C-4 | `Beta` = `TARGET_RANGE`，`Tracking Error` = `STRATEGY_DEPENDENT` | `02-business-requirements` §11.3 |
| C-5 | Composite Benchmark 按 Component 加权，不得简化为单一指数 | 上游 §4.2 ①-B |
| C-6 | `R_p`、`R_f`、`σ_p` 必须同年化基准 | 本文档 §7 F-RAP-001 |
| C-7 | `R_f` 缺失时不得默认为 0 | 本文档 §7 |
| C-8 | **`R_f` 与 `MAR` 不得写死为常量**，须由 Threshold Resolver 解析 | 上游 §5.5、`02-architecture/01-system-architecture` §13 |
| C-9 | **依赖 `MAR` 的 Factor（`F-RISK-002`、`F-RAP-002` 及 Rolling 变体）其 Factor Result 必须携带 `Evaluation Policy Version`** | 上游 §5.5.2 |
| C-10 | 同一 `Peer Group` 内必须使用同一 `MAR` | 上游 §5.5.3 |
| C-11 | 本域**不得自行填充 `MAR` 的具体数值** | 上游 §14 TBD-19 |
| C-8 | Factor 层不做多因子合成 | 上游 §4.2 ② |

---

## 14. TBD

### 14.1 阻塞投产的项

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~FD-1~~ | ~~无风险利率的币种、期限与来源~~ —— **已定案**：按计价币种选曲线、按评价周期匹配 tenor（§2.1.1）；剩余为数据源与插值方法（`OPEN-2`/`OPEN-4`） | — | ✅ 已定案 2026-08-27 |
| ~~FD-2~~ | ~~MAR 的取值与按 `Fund Category` 的差异化配置~~ —— **已定案**：三模式 `ZERO` / `RISK_FREE` / `CUSTOM`，第一版默认 `ZERO`（§2.2.4）；剩余为 `CUSTOM` 粒度（`OPEN-5`） | — | ✅ 已定案 2026-08-27 |
| **FD-8** | **`MAR` 配置粒度与 `Peer Group` 划分粒度的对齐**——不对齐则同组 Sortino 不可比 | `F-RISK-002` / `F-RAP-002` 的分位排名 | `05-fund-evaluation` |
| ~~DN-3~~ | ~~复权方向~~ —— 后复权（`BACKWARD`）+ 原始净值双轨 | — | ✅ 2026-08-27 |
| ~~DN-6~~ | ~~Benchmark 类型~~ —— 权益 `TOTAL_RETURN`，债券 M1 `FULL_PRICE` | — | ✅ 2026-09-08 |

### 14.2 参数类

| # | 事项 | 影响 |
|---|---|---|
| ~~FD-3~~ | ~~各 Factor 的最小观测数~~ —— 窗口理论交易日数 90%；回归类至少 60 个配对观测 | ✅ 2026-09-08 |
| ~~FD-4~~ | ~~Rolling 序列的最小滚动点数~~ —— Rolling Sharpe 至少 12 个有效滚动点 | ✅ 2026-09-08 |
| ~~FD-5~~ | ~~评分使用 Rolling 序列的哪个统计量~~ —— **已定案**：评分使用 Rolling 序列的【均值】与【标准差】两个统计量，分别进入 Stability 子分 | ✅ 2026-08-27 |
| ~~FT-3~~ | ~~Beta 的 `TARGET_RANGE` 取值~~ —— Active `[0.85,1.15]`、Passive `[0.98,1.02]`、Bond/Hybrid `[0.90,1.10]` | ✅ 2026-09-08 |

> **FD-1 曾是本域最紧急的缺口，现已关闭**（2026-08-27）：数据源已回补至 `03-data/01-data-source` §3.1.5（v2.1 新增 Dataset、v2.2 补全数据模型、v2.3 定案曲线来源与解析规则）。本域的三个直接消费方（Sharpe / Alpha / Beta）可计算。**剩余的 `OPEN-2`（具体数据源）属接入工作，不阻塞因子定义。**

---

## 15. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/02-business-requirements.md` v2.3（§10–§13 指标体系、§11.3 方向） |
| **数据依赖** | `03-data/02-data-domain-model`（NAV / Benchmark 实体）、`03-data/05-data-normalization`（复权与口径）、`03-data/01-data-source`（Benchmark 来源、**Risk-free Rate 待补**） |
| **本域** | `02-factor-taxonomy`（分类与 Catalog）、`04-factor-calculation`（如何算）、`05-factor-normalization`（方向转换）、`07-factor-validation`（校验）、`08-factor-output`（结果结构） |
| **下游** | `05-fund-evaluation`（消费并按画像加权）、Fund Universe、`08-backtest` |

---

## 16. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.4** | 2026-09-08 | 固定最小观测规则、Beta Profile 区间及 Benchmark 类型；移除 Portfolio 消费语义 | Plan-2 设计 v1.1 |
| **v1.3** | 2026-08-27 | **第二批定案（2 项）**。`FD-5` 评分使用 Rolling 序列的**均值 + 标准差**两个统计量进 Stability 子分（只取末值等同于普通因子，Rolling 的计算成本白付）；`OPEN-5` `CUSTOM` MAR 粒度保持 `fund_category × currency`（细化会与 Peer Group 对齐约束冲突）。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.2** | 2026-08-27 | **`TBD-FD-1` / `TBD-FD-2` 关闭 + Beta 表述精确化**。<br/>**`FD-2`**：新增 §2.2.4 —— MAR Policy 定案为 `ZERO` / `RISK_FREE` / `CUSTOM` 三模式、第一版默认 `ZERO`，并明确 **`mar_policy = ZERO`（已配置）与未配置（缺失）语义相反**，后者一律 `UNAVAILABLE`；说明现在的 `ZERO` 默认与 v1.0 被撤销的「文档假定 MAR=0」性质不同。<br/>**`FD-1`**。①`F-REL-002/003` 新增小节 —— Beta 对 `R_f` 的依赖是**形式上的**：`R_f` 恒定时完全无关，时变时只有其**波动**影响 Beta 而水平不影响，敏感度显著低于 Sharpe 与 Alpha；但不构成放松 PIT 约束的理由。②新增三个小节 —— §2.1.1 期限匹配表（`tenor` 由 Factor 的 Evaluation Period 决定，因此同一基金的 1Y 与 3Y Sharpe 用不同 `R_f`）；§2.1.2 **逐期超额而非年化相减**，并指出错误实现只在利率变动期显现、恰是指标最需准确之时；§2.1.3 `rate_source_quality` 须随因子结果落库。详见 `TBD-resolution.md` Policy ① | `03-data/01-data-source` v2.3 §3.1.5.5 |
| v1.1 | 2026-08-25 | **重写 §2 两个共同依赖**（上游 v2.5 §5.5）。此前把 `R_f` 与 `MAR` 并列为"待确认项"而未区分性质，会诱导下游按"数值相同即可共用"实现。新增 §2.0 性质对照；§2.1 五条 `R_f` 使用约束（**不得写死为常量**、按 `(currency, tenor)` 解析、PIT、口径一致、缺失不补 0）；§2.2.1 本域消费的 **MAR Policy 契约**与解析键；**§2.2.2 `MAR` 使 `F-RISK-002` / `F-RAP-002` 的值不再由 (Fund, Factor, Window, Date) 唯一确定**，必须携带 `Evaluation Policy Version`；§2.2.3 同一 Peer Group 内必须同 MAR。**撤销 v1.0 的"默认假设 `MAR = 0`"**——默认取值属业务决策，不应由因子文档假定。新增 C-8~C-11 与 TBD FD-8。<br/>**同时修正一处沿用自初版的事实错误**：`F-REL-004` Information Ratio 的公式为 `(R_p − R_b) / TE`，**并不依赖 `R_f`**，此前多处将其列为无风险利率消费方；`R_f` 的直接消费方是 `F-RAP-001` Sharpe、`F-REL-002` Alpha、`F-REL-003` Beta，`F-RAP-002` Sortino 仅在 `MAR = R_f` 时间接依赖 | `01-product-overview.md` v2.5 §5.5、`03-data/01-data-source.md` v2.2 |
| v1.0 | 2026-08-25 | 初始版本。定义 26 个 Factor 的完整语义（RET 4 / RISK 7 / RAP 3 / STAB 7 / REL 5）；核心 Factor 用完整模板、其余用覆盖 10 项必需字段的紧凑条目；**发现并标注两个跨域缺口**——无风险利率在 `03-data` 中缺失、MAR 取值未定；建立**除零边界条件汇总**并确立"除零一律 `UNAVAILABLE`"原则（含"好消息型除零"的处理）；明确 Beta 与 Tracking Error 的非单调方向；Rolling 类的序列输出结构与统计量选择 | `02-business-requirements.md` v2.3、`03-data` v1.0–v2.0 |