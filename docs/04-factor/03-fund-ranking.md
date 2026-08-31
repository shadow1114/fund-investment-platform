# 基金排名 · Fund Ranking

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：③ Fund Score 派生链
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§7 Peer Group、§16.1–§16.2
> 本域上游：docs/05-fund-evaluation/01-fund-evaluation.md、02-fund-scoring.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **基金如何与同类基金进行相对比较？**

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 分数如何合成 | `02-fund-scoring` |
| 分层阈值与 Tier | `04-fund-classification` |
| 候选池筛选 | `05-fund-selection` |
| `Peer Group` 的定义与参与规则 | `01-fund-evaluation` §3、上游 §7 |

---

## 2. Ranking Objective

### 2.1 Score 与 Ranking 的区别

| | **Fund Score** | **Ranking** |
|---|---|---|
| 表达 | 数值化的评价 | **序位** |
| 回答 | 这只基金得几分 | 它排第几 |
| 变化来源 | 自身指标变化 | 自身变化**或他人变化** |

### 2.2 一个必须澄清的常见误解

> **提示词把 Score 称为 "Absolute Evaluation"、Ranking 称为 "Relative Position"。在本项目中这个二分不成立。**

```
Fund Score 已经是相对量
    → 它由各 Factor 在 Peer Group 内做分位标准化后合成
    → 80 分的含义就是"约排前 20%"
```

**因此 Score 与 Ranking 的真实区别不是"绝对 vs 相对"，而是：**

| | Fund Score | Ranking |
|---|---|---|
| 相对性来自 | **因子层**的分位标准化 | **总分层**的排序 |
| 粒度 | 连续值，保留分数差距 | 离散序位，丢失差距信息 |
| 可加性 | 可拆解、可归因 | 不可拆解 |

> **这个区分为什么重要**：`02-business-requirements` §16.3.1 正是据此论证"不按绝对分数分层"——在已经是相对量的 Score 上再切绝对阈值，切出来仍然是分位，只是把这一事实隐藏起来。若误以为 Score 是绝对量，就会得出相反结论。

### 2.3 排名丢失了什么

> **排名是有损压缩**，必须与 Score 一同呈现。

```
基金 A：Score = 85.0  →  Rank 10
基金 B：Score = 84.9  →  Rank 11
基金 C：Score = 60.0  →  Rank 12

Rank 10 与 11 相差 0.1 分，Rank 11 与 12 相差 24.9 分
    → 仅看排名会认为三者等距
```

---

## 3. Peer Group

> **`Peer Group` 由上游 §7 定义，本文档不重新定义，只说明其在排名中的作用。**

### 3.1 定义（引用）

```
Peer Group = Fund Classification  +  effective_at  +  参与规则
```

它是**标准化、排名、分位与分层的同一个计算样本集**——四者必须用同一个 Peer Group，否则不自洽。

### 3.2 最关键的约束（引用）

> **`Peer Group` 的构成不得依赖 `Fund Score` 或 `Fund Universe`**（上游 §7.2、`FR-PEER-001`）。

违反会形成 `Score → Universe → Peer Group → Score` 的循环依赖——**它不会报错，只会让每次重算得到不同的排名**。

### 3.3 参与规则（引用）

| 规则 | 内容 |
|---|---|
| 基础集合 | `Fund Coverage` 中属于该分类的全部基金 |
| 最低数据要求 | 该指标可计算（非 `UNAVAILABLE`）的基金才参与**该指标**的排名 |
| **已清盘基金** | **历史时点包含** —— 回测在 `T` 时点必须含当时存续的全部基金 |
| **不可投资基金** | **包含** —— 可投资性不影响评价 |
| 最小样本量 | 低于阈值时排名不具统计意义，标记低置信 |

### 3.4 本域不新增 Peer Group 划分维度

> 提示词列举了 Fund Category / Asset Class / Investment Objective / Strategy / Currency / Market 等可能依据。**上游已定为 `Fund Classification`**，本域不自行引入新维度。

