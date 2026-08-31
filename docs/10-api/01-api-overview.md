# API 总览 · API Overview

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文定位：支撑层 · 对外接口契约
> 非功能需求：docs/01-product/05-non-functional-requirements.md（v1.0）§3.1、§3.5
> 架构依赖：docs/02-architecture/02-service-architecture.md（v1.3）、04-integration-architecture.md（v1.2）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **API 层整体的契约约定是什么？**

### 1.2 API 层的定位

```
Client
   ↓
API Layer            ← 本域
   ↓
Application Service
   ↓
Domain Service       ← 05-fund-evaluation / 06-portfolio / 07-return-risk / 08-backtest
   ↓
Data Layer           ← 03-data
```

### 1.3 API 层不是什么 ⚠️

| API 层**不是** | 归属 |
|---|---|
| 数据访问层 | `03-data` |
| **业务规则的定义处** | 各业务域 |
| 量化方法论的定义处 | `04-factor` / `07-return-risk` |
| 数据库表结构文档 | `11-database` |
| 回测算法文档 | `08-backtest` |

> **本域只暴露能力，不定义能力。**

### 1.4 契约先于实现，且与协议无关

> **接口契约的定义权属本域，承载技术属 `02-architecture`**（`06-technology-stack` §7.1）。

```
API 框架选型 = TBD-TECH-2（技术评审）
    → 本域的契约定义【不依赖】该选型
    → 无论最终采用何种框架或协议，契约不变
```

### 1.5 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 各域 API 的具体端点 | `02` / `03` / `04` / `05` |
| 服务如何拆分与部署 | `02-architecture` |
| 表结构与索引 | `11-database` |
| 监控与告警 | `12-operations` |
| 权限的治理流程 | `13-governance` |

---

## 2. API Consumers

| 消费者 | 主要使用的 API | 对应角色 |
|---|---|---|
| **投研分析师工作台** | Fund / Factor | `Researcher` |
| **组合管理界面** | Portfolio | `Portfolio Manager` |
| **策略研究工具** | Factor / Backtest | `Quant Researcher` |
| **运维控制台** | 各域的状态查询 | `Operations` |
| **外部执行系统对接** | Portfolio（调仓指令交付与回报接收） | 系统账号 |

> 角色定义沿用 `05-non-functional-requirements` `NFR-SEC-001`，本域**不新增角色**。

---

## 3. API Categories

| 类别 | 文档 | 回答的问题 |
|---|---|---|
| **Fund API** | `02-fund-api` | 有哪些基金？它们被如何评价与筛选？ |
| **Factor API** | `03-factor-api` | 有哪些因子？它们的值与定义是什么？ |
| **Portfolio API** | `04-portfolio-api` | 可以做出、评估与管理哪些组合决策？ |
| **Backtest API** | `05-backtest-api` | 如何模拟并评估一个历史投资过程？ |

### 3.1 类别边界

| API | 负责 | **不负责** |
|---|---|---|
| Fund | 基金查询、评价、评分、排名、分层、筛选结果 | 因子计算、组合决策 |
| Factor | 因子定义、因子值、因子历史、因子元数据 | 评分合成（属 Fund API） |
| Portfolio | 组合、配置、优化、风险预算、约束、再平衡 | 回测 |
| Backtest | 回测配置、执行、结果、报告、偏差检查 | 实盘决策 |

### 3.2 API 之间不互相调用

> **提示词 §54 的澄清：**

```
Fund API → Factor API → Portfolio API → Backtest API
    这是【逻辑依赖】，不是【调用关系】

它们共享同一 Domain / Application Layer
    → 不通过 HTTP 互相调用
```

---

## 4. 命名约定

### 4.1 资源命名

| 规则 | 说明 |
|---|---|
| **资源用名词复数** | `/funds`、`/factors`、`/portfolios`、`/backtests` |
| **禁止动词式路径** | ❌ `/getFunds`、`/calculateFactor` |
| **业务操作用子资源** | `/portfolios/{id}/optimizations`、`/backtests/{id}/runs` |
| 路径分隔用 `-` | `/fund-scores` 而非 `/fund_scores` |

### 4.2 参数与字段命名

| 对象 | 约定 |
|---|---|
| **Query 参数** | `snake_case`（如 `as_of_date`、`page_size`） |
| **JSON 字段** | `snake_case` |
| **Enum 值** | `UPPER_SNAKE_CASE`（如 `FULLY_ELIGIBLE`、`APPROVED_FOR_USE`） |
| **标识符字段** | 一律以 `_id` 结尾 |
| **版本字段** | 一律以 `_version` 结尾 |

### 4.3 Enum 值必须与业务域一致 ⚠️

> **API 层不得重命名业务枚举。**

```
❌ 业务域定义 HOLD_ONLY，API 暴露为 "hold-only" 或 "SUSPENDED"
✅ 原样暴露 HOLD_ONLY
```

**理由**：重命名会使 API 消费者与业务文档之间产生一层需要人工维护的映射，且该映射在文档中不可见。

---

## 5. Response Convention

### 5.1 统一结构

```json
{
  "data": {},
  "meta": {},
  "error": null
}
```

| 字段 | 说明 |
|---|---|
| `data` | 业务数据；错误时为 `null` |
| `meta` | 分页、版本引用、时点信息（§5.2） |
| `error` | 错误对象；成功时为 `null` |

### 5.2 `meta` 必须携带版本引用 ⚠️

> **这是全平台可复现性（`NFR-REPRO-001`）在 API 层的落实。**

```json
{
  "meta": {
    "as_of_date": "2026-08-24",
    "data_version": "...",
    "versions": {
      "factor_version": "...",
      "scoring_policy_version": "...",
      "peer_group_version": "..."
    },
    "is_point_in_time": true
  }
}
```

> **返回一个数值而不告知它是"用哪一版规则、哪一版数据算出来的"，该数值不可解释也不可复现。**

### 5.3 不创建第二套响应格式

