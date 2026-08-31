# 回测 API · Backtest API

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文暴露的域：**⑧ Backtest**
> 业务语义来源：docs/08-backtest/（v1.0，全 6 份）
> 本域上游：docs/10-api/01-api-overview.md（v1.0）
>
> **文档版本**：v1.5 ｜ **产品阶段**：第一阶段

---

## 1. Overview

### 1.1 本文档回答什么

> **历史投资过程的模拟与评估能力如何对外暴露？**

### 1.2 本文档不定义回测逻辑 ⚠️

| 不定义 | 归属 |
|---|---|
| 引擎执行流程与快照优先原则 | `08-backtest/01` |
| IS/OOS 与三重证据判定 | `08-backtest/02` |
| 前视偏差的检测 | `08-backtest/03` |
| 幸存者偏差的控制 | `08-backtest/04` |
| 交易成本模型 | `08-backtest/05` |
| 报告结构与 Validation Status | `08-backtest/06` |

### 1.3 回测是长任务，本域以异步为主

> 沿用 `01-api-overview` §16：回测执行属 Long-running Operation。

---

## 2. Scope

| 能力 | 对应 |
|---|---|
| 创建 / 校验回测配置 | `08-backtest/01` §20 |
| 启动执行 | `08-backtest/01` §21 |
| 查询状态 | 同上 |
| 查询结果与绩效 | `08-backtest/02`、`06` |
| 查询风险 | `08-backtest/06` §10 |
| 查询组合历史与调仓历史 | `08-backtest/06` §8、§9 |
| 查询交易成本 | `08-backtest/05` |
| **查询偏差检查** | **`08-backtest/06` §12** |
| 查询完整报告 | `08-backtest/06` |

---

## 3. API List

| # | Endpoint | Method | 类型 |
|---|---|---|---|
| 3.1 | `/api/v1/backtests` | POST / GET | **创建** / 列表 |
| 3.2 | `/api/v1/backtests/{id}` | GET | 详情 |
| 3.3 | `/api/v1/backtests/{id}/validate-configuration` | POST | **配置预校验** |
| 3.4 | **`/api/v1/backtests/{id}/runs`** | **POST** | **启动执行** |
| 3.5 | `/api/v1/backtests/{id}/status` | GET | 状态与进度 |
| 3.6 | `/api/v1/backtests/{id}/result` | GET | 结果摘要 |
| 3.7 | `/api/v1/backtests/{id}/performance` | GET | 绩效与时序 |
| 3.8 | `/api/v1/backtests/{id}/risk` | GET | 风险指标 |
| 3.9 | `/api/v1/backtests/{id}/portfolio-history` | GET | 逐期组合 |
| 3.10 | `/api/v1/backtests/{id}/rebalance-history` | GET | 调仓历史 |
| 3.11 | `/api/v1/backtests/{id}/transaction-cost` | GET | 成本汇总 |
| 3.12 | **`/api/v1/backtests/{id}/bias-check`** | GET | **偏差检查** |
| 3.13 | `/api/v1/backtests/{id}/report` | GET | 完整报告 |

> 路径待接口评审确认（`<TBD-BA-1>`）。

---

## 4. API Details

### 4.1 POST /backtests — 创建回测

**Purpose**：创建 Backtest Run，**不立即执行**。

**Authorization**：`Quant Researcher` 或 `Portfolio Manager`。

**Request Body**

```json
{
  "strategy_id": "...",
  "start_date": "2018-01-01",
  "end_date": "2026-06-30",
  "initial_capital": { "amount": "100000000.00", "currency": "CNY" },
  "backtest_mode": "CURRENT_RULE",
  "benchmark_id": "...",
  "equal_weight_baseline_enabled": true,
  "is_oos_split": {
    "in_sample_end": "2023-12-31",
    "parameter_freeze_date": "2023-12-31"
  },
  "rebalancing_policy_version": "...",
  "portfolio_rule_version": "...",
  "return_estimate_version": "...",
  "risk_model_version": "...",
  "eligibility_rules_version": "...",
  "transaction_cost_model_version": "...",
  "execution_price_rule": "NEXT_DAY_NAV",
  "cash_return_assumption": "ZERO",
  "infeasible_handling": "ABORT"
}
```

#### 4.1.1 创建与执行分离 ⚠️

> **沿用提示词 §30.3：创建不应立即执行复杂计算。**

```
POST /backtests        → 201 Created，返回 backtest_id，status = CREATED
POST /backtests/{id}/runs → 202 Accepted，开始执行
```

**理由**：配置可以先创建、校验、修改，再执行 —— 一次创建可对应多次执行（如修复配置后重跑）。

#### 4.1.2 `backtest_mode` 是必填字段 ⚠️

> **沿用 `08-backtest/03` §6.3、`06` §3.1：**

| 模式 | 用的版本 | 回答 |
|---|---|---|
| **`HISTORICAL_FIDELITY`** | **当时生效的** | 当时的策略会怎样 |
| **`CURRENT_RULE`** | **今天的** | 用今天的规则在历史上会怎样 |

```
未声明模式的回测结果【无法解释】
    → 读者无法判断它回答的是哪个问题
```

> **两者适用场景不可互换**：新策略验证必须用 `CURRENT_RULE`（该策略在历史上不存在），复现历史决策必须用 `HISTORICAL_FIDELITY`。

#### 4.1.3 `equal_weight_baseline_enabled` 默认为 true ⚠️

> **沿用 `02-business-requirements` §21.6、`08-backtest/02` §7.1：三方对比是业务硬要求。**

```
若禁用等权基线
    → 无法回答"策略复杂度是否物有所值"
    → Baseline Gate 无法评估（02-business-requirements §22.4）
```

**API 允许禁用，但必须在结果与报告中标注该缺失。**