> **已定案 · 2026-08-27**：**`Currency` 必须作为 Peer Group 的划分维度；`Market` 不作为。**
>
> **Currency 必须划分的两个理由**：
>
> | # | 理由 |
> |---|---|
> | 1 | **跨币种收益含汇率成分** —— 一只 USD 计价基金对 CNY 投资者的实际收益 = 基金收益 + 汇率变动。用未经汇率调整的收益直接排名，比较的不是管理能力 |
> | 2 | **MAR 的 `RISK_FREE` 模式在多币种组中不可用**（`01-fund-evaluation` §16.3.2 已论证）—— 各基金的 MAR 随其计价币种解析出不同的 `R_f`，组内 Sortino 不在同一标尺 |
>
> **Market 不作为划分维度**：同一币种下的不同上市地（如沪深两市）不影响收益的可比性，也不影响 `R_f` 的解析。按 Market 细分只会缩小组规模，触发更多 `INSUFFICIENT_SAMPLE`。
>
> **连带影响**：`R_f` 的解析键 `(currency, tenor)` 中的 `currency` 与本条的划分维度**必须取自同一字段**（`fund_share_class.base_currency`），否则会出现「按 A 币种分组、按 B 币种解析利率」的错配。

---

## 4. Ranking Scope

> **一次排名必须完整声明五项，缺一则结果无法解释。**

| 项 | 说明 |
|---|---|
| **`as_of_date`** | 排名时点 |
| **`evaluation_period`** | 1M / 3M / 6M / 1Y / 3Y / 5Y |
| **`peer_group_id` + `peer_group_version`** | 跟谁比 |
| **`ranking_metric`** | 按什么排 |
| **`ranking_policy_version`** | 用什么规则排 |

### 4.1 为什么 `evaluation_period` 必须显式声明

```
同一只基金：
  1Y  Rank = 5 / 120
  3Y  Rank = 80 / 95
```

**两个排名都正确**，但含义完全不同。不声明周期的排名是无意义的。

---

## 5. Ranking Metric

### 5.1 默认与可选

| Metric | 说明 |
|---|---|
| **`Total Score`** | **默认** —— 覆盖五个维度 |
| 单项子分（如 Risk-Adjusted Score） | 支持，用于专项视角 |
| 单个 Factor（如 Annual Return、Sharpe） | 支持，用于展示与筛选 |

### 5.2 单因子排名的使用边界

> **单因子排名可以展示，但不得代替综合评价。**

沿用 `02-business-requirements` §15.2：**严禁 `收益率排名 = 基金评分`**。

按单因子排名做筛选是允许的（属 `SCREENING` 用途），但把它当作基金的"综合排名"则违反上游约束。

### 5.3 Metric 必须与 Peer Group 同源

> 排名所用的 Metric，其标准化必须在**同一个** Peer Group 内完成。

```
❌ 用 Peer Group A 标准化得到的 Score，在 Peer Group B 内排名
```

---

## 6. Rank

### 6.1 定义

```
Rank = 该基金在 Peer Group 内按 Ranking Metric 降序排列的序位
```

**表示形式**：`Rank / N`，其中 `N` 是该指标在该组内的**有效参与数**。

```
Fund A = 5 / 120
```

### 6.2 `N` 是有效参与数，不是组规模

> **这是排名中最容易出错的一处。**

```
Peer Group 规模 = 200 只
其中 80 只的 3Y Sharpe 为 UNAVAILABLE（成立不足 3 年）

3Y Sharpe 排名的 N = 120，不是 200
```

**必须同时呈现 `N` 与组规模**，否则用户无法判断"120 只里的第 5 名"与"200 只里的第 5 名"的差别。

### 6.3 排名方向

> **统一按"越优越靠前"排列**，Rank = 1 表示最优。

这依赖标准化已把全部因子统一为"越高越好"（`04-factor/05-factor-normalization`）。若某展示场景直接按 Raw Value 排名（如按 Volatility 从低到高），必须显式标注排序方向。

