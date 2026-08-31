# 组合优化 · Portfolio Optimization

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑦ Portfolio Optimization** + **⑦-R**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§19.2、§20.5
> 本域上游：docs/06-portfolio/01-portfolio-construction.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **在给定的目标函数与约束集下，如何求解出目标权重？**

### 1.2 Optimization 只求解，不定义 ⚠️

> **上游 §5.3 的核心规则：**

```
Construction 定义问题  →  Optimization 求解问题
```

| Optimization **负责** | Optimization **不负责** |
|---|---|
| 求解权重向量 `w` | 定义目标函数与约束集 |
| 返回求解状态与诊断 | 修改约束以求得可行解 |
| 计算 ⑦-R 事后组合风险 | 基金筛选、评分、分类 |
| 声明求解路径 | 数据采集与估计 |

### 1.3 求解器不得自行放松约束 ⚠️

> **当优化问题不可行时，必须返回失败并上报，由 Construction 层决定如何修改约束。**

```
❌ 优化器发现无解 → 自行放松单基金上限 → 返回一个"差不多的解"
   → 等于求解层悄悄改变了投资约束
   → 实际组合违反本应遵守的合规限制，且无人知晓
```

（上游 §5.3、§4.2 ⑦）

---

## 2. Input

| 输入 | 来源 | 必需 |
|---|---|---|
| **Candidate Funds** | `01-portfolio-construction` 的成分候选集 | ✅ |
| **Objective Function** | `01` §8 定义的目标函数形式 | 路径二必需 |
| **Constraint Set** | `05-constraints` | ✅ |
| **Risk Budget** | `04-risk-budgeting` | ✅ |
| **Covariance Matrix `Σ`** | `07-return-risk` | 路径二必需 |
| **Return Estimate `μ`** | `07-return-risk` | Max Sharpe / Mean-Variance 必需 |
| Correlation Matrix | `07-return-risk` | 诊断与展示 |
| `Portfolio Benchmark` | `01` §7.2 | Tracking Error 目标必需 |
| `Risk-free Rate` | `03-data`，经 Threshold Resolver | Sharpe 类目标必需 |
| Current Weights | Live Portfolio（`06`） | 换手率约束必需 |
| Asset Class Constraints | `02-asset-allocation` | ✅ |

---

## 3. 五个必须区分的"收益"概念 ⚠️

> **这五个概念在优化环节最容易被混成一个字段。**

| 概念 | 含义 | 归属 | 在优化中的角色 |
|---|---|---|---|
| **Historical Return** | 历史已实现收益 | `04-factor`（`F-RET-001` 等） | **不得**直接作为 `μ` |
| **Expected Return（`μ`）** | 对未来持有期的收益估计 | **`07-return-risk`** | Mean-Variance / Max Sharpe 的输入 |
| **Portfolio Target Return** | 组合的收益目标 | 本域（若采用） | 可作为约束 `μ'w ≥ target` |
| **MAR** | 最低可接受收益（**评价标准**） | `05-fund-evaluation` | **不得**用作组合收益目标 |
| **Risk-free Rate（`R_f`）** | 市场无风险利率（**市场数据**） | `03-data` | Sharpe 的基准 |

### 3.1 Historical Return ≠ Expected Return

> **即使 `07-return-risk` 采用历史均值作为估计方法，两者仍不是同一个字段。**

```
Historical Return  = 事实，属 Factor，带 Factor Version
Expected Return    = 估计，属 07-return-risk，带 Return Estimate Version
                     且必须声明 Estimation Window / Horizon / Return Basis 三口径
```

**混用的后果**：把 Factor 直接喂给优化器，会绕过 `Return Estimate Version` 的版本治理 —— 估计方法的变更不会被记录，历史决策无法解释当时用的是什么估计。

> 若 `07-return-risk` 尚未提供 `μ`：**依赖 `μ` 的目标（Max Sharpe、Mean-Variance）不可投产**，而不是"用历史收益代替"。Min Volatility 与 Risk Parity 不需要 `μ`，可先行投产。

### 3.2 MAR 不得当作 Portfolio Return Target ⚠️

> **两者性质完全不同**（上游 §5.5）。

| | **MAR** | **Portfolio Target Return** |
|---|---|---|
| 作用对象 | **单只基金**的下行风险度量阈值 | **整个组合**的收益目标 |
| 归属 | `05-fund-evaluation` 的 Evaluation Policy | 本域的 Optimization Policy |
| 用途 | Sortino / Downside Volatility 的计算参数 | 优化的收益约束 |
| 粒度 | 按 `fund_category` × `currency` | 按组合 |

```
❌ 直接复用 MAR 作为组合最低收益要求
   → MAR 是"评价一只基金时认为多少算可接受"
   → 与"这个组合要达到多少收益"是两个问题
```

