# 风险预算 · Risk Budgeting

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑥ Portfolio Construction**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§20 Risk Control
> 本域上游：docs/06-portfolio/01-portfolio-construction.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **组合风险如何在各组成部分之间分配？**

### 1.2 三组必须区分的概念 ⚠️

| 概念 | 回答 | 归属 |
|---|---|---|
| **Risk Measurement** | 组合**有多少**风险？ | `07-return-risk`（事前）+ `03`（⑦-R 事后） |
| **Risk Budgeting** | 各部分**允许承担多少**风险？ | **本文档**（事前，属 ⑥） |
| **Risk Contribution** | 各部分**实际承担了多少**风险？ | `03-portfolio-optimization`（⑦-R，事后） |

```
Risk Budget（本文档，事前）
      ↓  作为约束进入优化问题
Optimization 求解
      ↓
Risk Contribution（03，事后）
      ↓  与 Budget 对比
Budget Validation（本文档 §7）
```

### 1.3 Risk Budget 与 Constraint 不是同一件事 ⚠️

> **两者都限制组合，但表达的是不同的东西。**

| | **Risk Budget** | **Constraint** |
|---|---|---|
| 表达 | 各部分**应当消耗多少风险** | **不得超过**什么 |
| 关注 | 风险的**分配结构** | 单点的**上下限** |
| 典型 | `Equity 风险贡献 ≤ 60%` | `组合波动率 ≤ X%` |
| 单位 | 通常是**占比**（相对） | 通常是**绝对量** |
| 归属 | 本文档 | `05-constraints` |

```
Risk Budget:  Equity Risk Contribution = 50%   ← 风险如何分布
Constraint:   Portfolio Volatility ≤ TBD       ← 总量不得超过
```

> **一个组合可以满足全部 Constraint 却严重违反 Risk Budget** —— 总波动率达标，但 90% 的风险来自单一类别。这正是需要两套机制的原因。

### 1.4 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| `Σ`、Volatility 等风险量的**估计方法** | `07-return-risk` |
| 单个 Factor 的定义与公式 | `04-factor` |
| 约束的完整清单与优先级 | `05-constraints` |
| 风险贡献的**实际计算** | `03-portfolio-optimization`（⑦-R） |
| 风险告警的处置流程 | `12-operations`、`13-governance` |

---

## 2. Risk Metrics

> **本域不定义风险指标，只引用。**

| 指标 | 定义归属 | 可作为 Budget 的对象 |
|---|---|---|
| **Portfolio Volatility** | `03` ⑦-R（`σ_p = sqrt(w'Σw)`） | ✅ |
| **Risk Contribution** | `03` ⑦-R（`TRC_i`、`RCP_i`） | ✅ |
| **Tracking Error** | `04-factor`（`F-REL-005`）的组合层版本 | ✅ |
| Downside Volatility | `04-factor`（`F-RISK-002`） | 见 §2.1 |
| VaR / CVaR | `04-factor`（`F-RISK-004/005`） | 见 §2.1 |
| **Maximum Drawdown** | `04-factor`（`F-RISK-003`） | **❌ 见 §3** |

### 2.1 组合层指标不等于基金层指标的加权平均 ⚠️

> **这是一处根本性的区分。**

```
组合波动率  ≠  Σ w_i × σ_i
    → 正确算法是 sqrt(w'Σw)，依赖相关性

组合 VaR    ≠  Σ w_i × VaR_i
    → VaR 不满足次可加性的加权关系，需按组合收益分布重新计算

组合最大回撤 ≠  Σ w_i × MDD_i
    → 各基金的回撤发生在不同时点
```

**因此**：以 VaR / CVaR / Downside Volatility 为对象的 Risk Budget，**需要组合层的重新计算**，不能由基金层 Factor 加权得到。这些计算属 `07-return-risk` 与 `03` ⑦-R，本域只声明预算对象。

> **已定案 · 2026-08-27**：采用 **`07-return-risk/03-risk-estimate` §7.6 推荐的历史模拟法** —— 用组合权重重构历史组合收益序列，再取其分位数。
>
> **依据**：基金收益**厚尾**，参数法（正态假设）会系统性**低估**尾部风险 —— 而 VaR/CVaR 存在的意义正是度量尾部。蒙特卡洛法引入随机性，与可复现性要求冲突。
>
> **与 `07-return-risk/03` `RI-10` 是同一决策，两处不得分别配置** —— 若本域用参数法而估计域用历史模拟，同一组合的 CVaR 在两处会是两个数。
>
> **历史模拟的局限须在报告中声明**：它无法表达样本期外的风险。**这个局限是诚实的** —— 参数法看似能外推，实际是用一个已知错误的分布假设在外推。