> 全部 API 使用同一结构，**包括错误响应**。不得出现某些端点直接返回裸数组。

---

## 6. Error Convention

### 6.1 统一结构

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Fund not found",
    "details": {}
  }
}
```

### 6.2 错误类别

| 类别 | HTTP | 说明 |
|---|---|---|
| **Validation Error** | 400 / 422 | 参数格式或取值不合法 |
| **Authentication Error** | 401 | 未认证 |
| **Authorization Error** | 403 | 无权限 |
| **Resource Not Found** | 404 | 资源不存在 |
| **Conflict** | 409 | 状态冲突（如重复提交、状态不允许） |
| **Business Rule Violation** | 422 | 请求合法但违反业务规则 |
| **Processing Error** | 500 | 处理过程失败 |
| **Service Unavailable** | 503 | 依赖不可用或限流 |

### 6.3 Validation Error 与 Business Rule Violation 必须区分 ⚠️

> **两者都返回 4xx，但消费者的处置完全不同。**

| | Validation Error | Business Rule Violation |
|---|---|---|
| 含义 | **请求本身不合法** | 请求合法，但**业务上不允许** |
| 例 | `as_of_date` 格式错误 | 优化不可行（`INFEASIBLE`） |
| 消费者处置 | 修正参数重试 | **不应重试** —— 需要业务侧介入 |

> **混为一谈会导致客户端对不可行的优化反复重试。**

### 6.4 具体 Error Code

```
Error Code 全集 = TBD
```

> **本域给出类别与结构，具体码值待接口评审确认。**

`<TBD-API-1: Error Code 全集及其与业务状态的映射，待接口评审确认>`

### 6.5 `details` 必须携带可操作信息

> **只给 `code` 与 `message` 不足以定位问题。**

```json
{
  "code": "OPTIMIZATION_INFEASIBLE",
  "message": "No feasible solution under current constraints",
  "details": {
    "binding_constraints": ["max_fund_weight", "equity_class_min"],
    "conflicting_pair": ["min_holdings", "max_fund_weight"]
  }
}
```

> 沿用 `06-portfolio/03` §10.2：**紧约束清单是关键诊断信息** —— 它同样应通过 API 暴露。

---

## 7. Pagination

### 7.1 统一采用 `page` / `page_size`

| 参数 | 说明 | 默认 |
|---|---|---|
| `page` | 页码，从 **1** 开始 | 1 |
| `page_size` | 每页条数 | `TBD` |

```json
{
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total_items": 1240,
      "total_pages": 25
    }
  }
}
```

### 7.2 分页必须有确定性排序 ⚠️

> **没有确定性排序的分页会导致漏项与重复项。**

```
若排序不确定（如两只基金 Score 相同且无次级规则）
    → 第 1 页与第 2 页之间可能【重复】或【遗漏】某只基金
