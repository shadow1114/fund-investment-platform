# 前视偏差 · Look-ahead Bias

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑧ Backtest**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§26.1 Look-ahead Bias
> 本域上游：docs/08-backtest/01-backtest-engine.md（v1.0）
>
> **文档版本**：v1.3 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **如何识别并防止未来信息进入历史决策？**

### 1.2 为什么这是回测的核心控制文档

> **前视偏差在净值曲线上完全看不出来。**

```
一条前视污染的回测曲线，与一条干净的曲线在形态上没有区别
    → 它只是【更好看】
    → 没有任何异常可供察觉
    → 只能靠机制防范，不能靠事后观察
```

（`02-business-requirements` §26.1）

### 1.3 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 引擎如何执行 | `01-backtest-engine` |
| 幸存者偏差 | `04-survivorship-bias` |
| 交易可得性偏差 | `04-survivorship-bias` §11（Tradability） |
| 数据版本机制 | `03-data/04-data-versioning` |
| 各域自身的 PIT 实现 | 各域文档 |

---

## 2. Definition

> **在历史决策中使用了该决策时点实际不可获得的信息。**

```
Decision Date = T
只能使用：available_at ≤ T 的数据
```

---

## 3. 判定标准用 `available_at`，不是 `effective_at` ⚠️

> **沿用上游 §4.2 ①-PIT 与 `02-business-requirements` §26.1。**

```
基金经理变更   effective_at = 2026-08-20   （生效日）
               available_at = 2026-08-25   （公告发布）
决策日         decision_at  = 2026-08-22

按 effective_at 判断 → 通过 ✗   系统在 8/22 根本不知道这件事
按 available_at 判断 → 拒绝 ✓
```

### 3.1 生效日早于披露日是基金数据的常态

> **不是例外情形。** 经理变更、基金分类调整、定期报告持仓、规模数据、净值修订 —— 全都如此（上游 §4.2 ①-PIT）。

**按生效日筛选会稳定地使用当时不可能知道的信息**，而不是偶发地。

### 3.2 同一时点多版本时取 `version` 最大者

> 沿用上游 ①-PIT：满足 `available_at ≤ T` 的版本可能有多个（数据被修订过），取**版本序号最大者** —— 即"当时能看到的最新版本"。

---

## 4. Observation Date vs Available Date

| | **Observation Date**（`effective_at`） | **Available Date**（`available_at`） |
|---|---|---|
| 含义 | 数据**描述的**时点 | 数据**可被使用的**最早时刻 |
| 例 | 季报期末 = 3-31 | 季报披露 = 4-25 |
| PIT 判定 | ❌ 不用它 | ✅ **用它** |

```
Period End    = T
Publication   = T + N
→ 在 [T, T+N) 期间，该数据【不可用】
→ 只有 T+N 之后才可以
```

---

## 5. 各类输入的 PIT 要求

> **全部输入无一例外。**

| 输入 | PIT 要点 | 来源 |
|---|---|---|
| **Fund NAV** | NAV 日期 ≠ 披露日期 | `03-data` |
| **Factor** | 只能用 `available_at ≤ T` 的 Factor Result | `04-factor/08` |
| **Benchmark 序列** | 指数数据也可能修订 | `03-data` |
| **Benchmark Mapping** | 基金转型会改变基准 | `03-data/01-data-source` §5 |
| **Risk-free Rate** | **利率通常滞后发布** | `03-data` §3.1.5.2 |
| **MAR / Evaluation Policy** | 评价标准变更属版本前视，见 §7 | `05-fund-evaluation/01` §16 |
| **Fund Classification** | 分类调整有生效日与披露日 | `03-data` |
| **Peer Group 构成** | 必须是当时的组成员 | `05-fund-evaluation/01` §9.3 |
| **Fund Score / Rank / Tier** | **不得使用今天重算的历史值** | §8 |
| **Fund Universe** | 当时的池子 | `04-survivorship-bias` |
| **Expected Return / Risk / Σ / ρ** | 当时可产出的估计 | `07-return-risk/01` §8 |
| **Investment Eligibility** | 当时的可投资性状态 | `02-business-requirements` §18 |

### 5.1 Risk-free Rate 的滞后是一个真实约束

