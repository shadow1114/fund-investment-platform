# 组合 API · Portfolio API

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文暴露的域：**⑤ ⑥ ⑦ ⑨ ⑩**
> 业务语义来源：docs/06-portfolio/（v1.0–v1.1，全 6 份）、docs/07-return-risk/（v1.0，全 6 份）
> 本域上游：docs/10-api/01-api-overview.md（v1.0）
>
> **文档版本**：v1.1 ｜ **产品阶段**：第一阶段

---

## 1. Overview

### 1.1 本文档回答什么

> **组合的构建、优化、风险与再平衡能力如何对外暴露？**

### 1.2 本文档不定义业务规则 ⚠️

| 不定义 | 归属 |
|---|---|
| 权重生成的两条路径 | `06-portfolio/01` §8 |
| 资产配置层级与映射 | `06-portfolio/02` |
| 优化目标与求解路径 | `06-portfolio/03` |
| Risk Budget 六要素 | `06-portfolio/04` |
| 约束定义与优先级 | `06-portfolio/05` |
| 调仓触发与四个阈值 | `06-portfolio/06` |
| `μ` / `Σ` 的估计方法 | `07-return-risk` |

### 1.3 本域涉及写操作与业务命令

> **与 Fund / Factor API 不同**：本域包含**执行类操作**（优化、再平衡生成、决策复核），因此必须处理**幂等、授权、审计、异步**。

---

## 2. Scope

| 能力 | 对应业务域 |
|---|---|
| 组合定义与状态 | `06-portfolio/01` |
| **组合三态持仓** | 上游 ⑨-S |
| 资产配置 | `06-portfolio/02` |
| **优化执行与结果** | `06-portfolio/03` |
| 事后组合风险（⑦-R） | `06-portfolio/03` §9 |
| 风险预算与达成 | `06-portfolio/04` |
| 约束校验结果 | `06-portfolio/05` |
| **再平衡生成与查询** | `06-portfolio/06` |
| **收益与风险估计** | `07-return-risk` |
| **决策复核** | 上游 §7.1.1、`NFR-SEC-001` |

---

## 3. API List

| # | Endpoint | Method | 类型 |
|---|---|---|---|
| 3.1 | `/api/v1/portfolios` | GET / POST | 查询 / 创建 |
| 3.2 | `/api/v1/portfolios/{id}` | GET / PATCH | 详情 / 更新 |
| 3.3 | `/api/v1/portfolios/{id}/holdings` | GET | **三态持仓** |
| 3.4 | `/api/v1/portfolios/{id}/allocations` | GET | 资产配置 |
| 3.5 | `/api/v1/portfolios/{id}/performance` | GET | 绩效 |
| 3.6 | `/api/v1/portfolios/{id}/risk` | GET | 风险（⑦-R） |
| 3.7 | `/api/v1/portfolios/{id}/risk-budget` | GET | 预算与达成 |
| 3.8 | `/api/v1/portfolios/{id}/constraints` | GET | 约束校验结果 |
| 3.9 | **`/api/v1/portfolios/{id}/optimizations`** | **POST** / GET | **执行优化** / 历史 |
| 3.10 | **`/api/v1/portfolios/{id}/rebalances`** | **POST** / GET | **生成调仓建议** / 历史 |
| 3.11 | `/api/v1/portfolios/{id}/rebalances/{rid}` | GET | 调仓详情 |
| 3.12 | **`/api/v1/decisions/{decision_id}/review`** | **POST** | **决策复核** |
| 3.13 | `/api/v1/estimates/returns` | GET | Return Estimate |
| 3.14 | `/api/v1/estimates/risk` | GET | Risk Estimate |
| 3.15 | `/api/v1/estimates/covariance` | GET | 协方差与相关性矩阵 |

> 路径待接口评审确认（`<TBD-PA-1>`）。

---

## 4. API Details

### 4.1 GET /portfolios/{id} — 组合详情

**Response 要点**

| 字段 | 说明 |
|---|---|
| `portfolio_id` / `portfolio_name` / `portfolio_type` | 标识 |
| **`base_currency`** | 影响 `R_f` 口径与跨币种成分 |
| **`risk_profile`** | 决定 Risk Budget 与约束档位 |
| **`portfolio_benchmark`** | 见 §4.1.1 |
| `status` | `DRAFT` / `ACTIVE` / `SUSPENDED` / `CLOSED` |
| **`portfolio_version`** | 组合版本 |
| **`portfolio_rule_version`** | 策略规则版本 |

#### 4.1.1 Portfolio Benchmark 不得借用成分基金的 Benchmark ⚠️

> **沿用上游 §4.2 ①-B 与 `06-portfolio/01` §7.2。**

```
Fund Benchmark      = 单只基金的业绩比较基准
Portfolio Benchmark = 整个组合的比较基准 —— 【不同概念】

多资产组合通常需要 Composite Benchmark
    → 必须保留全部 Component 与权重
    → 不得直接借用某只成分基金的 Fund Benchmark
```

#### 4.1.2 `portfolio_version` 与 `portfolio_rule_version` 必须区分 ⚠️

> **沿用 `06-portfolio/01` §14.2：**

| | `portfolio_version` | `portfolio_rule_version` |
|---|---|---|
| 变化时机 | **每次成分或权重变化** | 策略规则变化 |
| 频率 | 高（每个调仓周期） | 低 |
| 含义 | "组合当时是什么样" | "用什么规则构建" |