---

## 3. 最大回撤不能作为事前预算 ⚠️

> **沿用 `02-business-requirements` §20.2 的可计算性边界。**

```
Volatility 事前约束：  σ_p = sqrt(w'Σw) ≤ X       ✅ 给定 w 与 Σ 即可计算
最大回撤事前约束：     Future MaxDD(w) ≤ X        ❌ 依赖未来价格路径，建仓时未知
```

**最大回撤是路径依赖的量**。同样的权重与协方差，不同的价格路径会产生完全不同的回撤。

### 3.1 事前 / 事后能力矩阵

| 控制项 | 事前约束 | 事后监控 |
|---|:---:|:---:|
| 单基金权重上限 | ✅ | ✅ |
| 类别权重上限 | ✅ | ✅ |
| **组合波动率上限** | ✅ | ✅ |
| **最大组合回撤** | **❌** | ✅ |
| 组合集中度（HHI / 前 N 大） | ✅ | ✅ |
| 相关性约束 | ✅ | ✅ |
| 换手率上限 | ✅ | ✅ |
| **风险贡献占比** | ✅ | ✅ |

### 3.2 若需事前控制回撤，必须先定义可计算的代理

| 代理方法 | 说明 | 代价 |
|---|---|---|
| **历史情景重演** | 用历史极端区间重算该权重下的回撤 | 依赖历史情景的代表性 |
| **蒙特卡洛路径分位** | 模拟路径后取回撤分位数 | **引入随机性，须固定种子**，否则破坏可复现性 |
| **波动率-相关性代理** | 由 `σ_p` 与相关性构造回撤代理指标 | 只是近似，与真实回撤的关系不稳定 |

> **不得在业务需求层写下一个无法落地的约束** —— 那会让本域面对一个无解的要求。

> **已定案 · 2026-08-27**：**不设事前回撤约束**；下行风险的事前控制由 **CVaR 约束**承担。见 `02-business-requirements` §21（`P1-11`）与 `07-return-risk/03` `RI-1`。
>
> **本域的连带结论**：`07-return-risk` 不提供回撤代理量（三个候选方案均不实现），因此本域**没有可纳入的代理约束**。
>
> **最大回撤仍在本域的风险指标体系内**，但作为**事后监控项** —— 计算、落库、超阈值告警（阈值属 `RB-4`），不进优化。
>
> ⚠️ **不得把 CVaR 约束表述为「回撤控制」**：CVaR 回答「最坏 5% 的期间平均亏多少」，回撤回答「从峰到谷最多亏多少」。**约束住前者不等于约束住了后者** —— 一个 CVaR 达标的组合仍可能经历深度回撤（若亏损期连续发生）。

### 3.3 蒙特卡洛代理与可复现性的冲突

> **若采用蒙特卡洛路径分位作为代理，必须固定随机种子**，且种子是 `Portfolio Rule Version` 的一部分 —— 否则相同配置每次得到不同的约束边界，优化结果不可复现（上游 §9 原则六）。

---

## 4. Risk Contribution 的数学定义

> **公式在此给出是为了定义预算对象；实际计算属 `03` ⑦-R。**

```
组合波动率              σ_p  = sqrt(w'Σw)
边际风险贡献            MRC_i = ∂σ_p / ∂w_i  =  (Σw)_i / σ_p
总风险贡献              TRC_i = w_i × MRC_i
风险贡献占比            RCP_i = TRC_i / σ_p
```

### 4.1 欧拉分解恒等式

```
Σ TRC_i = σ_p      ⟹      Σ RCP_i = 1
```

> **这是校验计算正确性的硬判据。** 若 `Σ RCP_i ≠ 1`（超出数值容差），说明 `TRC` 计算有误。

### 4.2 风险贡献可以与权重严重背离

> **这是 Risk Budget 存在的根本理由。**

```
权重分布：Equity 40% / Bond 60%          看起来偏保守
风险贡献：Equity 85% / Bond 15%          实际上高度集中于权益

原因：权益基金的波动率远高于债券基金，且组内相关性高
```