```
利率的 effective_at 与 available_at 之间常有间隔
    → 且利率会被事后修订（03-data §3.1.5.2）
    → T 时点的 Sharpe 必须用 T 时点可得的 R_f
```

**定案后新增的两个检测点**（`03-data/01-data-source` §3.1.5.5、`TBD-resolution.md` Policy ①）：

| # | 检测点 |
|---|---|
| 1 | **`R_f` 是序列不是标量** —— 窗口内逐期取值，且**全窗口统一以 `decision_at` 为 PIT 基准**。按各期自身日期做 PIT 过滤会让窗口早期取到旧修订、晚期取到新修订，是一类**看起来更严格实则错误**的实现（`04-factor/04-factor-calculation` §3.4.2） |
| 2 | **插值点同样受 PIT 约束** —— 事后补入真实观测产生新 `version` 而不覆盖插值行；回测在 `T` 时点应取到当时的插值版本，取到补入后的观测版本即前视（`11-database/04` §7.3.1） |

> **第 2 点是一类隐蔽的版本前视**：它不涉及"未来的数据"，而涉及"未来才补齐的数据质量"。与 §6 的版本前视同源。

### 5.2 派生量的 PIT 不是自动成立的 ⚠️

> **即使全部原始数据都满足 PIT，派生量仍可能前视。**

```
Factor 用 PIT 数据算出 → Factor 本身满足 PIT ✓
但 Factor Result 的 available_at 是【计算完成之后】
    → 若某期 Factor 在 T+2 才算完
    → T 时点不能使用它
```

**要求**：派生量必须有自己的 `available_at`，而非继承输入的（`04-factor/04-factor-calculation` §4.3）。

#### 5.2.1 派生量 `available_at` 的确定规则（v1.1 定案）

> **定案 · 2026-08-27**：`LB-2` 关闭。这是 `03-data/01-data-source` §11 的 `max(源头可得, 平台可用)` 在派生层的自然延伸。

```
派生量.available_at = max( 全部输入的 available_at , 计算完成时刻 )
```

**两项各自的必要性**：

| 项 | 少了会怎样 |
|---|---|
| **全部输入的 `available_at` 的最大值** | 输入中最晚可得的那一个决定了这个派生量最早何时**可能**被算出。忽略它 → 派生量看起来比它的输入还早可用，是**结构性前视** |
| **计算完成时刻** | 即使输入都齐了，计算本身要时间与调度。忽略它 → T 时点使用了 T+2 才算完的值 |

> **"批次可用时刻"不是第三个候选，而是"计算完成时刻"在批处理下的具体形态** —— 批量计算时，同批全部结果的计算完成时刻即批次落地时刻。原 `LB-2` 把二者列为互斥选项是不准确的。

**`availability_quality` 的传递规则**：

```
派生量.availability_quality = min( 全部输入的 availability_quality )
                              按 EXACT > DERIVED > INFERRED 排序
```

| # | 说明 |
|---|---|
| 1 | **取最弱一档而非最强** —— 一个 `INFERRED` 输入足以让整个派生量的时点不精确 |
| 2 | 若某输入的 quality 为 `DERIVED`，派生量继承 `DERIVED`，其残余前视风险随之传递 |
| 3 | **计算完成时刻本身始终是 `EXACT` 的**（平台自己的时钟），因此它不会拉低 quality，只可能推后 `available_at` |

> **一个反直觉的结论**：若某派生量的 `available_at` 由「计算完成时刻」决定（即计算完成晚于所有输入可得），它的 `availability_quality` **仍取决于输入**而非计算。因为 quality 回答的是「这个时点有多可信」，而这里可信的是**下界**（不早于输入可得）—— 输入的时点不准，派生量的时点下界就不准。

---

## 6. 版本前视 ⚠️

> **这是最隐蔽的一类前视 —— 它不涉及"未来的数据"，而涉及"未来的定义"。**（`04-factor/08-factor-output` §6.2 点名要求本域细化）

### 6.1 四种版本前视

| # | 版本前视 | 说明 |
|---|---|---|
| 1 | **Factor Version** | 用今天的公式重算历史因子 |
| 2 | **Evaluation / Scoring / Ranking / Classification Policy Version** | 用今天的评价标准解释历史评分 |
| 3 | **Portfolio Rule Version** | 用今天的约束与目标重解历史组合 |
| 4 | **Return Estimate / Risk Model Version** | 用今天的估计方法回溯历史 |