> **一次调仓产生新的 `portfolio_version`，但 `portfolio_rule_version` 不变。** 混用会使"策略变了"与"仓位变了"无法区分。

---

### 4.2 GET /portfolios/{id}/holdings — 三态持仓 ⚠️

> **本域最重要的一个端点。**

**Response**

```json
{
  "data": {
    "portfolio_id": "...",
    "as_of_date": "2026-08-24",
    "target": {
      "source_decision_id": "...",
      "effective_date": "2026-08-22",
      "positions": [
        { "fund_id": "F001", "target_weight": 0.15 }
      ]
    },
    "pending_execution": {
      "rebalance_id": "...",
      "delivered_at": "2026-08-22T15:30:00+08:00",
      "adjustments": [
        { "fund_id": "F001", "delta_weight": 0.03, "status": "PENDING" }
      ]
    },
    "actual": {
      "confirmation_status": "PENDING_CONFIRMATION",
      "last_confirmed_at": "2026-08-21T18:00:00+08:00",
      "positions": [
        {
          "fund_id": "F001",
          "shares": "125000.0000",
          "nav": "2.4531",
          "market_value": { "amount": "306637.50", "currency": "CNY" },
          "actual_weight": 0.1204,
          "is_frozen": false
        }
      ],
      "cash": { "amount": "45230.11", "currency": "CNY" }
    }
  },
  "meta": { "portfolio_version": "...", "data_version": "..." },
  "error": null
}
```

#### 4.2.1 三态必须全部可表达，不得以 `Target` 冒充 `Actual` ⚠️

> **沿用上游 ⑨-S 与 `06-portfolio/06` §2.2：**

```
回报延迟时若用 Target 冒充 Actual
    → Drift = |Target − Target| = 0
    → 得出"刚下单就零偏离"的错误结论
    → 且无法表达部分成交
```

**API 必须允许 `actual` 与 `target` 不同，并通过 `confirmation_status` 标注待确认状态。**

#### 4.2.2 各用途该用哪个状态

> **沿用上游 ⑨-S 使用规则，API 文档须明确告知消费者：**

| 用途 | 使用 |
|---|---|
| **Drift 检测** | **`actual` vs `target`** |
| 事后组合风险 | **`actual`** |
| 约束合规校验 | `target`（决策时）+ **`actual`**（持续监控） |
| 展示"当前持仓" | **`actual`**，并标注是否存在 `pending` |

#### 4.2.3 持仓以份额为主，权重是导出量

> **沿用 `08-backtest/01` §11.1：** 只有权重则无法反推交易数量。API 返回 `shares` + `nav` + `market_value` + `actual_weight` 四者，其中权重是导出量。

#### 4.2.4 冻结持仓必须标注

```json
{ "fund_id": "F009", "is_frozen": true, "frozen_reason": "NOT_TRADABLE" }
```

> **沿用 `06-portfolio/01` §9.2、`02` §7.4：** 冻结持仓占据权重但不可调整，使可优化空间小于 100%。**不标注会导致消费者误以为该仓位可调。**

---

### 4.3 GET /portfolios/{id}/risk — 事后组合风险（⑦-R）

**Response**

```json
{
  "data": {
    "as_of_date": "2026-08-24",
    "weight_basis": "ACTUAL",
    "portfolio_volatility": 0.1342,
    "risk_contributions": [
      {
        "fund_id": "F001",
        "weight": 0.1204,
        "marginal_risk_contribution": 0.1876,
        "total_risk_contribution": 0.02258,
        "risk_contribution_pct": 0.1683
      }
    ],
    "concentration": { "hhi": 0.0871, "top_5_weight": 0.4820 },
    "euler_check": { "sum_rc_pct": 1.0000, "status": "PASS" }
  },
  "meta": { "risk_model_version": "...", "covariance_estimate_id": "..." },
  "error": null
}
```

#### 4.3.1 `weight_basis` 必须返回 ⚠️

> **同一组合基于 `Target` 与基于 `Actual` 的风险不同。** 不标注则消费者无法判断该数值的含义（§4.2.2）。

#### 4.3.2 `euler_check` 是计算正确性的硬判据

> **沿用 `06-portfolio/04` §4.1：`Σ RCP_i = 1`。** 不成立说明 `TRC` 计算有误 —— API 暴露该检查使消费者能自行验证。

#### 4.3.3 风险贡献可与权重严重背离

> **沿用 `06-portfolio/04` §4.2：** 权重 40%/60% 的组合，风险贡献可能是 85%/15%。

**API 同时返回 `weight` 与 `risk_contribution_pct`**，使这一现象可见 —— 这正是 Risk Budget 存在的理由。

#### 4.3.4 最大回撤不在本端点

> **沿用 `06-portfolio/04` §3：最大回撤是路径依赖量，不是事前可估的风险。** 它属**事后监控**，在 `/performance` 端点返回（基于历史净值序列）。

> **API 不得在风险端点返回"预期最大回撤"** —— 那会暗示它是一个可事前约束的量。

---

### 4.4 GET /portfolios/{id}/risk-budget — 预算与达成

**Response 要点**