**因此只看权重的分散化是不够的** —— 权重分散不等于风险分散。这也是 `01-portfolio-construction` §5.1 把"分散化"落到风险预算而非模糊目标的原因。

### 4.3 风险贡献依赖 `Σ`，因而继承其全部脆弱性

> `Σ` 估计不佳时，风险贡献的分解同样不可信。`Σ` 的可用性问题见 `03` §5.2。

---

## 5. Risk Budget 六要素（已定案）

> **每条 Risk Budget 必须完整定义六要素，缺一不得进入优化问题**（上游 §11.2、`02-business-requirements` §20.3）。

| 要素 | 内容 | 示例 |
|---|---|---|
| **① 风险指标** | 对哪个量做预算 | 组合波动率 / 风险贡献占比 / Tracking Error |
| **② 预算值** | 数值上限或目标 | ≤ TBD |
| **③ 适用范围** | 整体 / 类别 / 单基金 / 风险因子 | 权益类整体 |
| **④ 计算方式** | 如何计算该风险量 | `TRC_i / σ_p` |
| **⑤ 超预算处理** | 硬性拒绝 / 告警 / 自动收缩 | 触发 `WARNING`，超 X% 触发 `CRITICAL` |
| **⑥ 硬约束 or 软目标** | 是否可被违反 | 硬约束 |

### 5.1 缺任一要素的预算不得进入优化问题

> **这不是形式要求。** 每个要素的缺失都会产生一个具体的失败模式：

| 缺失 | 后果 |
|---|---|
| ① 风险指标 | 不知道在预算什么 |
| ② 预算值 | 无法形成约束 |
| **③ 适用范围** | **"最大权重 10%" 却没说 10% 是对什么而言**（`05-constraints` §7 同一问题） |
| ④ 计算方式 | 同一指标有多种算法，结果不同 |
| ⑤ 超预算处理 | 触发时无处置依据 |
| **⑥ 硬 or 软** | **优化器不知道该把它当约束还是惩罚项** —— 直接决定问题的数学形式 |

---

## 6. Risk Budget 的层级

```
Portfolio Risk Budget
      ↓
Asset Class Risk Budget
      ↓
Fund Risk Budget
```

> **与 `02-asset-allocation` 的层级一致**（三层，不引入 Sleeve）。

### 6.1 层级示例

```
组合波动率预算        Portfolio Volatility ≤ TBD
类别风险贡献预算      Equity Risk Contribution ≤ TBD
单基金风险贡献预算    Single Fund Risk Contribution ≤ TBD
跟踪误差预算          Tracking Error ≤ TBD
```

> **以上参数当前均为 TBD，投产前必须由业务负责人确认。** 本域不自行指定比例。

`<TBD-RB-3: 各项 Risk Budget 的具体预算值（= 上游 TBD-P1-12），待投研与风控确认>`

### 6.2 层级间的一致性不是简单相加 ⚠️

> **风险贡献占比可以按层级相加，但风险量本身不能。**

```
✅ Σ RCP_i = 1，因此类别层 RCP 之和 = 1
   → 类别风险贡献预算之和必须 ≥ 100%，否则必然不可行

❌ σ_Equity + σ_Bond ≠ σ_p
   → 波动率不可加，类别波动率预算之和与组合波动率预算无直接关系
```

**因此**：以 `RCP` 为对象的预算可做层级校验（和为 1）；以 `Volatility` 为对象的预算**不能**跨层级做加法校验。

> **这是配置校验中最容易写错的一处** —— 套用权重的"子层之和等于父层"逻辑到波动率上，会得到恒假的校验。

---

## 7. Risk Budget Validation

### 7.1 校验形式

```
Actual Risk Contribution（来自 03 ⑦-R）
        vs
Allowed Risk Budget（本文档定义）
```

### 7.2 校验结果

| 状态 | 含义 |
|---|---|
| **`WITHIN_LIMIT`** | 实际风险贡献在预算内 |
| **`BREACHED`** | 超出预算 |
| **`NOT_AVAILABLE`** | 无法计算（`Σ` 不可得、成分数据缺失等） |

### 7.3 `NOT_AVAILABLE` 不得当作 `WITHIN_LIMIT` ⚠️

> 与全平台"缺失不得转 0"是同一条原则。

```
❌ 风险贡献算不出来 → 视为"没有超预算" → 放行
   → 这是最危险的默认值选择：把"不知道"当作"没问题"
```

