# 再平衡 · Rebalancing

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑨ Live Portfolio** + **⑩ Rebalancing** + **⑩-T**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§28 Rebalancing
> 本域上游：docs/06-portfolio/03-portfolio-optimization.md、05-constraints.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **组合何时、如何从当前权重调整到目标权重？**

### 1.2 Rebalancing ≠ Optimization ⚠️

```
Current Portfolio
       ↓
   Optimization   ← 生成 Target Portfolio（03）
       ↓
Target Portfolio
       ↓
   Rebalancing    ← 从 Current 调整到 Target（本文档）
       ↓
  New Portfolio
```

| | **Optimization** | **Rebalancing** |
|---|---|---|
| 产出 | Target Portfolio | **调仓建议**（买卖清单） |
| 关注 | 最优权重是什么 | **是否值得调、怎么调** |
| 输入 | `μ`、`Σ`、约束 | Current + Target + 成本 |

### 1.3 再平衡不是简单的比例复原 ⚠️

> **上游 §4.2 ⑩ 边界条款：**

```
❌ "再平衡 = 把权重调回目标比例"
✅ 再平衡是一次 Strategy Re-evaluation（策略重评估）
   → 重算范围由触发类型决定
   → 基金池本身可能已经变化
```

### 1.4 本域不执行交易

> 平台输出指令，实际下单、成交、清算由**外部交易系统**负责（上游 §6 Out of Scope）。

---

## 2. 三态：本文档的基础

> **沿用上游 ⑨-S 与 `02-architecture/01-system-architecture` §12。**

| 状态 | 含义 | 来源 |
|---|---|---|
| **`Target Portfolio`** | 决策确定的目标持仓与权重 | `Approved Investment Decision` |
| **`Pending Execution`** | 已交付执行但**尚未收到回报**的调整 | 建议已交付、Fill 未回 |
| **`Actual Portfolio`** | **实际持仓与权重** | **外部执行/清算系统的回报** |

### 2.1 状态使用规则

| 用途 | 使用的状态 |
|---|---|
| **Drift 检测（触发再平衡）** | **`Actual` vs `Target`** |
| 事后组合风险 | `Actual` |
| 约束合规校验 | `Target`（决策时）+ `Actual`（持续监控） |
| Backtest-Live Deviation | `Actual` |
| 展示"当前持仓" | `Actual`，并标注是否存在 `Pending` |

### 2.2 不得以 `Target` 冒充 `Actual` ⚠️

> **这是三态分离的根本原因。**

```
刚下单，Fill 未回
  若用 Target 冒充 Actual
    → Drift = |Target − Target| = 0
    → 得出"刚下单就零偏离"的错误结论
    → 且无法表达部分成交
```

**回报缺失或延迟时**，`Actual Portfolio` 标记为**待确认**，`Pending` 部分显式呈现。

### 2.3 `Pending Execution` 期间不应重复触发调仓 ⚠️

> **这是三态在再平衡逻辑中的直接后果。**

```
T 日：检测到 Drift 超阈值 → 产出调仓建议 → 交付执行
T+1：Fill 未回，Actual 仍是旧权重
     → Drift 依然超阈值
     → 若不判断 Pending 状态，会再次产出同一份调仓建议
     → 重复下单
```

**要求**：Drift 检测必须先检查是否存在未完成的 `Pending Execution`。存在时**不产出新的调仓建议**，除非该 Pending 已超时（见 §11）。

---

## 3. Rebalancing Trigger（已定案）

> **沿用上游 §4.2 ⑩-T 与 `02-business-requirements` §28.1。再平衡触发 ≠ 必然重算整条链路。**

| 触发类型 | 触发条件 | 重算范围 |
|---|---|---|
| **Periodic** | 调仓周期到期 | **Full Pipeline**：Factor → Score → Universe → ⑤ → ⑥ → ⑦ |
| **Drift** | 实际权重偏离目标超阈值 | ⑤ → ⑥ → ⑦（**Universe 与 Score 不变**） |
| **Eligibility Event** | 成分基金失去可投资性 | Universe → ⑤ → ⑥ → ⑦ |
| **Constraint Breach** | 触碰约束上限 | ⑥ → ⑦（**仅重新求解**） |

### 3.1 为什么必须分级

> **全链路重跑代价高，且会在无必要时改变基金池，引入非预期换手。**

```
权重漂移只需要重新优化
    → 不应该顺带换掉一批基金
    → 否则一次 5% 的权重偏离，可能引发 30% 的换手
```

### 3.2 触发条件必须事先定义且可回测

> **不得由人工临时决定，也不得在运行时动态调整重算深度**（上游 §4.2 ⑩ 关键约束、`02-business-requirements` §28.5）。

### 3.3 多个触发同时发生时取最深范围

> **上游未明确此情形，本域给出规则。**

```
同一时点既到调仓周期（Periodic）又有基金失去可投资性（Eligibility Event）
    → 取重算范围最深的那个（Periodic = Full Pipeline）
    → 而非分别执行两次
```