| 字段 | 说明 |
|---|---|
| **`budgets`** | 逐条，**每条含六要素** |
| **`actual_vs_budget`** | 实际风险贡献与预算的对比 |
| **`validation_result`** | `WITHIN_LIMIT` / `BREACHED` / **`NOT_AVAILABLE`** |
| `alert_level` | `NORMAL` / `WARNING` / `CRITICAL` |

#### 4.4.1 Budget 与 Contribution 必须成对返回 ⚠️

> **沿用上游 ⑦-R：** 只存其一都无法回答"风险预算是否被实际满足"。

#### 4.4.2 `NOT_AVAILABLE` 不等于 `WITHIN_LIMIT` ⚠️

> **沿用 `06-portfolio/04` §7.3：把"不知道"当作"没问题"是最危险的默认值选择。**

```
❌ 风险贡献算不出来 → 返回 WITHIN_LIMIT → 消费者认为合规
✅ 返回 NOT_AVAILABLE + reason
```

#### 4.4.3 六要素缺失的预算不得返回为"有效预算"

> 沿用 `06-portfolio/04` §5.1：缺 `scope` 的预算无法被校验也无法被解释。API 应标注该预算为 `INCOMPLETE`。

---

### 4.5 GET /portfolios/{id}/constraints — 约束校验

**Response**

```json
{
  "data": {
    "weight_basis": "ACTUAL",
    "mode": "REBALANCE",
    "results": [
      {
        "constraint_id": "...",
        "constraint_type": "MAX_FUND_WEIGHT",
        "scope": "FUND",
        "scope_key": "F001",
        "limit": 0.15,
        "actual": 0.15,
        "status": "PASS",
        "is_binding": true
      },
      {
        "constraint_id": "...",
        "constraint_type": "MAX_FUND_WEIGHT",
        "scope": "FUND",
        "scope_key": "F009",
        "limit": 0.10,
        "actual": 0.12,
        "status": "BREACH",
        "is_unresolvable": true,
        "unresolvable_reason": "FROZEN_HOLDING"
      }
    ]
  },
  "meta": { "constraint_policy_version": "..." },
  "error": null
}
```

#### 4.5.1 `scope` + `scope_key` 是必备字段 ⚠️

> **沿用 `06-portfolio/05` §2：** "Maximum Weight = 10%" 不说明 10% 是对什么而言，就无法校验也无法解释。

#### 4.5.2 `is_binding` 必须返回 ⚠️

> **沿用 `06-portfolio/05` §10.1：`PASS + BINDING` 与 `PASS + 大量余量` 是两种完全不同的状态。**

```
仅报告 PASS 会把两者混为一谈
    → 前者正在实质性塑造组合
    → 后者在本次求解中没有起作用
```

#### 4.5.3 冻结持仓引起的 Breach 须标 `is_unresolvable`

> **沿用 `06-portfolio/05` §11.1：** 它不可通过调仓消除，若不标注会使消费者反复尝试无效的再平衡。

#### 4.5.4 `mode` 必须返回

> **沿用 `06-portfolio/05` §8：** 换手率约束不适用于 `INITIAL` 模式。不返回 `mode`，消费者无法理解为何某些约束未被校验。

---

### 4.6 POST /portfolios/{id}/optimizations — 执行优化 ⚠️

**Purpose**：这是**业务命令**，不是 CRUD。

**Authorization**：`Portfolio Manager` 或 `Quant Researcher`。

**Headers**

```
Idempotency-Key: <uuid>
```

**Request Body**

```json
{
  "decision_at": "2026-08-24",
  "universe_id": "...",
  "portfolio_rule_version": "...",
  "return_estimate_version": "...",
  "risk_model_version": "...",
  "mode": "REBALANCE"
}
```

#### 4.6.1 请求体传的是**版本引用**，不是估计值本身 ⚠️

> **这是一处关键的契约选择。**

```
❌ 客户端传入 μ 与 Σ 的具体数值
   → 服务端无法校验这些值是否满足 PIT
   → 违反「PIT 校验由服务端强制」（01-api-overview §11.5）
   → 且客户端可能传入未来数据

✅ 客户端传入版本引用，服务端自行取用已通过 Gate 的估计
```

> **这与 `08-backtest` 的「API 不应让客户端传入未来信息」是同一条原则。**

#### 4.6.2 Response — 异步

```
202 Accepted
```

```json
{
  "data": { "operation_id": "...", "status": "RUNNING", "optimization_id": "..." },
  "meta": {},
  "error": null
}
```

#### 4.6.3 完成后的结果结构

```json
{
  "data": {
    "optimization_id": "...",
    "optimization_status": "OPTIMAL",
    "target_weights": [ { "fund_id": "F001", "weight": 0.15 } ],
    "objective_value": 0.0142,
    "binding_constraints": ["MAX_FUND_WEIGHT:F001", "EQUITY_CLASS_MIN"],
    "shadow_prices": { "MAX_FUND_WEIGHT:F001": 0.0031 },
    "post_optimization_risk": { "portfolio_volatility": 0.1342 },
    "excluded_candidates": [
      { "fund_id": "F022", "reason": "COVARIANCE_UNAVAILABLE" }
    ],
    "solve_path": "DIRECT_QP"
  },
  "meta": {
    "portfolio_rule_version": "...",
    "return_estimate_version": "...",
    "risk_model_version": "...",
    "code_version": "...",
    "random_seed": 42
  },
  "error": null
}
```