### 6.2 "用今天的公式测历史"与"当时的策略会怎样"是两回事

> **沿用 `04-factor/08-factor-output` §6.3：**

```
回测使用当前 Factor Version
    → 测的是"用今天的公式在历史上会怎样"
    → 不是"当时的策略会怎样"
```

**两者都有意义，但必须被区分并明确声明。**

### 6.3 本域的定义：两种回测模式

| 模式 | 使用的版本 | 回答的问题 | 用途 |
|---|---|---|---|
| **`HISTORICAL_FIDELITY`**（历史保真） | **当时生效的版本** | 当时的策略会怎样 | 复现历史决策、审计 |
| **`CURRENT_RULE`**（当前规则） | **今天的版本** | 用今天的规则在历史上会怎样 | 新策略验证、策略比较 |

### 6.4 两种模式的适用场景不同，不可互换 ⚠️

```
新策略上线前的验证
    → 必须用 CURRENT_RULE
    → 因为该策略在历史上根本不存在，没有"当时的版本"

复现某次历史决策 / 审计
    → 必须用 HISTORICAL_FIDELITY
    → 用今天的规则重算会得出与当时不同的结论

策略变更前后的对比
    → 两个版本【各跑一次 CURRENT_RULE】
    → 而非一个用历史版本、一个用当前版本
```

### 6.5 `CURRENT_RULE` 不是前视，但有它自己的问题

> **需要澄清一处容易混淆的地方。**

```
CURRENT_RULE 模式下用今天的规则测历史
  ✓ 不构成【数据】前视 —— 数据仍严格 PIT
  ✗ 但存在【规则设计】的前视：
      今天的规则是在看过这段历史之后设计的
      → 这正是 02-backtest-methodology §4 的 IS/OOS 要解决的问题
```

**因此**：`CURRENT_RULE` 模式的回测**必须配合 IS/OOS 划分**才有验证意义；单纯在全历史上跑一次今天的规则，结论不可信。

### 6.6 模式必须在配置中显式声明

```
backtest_mode = TBD
```

> 未声明模式的回测结果**无法解释** —— 读者无法判断它回答的是哪个问题。

> **已定案 · 2026-08-27**：默认模式 = **`HISTORICAL_FIDELITY`**（用当时的规则）。
>
> **依据 —— 两种模式回答的是不同问题**：
>
> | 模式 | 回答的问题 | 用途 |
> |---|---|---|
> | **`HISTORICAL_FIDELITY`** | 「当时这样做会怎样」 | **回测的默认目的** —— 评估策略在历史中的真实表现 |
> | `CURRENT_RULE` | 「如果一直用现在的规则会怎样」 | **专项分析** —— 评估规则变更本身的影响 |
>
> **`CURRENT_RULE` 用当前规则重算历史，本质上是一种版本前视**（§6）—— 它使用了历史时点上尚不存在的规则定义。这不意味着它错误，而是意味着**它的结论不能被解释为「历史表现」**。
>
> **两种模式的结果不可直接比较**，报告须显式标注所用模式（`08-backtest/06` 的必备字段）。混用会让「规则变更带来的差异」与「策略本身的表现」不可分离。

---

## 7. MAR 与 Evaluation Policy 的时点语义 ⚠️

> **这里有一处与其他输入不同的地方，容易出错。**

| | 走什么 | 判定 |
|---|---|---|
| **`Risk-free Rate`** | **PIT** | `available_at ≤ T` 的最大 version |
| **`MAR`** | **版本** | 当时生效的 `Evaluation Policy Version` |

（沿用上游 §5.5、`04-factor/04-factor-calculation` §3.4）

### 7.1 为什么 MAR 不走 PIT

> **PIT 回答"当时能拿到什么数据"，而 `MAR` 不是数据** —— 不存在"当时拿不到"的问题。它回答的是"当时我们用的是哪套评价标准"。

```
❌ 把 MAR 塞进 PIT 查询
   → 会让评价标准的变更表现为一次数据更新
   → 绕过版本治理
```

### 7.2 但两者在回测中的效果相同

