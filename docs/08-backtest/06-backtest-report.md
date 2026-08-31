# 回测报告 · Backtest Report

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑧ Backtest**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§22.1、§26.4
> 本域上游：docs/08-backtest/02-backtest-methodology.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **回测结果如何被组织、呈现与判定为可用？**

### 1.2 报告不只是展示，它承载一道 Gate ⚠️

> **上游 §4.2 ⑧ 关键约束：任何未声明处理方式的回测结果不得作为决策依据。**

```
Backtest Report 不是"把数字画出来"
    → 它是【回测结果能否被使用】的判定载体
    → Validation Status 与 Bias Check 是其核心，不是附录
```

### 1.3 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 引擎如何执行 | `01-backtest-engine` |
| 指标如何计算、如何解读 | `02-backtest-methodology` |
| 偏差如何检测 | `03` / `04` |
| 成本如何建模 | `05-transaction-cost` |
| 策略上线的治理流程与 Gate 阈值 | `13-governance` |
| 报告的界面呈现 | `10-api` / 前端 |

---

## 2. 报告必须回答的九个问题

| # | 问题 | 章节 |
|---|---|---|
| 1 | **测的是什么？** | §3 元数据 + §4 配置摘要 |
| 2 | **测的是哪段时间？** | §3 |
| 3 | **用了什么假设？** | §4 + §14 |
| 4 | **产生了什么组合？** | §8 组合构成 |
| 5 | **收益如何？** | §6 / §7 |
| 6 | **承担了什么风险？** | §10 |
| 7 | **付出了什么成本？** | §11 |
| 8 | **与基准比如何？** | §7 三方对比 |
| 9 | **有没有数据或方法问题？** | §12 / §13 |

---

## 3. Report Metadata

| 字段 | 说明 |
|---|---|
| **`backtest_id`** | 唯一标识 |
| **`strategy_id`** / `portfolio_id` | 被测策略 |
| **`start_date`** / **`end_date`** | 回测区间 |
| **`warm_up_end_date`** | 绩效计算起点（`02` §5.2） |
| **`is_oos_split`** + **`parameter_freeze_date`** | IS/OOS 划分（`02` §4） |
| `run_timestamp` | 运行时刻 |
| **`configuration_version`** | 回测配置版本 |
| **`data_version`** | 数据版本 |
| **九项 Strategy Version** | 完整列出 |
| **`code_version`** | 策略库 / 求解器 / 数值库 |
| **`backtest_mode`** | `HISTORICAL_FIDELITY` / `CURRENT_RULE`（`03` §6.3） |
| **`methodology_policy_version`** | 判定规则版本 |
| **`transaction_cost_model_version`** | 成本模型版本 |

### 3.1 `backtest_mode` 必须在报告首屏

> **它决定了这份报告回答的是哪个问题**（`03` §6.6）：

```
HISTORICAL_FIDELITY → "当时的策略会怎样"
CURRENT_RULE        → "用今天的规则在历史上会怎样"
```

未标注模式的报告**无法被正确解读**。

---

## 4. 配置摘要

> **§2 第 3 问"用了什么假设"的主体。**

| 项 | 内容 |
|---|---|
| 初始资金 / 初始持仓 | `01` §7 |
| **调仓策略与四个阈值** | `06-portfolio/06` |
| **执行价格规则** | `01` §10 |
| **现金收益假设** | `01` §14 |
| **不可行处理策略** | `01` §18（默认 `ABORT`） |
| **成本模型与参数** | `05` §16 |
| **未建模的成本项** | `05` §12.2 |
| Benchmark 与 Equal Weight 基线定义 | `02` §7 |
| 组合层 Sortino 的下行阈值 | `02` §8.3 |

---

## 5. Executive Summary

