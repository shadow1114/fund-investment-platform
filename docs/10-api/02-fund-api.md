# 基金 API · Fund API

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文暴露的域：**③ Fund Score · ④ Fund Universe**
> 业务语义来源：docs/05-fund-evaluation/（v1.0，全 5 份）、docs/03-data/（v1.0–v2.2）
> 本域上游：docs/10-api/01-api-overview.md（v1.0）
>
> **文档版本**：v1.4 ｜ **产品阶段**：第一阶段

---

## 1. Overview

### 1.1 本文档回答什么

> **基金相关的查询、评价与筛选能力如何对外暴露？**

### 1.2 全局约定引用 `01-api-overview`

> **本文档不重复定义**响应结构、错误模型、分页、排序、时间格式、百分比表示、认证授权 —— 全部沿用 `01-api-overview`。

### 1.3 本文档不定义业务规则 ⚠️

| 不定义 | 归属 |
|---|---|
| Peer Group 如何构建 | `05-fund-evaluation/01` §3 |
| Score 如何合成 | `05-fund-evaluation/02` |
| 排名与分位公式 | `05-fund-evaluation/03` |
| Tier 阈值 | `05-fund-evaluation/04` |
| Eligibility Rules | `05-fund-evaluation/05` |
| 基金数据模型 | `03-data/02-data-domain-model` |

---

## 2. Scope

| 能力 | 对应业务域 |
|---|---|
| **基金检索与详情** | `03-data` |
| **基金历史数据** | `03-data` |
| **基金评价结果** | `05-fund-evaluation/01` |
| **基金评分与归因** | `05-fund-evaluation/02` |
| **基金排名与分位** | `05-fund-evaluation/03` |
| **基金分层（Tier）** | `05-fund-evaluation/04` |
| **候选池（Fund Universe）** | `05-fund-evaluation/05` |

### 2.1 粒度是 Share Class ⚠️

> **沿用 `03-data/02-data-domain-model` §3.1 与 `05-fund-evaluation/01` §5：`Fund Share Class` 是最小单位。**

```
同一基金的 A / C / I 类份额费率不同 → 净值序列不同 → 评价结果不同
    → API 的 fund_id 指向 Share Class，不是"基金产品"
```

> **若未来需要产品级聚合视图，须作为新概念回上游登记**，不得在 API 层临时合并。

---

## 3. API List

| # | Endpoint | Method | 能力 |
|---|---|---|---|
| 3.1 | `/api/v1/funds` | GET | 基金检索 |
| 3.2 | `/api/v1/funds/{fund_id}` | GET | 基金详情 |
| 3.3 | `/api/v1/funds/{fund_id}/nav-series` | GET | 净值序列 |
| 3.4 | `/api/v1/funds/{fund_id}/evaluations` | GET | 评价结果 |
| 3.5 | `/api/v1/funds/{fund_id}/scores` | GET | 评分与归因 |
| 3.6 | `/api/v1/fund-rankings` | GET | 排名与分位 |
| 3.7 | `/api/v1/funds/{fund_id}/tier` | GET | 分层结果 |
| 3.8 | `/api/v1/fund-universes` | GET | 候选池列表 |
| 3.9 | `/api/v1/fund-universes/{universe_id}` | GET | 候选池详情（含入池/未入池原因） |
| 3.10 | `/api/v1/peer-groups/{peer_group_id}` | GET | Peer Group 构成与组内水平 |

> **具体路径待接口评审确认**（`<TBD-FA-1>`），本文档定义的是**能力与契约**，路径为建议。

---

## 4. API Details

### 4.1 GET /funds — 基金检索

**Purpose**：按条件检索基金，供研究人员做探索性查询。

**Authorization**：`Researcher` 及以上。

**Query Parameters**

| 参数 | 类型 | 说明 |
|---|---|---|
| `fund_name` | string | 模糊匹配 |
| `fund_type` | enum, multi | 沿用 `03-data` 的 `Fund Classification` 取值 |
| `management_company_id` | string | 管理人 |
| `manager_id` | string | 基金经理 |
| **`lifecycle_status`** | enum, multi | `NORMAL` / `SUSPENDED_SUBSCRIPTION` / `LIQUIDATED` / `MERGED` / `TRANSFORMED` |
| **`investment_eligibility`** | enum, multi | `FULLY_ELIGIBLE` / `HOLD_ONLY` / `LIMITED` / `EXIT_ONLY` / `NOT_TRADABLE` |
| `inception_date_from` / `_to` | date | 成立日范围 |
| `aum_min` / `aum_max` | number | 规模范围 |
| `as_of_date` | date | **PIT 语义**（`01` §11.2） |
| `page` / `page_size` / `sort` / `order` | — | `01` §7、§8 |

**Sortable Fields**：`inception_date`、`aum`、`fund_name`

**这是 Filtering，不是 Eligibility Rules** ⚠️

> 沿用 `01` §9.2、`05-fund-evaluation/05` §4：**本端点的检索结果不构成 `Fund Universe`。** 只有版本化的 `Eligibility Rules` 才产生 Universe（见 §4.8）。

**Response**

```json
{
  "data": [
    {
      "fund_id": "...",
      "fund_name": "...",
      "share_class": "A",
      "fund_classification": "EQUITY_ACTIVE",
      "management_company_id": "...",
      "inception_date": "2018-03-15",
      "lifecycle_status": "NORMAL",
      "investment_eligibility": "FULLY_ELIGIBLE"
    }
  ],
  "meta": {
    "as_of_date": "2026-08-24",
    "is_point_in_time": true,
    "data_version": "...",
    "pagination": { "page": 1, "page_size": 50, "total_items": 1240, "total_pages": 25 }
  },
  "error": null
}
```