---

## 7. Percentile

### 7.1 定义与公式

```
Percentile = (N − Rank) / (N − 1) × 100%
```

> **本公式使最优者 = 100%、最劣者 = 0%，与 Score 的 0–100 标尺方向一致。**

```
Rank = 5，N = 120
Percentile = (120 − 5) / 119 × 100% ≈ 96.6%
```

### 7.2 公式选择必须显式声明

> **分位有多种约定，不同约定的结果不同**，必须在 `Ranking Policy` 中固定一种。

| 约定 | 公式 | 最优者 | 最劣者 |
|---|---|---|---|
| **本项目采用** | `(N − Rank) / (N − 1)` | **100%** | **0%** |
| 常见变体 A | `(N − Rank) / N` | `(N−1)/N` | 0% |
| 常见变体 B | `(N − Rank + 0.5) / N` | 不达 100% | 不达 0% |

> **为什么选第一种**：`Fund Tier` 的分位阈值是 5% / 20% / 50% / 80%（`02-business-requirements` §16.3.1），采用端点为 0/100 的约定使阈值语义直观——"前 5%"就是 `Percentile ≥ 95%`。

### 7.3 `N = 1` 的边界

```
N = 1  →  分母为 0
```

**处理**：`N = 1` 时分位无意义，`Percentile = UNAVAILABLE`。这与 `04-factor/05-factor-normalization` §5.2「组内仅 1 只基金 → `UNAVAILABLE`」一致。

### 7.4 Percentile 与 Score 的关系

> **两者高度相关但不相同。**

```
Total Score  由各因子分位加权合成  →  合成后不再是分位
Percentile   对 Total Score 再排序 →  重新变回分位
```

因此 `Score = 85` 与 `Percentile = 85%` **不是同一件事**，不得互相替代。

---

## 8. Tie Handling

### 8.1 三种方法

| 方法 | 说明 | 示例（分数 90, 85, 85, 80） |
|---|---|---|
| **`COMPETITION_RANK`** | 并列同名次，后续跳号 | 1, 2, 2, **4** |
| **`DENSE_RANK`** | 并列同名次，后续不跳号 | 1, 2, 2, **3** |
| **`ORDINAL_RANK`** | 强制唯一名次，按次级规则打破并列 | 1, 2, 3, 4 |

### 8.2 取值

```
Ranking Tie Method = TBD
```

> **本参数当前为 TBD，投产前必须由业务负责人确认。**

> **已定案 · 2026-08-27**：Tie Method = **`COMPETITION_RANK`**（并列同名次，后续名次跳过，如 1, 2, 2, 4）。
>
> **依据 —— `DENSE_RANK` 会破坏分位口径**：
>
> ```
> DENSE_RANK（1, 2, 2, 3）：名次不跳过
>     → N 只基金的最大名次 < N
>     → §7.2 的 Percentile 公式 (N − Rank)/(N − 1) 分母与实际名次范围不匹配
>     → 「前 10%」实际包含的基金数随并列数量漂移
>
> COMPETITION_RANK（1, 2, 2, 4）：名次跳过
>     → 最大名次 = N，分位口径稳定
> ```
>
> **这不只是惯例问题** —— 上游已定 Tier 按 5/20/50/80 分位划分，若分位的分母口径会随并列情况浮动，Tier 的边界就不稳定。
>
> **浮点因子值的并列极少发生**，但**分位标准化后**（`04-factor/05`）并列会变得常见 —— 因为分位是离散化的。因此本条在实践中会被频繁触发。

### 8.3 选择时必须考虑的三点

| # | 考量 |
|---|---|
| 1 | **对 `N` 的影响** —— `COMPETITION_RANK` 下最大 Rank 等于 N，`DENSE_RANK` 下小于 N，这会改变 §7.1 的分位计算 |
| 2 | **`ORDINAL_RANK` 需要次级排序规则** —— 且该规则必须**确定性**，不得依赖数据返回顺序 |
| 3 | **对分层的影响** —— 大量并列跨越 Tier 边界时，不同方法会把并列的基金分到不同 Tier |

