# 基金分层 · Fund Tier Classification

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：③ Fund Score 派生链的 `Fund Tier`
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§16.3、§16.4
> 本域上游：docs/05-fund-evaluation/03-fund-ranking.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **完成评价的基金如何被划入评价档次？**

### 1.2 ⚠️ 命名澄清：本文档定义的是 `Fund Tier`，不是 `Fund Classification`

> **这是本文档最重要的一条前置说明。文件名 `04-fund-classification.md` 与上游概念 `Fund Classification` 撞名，两者完全不是一回事。**

| | **`Fund Classification`** | **`Fund Tier`**（本文档） |
|---|---|---|
| 回答 | 这是一只**什么类型**的基金 | 这只基金**评价得怎么样** |
| 取值 | 股票型 / 债券型 / 混合型 … | **A+ / A / B / C / D** |
| 性质 | **客观属性**（基金合同决定） | **评价结论**（由 Score 派生） |
| 归属 | **`03-data`** 的数据实体 | **本域** |
| 是否依赖 Score | **绝不** —— 它是 `Peer Group` 的构建依据 | **完全依赖** |
| 变更来源 | 基金转型 | 评分或组内分布变化 |

> **混淆两者的后果**：若把 `Fund Tier` 当作 `Fund Classification` 用于构建 `Peer Group`，将直接形成 `Score → Tier → Peer Group → Score` 的循环依赖——正是上游 §7.2 明令禁止的错误。

**本文档全文使用上游术语 `Fund Tier`。** 文件名保持 `04-fund-classification.md` 以与目录约定一致。

### 1.3 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 基金类型分类 | `03-data/02-data-domain-model` |
| Score 如何合成 | `02-fund-scoring` |
| Rank / Percentile 如何计算 | `03-fund-ranking` |
| 候选池筛选 | `05-fund-selection` |

---

## 2. Classification Objective

| # | 目的 |
|---|---|
| 1 | 把连续的分位压缩为**少数几个可沟通的档次** |
| 2 | 快速发现优秀基金 |
| 3 | 快速排除弱势基金 |
| 4 | 作为 `Eligibility Rules` 的**可选**输入 |
| 5 | 支持组合角色划分 |

### 2.1 分层不等于投资建议

> **`A+` 不意味着"应该买"，`D` 也不意味着"应该卖"**（`02-business-requirements` §16.4、§27.4）。

分层是**评价结论**，投资决策还需经过 `Eligibility Rules`、组合构建、优化与 PM Review。

---

## 3. 派生链中的位置

```
Fund Score
    ↓  在 Peer Group 内排序
Peer Group Ranking
    ↓  转换为分位
Percentile
    ↓  按阈值分层
Fund Tier
```

> **四者是同一条派生链上的不同表示，不是四个独立概念**（`02-business-requirements` §16.1）。任一环节的输入变化会沿链传导——Score 变、组构成变、甚至只是某只基金的指标从 `UNAVAILABLE` 变为可得，都可能改变 Tier。

---

## 4. Classification Inputs

| 输入 | 是否必需 | 说明 |
|---|---|---|
| **`percentile`** | ✅ **必需** | 第一阶段的唯一分层依据 |
| `rank` + `n_effective` | ✅ | 用于校验与展示 |
| `total_score` | ✅ | 随 Tier 一同呈现 |
| `peer_group_id` + `version` | ✅ | 分层上下文 |
| `data_completeness` | ✅ | 可信度 |
| 组内绝对水平指标 | ✅ | 见 §7 强制缓解措施 |

---

## 5. Classification Method

> **第一阶段采用 Rule-based Classification。**

| # | 约束 |
|---|---|
| 1 | **不引入 AI / ML** —— 上游 §6.2.1、§9 原则十至十一 |
| 2 | **必须确定性** —— 相同 Percentile 必须得到相同 Tier |
| 3 | **阈值配置化，严禁硬编码**（`02-business-requirements` §16.3） |

