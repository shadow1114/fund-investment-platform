# 因子 API · Factor API

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文暴露的域：**② Factor**
> 业务语义来源：docs/04-factor/（v1.0–v1.1，全 8 份）
> 本域上游：docs/10-api/01-api-overview.md（v1.0）
>
> **文档版本**：v1.3 ｜ **产品阶段**：第一阶段

---

## 1. Overview

### 1.1 本文档回答什么

> **因子的定义、取值与元数据如何对外暴露？**

### 1.2 本文档不定义因子 ⚠️

| 不定义 | 归属 |
|---|---|
| 因子公式 | `04-factor/03-factor-definition` |
| 计算管线与边界条件 | `04-factor/04-factor-calculation` |
| 标准化方法 | `04-factor/05-factor-normalization` |
| 版本规则 | `04-factor/06-factor-versioning` |
| 校验规则 | `04-factor/07-factor-validation` |
| 结果结构 | `04-factor/08-factor-output` |

> **API 只暴露结果与元数据，公式由 `04-factor` 引用。**

### 1.3 全局约定引用 `01-api-overview`

---

## 2. Scope

| 能力 | 说明 |
|---|---|
| **因子目录** | 26 个已定义 Factor 的清单与元数据 |
| **因子定义** | 单个 Factor 的完整元数据（引用公式，不重述） |
| **因子值** | 单基金单因子的当前或历史值 |
| **因子历史** | 时序 |
| **批量因子值** | 一次取多只基金的多个因子 |
| **Rolling 因子序列** | Rolling 类因子的序列输出 |

### 2.1 第一阶段不提供主动计算 API

```
Factor Calculation API = 不提供（第一阶段）
```

**理由**：

| # | 理由 |
|---|---|
| 1 | 因子计算是**批量管线**，按 `decision_at` 统一执行（`04-integration-architecture` §4） |
| 2 | 允许按需触发计算会绕过幂等键 `(decision_at, Strategy Version)` |
| 3 | 单只基金的临时计算结果**不进入快照**，无法被下游引用，价值有限 |

> **若未来需要，须作为独立能力设计**，并明确其结果是否进入快照。

> **已定案 · 2026-08-27**：第一阶段**不提供按需触发的 Factor 计算 API**。
>
> **依据（§2.1 已论证，此处落案）—— 按需计算的结果没有快照归属**：
>
> ```
> Factor 值由 (decision_at, factor_version, data_version, evaluation_policy_version) 共同确定
>
> 按需触发的计算：用什么 decision_at？
>     → 用「现在」：产生一个不属于任何决策周期的孤立值
>     → 用指定历史时点：等于重算历史，绕过版本治理
> ```
>
> **两条路径都会破坏「因子值属于某次批量计算（`factor_run`）」这一结构** —— 而该结构正是可追溯性的基础。
>
> **替代方案**：需要探索性计算时，走离线分析环境，其结果不进入生产的 `factor_value` 表。

---

## 3. API List

| # | Endpoint | Method | 能力 |
|---|---|---|---|
| 3.1 | `/api/v1/factors` | GET | 因子目录 |
| 3.2 | `/api/v1/factors/{factor_id}` | GET | 因子定义与元数据 |
| 3.3 | `/api/v1/funds/{fund_id}/factors` | GET | 单基金的全部因子值 |
| 3.4 | `/api/v1/funds/{fund_id}/factors/{factor_id}` | GET | 单个因子值 |
| 3.5 | `/api/v1/funds/{fund_id}/factors/{factor_id}/series` | GET | 因子历史序列 |
| 3.6 | `/api/v1/factor-values` | GET | **批量查询**（多基金 × 多因子） |

> 路径待接口评审确认（`<TBD-FTA-2>`）。

---

## 4. API Details

### 4.1 GET /factors — 因子目录

**Purpose**：列出平台已定义的 Factor。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `category` | `RET` / `RISK` / `RAP` / `STAB` / `REL` |
| `usage` | `DISPLAY` / `SCORING` / `SCREENING` / `PORTFOLIO` / `BACKTEST` |
| `status` | `DRAFT` / `VALIDATING` / `ACTIVE` / `DEPRECATED` / `RETIRED` |

**Response**