#### 4.1.4 `infeasible_handling` 默认 `ABORT`

> **沿用 `08-backtest/01` §18.3：第一阶段某期不可行时中止回测。**

若配置为 `SKIP_PERIOD`，API 必须：

| 要求 | 说明 |
|---|---|
| 记录该配置 | 出现在结果的 `configuration` 中 |
| **Validation Status 降为 `WARNING`** | `08-backtest/01` §18.3 |
| 报告中列出全部跳过期次 | `08-backtest/06` |

#### 4.1.5 创建时不校验业务可行性

> 创建只做**结构性校验**（必填字段、日期合法性）。**业务可行性由 §4.2 的预校验或执行时判定。**

**Response（201）**

```json
{
  "data": { "backtest_id": "BT-2026-0827-001", "status": "CREATED", "created_at": "2026-08-27T10:00:00+08:00" },
  "meta": {},
  "error": null
}
```

---

### 4.2 POST /backtests/{id}/validate-configuration — 配置预校验

**Purpose**：在执行前发现配置问题，避免跑了几小时才失败。

**校验项**

| 检查 | 说明 |
|---|---|
| **Warm-up 后的有效区间是否足够** | `08-backtest/02` §5.3 |
| **OOS 段是否达最小样本期** | `08-backtest/02` §9.4 |
| **各 Policy Version 在回测区间内是否可解析** | `HISTORICAL_FIDELITY` 模式必需 |
| **Benchmark 在区间内是否可得** | 缺失则相对指标不可算 |
| **约束集结构性自洽** | `06-portfolio/01` §13.1 |
| **成本模型是否配置** | 未配置则 Cost-Benefit 判据不可用 |

#### 4.2.1 预校验发现的问题分两类

| 类型 | 处理 |
|---|---|
| **阻断性**（如 Policy 版本不可解析） | 返回 422，不允许执行 |
| **警示性**（如 OOS 段偏短、成本模型未配置） | 返回 200 + `warnings`，允许执行但结果会降级 |

**Response（200，含警告）**

```json
{
  "data": {
    "validation_result": "PASS_WITH_WARNINGS",
    "warm_up_end_date": "2021-01-04",
    "effective_period": { "from": "2021-01-04", "to": "2026-06-30" },
    "in_sample_length_days": 1092,
    "out_of_sample_length_days": 546,
    "warnings": [
      {
        "code": "OOS_PERIOD_SHORT",
        "message": "样本外区间偏短，可能不足以支撑显著性结论",
        "detail": { "oos_days": 546, "recommended_min": null }
      },
      {
        "code": "TRANSACTION_COST_MODEL_NOT_CONFIGURED",
        "message": "成本模型未配置，Cost-Benefit 判据不可用"
      }
    ],
    "blocking_issues": []
  },
  "meta": {},
  "error": null
}
```

#### 4.2.2 Warm-up 必须在预校验中显式返回 ⚠️

> **沿用 `08-backtest/02` §5.3：Warm-up 会缩短有效回测区间。**

```
配置 2018–2026（8 年）
Σ 需要 3 年历史
    → 实际有效回测只有 5 年
    → 再划 IS/OOS，OOS 可能只有 1.5 年
```

**用户在创建时通常按配置区间理解回测长度**，预校验必须纠正这一预期。

---

### 4.3 POST /backtests/{id}/runs — 启动执行

**Headers**：`Idempotency-Key`（必需）。

**Response（202）**

```json
{
  "data": { "operation_id": "OP-...", "backtest_id": "BT-...", "status": "RUNNING" },
  "meta": {},
  "error": null
}
```

#### 4.3.1 重复启动的处理

| 情形 | 响应 |
|---|---|
| 相同 `Idempotency-Key` 重复投递 | 返回首次结果，**不重复执行** |
| 该回测已在 `RUNNING` | **409 `BACKTEST_ALREADY_RUNNING`** |
| 该回测已 `COMPLETED`，请求重跑 | 允许 —— 创建新的 Run（§4.3.2） |

#### 4.3.2 重跑产生新 Run，不覆盖历史 ⚠️

> **沿用 `08-backtest/01` §22.1：**

```
同一配置两次运行结果可能不同
    → 若中间某期的快照被补齐或删除
    → 因此两次 Run 都必须保留
```

**API 不得用新结果覆盖旧结果** —— 否则"为什么这次和上次不一样"无法回答。

---

### 4.4 GET /backtests/{id}/status — 状态与进度

**Response**

```json
{
  "data": {
    "backtest_id": "BT-...",
    "status": "RUNNING",
    "progress": {
      "current_decision_date": "2023-06-30",
      "completed_periods": 42,
      "total_periods": 68
    },
    "started_at": "2026-08-27T10:05:00+08:00"
  },
  "meta": {},
  "error": null
}
```

#### 4.4.1 状态枚举沿用 `08-backtest/01` §21

| 状态 | 含义 |
|---|---|
| `CREATED` | 已创建，未执行 |
| `VALIDATING_CONFIGURATION` | 配置校验中 |
| `RUNNING` | 执行中 |
| `VALIDATING_RESULTS` | 结果校验中 |
| `COMPLETED` | 执行完成 |
| `FAILED` | 执行错误 |
| **`INVALID`** | 结果未通过校验 |
| `CANCELLED` | 人工取消 |
| **`ABORTED`** | **因不可重建或不可行而中止** |

#### 4.4.2 `COMPLETED` 不等于 `VALID` ⚠️

> **沿用 `08-backtest/01` §21.2、`06` §14.3：**

```
COMPLETED  = 执行完成（技术状态）
VALID      = 通过全部完整性检查（业务状态）
```

> **API 必须同时暴露两者** —— `status: COMPLETED` 且 `validation_status: INVALID` 是一个合法且重要的组合。