**理由**：分别执行会产生两次换手，且第二次基于第一次的结果，路径依赖使结果不可复现。

**重算深度序**：`Constraint Breach` < `Drift` < `Eligibility Event` < `Periodic`

> **已定案 · 2026-08-27**：多触发并发时采用**取最深**合并。
>
> **依据**：各触发类型的重算范围是**嵌套的** ——
>
> ```
> Drift 触发      → 仅重新配平权重（不重选基金）
> Periodic 触发   → 重跑评分与选基
> Event 触发      → 重跑全链路（含 Universe 重构）
>
> 三者同时触发时，最深的那个【已包含】其余两个的工作
> ```
>
> **「取并集」与「取最深」在结果上等价**，但后者的表述更准确 —— 并集暗示三次重算合并，实际只需执行一次最深的。
>
> **须记录全部触发原因而非只记最深的那个** —— 否则事后无法回答「这次调仓是什么引起的」，而多重触发本身就是一个值得关注的信号。

### 3.4 Frequency

```
Rebalancing Frequency = TBD
```

> **本参数当前为 TBD，投产前必须由业务负责人确认。** 本域不自行决定 Monthly / Quarterly。

> **推荐默认 · 2026-08-27**：Periodic 触发频率 = **季度**（同 `P1-16` 的默认调仓频率）。业务方可改。
>
> **依据**：季度在「响应市场变化」与「控制交易成本」之间取平衡。月度调仓的成本在基金申赎费率下显著（单边 0.15% + 赎回费阶梯），而基金的相对表现变化通常不会在一个月内产生足以覆盖该成本的改善。
>
> **改动时须同步核对 `RE-6`** —— 调仓频率是成本摊薄的分母，改频率会直接改变「是否值得调仓」的判定。

---

## 4. Drift

### 4.1 两种定义

| 定义 | 公式 |
|---|---|
| **Signed Drift** | `D_i = w_actual,i − w_target,i` |
| **Absolute Drift** | `D_i = \|w_actual,i − w_target,i\|` |

### 4.2 本项目的选择

> **触发判定使用 Absolute Drift；展示与归因使用 Signed Drift。**

| 用途 | 使用 |
|---|---|
| **触发判定** | **Absolute** —— 超配与低配都需要调整 |
| 展示与归因 | **Signed** —— 用户需要知道是超配还是低配 |
| 买卖方向 | **Signed** —— 符号决定买还是卖 |

> **只保留 Absolute 会丢失方向信息**，无法生成买卖清单；**只用 Signed 做触发**则需要分别判断正负阈值，且正负阈值通常相同，徒增配置项。

### 4.3 Drift 的两个层级

```
基金层 Drift    D_i = |w_actual,i − w_target,i|
类别层 Drift    D_k = |Σ_{i∈k} w_actual,i − Σ_{i∈k} w_target,i|
```

> **两者可能不一致** —— 类别内部两只基金一涨一跌，基金层 Drift 显著但类别层几乎为零。

**触发判定应同时考虑两个层级**，各自有独立阈值。

> **已定案 · 2026-08-27**：基金层与类别层 Drift 阈值**独立配置**。
>
> **依据 —— 两者的容忍度本就不同**：
>
> | 层 | 偏离的含义 | 容忍度 |
> |---|---|---|
> | **类别层** | 资产配置偏离目标 —— 直接改变组合的风险特征 | **较低** |
> | **基金层** | 类别内个基权重偏离 —— 在同类基金间的再分配 | 较高 |
> |
>
> 用同一个阈值会导致其中之一不合理：按类别层的严格度要求基金层，会因同类基金间的正常涨跌差异频繁触发调仓；按基金层的宽松度要求类别层，会让资产配置长期偏离目标而不被察觉。
>
> **两个阈值的具体取值属 `RE-4`**（= 上游 `P1-19`），仍待投研确定。本条定的是「必须是两个数」而非「这两个数是多少」。

### 4.4 Drift 的来源不只是净值波动

| 来源 | 说明 |
|---|---|
| **净值波动** | 主要来源，持续发生 |
| **分红** | 现金分红使权重下降（若不再投资） |
| **申赎** | 组合层面的资金流入流出 |
| **部分成交** | `Pending` 未完全成交 |

> 后三项使 Drift 出现**跳变**而非渐变，可能在两次检测之间就突破阈值。

---

## 5. Rebalancing Threshold

### 5.1 四个阈值（已定案结构）

> **沿用 `02-business-requirements` §28.2，四者共同构成 `Rebalance Rule Version`。**

| 阈值 | 作用 |
|---|---|
| **Weight Drift Threshold** | 单只基金权重偏离超过此值才触发 Drift 类型再平衡 |
| **Minimum Trade Threshold** | 单笔调整低于此值不执行 —— 避免成本高于收益的碎片交易 |
| **Turnover Threshold** | 单次调仓总换手上限，超过则需人工确认 |
| **Cost-Benefit Threshold** | 预期改善需超过成本的倍数才建议调仓 |