---

## 6. Tier 定义与阈值（已定案）

### 6.1 五档

> **沿用 `02-business-requirements` §16.3.1（已定案 · 2026-08-25），本域不得改动。**

| Tier | 分位区间 | 含义 |
|---|---|---|
| **A+** | 前 5% | Excellent |
| **A** | 5% – 20% | Very Good |
| **B** | 20% – 50% | Good |
| **C** | 50% – 80% | Neutral |
| **D** | 后 20% | Weak |

> **提示词建议的 `Excellent / Good / Average / Weak` 四档不采用** —— 上游已定案五档且命名固定为 `A+ / A / B / C / D`，英文含义作为注释保留。

### 6.2 按分位分层，不按绝对分数

> **这是已定案的结构性决策**（`02-business-requirements` §16.3.1）。

**为什么不按绝对分数分层**：

```
Fund Score 本身就是各 Factor 在 Peer Group 内做分位标准化后合成的
    → 它已经是相对量
    → 在相对量上再切绝对阈值，切出来仍然是分位
    → 只是把这一事实隐藏起来
    → 并引入各层人数随组内分布漂移的副作用
```

### 6.3 分层阈值不是 TBD

> 提示词将 Classification Threshold 列为待定。**上游已定案为分位 5 / 20 / 50 / 80**，本域沿用，不标 TBD。

---

## 7. 已知局限与强制缓解措施

### 7.1 局限

> **分位分层意味着无论该 `Peer Group` 整体质量如何，永远有 5% 被评为 `A+`。**

一个整体表现糟糕的组，其 `A+` 基金可能绝对水平仍然很差。

### 7.2 强制缓解措施

> **缓解手段不在分层规则内，而是展示层的强制要求**（`02-business-requirements` §16.3.1）：

```
Fund Tier 必须与该 Peer Group 的绝对水平同屏展示
    至少包含：组内 Sharpe 中位数、组内 Maximum Drawdown 中位数
```

> **仅展示 Tier 而不展示组内绝对水平，视为违反本条。**

这使读者能判断"`A+` 在这一组意味着什么"。

### 7.3 绝对门槛是 P1 项

> 若后续需要绝对门槛（未达标者不得进入 `A+`/`A`），作为 P1 追加，**不改变分位分层的基础方案**。

> **已定案 · 2026-08-27**：第一阶段**不为 A+/A 追加绝对门槛**。
>
> **依据 —— 会破坏跨期可比**：
>
> ```
> Tier 是【相对】分层（上游已定 5/20/50/80 分位）
>
> 叠加绝对门槛（如「A+ 还须 Sharpe > 1.5」）
>     → 熊市中全组 Sharpe 普遍低于 1.5
>     → A+ 档【空缺】，而组内相对最优的基金仍然存在
>     → 同一只基金在不同市场环境下的 Tier 变化，反映的是市场而非它自己
> ```
>
> **绝对门槛的需求是真实的** —— 「分位第一但绝对表现很差」确实值得提示。但它应由**展示层的补充标注**承担（如「本组整体表现低于历史中位」），而不是改变 Tier 的定义。
>
> **保留为 P1 项**：若将来确需，须一并解决「绝对门槛在不同资产类别间如何设定」（债券型与股票型的 Sharpe 不可比）与「门槛本身是否随时间调整」两个问题。

---

## 8. Boundary Rules

### 8.1 边界必须无歧义

> **每个 Tier 的边界必须明确使用 `>=` / `>` / `<=` / `<`，不得留有歧义。**

### 8.2 本项目采用的边界约定

> 采用**上闭下开**（对分位而言即"高分位端闭合"），使每个分位值恰好落入一个 Tier：

| Tier | 边界条件 |
|---|---|
| **A+** | `percentile >= 95` |
| **A** | `80 <= percentile < 95` |
| **B** | `50 <= percentile < 80` |
| **C** | `20 <= percentile < 50` |
| **D** | `percentile < 20` |