### 8.4 确定性要求

> **无论选择哪种方法，相同输入必须得到相同排名。**

```
❌ 并列时按数据库返回顺序 → 每次重算可能不同 → 违反可复现性
✅ 并列时按显式声明的次级规则（如 fund_id 升序）
```

即使采用 `COMPETITION_RANK` / `DENSE_RANK`（不强制打破并列），**结果列表的输出顺序**仍需确定性排序。

---

## 9. Ranking Eligibility

### 9.1 评价合格 ≠ 排名合格

> **一只基金可以完成 Evaluation，却不能参与 Ranking。**

| 情形 | Evaluation | Ranking |
|---|---|---|
| 基金正常，Peer Group 充足 | ✅ | ✅ |
| **Peer Group 样本量低于阈值** | ✅ | ❌ / **低置信** |
| **Peer Group 内仅 1 只基金** | ✅ | ❌ `UNAVAILABLE` |
| 该指标为 `UNAVAILABLE` | ✅（其他指标） | ❌ **该指标**的排名 |
| `evaluation_status = FAILED` | ❌ | ❌ |

### 9.2 排名资格是逐指标判定的

> **不是"这只基金能否排名"，而是"这只基金的哪个指标能排名"。**

```
基金 X：
  1Y Sharpe  → 可排名（N = 120）
  3Y Sharpe  → UNAVAILABLE（成立不足 3 年）→ 该项无排名
  Total Score→ 可排名，但 data_completeness 偏低
```

### 9.3 最小样本量

```
Minimum Peer Group Size = 30      ← 已定案 2026-08-27
```

> **定案**：见 `02-business-requirements` §7.3.1、`TBD-resolution.md` Policy ⑤。

该阈值同时影响标准化（`04-factor/05-factor-normalization` §5.2.1）、排名与分层（`04-fund-classification` §8.5），**三处必须用同一个值，且配置来源唯一** —— 不得三处各自定义常量。

#### 9.3.1 `n_effective < 30` 时不产出 Ranking

| 输出字段 | 值 |
|---|---|
| `rank` | `null` |
| `percentile` | `null` |
| `n_effective` | 实际值（如 17） |
| **`ranking_status`** | **`INSUFFICIENT_SAMPLE`** |

> **`n_effective` 仍须返回** —— 调用方需要知道「差多少」。返回 17 与返回 29 对使用方的含义不同：后者接近阈值，可能下一期就恢复。

> **这不是错误状态** —— 样本不足是正常业务情形（§6.1），`ranking_status` 与 `FAILED` 是两回事。新成立的细分类别天然样本少，不应产生告警。

> **与 §6.2 的关系**：本节的判定基数沿用 §6.2 定义的 `n_effective`（有效参与数），不是组规模。同一组内不同指标可有不同的 `ranking_status`。

---

## 10. 排名的时间序列

> **`02-business-requirements` §16.2 要求支持查看排名随时间的变化。**

```
排名持续下滑的基金，即使当前分数仍高，也值得警惕
```

### 10.1 排名变化的三个来源

> **排名下降不一定意味着基金变差** —— 这是解读排名时序的关键。

| 来源 | 说明 |
|---|---|
| **自身表现变化** | 真正的能力变化 |
| **同组其他基金表现变化** | 自身未变，别人变好了 |
| **`Peer Group` 构成变化** | 新基金成立、老基金清盘、分类调整 |

**因此排名时序必须与 Score 时序、组规模时序一同呈现**，否则无法归因。

---

## 11. Ranking Policy