```

**要求**：每个列表 API 必须有**默认排序**，且排序键必须能唯一确定顺序（末位追加 `fund_id` 等唯一键作为 tie-breaker）。

> 与 `05-fund-evaluation/03` §8.4 的"排名确定性"是同一条原则。

> **已定案 · 2026-08-27**：默认 `page_size` = **50**，上限 **500**。
>
> **依据**：横截面查询的典型规模是一个 Peer Group（数十至数百只基金），50 覆盖首屏、500 覆盖整组。
>
> **上限不设更高的理由**：单次返回超过 500 条会与 **W2 的 P95 目标冲突**（`06-technology-stack` §4.6.2）—— 分页的作用之一就是把大结果集的成本切分开。需要全量数据的场景应使用批量导出而非调大 `page_size`。

---

## 8. Sorting

| 参数 | 说明 |
|---|---|
| `sort` | 排序字段 |
| `order` | `asc` / `desc`（默认 `desc`） |

```
GET /api/v1/funds?sort=total_score&order=desc
```

### 8.1 可排序字段必须显式列出

> **不得允许按任意字段排序** —— 某些字段（如嵌套的归因明细）排序无意义，且会成为性能风险点。

各 API 在其文档中列出 `sortable_fields`。

---

## 9. Filtering

### 9.1 五类过滤

| 类型 | 约定 | 示例 |
|---|---|---|
| **Exact** | `field=value` | `fund_type=EQUITY` |
| **Range** | `field_min` / `field_max` | `aum_min=100000000` |
| **Date** | `date_from` / `date_to` | `date_from=2026-01-01` |
| **Enum** | 取值必须来自业务枚举 | `status=ACTIVE` |
| **Multi-value** | 逗号分隔 | `fund_type=EQUITY,BOND` |

### 9.2 过滤不等于筛选 ⚠️

> **这是一处必须澄清的边界。**

| | **API Filtering** | **Eligibility Rules** |
|---|---|---|
| 性质 | 查询便利 | **策略配置的一部分** |
| 是否版本化 | 否 | **是**（`Strategy Version` 第 3 项） |
| 是否产生 Universe | **否** | **是** |
| 归属 | 本域 | `05-fund-evaluation/05` |

> 沿用 `05-fund-evaluation/05` §4：**UI 上的一次筛选不构成 `Fund Universe`。** API 的 Filtering 属于前者。

---

## 10. Date / Time

### 10.1 格式约定

| 类型 | 格式 | 示例 |
|---|---|---|
| **Date** | `YYYY-MM-DD` | `2026-08-24` |
| **DateTime** | ISO 8601 带时区 | `2026-08-24T09:30:00+08:00` |
| **Timezone** | `TBD` | 见 §10.2 |

> **已定案 · 2026-08-27**：系统时区 = **UTC 存储 + ISO 8601 带偏移返回**；**业务日期**按基金计价市场的本地日历。
>
> **两类时间必须分开**：
>
> | 类型 | 例子 | 处理 |
> |---|---|---|
> | **时刻**（Timestamp） | `available_at`、`ingested_at` | UTC 存储，返回带偏移的 ISO 8601 |
> | **业务日期**（Date） | `effective_at`、`as_of_date` | 本地日历的日期，**无时区概念** |
>
> **把业务日期当作时刻处理会产生日界错误**：`2026-01-02` 这个估值日在 UTC 与 UTC+8 下可能落在不同的日期上，而它本身表达的是「基金在其本地市场的哪一个交易日」，与时区无关。
>
> **本条是 §10.3（`available_at` 定为 `TIMESTAMPTZ`）的全局化**。

### 10.2 业务日期用 Date，运维时刻用 DateTime ⚠️

> **两者的混用是本域最容易出错的一处。**

| 字段 | 类型 | 理由 |
|---|---|---|
| `as_of_date` / `decision_at` / `effective_at` | **Date** | 业务时点，与交易日对齐 |
| `available_at` | **见 §10.3** | |
| `created_at` / `run_timestamp` / `validation_timestamp` | **DateTime** | 物理时刻，用于运维排查 |

> 沿用 `04-factor/08` §2.1：**Calculation Time 不是业务时点，不得用于 PIT 判定。**

### 10.3 `available_at` 确定为 `TIMESTAMPTZ`（v1.1 定案）

> **定案 · 2026-08-27**：上游 `TBD-17` 关闭（`01-product-overview` v2.6、`TBD-resolution.md` Policy ④），本域此前的「暂按 DateTime」转为正式约定。

**类型**：`TIMESTAMPTZ`，ISO 8601 带时区偏移，秒级精度。

```json
{ "available_at": "2026-01-02T18:03:00+08:00" }
```

**三条理由**：

| # | 理由 |
|---|---|
| 1 | 定案后 `available_at` 首选取自 `provider_available_at`（推送时刻），**同一天内的先后有实际意义** —— 10:03 推送与 18:03 推送对盘中决策是不同的 |
| 2 | `03-data/01-data-source` §11.5 AV-3 明确要求「精度到时刻而非日期」 |
| 3 | 带时区是必需的 —— 跨市场数据源的推送时刻不在同一时区，裸 `TIMESTAMP` 会在跨境场景下产生日界歧义 |

> **与 `as_of_date` 的区别**：请求参数 `as_of_date` 是**日期**（PIT 语义，见 §11.2），响应字段 `available_at` 是**时刻**。二者粒度不同不是不一致 —— 前者是决策口径（「按哪天的信息集」），后者是数据事实（「这条数据几点可得」）。

#### 10.3.1 伴随字段 `availability_quality`

> 与 `available_at` **成对出现**，缺一不可。

| 值 | 含义 |
|---|---|
| `EXACT` | 取自供应商推送时刻 |
| `DERIVED` | 取自公告时刻（推送时刻不可得） |
| `INFERRED` | 取自平台落库时刻（前两者皆不可得） |

**对 API 契约的两条要求**：

| # | 要求 |
|---|---|
| 1 | 凡返回 `available_at` 的响应，**必须同时返回 `availability_quality`** —— 单独给出时刻会让调用方无从判断其可信度 |
| 2 | 带 `as_of_date` 的列表端点须在 `meta` 中给出**本次结果集的 quality 分布**（见 §11.x 与 `10-api/05-backtest-api` 的 bias-check 响应） |

```json
{
  "meta": {
    "as_of_date": "2026-01-02",
    "availability_quality_distribution": {
      "EXACT": 0.62,
      "DERIVED": 0.31,
      "INFERRED": 0.07
    }
  }
}
```

---

## 11. Point-in-Time

> **这是本域最重要的横切关注点。**

### 11.1 两种查询语义必须区分 ⚠️

| | **Current View** | **Historical View** |
|---|---|---|
| 回答 | **现在**是什么样 | **当时**是什么样 |
| 参数 | 无 `as_of_date` | 有 `as_of_date` |
| 数据 | 最新版本 | `available_at ≤ as_of_date` 的最大 `version` |
| `meta.is_point_in_time` | `false` | **`true`** |

### 11.2 `as_of_date` 的语义必须精确定义 ⚠️

> **同一个 `as_of_date=T` 可以有两种完全不同的解读。**

```
解读 A（PIT 语义）：返回"在 T 时点能看到的"数据
    → 按 available_at ≤ T 过滤
    → 用于回测复现、历史决策审计

解读 B（业务日期语义）：返回"描述 T 这一天的"数据
    → 按 effective_at = T 过滤
    → 用于"查 2026-08-24 的净值"
```

**本域的定案**：

| 参数 | 语义 | 用途 |
|---|---|---|
| **`as_of_date`** | **解读 A（PIT）** | 历史状态复现 |
| **`business_date` / `date_from` / `date_to`** | **解读 B（业务日期）** | 时序数据查询 |

> **两者不可混用。** 使用 `as_of_date` 查净值序列会得到"截至 T 时点已披露的全部净值"，而非"T 这一天的净值"。

### 11.3 默认不带 `as_of_date` 时返回当前视图

> **且必须在 `meta` 中标注 `is_point_in_time: false`** —— 消费者不得把当前状态误认为历史状态（提示词 §22）。

### 11.4 历史查询必须返回当时的版本引用

```json
{
  "meta": {
    "as_of_date": "2022-03-31",
    "is_point_in_time": true,
    "versions": {
      "scoring_policy_version": "v1",
      "peer_group_version": "..."
    }
  }
}
```

> **不能只返回历史值而不返回当时的规则版本** —— 否则消费者无法判断该值是"当时的规则算的"还是"今天的规则重算的"（`08-backtest/03` §6）。

### 11.5 API 不得让客户端传入未来信息

> 沿用提示词 §24 与 `08-backtest`：

```
❌ 客户端传入 T 之后的数据参与 T 时点的计算
✅ PIT 校验由服务端强制，客户端无法绕过
```

**这与 `08-backtest/03` §13.4「检测必须在数据访问层强制」是同一条原则。**

---

## 12. 数值表示约定

### 12.1 百分比统一用小数

> **全项目统一，不得逐 API 变化。**

```
0.1523  表示 15.23%
```

| 规则 | 说明 |
|---|---|
| **表示** | 小数（`0.1523`），**不是** `15.23` |
| **字段命名** | 百分比类字段不加 `_pct` 后缀（因为统一是小数） |
| **展示层转换** | 由客户端负责乘 100 |

> **理由**：小数形式可直接参与运算（如 `w'μ`），而百分数形式需要先除 100，混用会在客户端产生难以察觉的 100 倍误差。