> **无论走 PIT 还是走版本，回测都必须使用"当时的那个值"** —— 不得使用今天的 `MAR` 回溯历史。这属于 §6 的版本前视。

---

## 8. Fund Evaluation 的 PIT：不得使用今天重算的历史值 ⚠️

> **这是回测中最常见的前视之一。**

```
❌ 今天重新计算 2022 年的 Fund Rank，用于 2022 年的回测决策
   → 今天的重算使用了：
      · 今天的 Peer Group 构成（含 2022 后成立的基金？不含已清盘的？）
      · 今天的 Scoring Policy
      · 修订后的历史数据
   → 三重污染
```

### 8.1 正确做法：快照优先

> **沿用 `01-backtest-engine` §8.2 的快照优先原则。**

```
① 优先读取当时固化的 Score / Rank / Tier / Universe 快照
② 快照不存在且满足可重建条件（§8.3）→ 按 PIT 重建并标记
③ 不满足 → 中止
```

### 8.2 重建时的三重 PIT 要求

> 若必须重建，以下三项必须**同时**是当时的：

| # | 项 | 若用今天的会怎样 |
|---|---|---|
| 1 | **Peer Group 构成** | 分位全部错位（`05-fund-evaluation/01` §9.3） |
| 2 | **Scoring / Ranking / Classification Policy Version** | 评分口径不同（§6.1 第 2 项） |
| 3 | **数据版本**（修订前的） | 净值修订会改变因子值 |

> **缺任一项，重建结果就与当时不同 —— 而这种不同在结果中不可见。**

---

## 9. Fund Selection 的 PIT

```
❌ Fund A 在 2024 年成立，却出现在 2022 年的 Universe 中
```

> 详见 `04-survivorship-bias` §4 —— 基金必须满足 `成立日 ≤ T` 且 `T 时未终止`。

---

## 10. Portfolio Optimization 的 PIT

> **优化在 T 时只能使用 T 时点已产出的 `μ` / `σ` / `ρ` / `Σ`。**

| 要求 | 说明 |
|---|---|
| 估计的 `estimation_as_of_date ≤ T` | `07-return-risk/01` §8 |
| 估计已通过 Validation Gate | `07-return-risk/06` §10 |
| 估计未过新鲜度阈值 | `07-return-risk/01` §15 |
| 使用的 Portfolio Rule Version 是当时的（`HISTORICAL_FIDELITY` 模式） | §6 |

---

## 11. Rebalancing 的 PIT

> **调仓决策只能使用决策时点之前可得的数据。**

### 11.1 Drift 检测的一处微妙之处 ⚠️

```
Drift = |w_actual − w_target|

w_actual 依赖当日净值
    → 若用【当日收盘净值】计算 Drift 并【当日】决策调仓
    → 相当于用当天涨跌决定当天调仓
    → 与 01-backtest-engine §10.2 的成交前视是同一类问题
```

**正确处理**：Drift 检测使用 `available_at ≤ T` 的净值（通常是 `T−1`），调仓在其后执行。

---

## 12. 三个例子

### 12.1 例一：使用未来才披露的数据

```
基金规模数据
  effective_at  = 2022-06-30（半年报期末）
  available_at  = 2022-08-28（半年报披露）

回测决策日 = 2022-07-15
  ❌ 用 6-30 的规模筛选 → 前视：当时规模数据尚未披露
  ✅ 用 2021 年报（已披露）的规模
```

**影响**：规模是 Universe 准入条件之一（`02-business-requirements` §17.4）。用未披露的规模会让回测提前排除掉后来缩水的基金。

### 12.2 例二：使用今天重算的历史 Fund Rank

```
回测决策日 = 2022-03-31
  ❌ 今天用当前 Peer Group 与当前 Scoring Policy 重算 2022-03-31 的 Rank
     → Peer Group 中缺少 2022 年后清盘的基金（幸存者偏差）
     → Scoring Policy 是 2026 年的版本（版本前视）
     → 数据是修订后的（数据前视）
  ✅ 读取 2022-03-31 当时固化的 Score / Rank 快照
```

**影响**：这是**三种偏差叠加**的典型场景，且三者都不可见。

### 12.3 例三：使用未来修订后的 Fund Classification