#### 4.6.4 `optimization_status` 五态

| 状态 | 含义 | 是否产出权重 |
|---|---|---|
| `OPTIMAL` | 成功且收敛 | ✅ |
| **`INFEASIBLE`** | **约束互相冲突，数学上无解** | ❌ |
| `UNBOUNDED` | 目标无界 | ❌ |
| **`NOT_CONVERGED`** | 有解但求解器没找到 | ❌ |
| `NUMERICAL_ERROR` | 数值问题 | ❌ |

#### 4.6.5 `INFEASIBLE` 与 `NOT_CONVERGED` 必须区别对待 ⚠️

> **沿用 `06-portfolio/03` §8.4：混淆两者会让排查方向完全错误。**

| | `INFEASIBLE` | `NOT_CONVERGED` |
|---|---|---|
| 排查方向 | **回 Construction 层查约束配置** | 检查数值条件、迭代上限、`Σ` 条件数 |
| 是否可能通过重试解决 | **否** | 可能 |
| API 错误类别 | **Business Rule Violation** | Processing Error |

> **API 必须让消费者能区分这两者** —— 对 `INFEASIBLE` 重试是徒劳的。

#### 4.6.6 不可行时不得返回权重 ⚠️

> **沿用 `06-portfolio/03` §8.1–8.2：**

```
❌ 返回一个"差不多的解"并标记为成功
❌ 静默降级为等权或上期权重
✅ 返回 INFEASIBLE + binding_constraints + conflicting_constraints
```

**`INFEASIBLE` 的响应必须携带诊断信息**，使调用方能定位是哪些约束冲突。

#### 4.6.7 `solve_path` 必须返回

> **沿用 `06-portfolio/03` §4.3：** Max Sharpe 在换手率约束下 Charnes-Cooper 变换失效，须改用 λ 扫描 —— **相同配置在不同求解路径下会得到不同结果**。

不返回 `solve_path`，消费者无法解释两次结果的差异。

---

### 4.7 POST /portfolios/{id}/rebalances — 生成调仓建议 ⚠️

**Authorization**：`Portfolio Manager`。

**Headers**：`Idempotency-Key`（必需）。

#### 4.7.1 本端点生成建议，不执行交易

> **沿用上游 §6 Out of Scope：平台输出指令，实际下单由外部交易系统负责。**

#### 4.7.2 Response 要点

| 字段 | 说明 |
|---|---|
| **`trigger_type`** | `PERIODIC` / `DRIFT` / `ELIGIBILITY_EVENT` / `CONSTRAINT_BREACH` |
| **`trigger_reason`** | 具体触发原因 |
| **`recompute_scope`** | 本次重算范围 |
| `current_weights`（`Actual`）/ `target_weights` | 前后权重 |
| **`drift`** | 逐基金与逐类别的 **Signed** Drift |
| `proposed_trades` | 买卖清单 |
| **`turnover`** | **单边口径** |
| `estimated_cost` | 预计成本（模型可用时） |
| **`cost_benefit_result`** | 成本收益判据 |
| `constraint_status` | 调仓后校验 |
| **`unachievable_targets`** | 因可投资性无法达成的差额 |

#### 4.7.3 `turnover` 必须标注口径 ⚠️

> **沿用 `06-portfolio/06` §6.2：单边与双边口径相差一倍。**

```json
{ "turnover": 0.18, "turnover_convention": "ONE_SIDED" }
```

#### 4.7.4 `unachievable_targets` 必须返回

> **沿用 `06-portfolio/06` §10.1：不得静默用其他基金补足。**

```json
{
  "unachievable_targets": [
    {
      "fund_id": "F007",
      "target_weight": 0.15,
      "achievable_weight": 0.08,
      "gap": 0.07,
      "reason": "HOLD_ONLY",
      "gap_disposition": "RETAINED_AS_CASH"
    }
  ]
}
```

> **`gap_disposition` 必须明确**，否则消费者不知道那 7% 去了哪里。

#### 4.7.5 `Pending` 期间重复提交的处理

> **沿用 `06-portfolio/06` §2.3：存在未完成的 `Pending Execution` 时不产出新建议。**

```
409 Conflict
{ "error": { "code": "PENDING_EXECUTION_EXISTS", "details": { "rebalance_id": "...", "delivered_at": "..." } } }
```

> **这不是幂等问题** —— 幂等防的是同一请求的重复投递，本条防的是**在未完成状态下发起新调仓**。

#### 4.7.6 成本模型不可用时的响应

> **沿用 `06-portfolio/06` §7.3：** 无成本模型时 Cost-Benefit 判据不可用。

```json
{
  "cost_benefit_result": null,
  "cost_benefit_status": "NOT_AVAILABLE",
  "cost_benefit_reason": "TRANSACTION_COST_MODEL_NOT_CONFIGURED"
}
```

> **不得返回一个假设成本算出的判据。**

---

### 4.8 POST /decisions/{decision_id}/review — 决策复核 ⚠️

**Authorization**：**仅 `Portfolio Manager`**（`NFR-SEC-001` SEC-1）。

**Request Body**

```json
{
  "action": "OVERRIDDEN",
  "reason": "考虑到近期流动性收紧，将 F007 权重下调至 8%",
  "overridden_weights": [ { "fund_id": "F007", "weight": 0.08 } ]
}
```