```
Weight Drift Threshold   = TBD
Minimum Trade Threshold  = TBD
Turnover Threshold       = TBD
Cost-Benefit Threshold   = TBD
```

`<TBD-RE-4: 四个阈值的具体取值（= 上游 TBD-P1-19），待组合管理与投研确认>`

### 5.2 Drift Threshold 与 Allocation Range 不是同一件事

> 沿用 `02-asset-allocation` §6.3：前者是**触发条件**，后者是**优化硬约束**，前者通常更窄。

### 5.3 Minimum Trade Threshold 是非凸约束 ⚠️

> **"单笔调整要么为零，要么至少 X"** 与 `03-portfolio-optimization` §4.5 的最小持仓量是同一类问题：

```
Δw_i = 0  或  |Δw_i| ≥ X
    → 半连续变量，非凸（混合整数）
```

**第一阶段处理**：在**优化之后**过滤 —— 把低于阈值的调整置零，**再重新校验约束**。

> **与 `03` §4.5 完全相同的代价**：过滤后的组合不再是最优解，且**可能违反原约束**（如过滤掉某笔卖出后单基金权重仍超限）。因此过滤后必须重新校验，不通过则回到优化环节，而不是接受违约结果。

---

## 6. Turnover

### 6.1 定义

```
Turnover = 0.5 × Σ |w_target,i − w_current,i|
```

### 6.2 系数 0.5 的含义必须说明

> **这是一个容易引起歧义的约定。**

```
不带 0.5：Σ|Δw| 计入了买入与卖出两侧
          → 全部换掉一个组合，Σ|Δw| = 200%

带 0.5：  表示"单边换手"
          → 全部换掉一个组合，Turnover = 100%
```

> **本项目采用单边口径（带 0.5）**。口径必须在 `Rebalancing Policy` 中显式声明 —— 否则换手率上限的含义会相差一倍。

### 6.3 首次建仓的换手率

```
INITIAL 模式：Turnover = 0.5 × Σ|w_target − 0| = 50%
```

> 按单边口径，首次建仓的换手率是 50% 而非 100%。**这更凸显了换手率约束不应适用于 `INITIAL` 模式**（`05-constraints` §8）—— 一个 50% 的数值看起来"没超 100%"，容易被误认为可以套用常规上限。

### 6.4 换手率与冻结持仓

> 冻结持仓（`NOT_TRADABLE`）的权重差异**不计入换手率** —— 它无法交易，计入会虚增换手并可能使约束不可行。

---

## 7. Transaction Cost

```
Transaction Cost Model → 见 `08-backtest/05-transaction-cost`
```

> **模型已由 `08-backtest/05-transaction-cost` 定义**（回测与实盘共用，符合单一策略实现原则）。本域不自行假设费率结构；**费率参数取值仍为 TBD**（该文档 §22）。

### 7.1 需要建模的成本项

| 成本项 | 说明 | 数据来源 |
|---|---|---|
| **申购费 / 赎回费** | 基金交易的显性成本 | `03-data`（`Fund Fee`）✅ 已有 |
| **赎回费的持有期阶梯** | 持有不满一定期限费率更高 | `03-data` 需确认是否含阶梯 |
| 冲击成本 | 大额交易对净值的影响 | **无数据支撑** |
| 税费 | 视市场与账户类型 | **无数据支撑** |

### 7.2 赎回费的持有期依赖使成本成为路径函数 ⚠️

> **这是基金组合与股票组合的一个重要差异。**

```
股票：交易成本 ≈ f(交易量)
基金：赎回费 = f(交易量, 持有期)
    → 同样卖出 5%，持有 6 天与持有 60 天的成本可能相差数倍
    → 因此调仓成本依赖【每一笔持仓的买入时点】
```

**后果**：

| # | 后果 |
|---|---|
| 1 | 成本计算需要**持仓明细的买入批次**，而非仅当前权重 |
| 2 | "先进先出"还是"后进先出"的批次选择会改变成本 |
| 3 | 频繁调仓的成本远高于按平均费率的估算 |

`<TBD-RE-5: 交易成本**模型结构**已由 `08-backtest/05-transaction-cost` 给出（含赎回费阶梯与批次选择规则的设计）；余下**费率参数与批次规则的取值**待组合与数据确认>`

### 7.3 没有成本模型时 Cost-Benefit Threshold 不可用

> **不得用一个假设的费率填充。** 在成本模型确定前：

```
Cost-Benefit Threshold 判据不可用
    → Drift / Periodic 触发仍可工作（它们不依赖成本）
    → 但"是否值得调"的判断缺失
```

**这是一个真实的能力缺口**，应显式承认而非用默认值掩盖。

---

## 8. 调仓决策的成本收益判据