| 字段 | 说明 |
|---|---|
| `policy_id` | 标识 |
| `version` | 版本号 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`peer_group_definition`** | 引用上游 §7 的定义与参与规则 |
| **`ranking_metric`** | 默认 `Total Score` |
| **`percentile_convention`** | §7.2 三种约定中的一种 |
| **`tie_method`** | `COMPETITION` / `DENSE` / `ORDINAL` |
| **`tie_breaker`** | `ORDINAL` 时的次级排序规则 |
| **`minimum_peer_group_size`** | 最小样本量阈值 |

> 未确认参数使用 `TBD`，投产前须由业务负责人确认。

---

## 12. Ranking Reproducibility

### 12.1 五要素

```
as_of_date
+ evaluation_period
+ peer_group_id + peer_group_version
+ ranking_policy_version
+ scoring_policy_version（及其依赖的 evaluation_policy_version、factor_version、data_version）
        ↓
    相同排名
```

### 12.2 `peer_group_version` 是排名可复现的核心

> **排名是组内序位，组变了序位必然变。**

```
同一基金、同一时点、同一 Score
但 Peer Group 少了 10 只基金
    → N 变化 → Rank 可能不变但 Percentile 必变 → Tier 可能变
```

### 12.3 排名结果必须完整落库

> **不得只存 Rank 而不存 `N` 与 Percentile。**

重算 Percentile 需要当时的 `N`，而 `N` 依赖当时的 Peer Group 构成与各基金的指标可得性——若不落库，历史分位无法还原。

---

## 13. Input / Process / Output

### 13.1 Input

| 输入 | 来源 |
|---|---|
| Score Output（`total_score` + 五子分） | `02-fund-scoring` §13.3 |
| `Peer Group` + version + 成员列表 | `01-fund-evaluation` |
| `Ranking Policy` + version | 本文档 |

### 13.2 Process

```
① 取该 Peer Group 在 as_of_date 的成员列表
② 剔除该 Ranking Metric 为 UNAVAILABLE 的基金 → 得到有效参与集，规模 N
③ 若 N < minimum_peer_group_size → 标记低置信
④ 若 N = 1 → Percentile = UNAVAILABLE
⑤ 按 Ranking Metric 降序排列，按 tie_method 处理并列
⑥ 计算 Rank 与 Percentile
⑦ 落库：Rank、N、组规模、Percentile、版本引用
```

### 13.3 Output

| 字段 | 说明 |
|---|---|
| `fund_id` / `evaluation_period` / `as_of_date` | 标识 |
| **`rank`** | 序位 |
| **`n_effective`** | **有效参与数** |
| **`peer_group_size`** | 组规模（与 `n_effective` 可能不同） |
| **`percentile`** | 分位 |
| `ranking_metric` | 按什么排的 |
| `confidence_flag` | 样本量不足时标记低置信 |
| 版本引用 | §12.1 五要素 |

---

## 14. Edge Cases

| 情形 | 处理 |
|---|---|
| `N = 0`（组内无一只基金该指标可得） | 该组该指标无排名 |
| `N = 1` | `Rank = 1`，`Percentile = UNAVAILABLE` |
| 全组分数完全相同 | 按 `tie_method` 处理；`ORDINAL` 时依赖 tie_breaker |
| 基金在评价期内转型（分类改变） | 用当时的分类归组；**转型前后的排名不可直接比较** |
| 同一基金多个 Share Class 同在一组 | 各自独立排名（是否允许见 `01-fund-evaluation` `TBD-FE-1`） |
| Peer Group 规模骤变 | 排名可比性下降，须在时序展示中标注 |

---

## 15. 示例

> **全部数值以 `X` / 示意值表示。**

```
Fund A ｜ as_of = 2026-08-24 ｜ Period = 1Y
Peer Group        = 主动股票型 · v3
Peer Group Size   = 200
Ranking Metric    = Total Score

有效参与数 N      = 120（80 只因 Total Score UNAVAILABLE 被剔除）
Total Score       = X / 100
Rank              = 5 / 120
Percentile        = (120 − 5) / 119 × 100% ≈ 96.6%
Confidence        = NORMAL

→ 下游 Tier 判定：Percentile ≥ 95%  →  A+
```