---

### 4.2 GET /funds/{fund_id} — 基金详情

**Purpose**：获取单只基金的静态属性与当前状态。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `as_of_date` | 不提供 → 当前视图；提供 → 该时点的属性（PIT） |

**Response 字段**

| 字段 | 说明 | 来源 |
|---|---|---|
| `fund_id` / `fund_name` / `share_class` | 标识 | `03-data` |
| **`fund_classification`** + `classification_version` | 分类**及其版本** | `03-data` |
| `management_company_id` / `manager_ids` | 管理人与经理 | `03-data` |
| **`benchmark`** | 见 §4.2.1 | `03-data/01-data-source` §5 |
| `inception_date` | 成立日 | `03-data` |
| `lifecycle_status` | 生命周期状态 | `03-data/02-data-domain-model` §5 |
| **`investment_eligibility`** | 可投资性 | `02-business-requirements` §18.2 |
| **`fee_structure`** | 费率结构 **+ 包含关系** | `03-data`（`Fund Fee`）—— 见 §4.2.2 |

#### 4.2.2 `fee_structure` 必须返回包含关系（v1.2 新增）

> **定案 · 2026-08-27**：Policy ⑩ 要求每种费用显式声明是否已含于净值（`02-business-requirements` §21.7.1）。

```json
{
  "fee_structure": [
    {
      "expense_type": "MANAGEMENT_FEE",
      "expense_rate": 0.015,
      "included_in_nav": "TRUE",
      "included_in_backtest": false,
      "inclusion_source": "PROVIDER_SPEC"
    },
    {
      "expense_type": "SALES_SERVICE_FEE",
      "expense_rate": 0.004,
      "included_in_nav": "UNKNOWN",
      "included_in_backtest": false,
      "inclusion_source": "NOT_DECLARED"
    }
  ]
}
```

| # | 约定 |
|---|---|
| 1 | `included_in_nav` 是**字符串三值** `"TRUE"` / `"FALSE"` / `"UNKNOWN"`，**不是 JSON 布尔** —— 布尔无法表达 `UNKNOWN` |
| 2 | `included_in_backtest` 是 JSON 布尔（它确实只有两态），但为**推导值**，调用方不应据此反推 `included_in_nav` |
| 3 | 只返回费率而不返回包含关系是**错误的响应** —— 调用方无从判断该费率是否应在自己的计算中扣除 |

> **`included_in_nav: "UNKNOWN"` 与 `included_in_backtest: false` 同时出现不是矛盾** —— 它表示「不知道是否已含，因此选择不扣，且这一选择已披露」。这是 `08-backtest/05` §2.1 定义的处置。

#### 4.2.1 Benchmark 不在 API 层重新定义

> **沿用 `03-data/01-data-source` §5 的四层结构。**

```json
{
  "benchmark": {
    "benchmark_id": "...",
    "benchmark_name": "...",
    "benchmark_type": "SINGLE_INDEX",
    "mapping_version": "...",
    "components": null
  }
}
```

| 要点 | 说明 |
|---|---|
| **`mapping_version` 必须返回** | 基金转型会改变基准；历史查询须能判断用的哪版映射 |
| **Composite Benchmark 必须保留全部成分与权重** | 上游 §4.2 ①-B 约束 2 —— **不得简化为单一指数** |
| `benchmark_type` 取值 | 沿用 `03-data` |

> **简化 Composite Benchmark 的后果**：该基金的 Beta 被系统性低估、Alpha 被系统性高估（`04-factor/03-factor-definition`）。

#### 4.2.2 `lifecycle_status` 与 `investment_eligibility` 必须同时返回 ⚠️

> **两者是不同维度**（`02-business-requirements` §18.1）：

```
lifecycle_status       = 基金【处于什么状态】
investment_eligibility = 在该时点【能否交易】

"暂停申购" → 不可建仓、不可加仓，但【仍可持有、仍可减仓】
    → 单一 lifecycle_status 无法表达
```

> **只返回其一会导致消费者把暂停申购的持仓错误地强制清仓。**

---

### 4.3 GET /funds/{fund_id}/nav-series — 净值序列

**Purpose**：获取复权净值时序，供展示与自行分析。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| **`date_from` / `date_to`** | **业务日期语义**（`01` §11.2） |
| `frequency` | `DAILY` / `WEEKLY` / `MONTHLY` |
| **`as_of_date`** | **PIT 语义** —— 见 §4.3.1 |
| `nav_type` | `ADJUSTED`（默认） / `RAW` |

#### 4.3.1 `date_from/to` 与 `as_of_date` 同时使用时的语义 ⚠️

> **这是本域最容易混淆的一处。**

```
date_from=2022-01-01, date_to=2022-12-31, as_of_date=2023-01-15

含义：返回【2022 全年】的净值，但只包含【截至 2023-01-15 已披露且当时的版本】

→ 若某日净值在 2023-02 才被修订，返回的是【修订前】的值
```

| 参数 | 作用 |
|---|---|
| `date_from` / `date_to` | 选**哪一段**时间的数据（业务日期） |
| `as_of_date` | 选**当时能看到的哪一版**（PIT + version） |