```json
{
  "data": [
    {
      "factor_id": "F-RAP-001",
      "factor_name": "Sharpe Ratio",
      "category": "RAP",
      "unit": "RATIO",
      "preference_direction": "HIGHER_IS_BETTER",
      "usage": ["DISPLAY", "SCORING", "SCREENING", "BACKTEST"],
      "supported_windows": ["3M", "6M", "1Y", "3Y", "5Y"],
      "status": "ACTIVE",
      "current_version": "v1"
    }
  ],
  "meta": { "total_items": 26 },
  "error": null
}
```

#### 4.1.1 五分类对应五子分

> 沿用 `04-factor/02-factor-taxonomy` §2：`RET` / `RISK` / `RAP` / `STAB` / `REL` 与 `05-fund-evaluation` 的五子分一一对应。

#### 4.1.2 `usage` 决定该因子能出现在哪里 ⚠️

> **沿用 `02-business-requirements` §14.2 Factor Usage Matrix。**

```
Correlation / Covariance 的 usage 不含 SCORING
    → 它们是基金【之间】的关系，不是单只基金的属性
    → API 层不得提供"某基金的 Correlation 值"这类端点
```

**因此本域的因子值端点只覆盖单基金属性类因子**；基金间关系属 `04-portfolio-api`（协方差矩阵）。

---

### 4.2 GET /factors/{factor_id} — 因子定义

**Purpose**：返回单个 Factor 的完整元数据。

**Response**

```json
{
  "data": {
    "factor_id": "F-RAP-001",
    "factor_name": "Sharpe Ratio",
    "description": "单位总风险的超额收益",
    "category": "RAP",
    "unit": "RATIO",
    "preference_direction": "HIGHER_IS_BETTER",
    "usage": ["DISPLAY", "SCORING", "SCREENING", "BACKTEST"],
    "inputs": ["ADJUSTED_NAV", "RISK_FREE_RATE"],
    "supported_windows": ["3M", "6M", "1Y", "3Y", "5Y"],
    "frequency": "DAILY",
    "annualization_factor": 252,
    "min_observations": null,
    "boundary_conditions": [
      { "condition": "volatility == 0", "handling": "UNAVAILABLE" }
    ],
    "formula_reference": "docs/04-factor/03-factor-definition.md#F-RAP-001",
    "current_version": "v1",
    "status": "ACTIVE",
    "effectiveness_summary": {
      "latest_verdict": "VALID",
      "peer_group_id": "PG-EQUITY-ACTIVE",
      "evaluation_window": "3Y",
      "ic": 0.043,
      "icir": 0.51,
      "sample_split": "OOS",
      "validation_policy_version": "v2",
      "validated_at": "2026-06-30"
    }
  },
  "meta": {},
  "error": null
}
```

#### 4.2.1 `effectiveness_summary` 是摘要不是全量（v1.2 新增）

> **由 Policy ⑥ 引入，后按 2026-09-08 决策收敛**：有效性检验决定因子是否具备评分资格，不生成权重；调用方仍需知道某因子当前是否有效。

**三条约定**：

| # | 约定 |
|---|---|
| 1 | **只返回最近一次的 OOS 结论** —— 完整的检验历史（各 Peer Group × 各窗口 × IS/OOS）属独立查询，不塞进定义端点 |
| 2 | **`peer_group_id` 必须一并返回** —— 有效性是「在某个组里」的属性，脱离组的 `VALID` 没有意义 |
| 3 | **`validation_policy_version` 必须一并返回** —— 同一份 IC 在不同阈值下结论不同（`11-database/03-erd` §8.4.2） |

> **`latest_verdict` 为 `null` 的情形**：该因子尚未检验。**这不等于 `INVALID`** —— 前者是未知，后者是已判定不可用。消费方据此决定的行为不同：未检验的因子不进入评分（Score 不投产），已判 `INVALID` 的因子权重为 0 但评分照常。

#### 4.2.2 API 不重述公式，只提供引用 ⚠️

> **沿用提示词 §28.2 与 `01-api-overview` §24 第 1 项。**

```
❌ 在 API 响应中返回完整的 LaTeX 公式并逐项解释
   → 公式在 04-factor 与 API 两处维护，必然发散

✅ 返回 formula_reference 指向权威定义
```