---

## 16. Auditability

### 16.1 必须能回答的问题

> **这只基金为什么排这个名？**

```
Rank = 5 / 120
    ├─ Ranking Metric        = Total Score（来自 02-fund-scoring 的完整归因链）
    ├─ Peer Group + version  = 跟谁比、当时组里有谁
    ├─ n_effective = 120     = 200 只中 80 只因该指标 UNAVAILABLE 被剔除
    ├─ Tie Method            = 并列如何处理
    └─ Percentile Convention = 用哪个公式换算
```

### 16.2 排名的留痕不可省略 `N`

> **只存 `Rank` 是最常见的留痕缺失。**

重算 Percentile 需要当时的 `n_effective`，而它依赖当时的 Peer Group 构成与各基金的指标可得性。若不落库，历史分位**无法还原**，下游 Tier 也就无法解释。

### 16.3 被剔除的基金同样要能追溯

> 一只基金"没有排名"必须有据可查——是指标 `UNAVAILABLE`，还是 `evaluation_status = FAILED`，两者的处置完全不同（前者正常，后者须告警）。

---

## 17. Summary

排名是**比较**环节，其本质是在 Score 之上做组内序位。

四条容易出错的地方：

- **Score 已经是相对量** —— 提示词的"Score 绝对 / Ranking 相对"二分在本项目不成立；误认为 Score 是绝对量会推翻上游"不按绝对分数分层"的论证
- **`N` 是有效参与数，不是组规模** —— 80 只因指标不可得被剔除时，"120 只里的第 5 名"与"200 只里的第 5 名"含义不同
- **Percentile 公式必须显式声明** —— 三种常见约定结果不同，本项目采用端点为 0/100 的约定以匹配 Tier 的 5/20/50/80 阈值
- **排名下降不一定意味着基金变差** —— 可能是同组其他基金变好，或 Peer Group 构成变了

一项必须落库的内容：**Rank、`N`、Percentile 三者都要存**。只存 Rank 则历史分位无法还原。

---

## 18. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **不采用"Score 绝对 / Ranking 相对"的二分** | Score 由分位标准化合成，本身已是相对量 |
| D-2 | 排名与 Score 必须一同呈现 | 排名是有损压缩，丢失分数差距 |
| D-3 | `Peer Group` 沿用上游定义，**不新增划分维度** | 上游 §7 已定为 `Fund Classification` |
| D-4 | Ranking Scope 必须完整声明五项 | 缺任一项排名无法解释 |
| D-5 | 默认 Ranking Metric 为 `Total Score` | 覆盖五维度；单因子排名不得代替综合评价 |
| D-6 | **`N` 取有效参与数**，并同时呈现组规模 | 二者不同，混用会误导 |
| D-7 | Percentile 采用 `(N − Rank) / (N − 1)` | 端点为 0/100，与 Tier 的 5/20/50/80 阈值语义直观匹配 |
| D-8 | `N = 1` 时 `Percentile = UNAVAILABLE` | 分母为 0；与标准化层一致 |
| D-9 | **Tie Method = TBD**，但确定性是硬要求 | 并列按数据库返回顺序会破坏可复现性 |
| D-10 | 排名资格**逐指标判定** | 不是"能否排名"而是"哪个指标能排名" |
| D-11 | 最小样本量三处（标准化 / 排名 / 分层）必须用同一值 | 否则三者不自洽 |
| D-12 | **Rank、`N`、Percentile 三者都必须落库** | 只存 Rank 则历史分位不可还原 |

---