| 指标 | 说明 |
|---|---|
| Total Return | 全期累计收益（**Net**） |
| Annualized Return | 年化收益（Net） |
| Volatility | 年化波动率 |
| Maximum Drawdown | 最大回撤 |
| Sharpe Ratio | 风险调整收益 |
| Benchmark Return | 基准同期收益 |
| **Equal Weight Baseline Return** | **等权基线同期收益** |
| Excess Return | 相对基准与相对基线**各一** |
| **Validation Status** | §13 |

### 5.1 摘要必须含等权基线，不只是 Benchmark ⚠️

> **沿用 `02-backtest-methodology` §7.1：** 若摘要只给 Benchmark 对比，读者会漏掉"策略是否值得其复杂度"这一关键判断。

### 5.2 摘要必须含 Validation Status

> **一份 `INVALID` 回测的漂亮摘要是危险的** —— 状态必须与数字同屏，不能藏在报告末尾。

---

## 6. Performance Summary

### 6.1 三方对比表

| Metric | Portfolio | Benchmark | Equal Weight | vs Benchmark | vs Equal Weight |
|---|---|---|---|---|---|
| Total Return | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Annualized Return | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| **Volatility** | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| **Maximum Drawdown** | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Sharpe Ratio | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Sortino Ratio | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Calmar Ratio | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |

> **风险维度必须与收益维度并列呈现**（`02` §7.4）—— 只比收益会把高风险误认为高能力。

### 6.2 IS / OOS 必须分段呈现 ⚠️

```
整段结果  ← 容易掩盖 IS 与 OOS 的差异
IS 段结果
OOS 段结果  ← 【策略批准的依据】（02 §4 规则 4）
```

> **IS 与 OOS 表现差异悬殊是过拟合信号**（`02` §18），只给整段结果会掩盖它。

### 6.3 相对基准的指标

| 指标 | 说明 |
|---|---|
| Alpha / Beta | 相对 Benchmark |
| Tracking Error | 相对 Benchmark |
| **Information Ratio** | 相对 Benchmark **与** 相对 Equal Weight **各一**（`02` §9.3.1） |
| R² | 相对 Benchmark |

---

## 7. 统计判定结果

> **呈现 `02-backtest-methodology` §9 的四层判据**（v1.1 —— 由三重证据扩为四层，见 `02-business-requirements` §22.2.2）。

| 层 | 判据 | 对 Benchmark | 对 Equal Weight | 阈值 | 通过 |
|---|---|---|---|---|---|
| **① 统计显著性** | Bootstrap 区间下界 | `TBD` | `TBD` | `> 0` | `TBD` |
| **② 效应量** | Information Ratio | `TBD` | `TBD` | `TBD` | `TBD` |
| **② 效应量** | ΔSharpe | `TBD` | `TBD` | `TBD` | `TBD` |
| **③ 稳健性** | 跑赢概率 | `TBD` | `TBD` | `TBD` | `TBD` |
| **④ 经济显著性** | 年化收益改善 | `TBD` | `TBD` | `TBD` | `TBD` |
| **④ 经济显著性** | 最大回撤改善 | `TBD` | `TBD` | `TBD` | `TBD` |

> **第②层内部是 AND，第④层内部是 OR，层与层之间是 AND**（`02-backtest-methodology` §9.3.4）。报告须呈现每一行的通过与否，而非只给一个总判定 —— 使用方需要知道是哪一层没过。

### 7.0 呈现顺序按层而非按指标

> **四层是有逻辑次序的**：① 差异是否真实 → ② 差异有多大 → ③ 是否稳定 → ④ 是否值得。

按此顺序呈现，读者能自然地在第一个不通过的层停下。按指标名字母序或按数值大小排列会打断这个推理链。

### 7.1 必须同时呈现判定参数

| 参数 | 理由 |
|---|---|
| **滚动窗口长度与步长** | 跑赢概率对此高度敏感（`02` §9.3.2） |
| **Bootstrap 块长、次数、置信水平、随机种子** | 否则判定不可复现（`02` §9.5） |
| **OOS 样本期长度** | 判断结论强度（`02` §9.4） |
| **尝试过的配置数量** | 多重检验背景（`02` §12.1） |