**若优化需要最低收益约束**，必须定义为独立的 **`Minimum Portfolio Return`**，除非业务明确规定二者相同。

`<TBD-PO-1: 是否需要 Minimum Portfolio Return 约束及其取值，待投研确认>`

---

## 4. Optimization Objective

### 4.1 候选目标与数学性质（已定案）

> **沿用 `02-architecture/06-technology-stack` §5.2.1。此前笼统称"第一阶段目标均为凸问题"的表述不准确。**

| 目标 | 数学性质 | 求解路径 | 需要 `μ` | 第一阶段 |
|---|---|---|---|---|
| **Minimum Volatility** | **凸 QP** | 直接求解 `min w'Σw` | ❌ | ✅ |
| **Maximum Sharpe** | **拟凸**（分式规划） | **需 Charnes-Cooper 变换** —— 见 §4.3 | ✅ | ✅ |
| **Mean-Variance** | **凸 QP** | `max μ'w − λ/2·w'Σw` | ✅ | ✅ |
| **Risk Parity** | 凸（对数障碍形式） | 转为凸问题求解 | ❌ | 后续 |
| **Minimum CVaR** | **凸 LP** | Rockafellar-Uryasev 表达 | ❌ | 后续 |
| **Minimum Tracking Error** | **凸 QP** | `min (w−w_b)'Σ(w−w_b)` | ❌ | 后续 |

```
Optimization Objective = TBD
```

> **本域不自行选择最终生产目标。** `02-business-requirements` §19.4 已给出四个候选策略（Baseline-EW / Baseline-SW / MinVol / MaxSharpe），上线顺序待 `TBD-P1-10` 确认。

### 4.2 Minimum CVaR 是凸问题，不是非凸

> **需要澄清一处常见误解**：Mean-CVaR 经 Rockafellar-Uryasev 变换后可表达为**凸线性规划**，不属于非凸情形。真正非凸的是基数约束与最小持仓量（§4.4）。

### 4.3 Maximum Sharpe 的求解路径必须显式声明 ⚠️

> **这是架构层明确交由本域定义的一项**（`06-technology-stack` §5.2.1）。

**问题**：Max Sharpe 是分式规划

```
max  (μ'w − R_f) / sqrt(w'Σw)
```

它**不是凸问题**，但在约束集**可齐次化**时，可通过 Charnes-Cooper 变换（令 `y = κw`，`κ > 0`）转为凸 QP。

**变换的前提**：

| 前提 | 说明 |
|---|---|
| 约束必须可齐次化 | 形如 `Aw ≤ b` 的约束需能改写为 `Ay ≤ bκ` |
| **换手率约束破坏齐次性** | `Σ\|w − w_current\| ≤ T` 中的 `w_current` 是常量，不随 `κ` 缩放 |

> **因此：当策略同时启用 Maximum Sharpe 与换手率约束时，Charnes-Cooper 路径不可用。**

**本域定义的替代路径**：

| 路径 | 做法 | 权衡 |
|---|---|---|
| **A：风险厌恶参数扫描（推荐）** | 对一组 `λ` 分别求解 `max μ'w − λ/2·w'Σw`（凸 QP），在有效前沿上取 Sharpe 最优点 | 需多次求解；`λ` 网格是**结果的一部分**，必须版本化 |
| B：直接拟凸求解 | 用二分法配合可行性判定 | 实现复杂，收敛判据需额外定义 |
| C：放弃换手率约束 | 在优化后单独校验换手率 | 可能得到超出换手上限的解，须回到 Construction 层 |

**强制要求**：

```
求解路径必须随 Portfolio Rule Version 显式声明
    → 不得由实现隐式选择
    → 否则相同配置在不同实现下会得到不同结果
```

**路径 A 的 `λ` 网格必须版本化**：不同的网格密度会给出不同的"Sharpe 最优点"，它是配置而非实现细节。

> **已定案 · 2026-08-27**：采用 **λ 网格扫描 + 择优**，λ 取 **21 点对数网格**（`10^-2` 到 `10^2`，每十倍 5 点）。
>
> **依据 —— Charnes-Cooper 变换在换手率约束下失效**（§4.3 已论证）。可选路径只有两条：
>
> | 路径 | 评价 |
> |---|---|
> | **λ 网格扫描**（已采纳） | 对每个 λ 解一个**凸 QP**（Min Variance with Return Target），在解集中取 Sharpe 最大者。**每个子问题都保持凸性**，结果可复现 |
> | 直接非凸求解 | 失去凸性保证，可能收敛到局部最优，且结果依赖初值 —— 与可复现性要求冲突 |
>
> **21 点对数网格的理由**：λ 的作用是量级性的（风险厌恶从 0.01 到 100 覆盖了实践中的全部合理范围），线性网格会在小 λ 区间过密、大 λ 区间过疏。
>
> **网格扫描是近似，须声明**：真实最优 Sharpe 可能落在两个网格点之间。**扫描结果的 Sharpe 是下界** —— 报告中不得表述为「最优 Sharpe」，而应表述为「网格扫描下的最佳解」。
>
> **21 个子问题可并行求解**，不构成性能瓶颈。