> **沿用 `02-business-requirements` §28.2。没有这条规则，理论最优组合会产生大量无意义的微小交易。**

```
建议调仓  ⟺  预期改善  >  交易成本  +  最小改善阈值
```

### 8.1 "预期改善"如何度量是一个未决问题 ⚠️

> **上游给出了判据形式，但未定义"预期改善"的计算方式。**

候选方式：

| 方式 | 说明 | 问题 |
|---|---|---|
| 目标函数值的改善 | `f(w_target) − f(w_current)` | 不同目标函数的量纲不同，与成本不可直接比较 |
| 风险降低幅度 | `σ_current − σ_target` | 只覆盖风险维度 |
| 偏离度的减少 | Drift 的减少量 | 与"改善"的经济含义间接 |

> **难点在于成本是货币量，而目标函数值通常不是** —— 两者相比需要一个转换。

> **已定案 · 2026-08-27**：「预期改善」以**年化收益改善**度量，与交易成本**统一为年化百分比**后比较。
>
> **依据 —— 量纲必须统一才能比较**：
>
> ```
> 交易成本是【一次性】的：申购费 0.15% 一次扣完
> 预期改善是【持续性】的：更优的权重带来每年 0.3% 的改善
>
> 直接比较 0.15% 与 0.3% 是错的
>     → 须把一次性成本按【预期持有期】摊薄为年化
>     → 持有一年：0.15% / 1 = 0.15%   → 值得调
>     → 持有一季：0.15% / 0.25 = 0.6% → 不值得调
> ```
>
> **摊薄的分母是「预期持有到下次调仓的时间」**，即调仓周期（`RE-2`）。这使同一笔成本在高频调仓下自动显得更贵 —— 这是正确的，因为高频调仓确实会重复付出这笔成本。
>
> **预期改善的估计误差须纳入考虑**：改善来自 `μ` 的估计，而 `μ` 本身有估计误差。**当预期改善与成本接近时，不应调仓** —— 此时「改善」很可能落在估计噪声范围内。建议设置改善须超过成本的倍数门槛（属 `RE-4` 的取值范围）。

---

## 9. Partial Rebalancing

| 类型 | 说明 | 第一阶段 |
|---|---|---|
| **Full Rebalance** | 调整到完整的 Target | ✅ |
| **Partial Rebalance** | 只调整偏离最大的部分 | **框架预留** |

### 9.1 Partial 的一个隐患

> Partial Rebalance 会使组合**长期处于"部分达成目标"的状态**，而 Target 本身在下次决策时又会变化。

```
T 期：只调整了偏离最大的 3 只
T+1 期：新的 Target 产生，上期未调整的偏离被并入新的 Drift
    → 组合实际上从未真正达到过任何一个 Target
    → 归因时无法判断偏差来自策略还是来自未完成的调仓
```

**因此若启用 Partial**，必须记录"本次未调整的部分及原因"，否则归因链断裂。

> **推荐默认 · 2026-08-27**：启用 **Partial Rebalance**，仅调整偏离最大的前 N 只至目标。业务方可改。
>
> **依据**：全额调仓的成本常高于剩余偏离带来的收益 —— 偏离 0.5% 的持仓，调回目标的收益改善远小于交易成本。
>
> **N 的选择规则**：按偏离幅度降序，累计调整量达到总偏离的 **80%** 时停止。这使调整集中在少数偏离大的持仓上。
>
> **须记录未被调整的偏离** —— 否则连续多期部分调仓会让小偏离累积成大偏离而不被察觉。

---

## 10. Investment Eligibility 对调仓的约束（已定案）

> **沿用 `02-business-requirements` §28.4。**

| 状态 | 买入清单 | 卖出清单 |
|---|---|---|
| `FULLY_ELIGIBLE` | ✅ | ✅ |
| **`HOLD_ONLY`** | **❌ 不得出现** | ✅ 可出现 |
| `LIMITED` | 受限 | ✅ |
| `EXIT_ONLY` | ❌ | ✅ |
| **`NOT_TRADABLE`** | **❌** | **❌ 持仓冻结** |

### 10.1 无法达成目标权重时必须显式报告差异

> **不得静默用其他基金补足。**

```
Target: Fund A 15%，但 Fund A 变为 HOLD_ONLY，当前仅持有 8%
    ❌ 静默把差额 7% 分给 Fund B
    ✅ 报告"Fund A 因不可加仓，实际 8%，与目标差 7%"
       并明确说明剩余 7% 的处置（保留现金 / 显式再分配 / 重新优化）
```

**理由**：静默补足会使实际组合与记录的 Target 不符，破坏归因与可复现性。

### 10.2 `NOT_TRADABLE` 持仓需在风险分析中单独标注

> 它占据权重但不可调整，使实际可优化空间小于 100%（`02-asset-allocation` §7.4）。

---

## 11. Pending Execution 的生命周期

### 11.1 状态流转