### 12.2 金额必须带币种与精度

```json
{
  "market_value": {
    "amount": "1234567.89",
    "currency": "CNY"
  }
}
```

| 规则 | 说明 |
|---|---|
| **`amount` 用字符串** | 避免 JSON 浮点精度丢失 |
| **必须带 `currency`** | 组合可能跨币种（`06-portfolio/01` §7.1 `base_currency`） |
| **精度与小数位** | `TBD` |

> **不得只写 `amount` 而不说明其业务含义** —— 是市值、成本还是净值？字段名须自明（`market_value` / `cost_basis` / `nav`）。

> **已定案 · 2026-08-27**：金额 **`NUMERIC(20,4)`**；权重、比率、百分比一律**小数**（非百分数），精度 **`NUMERIC(12,8)`**。见 `TBD-resolution-2.md` Policy A §A.2。
>
> **两条既有原则的具体化**：①`11-database/01` §5.1「金融数值禁止浮点」；②`10-api/01` §12.1「百分比统一用小数」。
>
> **「小数而非百分数」在 API 层尤其重要** —— 同一份响应内出现 `0.0742`（收益率）与 `15`（权重百分比）会让调用方在每个字段上都要确认一次量纲。**展示层乘 100 是渲染，不是传输约定。**

### 12.3 收益必须指明类型

> **不得只用 `return` 而不说明含义**（提示词 §17）。

| 字段 | 含义 | 定义来源 |
|---|---|---|
| `period_return` | 区间收益 | `03-data/05-data-normalization` §6 |
| `cumulative_return` | 累计收益 | `04-factor`（`F-RET-002`） |
| `annualized_return` | 年化收益（**252 交易日**） | `04-factor`（`F-RET-001`） |
| `excess_return` | 超额收益（须指明对比对象） | `04-factor`（`F-REL-001`） |

### 12.4 `null` 与 `0` 必须区分 ⚠️

> **这是全平台"缺失不得转 0"原则在 API 层的落实。**

```json
{
  "sharpe_ratio": null,
  "sharpe_ratio_status": "UNAVAILABLE",
  "sharpe_ratio_reason": "INSUFFICIENT_HISTORY"
}
```

| 值 | 含义 |
|---|---|
| **数值** | 算出来了 |
| **`null` + `status`** | **没算出来** —— 必须附状态与原因 |
| **`0`** | **算出来就是 0** —— 是有效数值 |

> **只返回 `null` 而不附状态是不够的** —— 消费者无法区分"数据不足"与"计算失败"（`04-factor/07` §11.2）。

---

## 13. HTTP Status Codes

| 码 | 使用场景 |
|---|---|
| **200** | 查询成功 |
| **201** | 资源创建成功（如 Backtest 创建） |
| **202** | **异步任务已接受**（§16） |
| **204** | 删除成功，无返回体 |
| **400** | 请求格式错误 |
| **401** | 未认证 |
| **403** | 无权限 |
| **404** | 资源不存在 |
| **409** | 状态冲突 |
| **422** | **业务规则违反** |
| **429** | 限流 |
| **500** | 服务端错误 |
| **503** | 依赖不可用 |

### 13.1 `422` 用于业务规则违反，不是参数错误

> 沿用 §6.3：参数格式错误用 `400`，参数合法但业务不允许用 `422`。

---

## 14. Versioning

### 14.1 URL 版本

```
/api/v1/...
```

### 14.2 API Version 与 Domain Version 分离 ⚠️

> **业务域升版本不必然导致 API 升版本**（提示词 §49）。

```
Scoring Policy v1 → v2（业务规则变了）
    → API 契约不变（字段结构相同）
    → API 仍是 v1，但响应的 meta.scoring_policy_version 变了
```

**判定**：只有**契约结构**变化（字段增删、语义改变）才升 API 版本。

### 14.3 向后兼容规则

| 变更 | 是否兼容 | 处理 |
|---|---|---|
| **新增可选字段** | ✅ 兼容 | 直接发布 |
| 新增可选参数 | ✅ 兼容 | 直接发布 |
| **删除字段** | ❌ 不兼容 | 须走 Deprecation |
| **修改字段语义** | ❌ **不兼容且最危险** | 见 §14.4 |
| 修改字段类型 | ❌ 不兼容 | 须走 Deprecation |
| 新增枚举值 | ⚠️ **见 §14.5** | |

### 14.4 修改字段语义比删除字段更危险 ⚠️

```
删除字段 → 客户端立即报错 → 问题被发现
修改语义 → 客户端照常解析 → 【静默出错】

例：percentage 从 15.23 改为 0.1523
    → 客户端不报错，但所有展示值缩小 100 倍
```

**要求**：语义变更**必须**升 API 版本，不得在同版本内进行。

### 14.5 新增枚举值的兼容性取决于客户端

> **服务端认为兼容，客户端可能不。**

```
新增 Investment Eligibility 状态 EXIT_ONLY
    → 客户端若用穷举 switch 处理，会落入 default 分支
    → 行为取决于其 default 实现
```

**要求**：枚举字段的文档必须声明"客户端应容忍未知值"，且服务端**新增枚举值前须通知消费者**。

### 14.6 具体版本策略

```
Versioning Strategy = TBD
```