**处理**：`NOT_AVAILABLE` 必须**阻断**并告警，与 `BREACHED` 同等对待（在放行判定上）。

### 7.4 Budget 校验发生在两个时点

| 时点 | 使用的权重 | 目的 |
|---|---|---|
| **决策时** | `Target Portfolio` | 校验优化结果是否达成预算 |
| **持续监控** | **`Actual Portfolio`** | 净值漂移可能使实际风险贡献偏离 |

> 沿用上游 ⑨-S 使用规则：约束合规校验用 `Target`（决策时）+ `Actual`（持续监控）。

---

## 8. Risk Budget Breach

### 8.1 Breach 不自动触发再平衡

> **这是一条重要的职责边界。**

```
Risk Budget Breach 发生
        ↓
   ❌ 不自动 Rebalance
        ↓
   ✅ 由 Rebalancing Policy 决定是否、何时、如何调整
```

**理由**：调仓有成本。一次轻微且可能自行回复的 Breach，不值得付出换手成本。成本收益判据属 `06-rebalancing` §4。

### 8.2 但 `CRITICAL` 必须阻断调仓流程

> 沿用 `02-business-requirements` §20.4：

```
NORMAL   ──  各项风险指标在阈值内
WARNING  ──  接近阈值，需关注
CRITICAL ──  突破阈值，需处置并【阻断调仓流程】
```

> **注意这与 §8.1 不矛盾**：§8.1 说 Breach 不自动**发起**调仓；§8.2 说 `CRITICAL` 阻断**正在进行的**调仓。前者是"不主动做"，后者是"不许做"。

`<TBD-RB-4: 各风险指标的 WARNING / CRITICAL 阈值（= 上游 TBD-P1-13），待投研与风控确认>`

### 8.3 超预算处理方式由要素⑤声明

| 方式 | 说明 |
|---|---|
| **硬性拒绝** | 优化时作为硬约束，违反则 `INFEASIBLE` |
| **告警** | 允许通过但产生告警，进入 Human Review |
| **自动收缩** | 按规则缩减超预算部分的权重 —— **第一阶段不实现** |

> **自动收缩第一阶段不实现**：它实质上是在优化之后修改权重，等价于"求解层放松/修改了结果"，与 `03` §1.3 的原则冲突。若需要，应作为约束进入优化问题，而非事后修正。

---

## 9. Risk Budgeting 与 Optimization 的关系

### 9.1 两种实现形态

> **业务文档不绑定具体实现**（提示词 §13.8）。

```
形态 A：Risk Budget 作为优化约束
    Risk Budget → Constraint Set → Optimization → 结果天然满足预算

形态 B：优化后校验，不满足则重解
    Optimization → Risk Budget Check → 不满足 → 调整后 Re-optimize
```

### 9.2 但两种形态下 Budget 都是"输入" ⚠️

> **无论采用哪种实现，概念上 Risk Budget 是事前定义的输入，Risk Contribution 是事后产生的输出**（上游 ⑦-R）。

形态 B 的"事后校验"校验的是**结果是否达成事前定义的预算**，不是"事后才定义预算"。

### 9.3 形态 B 的迭代必须有终止条件

> 若采用形态 B，反复"求解 → 校验 → 调整 → 重解"可能不收敛。

**要求**：迭代次数上限与终止条件必须显式定义，达到上限仍不满足时返回 `INFEASIBLE`，**不得接受最后一次的违约解**。

> **已定案 · 2026-08-27**：采用**形态 A（优化后校验）**，**不迭代**。
>
> **依据 —— 迭代会破坏可复现性**：
>
> ```
> 形态 B（迭代）：优化 → 校验 → 超限则调整参数重优化 → 再校验 …
>     → 结果依赖迭代次数与终止条件
>     → 而终止条件本身是又一组待定参数
>     → 且不保证收敛：调整参数可能在两个超限状态间震荡
>
> 形态 A（一次性）：优化 → 校验 → 超限则【返回违反项，由人决策】
>     → 结果唯一，可复现
> ```
>
> **形态 A 的代价**：超限时不产出可用组合，需要人介入。**但这正是 Risk Budget 存在的意义** —— 它是一条需要被知晓的边界，而非一个自动调节的旋钮。
>
> **与 `PO-4` 是同一原则**：不可行/超限时暴露问题，不自动修正。

---

## 10. Risk Budget Policy