```
调仓建议交付
      ↓
Pending Execution
      ↓
  ┌───┴───┬────────┬─────────┐
  ▼       ▼        ▼         ▼
全部成交  部分成交   未成交    超时
  │       │        │         │
  ▼       ▼        ▼         ▼
Actual  Actual   保持      标记异常
更新    部分更新  Pending   并告警
        剩余Pending
```

### 11.2 超时处理

> **Pending 不能无限期挂起** —— 否则会永久阻塞后续调仓（§2.3）。

```
Pending Timeout = TBD
```

超时后应：标记异常、告警、并允许重新发起调仓评估。

> **推荐默认 · 2026-08-27**：Pending Execution 超时 = **5 个交易日**，超时转 `EXPIRED` 并重算（同 `P1-18`）。
>
> **依据**：超过一周未执行的调仓指令，其输入数据（净值、评分、估计）已显著变化，**继续执行等于用过时的决策交易**。重算的成本远低于执行一个失效决策的代价。
>
> **`EXPIRED` 不是失败状态** —— 它表示「该决策的有效期已过」，须在下一决策周期重新产出。区别于 `FAILED`（执行出错）。

### 11.3 部分成交必须能表达

> 这是三态设计的直接目的之一 —— 部分成交时 `Actual` 部分更新，剩余仍在 `Pending`。

---

## 12. Input

| 输入 | 来源 | 用途 |
|---|---|---|
| **`Actual Portfolio`**（Current Weights） | Live Portfolio · 外部执行回报 | Drift 检测的一端 |
| **`Target Portfolio`** | `03-portfolio-optimization` | Drift 检测的另一端 |
| **`Pending Execution`** | Live Portfolio | 判断是否重复触发（§2.3） |
| **`Rebalancing Policy`** + version | 本文档 | 触发条件与阈值 |
| **`Investment Eligibility`** | `03-data` | 买卖清单的可行性（§10） |
| **`Fund Fee`** | `03-data` | 交易成本（成本模型可用时） |
| 约束校验结果 | `05-constraints` | `Constraint Breach` 触发判定 |
| 风险预算校验结果 | `04-risk-budgeting` | 风险类触发的输入 |
| 冻结持仓清单 | Live Portfolio | 排除出换手与触发判定 |

> **重算所需的上游输入**（Universe、Score、`μ`、`Σ`）**由触发类型决定**（§3），不在本表逐一列出。

---

## 13. Rebalancing Output

| 字段 | 说明 |
|---|---|
| `portfolio_id` + `decision_at` | 标识 |
| **`trigger_type`** | `Periodic` / `Drift` / `Eligibility Event` / `Constraint Breach` |
| **`trigger_reason`** | 具体触发原因（§14） |
| **`recompute_scope`** | 本次重算范围（§3） |
| **`current_weights`**（`Actual`） | 当前实际权重 |
| **`target_weights`** | 目标权重 |
| **`drift`** | 逐基金与逐类别的 Signed Drift |
| **`proposed_trades`** | 买卖清单（含方向与数量） |
| **`turnover`** | 预计换手率（单边口径） |
| **`estimated_cost`** | 预计交易成本（成本模型可用时） |
| **`cost_benefit_result`** | 成本收益判据的计算结果 |
| **`constraint_status`** | 调仓后的约束校验结果 |
| **`unachievable_targets`** | 因可投资性无法达成的目标及差额（§10.1） |
| `rebalance_rule_version` | 策略版本 |

---

## 14. Explainability

> **必须能回答：Why did the system rebalance?**

```
触发类型：Drift
触发原因：Fund A 实际权重 X%，目标 X%，偏离 X% > 阈值 X%
重算范围：⑤ → ⑥ → ⑦（Universe 与 Score 不变）
成本收益：预期改善 X > 交易成本 X × 倍数阈值 X  →  建议调仓
换手率：  X%（上限 X%）
约束校验：全部 PASS，其中单基金上限（Fund C）为紧约束
未达成：  Fund D 因 HOLD_ONLY 无法加仓，差额 X%
```

### 14.1 同样必须能回答"为什么不调仓"

> **未触发调仓的时点同样要留痕。**

```
Drift 检测：最大偏离 X% < 阈值 X%  →  不触发
或
Drift 超阈值但成本收益判据未通过：预期改善 X < 成本 X × 倍数 X  →  不调仓
或
存在未完成的 Pending Execution  →  本期不重复发起
```

**理由**：只记录"调了什么"而不记录"为什么没调"，会使"系统是否正常工作"无法验证 —— 长期不调仓既可能是正常（组合稳定），也可能是检测逻辑失效。

---

## 15. Rebalancing Policy