```
Fund A
  2022-01：分类 = 偏债混合型
  2023-06：基金转型 → 分类改为 偏股混合型（effective_at = 2023-06-01）

回测决策日 = 2022-05-01
  ❌ 用今天的分类（偏股混合型）
     → Peer Group 归组错误
     → Benchmark Mapping 错误 → Alpha / Beta / TE 全错
     → Asset Class 归属错误 → 类别配置约束错误
  ✅ 用 2022-05-01 当时的分类（偏债混合型）
```

**影响**：分类是 Peer Group、Benchmark Mapping、Asset Class 三条链路的共同源头，一处错则三处全错。

---

## 13. Detection

### 13.1 基础检测规则

```
对每一个进入决策的输入：
    assert input.available_at ≤ decision_at
否则 → FAIL
```

### 13.2 基础规则不足以覆盖版本前视 ⚠️

> **版本没有 `available_at`。**

```
Scoring Policy v3 生效于 2024-01
回测决策日 = 2022-05

Policy 本身不是"数据"，它没有 available_at 字段
    → 基础规则检测不到这个前视
```

**补充规则**：

```
对每一个使用的 Policy / Method Version：
    assert version.effective_from ≤ decision_at ≤ (version.effective_to or ∞)
    —— 仅在 HISTORICAL_FIDELITY 模式下强制
否则 → FAIL
```

### 13.3 三层检测

| 层 | 检测对象 | 规则 |
|---|---|---|
| **① 数据层** | 全部数据输入 | `available_at ≤ decision_at` |
| **② 版本层** | 全部 Policy / Method Version | §13.2（`HISTORICAL_FIDELITY` 模式） |
| **③ 派生层** | Factor / Score / Universe / Estimate | 其自身的 `available_at`，而非输入的（§5.2） |

### 13.4 检测必须在数据访问层强制，不能靠自觉 ⚠️

> **沿用架构 §11.7：PIT-aware Data Access Interface 强制过滤，领域服务无法绕过。**

```
❌ 由各领域逻辑自行检查 available_at
   → 任何一处遗漏就形成前视
   → 且遗漏之处无法被发现

✅ 由数据访问层统一过滤
   → 领域逻辑拿到的【本来就只有】合格数据
   → 没有绕过的可能
```

**这是"机制防范"与"事后检查"的区别** —— 前视看不出来，因此必须靠机制。

---

## 14. Audit

> **每个 Backtest Decision 必须记录：**

| 字段 | 说明 |
|---|---|
| **`decision_date`** | 决策时点 |
| **逐输入的 `effective_at`** | 数据描述的时点 |
| **逐输入的 `available_at`** | 数据可用的时点 |
| **逐输入的 `version`** | 所取的数据版本 |
| **全部 Policy / Method Version** | 版本层审计 |
| **`backtest_mode`** | `HISTORICAL_FIDELITY` / `CURRENT_RULE`（§6.3） |
| **快照 or 重建标记** | `01-backtest-engine` §8.4 |

### 14.1 只记录 `decision_date` 与结果是不够的

> 没有逐输入的 `available_at`，就无法事后验证该次决策是否满足 PIT —— 而这正是审计要回答的问题。

---

## 15. Failure Handling

### 15.1 检测到违规必须阻断

```
若 available_at > decision_at：
    ① 拒绝该输入
    ② 标记该次回测为 INVALID
    ③ 记录违规明细（哪个输入、差多少天）
```

> **不得静默继续。**

### 15.2 为什么整个回测都要标 `INVALID`，而不只是该期

> **前视会沿时间轴传导。**

```
T 期用了未来数据 → T 期组合被污染
    → T 期的持仓成为 T+1 期的 Current Weights
    → T+1 期的 Drift、换手、成本全部受影响
    → 污染沿整条净值曲线传导
```

**因此单期的前视违规使整个回测结果不可用**，不能只丢弃该期。

### 15.3 `INVALID` 的回测不得用于策略比较

> 沿用 `06-backtest-report` §13：`INVALID` 结果不得作为决策依据（上游 §4.2 ⑧ 关键约束）。

---

## 16. Input / Output

### 16.1 Input

| 输入 | 来源 |
|---|---|
| 每期的全部决策输入及其时点元数据 | `01-backtest-engine` |
| 使用的全部 Policy / Method Version | 各域 |
| `backtest_mode` | Backtest Configuration |