| 字段 | 说明 |
|---|---|
| `policy_id` / `version` | 标识与版本 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`budgets`** | 预算条目列表，**每条含六要素** |
| **`alert_thresholds`** | `WARNING` / `CRITICAL` 阈值 |
| `validation_mode` | 形态 A 或 B（§9.1） |
| `iteration_limit` | 形态 B 的迭代上限 |
| `drawdown_proxy_method` | 事前回撤代理方法（若启用，§3.2） |
| `random_seed` | 蒙特卡洛代理时必需（§3.3） |

### 10.1 属 `Portfolio Rule Version`

> Risk Budget 是 Strategy Version 第 7 项的组成部分（上游 §11.2 术语表：`Portfolio Rule Version` = 目标函数 / 权重规则 + 约束集 + **风险预算** + 求解器版本）。本域**不新增版本类型**。

---

## 11. Input / Process / Output

### 11.1 Input

| 输入 | 来源 |
|---|---|
| `Risk Budget Policy` + version | 本文档 |
| Asset Class 映射 | `02-asset-allocation` |
| `Σ` | `07-return-risk` |
| `risk_profile` | Portfolio Object（`01` §7.1） |
| Risk Contribution（校验时） | `03` ⑦-R |

### 11.2 Output

| 字段 | 说明 |
|---|---|
| **`risk_budget_set`** | 进入优化问题的预算约束（六要素齐备） |
| **`budget_validation_result`** | 逐条的 `WITHIN_LIMIT` / `BREACHED` / `NOT_AVAILABLE` |
| **`actual_vs_budget`** | 实际风险贡献与预算的对比明细 |
| `alert_level` | `NORMAL` / `WARNING` / `CRITICAL` |
| `risk_budget_policy_version` | 政策版本 |

---

## 12. Explainability

> **必须能回答：Why does this fund consume this much risk?**

```
Fund A 的风险贡献占比 = X%，因为：
  ① 其权重 w_A = X%
  ② 其边际风险贡献 MRC_A = X（= (Σw)_A / σ_p）
  ③ TRC_A = w_A × MRC_A = X
  ④ RCP_A = TRC_A / σ_p = X%
  ⑤ 该基金与组合其他成分的相关性偏高，使 MRC 高于其自身波动率的直觉预期
  ⑥ 所属类别 Equity 的预算为 ≤ X%，当前该类别合计 X% → WITHIN_LIMIT
```

### 12.1 必须能解释"权重不高但风险贡献高"

> 这是使用者最常提出的疑问，也是 §4.2 现象的直接体现。解释必须落到 `MRC` 与相关性，而非仅给出数值。

---

## 13. Edge Cases

| 情形 | 处理 |
|---|---|
| `Σ` 不可得 | 风险贡献 `NOT_AVAILABLE` → **阻断**，不得视为通过（§7.3） |
| `σ_p = 0` | `RCP` 分母为零 → `NOT_AVAILABLE`；这通常意味着 `Σ` 有误 |
| `Σ RCP_i ≠ 1` | 计算错误 → 阻断并告警（§4.1 恒等式） |
| 类别风险贡献预算之和 < 100% | **配置错误** —— 必然不可行（§6.2） |
| 对波动率做跨层级加法校验 | **校验本身写错了** —— 波动率不可加（§6.2） |
| 冻结持仓贡献大量风险 | 该部分风险不可通过调仓消除；预算校验须**单独标注**，不应导致整体判定为不可行 |
| 单基金风险贡献超预算但权重在限内 | 正常情形 —— 说明该基金波动或相关性高；这正是 Risk Budget 的价值 |
| 事前回撤代理未配置但要求回撤约束 | **阻断** —— 不得使用无法计算的约束（§3） |

---

## 14. Reproducibility

```
Σ（Risk Model Version）
+ Risk Budget Policy Version
+ 权重 w（来自 03）
+ 层级映射（Allocation Policy Version）
+ random_seed（若使用蒙特卡洛代理）
        ↓
    相同的风险贡献与校验结果
```

> **Risk Budget 与 Risk Contribution 必须同时留存于决策快照**，事后才能回答"风险预算是否被实际满足"（上游 ⑦-R）。

---

## 15. Auditability

> 本域审计总纲见 `01-portfolio-construction` §20。本节只列风险预算特有的要点。

### 15.1 Budget 与 Contribution 必须成对留存