#### 4.4.3 `total_periods` 在 `n` 不固定时是估算值

> **沿用 `08-backtest/01` §5.2：`T+n` 的 `n` 由 Trigger 类型决定，各期持有时长不均等。**

```
Drift / Eligibility Event 触发的期次事先不可知
    → total_periods 只能按 Periodic 频率估算
    → 实际期数可能更多
```

**API 须标注该字段是估算**，避免进度条出现"超过 100%"的现象。

---

### 4.5 GET /backtests/{id}/result — 结果摘要

**Response**

```json
{
  "data": {
    "backtest_id": "BT-...",
    "status": "COMPLETED",
    "validation_status": "WARNING",
    "backtest_mode": "CURRENT_RULE",
    "period": { "start_date": "2018-01-01", "end_date": "2026-06-30", "warm_up_end_date": "2021-01-04" },
    "initial_capital": { "amount": "100000000.00", "currency": "CNY" },
    "final_value": { "amount": "148230115.44", "currency": "CNY" },
    "summary": {
      "portfolio": { "total_return": 0.4823, "annualized_return": 0.0742, "volatility": 0.1342, "max_drawdown": 0.2184, "sharpe_ratio": 0.44 },
      "benchmark": { "total_return": 0.3915, "annualized_return": 0.0621, "volatility": 0.1520, "max_drawdown": 0.2761, "sharpe_ratio": 0.31 },
      "equal_weight_baseline": { "total_return": 0.4402, "annualized_return": 0.0688, "volatility": 0.1418, "max_drawdown": 0.2395, "sharpe_ratio": 0.39 }
    },
    "excess_return": { "vs_benchmark": 0.0908, "vs_equal_weight": 0.0421 },
    "significance_verdict": {
      "overall": "NOT_SIGNIFICANT",
      "thresholds_status": "PENDING_CALIBRATION",
      "layers": {
        "statistical": { "passed": null, "bootstrap_ci_lower_vs_benchmark": 0.0031, "bootstrap_ci_lower_vs_equal_weight": -0.0008 },
        "effect_size": { "passed": null, "ir_vs_benchmark": 0.62, "ir_vs_equal_weight": 0.21, "delta_sharpe_vs_benchmark": 0.13, "delta_sharpe_vs_equal_weight": 0.05 },
        "robustness": { "passed": null, "outperform_ratio_vs_benchmark": 0.68, "outperform_ratio_vs_equal_weight": 0.54 },
        "economic": { "passed": null, "annualized_return_improvement_vs_benchmark": 0.0121, "annualized_return_improvement_vs_equal_weight": 0.0054, "max_drawdown_improvement_vs_benchmark": 0.0577, "max_drawdown_improvement_vs_equal_weight": 0.0211 }
      }
    },
    "validation_summary": {
      "warnings": ["REBUILT_PERIOD_RATIO_HIGH", "TRADABILITY_NOT_VERIFIED"],
      "invalid_reasons": []
    }
  },
  "meta": {
    "configuration_version": "...",
    "data_version": "...",
    "strategy_versions": { "metric_version": "...", "scoring_version": "...", "portfolio_rule_version": "...", "rebalance_rule_version": "...", "return_estimate_version": "...", "risk_model_version": "...", "eligibility_universe_version": "...", "benchmark_version": "...", "peer_group_classification_version": "..." },
    "code_version": "...",
    "transaction_cost_model_version": "...",
    "methodology_policy_version": "...",
    "report_policy_version": "..."
  },
  "error": null
}
```

#### 4.5.1 摘要必须含等权基线与 `validation_status` ⚠️

> **沿用 `08-backtest/06` §5.1–5.2：**

| 要求 | 理由 |
|---|---|
| **含等权基线** | 只给 Benchmark 对比会漏掉"复杂度是否值得"的判断 |
| **含 `validation_status`** | 一份 `INVALID` 回测的漂亮摘要是危险的，状态不能藏在末尾 |

#### 4.5.2 摘要必须同时给收益与风险

> **沿用 `08-backtest/02` §7.4：只比收益会把高风险误认为高能力。**

#### 4.5.3 `significance_verdict` 是四层结构（v1.4 新增）

> **定案 · 2026-08-27**：「显著优于」由四层判据决定（`02-business-requirements` §22.2.2、`08-backtest/02` §9.1、`TBD-resolution.md` Policy ⑨）。

| 字段 | 说明 |
|---|---|
| `overall` | `SIGNIFICANT` / `NOT_SIGNIFICANT` / **`CANNOT_DETERMINE`** |
| **`thresholds_status`** | `CALIBRATED` / **`PENDING_CALIBRATION`** |
| `layers.*.passed` | 该层是否通过；阈值未校准时为 **`null`** |
| `layers.*.<metric>` | 各判据的**数值**，无论阈值是否校准都必须返回 |

**三条约定**：

| # | 约定 |
|---|---|
| 1 | **阈值未校准时 `passed` 为 `null`、`overall` 为 `NOT_SIGNIFICANT`** —— 不是 `false`，也不是省略字段。`null` 表示「无法判定」，`false` 表示「判定为不通过」 |
| 2 | **数值字段始终返回** —— 阈值待定不妨碍陈述数值差异，这正是 `08-backtest/06` §7.2 允许的表述 |
| 3 | **每个判据须分别给出对 Benchmark 与对 Equal Weight 的两个值** —— 只给其一会让「跑赢基准但跑不赢等权」的情形不可见 |

> **`overall` 在阈值未校准时取 `NOT_SIGNIFICANT` 而非 `CANNOT_DETERMINE`**：后者留给「数据不足以计算判据」的情形（Benchmark 缺失、OOS 样本期不足）。阈值未校准时判据算得出来，只是无从比较 —— 而在无从比较时，**默认结论必须是「不显著」**，否则调用方可能把 `CANNOT_DETERMINE` 当作中性而据以放行。