### 7.2 阈值未定案前不得出现"显著优于" ⚠️

> **沿用 `02-business-requirements` §22.2：**

```
❌ "该策略显著优于基准"
✅ "该策略在回测期内年化超额 X%，IR 为 X（阈值待定案）"
```

**报告模板层面即应阻止该表述** —— 不能依赖撰写者自觉。

#### 7.2.1 `prohibited_expressions` 的执行机制（v1.1 定案）

> **定案 · 2026-08-27**：见 §17 `Report Policy`、`TBD-resolution.md` Policy ⑨。

| 状态 | 允许的表述 |
|---|---|
| **四层阈值未定案** | 只能陈述**数值差异**；「显著」「优于」「跑赢」等结论性词汇一律禁止 |
| 阈值已定案且四层全过 | 可用「显著优于」 |
| 阈值已定案但任一层未过 | **仍只能陈述数值差异** —— 不得用「接近显著」「趋势上优于」等软化表述 |

**禁用词表**（`prohibited_expressions` 的初始内容）：

```
显著优于 / 显著跑赢 / 明显好于 / 接近显著 / 趋势上优于 / 基本达标
```

> **「接近显著」比「显著优于」更危险** —— 后者是明确的错误主张，会被审阅者抓住；前者听起来诚实，实际上把未通过判定的结果包装成了正面结论，且难以反驳。因此它同样进禁用词表。

> **执行位置在报告生成层，不在撰写层** —— 模板渲染时校验，命中禁用词则报告状态 `INVALID`。依赖撰写者自觉等于没有约束。

---

## 8. Time Series

| 序列 | 说明 |
|---|---|
| **Portfolio Value** | 组合净值（Net） |
| **Portfolio Return** | 逐期收益 |
| **Cumulative Return** | 累计收益，与 Benchmark、Equal Weight 同图 |
| **Drawdown** | 回撤序列 |
| **Rolling Sharpe / Volatility** | 滚动指标（支撑 `02` §10 第 2 问） |
| **Rolling Excess Return** | 滚动超额（支撑第 4 问"是否存在明显失效阶段"） |

### 8.1 Warm-up 期须在图上标出

> 绩效从 `warm_up_end_date` 起算，图上应显示该分界，避免读者误以为回测从 `start_date` 就在运作。

---

## 9. Portfolio Composition

| 内容 | 说明 |
|---|---|
| **Asset Allocation 时序** | 类别权重随时间变化 |
| **Fund Weights** | 逐期成分与权重 |
| **Weight Changes** | 期间变动 |
| **Concentration** | HHI / 前 N 大权重占比 |
| **持仓基金数** | 随时间变化 |

### 9.1 收益归因至个基（业务硬要求）

> **支撑 `02` §10 第 5 问"是否过度依赖某些基金"。**

```
逐基金的收益贡献 = Σ (该基金各期权重 × 该基金各期收益)
```

**必须呈现贡献集中度** —— 若收益集中于一两只基金，说明**在押注个基而非依靠规则**（`02-business-requirements` §22.3）。

### 9.2 分阶段 / 分市场环境归因（业务硬要求）

> **支撑第 4、6 问。**

| 切分方式 | 说明 |
|---|---|
| **分年度** | 策略是否长期有效 |
| **分市场环境** | 上涨 / 下跌 / 震荡区间的表现 |

> **若超额收益全部产生于某一段行情，说明策略是环境依赖的** —— 这必须被显式呈现，而非埋在整段平均数里。