### 8.3 分位区间与阈值的对应关系

> **§6.1 的"前 5%"对应 `percentile >= 95`** —— 因为本项目的 Percentile 约定是**越优越高**（`03-fund-ranking` §7.1）。

```
前 5%      →  percentile ∈ [95, 100]
5% – 20%   →  percentile ∈ [80, 95)
20% – 50%  →  percentile ∈ [50, 80)
50% – 80%  →  percentile ∈ [20, 50)
后 20%     →  percentile ∈ [0, 20)
```

> **这是一处极易出错的换算** —— "前 5%"在 Rank 语义下是小序号，在 Percentile 语义下是大数值。两种表述必须能互相校验。

### 8.4 边界校验

| 校验 | 要求 |
|---|---|
| **完备性** | 五个区间必须覆盖 `[0, 100]` 全部取值，无空隙 |
| **互斥性** | 任一 percentile 值只能落入一个 Tier |
| **单调性** | percentile 越高，Tier 越优 |

### 8.5 小样本下的边界失真

> **组规模很小时，分位阈值会失去意义。**

```
N = 10 只基金
"前 5%" → 0.5 只
    → 实际要么 1 只（占 10%）要么 0 只
    → A+ 档要么超配要么空缺
```

**定案 · 2026-08-27**：`TBD-FC-2` 关闭 —— **`n_effective < 30` 时不产出 Tier**。见 `02-business-requirements` §7.3.1、`TBD-resolution.md` Policy ⑤。

| 输出字段 | 值 |
|---|---|
| `tier` | `null` |
| `n_effective` | 实际值 |
| **`classification_status`** | **`INSUFFICIENT_SAMPLE`** |

#### 8.5.1 为什么选「不产出」而非「低置信标记」

> **两个候选在本节的场景下不等价。**

| 方案 | 问题 |
|---|---|
| 低置信标记 | Tier 值仍存在，**下游会照常使用它** —— 进入 Universe 筛选条件、进入组合构建的分层约束。标记只在展示层可见，而消费 Tier 的是代码不是人 |
| **不产出**（已采纳） | 强制下游显式处理 `null`，无法「不小心用上」 |

> **Tier 与 Percentile 的不同之处**：Percentile 是连续值，小样本下它「不准」但仍单调；**Tier 是离散档位，小样本下它会跳档**。`N = 10` 时「前 5%」落在 0.5 只上，A+ 档要么占 10% 要么空缺 —— 同一只基金在 `N = 10` 和 `N = 11` 下可能从 A+ 掉到 A，而其表现毫无变化。这种不连续性无法用「低置信」表达。

> **判定基数沿用 `n_effective`**（`03-fund-ranking` §6.2）—— Tier 基于 Percentile，Percentile 不可得则 Tier 不可得，两者的 `INSUFFICIENT_SAMPLE` 必然同时出现。

---

## 9. Classification Result

| 字段 | 说明 |
|---|---|
| `fund_id` / `evaluation_period` / `as_of_date` | 标识 |
| **`fund_tier`** | `A+` / `A` / `B` / `C` / `D` |
| `total_score` | 随 Tier 呈现 |
| `percentile` | 分层依据 |
| `rank` + `n_effective` | 序位与有效参与数 |
| `peer_group_id` + `peer_group_version` | 分层上下文 |
| **组内绝对水平**（Sharpe 中位数、MDD 中位数） | **§7.2 强制要求** |
| `data_completeness` | 可信度 |
| `confidence_flag` | 小样本标记 |
| **`classification_policy_version`** | 政策版本 |

### 9.1 Tier 不得单独输出

> **`fund_tier` 必须与 `percentile`、`total_score`、组内绝对水平一同输出。** 单独的 `"A+"` 是不可解释的。

---

## 10. Classification Policy