#### 4.8.1 `action` 沿用上游七态中的复核动作

| `action` | 说明 |
|---|---|
| `APPROVED` | 原样批准 |
| `REJECTED` | 拒绝，本期不调仓 |
| **`OVERRIDDEN`** | 人工修改后批准 |

> **`PROPOSED` / `EXPIRED` / `SUPERSEDED` / `INFEASIBLE` 是系统产生的状态，不是复核动作。**

#### 4.8.2 `reason` 是必填字段 ⚠️

> **沿用上游 §7.1.1：** PM 修改权重必须完整留痕，否则原则六（可复现）与原则七（可追溯）将被破坏。

```
缺少 reason → 422 MISSING_OVERRIDE_REASON
```

#### 4.8.3 职责分离在 API 层的落实

> **沿用 `NFR-SEC-001` SEC-2：策略配置变更权限与决策放行权限必须分离。**

```
同一 token 不得同时具备：
  · 修改 Portfolio Rule / Scoring Policy 的权限
  · 对该策略产出的决策执行 Approve 的权限
```

> **这不是技术偏好，是职责分离要求** —— 同一人不应既定规则又批准其产出。

---

### 4.9 GET /estimates/returns — Return Estimate

**Response 要点**

| 字段 | 说明 |
|---|---|
| `fund_id` / `expected_return` | 估计值 |
| **`return_basis`** | `ABSOLUTE` / `EXCESS` —— **不可省略** |
| **`forecast_horizon`** / **`lookback_window`** | 两个独立参数 |
| `method_id` + `method_version` + `parameter_version` | 方法与参数 |
| **`status`** | `07-return-risk/01` §12 |

#### 4.9.1 `return_basis` 不可省略 ⚠️

> **沿用上游 ⑤-A 约束 4、`07-return-risk/02` §5.5.1：**

```
Benchmark-relative 方法产出的是 Expected Excess Return
    → 若消费者按绝对收益使用，μ'w 的金融含义不成立
    → 不记录 return_basis，消费者无法判断是否需要还原
```

#### 4.9.2 `forecast_horizon` 与 `lookback_window` 必须分别返回 ⚠️

> **沿用 `07-return-risk/01` §7：两者方向相反、含义不同。**

```
用 3 年历史估计未来 1 年  ≠  用 1 年历史估计未来 3 年
```

#### 4.9.3 只有 `APPROVED_FOR_USE` 的估计可用于优化

> **沿用 `07-return-risk/01` §12.3：`VALIDATED` 不等于可用。** API 必须返回完整的 `status`，消费者不得仅凭"有数值"就使用。

---

### 4.10 GET /estimates/covariance — 协方差与相关性

**Response**

```json
{
  "data": {
    "estimate_id": "...",
    "instrument_ids": ["F001", "F002", "F003"],
    "covariance_matrix": [
      [0.018010, 0.006420, 0.003115],
      [0.006420, 0.014400, 0.004032],
      [0.003115, 0.004032, 0.010240]
    ],
    "correlation_matrix": [
      [1.0000, 0.3987, 0.2294],
      [0.3987, 1.0000, 0.3320],
      [0.2294, 0.3320, 1.0000]
    ],
    "diagnostics": {
      "effective_observation_count": 756,
      "n_instruments": 3,
      "t_over_n": 252.0,
      "min_eigenvalue": 0.000142,
      "condition_number": 41.3,
      "psd_adjustment_applied": false
    },
    "excluded_instruments": [
      { "fund_id": "F022", "reason": "INSUFFICIENT_HISTORY" }
    ],
    "return_basis": "ABSOLUTE",
    "status": "APPROVED_FOR_USE"
  },
  "meta": { "risk_model_version": "...", "lookback_window": "3Y", "frequency": "DAILY" },
  "error": null
}
```

#### 4.10.1 `instrument_ids` 的顺序是矩阵语义的一部分 ⚠️

> **沿用 `07-return-risk/04` §9.1：**

```
矩阵本身不携带基金标识
    → 若顺序丢失或与 μ 的顺序不一致
    → w'Σw 计算出的是一个无意义的数
    → 【且不会报错】
```

**API 必须保证 `instrument_ids` 与矩阵行列严格对应，且与同批次的 `μ` 使用同一序列。**

#### 4.10.2 `diagnostics` 是必备字段 ⚠️

> **沿用 `07-return-risk/04` §14.2：只存矩阵不存诊断量，等于存了结论而没存可信度。**

| 诊断量 | 用途 |
|---|---|
| `t_over_n` | 高维小样本判据 |
| `min_eigenvalue` | 半正定诊断 |
| **`condition_number`** | **比半正定更能反映可用性** |
| `psd_adjustment_applied` | 是否做过最近半正定投影 |

#### 4.10.3 矩阵可能很大

> `N × N` 的矩阵在 Universe 较大时体积可观。**是否支持稀疏表示或分块获取待接口评审。**