> **已定案 · 2026-08-27**：版本演进 = **URL 路径版本**（`/api/v1/`），并存版本数上限 **2**。
>
> **依据**：①现有全部端点已使用该形式，改为 Header 协商需要重做全部路由；②**路径版本对调试与缓存友好** —— URL 即完整标识，日志、CDN 缓存键、浏览器书签都能直接区分版本；Header 协商则需要额外配置 `Vary` 头，且日志中看不出调用的是哪一版。
>
> **并存 2 版的理由**：允许一个完整的迁移窗口（旧版 + 新版），但不允许长期维护三代以上 —— 那会使每个变更都要在多处同步。
>
> **废弃期见 `API-10`**。

---

## 15. Authentication & Authorization

### 15.1 Authentication

```
Authentication Mechanism = TBD
```

> **沿用 `NFR-SEC-002`：系统必须对所有访问进行身份认证；具体机制属 `02-architecture`。**

**本域的契约要求**：无论采用何种机制，认证信息通过标准 HTTP 头传递，失败返回 `401`。

`<TBD-API-6: 认证机制（Bearer Token / OAuth2 / mTLS）— 属 `02-architecture`，本域待其定案后同步>`

### 15.2 Authorization 沿用五类角色

> **不新增角色**（`NFR-SEC-001`）：

| 角色 | 可读 | 可写 | 特有权限 |
|---|---|---|---|
| `Researcher` | 基金数据、Factor、Score、排名、Universe | 探索性筛选配置 | — |
| `Portfolio Manager` | 全部分析数据、组合、决策 | 组合策略配置 | **Approve / Reject / Override** |
| `Quant Researcher` | 全部分析数据、回测 | 评分方案、准入规则、策略配置 | 提交策略进入 `VALIDATING` |
| `Operations` | 数据状态、任务状态 | 任务重试、数据修复触发 | — |
| `Administrator` | 全部 | 用户与角色配置 | 授权管理 |

### 15.3 两条硬性权限边界 ⚠️

> **沿用 `NFR-SEC-001` SEC-1 / SEC-2：**

| # | 约束 | API 层的落实 |
|---|---|---|
| **SEC-1** | **Approve / Reject / Override 仅限 `Portfolio Manager`** | 决策复核类端点强制该角色 |
| **SEC-2** | **策略配置变更权限与决策放行权限必须分离** | 同一 token 不得同时具备两类权限 |

> **SEC-2 是职责分离要求，不是技术偏好** —— 同一人不应既定规则又批准其产出。

### 15.4 授权粒度

| 层级 | 说明 |
|---|---|
| **Operation-level** | 该角色能否执行该操作 |
| **Resource-level** | 该角色能否访问该资源实例（如某个组合） |

```
Resource-level Authorization Model = TBD
```

`<TBD-API-7: 资源级授权模型（组合归属、数据可见范围），待产品与治理确认>`

---

## 16. Sync vs Async

### 16.1 划分原则

| 类型 | 模式 | 示例 |
|---|---|---|
| **查询类** | **Sync** | 基金查询、因子查询、历史查询 |
| **短计算** | Sync | 单只基金的指标查询 |
| **长任务** | **Async** | **组合优化、回测执行、批量重算** |

### 16.2 Async 模式

```
POST /api/v1/backtests/{id}/runs
    → 202 Accepted
    → { "data": { "operation_id": "...", "status": "RUNNING" } }

GET /api/v1/operations/{operation_id}
    → 200 { "data": { "status": "...", "progress": ..., "result_ref": "..." } }
```

### 16.3 Async 阈值

```
Async Threshold = TBD
```

> **不自行设定生产 SLA**（提示词 §39）。`NFR-PERF-001` / `002` / `003` 的分位数目标同为 `TBD`。

`<TBD-API-8: Sync/Async 的划分阈值与各端点的响应时间目标（关联 `TBD-NFR-1`、`TBD-NFR-2`），待产品与运维确认>`

### 16.4 Operation 是独立资源

> **它有自己的生命周期，不隶属于业务资源。**

```
/api/v1/operations/{operation_id}
```

**理由**：优化与回测都产生 Operation，用统一的资源查询状态，避免每类业务各自定义一套轮询端点。

---

## 17. Idempotency

### 17.1 需要幂等的操作

| 操作 | 理由 |
|---|---|
| **Backtest 执行** | 重复提交会产生重复运行与资源浪费 |
| **Portfolio Optimization** | 同上 |
| **Rebalancing 指令生成** | **重复生成可能导致重复下单** |

### 17.2 幂等键

```
Idempotency-Key: <client-generated-uuid>
```

| 规则 | 说明 |
|---|---|
| 客户端生成 | 同一逻辑请求使用同一 key |
| 服务端缓存结果 | 相同 key 的重复请求返回首次结果，**不重复执行** |
| 有效期 | `TBD` |

### 17.3 业务层已有天然幂等键 ⚠️

> **沿用 `04-integration-architecture` §4.4：**

```
批量计算阶段的幂等键 = (decision_at, Strategy Version 组合)
    → 重复执行同一键不产生重复或冲突结果
```

**两层幂等的关系**：

| 层 | 键 | 作用 |
|---|---|---|
| **API 层** | `Idempotency-Key` | 防止**网络重试**导致的重复提交 |
| **业务层** | `(decision_at, Strategy Version)` | 防止**同一决策**被重复计算 |

> **两者不可互相替代** —— API 层的键防的是传输问题，业务层的键防的是逻辑重复。

> **推荐默认 · 2026-08-27**：`Idempotency-Key` 有效期 **24 小时**；冲突返回 **409** 并附原请求摘要。
>
> **24 小时的依据**：覆盖一个完整的决策日与重试窗口。更长会使键空间持续增长，更短则跨日重试会失效。
>
> **冲突时返回原请求摘要**（而非仅返回 409）—— 使调用方能判断「是我重复提交了」还是「键被别人用了」。

---

## 18. Request ID & Observability

### 18.1 追踪头

| Header | 说明 |
|---|---|
| **`X-Request-ID`** | 客户端可提供；未提供时服务端生成 |
| `X-Trace-ID` | 跨服务追踪 |

> 响应必须回显 `X-Request-ID`，且**错误响应的 `details` 中应包含它**，便于消费者报障时定位。