> **推荐默认 · 2026-08-27**：市场环境按 **Benchmark 年度收益三分档** —— `< -10%` 熊市、`-10% ~ 10%` 震荡、`> 10%` 牛市。业务方可改。
>
> **依据**：用 Benchmark 而非绝对收益划分，使分档与组合的比较基准一致。三档是能保证每档有足够样本的最细粒度 —— 五档会让 8 年区间内某些档只有一两年。
>
> **划分须在报告中显式声明** —— 环境依赖的判定（`BM-6`）直接依赖本划分，换一套阈值会改变结论。

---

## 10. Risk Summary

| 指标 | 说明 |
|---|---|
| Volatility | 年化 |
| **Downside Volatility** | 阈值见 `02` §8.3 |
| **Maximum Drawdown** + Drawdown Duration | 含回撤持续期 |
| VaR 95% / CVaR 95% | 组合层，按组合净值序列计算 |
| Tracking Error | 相对 Benchmark |

### 10.1 组合层指标由组合净值序列直接计算

> **沿用 `02` §8.1：不是成分指标的加权。** 回测的优势正在于它有真实的组合净值序列。

### 10.2 Risk Budget 达成情况

> **沿用上游 ⑦-R：Risk Budget（事前）与 Risk Contribution（事后）必须同时留存。**

| 呈现 | 说明 |
|---|---|
| 各期的 Risk Budget 设定 | 事前目标 |
| 各期的实际 Risk Contribution | 事后结果 |
| **超预算的期次** | `BREACHED` 的时点与幅度 |

---

## 11. Transaction Cost Summary

| 项 | 说明 |
|---|---|
| **Gross Return** | 不含成本 |
| **Transaction Cost** | 累计，且按类型拆分（申购 / 赎回 / 其他） |
| **Net Return** | 含成本 —— **全部绩效判定基于此** |
| **成本侵蚀比例** | `(Gross − Net) / \|Gross\|` |
| **Turnover** | 单边口径，年化与累计 |
| **调仓次数** | 按触发类型拆分 |
| **`unmodeled_costs`** | **未建模的成本项清单** |

### 11.1 未建模成本必须与成本数字同屏 ⚠️

> **沿用 `05-transaction-cost` §12.2：未声明的简化 = 回测高估了表现而读者不知情。**

```
报告显示：Transaction Cost = 0.8%/年
若未标注"场内价差与冲击成本未建模"
    → 读者会以为 0.8% 就是全部成本
```

### 11.2 成本按触发类型拆分

> 便于回答"哪类调仓最费钱"：

| 触发类型 | 调仓次数 | 换手 | 成本 |
|---|---|---|---|
| Periodic | `TBD` | `TBD` | `TBD` |
| Drift | `TBD` | `TBD` | `TBD` |
| Eligibility Event | `TBD` | `TBD` | `TBD` |
| Constraint Breach | `TBD` | `TBD` | `TBD` |

---

## 12. Bias Check（核心）⚠️

> **上游 §4.2 ⑧ 关键约束：必须显式处理并在报告中声明四类问题。**

| 检查 | 状态 | 来源 |
|---|---|---|
| **Look-ahead Bias** | `PASS` / `FAIL` | `03` §16.2 |
| **Survivorship Bias** | `PASS` / `FAIL` | `04` §15.2 |
| **Tradability Bias** | `PASS` / `FAIL` / **`NOT_VERIFIED`** | `04` §15.2 |
| **Point-in-Time** | `PASS` / `FAIL` | `03` §13.3 三层检测 |
| **Transaction Cost** | 已计入 / 部分计入 | `05` |
| **申赎限制与到账时滞** | 已建模 / **未建模** | `01` §10.3 |

### 12.1 `NOT_VERIFIED` 是独立状态，不等于 `PASS` ⚠️

> **沿用 `04` §11.6：`Investment Eligibility` 历史数据缺失时不得默认为合规。**

```
PASS         → 检查了，通过
FAIL         → 检查了，未通过
NOT_VERIFIED → 【没法检查】—— 数据不足
```

**把 `NOT_VERIFIED` 当作 `PASS` 是把"不知道"当作"没问题"** —— 与全平台的同一条原则一致。