> **两者正交，不可互相替代。** 不提供 `as_of_date` 时返回最新版本，并标注 `is_point_in_time: false`。

#### 4.3.2 复权口径必须返回（v1.1 定案）

> **定案 · 2026-08-27**：`TBD-DN-3` 关闭，`adjustment_convention` 固定为 `BACKWARD`（`03-data/05-data-normalization` §5.3.1、`TBD-resolution.md` Policy ③）。

```json
{
  "meta": {
    "nav_type": "ADJUSTED",
    "adjustment_convention": "BACKWARD",
    "adjustment_rule_version": "v2"
  }
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `nav_type` | `ADJUSTED`（默认） / `RAW` | 由请求参数决定 |
| `adjustment_convention` | **固定 `BACKWARD`** | 全平台统一，不随请求变化 |
| `adjustment_rule_version` | 版本号 | 规则变更不追溯改写，**同一响应内的不同时段可能对应不同版本** |

> **`adjustment_convention` 恒为 `BACKWARD` 仍必须返回** —— 它是数值可比性的前提，不能靠调用方查文档推断。

#### 4.3.3 `nav_adjusted` 缺失时的响应约定

> **分红或拆分记录缺失时该点位的复权净值不可得**（`03-data/05` §5.3.2），API **不得回填原始净值**。

```json
{
  "date": "2024-03-15",
  "nav": null,
  "reason_code": "DISTRIBUTION_RECORD_MISSING"
}
```

| # | 约定 |
|---|---|
| 1 | `nav_type=ADJUSTED` 时，不可得的点位 `nav` 返回 `null` 并给出 `reason_code`，**不跳过该日期** —— 跳过会让调用方误以为当日无交易 |
| 2 | `nav_type=RAW` 时不受影响，原始净值永远可得 |
| 3 | `meta` 中给出本次结果集的 `unavailable_count`，便于调用方判断序列可用性 |

---

### 4.4 GET /funds/{fund_id}/evaluations — 评价结果

**Purpose**：暴露 `05-fund-evaluation/01` 定义的 Evaluation Result。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `evaluation_period` | `1M` / `3M` / `6M` / `1Y` / `3Y` / `5Y` |
| `as_of_date` | PIT |

**Response**

```json
{
  "data": {
    "fund_id": "...",
    "evaluation_period": "1Y",
    "as_of_date": "2026-08-24",
    "evaluation_status": "PARTIAL",
    "evaluation_profile": "ACTIVE_EQUITY",
    "data_completeness": { "available": 9, "expected": 12 },
    "factor_results": [
      {
        "factor_id": "F-RAP-001",
        "window": "1Y",
        "raw_value": 1.24,
        "normalized_value": 87.0,
        "status": "VALID",
        "direction": "HIGHER_IS_BETTER"
      },
      {
        "factor_id": "F-RAP-002",
        "window": "1Y",
        "raw_value": null,
        "normalized_value": null,
        "status": "UNAVAILABLE",
        "reason_code": "MAR_NOT_CONFIGURED"
      }
    ]
  },
  "meta": {
    "is_point_in_time": true,
    "peer_group_id": "...",
    "peer_group_version": "...",
    "evaluation_policy_version": "...",
    "factor_version": "...",
    "data_version": "..."
  },
  "error": null
}
```

#### 4.4.1 `evaluation_status` 四态

| 状态 | 含义 |
|---|---|
| `NOT_ELIGIBLE` | 未通过准入检查 |
| `COMPLETED` | 全部要求的 Factor 可得 |
| `PARTIAL` | 部分 `UNAVAILABLE`，其余可用 |
| **`FAILED`** | 计算异常 —— **须告警** |

> **`NOT_ELIGIBLE`（不该评）与 `FAILED`（评坏了）必须区分**（`05-fund-evaluation/01` §14.1）。

#### 4.4.2 `data_completeness` 是必备字段 ⚠️

> **沿用上游术语表：基于 3 个指标的 85 分与基于 12 个指标的 85 分，可信度完全不同。**

它是**输出的一部分，不是可选的附加信息**。API 不得省略。

#### 4.4.3 本端点不返回 Total Score

> **沿用 `05-fund-evaluation/01` §1.2：评价的产出不含总分，合成属 §4.5。**

---

### 4.5 GET /funds/{fund_id}/scores — 评分与归因

**Purpose**：暴露 `05-fund-evaluation/02` 的 Fund Score 及其完整归因链。

**Response**

```json
{
  "data": {
    "fund_id": "...",
    "evaluation_period": "1Y",
    "as_of_date": "2026-08-24",
    "total_score": 85.2,
    "sub_scores": {
      "return_score": 88.0,
      "risk_score": 79.5,
      "risk_adjusted_score": 90.1,
      "stability_score": 82.3,
      "relative_performance_score": 86.4
    },
    "attribution": [
      {
        "factor_id": "F-RAP-001",
        "window": "1Y",
        "raw_value": 1.24,
        "normalized_value": 87.0,
        "direction": "HIGHER_IS_BETTER",
        "weight": 0.3333,
        "weight_source": "PROFILE_FIXED_V1",
        "effectiveness_verdict": "VALID",
        "weighted_contribution": 29.0,
        "sub_score": "risk_adjusted_score"
      },
      {
        "factor_id": "F-RAP-003",
        "window": "1Y",
        "raw_value": 0.91,
        "status": "EXCLUDED",
        "exclusion_reason": "FACTOR_INEFFECTIVE",
        "effectiveness_verdict": "INVALID",
        "weight": 0.0
      },
      {
        "factor_id": "F-RAP-002",
        "status": "UNAVAILABLE",
        "reason_code": "MAR_NOT_CONFIGURED",
        "original_weight": 0.10,
        "reallocated_to": [
          { "factor_id": "F-RAP-001", "delta_weight": 0.06 },
          { "factor_id": "F-RAP-003", "delta_weight": 0.04 }
        ]
      }
    ],
    "data_completeness": { "available": 9, "expected": 12 },
    "score_status": "PARTIAL"
  },
  "meta": {
    "peer_group_id": "...",
    "peer_group_version": "...",
    "scoring_policy_version": "...",
    "evaluation_policy_version": "...",
    "factor_version": "...",
    "data_version": "..."
  },
  "error": null
}
```

#### 4.5.1 五子分命名固定，不得更改 ⚠️

> **沿用上游 §4.2 ③-S**：`Return / Risk / Risk-Adjusted / Stability / Relative Performance`。API 层不得重命名（`01` §4.3）。

#### 4.5.2 归因必须含 `raw_value` 与被排除因子

> **沿用 `05-fund-evaluation/02` §10.3、§10.4：**

| 要求 | 理由 |
|---|---|
| **必须含 `raw_value`** | 只有标准化值时用户看不懂"87.0 分"从何而来 |
| **被排除的因子也要留痕** | 否则无法解释"为什么 Sharpe 的贡献比配置的权重高" |

#### 4.5.3 权重来源必须标注（v1.4 新增）

> **定案 · 2026-09-08**：M1 权重来自 `PROFILE_FIXED_V1`；有效性检验只决定指标是否具备评分资格，不生成权重。

| 字段 | 取值 | 说明 |
|---|---|---|
| **`weight_source`** | `PROFILE_FIXED_V1` / `OPTIMIZED` | M1 恒为前者；后者仅为未来扩展 |
| **`effectiveness_verdict`** | `VALID` / `INVALID` | 该因子在本次检验中的判定 |

**两条要求**：

| # | 要求 |
|---|---|
| 1 | **`INVALID` 因子必须出现在归因中**，`status = EXCLUDED`、`exclusion_reason = FACTOR_INEFFECTIVE`、`weight = 0` —— 否则无法回答「为什么这只基金的 Calmar 没影响分数」 |
| 2 | `EXCLUDED`（因子无效，全体基金一致）与 `UNAVAILABLE`（该基金数据不可得）是**不同状态**，不得混用 |

> **两者的区别对用户是可见的**：`UNAVAILABLE` 意味着「这只基金缺数据」，`EXCLUDED` 意味着「这个指标对所有基金都不用了」。前者是这只基金的问题，后者是评分体系的决定。

#### 4.5.4 检验未产出时不返回 Score

| 情形 | 响应 |
|---|---|
| 有效性检验已产出 | 正常返回 |
| **检验尚未产出** | `score_status = VALIDATION_PENDING`，`total_score = null` |

> **不得按等权临时返回一个分数** —— 「先按等权上线，等检验出来再调」与「未经检验就拍权重」完全等价（`05-fund-evaluation/02` §8.4.2）。

#### 4.5.5 `total_score` 是无量纲相对量 ⚠️

> **沿用上游 §5.2 与 `01-api-overview` §24.1。**

```
85.2 的含义 = "在这个 Peer Group 内排前约 15%"
    ≠ 任何形式的收益率