### 4.4 真正的非凸情形

> 以下约束会使问题变为**混合整数**（非凸），开源求解器能力有限：

| 约束 | 说明 | 第一阶段 |
|---|---|---|
| **基数约束**（"最多持有 N 只"） | 混合整数 | **通过 Universe 层 Top-N 规避**（`01` §12.2） |
| **最小持仓量**（`w_i = 0` 或 `w_i ≥ l`） | 半连续变量，本身即非凸 | 见 §4.5 |
| **最小交易量** | 同上 | 见 `06-rebalancing` |

### 4.5 最小持仓量与"最小权重"不是一回事 ⚠️

> **这处区分极易出错。**

```
约束 A：w_i ≥ 0.02  对全部候选基金
    → 凸约束
    → 但强制每只候选基金都必须持有至少 2%
    → 候选集有 60 只时，Σ min = 120% > 100%，必然不可行

约束 B：w_i = 0 或 w_i ≥ 0.02
    → "要么不持有，要么至少 2%"
    → 半连续变量，非凸（混合整数）
    → 这才是业务真正想要的"避免碎片持仓"
```

**业务意图几乎总是 B，但 B 是非凸的。** 第一阶段的处理：

| 方式 | 说明 |
|---|---|
| **优化后截断（推荐）** | 求解后把低于阈值的权重置零，重新归一化，**再校验约束是否仍满足** |
| 引入混合整数求解 | 需评估求解器能力，`06-technology-stack` §5.2.2 已标注开源 MIQP 能力有限 |

> **截断法的代价必须承认**：截断后的解不再是最优解，且**可能违反原约束**（如截断后某类别权重跌破下限）。因此截断后必须重新校验，不通过则返回 `INFEASIBLE`，而不是接受一个违约的解。

> **已定案 · 2026-08-27**：第一阶段**不实现最小持仓量约束**；改用「**优化后截断 + 重新归一**」，并**记录截断量**。
>
> **依据 —— 最小持仓量是基数约束，使问题非凸**：
>
> ```
> 约束形式：w_i = 0  或  w_i ≥ w_min
>     → 这是一个【或】关系，不是凸集
>     → 严格求解需要混合整数规划（MIQP）
>     → 求解时间随资产数指数增长，且无法保证在决策时间窗内完成
> ```
>
> **截断法的做法与代价**：
>
> ```
> ① 正常求解凸 QP，得到 w*
> ② 将 w_i < w_min 的置零
> ③ 剩余权重重新归一化
> ④ 记录 truncated_weight_total（被截断的权重总和）
> ```
>
> 截断后的解**不再是最优解**，且归一化会放大剩余持仓的权重。**但在小权重场景下偏差可控** —— 被截断的都是原本权重就很小的持仓，其对组合特征的影响有限。
>
> **`truncated_weight_total` 必须落库并在超过阈值（如 5%）时告警** —— 截断量大说明优化产出了大量微小持仓，那通常意味着 Universe 过大或约束过松，是需要处理的信号而非可忽略的舍入。
>
> **区分「最小持仓量」与「最小权重」**（§4.5，不变）：前者是本条讨论的基数约束，后者是简单的下界约束 `w_i ≥ w_min`（对全部 i，凸），后者可实现。

---

## 5. Risk Model

> **本域不重新定义风险数据。** 风险模型的输入来自：

| 输入 | 来源 |
|---|---|
| Volatility | `04-factor`（`F-RISK-001`） |
| Downside Volatility | `04-factor`（`F-RISK-002`） |
| **Covariance Matrix `Σ`** | **`07-return-risk`** |
| **Correlation Matrix** | **`07-return-risk`** |
| VaR / CVaR | `04-factor`（`F-RISK-004/005`） |

### 5.1 `Σ` 必须来自 `07-return-risk`，不得在本域估计

> **协方差估计涉及估计窗口、收缩方法、频率对齐等一整套方法论**，属 `Risk Model Version`（Strategy Version 第 6 项）。在本域重新估计会绕过版本治理。

### 5.2 `Σ` 的质量直接决定优化结果的可信度

> **这是优化环节最脆弱的一环。**

| 问题 | 后果 |
|---|---|
| **候选基金数接近或超过观测数** | `Σ` 病态或不可逆，Min Vol 解极端集中 |
| 估计窗口内有基金成立不足 | 该基金的协方差行列不可得 |
| 基金间交易日历错位 | 可配对观测不足 |