| 字段 | 说明 |
|---|---|
| `policy_id` | 标识 |
| `version` | 版本号 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`tier_definitions`** | 五档及其分位区间 |
| **`boundary_convention`** | 边界符号约定（§8.2） |
| **`threshold_basis`** | `PERCENTILE`（第一阶段固定） |
| `minimum_peer_group_size` | 小样本阈值 |
| `small_sample_handling` | 小样本处理方式 |
| `absolute_floor`（P1 预留） | A+/A 的绝对门槛，第一阶段为空 |

### 10.1 阈值方式必须显式声明

> `02-business-requirements` §16.3 要求"须声明按绝对分数还是按分位分层"。`threshold_basis` 字段承担此职责，第一阶段固定为 `PERCENTILE`。

---

## 11. Classification Stability

### 11.1 Policy 变更不覆盖历史

```
Policy V1 产出的历史 Tier  →  保持不变
Policy V2 产出的新 Tier    →  以新版本号记录
```

历史结果必须保持可追溯，两者通过 `classification_policy_version` 区分。

### 11.2 Tier 的天然不稳定性

> **即使 Policy 完全不变、基金自身完全不变，Tier 仍可能变化。**

| 来源 | 说明 |
|---|---|
| **同组其他基金变化** | 别人变好，自己相对下滑 |
| **Peer Group 构成变化** | 新基金成立、老基金清盘、分类调整 |
| **某指标从 `UNAVAILABLE` 变为可得** | `n_effective` 变化 → Percentile 变化 |
| **边界附近的微小波动** | `percentile = 94.9` 与 `95.1` 分属不同 Tier |

### 11.3 边界抖动

> **紧邻阈值的基金会在相邻 Tier 之间频繁跳动**，这不代表基金质量发生了实质变化。

```
2026-07：percentile = 95.2  →  A+
2026-08：percentile = 94.8  →  A
```

**第一阶段不引入平滑机制**（如缓冲区、最小停留期）——它会引入路径依赖，使 Tier 不再由当期数据唯一确定，破坏可复现性。

**替代做法**：展示层同时呈现 `percentile` 数值，使读者看到 `94.8` 与 `95.2` 的实质接近。

> **推荐默认 · 2026-08-27**：提供「接近上一档」提示 —— 距上档阈值 **< 2 个百分点**时标注。产品方可改。
>
> **依据**：Tier 是离散档位，边界附近的基金与相邻档的实质差异很小。不提示会让使用者误以为 A 与 B 之间存在实质鸿沟。
>
> **纯展示层增强，不影响 Tier 值本身** —— 该标记不落库为 Tier 的一部分，不进入 Universe 筛选条件，不参与任何计算。这一点须在实现中明确，否则「接近 A」会逐渐被当作一个新的档位使用。

### 11.4 Tier 变动监控

> 业务上需要能回答：本期哪些基金升档/降档、原因是自身变化还是组内变化。

沿用 §11.2 的三个来源做归因，**不得只报告"Tier 从 A 变为 B"**。

---

## 12. Input / Process / Output

### 12.1 Process

```
① 取 Ranking Output（percentile、rank、n_effective）
② 若 percentile = UNAVAILABLE → 该基金无 Tier
③ 若 n_effective < minimum_peer_group_size → 按小样本规则处理
④ 按 Classification Policy 的分位区间与边界约定判定 Tier
⑤ 取该 Peer Group 的组内绝对水平指标（Sharpe 中位数、MDD 中位数）
⑥ 落库：Tier + percentile + score + 组内绝对水平 + 版本引用
```

---

## 13. Edge Cases