#### 4.2.3 `preference_direction` 四取值，不得简化

> **沿用上游术语表：**`HIGHER_IS_BETTER` / `LOWER_IS_BETTER` / **`TARGET_RANGE`** / **`STRATEGY_DEPENDENT`**。

```
Beta            → TARGET_RANGE（需目标区间）
Tracking Error  → STRATEGY_DEPENDENT（随 Evaluation Profile 变化）
```

> **API 不得把这两者简化为单调方向** —— 那会让消费者按"越低越好"处理 Tracking Error，而这对主动型基金是错的（`02-business-requirements` §5.2.1）。

**因此 `TARGET_RANGE` / `STRATEGY_DEPENDENT` 的因子必须额外返回其上下文依赖**：

```json
{
  "preference_direction": "STRATEGY_DEPENDENT",
  "direction_depends_on": "evaluation_profile",
  "direction_by_profile": {
    "ACTIVE_EQUITY": "NEUTRAL",
    "PASSIVE_EQUITY": "LOWER_IS_BETTER",
    "BOND": "NOT_APPLICABLE",
    "HYBRID": null
  }
}
```

#### 4.2.4 `boundary_conditions` 必须暴露

> **沿用 `04-factor/03-factor-definition` §10：除零一律 `UNAVAILABLE`。**

消费者需要知道"为什么这只基金的 Calmar 是 `null`" —— 边界条件说明是答案的一部分。

---

### 4.3 GET /funds/{fund_id}/factors — 单基金全部因子

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `window` | `1Y` 等；不填返回全部窗口 |
| `category` | 按类别过滤 |
| `as_of_date` | PIT |

**Response**

```json
{
  "data": [
    {
      "factor_id": "F-RAP-001",
      "window": "1Y",
      "raw_value": 1.24,
      "normalized_value": 87.0,
      "status": "VALID",
      "as_of_date": "2026-08-24",
      "risk_free_rate_ref": {
        "currency": "CNY", "tenor": "1Y", "effective_at": "2026-08-23",
        "version": 1, "rate_source_quality": "EXACT"
      }
    },
    {
      "factor_id": "F-RAP-002",
      "window": "1Y",
      "raw_value": null,
      "normalized_value": null,
      "status": "UNAVAILABLE",
      "reason_code": "MAR_NOT_CONFIGURED",
      "evaluation_policy_version": null
    },
    {
      "factor_id": "F-RAP-003",
      "window": "1Y",
      "raw_value": null,
      "normalized_value": null,
      "status": "UNAVAILABLE",
      "reason_code": "ZERO_MAX_DRAWDOWN",
      "reason_message": "窗口内无回撤，比率无法计算"
    }
  ],
  "meta": {
    "as_of_date": "2026-08-24",
    "is_point_in_time": true,
    "factor_version": "...",
    "peer_group_id": "...",
    "peer_group_version": "...",
    "normalization_method": "PERCENTILE_RANK",
    "data_version": "..."
  },
  "error": null
}
```

#### 4.3.1 `raw_value` 与 `normalized_value` 必须同时返回 ⚠️

> **沿用 `04-factor/08-factor-output` §2.3：**

| 值 | 用途 |
|---|---|
| **`raw_value`** | 展示、人工核对、**筛选阈值** |
| **`normalized_value`** | 评分、Ranking 与 Tier，范围 `[0,100]` |

```
只返回 Normalized → 用户看不懂"87.0"是什么意思
只返回 Raw        → 下游各自标准化，破坏一致性
```

#### 4.3.2 `normalized_value` 必须附 Peer Group 上下文 ⚠️

> **同一 `raw_value` 在不同 Peer Group 中会得到完全不同的 `normalized_value`。**

**缺少 `peer_group_id` + `peer_group_version` 时，`normalized_value` 无法跨基金比较**（`04-factor/08` §2.4）。

#### 4.3.3 依赖 MAR 的因子必须返回 `evaluation_policy_version` ⚠️

> **这是本域最容易漏掉的一处**（上游 §5.5.2、`04-factor/08` §2.5）。