### 18.2 不在本域描述基础设施

> 本域**不描述**消息中间件、存储引擎、容器编排等基础设施 —— 它们属 `02-architecture` 与 `12-operations`，且不影响 API 契约。

---

## 19. Audit

### 19.1 必须留审计轨迹的操作

> **沿用 `NFR-SEC-004`：全部用户操作必须记入不可篡改的审计日志。**

| 操作 | 特别理由 |
|---|---|
| **Portfolio 创建 / 修改** | 策略配置变更 |
| **Portfolio Optimization 执行** | 产生决策输入 |
| **Rebalancing 生成与交付** | 产生调仓指令 |
| **决策 Approve / Reject / Override** | **投资决策责任边界**（SEC-1） |
| **Backtest 创建 / 执行** | 策略验证依据 |
| 策略配置变更 | 影响全部下游 |

### 19.2 审计记录字段

| 字段 | 说明 |
|---|---|
| `caller` | 用户或服务账号 |
| `timestamp` | 操作时刻 |
| `resource` | 资源标识 |
| `operation` | 操作类型 |
| `request_id` | 关联请求 |
| `result` | 成功 / 失败 |
| **`versions`** | 涉及的全部版本引用 |

### 19.3 `Override` 必须记录理由

> 沿用上游 §7.1.1：PM 修改权重必须完整留痕，否则原则六（可复现）与原则七（可追溯）将被破坏。

**API 层的落实**：`Override` 类端点的请求体**必须**含 `reason` 字段，缺失则 `422`。

---

## 20. API Data Consistency

| API 类型 | 返回什么 |
|---|---|
| **查询 API**（无 `as_of_date`） | 当前可用的数据 |
| **历史 API**（有 `as_of_date`） | 对应时点的数据 |
| **Backtest API** | **Backtest Run 的快照** |

### 20.1 历史结果必须引用快照，而非实时重查 ⚠️

> **沿用提示词 §42：避免"今天重新查询 API 导致过去的 Backtest Result 发生变化"。**

```
❌ Backtest Result 中只存 fund_id，展示时实时查询基金当前信息
   → 基金改名、分类调整后，历史回测的展示内容发生变化
   → 历史结果"活"了

✅ Backtest Result 引用当时的快照
   → 展示的是当时的名称、分类、权重
```

**这与 `08-backtest/01` §22.1 的快照可复现性是同一问题在 API 层的表现。**

---

## 21. API Lifecycle

```
Draft  →  Active  →  Deprecated  →  Removed
```

### 21.1 Deprecated API 必须声明三项

| 项 | 说明 |
|---|---|
| **`Deprecated Date`** | 标记为废弃的日期 |
| **`Replacement`** | 替代端点 |
| **`Removal Date`** | 计划移除日期 |

> 响应中通过 `Deprecation` 与 `Sunset` 标准头声明。

```
Deprecation Policy = TBD
```

> **推荐默认 · 2026-08-27**：废弃期 = **2 个版本或 6 个月，取长者**；通知方式为响应头 `Deprecation` + `Sunset`（RFC 8594）。
>
> **「取长者」的理由**：仅按版本数会在快速迭代期给调用方过短的窗口；仅按时间会在迭代缓慢时无谓地延长维护成本。

---

## 22. Performance & Rate Limiting

```
Response Time Target = TBD（关联 NFR-PERF-001）
Pagination Limit     = TBD
Max Request Size     = TBD
Rate Limit           = TBD
```

> **本域不自行设定生产 SLA**（提示词 §39）。

`<TBD-API-11: 限流策略与配额，待运维确认>`

---

## 23. 外部执行系统对接（回应 `INT-4`）⚠️

> **`04-integration-architecture` `INT-4`（外部执行系统的回报格式与对接方式）归 `10-api` + `03-data`。本节给出 API 侧的契约要求。**

### 23.1 方向与职责

> 沿用 `04-integration-architecture` §2.6：

```
平台 → 外部执行系统：交付 Rebalancing Recommendation（调仓指令）
外部执行系统 → 平台：回报成交（Fill）或持仓状态
```

### 23.2 平台不执行交易

> **上游 §6 Out of Scope：平台输出指令，实际下单、成交、清算由外部交易系统负责。**

### 23.3 回报接收的契约要求

| 要求 | 说明 |
|---|---|
| **回报必须可关联到指令** | 携带 `rebalance_id` 或等价引用 |
| **必须支持部分成交** | 沿用 `06-portfolio/06` §11.3 |
| **必须区分"未回报"与"回报为零"** | 前者是 `Pending`，后者是"确实没成交" |
| **回报格式的规范化属 `03-data`** | 本域只定义接收端点与校验 |

### 23.4 `Pending` 与 `Actual` 的边界在 API 层同样成立

> **沿用上游 ⑨-S：不得以 `Target` 冒充 `Actual`。**

```json
{
  "data": {
    "target_weights": {},
    "pending_execution": {},
    "actual_weights": {},
    "actual_status": "PENDING_CONFIRMATION"
  }
}
```

> **API 必须能表达三态**，否则消费者无法判断"当前持仓"是已确认的还是待确认的。

`<TBD-API-12: 外部执行系统回报的接收端点与格式（= `INT-4`，与 `03-data` 一并定义），待集成方案确认>`

---

## 24. 禁止在 API 层做的事

| # | 禁止 | 理由 |
|---|---|---|
| 1 | **重新定义业务公式** | Factor / Score / 优化目标属各业务域 |
| 2 | **重命名业务枚举** | 产生不可见的映射层（§4.3） |
| 3 | **把数据库表直接暴露为 CRUD** | 违反业务导向原则 |
| 4 | **把 `Fund Score` 当收益率暴露** | 上游 §5.2 —— 字段命名与文档须防止该误用 |
| 5 | **返回 `INVALID` 回测的"正常"结果** | `08-backtest/06` §14.4 |
| 6 | **允许客户端传入未来数据** | §11.5 |
| 7 | **对不同 API 使用不同的响应/分页/错误格式** | §5.3 |
| 8 | 引入 AI / ML | 上游 §6.2.1 |
| 9 | 提供实盘下单能力 | 上游 §6 Out of Scope |