```

| 禁止 | 后果 |
|---|---|
| 把 `total_score` 作为 `μ` 输入优化器 | 量纲错误，`λ` 失去意义 |
| 跨 Peer Group 比较 Score | **默认不可比**（上游 §4.2 ③） |

> **响应中必须携带 `peer_group_id`** —— 没有它，Score 无法被正确解读。

---

### 4.6 GET /fund-rankings — 排名与分位

**Purpose**：暴露 `05-fund-evaluation/03` 的排名结果。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| **`peer_group_id`** | **必填** —— 排名必须在组内 |
| `evaluation_period` | 必填 |
| `ranking_metric` | 默认 `TOTAL_SCORE` |
| `as_of_date` | PIT |
| `page` / `page_size` | 分页 |

**Response**

```json
{
  "data": [
    {
      "fund_id": "...",
      "rank": 5,
      "n_effective": 120,
      "peer_group_size": 200,
      "percentile": 96.6,
      "total_score": 85.2,
      "confidence_flag": "NORMAL"
    }
  ],
  "meta": {
    "peer_group_id": "...",
    "peer_group_version": "...",
    "ranking_metric": "TOTAL_SCORE",
    "ranking_policy_version": "...",
    "percentile_convention": "(N - Rank) / (N - 1)",
    "tie_method": "...",
    "as_of_date": "2026-08-24",
    "is_point_in_time": true
  },
  "error": null
}
```

#### 4.6.1 `n_effective` 与 `peer_group_size` 必须同时返回 ⚠️

> **沿用 `05-fund-evaluation/03` §6.2：`N` 是有效参与数，不是组规模。**

```
组内 200 只，其中 80 只该指标 UNAVAILABLE
    → n_effective = 120
    → "120 只里的第 5 名"与"200 只里的第 5 名"含义不同