| 字段 | 说明 |
|---|---|
| `policy_id` / `version` | 标识与版本（即 `Rebalance Rule Version`） |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`triggers`** | 启用的触发类型及各自条件 |
| **`recompute_scope_map`** | 触发类型 → 重算范围（不得运行时调整） |
| **`frequency`** | Periodic 的周期 |
| **`thresholds`** | 四个阈值（§5.1） |
| **`drift_definition`** | 基金层 / 类别层阈值 |
| **`turnover_convention`** | 单边或双边口径（§6.2） |
| **`transaction_cost_model`** | 成本模型（当前 `TBD`） |
| **`multi_trigger_rule`** | 多触发并发时的合并规则（§3.3） |
| **`pending_timeout`** | Pending 超时时长 |
| `partial_rebalance_enabled` | 第一阶段 `false` |

### 15.1 `Rebalance Rule Version` 是 Strategy Version 的第 8 项

```
第 8 项 = Rebalance Rule Version
    = 触发条件 + 重算范围 + 四个调仓阈值
```

（`02-architecture/01-system-architecture` §8.2）本域**不新增版本类型**。

---

## 16. Portfolio Versioning 与快照

### 16.1 调仓不覆盖历史组合

```
Portfolio V1 → V2 → V3
每次调仓产生新版本，历史版本保持不变
```

### 16.2 Portfolio Snapshot

| 字段 | 说明 |
|---|---|
| `portfolio_id` + `version` + `as_of_date` | 标识 |
| **成分与权重**（三态各自） | `Target` / `Pending` / `Actual` |
| **Asset Allocation** | 类别层实际配比 |
| **Risk Metrics** | ⑦-R 事后风险 |
| **Constraint Status** | 约束校验结果 |
| **Risk Budget vs Contribution** | 预算与实际（上游 ⑦-R 要求同时留存） |
| **全部 Policy 版本** | 六个 Policy 的版本引用 |

### 16.3 完整快照是审计的唯一依据

> **上游 §4.2 ⑨ 关键约束**：每一次实盘决策必须留存完整快照 —— Universe、Score、Return Estimate、Risk Metrics、Correlation Matrix、Covariance Matrix、Constraint Set、Risk Budget、Optimization Objective、Optimization Result、Target Weight。

**快照必须足以完整重建该次历史决策。**

### 16.4 快照必须在单一事务内完整写入

> 沿用上游 §8.4 的产品级约束与 `02-architecture/01-system-architecture` §10 的一致性边界 —— 快照具备**全有或全无**的语义。

---

## 17. Point-in-Time 与可复现

### 17.1 要素

```
Fund Universe（该时点快照）
+ μ、Σ（Return Estimate Version、Risk Model Version）
+ Portfolio Rule Version（Construction + Allocation + Optimization + Risk Budget + Constraint）
+ Rebalance Rule Version
+ Current Weights（Actual，该时点）
+ Code Version
+ decision_at
        ↓
    相同的调仓建议
```

### 17.2 `Current Weights` 使再平衡具有路径依赖 ⚠️

> **这是再平衡与前序环节的一个本质差异。**

```
Factor / Score / Universe / Optimization
    → 给定输入即可重算，与历史路径无关

Rebalancing
    → 依赖 Current Weights
    → Current Weights 来自上一次调仓的执行结果
    → 因此再平衡的复现需要【完整的历史执行链】
```

**后果**：若某一期的 `Actual` 未正确记录，其后**全部**期次的再平衡都无法复现。这使 §15 的快照完整性成为硬性要求，而非"最好有"。

---

## 18. Edge Cases

| 情形 | 处理 |
|---|---|
| 存在未完成的 `Pending Execution` | **不重复发起调仓**，除非超时（§2.3、§11.2） |
| 回报延迟，`Actual` 未确认 | 标记待确认；**不得以 `Target` 冒充**（§2.2） |
| 部分成交 | `Actual` 部分更新，剩余仍在 `Pending` |
| 多个触发同时发生 | 取重算范围最深者（§3.3） |
| 重算后 Target 与当前几乎相同 | 各笔调整低于 Minimum Trade Threshold → **不调仓**，但须留痕（§13.1） |
| 换手率超过 Turnover Threshold | 需人工确认，**不自动执行** |
| 成本模型不可用 | Cost-Benefit 判据不可用；须显式声明而非用默认值（§7.3） |
| 目标基金 `HOLD_ONLY` 无法加仓 | **显式报告差额**，不得静默补足（§10.1） |
| 持仓基金 `NOT_TRADABLE` | 冻结；不计入换手；在风险分析中单独标注 |
| 重算后 Universe 为空 | 阻断（`05-fund-evaluation/05` §19） |
| 优化返回 `INFEASIBLE` | 按 `03` §8.3 闭环；**不得沿用上期权重作为静默降级** |
| 冻结持仓导致的 Constraint Breach | **不进入触发判定**（`05-constraints` §11.1），避免无效重试循环 |

---

## 19. Auditability

> 本域审计总纲见 `01-portfolio-construction` §20。本节只列再平衡特有的要点。

### 19.1 执行链的完整性是硬性要求

> **沿用 §17.2 的路径依赖结论。**