```
R_f 是市场数据 → 全平台唯一
    → (Fund, F-RAP-001, 1Y, Date) 确定唯一 Sharpe
    → risk_free_rate_ref 是【溯源信息】

MAR 是评价配置 → 随 Evaluation Policy 不同
    → (Fund, F-RAP-002, 1Y, Date) 【不足以】确定唯一 Sortino
    → evaluation_policy_version 是【标识的一部分】
```

| 因子 | 必需的版本字段 | 该字段的性质 |
|---|---|---|
| `F-RAP-001` Sharpe、`F-REL-002` Alpha、`F-REL-003` Beta | `risk_free_rate_ref` | 溯源 |

> **Beta 的依赖是形式上的** —— `R_f` 恒定时 Beta 与它完全无关，时变时只有 `R_f` 的**波动**影响 Beta（`04-factor/03-factor-definition` `F-REL-002/003`）。API 仍为它返回 `risk_free_rate_ref`，因为 Alpha 与 Beta 出自**同一回归**，两者的溯源必须一致。
| **`F-RISK-002` Downside Volatility、`F-RAP-002` Sortino** | **`evaluation_policy_version`** | **标识** |

> **把两者当作同一类字段处理，会导致 Sortino 的多个版本互相覆盖。**

#### 4.3.4 `F-REL-004` Information Ratio 不依赖 `R_f`

> **沿用 `04-factor/03-factor-definition`：** IR 的公式是 `(R_p − R_b) / TE`。**API 不得为它返回 `risk_free_rate_ref`** —— 那会误导消费者以为 IR 受利率影响。

#### 4.3.5 `reason_code` 必须区分四类 ⚠️

| `status` | 含义 | 是否需修复 |
|---|---|---|
| `VALID` | 正常 | — |
| `WARNING` | 可疑但可用 | 核查 |
| **`INVALID`** | **算了但算错了** | **是，须告警** |
| **`UNAVAILABLE`** | **没法算** | **否，正常业务情形** |

> **沿用 `04-factor/07-factor-validation` §11.2：混淆两者会产生大量无意义告警。**

**`UNAVAILABLE` 的原因需进一步细分**，因为它们的业务含义不同：

| `reason_code` | 含义 |
|---|---|
| `INSUFFICIENT_HISTORY` | 成立时长不足 |
| `BENCHMARK_UNAVAILABLE` | REL 类整类不可算 |
| `RISK_FREE_RATE_UNAVAILABLE` | `R_f` 不可得 |
| `MAR_NOT_CONFIGURED` | **`mar_policy` 未配置** —— 注意这**不是** `mar_policy = ZERO`（后者是已配置状态，因子正常返回）。见 §4.3.7 |
| **`ZERO_MAX_DRAWDOWN`** | **窗口内无回撤 —— 这是"好消息型"不可用** |
| **`ZERO_DOWNSIDE_VOLATILITY`** | **窗口内从未下跌** |
| `ZERO_TRACKING_ERROR` | 完全复制基准 |
| `ZERO_VOLATILITY` | 净值无波动（通常是数据问题） |

#### 4.3.6 "好消息型"不可用需要特别的展示提示 ⚠️

> **沿用 `04-factor/03-factor-definition` §10：**

```
σ_d = 0 意味着【从未下跌】—— 业务上是优秀表现
MDD = 0 意味着【从未回撤】—— 同上

但数学上无法计算比率 → UNAVAILABLE

若不加说明，用户会以为"数据缺失"或"基金有问题"
```

**API 通过 `reason_message` 提供人可读的说明**，供展示层直接使用。

#### 4.3.7 `MAR_NOT_CONFIGURED` 与 `mar_policy = ZERO` 是相反的两件事（v1.1）

> **MAR Policy 已于 2026-08-27 定案**（`05-fund-evaluation/01` §16.3、`04-factor/03` §2.2.4）。

| 情形 | 响应 |
|---|---|
| `mar_policy = ZERO`（已配置） | **正常返回 Sortino**，`evaluation_policy_version` 非空 |
| `mar_policy` 未配置 | `status = UNAVAILABLE`，`reason_code = MAR_NOT_CONFIGURED` |

> **两者算出的 Sortino 数值会完全相同**（MAR 都是 0），但只有前者是有效结果。API **不得**在未配置时按 0 计算并正常返回 —— 那会让调用方拿到一个看起来完全正常、实则标尺从未被确认过的值。