```

#### 4.6.2 `percentile_convention` 必须返回

> **三种常见约定结果不同**（`05-fund-evaluation/03` §7.2）。不返回约定，消费者无法正确解读 96.6 这个数字。

#### 4.6.3 历史排名必须是 PIT 排名

> **沿用提示词 §27.7 与 `08-backtest/03` §8：**

```
❌ 用今天的 Peer Group 与今天的 Scoring Policy 重算 2022 年的 Rank
   → 三重污染：组构成（幸存者偏差）+ 政策版本（版本前视）+ 数据版本
✅ 返回 2022 年当时固化的排名快照
```

**API 必须在 `meta` 中标注该排名是**快照读取**还是**重建产物**：

```json
{ "meta": { "ranking_source": "SNAPSHOT" } }
```

---

### 4.7 GET /funds/{fund_id}/tier — 分层结果

**Purpose**：暴露 `05-fund-evaluation/04` 的 `Fund Tier`。

#### 4.7.1 `Fund Tier` 不是 `Fund Classification` ⚠️

> **沿用 `05-fund-evaluation/04` §1.2 —— 这是本域必须防止的一处命名混淆。**

| | `fund_classification` | **`fund_tier`** |
|---|---|---|
| 回答 | 这是**什么类型**的基金 | 这只基金**评价得怎么样** |
| 取值 | `EQUITY_ACTIVE` 等 | **`A+` / `A` / `B` / `C` / `D`** |
| 归属 | `03-data` | `05-fund-evaluation/04` |

> **API 字段名必须保持 `fund_tier`，不得命名为 `classification`。**

**Response**

```json
{
  "data": {
    "fund_id": "...",
    "fund_tier": "A+",
    "percentile": 96.6,
    "total_score": 85.2,
    "rank": 5,
    "n_effective": 120,
    "peer_group_context": {
      "peer_group_id": "...",
      "peer_group_size": 200,
      "median_sharpe": 0.62,
      "median_max_drawdown": 0.184
    },
    "data_completeness": { "available": 9, "expected": 12 },
    "confidence_flag": "NORMAL"
  },
  "meta": {
    "classification_policy_version": "...",
    "tier_thresholds": { "A+": 95, "A": 80, "B": 50, "C": 20 },
    "as_of_date": "2026-08-24"
  },
  "error": null
}
```

#### 4.7.2 `peer_group_context` 是强制字段 ⚠️

> **沿用 `02-business-requirements` §16.3.1：`Fund Tier` 必须与该 `Peer Group` 的绝对水平同屏展示** —— 至少含组内 Sharpe 中位数与 Maximum Drawdown 中位数。

```
仅返回 Tier 而不返回组内绝对水平，【视为违反业务约束】
```

**理由**：分位分层意味着无论该组整体质量如何，永远有 5% 被评为 `A+`。没有组内水平，读者无法判断"`A+` 在这一组意味着什么"。

#### 4.7.3 Tier 不是投资建议

> `A+` 不意味着"应该买"，`D` 不意味着"应该卖"（`02-business-requirements` §16.4）。**API 文档与字段说明须防止该误读。**

---

### 4.8 GET /fund-universes — 候选池

**Purpose**：暴露 `05-fund-evaluation/05` 的 `Fund Universe`。

#### 4.8.1 Universe 由版本化的 Eligibility Rules 产生

> **不是本 API 的查询结果**（`05-fund-evaluation/05` §4）。本端点**查询已产生的 Universe**，不即时生成。

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `strategy_id` | 所属策略 |
| `decision_at` | 决策时点 |
| `eligibility_rules_version` | 准入规则版本 |

**Response（列表）**

```json
{
  "data": [
    {
      "universe_id": "...",
      "strategy_id": "...",
      "decision_at": "2026-08-24",
      "universe_strategy": "B",
      "member_count": 42,
      "eligibility_rules_version": "...",
      "scoring_policy_version": "..."
    }
  ],
  "meta": {},
  "error": null
}
```

#### 4.8.2 策略 A 下评分字段为空是正常的

> **沿用 `05-fund-evaluation/05` §7.2：** 采用「Eligibility only」策略时，`scoring_policy_version` 与评分字段为 `null`，**不构成留痕缺失**。

**API 文档须明确这一点**，否则消费者会误判为数据缺失。

---

### 4.9 GET /fund-universes/{universe_id} — 候选池详情

**Purpose**：返回成员列表**及被排除基金的原因**。

**Response**

```json
{
  "data": {
    "universe_id": "...",
    "decision_at": "2026-08-24",
    "universe_strategy": "B",
    "members": [
      {
        "fund_id": "...",
        "selection_status": "SELECTED",
        "total_score": 85.2,
        "rank": 5,
        "percentile": 96.6,
        "fund_tier": "A+",
        "investment_eligibility": "FULLY_ELIGIBLE",
        "passed_conditions": [
          { "condition": "total_score >= 70", "actual": 85.2, "result": "PASS" },
          { "condition": "fund_tier in [A+, A]", "actual": "A+", "result": "PASS" }
        ],
        "failed_conditions": []
      }
    ],
    "excluded": [
      {
        "fund_id": "...",
        "selection_status": "REJECTED",
        "passed_conditions": [],
        "failed_conditions": [
          { "condition": "total_score >= 70", "actual": 62.1, "result": "FAIL", "gap": 7.9 },
          { "condition": "fund_tier in [A+, A]", "actual": "B", "result": "FAIL" }
        ]
      }
    ]
  },
  "meta": { "eligibility_rules_version": "...", "scoring_policy_version": "..." },
  "error": null
}
```

#### 4.9.1 被排除的基金必须返回，且须列出**全部**未通过条件 ⚠️

> **沿用 `05-fund-evaluation/05` §14.3、§14.4：**

| 要求 | 理由 |
|---|---|
| **被排除的同样记录** | 若 90% 基金因同一条件被排除，说明该条件可能设置不当 —— 只有留痕才能发现 |
| **不短路，列出全部未通过条件** | 否则无法回答"放宽某条件能新增多少基金" |

> **只返回 `selection_status: REJECTED` 而不列出原因，等于给了结论没给依据。**

#### 4.9.2 `HOLD_ONLY` 的基金在池内且标注不可建仓

> **沿用 `05-fund-evaluation/05` §9.2：** 不得因不可建仓而移出 Universe —— 那会导致已持仓被优化器强制清仓。

---

### 4.10 GET /peer-groups/{peer_group_id} — Peer Group

**Purpose**：返回该时点的组构成与组内绝对水平。

**Response 要点**

| 字段 | 说明 |
|---|---|
| `peer_group_id` + **`peer_group_version`** | 标识与版本 |
| `effective_at` | 生效时点 |
| `member_count` | 成员数 |
| `members` | 成员列表（分页） |
| **`group_level_metrics`** | 组内 Sharpe / MDD 中位数等 |

#### 4.10.1 Peer Group 独立于 Fund Score

> **沿用上游 §7.2：** Peer Group 的构成不依赖 Score 或 Universe。**API 不得提供"按 Score 筛选 Peer Group 成员"的能力** —— 那会在使用层面诱导出循环依赖。

---

## 5. Request / Response Convention

> 全部沿用 `01-api-overview` §5–§12。本文档特有的补充：

| 补充 | 说明 |
|---|---|
| **`meta.peer_group_id` 是评分/排名/分层类响应的必备字段** | 没有它，相对量无法解读 |
| **`meta.ranking_source`** | `SNAPSHOT` / `REBUILT`（§4.6.3） |
| **`data_completeness` 是评价/评分类响应的必备字段** | §4.4.2 |

---

## 6. Error Handling

| 场景 | HTTP | Code（建议） |
|---|---|---|
| 基金不存在 | 404 | `FUND_NOT_FOUND` |
| `as_of_date` 格式错误 | 400 | `INVALID_DATE_FORMAT` |
| **`as_of_date` 早于基金成立日** | 422 | `FUND_NOT_EXIST_AT_DATE` |
| 缺少必填的 `peer_group_id` | 400 | `MISSING_REQUIRED_PARAMETER` |
| 评价结果不存在（该时点未计算） | 404 | `EVALUATION_NOT_FOUND` |
| **Peer Group 样本量不足**（`n_effective < 30`） | 200 + `INSUFFICIENT_SAMPLE` | 不报错，但**不返回 rank / percentile / tier**（§6.1） |
| **Peer Group 仅 1 只基金** | 200 + `percentile: null` | 分位无意义（`05-fund-evaluation/03` §7.3） |
| 无权限访问该 Universe | 403 | `FORBIDDEN` |

### 6.1 样本量不足不是错误，但横截面派生量不返回 ⚠️（v1.2 定案）

> **定案 · 2026-08-27**：`MIN_PEER_GROUP_SIZE = 30`（`02-business-requirements` §7.3.1、`TBD-resolution.md` Policy ⑤）。

```
❌ 组内仅 8 只基金 → 返回 422
   → 消费者无法获得任何信息