> **API 不返回「接近显著」类字段** —— `08-backtest/06` §7.2.1 已将该类表述列入禁用词表，API 层不得以字段形式重新引入。

#### 4.5.4 `meta` 必须携带九项 Strategy Version

> **这是 `NFR-REPRO-001` 在回测 API 上的落实。** 缺任一项，该回测不可复现。

---

### 4.6 GET /backtests/{id}/bias-check — 偏差检查 ⚠️

> **本域最重要的端点。**

> **`point_in_time` 的 `PASS` 必须连同 quality 分布一起读**（`03-look-ahead-bias` §18.1.1）：`DERIVED` 那部分的 `PASS` 含残余前视风险（用的是公告时刻，未计入公告到推送的延迟），`INFERRED` 那部分的 `PASS` 偏保守。只看 `status` 会把「62% 精确 + 31% 有残余风险」和「100% 精确」当成同一件事。

**Response**

```json
{
  "data": {
    "backtest_id": "BT-...",
    "checks": {
      "look_ahead_bias": { "status": "PASS", "violations": [] },
      "survivorship_bias": { "status": "PASS", "violations": [] },
      "tradability_bias": {
        "status": "NOT_VERIFIED",
        "reason": "INVESTMENT_ELIGIBILITY_HISTORY_INCOMPLETE",
        "affected_periods": 12
      },
      "point_in_time": {
        "status": "PASS",
        "availability_quality_distribution": {
          "EXACT": 0.62,
          "DERIVED": 0.31,
          "INFERRED": 0.07
        }
      },
      "transaction_cost": {
        "status": "PARTIALLY_MODELED",
        "unmodeled_costs": ["BID_ASK_SPREAD", "MARKET_IMPACT", "SALES_SERVICE_FEE"]
      },
      "subscription_redemption_lag": { "status": "NOT_MODELED" }
    },
    "snapshot_summary": {
      "snapshot_periods": 56,
      "rebuilt_periods": 12,
      "total_periods": 68,
      "rebuilt_period_list": ["2019-03-29", "2019-06-28"]
    },
    "data_limitations": [
      "已清盘基金的历史数据在 2019 年之前不完整，该区间的幸存者偏差控制受限"
    ]
  },
  "meta": {},
  "error": null
}
```

#### 4.6.1 `NOT_VERIFIED` 是独立状态，不等于 `PASS` ⚠️

> **沿用 `08-backtest/06` §12.1、`04` §11.6：**

```
PASS         → 检查了，通过
FAIL         → 检查了，未通过
NOT_VERIFIED → 【没法检查】—— 数据不足
```

**把 `NOT_VERIFIED` 当作 `PASS`，是把"不知道"当作"没问题"。**

> **API 必须用三个不同的枚举值**，不得把 `NOT_VERIFIED` 折叠进 `PASS` 或 `WARNING`。

#### 4.6.2 未建模成本必须列出

> **沿用 `08-backtest/06` §11.1、`05` §12.2：**

```
若只显示 Transaction Cost = 0.8%/年 而不标注未建模项
    → 读者会以为 0.8% 就是全部成本
```

**`unmodeled_costs` 是必备字段。**

#### 4.6.3 快照 vs 重建的比例必须暴露

> **沿用 `08-backtest/01` §8.4：重建的可信度低于快照，混在一起呈现会误导。**

#### 4.6.4 未声明处理方式的回测结果不得作为决策依据

> **上游 §4.2 ⑧ 关键约束。API 层的落实**：

```
若本端点返回 404 或缺少任一 check 项
    → 该回测的结果【不可使用】
    → 消费者应视其为 INVALID
```

**API 文档须明确告知这一点。**

---

### 4.7 GET /backtests/{id}/performance — 绩效与时序

**Query Parameters**

| 参数 | 说明 |
|---|---|
| `date_from` / `date_to` | 区间 |
| `frequency` | 时序频率 |
| `segment` | **`FULL` / `IN_SAMPLE` / `OUT_OF_SAMPLE`** |
| `include_series` | 需要哪些序列 |

#### 4.7.1 IS / OOS 必须可分段查询 ⚠️

> **沿用 `08-backtest/06` §6.2：只给整段结果会掩盖过拟合信号。**

```
IS 与 OOS 表现差异悬殊是过拟合信号
    → 而 OOS 才是策略批准的依据
```

#### 4.7.2 时序必须含三方对比

```json
{
  "data": {
    "segment": "OUT_OF_SAMPLE",
    "series": {
      "portfolio_value": [
        { "date": "2024-01-02", "value": "121043210.55" },
        { "date": "2024-01-03", "value": "120887431.20" }
      ],
      "cumulative_return": {
        "portfolio": [
          { "date": "2024-01-02", "value": 0.2104 },
          { "date": "2024-01-03", "value": 0.2089 }
        ],
        "benchmark": [
          { "date": "2024-01-02", "value": 0.1832 },
          { "date": "2024-01-03", "value": 0.1815 }
        ],
        "equal_weight_baseline": [
          { "date": "2024-01-02", "value": 0.1977 },
          { "date": "2024-01-03", "value": 0.1962 }
        ]
      },
      "drawdown": [
        { "date": "2024-01-02", "value": 0.0142 },
        { "date": "2024-01-03", "value": 0.0155 }
      ],
      "rolling_sharpe": [
        { "date": "2024-01-02", "value": 0.51 }
      ],
      "rolling_excess_return": [
        { "date": "2024-01-02", "value": 0.0272 }
      ]
    }
  },
  "meta": { "warm_up_end_date": "2021-01-04" },
  "error": null
}
```