> **定案后 `MAR_NOT_CONFIGURED` 的预期出现频率大幅下降**，但该枚举**必须保留** —— 它是配置遗漏的唯一可见信号。

---

### 4.4 GET /funds/{fund_id}/factors/{factor_id} — 单个因子值

字段同 §4.3 的单条元素。

---

### 4.5 GET /funds/{fund_id}/factors/{factor_id}/series — 因子历史序列

**Purpose**：Rolling 类因子的序列输出，或普通因子在不同 `as_of_date` 的历史值。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `date_from` / `date_to` | **业务日期语义** |
| `window` | 因子窗口 |
| `frequency` | 序列频率 |
| `as_of_date` | **PIT 语义** —— 见 §4.5.1 |

#### 4.5.1 两种"历史"必须区分 ⚠️

> **这是因子历史查询最易混淆的一处。**

```
情形 A：Rolling Sharpe 的序列
    → 每个点是"截至该日的 1Y Sharpe"
    → 由 date_from/to 选取序列区间

情形 B：同一个 1Y Sharpe 在不同时点的历史值
    → 也是一条序列，但每个点对应不同的 as_of_date

两者【数值上可能相同】，但语义不同：
    A 是因子本身的定义（Rolling 类因子）
    B 是同一因子在时间上的取值变化
```

**本域的处理**：

| 因子类型 | 序列语义 |
|---|---|
| **Rolling 类**（`F-STAB-005` 等） | 情形 A —— 因子定义本身就是序列 |
| **非 Rolling 类** | 情形 B —— 逐时点取值 |

> **`meta.series_semantics` 必须标明是 `ROLLING_FACTOR` 还是 `POINT_IN_TIME_HISTORY`。**

#### 4.5.2 Rolling 序列中的 `UNAVAILABLE` 点不中断序列

> **沿用 `04-factor/03-factor-definition`：** 某滚动点观测不足 → **该点** `UNAVAILABLE`，**不中断整个序列**；`UNAVAILABLE` 比例超阈值 → 整个序列标 `WARNING`。

```json
{
  "data": {
    "factor_id": "F-STAB-005",
    "window": "1Y",
    "series_status": "WARNING",
    "unavailable_ratio": 0.12,
    "points": [
      { "date": "2026-08-24", "value": 1.24, "status": "VALID" },
      { "date": "2026-08-23", "value": null, "status": "UNAVAILABLE", "reason": "INSUFFICIENT_HISTORY" }
    ]
  },
  "meta": { "series_semantics": "ROLLING_FACTOR" },
  "error": null
}
```

---

### 4.6 GET /factor-values — 批量查询

**Purpose**：一次取多只基金的多个因子 —— **这是最典型的查询形态**（`06-technology-stack` §7.1 评估维度）。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `fund_ids` | 逗号分隔或请求体传入 |
| `factor_ids` | 同上 |
| `window` | 统一窗口 |
| `as_of_date` | PIT |

#### 4.6.1 批量查询的规模上限

```
Max fund_ids × factor_ids = TBD
```

> 超出返回 `422` 并提示分批。

> **已定案 · 2026-08-27**：批量查询上限 = **500 个 `(fund, factor, window)` 组合**；超限改用 **POST**（请求体传参）。
>
> **依据**：①与 `API-2` 的 `page_size` 上限一致，保持全平台的批量规模口径统一；②**GET 的 URL 长度在数百个组合时已触顶** —— 多数网关与代理对 URL 长度的限制在 2~8KB，500 个三元组的编码已接近该量级。
>
> **POST 用于查询不违反 REST 语义**：这是「用请求体表达复杂查询条件」的标准做法，端点命名为 `/factors/batch-query` 以示其为查询而非创建。

#### 4.6.2 部分基金不可得时不整体失败 ⚠️

```
❌ 请求 50 只基金，其中 3 只无数据 → 整个请求 404
   → 消费者无法获得其余 47 只的结果

✅ 返回 47 只的结果 + 3 只的 UNAVAILABLE 说明
```

> 与 `04-factor` 的"单基金失败不影响其他基金"是同一原则。

---

## 5. Request / Response Convention

> 沿用 `01-api-overview` §5–§12。本域特有补充：