> **已定案 · 2026-08-27**：协方差矩阵传输 = **完整下三角 + `instrument_ids` 顺序数组**，**不做稀疏化**。
>
> **依据**：
>
> | 方案 | 评价 |
> |---|---|
> | **下三角 + 顺序数组**（已采纳） | 协方差矩阵**对称**，下三角已含全部信息，省一半传输量；`instrument_ids` 的顺序是矩阵语义的一部分（`07-return-risk/04` §9.1） |
> | 完整方阵 | 冗余一倍，且存在上下三角不一致的可能（实现缺陷会被掩盖） |
> | 稀疏格式 | **协方差矩阵稠密** —— 收缩估计后几乎无零元素，稀疏格式的开销大于收益 |
> | 分块 | 增加协议复杂度，而 N ≤ 数百时单次传输的量级可接受 |
>
> **`instrument_ids` 必须与矩阵一并返回且顺序严格对应** —— 缺它则矩阵无法解读，而这是一个容易被当作「元数据」而遗漏的字段。

---

## 5. Request / Response Convention

> 沿用 `01-api-overview` §5–§12。本域特有补充：

| 补充 | 说明 |
|---|---|
| **执行类操作必须携带 `Idempotency-Key`** | §4.6、§4.7 |
| **`weight_basis` 是风险/约束类响应的必备字段** | §4.3.1 |
| **`turnover_convention` 必须随 `turnover` 返回** | §4.7.3 |
| **`return_basis` 必须随估计返回** | §4.9.1 |

---

## 6. Error Handling

| 场景 | HTTP | Code（建议） | 类别 |
|---|---|---|---|
| 组合不存在 | 404 | `PORTFOLIO_NOT_FOUND` | — |
| **优化不可行** | **422** | `OPTIMIZATION_INFEASIBLE` | **Business Rule Violation** |
| **优化未收敛** | **500** | `OPTIMIZATION_NOT_CONVERGED` | **Processing Error** |
| `Σ` 病态或不可逆 | 500 | `COVARIANCE_ILL_CONDITIONED` | Processing Error |
| **估计未通过 Gate** | 422 | `ESTIMATE_NOT_APPROVED` | Business Rule Violation |
| **估计已过期** | 422 | `ESTIMATE_STALE` | Business Rule Violation |
| Universe 为空 | 422 | `EMPTY_UNIVERSE` | Business Rule Violation |
| **存在未完成的 Pending** | 409 | `PENDING_EXECUTION_EXISTS` | Conflict |
| `Override` 缺少 `reason` | 422 | `MISSING_OVERRIDE_REASON` | Validation |
| 非 PM 执行复核 | 403 | `FORBIDDEN` | Authorization |
| `μ` / `Σ` 维度不一致 | 500 | `DIMENSION_MISMATCH` | Processing Error |

### 6.1 `INFEASIBLE` 用 422，`NOT_CONVERGED` 用 500 ⚠️

> **这是 §4.6.5 在错误码上的落实。**

```
422 → 请求合法但业务不允许 → 【不应重试】，需调整约束
500 → 处理过程失败       → 可能通过调整求解参数解决
```

> **若两者用同一状态码，客户端会对不可行的优化反复重试。**

### 6.2 不可行错误必须携带诊断

```json
{
  "error": {
    "code": "OPTIMIZATION_INFEASIBLE",
    "message": "No feasible solution under current constraints",
    "details": {
      "conflicting_constraints": [
        { "constraint_id": "...", "type": "MIN_HOLDINGS", "value": 20 },
        { "constraint_id": "...", "type": "MAX_FUND_WEIGHT", "value": 0.04 }
      ],
      "diagnosis": "min_holdings * max_fund_weight = 0.80 < 1.00"
    }
  }
}
```

> **沿用 `06-portfolio/01` §13.1 的结构性可行性预检** —— 它能把"约束配错了"与"市场条件导致无解"区分开，这对排查很有价值。

---

## 7. Examples

### 7.1 执行优化（异步）

**Request**

```
POST /api/v1/portfolios/P001/optimizations
Authorization: Bearer <token>
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Content-Type: application/json

{
  "decision_at": "2026-08-24",
  "universe_id": "U-2026-08-24-001",
  "portfolio_rule_version": "v2",
  "return_estimate_version": "v1",
  "risk_model_version": "v1",
  "mode": "REBALANCE"
}
```

**Response（202）**

```json
{
  "data": { "operation_id": "OP-8f3c", "optimization_id": "OPT-1042", "status": "RUNNING" },
  "meta": { "request_id": "..." },
  "error": null
}
```

### 7.2 优化不可行

**Request**

```
GET /api/v1/operations/OP-8f3c
```

**Response（200，Operation 完成但业务失败）**

```json
{
  "data": {
    "operation_id": "OP-8f3c",
    "status": "COMPLETED",
    "result": {
      "optimization_id": "OPT-1042",
      "optimization_status": "INFEASIBLE",
      "target_weights": null,
      "conflicting_constraints": [
        { "constraint_type": "MIN_HOLDINGS", "scope": "PORTFOLIO", "value": 20 },
        { "constraint_type": "MAX_FUND_WEIGHT", "scope": "FUND", "value": 0.04 }
      ],
      "diagnosis": "20 × 4% = 80% < 100%，无法凑满权重"
    }
  },
  "meta": { "portfolio_rule_version": "v2" },
  "error": null
}
```

#### 7.2.1 Operation 成功但业务失败时用 200 而非 4xx

> **需要澄清的一处：**

```
Operation 的 status = COMPLETED（任务执行完了）
业务的 optimization_status = INFEASIBLE（业务上无解）

→ HTTP 200：Operation 查询本身成功
→ 业务失败体现在 result 内部
```