### 16.2 Output

| 输出 | 说明 |
|---|---|
| **`look_ahead_check_status`** | `PASS` / `FAIL` |
| **违规明细** | 期次、输入项、`available_at`、`decision_at`、差值 |
| **逐期的时点审计记录** | §14 |
| `mode_declaration` | 本次回测的模式声明 |

---

## 17. Edge Cases

| 情形 | 处理 |
|---|---|
| 某输入无 `available_at` 字段 | **视为不可用** —— 不得假设等于 `effective_at` |
| `available_at` 恰好等于 `decision_at` | **通过** —— 判定是 `≤` |
| 数据在决策后被修订 | 使用当时的 version；修订版本不参与该期 |
| 派生量的 `available_at` 晚于其输入 | **正常** —— 计算需要时间（§5.2） |
| `CURRENT_RULE` 模式 | 版本层检测**不适用**，但数据层检测仍强制 |
| Policy 的 `effective_to` 为空 | 视为仍生效 |
| 某期无任何输入违规但结果异常好 | 不构成前视证据，但值得核查是否有未被检测的路径 |

### 17.1 无 `available_at` 的数据必须视为不可用 ⚠️

```
❌ 该字段缺失 → 退而用 effective_at 判断
   → 这恰好是 §3 明令禁止的做法
   → 且缺失往往发生在最需要它的数据上（如公告类）
```

---

## 18. Reproducibility

```
逐期的输入时点元数据（effective_at / available_at / version）
+ 使用的全部 Policy / Method Version
+ backtest_mode
+ Detection Rule Version
        ↓
    相同的检测结论
```

### 18.1 检测结论依赖 `available_at` 的确定规则（v1.1 定案）

> **上游 `TBD-17` 已于 2026-08-27 定案**（`01-product-overview` v2.6、`03-data/01-data-source` §11、`TBD-resolution.md` Policy ④）。

**定案内容**：`available_at = max(源头可得时刻, 平台可用时刻)`，源头侧按 `provider_available_at → published_at → ingested_at` 三级优先级解析，并落库 `availability_quality`（`EXACT` / `DERIVED` / `INFERRED`）。

```
同一份数据，按不同口径确定 available_at
    → 同一次回测可能一次 PASS 一次 FAIL
```

该风险**不因定案而消失** —— 规则统一了，但数据源能力差异仍使同一批数据落在不同 quality 档。因此两条要求保留并强化：

| # | 要求 |
|---|---|
| 1 | **`available_at` 的确定规则本身必须版本化**，检测结论须记录所依据的规则版本 |
| 2 | **检测结论须按 `availability_quality` 分层呈现**（见 §18.1.1） |

#### 18.1.1 检测结论必须区分三档 quality

> **`PASS` 的含金量取决于 `available_at` 的可信度。**

| Quality | 对检测结论的意义 |
|---|---|
| **`EXACT`** | `PASS` 可信 —— 时点是精确的 |
| **`DERIVED`** | `PASS` **存在残余风险** —— 用的是公告时间，未计入公告到推送的延迟，**方向上偏前视** |
| **`INFERRED`** | `PASS` 可信但**偏保守** —— 用的是落库时间，方向上不会前视 |

**因此检测报告必须给出三档的占比**，而非只给一个总体 `PASS` / `FAIL`：

```
point_in_time_check:
    result           = PASS
    exact_ratio      = 0.62
    derived_ratio    = 0.31   ← 这 31% 的 PASS 含残余前视风险
    inferred_ratio   = 0.07
```

> **`DERIVED` 占比高时的处置**：日频决策场景下公告到推送的分钟级延迟可忽略，`PASS` 依然成立；**盘中决策场景下必须逐类复核**。这一分界由决策频率决定，不由检测器判断。

> **已定案 · 2026-08-27**：`INFERRED` 占比 **> 30% 降级 `WARNING`**、**> 60% 降级 `NOT_VERIFIED`**（`03-data/01-data-source` §3.1.5.5 定义，与 `08-backtest/01` `BE-3` 的重建期占比同档）。
>
> **`INFERRED` 的偏差方向是安全的**（用落库时刻，保守，不会前视），因此门槛可比 `DERIVED` 宽松；`DERIVED` 的方向偏前视，但在日频决策下风险可忽略，故不单设降级阈值，只在分层呈现中暴露占比。