```
再平衡依赖 Current Weights（Actual）
Actual 来自上一次调仓的执行回报
    → 某一期 Actual 未正确记录
    → 其后【全部】期次的再平衡都无法复现
```

**因此执行回报的记录不是"运维日志"，而是决策链的一环。**

### 19.2 三态各自的历史都要保留

| 状态 | 为什么要留历史 |
|---|---|
| `Target` | 归因的基准 |
| **`Pending`** | 解释"为什么这期没调" —— 存在未完成的 Pending（§2.3） |
| `Actual` | 全部事后计算的基础 |

> 只保留 `Actual` 会使"某期为何未调仓"无法解释。

### 19.3 未触发调仓的时点同样要留痕

> 见 §14.1。这是验证检测逻辑是否失效的唯一途径。

### 19.4 触发类型与重算范围必须成对记录

> 只记"发生了再平衡"不足以复现 —— `Drift` 与 `Periodic` 的重算范围不同，产出的 Universe 与 Score 可能不同。

---

## 20. Summary

再平衡是一次**策略重评估**，不是简单的比例复原；重算范围由触发类型决定，**四类触发分级**是为了避免权重漂移引发不必要的基金池变动。

三条来自三态的直接后果：

- **Drift 检测必须用 `Actual` vs `Target`** —— 用 `Target` 冒充 `Actual` 会得出"刚下单就零偏离"
- **`Pending Execution` 期间不应重复触发调仓** —— 否则 Fill 未回时会反复产出同一份建议，重复下单
- **Pending 不能无限期挂起** —— 需要超时机制，否则永久阻塞后续调仓

三处基金组合特有的复杂性：

- **赎回费的持有期阶梯使调仓成本成为路径函数** —— 同样卖出 5%，持有 6 天与 60 天成本可能相差数倍；成本计算需要持仓的买入批次，而非仅当前权重
- **没有成本模型时 Cost-Benefit 判据不可用** —— 应显式承认这一能力缺口，不得用假设费率填充
- **"预期改善"的度量方式尚未定义** —— 成本是货币量而目标函数值通常不是，两者相比需要一个未定的转换

两处口径与路径问题：

- **换手率的 0.5 系数必须显式声明** —— 单边与双边口径相差一倍，直接改变约束的含义
- **再平衡具有路径依赖** —— 依赖 `Current Weights`，因此复现需要完整的历史执行链；某一期 `Actual` 记录缺失，其后全部期次都无法复现

---

## 21. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **再平衡是策略重评估，重算范围按触发类型分级** | 上游 ⑩-T；避免非预期换手 |
| D-2 | **多触发并发时取最深重算范围** | 分别执行产生两次换手且路径依赖 |
| D-3 | 触发判定用 Absolute Drift，展示与买卖方向用 Signed | 只保留其一都会丢失必要信息 |
| D-4 | Drift 同时在基金层与类别层判定 | 两者可能不一致 |
| D-5 | **`Pending` 期间不重复发起调仓** | 否则 Fill 未回时重复下单 |
| D-6 | **Pending 必须有超时机制** | 否则永久阻塞后续调仓 |
| D-7 | **换手率采用单边口径（带 0.5），且必须显式声明** | 两种口径相差一倍 |
| D-8 | 冻结持仓的权重差异不计入换手率 | 无法交易，计入会虚增并可能致不可行 |
| D-9 | **Minimum Trade Threshold 在优化后过滤，过滤后必须重新校验约束** | 它是非凸约束；过滤解可能违约 |
| D-10 | **没有成本模型时显式声明 Cost-Benefit 不可用** | 不得用假设费率掩盖能力缺口 |
| D-11 | **无法达成目标权重时显式报告差额，不得静默补足** | 静默补足破坏归因与可复现性 |
| D-12 | **未触发调仓的时点同样留痕** | 否则无法验证检测逻辑是否失效 |
| D-13 | 第一阶段只实现 Full Rebalance | Partial 会使组合从未真正达到任何 Target，归因链断裂 |
| D-14 | 快照必须在单一事务内完整写入 | 上游 §8.4 产品级约束 |

---

## 22. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 触发条件与重算范围必须**事先定义、可回测**，不得运行时调整 | 上游 §4.2 ⑩、`02-business-requirements` §28.5 |
| C-2 | Drift 检测必须基于 `Actual` vs `Target` | 上游 ⑨-S |
| C-3 | **不得以 `Target` 冒充 `Actual`** | 同上 |
| C-4 | `HOLD_ONLY` 不得出现在买入清单；`NOT_TRADABLE` 持仓冻结 | `02-business-requirements` §28.4 |
| C-5 | 无法达成目标权重必须显式报告差异 | 同上 |
| C-6 | 每次实盘决策必须留存**完整快照** | 上游 §4.2 ⑨ |
| C-7 | 快照必须可**完整重建**该次历史决策 | 同上 |
| C-8 | **本域不执行交易** | 上游 §6 Out of Scope |
| C-9 | 优化不可行时**不得沿用上期权重作为静默降级** | `02-business-requirements` §20.5 |
| C-10 | `Rebalance Rule Version` 属 Strategy Version 第 8 项，不新增版本类型 | `02-architecture/01-system-architecture` §8.2 |