**若同步调用优化端点，则直接返回 422**（§6）。**两种形态下业务语义一致，HTTP 语义不同** —— API 文档须明确告知。

### 7.3 决策复核（Override）

**Request**

```
POST /api/v1/decisions/D-2026-0824-01/review
Authorization: Bearer <pm-token>
Idempotency-Key: 3f2a...

{
  "action": "OVERRIDDEN",
  "reason": "近期流动性收紧，下调 F007 权重",
  "overridden_weights": [{ "fund_id": "F007", "weight": 0.08 }]
}
```

**Response（200）**

```json
{
  "data": {
    "decision_id": "D-2026-0824-01",
    "decision_status": "OVERRIDDEN",
    "reviewed_by": "...",
    "reviewed_at": "2026-08-24T16:12:00+08:00",
    "reason": "近期流动性收紧，下调 F007 权重",
    "original_weights": [{ "fund_id": "F007", "weight": 0.15 }],
    "final_weights": [{ "fund_id": "F007", "weight": 0.08 }]
  },
  "meta": { "audit_id": "..." },
  "error": null
}
```

> **`original_weights` 与 `final_weights` 必须同时返回** —— 只保留最终结果会使 Override 的幅度不可见（上游 §7.1.1）。

---

## 8. Security

| 项 | 说明 |
|---|---|
| Authentication | `01-api-overview` §15.1 |
| **Approve / Reject / Override** | **仅 `Portfolio Manager`**（SEC-1） |
| **策略配置与决策放行权限分离** | SEC-2（§4.8.3） |
| 优化 / 再平衡执行 | `Portfolio Manager` 或 `Quant Researcher` |
| 查询类 | `Researcher` 及以上 |

### 8.1 资源级授权

> 组合的可见范围属 `TBD-API-7`。

---

## 9. Audit

### 9.1 必须审计的操作

| 操作 | 特别理由 |
|---|---|
| 组合创建 / 修改 | 策略配置变更 |
| **优化执行** | 产生决策输入 |
| **再平衡生成与交付** | 产生调仓指令 |
| **决策 Approve / Reject / Override** | **投资决策责任边界** |

### 9.2 Override 的审计记录

> 除 `01-api-overview` §19.2 的通用字段外，必须额外记录：

| 字段 | 说明 |
|---|---|
| `original_weights` | 系统产出 |
| `final_weights` | 人工修改后 |
| **`reason`** | 修改理由 |
| `reviewed_by` / `reviewed_at` | 责任人与时刻 |

---

## 10. Versioning

| 版本 | 说明 |
|---|---|
| `portfolio_version` | 每次成分/权重变化 |
| `portfolio_rule_version` | Strategy Version 第 7 项 |
| `rebalance_rule_version` | 第 8 项 |
| `return_estimate_version` | 第 5 项 |
| `risk_model_version` | 第 6 项 |
| **`code_version`** | 求解器与数值库 —— 可复现第四要素 |

### 10.1 `code_version` 必须返回

> **沿用 `06-portfolio/03` §12.3：** 相同配置在不同求解器版本下可能产出不同权重。不返回它，优化结果不可复现。

---

## 11. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **优化与再平衡是业务命令，用 POST** | 不是 CRUD |
| D-2 | **执行类操作必须携带 `Idempotency-Key`** | 防重复下单 |
| D-3 | **请求体传版本引用而非估计值本身** | 否则服务端无法强制 PIT，客户端可传未来数据 |
| D-4 | **三态必须全部可表达** | 以 Target 冒充 Actual 会得出"零偏离" |
| D-5 | 持仓以份额为主，权重为导出量 | 否则无法反推交易数量 |
| D-6 | **冻结持仓必须标注** | 否则误以为该仓位可调 |
| D-7 | **`weight_basis` 是风险/约束响应的必备字段** | Target 与 Actual 的风险不同 |
| D-8 | **`euler_check` 暴露给消费者** | 使其能自行验证计算正确性 |
| D-9 | **风险端点不返回"预期最大回撤"** | 会暗示它可事前约束 |
| D-10 | Budget 与 Contribution **成对返回** | 否则无法回答预算是否达成 |
| D-11 | **`NOT_AVAILABLE` 不等于 `WITHIN_LIMIT`** | 把"不知道"当"没问题" |
| D-12 | **`scope` + `scope_key` 是约束的必备字段** | 缺失则无法校验与解释 |
| D-13 | **`is_binding` 必须返回** | `PASS+BINDING` 与 `PASS+余量` 是不同状态 |
| D-14 | 冻结引起的 Breach 标 `is_unresolvable` | 避免无效重试 |
| D-15 | **`INFEASIBLE` 用 422，`NOT_CONVERGED` 用 500** | 前者不应重试 |
| D-16 | **不可行时不返回权重，但必须返回诊断** | 严禁"差不多的解" |
| D-17 | **`solve_path` 必须返回** | 不同路径结果不同 |
| D-18 | **`turnover_convention` 必须随 `turnover` 返回** | 两种口径相差一倍 |
| D-19 | **`unachievable_targets` 含 `gap_disposition`** | 否则不知差额去向 |
| D-20 | `Pending` 期间重复提交返回 409 | 与幂等是两回事 |
| D-21 | 成本模型不可用时返回 `NOT_AVAILABLE`，**不假设成本** | 沿用 `06-portfolio/06` §7.3 |
| D-22 | **`Override` 的 `reason` 必填，且须返回前后权重** | 上游 §7.1.1 |
| D-23 | **`return_basis` / `forecast_horizon` / `lookback_window` 必须返回** | 语义不可推断 |
| D-24 | **`instrument_ids` 顺序与矩阵严格对应** | 顺序错乱不会报错 |
| D-25 | **协方差 `diagnostics` 是必备字段** | 只给矩阵等于只给结论 |
| D-26 | 异步下业务失败用 200 + result 内状态 | Operation 查询本身成功 |