### 24.1 第 4 项在 API 层的具体要求

> **`Fund Score` 的字段命名与文档必须明确它是无量纲相对量。**

```
✅ "total_score": 85.2,  // 0–100，Peer Group 内相对位置，【非收益率】
❌ 与 expected_return 并列且不加说明 → 消费者可能直接相加或代入优化
```

---

## 25. 文档结构约定

> 本域五份文档统一采用以下结构：

| 序 | 章节 | 说明 |
|---|---|---|
| — | Title | 文档标题与依赖声明 |
| 1 | **Overview** | 文档目的与边界 |
| 2 | **Scope** | 能力范围 |
| 3 | **API List** | 端点清单 |
| 4 | **API Details** | 逐端点契约 |
| 5 | Request / Response Convention | 引用本文档，只列特有补充 |
| 6 | **Error Handling** | 错误场景与码 |
| 7 | **Examples** | 请求 / 响应 / 错误 |
| 8 | Security | 认证与授权 |
| 9 | Audit | 审计要求 |
| 10 | Versioning | 版本策略 |

> 各文档可按需增删章节，但**必须包含 API List、API Details、Examples、Error Handling**。

---

## 26. Summary

API 层**只暴露能力，不定义能力** —— 全部业务语义引用各业务域，本域负责契约的稳定、一致与可审计。

三条本域必须定案的全局约定：

- **百分比统一用小数**（`0.1523` 表示 15.23%）—— 混用会在客户端产生难以察觉的 100 倍误差
- **`null` 必须附 `status` 与原因** —— 只返回 `null` 时消费者无法区分"数据不足"与"计算失败"，这是全平台"缺失不得转 0"在 API 层的落实
- **`meta` 必须携带版本引用** —— 返回一个数值而不告知用哪一版规则、哪一版数据算出，该数值不可解释也不可复现

三处易被忽略的语义区分：

- **`as_of_date` 是 PIT 语义，不是业务日期语义** —— 前者返回"T 时点能看到的"，后者返回"描述 T 这一天的"；用 `as_of_date` 查净值序列会得到截至 T 已披露的全部净值，而非 T 当天的净值
- **Validation Error 与 Business Rule Violation 必须区分** —— 混为一谈会导致客户端对不可行的优化反复重试
- **API Filtering 不等于 Eligibility Rules** —— 前者是查询便利，后者是版本化的策略配置且产生 Universe

三处兼容性判断：

- **修改字段语义比删除字段更危险** —— 删除会立即报错让问题暴露，修改语义则静默出错
- **新增枚举值的兼容性取决于客户端** —— 服务端认为兼容，用穷举 switch 的客户端会落入 default 分支
- **分页必须有确定性排序** —— 否则页间会出现重复项与遗漏项

一处必须由服务端强制的机制：**PIT 校验不能依赖客户端** —— 与 `08-backtest/03` §13.4 是同一条原则。

---

## 27. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **API 层不定义业务规则** | 定义权属各业务域 |
| D-2 | 契约定义**与框架选型无关** | `TBD-TECH-2` 不阻塞本域 |
| D-3 | **不得重命名业务枚举** | 会产生不可见的映射层 |
| D-4 | 统一响应结构，**含错误响应** | 不创建第二套格式 |
| D-5 | **`meta` 必须携带版本引用** | `NFR-REPRO-001` 在 API 层的落实 |
| D-6 | **Validation Error 与 Business Rule Violation 分离** | 消费者的处置不同 |
| D-7 | `details` 必须携带可操作信息（如紧约束清单） | 只给 code 不足以定位 |
| D-8 | **分页必须有确定性排序**，含唯一 tie-breaker | 否则页间重复与遗漏 |
| D-9 | 可排序字段必须显式列出 | 避免无意义排序与性能风险 |
| D-10 | **`as_of_date` 定为 PIT 语义**，业务日期用 `business_date` / `date_from`/`to` | 两种解读结果完全不同 |
| D-11 | 无 `as_of_date` 时返回当前视图并标注 `is_point_in_time: false` | 防止误认为历史状态 |
| D-12 | **历史查询必须返回当时的版本引用** | 否则无法判断是当时规则还是今天规则 |
| D-13 | **百分比统一用小数** | 可直接参与运算；混用产生 100 倍误差 |
| D-14 | 金额用字符串并携带 `currency` | 避免浮点精度丢失；组合可能跨币种 |
| D-15 | **`null` 必须附 `status` 与原因** | 区分"数据不足"与"计算失败" |
| D-16 | **语义变更必须升 API 版本** | 静默出错比立即报错更危险 |
| D-17 | 枚举字段须声明"客户端应容忍未知值" | 新增枚举的兼容性取决于客户端 |
| D-18 | **Operation 是独立资源** | 避免每类业务各定义一套轮询端点 |
| D-19 | **API 幂等键与业务幂等键并存，不可互替** | 前者防传输重复，后者防逻辑重复 |
| D-20 | **`Override` 请求必须含 `reason`** | 上游 §7.1.1 留痕要求 |
| D-21 | 历史结果引用快照而非实时重查 | 否则历史结果会"活"起来 |
| D-22 | **API 必须能表达 `Target` / `Pending` / `Actual` 三态** | 上游 ⑨-S |

---