#### 4.7.3 `warm_up_end_date` 必须在 `meta` 中返回

> **绩效从该日起算。** 不返回它，消费者会误以为回测从 `start_date` 就在运作（`08-backtest/06` §8.1）。

#### 4.7.4 全部绩效基于 Net Return

> **沿用 `08-backtest/05` §10.2：Gross 仅用于成本归因。** API 的绩效字段一律是 Net，Gross 只出现在 `/transaction-cost` 端点。

---

### 4.8 GET /backtests/{id}/portfolio-history — 逐期组合

**Response 要点**

| 字段 | 说明 |
|---|---|
| `decision_date` | 决策时点 |
| **`universe_source`** | `SNAPSHOT` / `REBUILT` |
| `selected_funds` + `weights` | 该期成分与权重 |
| `portfolio_value` / `cash` | 组合状态 |
| `turnover` | 该期换手 |
| **`optimization_status`** | 该期求解状态 |
| **归因入口** | 见 §4.8.1 |

#### 4.8.1 必须支持五个必答问题的下钻 ⚠️

> **沿用 `08-backtest/01` §25.2、`06` §16.1：**

| 问题 | API 应提供的入口 |
|---|---|
| **Fund A 为什么被选中？** | 该期的 Universe 入池条件明细 |
| **Fund A 为什么占 X%？** | 该期的 Optimization 结果与紧约束 |
| **Fund A 为什么被卖出？** | 该期的 Rebalancing Trigger |
| **为什么净收益低于毛收益？** | `/transaction-cost` 端点 |
| **这次回测能复现吗？** | `meta` 中的全部版本引用 |

> **只返回权重而不提供下钻入口，回测结果不可解释。**

---

### 4.9 GET /backtests/{id}/transaction-cost — 成本汇总

**Response**

```json
{
  "data": {
    "gross_return": 0.5104,
    "transaction_cost_total": { "amount": "1842300.00", "currency": "CNY" },
    "net_return": 0.4823,
    "cost_erosion_ratio": 0.0551,
    "turnover": { "annualized": 0.42, "cumulative": 3.57, "convention": "ONE_SIDED" },
    "cost_by_type": { "subscription_fee": "982400.00", "redemption_fee": "741500.00", "other": "118400.00" },
    "excluded_costs": [
      { "expense_type": "MANAGEMENT_FEE",    "reason": "INCLUDED_IN_NAV" },
      { "expense_type": "CUSTODY_FEE",       "reason": "INCLUDED_IN_NAV" },
      { "expense_type": "SALES_SERVICE_FEE", "reason": "INCLUSION_UNKNOWN" }
    ],
    "cost_by_trigger": [
      { "trigger_type": "PERIODIC", "rebalance_count": 34, "turnover": 2.10, "cost": "..." },
      { "trigger_type": "DRIFT", "rebalance_count": 22, "turnover": 1.12, "cost": "..." }
    ],
    "unmodeled_costs": ["BID_ASK_SPREAD", "MARKET_IMPACT"]
  },
  "meta": { "transaction_cost_model_version": "..." },
  "error": null
}
```

#### 4.9.1 `excluded_costs` 区分两种"不在成本中"（v1.3 新增）

> **定案 · 2026-08-27**：Policy ⑩ 要求区分「已含于净值」与「包含关系未知」。见 `08-backtest/05-transaction-cost` §2.1。

| `reason` | 含义 | 对结果的影响 |
|---|---|---|
| **`INCLUDED_IN_NAV`** | 已内含于基金净值 | **无影响** —— 成本已在净值收益里体现 |
| **`INCLUSION_UNKNOWN`** | 数据源未声明是否已含 | **成本可能被低估** —— 若实际未含，这笔费用没人扣 |

> **两者放同一个数组但语义相反**：前者是"扣过了"，后者是"可能没扣"。用一句"管理费不在成本中"概括两者，会让 `UNKNOWN` 的风险被前者的正当性掩盖。

**`excluded_costs` 与 `unmodeled_costs` 的分工**：

| 字段 | 装什么 |
|---|---|
| `excluded_costs` | **基金费用**中未计入的项，附原因 |
| `unmodeled_costs` | **交易成本模型**未建模的项（价差、冲击） |

> `INCLUSION_UNKNOWN` 的费用**同时出现在两者中** —— 它既是被排除的基金费用，也构成成本模型的缺口。这不是重复，是两个视角。

**API 文档须明确说明管理费与托管费不在成本中**，否则消费者会疑惑"为什么成本里没有管理费"，甚至自行再扣一次。

#### 4.9.2 `unmodeled_costs` 必须与成本数字同屏

> 沿用 §4.6.2。

#### 4.9.3 `cost_by_trigger` 支持"哪类调仓最费钱"

> 沿用 `08-backtest/06` §11.2。

---

### 4.10 GET /backtests/{id}/report — 完整报告

**Response**：`08-backtest/06` §3–§16 定义的全部章节的结构化表示。

#### 4.10.1 报告缺少 Bias Check 章节即视为未完成

> **沿用 `08-backtest/06` §14.2 第 9 项：Bias Check 缺失 → `INVALID`。**

#### 4.10.2 `limitations` 必须逐次生成 ⚠️

> **沿用 `08-backtest/06` §15.2：Limitations 不是免责声明，而是解读结果的必要上下文。**

```
❌ 返回一段固定的免责文本
✅ 返回本次的实际局限：
   · 未建模场内价差与冲击成本
   · 12 期为重建产物
   · OOS 仅 1.5 年
   · Tradability 未校验
```

#### 4.10.3 报告文件导出

```
Report File Export = TBD
```

`<TBD-BA-2: 是否提供报告文件导出（PDF / Excel）及其格式，待产品确认>`

---

## 5. Request / Response Convention