| 补充 | 说明 |
|---|---|
| **`raw_value` 与 `normalized_value` 成对返回** | §4.3.1 |
| **`normalized_value` 必须附 Peer Group 上下文** | §4.3.2 |
| **依赖 MAR 的因子必须附 `evaluation_policy_version`** | §4.3.3 |
| **`reason_code` 是 `INVALID` / `UNAVAILABLE` 时的必备字段** | §4.3.5 |
| **`meta.series_semantics`** | 序列端点必备（§4.5.1） |

---

## 6. Error Handling

| 场景 | HTTP | Code（建议） |
|---|---|---|
| 因子不存在 | 404 | `FACTOR_NOT_FOUND` |
| 基金不存在 | 404 | `FUND_NOT_FOUND` |
| 不支持的窗口 | 422 | `UNSUPPORTED_WINDOW` |
| 批量规模超限 | 422 | `BATCH_SIZE_EXCEEDED` |
| **因子值 `UNAVAILABLE`** | **200** | 不报错（§6.1） |
| **因子值 `INVALID`** | **200 + status** | 不报错，但须告警（§6.2） |
| 因子已 `RETIRED` 但查询历史值 | 200 | 正常返回（§6.3） |

### 6.1 `UNAVAILABLE` 不是错误

> **它是正常业务情形**（成立不足、除零等）。返回 200 + `status` + `reason`，而非 4xx。

```
❌ 3Y Sharpe 不可得 → 404
   → 消费者以为接口坏了
✅ 200 + status: UNAVAILABLE + reason: INSUFFICIENT_HISTORY
```

### 6.2 `INVALID` 同样返回 200，但语义不同

> `INVALID` 表示**算错了**，是系统问题。API 仍返回 200（请求本身合法），但：

| 要求 | 说明 |
|---|---|
| `status` 必须为 `INVALID` | 消费者据此判断不可使用 |
| **服务端须告警** | 沿用 `04-factor/07` §11.2 |
| `raw_value` 应为 `null` | 不返回不可信的数值 |

### 6.3 已下线因子的历史值仍可查

> **沿用 `04-factor/06-factor-versioning`：** `RETIRED` 的因子其定义必须仍可查，历史值仍可返回 —— 否则历史决策无法解释。

---

## 7. Examples

### 7.1 查询单基金的 RAP 类因子

**Request**

```
GET /api/v1/funds/F001/factors?category=RAP&window=1Y&as_of_date=2026-08-24
Authorization: Bearer <token>
```

**Response（200）**

```json
{
  "data": [
    {
      "factor_id": "F-RAP-001",
      "window": "1Y",
      "raw_value": 1.24,
      "normalized_value": 87.0,
      "status": "VALID",
      "risk_free_rate_ref": { "currency": "CNY", "tenor": "1Y", "effective_at": "2026-08-23", "version": 1, "rate_source_quality": "INTERPOLATED" }
    },
    {
      "factor_id": "F-RAP-002",
      "window": "1Y",
      "raw_value": null,
      "normalized_value": null,
      "status": "UNAVAILABLE",
      "reason_code": "MAR_NOT_CONFIGURED",
      "reason_message": "MAR 尚未在评价政策中配置，Sortino 无法计算"
    },
    {
      "factor_id": "F-RAP-003",
      "window": "1Y",
      "raw_value": null,
      "normalized_value": null,
      "status": "UNAVAILABLE",
      "reason_code": "ZERO_MAX_DRAWDOWN",
      "reason_message": "该窗口内基金未出现回撤，Calmar 比率无法计算——这是优秀表现，不是数据缺失"
    }
  ],
  "meta": {
    "as_of_date": "2026-08-24",
    "is_point_in_time": true,
    "factor_version": "v1",
    "peer_group_id": "PG-EQ-ACTIVE",
    "peer_group_version": "v3",
    "normalization_method": "PERCENTILE_RANK",
    "data_version": "..."
  },
  "error": null
}
```

> **注意第三条的 `reason_message`** —— 它把"好消息型不可用"翻译成人可读的说明，避免用户误判为数据问题（§4.3.6）。

### 7.2 错误示例：不支持的窗口

**Request**

```
GET /api/v1/funds/F001/factors/F-RAP-001?window=10Y
```