## 28. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | **不得在 API 文档中重新定义业务规则或公式** | 提示词 §48、各业务域 |
| C-2 | 全部访问必须认证 | `NFR-SEC-002` |
| C-3 | **Approve / Reject / Override 仅限 `Portfolio Manager`** | `NFR-SEC-001` SEC-1 |
| C-4 | **策略配置权限与决策放行权限必须分离** | `NFR-SEC-001` SEC-2 |
| C-5 | 全部用户操作必须记入不可篡改的审计日志 | `NFR-SEC-004` |
| C-6 | 敏感配置不得出现在响应或日志中 | `NFR-SEC-003` |
| C-7 | **PIT 校验由服务端强制，客户端无法绕过** | 上游 §4.2 ①-PIT、`08-backtest/03` §13.4 |
| C-8 | **`Fund Score` 不得以可被误用为收益率的方式暴露** | 上游 §5.2 |
| C-9 | 本域**不提供**实盘下单能力 | 上游 §6 Out of Scope |
| C-10 | 不引入 AI / ML | 上游 §6.2.1 |
| C-11 | 接口契约定义权属本域，承载技术属 `02-architecture` | `06-technology-stack` §7.1 |

---

## 29. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| API-1 | **Error Code 全集及其与业务状态的映射** | 错误处理 | 接口评审 |
| ~~API-2~~ | ~~默认 `page_size` 与上限~~ —— **已定案**：默认 `page_size` = 50，上限 500 | — | ✅ 2026-08-27 |
| ~~API-3~~ | ~~系统时区与 DateTime 表示~~ —— **已定案**：系统时区 = **UTC 存储 + ISO 8601 带偏移返回**；业务日期按基金计价市场的本地日历 | — | ✅ 2026-08-27 |
| ~~API-4~~ | ~~金额的精度与小数位~~ —— **已定案**：金额精度 = `NUMERIC(20,4)`，小数位 4；权重与比率用小数（非百分数），精度 `NUMERIC(12,8)` | — | ✅ 2026-08-27 |
| ~~API-5~~ | ~~API 版本演进策略与并存版本数上限~~ —— **已定案**：版本演进 = **URL 路径版本**（`/api/v1/`），并存版本数上限 2 | — | ✅ 2026-08-27 |
| API-6 | **认证机制**（属 `02-architecture`，本域待其定案） | 安全 | 架构 |
| API-7 | 资源级授权模型 | 权限粒度 | 产品 + 治理 |
| API-8 | Sync/Async 阈值与响应时间目标（关联 `TBD-NFR-1/2`） | 性能契约 | 产品 + 运维 |
| ~~API-9~~ | ~~`Idempotency-Key` 有效期与冲突处理~~ —— **推荐默认**：`Idempotency-Key` 有效期 24 小时；冲突返回 409 并附原请求摘要 | — | ✅ 2026-08-27 |
| ~~API-10~~ | ~~废弃期长度与通知机制~~ —— **推荐默认**：废弃期 = 2 个版本或 6 个月（取长者） | — | ✅ 2026-08-27 |
| API-11 | 限流策略与配额 | 稳定性 | 运维 |
| API-12 | **外部执行系统回报的接收端点与格式**（= `INT-4`） | 实盘对接 | 集成 + `03-data` |

> **上游遗留**：`<TBD-17>` 各数据类型 `available_at` 的确定规则 —— 决定 §10.3 中 `available_at` 的暴露粒度。

---

## 30. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§5.2、§6 Out of Scope、⑨-S）、`05-non-functional-requirements.md` v1.0（`NFR-SEC`、`NFR-PERF`、`NFR-REPRO`） |
| **架构** | `02-architecture/02-service-architecture.md` v1.3、`04-integration-architecture.md` v1.2（幂等键、`INT-4`）、`06-technology-stack.md` v1.2 §7.1（框架选型） |
| **本域** | `02-fund-api`、`03-factor-api`、`04-portfolio-api`、`05-backtest-api` |
| **业务语义来源** | `03-data`、`04-factor`、`05-fund-evaluation`、`06-portfolio`、`07-return-risk`、`08-backtest` |
| **下游** | `11-database`（存储结构）、`12-operations`（监控） |

---

## 31. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（6 项）**。`API-3` **UTC 存储 + ISO 8601 带偏移返回**，并明确**时刻与业务日期必须分开**（把业务日期当时刻会产生日界错误）；`API-4` 金额 `NUMERIC(20,4)`、比率一律小数 `NUMERIC(12,8)`；`API-5` **URL 路径版本**、并存上限 2（路径版本对调试与缓存友好，Header 协商在日志中看不出版本）；`API-2` 默认 50 上限 500（更高会与 W2 的 P95 目标冲突）；`API-9`/`API-10` 推荐默认。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.1** | 2026-08-27 | **上游 `TBD-17` 关闭后的定案**。§10.3 改写 —— `available_at` 确定为 `TIMESTAMPTZ`（ISO 8601 带时区、秒级精度），并澄清它与请求参数 `as_of_date`（日期粒度）粒度不同不是不一致；新增 §10.3.1 —— `availability_quality` 与 `available_at` **成对出现**，带 `as_of_date` 的列表端点须在 `meta` 中给出 quality 分布。详见 `TBD-resolution.md` Policy ④ | `03-data/01-data-source` v2.3、`01-product-overview` v2.6 |
| v1.0 | 2026-08-27 | 初始版本。确立**API 只暴露能力不定义能力**与契约独立于框架选型；**§4.3 不得重命名业务枚举**；**§5.2 `meta` 必须携带版本引用**；**§6.3 Validation Error 与 Business Rule Violation 的区分**；**§7.2 分页必须有确定性排序**；**§9.2 API Filtering 不等于 Eligibility Rules**；**§11.2 `as_of_date` 定为 PIT 语义**并与业务日期语义分离；**§12.1 百分比统一用小数**、**§12.4 `null` 必须附 status 与原因**；**§14.4 修改字段语义比删除更危险**、**§14.5 新增枚举的兼容性取决于客户端**；§16.4 Operation 作为独立资源；**§17.3 API 幂等键与业务幂等键并存不可互替**；§20.1 历史结果引用快照；**§23 回应 `INT-4`** 外部执行系统对接的 API 侧契约要求 | `01-product-overview.md` v2.5、`05-non-functional-requirements.md` v1.0、`02-architecture` v1.2–v2.3 |