> 沿用 `01-api-overview` §5–§12。本域特有补充：

| 补充 | 说明 |
|---|---|
| **`backtest_mode` 是创建与全部结果响应的必备字段** | §4.1.2 |
| **`validation_status` 必须与 `status` 同时返回** | §4.4.2 |
| **`meta` 必须含九项 Strategy Version + `code_version`** | §4.5.3 |
| **`unmodeled_costs` 是成本相关响应的必备字段** | §4.6.2 |

---

## 6. Error Handling

| 场景 | HTTP | Code（建议） |
|---|---|---|
| 回测不存在 | 404 | `BACKTEST_NOT_FOUND` |
| **配置校验失败（阻断性）** | 422 | `BACKTEST_CONFIGURATION_INVALID` |
| **已在运行中** | 409 | `BACKTEST_ALREADY_RUNNING` |
| 状态不允许该操作 | 409 | `INVALID_STATE_TRANSITION` |
| **结果尚未就绪** | 409 | `BACKTEST_NOT_COMPLETED` |
| **回测被中止** | 200 + `status: ABORTED` | 见 §6.2 |
| **回测 `INVALID`** | 200 + `validation_status` | 见 §6.1 |
| Policy 版本在区间内不可解析 | 422 | `POLICY_VERSION_UNRESOLVABLE` |
| 无权限 | 403 | `FORBIDDEN` |

### 6.1 `INVALID` 回测返回 200，但不得返回"看起来正常"的结果 ⚠️

> **沿用提示词 §30.16 与 `08-backtest/06` §14.4：**

```
❌ 检测到前视 → 照常返回漂亮的绩效数字 → 附一行小字说明
   → 消费者可能直接使用

✅ 返回 200，但：
   · validation_status = INVALID
   · invalid_reasons 明确列出
   · 绩效字段【仍返回】但必须与 INVALID 标记同层级呈现
```

**API 必须明确告知 Consumer 为什么 `INVALID`**，且文档须声明 **`INVALID` 的结果不得用于策略比较**（`08-backtest/06` §14.4：污染的结果比没有结果更危险）。

> **已定案 · 2026-08-27**：`INVALID` 回测的绩效字段**照常返回**；但 `validation_status` **置顶**且报告整体标 `INVALID`。
>
> **依据 —— 置空会让使用方无法定位问题**：
>
> ```
> 一份 INVALID 回测，其绩效数字仍是「在那些有问题的假设下算出来的结果」
>     → 置空：使用方只知道「不行」，不知道差在哪
>     → 返回并标注：使用方能看出「年化 15% 但重建期占 40%」
>                    → 立刻明白问题所在
> ```
>
> **风险在于数字会被断章取义地使用** —— 因此 `validation_status` 与 `invalid_reasons` 必须在响应结构中**先于**绩效字段出现（`08-backtest/06` §5.2「状态不能藏在末尾」）。
>
> **报告导出时须在首页呈现 `INVALID` 标识**，不能只在附录说明。

### 6.2 `ABORTED` 的回测仍须可查

> **沿用 `08-backtest/06` §16.2：中止原因是有效信息，不是"什么都没发生"。**

```json
{
  "data": {
    "status": "ABORTED",
    "abort_reason": "SNAPSHOT_UNAVAILABLE_AND_NOT_REBUILDABLE",
    "abort_at_decision_date": "2020-03-31",
    "abort_detail": { "failed_condition": "R-2", "message": "该时点的 NAV 修订历史不完整，无法取到当时的 version" }
  },
  "meta": {},
  "error": null
}
```

---

## 7. Examples

### 7.1 完整流程

```
① POST /api/v1/backtests                        → 201 { backtest_id, status: CREATED }
② POST /api/v1/backtests/{id}/validate-configuration → 200 { validation_result: PASS_WITH_WARNINGS }
③ POST /api/v1/backtests/{id}/runs              → 202 { operation_id, status: RUNNING }
④ GET  /api/v1/backtests/{id}/status            → 200 { status: RUNNING, progress: {...} }
⑤ GET  /api/v1/backtests/{id}/status            → 200 { status: COMPLETED, validation_status: WARNING }
⑥ GET  /api/v1/backtests/{id}/bias-check        → 200 { checks: {...} }
⑦ GET  /api/v1/backtests/{id}/result            → 200 { summary: {...} }
```

> **注意第 ⑥ 步在 ⑦ 之前** —— 应先确认偏差检查结果，再看绩效数字。

### 7.2 偏差检查失败

**Request**

```
GET /api/v1/backtests/BT-2026-0827-002/bias-check
```

**Response（200）**

```json
{
  "data": {
    "backtest_id": "BT-2026-0827-002",
    "checks": {
      "look_ahead_bias": {
        "status": "FAIL",
        "violations": [
          {
            "decision_date": "2022-07-15",
            "input": "FUND_AUM",
            "effective_at": "2022-06-30",
            "available_at": "2022-08-28",
            "gap_days": 44
          }
        ]
      },
      "survivorship_bias": { "status": "PASS", "violations": [] },
      "tradability_bias": { "status": "PASS", "violations": [] },
      "point_in_time": {
        "status": "FAIL",
        "availability_quality_distribution": {
          "EXACT": 0.41,
          "DERIVED": 0.22,
          "INFERRED": 0.37
        }
      }
    }
  },
  "meta": { "validation_status": "INVALID" },
  "error": null
}
```

> **单期违规使整个回测 `INVALID`** —— 沿用 `08-backtest/03` §15.2：前视会沿时间轴传导，污染的持仓成为下期起点。

### 7.3 错误示例：结果尚未就绪

**Request**

```
GET /api/v1/backtests/BT-2026-0827-003/result
```

**Response（409）**