---

## 12. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 本域**不定义**组合业务规则 | `06-portfolio`、`07-return-risk` |
| C-2 | **不得以 `Target` 冒充 `Actual`** | 上游 ⑨-S |
| C-3 | **Approve / Reject / Override 仅限 `Portfolio Manager`** | `NFR-SEC-001` SEC-1 |
| C-4 | **策略配置权限与决策放行权限必须分离** | SEC-2 |
| C-5 | **Override 必须完整留痕** | 上游 §7.1.1 |
| C-6 | 不可行时**不得返回权重**或静默降级 | 上游 §4.2 ⑦、§5.3 |
| C-7 | **只有 `APPROVED_FOR_USE` 的估计可进入优化** | `07-return-risk/01` §12.3 |
| C-8 | `Portfolio Benchmark` 不得借用成分基金的 Benchmark | 上游 §4.2 ①-B |
| C-9 | 本域**不提供**实盘下单能力 | 上游 §6 Out of Scope |
| C-10 | `μ` / `Σ` 的维度对齐由 `07-return-risk` 保证，API 不得自行截断 | `07-return-risk/01` §6.2 |

---

## 13. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| PA-1 | 本域各端点的最终路径与参数名 | 契约 | 接口评审 |
| ~~PA-2~~ | ~~大规模协方差矩阵的传输格式~~ —— **已定案**：协方差矩阵传输 = **完整下三角 + `instrument_ids` 顺序数组**，不做稀疏 | — | ✅ 2026-08-27 |
| PA-3 | 优化的异步阈值（何时同步、何时 202） | 响应模式 | 产品 + 运维 |
| PA-4 | 组合的资源级可见性规则（= `TBD-API-7`） | 授权 | 产品 + 治理 |
| PA-5 | 是否暴露 Constraint 与 Risk Budget 的**写**接口 | 配置管理 | 产品 + 治理 |

### 13.1 关于 PA-5

> **第一阶段本域只暴露约束与预算的**查询**接口。** 它们属 `Portfolio Rule Version` 的组成部分，其变更须走版本治理与审批（`13-governance`），不宜作为普通的配置写接口暴露。

---

## 14. Related Documents

| 关系 | 文档 |
|---|---|
| **本域总纲** | `10-api/01-api-overview.md` v1.0 |
| **业务语义来源** | `06-portfolio/`（全 6 份 v1.0–v1.1）、`07-return-risk/`（全 6 份 v1.0） |
| **上游约束** | `01-product/01-product-overview.md` v2.5（§4.2 ⑤⑥⑦⑨⑩、⑨-S、§5.3、§7.1.1）、`05-non-functional-requirements.md` v1.0（`NFR-SEC-001`） |
| **相关 API** | `02-fund-api`（Universe）、`03-factor-api`、`05-backtest-api` |

---

## 15. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.1** | 2026-08-27 | **第二批定案（1 项）**。`PA-2` 协方差矩阵传输 = **完整下三角 + `instrument_ids` 顺序数组**，不做稀疏化（收缩估计后矩阵稠密）；`instrument_ids` 必须一并返回且顺序严格对应 —— 它是矩阵语义的一部分，容易被当作元数据而遗漏。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.0 | 2026-08-27 | 初始版本。**§4.1.2 `portfolio_version` 与 `portfolio_rule_version` 的区分**；**§4.2 三态持仓端点**及不得以 Target 冒充 Actual、§4.2.3 份额为主权重为导出、§4.2.4 冻结持仓标注；**§4.3.1 `weight_basis` 必备**、§4.3.2 `euler_check` 暴露、**§4.3.4 风险端点不返回"预期最大回撤"**；**§4.4.2 `NOT_AVAILABLE` 不等于 `WITHIN_LIMIT`**；**§4.5.1–4.5.4 约束的 `scope`/`is_binding`/`is_unresolvable`/`mode`**；**§4.6.1 请求体传版本引用而非估计值**（否则服务端无法强制 PIT）、**§4.6.5 `INFEASIBLE` 与 `NOT_CONVERGED` 区别对待**并落到 422/500、§4.6.7 `solve_path` 必须返回；**§4.7.3 `turnover_convention`**、**§4.7.4 `gap_disposition`**、**§4.7.5 `Pending` 期间 409**（与幂等是两回事）；**§4.8.2 `reason` 必填**、§4.8.3 职责分离；**§4.9.1–4.9.2 `return_basis` 与两个窗口参数必须返回**；**§4.10.1 `instrument_ids` 顺序是矩阵语义的一部分**、§4.10.2 `diagnostics` 必备；**§7.2.1 异步下业务失败用 200** | `06-portfolio` v1.0–v1.1、`07-return-risk` v1.0、`10-api/01-api-overview.md` v1.0 |