**Response（422）**

```json
{
  "data": null,
  "meta": { "request_id": "..." },
  "error": {
    "code": "UNSUPPORTED_WINDOW",
    "message": "Window not supported for this factor",
    "details": {
      "factor_id": "F-RAP-001",
      "requested_window": "10Y",
      "supported_windows": ["3M", "6M", "1Y", "3Y", "5Y"]
    }
  }
}
```

---

## 8. Security

| 项 | 说明 |
|---|---|
| Authentication | 沿用 `01-api-overview` §15.1 |
| Authorization | 全部为读操作，`Researcher` 及以上 |
| 敏感数据 | 本域不返回敏感项 |

---

## 9. Audit

> 本域**无写操作**（§2.1 不提供主动计算），仅记录访问日志。

---

## 10. Versioning

| 项 | 说明 |
|---|---|
| API 版本 | `/api/v1` |
| **`factor_version`** | 即 `Metric Version`（Strategy Version 第 1 项） |

### 10.1 因子版本升级不必然升 API 版本

> **沿用 `01-api-overview` §14.2：** 公式变更升 `factor_version`，但契约结构不变，API 仍是 v1。

### 10.2 新增因子是向后兼容的

> 因子目录新增条目属**新增数据**，不改变契约结构。但若新增的 Factor ID 出现在批量响应中，客户端须容忍未知 `factor_id`（`01` §14.5 的同类问题）。

---

## 11. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **第一阶段不提供主动计算 API** | 会绕过幂等键；临时结果不进快照 |
| D-2 | **不重述公式，只提供 `formula_reference`** | 两处维护必然发散 |
| D-3 | **`preference_direction` 保留四取值** | 简化会让 Tracking Error 被误按"越低越好"处理 |
| D-4 | `TARGET_RANGE` / `STRATEGY_DEPENDENT` 须返回上下文依赖 | 否则消费者无法使用该方向 |
| D-5 | **`boundary_conditions` 必须暴露** | 它是"为什么是 null"的答案 |
| D-6 | **`raw_value` 与 `normalized_value` 成对返回** | 缺任一都有问题 |
| D-7 | **`normalized_value` 必须附 Peer Group 上下文** | 否则不可跨基金比较 |
| D-8 | **依赖 MAR 的因子必须附 `evaluation_policy_version`** | 它是标识而非溯源 |
| D-9 | **IR 不返回 `risk_free_rate_ref`** | IR 不依赖 `R_f` |
| **D-10** | **`risk_free_rate_ref` 必含 `tenor` 与 `rate_source_quality`** | 前者用于验证期限匹配（同基金 1Y 与 3Y Sharpe 用不同 tenor），后者用于区分「基金确实差」与「`R_f` 是插出来的」 |
| D-10 | **`reason_code` 细分为八类** | 业务含义不同 |
| D-11 | **"好消息型"不可用须附人可读说明** | 否则被误判为数据缺失 |
| D-12 | Rolling 序列中的 `UNAVAILABLE` **不中断序列** | 沿用 `04-factor` |
| D-13 | **`series_semantics` 必须标明** | 两种"历史"语义不同 |
| D-14 | 批量查询部分失败**不整体失败** | 保留可得部分的价值 |
| D-15 | **`UNAVAILABLE` 与 `INVALID` 均返回 200** | 请求本身合法；但后者须告警 |
| D-16 | 已 `RETIRED` 因子的历史值仍可查 | 否则历史决策无法解释 |
| D-17 | **不提供基金间关系类因子的单基金端点** | Correlation 不是单只基金的属性 |

---

## 12. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 本域**不定义**因子公式与计算规则 | `04-factor` |
| C-2 | `preference_direction` 沿用上游四取值 | 上游术语表 |
| C-3 | 依赖 MAR 的 Factor Result 必须携带 `Evaluation Policy Version` | 上游 §5.5.2 |
| C-4 | `raw_value` 与 `normalized_value` 必须同时输出 | `04-factor/08` §2.3 |
| C-5 | 缺失一律 `UNAVAILABLE` + 原因，**不得返回 0 或哨兵值** | `04-factor/08` §3.3 |
| C-6 | 历史因子值必须满足 PIT | 上游 §4.2 ①-PIT |
| C-7 | 因子已下线后其定义与历史值仍须可查 | `04-factor/06` |