| 情形 | 处理 |
|---|---|
| `percentile = UNAVAILABLE`（N=1 或指标不可得） | **无 Tier**，不得默认为最低档 |
| `n_effective < 30` | **不产出 Tier**，`classification_status = INSUFFICIENT_SAMPLE`（§8.5） |
| `percentile` 恰好等于阈值（如 95.0） | 按 §8.2 的 `>=` 约定归入较优档（`A+`） |
| 全组分数相同 | 全部基金 percentile 相同 → 全部落入同一 Tier，**这是正确结果** |
| 基金在评价期内转型 | 用当时分类归组；转型前后的 Tier 不可直接比较 |
| `evaluation_status = PARTIAL` | 可产出 Tier，但 `data_completeness` 必须同屏呈现 |

### 13.1 `UNAVAILABLE` 不得默认为最低档

> 与 `02-fund-scoring` §9.1 同一条原则——把"没有分位"当作"分位最低"，等于宣称"数据不足 = 表现最差"。

---

## 14. 示例

```
Fund A ｜ as_of = 2026-08-24 ｜ Period = 1Y
Peer Group        = 主动股票型 · v3（Size = 200，N_effective = 120）

Total Score       = X / 100
Rank              = 5 / 120
Percentile        = 96.6%

→ 96.6 >= 95  →  Fund Tier = A+

【强制同屏展示】
组内 Sharpe 中位数        = X
组内 Max Drawdown 中位数  = X%
Data Completeness         = X / X
```

> 若组内 Sharpe 中位数很低，读者能立即判断"这一组整体不强，`A+` 的绝对水平有限"。这正是 §7.2 强制措施的目的。

---

## 15. Summary

分层是**归类**环节，把连续分位压缩为五档 `A+ / A / B / C / D`。

一条必须先澄清的命名冲突：

- **本文档定义的是 `Fund Tier`，不是上游的 `Fund Classification`** —— 后者是基金类型（`03-data` 的客观属性，`Peer Group` 的构建依据）。混淆两者会形成 `Score → Tier → Peer Group → Score` 的循环依赖

三条已定案、本域不得改动的内容：

- **五档 + 分位 5/20/50/80** —— 且**按分位而非绝对分数**分层，因为 Score 本身已是相对量
- **`Fund Tier` 必须与组内绝对水平同屏展示** —— 仅展示 Tier 视为违规；这是分位分层"永远有 5% 是 A+"这一局限的强制缓解措施
- **分层不等于投资建议**

两处容易出错的技术细节：

- **"前 5%"对应 `percentile >= 95`** —— Rank 语义下是小序号，Percentile 语义下是大数值，两种表述必须能互相校验
- **Tier 会在基金自身完全不变时改变** —— 组内他人变化、组构成变化、`n_effective` 变化都会传导

---

## 16. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **本文档定义 `Fund Tier`，与上游 `Fund Classification` 严格区分** | 撞名会导致循环依赖 |
| D-2 | 采用上游五档 `A+/A/B/C/D`，**不采用提示词的四档命名** | 上游已定案且命名固定 |
| D-3 | **按分位分层，不按绝对分数** | Score 已是相对量，切绝对阈值只是隐藏这一事实 |
| D-4 | 分层阈值**不标 TBD** | 上游已定案 5/20/50/80 |
| D-5 | 边界采用高分位端闭合（`>=`） | 保证完备性与互斥性 |
| D-6 | **Tier 不得单独输出**，须与 percentile、score、组内绝对水平同屏 | 单独的 "A+" 不可解释 |
| D-7 | **第一阶段不引入 Tier 平滑机制** | 平滑引入路径依赖，破坏"当期数据唯一确定结果"的可复现性 |
| D-8 | `percentile = UNAVAILABLE` 时无 Tier，**不默认最低档** | 与"缺失不得转 0"同一原则 |
| D-9 | 全组分数相同导致全部同档，视为**正确结果** | 分位分层的正常表现 |
| D-10 | Tier 变动必须归因到三个来源 | 只报"A 变 B"无法判断是否需要行动 |

---