> **上游 §4.2 ⑦-R 的明确要求。** 只存其一都无法回答审计的核心问题：

```
只存 Budget        → 不知道实际是否达成
只存 Contribution  → 不知道当时的目标是什么
成对留存           → 才能回答"风险预算是否被实际满足"
```

### 15.2 `NOT_AVAILABLE` 的原因必须记录

> 与 `WITHIN_LIMIT` / `BREACHED` 不同，`NOT_AVAILABLE` 本身需要归因：是 `Σ` 不可得、成分数据缺失，还是 `σ_p = 0`？不记录原因则无法排查。

### 15.3 蒙特卡洛代理的种子必须入快照

> 若启用事前回撤代理（§3.2），随机种子是**结果的一部分**（§3.3）。不记录则约束边界不可复现。

---

## 16. Summary

Risk Budgeting 定义**风险如何分配**，是事前的、属 Stage ⑥ 的输入。

三组必须区分的概念：

- **Risk Measurement（有多少）/ Risk Budgeting（允许多少）/ Risk Contribution（实际多少）**
- **Risk Budget（分配结构）与 Constraint（单点上限）不是同一件事** —— 一个组合可以满足全部 Constraint 却把 90% 风险集中在单一类别
- **无论实现形态如何，Budget 概念上都是输入，Contribution 是输出**

三条技术判断：

- **最大回撤不能作为事前预算** —— 它是路径依赖量；若需事前控制必须先定义可计算的代理，而蒙特卡洛代理会引入随机性、须固定种子否则破坏可复现性
- **组合层指标不是基金层指标的加权平均** —— 组合 VaR / 回撤都需要重新计算，不能由 Factor 加权得到
- **风险贡献占比可跨层级相加（和为 1），波动率不能** —— 套用权重的"子层之和等于父层"逻辑到波动率上，会得到恒假的校验

两处默认值陷阱：

- **`NOT_AVAILABLE` 不得当作 `WITHIN_LIMIT`** —— 把"不知道"当作"没问题"是最危险的默认选择
- **Breach 不自动触发再平衡，但 `CRITICAL` 阻断调仓** —— 前者是"不主动做"，后者是"不许做"，两者不矛盾

---

## 17. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **Risk Budget 属事前（⑥），Risk Contribution 属事后（⑦）** | 上游 ⑦-R |
| D-2 | **Risk Budget 与 Constraint 分开** | 前者管分配结构，后者管单点上限 |
| D-3 | **最大回撤不作为事前预算** | 路径依赖，建仓时不可计算 |
| D-4 | 事前回撤代理若用蒙特卡洛，**种子必须固定并版本化** | 否则破坏可复现性 |
| D-5 | 组合层 VaR / CVaR 需重新计算，**不由基金层加权** | 不满足加权关系 |
| D-6 | 六要素缺一不得进入优化问题 | 每个缺失都对应一个具体失败模式 |
| D-7 | **`RCP` 可跨层级校验（和为 1），`Volatility` 不可** | 波动率不可加 |
| D-8 | **`NOT_AVAILABLE` 必须阻断，不得视为通过** | "不知道"≠"没问题" |
| D-9 | Breach **不自动触发**再平衡 | 调仓有成本，由 Rebalancing Policy 权衡 |
| D-10 | `CRITICAL` **阻断**调仓流程 | `02-business-requirements` §20.4 |
| D-11 | **自动收缩第一阶段不实现** | 等价于事后修改优化结果，与 `03` §1.3 冲突 |
| D-12 | 形态 B 的迭代必须有终止条件，**不得接受最后一次违约解** | 否则等于静默放行 |
| D-13 | `Σ RCP_i = 1` 作为计算正确性的硬判据 | 欧拉分解恒等式 |

---

## 18. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 每条 Risk Budget 必须六要素齐备 | 上游 §11.2、`02-business-requirements` §20.3 |
| C-2 | 最大回撤**不得**作为事前约束，除非定义可计算代理 | `02-business-requirements` §20.2 |
| C-3 | Risk Budget 与 Risk Contribution 必须同时留存于决策快照 | 上游 §4.2 ⑦-R |
| C-4 | `CRITICAL` 必须阻断调仓流程 | `02-business-requirements` §20.4 |
| C-5 | 风险控制优先级高于收益最大化 | `02-business-requirements` §20.5 |
| C-6 | 本域**不估计** `Σ` 或其他风险量 | `07-return-risk` 拥有 |
| C-7 | 风险预算属 `Portfolio Rule Version`，不新增版本类型 | 上游 §11.2 |
| C-8 | 持续监控使用 `Actual Portfolio` | 上游 ⑨-S |