---

## 13. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~FTA-1~~ | ~~是否需要按需触发的 Factor 计算 API~~ —— **已定案**：第一阶段【不】提供按需触发的 Factor 计算 API | — | ✅ 2026-08-27 |
| FTA-2 | 本域各端点的最终路径与参数名 | 契约 | 接口评审 |
| ~~FTA-3~~ | ~~批量查询的规模上限与传参方式~~ —— **已定案**：批量查询上限 = 500 个 `(fund, factor, window)` 组合；超限改用 POST | — | ✅ 2026-08-27 |
| FTA-4 | `reason_message` 的文案是否需多语言 | 展示层 | 产品 |

---

## 14. Related Documents

| 关系 | 文档 |
|---|---|
| **本域总纲** | `10-api/01-api-overview.md` v1.0 |
| **业务语义来源** | `04-factor/`（全 8 份 v1.0–v1.1） |
| **上游约束** | `01-product/01-product-overview.md` v2.5（§4.2 ②、§5.5）、`02-business-requirements.md` v2.3（§14.2 Usage Matrix、§5.2.1） |
| **相关 API** | `02-fund-api`（评分消费因子）、`04-portfolio-api`（协方差矩阵） |

---

## 15. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.3** | 2026-08-27 | **第二批定案（2 项）**。`FTA-1` **不提供按需触发的 Factor 计算 API** —— 按需计算的结果没有快照归属，用「现在」会产生孤立值、用历史时点等于绕过版本治理；`FTA-3` 批量查询上限 500 组合、超限改用 POST（GET 的 URL 长度在数百个三元组时已触顶）。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.2** | 2026-08-27 | **Policy ⑥ 同步**。§4.2 因子定义响应新增 `effectiveness_summary`（最近一次 OOS 结论 + `peer_group_id` + `validation_policy_version`）；新增 §4.2.1 —— 三条约定并明确 **`latest_verdict = null`（未检验）不等于 `INVALID`（已判无效）**，两者的下游行为不同。原 §4.2.1~§4.2.4 顺移。详见 `TBD-resolution.md` Policy ⑥ | `04-factor/07-factor-validation` v1.2、`11-database/03-erd` v1.1 |
| **v1.1** | 2026-08-27 | **Policy ①② 同步**。<br/>**Policy ②**：新增 §4.3.7 —— `MAR_NOT_CONFIGURED` 与 `mar_policy = ZERO` 是相反的两件事，两者算出的 Sortino 数值相同但只有后者有效；API 不得在未配置时按 0 计算并正常返回。<br/>**Policy ①**。`risk_free_rate_ref` 补 `rate_source_quality` 字段（示例同步）；新增 D-10；补充说明 Beta 的 `R_f` 依赖是形式上的，但因 Alpha 与 Beta 出自同一回归，两者溯源必须一致。详见 `TBD-resolution.md` Policy ① | `04-factor/03-factor-definition` v1.2、`11-database/04` v1.5 |
| v1.0 | 2026-08-27 | 初始版本。**§2.1 第一阶段不提供主动计算 API** 及三条理由；**§4.1.2 `usage` 决定因子能出现在哪里**——Correlation 不提供单基金端点；**§4.2.1 不重述公式只提供引用**；**§4.2.2 `preference_direction` 四取值不得简化**并要求返回上下文依赖；§4.2.3 边界条件必须暴露；**§4.3.1–4.3.3 `raw_value`/`normalized_value` 成对返回、Peer Group 上下文、依赖 MAR 者须附 `evaluation_policy_version`**（标识 vs 溯源的区分）；**§4.3.4 IR 不返回 `risk_free_rate_ref`**；**§4.3.5 原不可用原因字段现统一为 `reason_code` 并细分八类**、**§4.3.6 "好消息型"不可用须附人可读说明**；**§4.5.1 两种"历史"语义的区分**与 `series_semantics`；§4.6.2 批量部分失败不整体失败；**§6.1–6.2 `UNAVAILABLE` 与 `INVALID` 均返回 200** | `04-factor` v1.0–v1.1、`10-api/01-api-overview.md` v1.0 |