> **`Σ` 的可用性校验属 `07-return-risk`**（已落实于 `07-return-risk/04-correlation-covariance` §7.1 与 `06-estimation-validation` §7），但本域必须在求解前检查其**维度完整性** —— 候选集中任一基金的协方差不可得时，该基金无法参与路径二的优化。

**处理**：不可得的基金**移出候选集并记录原因**，不得以 0 填充协方差（那等于宣称该基金与所有基金无关，会使优化器极度偏好它）。

---

## 6. 数学表达

### 6.1 基础量

```
组合收益     R_p = Σ w_i × R_i  =  μ'w
组合方差     σ_p² = w'Σw
组合波动率   σ_p = sqrt(w'Σw)
```

### 6.2 通用问题形式

```
        optimize    f(w)                      ← 目标函数，由 Construction 定义
        subject to  Σ w_i = 1                 ← 全额投资（或含现金的变体）
                    w_i ≥ 0                   ← 不做空（01 §9.3）
                    l_i ≤ w_i ≤ u_i           ← 单基金上下限
                    L_k ≤ Σ_{i∈k} w_i ≤ U_k   ← 类别上下限（02）
                    g(w) ≤ b                  ← 风险预算与其他约束（04、05）
```

> **具体目标函数与约束取值待 Construction 层定义**，本域只描述形式。

---

## 7. Optimization Output

| 字段 | 说明 |
|---|---|
| `portfolio_id` + `decision_at` | 标识 |
| **`optimization_status`** | 见 §8 |
| **`target_weights`** | 逐基金的 `w_i`（成功时） |
| **`objective_value`** | 目标函数值 |
| **`binding_constraints`** | **哪些约束是紧的**（§10.2） |
| **`shadow_prices` / 敏感性** | 约束的边际影响 |
| **⑦-R 事后组合风险** | 见 §9 |
| `solver_status` | 收敛 / 迭代次数 / 数值诊断 |
| **`solve_path`** | 所用求解路径（§4.3） |
| `excluded_candidates` | 被移出候选集的基金及原因（§5.2） |
| `portfolio_rule_version` | 策略版本 |
| `return_estimate_version` / `risk_model_version` | 输入版本 |
| **`code_version`** | 求解器与数值库版本（可复现第四要素） |

---

## 8. Optimization Status

| 状态 | 含义 | 是否产出权重 |
|---|---|---|
| **`OPTIMAL`** | 求解成功且收敛 | ✅ |
| **`INFEASIBLE`** | **不存在满足全部约束的解** | ❌ |
| **`UNBOUNDED`** | 目标无界（通常是约束配置错误） | ❌ |
| **`NOT_CONVERGED`** | 达到迭代上限仍未收敛 | ❌ |
| **`NUMERICAL_ERROR`** | 数值问题（如 `Σ` 病态） | ❌ |

### 8.1 系统不得返回违反约束的结果并标记为成功

> **这是硬性要求。** 任何非 `OPTIMAL` 状态都不得产出可执行的目标权重。

### 8.2 求解失败必须阻断，严禁静默降级 ⚠️

> **沿用上游 §4.2 ⑦ 关键约束：**

```
❌ 严禁静默降级为等权
❌ 严禁静默沿用上期权重
❌ 严禁静默放松约束
❌ 严禁静默修改风险预算
```

### 8.3 不可行时的闭环流程（已定案）

> **"不许自动放松"之后必须有闭环**（`02-business-requirements` §20.5）。