### 12.2 未声明处理方式的结果不得作为决策依据

> **这是上游的硬性约束，不是建议。** 报告若缺少 Bias Check 章节，该回测结果**不可使用**。

### 12.3 快照 vs 重建的比例必须呈现

> **沿用 `01` §8.4：**

```
快照期数 : X / N
重建期数 : X / N
重建期清单 : [T1, T5, T12…]
```

> 重建的可信度低于快照 —— 混在一起呈现会误导。

---

## 13. Data Quality

| 项 | 说明 |
|---|---|
| **缺失数据** | 期次、基金、字段 |
| **历史不足**（`INSUFFICIENT_DATA`） | 被排除的基金与期次 |
| **无效数据**（`INVALID`） | 触发告警的项 |
| **被排除的基金** | 逐只原因 |
| **Benchmark 缺失期** | 相对指标不可算的期次 |
| **成本数据缺失** | 费率缺失的基金（`05` §17.1） |
| **估计被 Gate 拒绝的期次** | `07-return-risk/06` |
| **优化不可行的期次** | `01` §18 |

### 13.1 数据质量问题的期次分布比总量更重要

```
"5% 的期次有数据问题" → 看起来可接受
但若这 5% 全部集中在市场剧烈波动期
    → 恰是策略最该被检验的时候数据不可靠
```

> 与 `07-return-risk/06` §9.7.1「VaR Exception 的聚集性比总数更重要」是同一类判断。

---

## 14. Validation Status

### 14.1 三态

| 状态 | 含义 | 可用于策略比较 |
|---|---|---|
| **`VALID`** | 全部关键检查通过 | ✅ |
| **`WARNING`** | 存在非关键问题 | ✅ 须携带标记 |
| **`INVALID`** | 存在关键问题 | ❌ |

### 14.2 判定为 `INVALID` 的情形

> **沿用提示词 §26 与本域各文档：**

| # | 情形 | 来源 |
|---|---|---|
| 1 | **检测到前视偏差** | `03` §15 |
| 2 | **Universe 与历史不符** | `04` §12 |
| 3 | 关键数据缺失导致中止 | `01` §8.3 |
| 4 | 协方差矩阵无效 | `07-return-risk/04` §10 |
| 5 | 优化不可行且未按声明策略处理 | `01` §18 |
| 6 | 交易成本无效或存在重复计入 | `05` §14 |
| 7 | 组合约束被违反 | `06-portfolio/05` |
| 8 | 数值失败 | `01` §17 |
| 9 | **Bias Check 章节缺失** | §12.2 |

### 14.3 `COMPLETED` 不等于 `VALID`

> 沿用 `01` §21.2：执行完成不代表结果可用。

### 14.4 `INVALID` 的回测不得用于策略比较 ⚠️

```
❌ "虽然这次回测检测到前视，但结果仅供参考"
   → 前视污染的结果比没有结果更危险
   → 它会给出一个看起来合理但系统性偏优的数字
```

**`INVALID` 的回测应当被明确标记并排除出比较，而非"打折使用"。**

### 14.5 降级为 `WARNING` 的情形

| 情形 | 来源 |
|---|---|
| 重建期占比超阈值 | `01` §8.4 |
| Tradability `NOT_VERIFIED` | §12.1 |
| 部分成本未建模 | `05` §12.2 |
| 窗口跨越基金转型 | `04` §9.1 |
| OOS 样本期不足 | `02` §9.4 |
| 数据质量问题集中于特定期 | §13.1 |

---

## 15. Limitations

> **必须显式披露**（`02` §14）。

| 类别 | 说明 |
|---|---|
| **历史依赖** | 回测只能覆盖历史出现过的市场状态 |
| **模型风险** | 估计方法、优化目标的选择本身是假设 |
| **参数风险** | 历史有效不保证未来有效 |
| **数据风险** | 修订、缺失、质量问题会影响结果 |
| **执行假设** | 成交价格、时滞、可成交量的简化 |
| **成本假设** | 成本模型的简化与未建模项 |
| **样本期限制** | OOS 段长度可能不足以支撑强结论 |
| **多重检验背景** | 本次判定是从多少候选中选出的 |