### 18.2 检测记录必须不可变

> 若逐期的时点元数据被后续数据修订覆盖，历史检测结论无法复现 —— 与 `01-backtest-engine` §22.1 的快照问题同源。

---

## 19. Summary

**前视偏差在净值曲线上完全看不出来** —— 它只是让结果更好看，没有任何异常可供察觉。因此只能靠**机制**防范，不能靠事后观察。

三条判定要点：

- **用 `available_at` 而非 `effective_at`** —— 基金数据中生效日早于披露日是常态而非例外，按生效日筛选会**稳定地**使用当时不可能知道的信息
- **无 `available_at` 的数据必须视为不可用** —— 退而用 `effective_at` 恰是被禁止的做法，且缺失往往发生在最需要它的数据上
- **派生量的 PIT 不自动成立** —— 即使输入全部合格，Factor Result 的 `available_at` 是计算完成之后，须有自己的时点

本域新增的一层：**版本前视**（`04-factor/08` 点名要求细化）

- 它不涉及"未来的数据"而涉及"未来的定义"，**基础的 `available_at` 检测覆盖不到** —— Policy 没有 `available_at` 字段
- 因此定义两种模式：**`HISTORICAL_FIDELITY`**（当时的版本，用于复现与审计）与 **`CURRENT_RULE`**（今天的版本，用于新策略验证）
- **`CURRENT_RULE` 不构成数据前视，但存在规则设计前视** —— 今天的规则是看过这段历史之后设计的，因此必须配合 IS/OOS 才有验证意义

两处执行要求：

- **检测必须在数据访问层强制** —— 靠各领域逻辑自觉检查，任何一处遗漏就形成前视，且遗漏之处无法被发现
- **单期违规使整个回测 `INVALID`** —— 前视会沿时间轴传导：污染的持仓成为下期的起点，影响此后全部的 Drift、换手与成本

---

## 20. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | 判定用 `available_at`，**不用 `effective_at`** | 上游 §4.2 ①-PIT |
| D-2 | 同一时点多版本取 `version` 最大者 | 即"当时能看到的最新版本" |
| D-3 | **无 `available_at` 的数据视为不可用** | 退用 `effective_at` 是被禁止的做法 |
| D-4 | **派生量必须有自己的 `available_at`** | 计算需要时间 |
| D-5 | **定义两种回测模式** | 区分"当时的策略会怎样"与"用今天的规则会怎样" |
| D-6 | **模式必须显式声明** | 否则结果无法解释 |
| D-7 | `CURRENT_RULE` 必须配合 IS/OOS | 它存在规则设计前视 |
| D-8 | **`MAR` 走版本而非 PIT，但同样不得用今天的值** | 上游 §5.5 |
| D-9 | Fund Score / Rank **快照优先，重建须三重 PIT** | 重建缺任一项则与当时不同且不可见 |
| D-10 | Drift 检测须用 `available_at ≤ T` 的净值 | 否则用当天涨跌决定当天调仓 |
| D-11 | **检测三层：数据层 + 版本层 + 派生层** | 基础规则覆盖不到版本前视 |
| D-12 | **检测在数据访问层强制** | 自觉检查必然遗漏且遗漏不可发现 |
| D-13 | **单期违规使整个回测 `INVALID`** | 前视沿时间轴传导 |

---

## 21. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 全部输入必须满足 `available_at ≤ decision_at` | 上游 §4.2 ①-PIT |
| C-2 | 适用范围为**全部派生量与全部映射关系** | `02-business-requirements` §26.1 |
| C-3 | PIT 由数据访问层强制，领域逻辑无法绕过 | 架构 §11.7 |
| C-4 | 检测到违规必须阻断，**不得静默继续** | 本文档 §15.1 |
| C-5 | `INVALID` 的回测不得作为决策依据 | 上游 §4.2 ⑧ |
| C-6 | 回测报告必须显式声明前视处理方式 | `02-business-requirements` §26.4 |
| C-7 | 不得使用今天重算的历史 Score / Rank / Classification | 本文档 §8 |

---