```
Optimization INFEASIBLE / NOT_CONVERGED
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
| 2 | 放松约束是 **Construction 层的显式决策**，必须**升版本并留痕** |
| 3 | "沿用上期权重"是一种**主动选择**，必须显式声明并记录，**不得作为静默降级** |
| 4 | 不可行事件本身必须记录到决策快照，供事后分析约束是否设置过紧 |

### 8.4 `INFEASIBLE` 与 `NOT_CONVERGED` 的区别

| | `INFEASIBLE` | `NOT_CONVERGED` |
|---|---|---|
| 含义 | **约束互相冲突，数学上无解** | 有解但求解器没找到 |
| 排查方向 | 回到 Construction 层查约束配置 | 检查数值条件、迭代上限、`Σ` 条件数 |
| 是否可能通过重试解决 | **否** | 可能（调整求解参数） |

> **混淆两者会导致排查方向完全错误** —— 把约束冲突当作数值问题反复重试，或把数值问题当作约束问题去放松约束（放松了也解不出来）。

### 8.5 Constraint Relaxation

```
Constraint Relaxation = OFF（第一阶段）
```

> **第一阶段不实现自动约束放松。** 若未来支持，必须明确：可放松哪些约束、最大放松幅度、优先级、审批流程、审计留痕。

> **已定案 · 2026-08-27**：第一阶段**不引入 Constraint Relaxation Policy**；不可行时返回 **`INFEASIBLE` 并给出冲突约束集**。
>
> **依据 —— 自动松弛会让「约束被违反」变成静默事件**：
>
> ```
> 约束的存在正是为了【不被违反】
>
> 自动松弛
>     → 系统在无人知晓的情况下越过了某条约束
>     → 且松弛顺序（先松哪条）本身是一个未经论证的风险偏好表达
>     → 合规约束若被自动松弛，后果不只是技术问题
> ```
>
> **`INFEASIBLE` 是正确的输出，不是失败** —— 它准确表达了「在当前约束下无解」这一事实，而这个事实需要人来处理（放松哪条约束是决策，不是计算）。
>
> **必须返回冲突约束集**，否则 `INFEASIBLE` 无法被处理。实现方式：求解不可行时用 IIS（Irreducible Infeasible Subsystem）或逐条松弛测试定位最小冲突集。
>
> **与 `CS-3` 的约束优先级配合**：优先级序列（合规 > 风控 > 策略 > 成本）在本阶段用于**人工决策的参考**，不用于自动松弛。

---

## 9. ⑦-R：Post-Optimization Portfolio Risk

> **权重 `w` 求出后，本环节负责计算依赖 `w` 的组合层风险量**（上游 §4.2 ⑦-R）。

### 9.1 指标

| 指标 | 公式 |
|---|---|
| **Portfolio Volatility** | `σ_p = sqrt(w'Σw)` |
| **Marginal Risk Contribution** | `MRC_i = ∂σ_p / ∂w_i` |
| **Total Risk Contribution** | `TRC_i = w_i × MRC_i` |
| **Risk Contribution %** | `RCP_i = TRC_i / σ_p` |
| **Concentration** | 权重 HHI、前 N 大权重占比 |
| **Factor Exposure** | 组合在各因子上的加权暴露 |

> `Σ TRC_i = σ_p`（欧拉分解），因此 `Σ RCP_i = 1`。这是校验 `TRC` 计算正确性的**恒等式**。

### 9.2 Risk Budget（事前）与 Risk Contribution（事后）必须区分 ⚠️

> **这是一组最容易混淆的概念**（上游 §4.2 ⑦-R）。

| | **Risk Budget（事前）** | **Risk Contribution（事后）** |
|---|---|---|
| 归属 Stage | **⑥ Construction** | **⑦ Optimization** |
| 归属文档 | `04-risk-budgeting` | **本文档** |
| 性质 | **目标 / 约束** —— 希望各部分承担多少风险 | **结果** —— 实际承担了多少风险 |
| 是否依赖 `w` | **否** | **是** |
| 用途 | 作为约束进入优化问题 | 检验优化结果是否达成风险预算 |

> **两者必须同时留存于决策快照**，事后才能回答"风险预算是否被实际满足"。

### 9.3 提示词的流水线顺序需要修正

> 提示词 §9 把 `Risk Budgeting` 列在 `Optimization` **之后**。**按上游的概念划分，这是不准确的**：

```
✅ 正确
Risk Budget（事前，属⑥）→ 进入约束集 → Optimization 求解 → Risk Contribution（事后，属⑦）→ 校验是否达成

❌ 提示词的表述容易被读成
Optimization → 然后才做 Risk Budgeting
```

**实际执行可以是迭代的**（求解 → 检查风险贡献 → 调整后重解），但**概念上 Risk Budget 是输入、Risk Contribution 是输出**，不可颠倒。

### 9.4 事后风险的实盘版本用 `Actual`

> ⑦-R 的实盘版本必须基于 **`Actual Portfolio`** 而非 `Target`（上游 ⑨-S 使用规则）。

---

## 10. Explainability

### 10.1 必须能回答

> **Why were these weights generated?**

```
① 目标函数：Minimum Volatility
② 求解路径：直接凸 QP
③ 输入：Σ（Risk Model v2，估计窗口 X）、候选集 N 只
④ 生效约束：单基金上限 X%、Equity 类别 [X%, X%]、换手率 ≤ X%
⑤ 结果：σ_p = X%，目标函数值 = X
⑥ 紧约束：单基金上限（Fund A、Fund C）、Equity 下限
```

### 10.2 紧约束（Binding Constraints）是关键诊断信息 ⚠️

> **哪些约束"卡住了"最优解，是理解结果的核心。**

```
若 Fund A 的权重恰好等于上限
    → 说明若放宽该上限，目标函数还能改善
    → 该约束正在实质性地塑造组合

若某约束远未触及
    → 它在本次求解中没有任何作用
    → 长期如此说明该约束可能设置过松
```

**要求**：优化输出必须列出紧约束清单。**只报告权重而不报告紧约束，等于给出结论而不给出原因。**

### 10.3 影子价格的业务含义

> 对紧约束，影子价格表示"放宽一单位该约束，目标函数能改善多少"。它使"是否值得放宽某约束"成为一个可量化的讨论，而非主观判断。

---

## 11. Optimization Policy

| 字段 | 说明 |
|---|---|
| `policy_id` / `version` | 标识与版本 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`objective`** | 目标函数 |
| **`solve_path`** | 求解路径（§4.3），**必须显式声明** |
| **`lambda_grid`** | 路径 A 的 `λ` 网格（若适用） |
| `return_estimate_model` | 引用 `07-return-risk` 的估计方法与版本 |
| `risk_model` | 引用 `07-return-risk` 的 `Σ` 估计方法与版本 |
| `min_holding_handling` | 最小持仓量的处理方式（§4.5） |
| `constraint_relaxation` | 第一阶段固定 `OFF` |
| **`solver_tolerance` / `max_iterations`** | 收敛判据 |
| **`random_seed`** | 固定随机种子（可复现要求） |

### 11.1 求解器技术选型不在本文档

> 具体求解器（建模层与后端）属 `02-architecture/06-technology-stack` §5.2。本域只声明**求解路径**与**收敛判据**这两项业务可见的配置。

### 11.2 Optimization Policy 属 `Portfolio Rule Version`

> 它是 Strategy Version 第 7 项的组成部分（含"求解器版本"），本域**不新增版本类型**。

---

## 12. Reproducibility

### 12.1 要素

```
Candidate Funds（该时点）
+ μ（Return Estimate Version）
+ Σ（Risk Model Version）
+ Constraint Set + Risk Budget（Portfolio Rule Version）
+ solve_path + lambda_grid + solver_tolerance + random_seed
+ Code Version（求解器与数值库版本）
+ decision_at
        ↓
    相同的权重向量（在既定数值容差内）
```

### 12.2 数值容差是可复现性的现实边界

> **凸优化的解在不同求解器、不同 BLAS 后端下可能有微小差异。**

因此可复现性的判据是"**在既定数值容差内相同**"，而非逐位相同。容差本身必须声明。

> **已定案 · 2026-08-27**：权重的数值容差 = **相对 1×10⁻⁶**（`TBD-resolution-2.md` Policy A）。
>
> **两条配套规则**：
>
> | # | 规则 |
> |---|---|
> | 1 | **权重的非零集合必须完全一致**（TOL-3）—— 这不是数值问题。持有哪些基金不一致，说明求解路径分叉 |
> | 2 | 权重之和的偏差须 `\|Σw − 1\| ≤ 1e-10` —— 归一化是确定性算术，不受求解器迭代影响，因此容差远严于权重本身 |
>
> **为什么权重容差比因子松四个数量级**：优化器的解是迭代逼近的，精度上限就是求解器终止容差（通常 1e-8~1e-6）。要求权重复现到 1e-10 等于要求每次走完全相同的迭代路径。

### 12.3 `Code Version` 是必需的第四要素

> 相同配置在不同求解器版本下可能产出不同数值（`02-architecture/01-system-architecture` §8.1）。求解器版本必须锁定并记录。

---

## 13. Edge Cases

| 情形 | 处理 |
|---|---|
| 候选集为空 | **阻断**，不进入求解 |
| 候选集仅 1 只基金 | 解退化为 `w = 1`；优化无实质作用但不构成错误 |
| `Σ` 病态或不可逆 | `NUMERICAL_ERROR`；须回 `07-return-risk` 检查估计方法 |
| **候选基金数 ≥ 观测数** | `Σ` 必然奇异；**求解前应预警**，这是估计问题不是求解问题（预警由 `07-return-risk/04` §7.1 提供 `T/N` 诊断） |
| 某基金协方差不可得 | 移出候选集并记录，**不得以 0 填充** |
| `μ` 不可得但目标需要 | **不得用历史收益代替** —— 该目标不可用（§3.1） |
| 约束互相冲突 | `INFEASIBLE` → §8.3 闭环 |
| 达到迭代上限 | `NOT_CONVERGED` → 与 `INFEASIBLE` 区别对待（§8.4） |
| Max Sharpe + 换手率约束 | Charnes-Cooper 不可用 → 按声明的替代路径（§4.3） |
| 最优解含大量微小权重 | 按 `min_holding_handling` 处理；截断后**必须重新校验约束**（§4.5） |
| 冻结持仓占据权重 | 作为固定量进入问题，可优化空间相应缩小（`02` §7.4） |

---

## 14. Auditability

> 本域审计总纲见 `01-portfolio-construction` §20。本节只列优化环节特有的要点。

### 14.1 求解过程本身必须可审计

> **只记录输出权重是不够的** —— 相同的权重可能来自不同的求解路径。

| 必须记录 | 理由 |
|---|---|
| **`solve_path`** | Max Sharpe 的 Charnes-Cooper 与 λ 扫描会给出不同结果（§4.3） |
| **`lambda_grid`** | 网格密度改变"Sharpe 最优点" |
| **`solver_tolerance` / 迭代次数** | 影响收敛判定 |
| **`random_seed`** | 若求解涉及随机初值 |
| **`code_version`** | 求解器与数值库版本 |

### 14.2 不可行事件必须入快照

> `INFEASIBLE` 不是"什么都没发生"，而是一次需要记录的决策事件（`02-business-requirements` §20.5 规则 4）。

**记录内容**：不可行的时点、当时的约束集、Human Review 的处置选择、以及**若选择"沿用上期权重"则必须显式标注**（§8.3 规则 3）。

### 14.3 紧约束的历史值得保留

> 与 `05-constraints` §14.2 同理 —— 某约束长期为紧约束，是它设置过紧的证据；这只能从历史中看出。

---

## 15. Summary

Optimization **只求解，不定义**。求解失败必须显式失败并阻断。

三条必须区分的边界：

- **五个"收益"概念不得混为一个字段** —— 尤其 `Historical Return ≠ Expected Return`（前者是 Factor，后者带 `Return Estimate Version`）；`μ` 不可得时依赖它的目标不可投产，而不是用历史收益代替
- **MAR 不得当作 Portfolio Return Target** —— 一个是"评价单只基金时多少算可接受"，一个是"这个组合要达到多少"，若需最低收益约束须定义独立的 `Minimum Portfolio Return`
- **Risk Budget（事前，属⑥）与 Risk Contribution（事后，属⑦）不可颠倒** —— 提示词把 Risk Budgeting 列在 Optimization 之后，按上游概念划分是不准确的

三项本域必须交付的技术判断：

- **Max Sharpe 是拟凸不是凸** —— 需 Charnes-Cooper 变换，而**换手率约束会破坏齐次性使变换失效**；替代路径（λ 扫描）必须随 `Portfolio Rule Version` 声明，且 `λ` 网格是结果的一部分
- **"最小持仓量"与"最小权重"不是一回事** —— 业务想要的"要么不持有要么至少 X%"是半连续变量、非凸；而 `w_i ≥ X%` 对全部候选基金会在候选集稍大时必然不可行
- **`INFEASIBLE` 与 `NOT_CONVERGED` 必须区别对待** —— 前者回 Construction 层查约束，后者查数值条件；混淆会让排查方向完全错误

一项容易被省略的输出：**紧约束清单**。只报告权重而不报告哪些约束卡住了解，等于给出结论而不给出原因。

---

## 16. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **优化器不得自行放松约束** | 等于求解层悄悄改变投资约束 |
| D-2 | 五个"收益"概念严格分离 | 混用会绕过版本治理 |
| D-3 | **`μ` 不可得时相关目标不可投产**，不用历史收益代替 | Min Vol / Risk Parity 不需 `μ`，可先行 |
| D-4 | **MAR 不得作为组合收益目标** | 粒度与语义均不同 |
| D-5 | 澄清 **Min CVaR 是凸 LP** | 避免沿用"CVaR 非凸"的错误表述 |
| D-6 | **求解路径必须随 `Portfolio Rule Version` 显式声明** | 否则相同配置在不同实现下结果不同 |
| D-7 | Max Sharpe + 换手率约束时采用 **λ 扫描（路径 A）**，`λ` 网格版本化 | Charnes-Cooper 在此失效；网格密度影响结果 |
| D-8 | **基数约束通过 Universe 层 Top-N 规避** | 避免混合整数 |
| D-9 | **最小持仓量优先用优化后截断**，且截断后必须重新校验 | 截断解可能违反原约束 |
| D-10 | 协方差不可得的基金移出候选集，**不得以 0 填充** | 填 0 等于宣称与所有基金无关，优化器会极度偏好它 |
| D-11 | **`INFEASIBLE` 与 `NOT_CONVERGED` 区别对待** | 排查方向完全不同 |
| D-12 | 第一阶段 **Constraint Relaxation = OFF** | 自动放松须配套审批与留痕 |
| D-13 | **紧约束清单是必备输出** | 只给结论不给原因 |
| D-14 | 可复现判据为"数值容差内相同" | 求解器与 BLAS 后端差异客观存在 |
| D-15 | Risk Budget 是输入、Risk Contribution 是输出，概念上不可颠倒 | 上游 ⑦-R |

---

## 17. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | Optimization **不定义**目标与约束，只求解 | 上游 §5.3 |
| C-2 | 不可行时必须返回失败并上报，**不得自行放松约束** | 上游 §4.2 ⑦、§5.3 |
| C-3 | **严禁静默降级为等权或上期权重** | 上游 §4.2 ⑦ |
| C-4 | 求解必须可复现（固定随机种子与求解器版本） | 同上 |
| C-5 | **`Fund Score` 不得作为 `μ`** | 上游 §5.2 |
| C-6 | `Σ` 必须来自 `07-return-risk`，不得在本域估计 | 本文档 §5.1 |
| C-7 | Risk Budget 与 Risk Contribution 必须同时留存于决策快照 | 上游 §4.2 ⑦-R |
| C-8 | 不可行事件必须记录到决策快照 | `02-business-requirements` §20.5 |
| C-9 | 本域**不引入** ML / AI 优化 | 上游 §6.2.1、`02-business-requirements` §19.7 |
| C-10 | 全部输入满足 `available_at ≤ decision_at` | 上游 §4.2 ①-PIT |

---

## 18. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| PO-1 | 是否需要 `Minimum Portfolio Return` 约束及取值 | 收益约束 | 投研 |
| ~~PO-2~~ | ~~Max Sharpe 在换手率约束下的求解路径及 `λ` 网格~~ —— **已定案**：Max Sharpe 在换手率约束下采用【λ 网格扫描 + 择优】，λ 取 21 点对数网格 | — | ✅ 2026-08-27 |
| ~~PO-3~~ | ~~最小持仓量的处理方式与阈值~~ —— **已定案**：第一阶段【不】实现最小持仓量约束，改用「优化后截断 + 重新归一」并记录截断量 | — | ✅ 2026-08-27 |
| ~~PO-4~~ | ~~是否引入 Constraint Relaxation Policy~~ —— **已定案**：第一阶段【不】引入 Constraint Relaxation Policy；不可行时返回 `INFEASIBLE` 并给出冲突约束集 | — | ✅ 2026-08-27 |
| ~~PO-5~~ | ~~权重的数值容差阈值~~ —— **已定案**：见 Policy A 数值容差体系 | — | ✅ 2026-08-27 |
| PO-6 | 最终生产目标函数的选择（= 上游 `TBD-P1-10`） | 策略投产 | 投研 |

---

## 19. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ⑦、⑦-R、§5.3）、`02-business-requirements.md` v2.3（§19.2、§20.5） |
| **本域** | `01-portfolio-construction`（问题定义）、`04-risk-budgeting`（事前预算）、`05-constraints`（约束集）、`06-rebalancing`（换手率与当前权重） |
| **输入来源** | `07-return-risk`（`μ`、`Σ`、Correlation）、`03-data`（`R_f`） |
| **架构** | `02-architecture/06-technology-stack.md` v1.2（§5.2 求解器、§5.2.1 凸性、§5.2.2 非凸情形）、`01-system-architecture.md` v2.2（§8.2） |

---

## 20. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（4 项）**。`PO-2` Max Sharpe 采用 **λ 网格扫描 + 择优**（21 点对数网格），每个子问题保持凸性；**结果是 Sharpe 的下界**，报告不得表述为「最优 Sharpe」。`PO-3` **不实现最小持仓量约束**（基数约束非凸需 MIQP），改用截断 + 归一并记录 `truncated_weight_total`，超 5% 告警。`PO-4` **不引入自动松弛**，`INFEASIBLE` 时返回冲突约束集 —— 自动松弛会让「约束被违反」变成静默事件，且松弛顺序本身是未经论证的风险偏好。`PO-5` 容差见 Policy A。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.1 | 2026-08-26 | `Σ` 可用性校验与 `T/N` 预警的落实位置补充指向 `07-return-risk/04` §7.1 与 `06` §7；`μ` 与 `Σ` 的维度对齐责任已由 `07-return-risk/01` §6.2 明确承担 | `07-return-risk` v1.0 |
| v1.0 | 2026-08-26 | 初始版本。**§3 五个"收益"概念的分离**（含 `Historical Return ≠ Expected Return` 与 **MAR 不得作为组合收益目标**）；**§4.1 各目标的数学性质表**（Max Sharpe 拟凸、Min CVaR 是凸 LP）；**§4.3 落实架构层交办的 Max Sharpe 求解路径定义**——换手率约束破坏齐次性使 Charnes-Cooper 失效，给出三条替代路径并要求 `λ` 网格版本化；**§4.5 区分"最小持仓量"与"最小权重"**（前者半连续非凸，后者在候选集稍大时必然不可行），截断法的代价与重新校验要求；§5.2 `Σ` 维度完整性检查与"不得以 0 填充协方差"；**§8.4 `INFEASIBLE` 与 `NOT_CONVERGED` 的区别**；§8.3 不可行闭环四条规则；**§9.3 指出提示词的流水线顺序与上游 ⑦-R 概念划分不一致**；**§10.2 紧约束清单是必备输出**；**§14.1 求解过程本身必须可审计**——相同权重可能来自不同求解路径 | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`06-technology-stack.md` v1.2 |