```json
{
  "data": null,
  "meta": { "request_id": "..." },
  "error": {
    "code": "BACKTEST_NOT_COMPLETED",
    "message": "Backtest result is not available yet",
    "details": { "current_status": "RUNNING", "progress": { "completed_periods": 42, "total_periods": 68 } }
  }
}
```

---

## 8. Security

| 项 | 说明 |
|---|---|
| Authentication | `01-api-overview` §15.1 |
| **创建 / 执行回测** | `Quant Researcher` 或 `Portfolio Manager` |
| 查询结果 | `Researcher` 及以上（视资源级授权） |
| **本域不提供实盘能力** | 上游 §4.2 ⑧：不产生任何实盘指令 |

---

## 9. Audit

### 9.1 必须审计的操作

| 操作 | 理由 |
|---|---|
| **回测创建** | 配置是策略验证的依据 |
| **回测执行** | 结果用于上线评估 |
| 回测取消 | 状态变更 |

### 9.2 审计须记录完整配置与版本

> 只记录"某人跑了一次回测"不足以事后复核 —— 必须记录**当时的配置与全部版本引用**。

---

## 10. Versioning

| 版本 | 说明 |
|---|---|
| API 版本 | `/api/v1` |
| `configuration_version` | 回测配置版本 |
| **九项 Strategy Version** | 完整记录 |
| `code_version` | 求解器与数值库 |
| `policy_version`（五子项） | 评价与判定标准，与九项**并列**（§10.1） |

### 10.1 Policy Version 是与 `strategy_version` 并列的返回字段 ✅

> **定案 · 2026-08-27**。原为「三个 Policy Version 尚未纳入九项」的缺口登记，现已随第 10 类 `Policy Version` 关闭。见 `02-architecture/01-system-architecture` §8.2.1、`TBD-resolution.md` Policy ⑧。

各域 Policy 到五个子项的映射：

| Policy | 归入子项 |
|---|---|
| Evaluation / Ranking / Classification Policy Version | `evaluation_policy` / `ranking_policy` / `classification_policy` |
| Estimation Framework Policy Version | `estimation_policy` |
| Estimation Validation Policy Version | `validation_policy` |
| **Methodology Policy Version**（本域） | `validation_policy` —— 回测证据门槛属校验策略 |
| **Report Policy Version**（本域） | `validation_policy` —— 报告的判定与降级规则同属校验策略 |

**对 API 契约的要求**：

```json
{
  "strategy_version": { "metric_version": "v3", "scoring_version": "v2", "portfolio_rule_version": "v5", "rebalance_rule_version": "v2", "return_estimate_version": "v1", "risk_model_version": "v4", "eligibility_universe_version": "v3", "benchmark_version": "v1", "peer_group_classification_version": "v2" },
  "policy_version": {
    "evaluation_policy": "v3",
    "ranking_policy": "v1",
    "classification_policy": "v2",
    "estimation_policy": "v4",
    "validation_policy": "v2"
  }
}
```

| # | 要求 |
|---|---|
| 1 | `strategy_version` 与 `policy_version` 是**两个并列的顶层对象**，不得把 Policy 嵌进前者 |
| 2 | `policy_version` 的**五个子项必须全部返回**，即便本次回测未触发某子项的任何规则 —— 缺项等于无法判定当时用的是哪一版 |
| 3 | 本域两个 Policy 归入 `validation_policy` 后，**它们各自的版本号不再单独出现在响应中**；调用方若需区分，从 `validation_policy` 的版本详情接口展开 |

---

## 11. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **创建与执行分离** | 一次创建可对应多次执行 |
| D-2 | **`backtest_mode` 必填** | 未声明的结果无法解释 |
| D-3 | 等权基线默认启用，禁用须标注 | 三方对比是业务硬要求 |
| D-4 | `infeasible_handling` 默认 `ABORT` | `08-backtest/01` §18.3 |
| D-5 | **提供配置预校验端点** | 避免跑几小时才失败 |
| D-6 | **预校验必须返回 Warm-up 后的有效区间** | 用户按配置区间理解长度是错的 |
| D-7 | 预校验区分阻断性与警示性问题 | 后者允许执行但结果降级 |
| D-8 | **重跑产生新 Run，不覆盖历史** | 两次结果可能不同 |
| D-9 | **`COMPLETED` 与 `validation_status` 同时返回** | 跑完不等于可用 |
| D-10 | `total_periods` 标注为估算 | `n` 不固定 |
| D-11 | **摘要必须含等权基线与 `validation_status`** | `08-backtest/06` §5 |
| D-12 | **`NOT_VERIFIED` 是独立枚举值** | 不得折叠进 `PASS` |
| D-13 | **`unmodeled_costs` 必备** | 否则读者以为显示的就是全部成本 |
| D-14 | **快照/重建比例必须暴露** | 可信度不同 |
| D-15 | Bias Check 缺失即视为结果不可用 | 上游 §4.2 ⑧ |
| D-16 | **IS / OOS 可分段查询** | 整段结果掩盖过拟合信号 |
| D-17 | `warm_up_end_date` 必须返回 | 否则误以为从 start_date 起运作 |
| D-18 | 绩效一律 Net，Gross 仅在成本端点 | `08-backtest/05` §10.2 |
| D-19 | **组合历史须支持五个必答问题的下钻** | 否则结果不可解释 |
| D-20 | **API 文档须说明管理费不在成本中** | 否则消费者自行再扣一次 |
| D-21 | **`INVALID` 返回 200 但须明确原因** | 不得返回"看起来正常"的结果 |
| D-22 | **`ABORTED` 的回测仍须可查** | 中止原因是有效信息 |
| D-23 | `limitations` 逐次生成 | 它是解读上下文，不是免责声明 |

---