## 22. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~LB-1~~ | ~~各类回测场景的默认模式（`HISTORICAL_FIDELITY` / `CURRENT_RULE`）~~ —— **已定案**：默认模式 = `HISTORICAL_FIDELITY`（用当时的规则） | — | ✅ 2026-08-27 |
| ~~LB-2~~ | ~~派生量 `available_at` 的确定规则~~ —— **已定案**：`max(全部输入的 available_at, 计算完成时刻)`，quality 取输入中最弱一档（§5.2.1） | — | ✅ 已定案 2026-08-27 |
| LB-3 | 前视违规的告警与上报流程 | 运维 | 运维 + 治理 |

> **原上游遗留 `<TBD-17>` 已于 2026-08-27 定案**（`01-product-overview` v2.6）：四时间字段同时建模、三级优先级解析、落库 `availability_quality`。本域检测据此可执行，且检测报告须按三档 quality 分层呈现（§18.1.1）。

---

## 23. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ①-PIT）、`02-business-requirements.md` v2.3（§26.1） |
| **架构** | `02-architecture/01-system-architecture.md` v2.2（§7.4 PIT-aware Data Access、§11.7 偏差防护点） |
| **本域** | `01-backtest-engine`（快照优先、执行价格前视）、`04-survivorship-bias`（另一类偏差）、`06-backtest-report`（Bias Check 呈现） |
| **数据** | `03-data/04-data-versioning`（三元时点与 PIT Query）、`03-data/01-data-source` §11（`available_at` 定义） |
| **被检查的域** | `04-factor/08` §6（版本前视的来源）、`05-fund-evaluation/01` §9、`07-return-risk/01` §8 |

---

## 24. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.3** | 2026-08-27 | **第二批定案（1 项）**。`LB-1` 默认模式 = **`HISTORICAL_FIDELITY`** —— `CURRENT_RULE` 用当前规则重算历史本质上是一种版本前视，其结论不能被解释为「历史表现」；两种模式的结果不可直接比较，报告须显式标注。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.2** | 2026-08-27 | **Policy ① 同步**。§5.1 补两个检测点 —— `R_f` 是序列且**全窗口统一以 `decision_at` 为 PIT 基准**（按各期自身日期过滤是看起来更严格实则错误的实现）；插值点同样受 PIT 约束，取到事后补入的观测版本即**版本前视**。详见 `TBD-resolution.md` Policy ① | `04-factor/04-factor-calculation` v1.2、`11-database/04` v1.5 |
| **v1.1** | 2026-08-27 | **上游 `TBD-17` 与本域 `LB-2` 一并关闭**。①新增 §5.2.1 —— 派生量 `available_at = max(全部输入的 available_at, 计算完成时刻)`，`availability_quality` 取输入中**最弱**一档；澄清原 `LB-2` 把「计算完成时刻」与「批次可用时刻」列为互斥选项是不准确的（后者是前者在批处理下的形态）。②§18.1 改写并新增 §18.1.1 —— 检测报告须按三档 quality 分层呈现，`DERIVED` 的 `PASS` 含残余前视风险（方向上偏前视），`INFERRED` 的 `PASS` 偏保守。详见 `TBD-resolution.md` Policy ④ | `03-data/01-data-source` v2.3、`01-product-overview` v2.6 |
| v1.0 | 2026-08-26 | 初始版本。**§1.2 前视在净值曲线上不可见**，只能靠机制防范；§3 判定用 `available_at` 及"生效日早于披露日是常态"；**§5.2 派生量的 PIT 不自动成立**；**§6 落实 `04-factor/08` 点名的版本前视细化**——定义 `HISTORICAL_FIDELITY` 与 `CURRENT_RULE` 两种模式及其不可互换的适用场景，并澄清 **§6.5 `CURRENT_RULE` 不是数据前视但存在规则设计前视**；**§7 `MAR` 走版本而非 PIT** 但同样不得用今天的值；**§8.2 重建历史评分的三重 PIT 要求**；**§11.1 Drift 检测的成交前视**；**§13.2 基础检测覆盖不到版本前视**，故设三层检测；**§13.4 检测必须在数据访问层强制**；**§15.2 单期违规使整个回测 `INVALID`** 的传导机制；**§17.1 无 `available_at` 的数据必须视为不可用** | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`02-architecture/01-system-architecture.md` v2.2 |