### 15.1 最根本的一条

> **回测不保证未来表现。** 它只能回答"若当时如此做会怎样"，**不能回答"今后如此做会怎样"**。

### 15.2 Limitations 不是免责声明 ⚠️

> **它是解读结果的必要上下文。**

```
❌ 放在报告末尾的固定段落，从不更新
✅ 逐次回测生成，反映【本次】的实际局限
   （如：本次未建模场内价差；本次 12 期为重建产物；本次 OOS 仅 2 年）
```

---

## 16. Audit Trail

> **沿用 `01` §25：逐期决策的完整追溯链。**

### 16.1 报告须提供五个必答问题的入口

| 问题 | 入口 |
|---|---|
| **Fund A 为什么被选中？** | 该期 Fund Evaluation / Selection 快照 |
| **Fund A 为什么占 X%？** | 该期 Optimization 结果与紧约束 |
| **Fund A 为什么被卖出？** | 该期 Rebalancing Trigger |
| **为什么净收益低于毛收益？** | Transaction Cost 明细（`05` §18.2） |
| **这次回测能复现吗？** | §3 元数据的全部版本引用 |

### 16.2 中止与失败同样要在报告中体现

> `ABORTED` 的回测也须产出报告 —— 记录中止原因、时点、缺失数据清单（`01` §25.3）。**它是有效信息，不是"什么都没发生"。**

---

## 17. Report Policy

| 字段 | 说明 |
|---|---|
| `policy_id` / `version` | 标识与版本 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`required_sections`** | 必备章节（含 Bias Check —— 缺失则 `INVALID`） |
| **`validation_rules`** | `VALID` / `WARNING` / `INVALID` 的判定规则 |
| **`warning_thresholds`** | 降级阈值（重建期占比、OOS 长度等） |
| **`metric_set`** | 呈现的指标清单（引用 `04-factor`） |
| **`market_regime_definition`** | 市场环境划分标准 |
| `prohibited_expressions` | **已定案初始词表**（§7.2.1）：显著优于 / 显著跑赢 / 明显好于 / **接近显著** / 趋势上优于 / 基本达标。在报告生成层校验，命中则报告 `INVALID` |

---

## 18. Input / Output

### 18.1 Input

| 输入 | 来源 |
|---|---|
| Backtest Result（净值、快照、交易明细） | `01-backtest-engine` |
| 绩效指标与三重证据判定 | `02-backtest-methodology` |
| Look-ahead 检测结果 | `03-look-ahead-bias` |
| Survivorship / Tradability 检测结果 | `04-survivorship-bias` |
| 成本汇总与未建模项 | `05-transaction-cost` |
| Report Policy + version | 本文档 §17 |

### 18.2 Output

| 输出 | 说明 |
|---|---|
| **完整回测报告** | §3–§16 全部章节 |
| **`validation_status`** | `VALID` / `WARNING` / `INVALID` |
| **降级/失效原因清单** | 逐条 |
| 机器可读的结果集 | 供 `13-governance` 的策略上线 Gate 消费 |

---

## 19. Edge Cases

| 情形 | 处理 |
|---|---|
| 回测 `ABORTED` | **仍须产出报告**，记录中止原因（§16.2） |
| Benchmark 全期缺失 | 相对指标与证据一不可用 → 三重证据不成立 → **不得给出"优于"结论** |
| 等权基线不可构造 | 报告标注；`Baseline Gate` 无法评估 |
| OOS 段为空（未划分） | **不得用于策略批准**（`02` §4 规则 4） |
| 全部期次均为重建产物 | `WARNING` 或 `INVALID`（按阈值） |
| Bias Check 任一为 `FAIL` | **`INVALID`** |
| Tradability `NOT_VERIFIED` | `WARNING`，不得计为 `PASS` |
| 成本侵蚀比例为负 | **异常** —— Net > Gross 说明成本计算有误，`INVALID` |
| 报告缺少 Limitations | **不符合 Report Policy** —— 视为报告未完成 |