## 19. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | `Peer Group` 必须独立于 `Fund Score` 与 `Fund Universe` | 上游 §7.2、`FR-PEER-001` |
| C-2 | 标准化、排名、分位、分层必须用**同一个** Peer Group | `02-business-requirements` §16.1 |
| C-3 | 历史时点的 Peer Group 必须含当时存续、后已清盘的基金 | `02-business-requirements` §7.3 |
| C-4 | **严禁 `收益率排名 = 基金评分`** | `02-business-requirements` §15.2 |
| C-5 | 排名必须确定性 —— 相同输入得到相同结果 | 上游 §9 原则六 |
| C-6 | 排名时序必须与 Score 时序、组规模时序一同呈现 | 本文档 §10.1 |
| C-7 | Percentile 约定必须在 Policy 中固定，不得逐场景变化 | 本文档 §7.2 |

---

## 20. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~FR-1~~ | ~~Currency / Market 是否作为 Peer Group 附加划分维度~~ —— **已定案**：Currency 必须作为 Peer Group 的划分维度；Market 不作为 | — | ✅ 2026-08-27 |
| ~~FR-2~~ | ~~Ranking Tie Method 及 `ORDINAL` 时的 tie_breaker~~ —— **已定案**：Tie Method = `COMPETITION_RANK`（并列同名次，后续名次跳过） | — | ✅ 2026-08-27 |
| ~~FR-3~~ | ~~Minimum Peer Group Size~~ —— **已定案 30**（§9.3）；`n_effective < 30` 时 `rank`/`percentile` 为 `null`、`ranking_status = INSUFFICIENT_SAMPLE` | — | ✅ 已定案 2026-08-27 |
| FR-4 | 排名时序的展示区间与变化告警阈值 | 展示层与监控 | 投研 + 运维 |

---

## 21. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ③、§7）、`02-business-requirements.md` v2.3（§7、§15.2、§16.1–16.2） |
| **功能需求** | `04-functional-requirements.md`（`FR-RANK-001~004`、`FR-PEER-001~004`） |
| **本域** | `01-fund-evaluation`（Peer Group）、`02-fund-scoring`（Total Score）、`04-fund-classification`（消费 Percentile） |
| **因子依赖** | `04-factor/05-factor-normalization` §5（组内样本量与 `UNAVAILABLE` 处理） |

---

## 22. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（2 项）**。`FR-1` **`Currency` 必须作为 Peer Group 划分维度、`Market` 不作为** —— 跨币种收益含汇率成分，且 `RISK_FREE` MAR 在多币种组中不可用；并要求分组用的 `currency` 与 `R_f` 解析键取自同一字段。`FR-2` Tie Method = **`COMPETITION_RANK`** —— `DENSE_RANK` 会使最大名次 < N，与 §7.2 的分位公式分母不匹配，进而让 Tier 边界随并列数漂移。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.1** | 2026-08-27 | **`TBD-FR-3` 关闭**。§9.3 定案 `Minimum Peer Group Size = 30`；新增 §9.3.1 —— 不足时 `rank` / `percentile` 为 `null`、`ranking_status = INSUFFICIENT_SAMPLE`，但 **`n_effective` 仍须返回**（17 与 29 对使用方含义不同）；明确这不是错误状态，新成立的细分类别天然样本少不应告警。详见 `TBD-resolution.md` Policy ⑤ | `02-business-requirements` v2.6 §7.3.1 |
| v1.0 | 2026-08-26 | 初始版本。**§2.2 澄清"Score 绝对 / Ranking 相对"二分在本项目不成立**——Score 由分位标准化合成本身已是相对量，误认会推翻上游"不按绝对分数分层"的论证；**§6.2 明确 `N` 是有效参与数而非组规模**；**§7.2 固定 Percentile 公式为 `(N−Rank)/(N−1)`** 并说明选择理由（端点 0/100 匹配 Tier 的 5/20/50/80 阈值）；§8.3 Tie Method 选择的三点考量（对 `N`、对次级规则、对分层边界的影响）与确定性硬要求；**§9 排名资格逐指标判定**；**§10.1 排名变化的三个来源**（自身 / 他人 / 组构成）；§12.3 Rank、`N`、Percentile 三者必须落库 | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`02-fund-scoring.md` v1.0 |