## 17. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 分层阈值配置化，**严禁硬编码** | `02-business-requirements` §16.3 |
| C-2 | 分层必须在 `Peer Group` 内，与排名同一样本集 | `02-business-requirements` §16.3 |
| C-3 | **`Fund Tier` 必须与组内绝对水平同屏展示**，否则视为违规 | `02-business-requirements` §16.3.1 |
| C-4 | 分层必须记录当时的阈值配置版本 | `02-business-requirements` §16.3 |
| C-5 | **分层不等于投资建议** | `02-business-requirements` §16.4、§27.4 |
| C-6 | 不引入 AI / ML | 上游 §6.2.1、§9 原则十至十一 |
| C-7 | `Fund Tier` **不得**用于构建 `Peer Group` | 上游 §7.2（否则形成循环依赖） |
| C-8 | Policy 变更不覆盖历史 Tier | 上游 §9 原则六 |

---

## 18. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~FC-1~~ | ~~是否为 `A+`/`A` 追加绝对门槛（P1 项）~~ —— **已定案**：第一阶段【不】为 A+/A 追加绝对门槛 | — | ✅ 2026-08-27 |
| ~~FC-2~~ | ~~小样本组是否产出 Tier~~ —— **已定案**：不产出，`classification_status = INSUFFICIENT_SAMPLE`（§8.5.1） | — | ✅ 已定案 2026-08-27 |
| ~~FC-3~~ | ~~是否需要"接近上一档"的展示层提示~~ —— **推荐默认**：提供「接近上一档」提示（距上档阈值 < 2 个百分点） | — | ✅ 2026-08-27 |
| FC-4 | Tier 变动的告警阈值（如单期降档比例骤增） | 监控 | 投研 + 运维 |

---

## 19. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§7、术语表 `Fund Tier`）、`02-business-requirements.md` v2.3（§16.3、§16.3.1、§16.4） |
| **本域** | `03-fund-ranking`（Percentile 来源）、`05-fund-selection`（消费 Tier） |
| **数据** | `03-data/02-data-domain-model`（`Fund Classification` —— 与本文档的 `Fund Tier` 严格区分） |

---

## 20. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（2 项）**。`FC-1` 第一阶段**不为 A+/A 追加绝对门槛** —— Tier 是相对分层，叠加绝对门槛会让熊市中 A+ 档空缺，使 Tier 变化反映市场而非基金自身；绝对表现的提示改由展示层承担。`FC-3` 提供「接近上一档」提示（距阈值 < 2 个百分点），**纯展示层、不落库、不参与计算**。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.1** | 2026-08-27 | **`TBD-FC-2` 关闭**。§8.5 定案 —— `n_effective < 30` 时**不产出 Tier**（`tier = null`、`classification_status = INSUFFICIENT_SAMPLE`）；新增 §8.5.1 说明为何不选「低置信标记」：标记只在展示层可见而消费 Tier 的是代码；且 **Tier 是离散档位，小样本下会跳档**（`N=10` 与 `N=11` 可让同一基金从 A+ 掉到 A 而表现未变），这种不连续性无法用低置信表达。详见 `TBD-resolution.md` Policy ⑤ | `02-business-requirements` v2.6 §7.3.1 |
| v1.0 | 2026-08-26 | 初始版本。**§1.2 澄清文件名与上游 `Fund Classification` 的撞名**——本文档定义的是 `Fund Tier`，混淆两者会形成 `Score → Tier → Peer Group → Score` 循环依赖；沿用上游已定案的五档与分位 5/20/50/80，**不采用提示词的四档命名，且分层阈值不标 TBD**；**§8.3 明确"前 5%"对应 `percentile >= 95`** 的换算（Rank 与 Percentile 语义方向相反，极易出错）；§8.5 小样本下的边界失真；**§11.2 Tier 的天然不稳定性四个来源**与 §11.3 不引入平滑机制的理由（平滑引入路径依赖、破坏可复现性）；§7.2 组内绝对水平同屏展示为强制项 | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`03-fund-ranking.md` v1.0 |