---

## 20. Reproducibility

```
Backtest Result（含全部版本引用）
+ Report Policy Version
+ Methodology Policy Version
        ↓
    相同的报告内容与 Validation Status
```

### 20.1 判定规则版本必须随报告落库

> 与 `07-return-risk/06` §18.1 同理：**阈值放宽后重跑会得到不同的 Validation Status**。若不记录 `report_policy_version`，历史报告的判定无法解释。

---

## 21. Summary

**报告不只是展示，它承载一道 Gate** —— 上游明确：任何未声明处理方式的回测结果不得作为决策依据。

三处呈现上的硬要求：

- **摘要必须含等权基线与 Validation Status** —— 只给 Benchmark 对比会漏掉"策略是否值得其复杂度"；一份 `INVALID` 回测的漂亮摘要是危险的，状态不能藏在末尾
- **IS / OOS 必须分段呈现** —— 只给整段结果会掩盖过拟合信号，而 OOS 才是策略批准的依据
- **未建模成本必须与成本数字同屏** —— 否则读者会以为显示的就是全部成本

三处状态判定的要点：

- **`NOT_VERIFIED` 是独立状态，不等于 `PASS`** —— 把"没法检查"当作"检查通过"，是把"不知道"当作"没问题"
- **`INVALID` 的回测不得"打折使用"** —— 前视污染的结果比没有结果更危险，它会给出一个看起来合理但系统性偏优的数字
- **数据质量问题的期次分布比总量更重要** —— 5% 的问题期若全部集中在市场剧烈波动期，恰是策略最该被检验的时候数据不可靠

一处常被形式化的内容：**Limitations 不是免责声明** —— 它必须逐次生成，反映本次的实际局限（未建模了什么、多少期是重建、OOS 有多长），而非固定不变的段落。

---

## 22. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **报告承载 Gate，Bias Check 是核心而非附录** | 上游 §4.2 ⑧ |
| D-2 | **`backtest_mode` 必须在首屏** | 决定报告回答的是哪个问题 |
| D-3 | **摘要必须含等权基线** | 否则漏掉复杂度是否值得的判断 |
| D-4 | **摘要必须含 Validation Status** | 状态与数字须同屏 |
| D-5 | **IS / OOS 分段呈现** | 整段结果掩盖过拟合信号 |
| D-6 | 风险维度与收益维度并列 | 只比收益会误判高风险为高能力 |
| D-7 | IR 须对 Benchmark 与等权基线**各算一份** | 三重证据的证据一 |
| D-8 | **判定参数必须与判定结果同时呈现** | 否则判定不可复现 |
| D-9 | **报告模板层面阻止"显著优于"表述** | 不能依赖撰写者自觉 |
| D-10 | 收益归因至个基、分阶段归因为**硬要求** | 支撑八个必答问题 |
| D-11 | **`NOT_VERIFIED` 是独立状态** | 不得计为 `PASS` |
| D-12 | **快照 vs 重建比例必须呈现** | 可信度不同 |
| D-13 | **`INVALID` 不得用于策略比较** | 污染结果比没有结果更危险 |
| D-14 | **`ABORTED` 的回测仍须产出报告** | 中止原因是有效信息 |
| D-15 | **Limitations 逐次生成，非固定段落** | 它是解读结果的必要上下文 |
| D-16 | `report_policy_version` 随报告落库 | 阈值变更后判定可解释 |

---