---

## 19. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~RB-1~~ | ~~组合层 VaR / CVaR 的方法选择 —— 方法已由 `07-return-risk/03` §7.6 给出（推荐方法 A），仅余选择~~ —— **已定案**：组合层 VaR/CVaR 采用 `07-return-risk/03` §7.6 推荐的【历史模拟法】 | — | ✅ 2026-08-27 |
| ~~RB-2~~ | ~~是否需要事前回撤约束及代理方法（= 上游 `TBD-P1-11`）~~ —— **已定案**：同 P1-11：不设事前回撤约束，用 CVaR 替代 | — | ✅ 2026-08-27 |
| RB-3 | **各项 Risk Budget 的具体预算值**（= 上游 `TBD-P1-12`） | 预算无法投产 | 投研 + 风控 |
| RB-4 | 各风险指标的 `WARNING` / `CRITICAL` 阈值（= 上游 `TBD-P1-13`） | 告警分级 | 投研 + 风控 |
| ~~RB-5~~ | ~~Budget 校验采用形态 A 或 B；若 B，迭代上限与终止条件~~ —— **已定案**：Risk Budget 校验采用【形态 A：优化后校验】，不迭代 | — | ✅ 2026-08-27 |
| RB-6 | 冻结持仓贡献的风险如何计入预算校验 | 预算判定 | 组合 + 风控 |

---

## 20. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ⑦-R、§11.2 Risk Budget）、`02-business-requirements.md` v2.3（§20） |
| **本域** | `01-portfolio-construction`（问题定义）、`02-asset-allocation`（层级）、`03-portfolio-optimization`（⑦-R 实际计算）、`05-constraints`（与 Constraint 的边界）、`06-rebalancing`（Breach 后的处置） |
| **输入来源** | `07-return-risk`（`Σ`）、`04-factor`（风险类 Factor 定义） |
| **下游** | `12-operations`（风险告警）、`13-governance`（风控治理） |

---

## 21. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（3 项）**。`RB-1` 组合层 VaR/CVaR 采用**历史模拟法**，与 `07-return-risk/03` `RI-10` 是同一决策不得分别配置；`RB-2` **不设事前回撤约束**，回撤转为事后监控，并明确**不得把 CVaR 约束表述为「回撤控制」**（CVaR 达标的组合仍可能经历深度回撤）；`RB-5` 校验采用**形态 A（一次性）不迭代** —— 迭代结果依赖终止条件且不保证收敛，会破坏可复现性。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.1 | 2026-08-26 | `TBD-RB-1` 与 `TBD-RB-2` 获 `07-return-risk` 回应：组合层 VaR/CVaR 的计算方法已由 `07-return-risk/03` §7.6 给出（**不可由基金层加权，须按组合收益序列重算**），回撤代理量由 §4.2 提供并列明各自代价。两项 TBD 收窄为"方法选择"而非"方法待定" | `07-return-risk/03-risk-estimate.md` v1.0 |
| v1.0 | 2026-08-26 | 初始版本。**§1.2 三组概念区分**（Measurement / Budgeting / Contribution）与 **§1.3 Risk Budget 与 Constraint 的分离**（满足全部 Constraint 仍可能 90% 风险集中于单一类别）；**§2.1 组合层指标不是基金层加权平均**；**§3 最大回撤不可事前预算**及三种代理方法的代价，**§3.3 蒙特卡洛代理与可复现性的冲突**；§4.1 欧拉分解恒等式作为计算正确性硬判据；**§4.2 风险贡献可与权重严重背离**——权重分散不等于风险分散；§5.1 六要素缺失的具体失败模式；**§6.2 `RCP` 可跨层级相加而 `Volatility` 不可**（套用权重逻辑会得到恒假校验）；**§7.3 `NOT_AVAILABLE` 不得当作 `WITHIN_LIMIT`**；**§8.1 与 §8.2 的区分**（Breach 不主动发起调仓 vs `CRITICAL` 阻断正在进行的调仓）；§8.3 自动收缩第一阶段不实现的理由；**§15.1 Budget 与 Contribution 必须成对留存** | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`01-portfolio-construction.md` v1.0 |