❌ 返回 rank / percentile / tier 并标 confidence_flag: LOW_SAMPLE
   → 值仍在响应里，调用方代码会照常读取它
   → 标记只在展示层可见

✅ 返回 200，横截面派生量为 null，附 *_status = INSUFFICIENT_SAMPLE 与 n_effective
   → 调用方被迫显式处理缺失
```

**响应形态**：

```json
{
  "fund_id": "F001",
  "rank": null,
  "percentile": null,
  "tier": null,
  "n_effective": 17,
  "ranking_status": "INSUFFICIENT_SAMPLE",
  "classification_status": "INSUFFICIENT_SAMPLE",
  "raw_factors": { "sharpe_1y": 1.24 }
}
```

| # | 约定 |
|---|---|
| 1 | **原始因子值照常返回** —— 样本不足只影响横截面派生量 |
| 2 | **`n_effective` 必须返回** —— 17 与 29 对调用方的含义不同 |
| 3 | 三个 `*_status` **各自独立** —— 同一组内不同 Factor 的 `n_effective` 可能不同 |
| 4 | HTTP 状态码仍是 **200** —— 这是正常业务情形，不是错误 |

> **`confidence_flag` 的去留**：它继续用于表达**其他**低置信情形（数据完整度偏低等），但**不再承担样本量不足的表达** —— 后者由 `*_status` 与 `n_effective` 精确表达。

---

## 7. Examples

### 7.1 查询历史某时点的基金排名

**Request**

```
GET /api/v1/fund-rankings?peer_group_id=PG-EQ-ACTIVE&evaluation_period=1Y&as_of_date=2022-03-31&page=1&page_size=20
Authorization: Bearer <token>
X-Request-ID: 8f3c...
```

**Response（200）**

```json
{
  "data": [
    { "fund_id": "F001", "rank": 1, "n_effective": 512, "peer_group_size": 800, "percentile": 100.0, "total_score": 93.7, "confidence_flag": "NORMAL" },
    { "fund_id": "F002", "rank": 2, "n_effective": 512, "peer_group_size": 800, "percentile": 99.8, "total_score": 92.1, "confidence_flag": "NORMAL" }
  ],
  "meta": {
    "peer_group_id": "PG-EQ-ACTIVE",
    "peer_group_version": "v3",
    "ranking_metric": "TOTAL_SCORE",
    "ranking_policy_version": "v1",
    "percentile_convention": "(N - Rank) / (N - 1)",
    "tie_method": "COMPETITION_RANK",
    "ranking_source": "SNAPSHOT",
    "as_of_date": "2022-03-31",
    "is_point_in_time": true,
    "scoring_policy_version": "v1",
    "data_version": "...",
    "pagination": { "page": 1, "page_size": 20, "total_items": 512, "total_pages": 26 }
  },
  "error": null
}
```

> **注意 `scoring_policy_version: v1`** —— 这是 2022 年当时的版本，不是今天的。若返回今天的版本号，说明该排名是用今天的规则重算的（版本前视，`08-backtest/03` §6）。

### 7.2 错误示例：查询早于成立日的时点

**Request**

```
GET /api/v1/funds/F999/evaluations?evaluation_period=3Y&as_of_date=2015-01-01
```

**Response（422）**

```json
{
  "data": null,
  "meta": { "request_id": "8f3c..." },
  "error": {
    "code": "FUND_NOT_EXIST_AT_DATE",
    "message": "Fund did not exist at the requested as_of_date",
    "details": {
      "fund_id": "F999",
      "inception_date": "2018-03-15",
      "requested_as_of_date": "2015-01-01"
    }
  }
}
```

---

## 8. Security

| 项 | 说明 |
|---|---|
| **Authentication** | 沿用 `01-api-overview` §15.1 |
| **Authorization** | 全部为读操作，`Researcher` 及以上 |
| **敏感数据** | 本域不返回费率协议、客户信息等敏感项 |

### 8.1 Universe 的资源级授权

> **不同策略的 Universe 可能有可见性差异** —— 属 `TBD-API-7` 的资源级授权模型。

---

## 9. Audit

| 操作 | 是否需审计 |
|---|---|
| 基金查询、评价、评分、排名查询 | 否（读操作，仅记录访问日志） |
| **Universe 查询** | 视资源级授权模型而定 |

> 本域**无写操作**，因此不涉及 `NFR-SEC-004` 的操作审计。

---

## 10. Versioning

| 项 | 说明 |
|---|---|
| API 版本 | `/api/v1` |
| **业务版本** | 通过 `meta.versions` 暴露，与 API 版本分离（`01` §14.2） |

### 10.1 业务枚举新增值的影响

> 若 `05-fund-evaluation` 新增 Tier 档位或 `03-data` 新增 `lifecycle_status`，属**新增枚举值** —— 兼容性取决于客户端（`01` §14.5）。

---

## 11. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | `fund_id` 指向 **Share Class** | 沿用 `03-data` 的最小单位 |
| D-2 | **不重新定义 Benchmark**，且返回 `mapping_version` | 历史查询须能判断用的哪版映射 |
| D-3 | **Composite Benchmark 不得简化** | 简化会使 Beta 低估、Alpha 高估 |
| D-4 | `lifecycle_status` 与 `investment_eligibility` **必须同时返回** | 两者是不同维度 |
| D-5 | **`date_from/to` 与 `as_of_date` 正交** | 前者选时间段，后者选版本 |
| D-6 | **`data_completeness` 是必备字段** | 3 个指标的 85 分与 12 个指标的不同 |
| D-7 | 评价端点**不返回 Total Score** | 合成属评分端点 |
| D-8 | 归因必须含 `raw_value`、**被排除因子**与 `weight_source` | 否则无法解释权重与配置不符；`EXCLUDED`（因子无效）与 `UNAVAILABLE`（该基金缺数据）须区分 |
| D-9 | **评分/排名/分层响应必须含 `peer_group_id`** | 相对量脱离组无法解读 |
| D-10 | **`n_effective` 与 `peer_group_size` 同时返回** | 两者含义不同 |
| D-11 | **`percentile_convention` 必须返回** | 三种约定结果不同 |
| D-12 | 历史排名须标注 `ranking_source` | 快照与重建可信度不同 |
| D-13 | **`fund_tier` 字段名不得写作 `classification`** | 防止与 `Fund Classification` 混淆 |
| D-14 | **`peer_group_context` 是强制字段** | 仅返回 Tier 视为违反业务约束 |
| D-15 | **被排除基金必须返回且列出全部未通过条件** | 支撑"放宽条件能新增多少"的分析 |
| D-16 | **不提供"按 Score 筛选 Peer Group 成员"** | 会在使用层面诱导循环依赖 |
| D-17 | **样本量不足返回 200，但横截面派生量为 `null` + `*_status = INSUFFICIENT_SAMPLE`** | 它是正常业务情形，不报错；但返回带低置信标记的值会被调用方代码照常读取 |

---

## 12. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 本域**不定义**任何业务规则或公式 | `01-api-overview` §1.3 |
| C-2 | **`Fund Tier` 必须与组内绝对水平同屏** | `02-business-requirements` §16.3.1 |
| C-3 | **`Peer Group` 必须独立于 `Fund Score`** | 上游 §7.2 |
| C-4 | `total_score` 不得以可被误用为收益率的方式暴露 | 上游 §5.2 |
| C-5 | Composite Benchmark 必须保留全部成分与权重 | 上游 §4.2 ①-B |
| C-6 | 历史查询必须返回当时的版本引用 | `01-api-overview` §11.4 |
| C-7 | 被排除基金的原因必须记录并可查询 | `02-business-requirements` §17.5 |
| C-8 | 五子分命名固定，不得重命名 | 上游 §4.2 ③-S |
| C-9 | `HOLD_ONLY` 不得移出 Universe | `05-fund-evaluation/05` §9.2 |

---

## 13. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| FA-1 | **本域各端点的最终路径与参数名** | 契约 | 接口评审 |
| FA-2 | `fund_name` 模糊匹配的规则（前缀 / 全文 / 拼音） | 检索体验 | 产品 |
| FA-3 | 是否需要产品级（跨 Share Class）聚合视图 | 粒度扩展 | 产品 + 投研 |
| FA-4 | Universe 的资源级可见性规则（= `TBD-API-7`） | 授权 | 产品 + 治理 |
| FA-5 | 批量查询（一次取多只基金的多个指标）的端点形态 | 性能 | 接口评审 |

---

## 14. Related Documents

| 关系 | 文档 |
|---|---|
| **本域总纲** | `10-api/01-api-overview.md` v1.0 |
| **业务语义来源** | `05-fund-evaluation/`（全 5 份 v1.0）、`03-data/`（v1.0–v2.2） |
| **上游约束** | `01-product/01-product-overview.md` v2.5（§4.2 ③、④、§5.2、§7）、`02-business-requirements.md` v2.3（§16.3.1、§17.5、§18） |
| **相关 API** | `03-factor-api`（因子明细）、`04-portfolio-api`（消费 Universe） |

---

## 15. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.5** | 2026-09-08 | `weight_source` 第一版枚举改为 `PROFILE_FIXED_V1`；保留 `VALIDATION_PENDING`，明确 OOS 检验决定使用资格而非权重 | Plan-2 设计 v1.0、`05-fund-evaluation/02` v1.3 |
| **v1.4** | 2026-08-27 | **Policy ⑥ 同步（后由 2026-09-08 决策替代权重来源）**。§4.5 归因新增 `weight_source` 与 `effectiveness_verdict`，示例补一条 `EXCLUDED` 因子；新增 §4.5.3 —— `INVALID` 因子须在归因中留痕，`EXCLUDED`（因子无效，全体一致）与 `UNAVAILABLE`（该基金缺数据）是不同状态；新增 §4.5.4 —— 检验未产出时 `score_status = VALIDATION_PENDING` 且不返回分数。M1 当前 `weight_source` 固定为 `PROFILE_FIXED_V1`。 | `05-fund-evaluation/02` v1.1 |
| **v1.3** | 2026-08-27 | **Policy ⑤ 同步**。§6.1 改写 —— 样本量不足（`n_effective < 30`）返回 200 但**横截面派生量为 `null`**，附 `*_status = INSUFFICIENT_SAMPLE` 与 `n_effective`；原始因子值照常返回；`confidence_flag` 不再承担样本量不足的表达。D-17 同步。详见 `TBD-resolution.md` Policy ⑤ | `05-fund-evaluation/03` v1.1、`05-fund-evaluation/04` v1.1 |
| **v1.2** | 2026-08-27 | **Policy ⑩ 同步**。新增 §4.2.2 —— `fee_structure` 必须返回包含关系；`included_in_nav` 是**字符串三值**而非 JSON 布尔（布尔表达不了 `UNKNOWN`）；只返回费率不返回包含关系是错误响应。详见 `TBD-resolution.md` Policy ⑩ | `02-business-requirements` v2.5 §21.7.1 |
| **v1.1** | 2026-08-27 | **`TBD-DN-3` 关闭后的同步**。§4.3.2 定案 —— `adjustment_convention` 固定为 `BACKWARD` 且仍须返回；新增 §4.3.3 —— `nav_adjusted` 不可得时 `nav` 返回 `null` 并给出原因码（现统一字段名为 `reason_code`），**不跳过日期、不回填原始净值**（跳过会被误读为当日无交易，回填会制造虚假暴跌）。详见 `TBD-resolution.md` Policy ③ | `03-data/05-data-normalization` v1.2 |
| v1.0 | 2026-08-27 | 初始版本。粒度定为 Share Class；**§4.2.1 Benchmark 须返回 `mapping_version` 且 Composite 不得简化**；**§4.2.2 `lifecycle_status` 与 `investment_eligibility` 必须同时返回**；**§4.3.1 `date_from/to` 与 `as_of_date` 正交**的语义澄清；§4.4.2 `data_completeness` 为必备字段；**§4.5.2 归因须含 `raw_value` 与被排除因子**、§4.5.3 `total_score` 是无量纲相对量；**§4.6.1 `n_effective` 与 `peer_group_size` 须同时返回**、§4.6.2 `percentile_convention` 必须返回、**§4.6.3 历史排名须标注 `ranking_source`**；**§4.7.1 `fund_tier` 不是 `fund_classification`**、**§4.7.2 `peer_group_context` 为强制字段**；**§4.9.1 被排除基金须列出全部未通过条件**；**§4.10.1 不提供按 Score 筛选 Peer Group 成员**；**§6.1 样本量不足不是错误** | `05-fund-evaluation` v1.0、`03-data` v2.2、`10-api/01-api-overview.md` v1.0 |