## 23. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | **必须显式声明四类问题的处理方式** | 上游 §4.2 ⑧ |
| C-2 | **未声明处理方式的结果不得作为决策依据** | 同上 |
| C-3 | 回测报告必须显式声明三类偏差的处理 | `02-business-requirements` §26.4 |
| C-4 | 必须回答八个业务问题 | `02-business-requirements` §22.1 |
| C-5 | 必须呈现三方对比 | `02-business-requirements` §21.6 |
| C-6 | 阈值定案前不得使用"显著优于" | `02-business-requirements` §22.2 |
| C-7 | 全部绩效基于 Net Return | `05-transaction-cost` §10.2 |
| C-8 | 指标定义复用 `04-factor` | `02-backtest-methodology` §8 |
| C-9 | Risk Budget 与 Risk Contribution 须同时呈现 | 上游 §4.2 ⑦-R |
| C-10 | 必须披露 Limitations | `02-backtest-methodology` §14 |

---

## 24. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~BR-1~~ | ~~市场环境的划分标准~~ —— **推荐默认**：市场环境按 Benchmark 年度收益三分档：< -10% 熊市、-10%~10% 震荡、> 10% 牛市 | — | ✅ 2026-08-27 |
| BR-2 | `WARNING` 各项的降级阈值 | Validation Status | 投研 + 治理 |
| BR-3 | 报告的必备章节清单与模板 | 报告完整性 | 产品 + 治理 |
| BR-4 | 机器可读结果集的结构（供 `13-governance` 消费） | 上线 Gate 集成 | 治理 + 技术 |

---

## 25. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ⑧ 关键约束、⑦-R）、`02-business-requirements.md` v2.3（§22.1、§22.4、§26.4） |
| **本域** | `01-backtest-engine`（结果与中止）、`02-backtest-methodology`（指标与判定）、`03-look-ahead-bias`、`04-survivorship-bias`、`05-transaction-cost` |
| **指标定义** | `04-factor/03-factor-definition` |
| **下游** | `13-governance`（策略上线的八个 Gate，消费本报告）、`12-operations`（回测运行监控） |

---

## 26. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（1 项）**。`BR-1` 市场环境按 Benchmark 年度收益**三分档**（熊 < -10% / 震荡 / 牛 > 10%），划分须在报告中显式声明 —— `BM-6` 的环境依赖判定直接依赖它。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.1** | 2026-08-27 | **Policy ⑨ 落地**。§7 判定表由三重证据扩为**四层六行**（第②层含 ΔSharpe、第④层含年化改善与回撤改善）；新增 §7.0 —— 按层而非按指标呈现，使读者能在第一个不通过的层停下；新增 §7.2.1 —— `prohibited_expressions` 初始词表定案，并说明**「接近显著」比「显著优于」更危险**（听起来诚实却把未通过的结果包装成正面结论），执行位置在报告生成层而非撰写层。§17 `Report Policy` 同步。详见 `TBD-resolution.md` Policy ⑨ | `02-backtest-methodology` v1.1、`02-business-requirements` v2.7 §22.2.2 |
| v1.0 | 2026-08-26 | 初始版本。**§1.2 报告承载 Gate 而非仅展示**；**§3.1 `backtest_mode` 必须在首屏**；**§5.1–5.2 摘要必须含等权基线与 Validation Status**；**§6.2 IS/OOS 必须分段呈现**；**§7.1 判定参数须与结果同时呈现**、**§7.2 报告模板层面阻止"显著优于"**；§9.1–9.2 收益归因至个基与分阶段归因为业务硬要求；**§11.1 未建模成本须与成本数字同屏**；**§12.1 `NOT_VERIFIED` 是独立状态**；§12.3 快照 vs 重建比例须呈现；**§13.1 数据质量问题的期次分布比总量更重要**；**§14.4 `INVALID` 不得"打折使用"**；**§15.2 Limitations 不是免责声明**，须逐次生成；§16.2 `ABORTED` 仍须产出报告 | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`08-backtest` 01–05 v1.0 |