---

## 23. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~RE-1~~ | ~~多触发并发时的合并规则~~ —— **已定案**：多触发并发时采用【取最深】合并 | — | ✅ 2026-08-27 |
| ~~RE-2~~ | ~~Periodic 触发的调仓频率~~ —— **推荐默认**：Periodic 触发频率 = 季度 | — | ✅ 2026-08-27 |
| ~~RE-3~~ | ~~基金层与类别层 Drift 阈值~~ —— **已定案**：基金层与类别层 Drift 阈值【独立配置】 | — | ✅ 2026-08-27 |
| RE-4 | **四个调仓阈值的取值**（= 上游 `TBD-P1-19`） | 再平衡无法投产 | 组合 + 投研 |
| RE-5 | 交易成本**参数取值** —— 模型结构已由 `08-backtest/05-transaction-cost` 定义 | Cost-Benefit 判据不可用 | 组合 + 数据 |
| ~~RE-6~~ | ~~"预期改善"的度量方式及与成本的量纲统一~~ —— **已定案**：「预期改善」以【年化收益改善】度量，与交易成本统一为年化百分比后比较 | — | ✅ 2026-08-27 |
| ~~RE-7~~ | ~~是否启用 Partial Rebalance 及选择规则~~ —— **推荐默认**：启用 Partial Rebalance，仅调整偏离最大的前 N 只至目标 | — | ✅ 2026-08-27 |
| ~~RE-8~~ | ~~Pending Execution 的超时时长与处置~~ —— **推荐默认**：Pending Execution 超时 = 5 个交易日，超时转 `EXPIRED` 并重算 | — | ✅ 2026-08-27 |

---

## 24. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ⑨、⑨-S、⑩、⑩-T、§8.4）、`02-business-requirements.md` v2.3（§18.2、§28） |
| **本域** | `01-portfolio-construction`（模式区分）、`02-asset-allocation`（Drift 与 Range 的区别）、`03-portfolio-optimization`（Target 生成、不可行闭环）、`04-risk-budgeting`（Breach 不自动触发）、`05-constraints`（调仓后校验、冻结持仓 Breach） |
| **数据** | `03-data/02-data-domain-model`（`Fund Fee`、`Investment Eligibility`） |
| **架构** | `02-architecture/01-system-architecture.md` v2.2（§10 一致性边界、§12 Portfolio State Model） |
| **下游** | `08-backtest`（回测中的再平衡）、`12-operations`（调仓监控） |

---

## 25. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（6 项）**。`RE-1` 多触发**取最深**（各触发的重算范围嵌套），须记录全部触发原因；`RE-3` 基金层与类别层 Drift 阈值**独立配置**（两者容忍度本就不同）；`RE-6` 「预期改善」以年化收益度量，**一次性成本须按预期持有期摊薄为年化**后比较，且改善与成本接近时不应调仓（可能落在估计噪声内）；`RE-2`/`RE-7`/`RE-8` 推荐默认（季度频率、启用 Partial Rebalance 覆盖 80% 偏离、超时 5 个交易日）。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.1 | 2026-08-26 | 交易成本模型获 `08-backtest/05-transaction-cost` 回应（**回测与实盘共用**）：含赎回费持有期阶梯、批次选择规则、Gross/Net 分离与 No Double Counting 检查。`TBD-RE-5` 由"模型待定"收窄为"参数取值待定" | `08-backtest/05-transaction-cost.md` v1.0 |
| v1.0 | 2026-08-26 | 初始版本。沿用上游 ⑩-T 四类触发与分级重算范围；**§3.3 补充上游未定义的多触发并发规则**（取最深，避免两次换手与路径依赖）；**§2.3 `Pending Execution` 期间不重复触发调仓**与 §11.2 超时机制（否则永久阻塞）；§4.2 Absolute 用于触发、Signed 用于方向；**§4.4 Drift 的四个来源**（后三项使 Drift 跳变）；**§6.2 换手率 0.5 系数的口径必须显式声明**（两种口径相差一倍）；**§7.2 赎回费的持有期阶梯使成本成为路径函数**——需要持仓买入批次而非仅当前权重；**§7.3 没有成本模型时 Cost-Benefit 判据不可用**，显式承认能力缺口；**§8.1 指出"预期改善"的度量方式上游未定义**且与成本量纲不统一；§10.1 无法达成目标时显式报告差额；**§14.1 未触发调仓的时点同样留痕**；**§17.2 再平衡的路径依赖**——某期 `Actual` 缺失则其后全部期次不可复现；**§19.2 三态各自的历史都要保留**（只留 `Actual` 会使"某期为何未调仓"无法解释） | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`03-portfolio-optimization.md` v1.0 |