## 12. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 本域**不定义**回测逻辑 | `08-backtest` |
| C-2 | **未声明偏差处理方式的结果不得作为决策依据** | 上游 §4.2 ⑧ |
| C-3 | **`INVALID` 的结果不得用于策略比较** | `08-backtest/06` §14.4 |
| C-4 | **API 不得让客户端传入未来信息** | `01-api-overview` §11.5 |
| C-5 | PIT 校验由 Backtest Engine 强制 | `08-backtest/03` §13.4 |
| C-6 | **不产生任何实盘指令** | 上游 §4.2 ⑧ |
| C-7 | 回测结果必须可复现，`meta` 须含全部版本引用 | `NFR-REPRO-001` |
| C-8 | 不引入 AI / ML | 上游 §6.2.1 |

---

## 13. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| BA-1 | 本域各端点的最终路径与参数名 | 契约 | 接口评审 |
| BA-2 | 是否提供报告文件导出及格式 | 产品能力 | 产品 |
| ~~BA-3~~ | ~~`INVALID` 回测的绩效字段是否置空~~ —— **已定案**：`INVALID` 回测的绩效字段**照常返回**，但 `validation_status` 置顶且报告标 `INVALID` | — | ✅ 2026-08-27 |
| BA-4 | 回测结果的保留期限与归档策略 | 存储 | 运维 + 合规 |
| BA-5 | 是否支持回测的取消与断点续跑 | 长任务体验 | 产品 + 技术 |

---

## 14. Related Documents

| 关系 | 文档 |
|---|---|
| **本域总纲** | `10-api/01-api-overview.md` v1.0 |
| **业务语义来源** | `08-backtest/`（全 6 份 v1.0） |
| **上游约束** | `01-product/01-product-overview.md` v2.5（§4.2 ⑧、§5.4）、`02-business-requirements.md` v2.3（§21、§22、§26） |
| **相关 API** | `04-portfolio-api`（共享 Portfolio 语义）、`02-fund-api`（Universe） |

---

## 15. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.5** | 2026-08-27 | **第二批定案（1 项）**。`BA-3` `INVALID` 回测的绩效字段**照常返回**但 `validation_status` 置顶 —— 置空会让使用方只知道「不行」而不知道差在哪；风险由「状态先于绩效字段出现」与导出报告首页标识来控制。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.4** | 2026-08-27 | **Policy ⑨ 同步**。§4.5 响应新增 `significance_verdict` 四层结构；新增 §4.5.3 —— 阈值未校准时 `passed` 为 **`null`**（不是 `false`）且 `overall` 取 `NOT_SIGNIFICANT`（不是 `CANNOT_DETERMINE`，后者留给数据不足的情形，且中性值会被误当作放行）；各判据须分别给出对 Benchmark 与对 Equal Weight 两个值；API 不得以字段形式重新引入「接近显著」。原 §4.5.3 顺移为 §4.5.4。详见 `TBD-resolution.md` Policy ⑨ | `08-backtest/02` v1.1、`08-backtest/06` v1.1 |
| **v1.3** | 2026-08-27 | **Policy ⑩ 同步**。§4.9 响应新增 `excluded_costs` 并把 `cost_by_type` 的省略值改为完整数值；新增 §4.9.1 —— 区分 `INCLUDED_IN_NAV`（已扣过，无影响）与 `INCLUSION_UNKNOWN`（可能没扣，成本被低估）两种排除原因，并厘清 `excluded_costs` 与 `unmodeled_costs` 的分工。详见 `TBD-resolution.md` Policy ⑩ | `08-backtest/05-transaction-cost` v1.1 |
| **v1.2** | 2026-08-27 | **§4.6 补 quality 分布**。`bias-check` 的 `point_in_time` 检查结果新增 `availability_quality_distribution`（`EXACT` / `DERIVED` / `INFERRED` 占比）—— 只看 `status` 会把「62% 精确 + 31% 有残余前视风险」与「100% 精确」当成同一件事。详见 `TBD-resolution.md` Policy ④ | `08-backtest/03-look-ahead-bias` v1.1 |
| **v1.1** | 2026-08-27 | **§10.1 改写**。原「三个 Policy Version 尚未纳入九项」的缺口关闭 —— 各域 Policy 归入第 10 类 `Policy Version` 的五个子项，本域的 `Methodology` 与 `Report` 两个 Policy 均归入 `validation_policy`。API 契约相应要求：`strategy_version` 与 `policy_version` 是两个并列顶层对象，后者五子项必须全部返回。详见 `TBD-resolution.md` Policy ⑧ | `02-architecture/01-system-architecture` v2.4 |
| v1.0 | 2026-08-27 | 初始版本。**§4.1.1 创建与执行分离**、**§4.1.2 `backtest_mode` 必填**、§4.1.3 等权基线默认启用；**§4.2 新增配置预校验端点**并要求 **§4.2.2 返回 Warm-up 后的有效区间**（用户按配置区间理解长度是错的）；**§4.3.2 重跑产生新 Run 不覆盖**；**§4.4.2 `COMPLETED` 不等于 `VALID`**、§4.4.3 `total_periods` 是估算；**§4.5.1 摘要必须含等权基线与 `validation_status`**；**§4.6 偏差检查端点**及 **§4.6.1 `NOT_VERIFIED` 是独立枚举值**、§4.6.2 未建模成本必列、§4.6.4 缺失即视为不可用；**§4.7.1 IS/OOS 可分段查询**、§4.7.3 `warm_up_end_date` 必返；**§4.8.1 五个必答问题的下钻入口**；**§4.9.1 API 须说明管理费不在成本中**；**§6.1 `INVALID` 返回 200 但不得"看起来正常"**、**§6.2 `ABORTED` 仍须可查** | `08-backtest` v1.0、`10-api/01-api-overview.md` v1.0 |