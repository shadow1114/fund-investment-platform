# 资产配置 · Asset Allocation

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：**⑥ Portfolio Construction**
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§19.5
> 本域上游：docs/06-portfolio/01-portfolio-construction.md（v1.0）
>
> **文档版本**：v1.1 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **组合资金如何在资产类别之间分配？**

### 1.2 Allocation 与 Optimization 的边界 ⚠️

| | **Asset Allocation**（本文档） | **Portfolio Optimization**（`03`） |
|---|---|---|
| 决定 | **类别层**的目标配比 | **基金层**的具体权重 |
| 性质 | 投资**观点**（配置逻辑） | 数学**求解** |
| 归属 Stage | **⑥**（定义问题的一部分） | **⑦** |
| 产出形式 | 类别目标 / 区间 → **进入约束集** | 权重向量 `w` |

> **Allocation 的产出是优化问题的约束，不是权重。** 它规定"权益类应占 X%"，但具体哪只权益基金占多少由 `03` 求解。

### 1.3 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 基金层权重 | `03-portfolio-optimization` |
| 风险如何分配 | `04-risk-budgeting` |
| 约束的完整定义与优先级 | `05-constraints` |
| 资产类别的**数据定义** | `03-data`（基金分类）|

---

## 2. Allocation Hierarchy

### 2.1 三层结构

```
Portfolio
    ↓  Asset Class Allocation      ← 本文档
Asset Class
    ↓  Fund Weight（优化求解）      ← 03-portfolio-optimization
Fund
```

### 2.2 第一阶段不引入 Strategy / Sleeve 层

> 提示词建议 `Portfolio → Asset Class → Strategy/Sleeve → Fund` 四层。**第一阶段采用三层。**

**理由**：

| # | 理由 |
|---|---|
| 1 | `02-business-requirements` 中**没有 Strategy / Sleeve 的业务需求** |
| 2 | 每增加一层，就多一组"子层权重之和 = 父层权重"的校验与配置项 |
| 3 | 引入无人维护的空层级，会使配置校验产生大量恒真检查 |

> **保留扩展性**：层级校验规则（§6）按**通用的父子关系**表述，未来插入 Sleeve 层时校验逻辑不变。

> **已定案 · 2026-08-27**：第一阶段**不引入 Strategy / Sleeve 层**，保持「资产类别 → 基金」两层。
>
> **依据 —— 三层会使约束的 scope 组合数翻倍**：
>
> ```
> 两层：约束 scope ∈ {PORTFOLIO, ASSET_CLASS, FUND}
> 三层：约束 scope ∈ {PORTFOLIO, SLEEVE, ASSET_CLASS, FUND}
>       且须定义 Sleeve 与 Asset Class 的嵌套关系
>       （一个 Sleeve 含多个类别？还是一个类别跨多个 Sleeve？）
> ```
>
> **两层已足以表达第一阶段的配置逻辑** —— 风险档位决定资产类别权重（`AA-4`），类别内由优化器选基金。Sleeve 层的价值在于表达「同一资产类别内的不同策略」（如股票内的价值/成长），而这需要策略标签，属 `DN-4` 分类体系的待定范围。

### 2.3 层级示例

```
Portfolio
├── Equity          目标 TBD%
│   ├── Fund A      ← 权重由优化求解
│   └── Fund B
├── Fixed Income    目标 TBD%
│   └── Fund C
└── Cash            目标 TBD%（是否作为类别见 01 §9.2）
```

---

## 3. Asset Classes

### 3.1 不自行定义资产类别

> **资产类别的划分依据是 `Fund Classification`**（`03-data` 的客观属性），本域不新增分类体系。

```
Fund Classification（03-data）→ 客观的基金类型
        ↓  映射
Asset Class（本域）           → 配置维度
```

### 3.2 映射关系必须显式且版本化

> **`Fund Classification` 与 `Asset Class` 不必一一对应。**

```
Fund Classification 可能有数十个细分类型
Asset Class 通常只有 3–6 个配置维度
    → 需要一个显式的多对一映射
```

**要求**：

| # | 要求 |
|---|---|
| 1 | 映射必须**显式声明**，不得由类型名称推断 |
| 2 | 映射必须**版本化**，属 `Allocation Policy` |
| 3 | 映射必须**满足 PIT** —— 基金转型改变分类，进而改变其所属 Asset Class |
| 4 | **必须完备** —— Universe 中任一基金都能映射到某个 Asset Class，否则该基金无法参与配置校验 |

### 3.3 候选类别

> **具体类别集合待确认，本域不自行拍板。**

可能包括：`Equity` / `Fixed Income` / `Money Market` / `Commodity` / `Alternative` / `Cash`。

```
Asset Class Set = TBD
```

`<TBD-AA-2: 资产类别集合及其与 Fund Classification 的映射规则，待投研确认>`

### 3.4 混合型基金的归属是一个真问题 ⚠️

> **混合型（Hybrid）基金同时持有权益与债券，把它整体归入某一类会使配置失真。**

```
组合配置：Equity 60% / Bond 40%
持有一只权益仓位 70% 的混合型基金，权重 20%

若把它整体计入 Equity   → 高估权益敞口
若把它整体计入 Bond     → 严重低估权益敞口
若按穿透拆分            → 需要基金持仓明细数据
```

**三种处理方式**：

| 方式 | 说明 | 数据要求 |
|---|---|---|
| **整体归类** | 按 `Fund Classification` 归入单一类别 | 无额外要求 |
| **穿透拆分** | 按基金实际持仓拆到各类别 | **需要持仓明细，`03-data` 当前不含** |
| **独立类别** | `Hybrid` 作为独立 Asset Class | 无额外要求，但配置语义模糊 |

> **第一阶段的数据现实**：`03-data` 的 Dataset 清单中**没有基金持仓明细**，穿透拆分不可行。因此只能在"整体归类"与"独立类别"之间选择，**且必须承认由此产生的敞口失真**。

> **已定案 · 2026-08-27**：混合型基金按其 **Fund Classification 归入单一资产类别**，**不做穿透拆分**。
>
> **依据**：与 `PC-4` 同源 —— 穿透拆分需要持仓明细数据，而该数据①不在第一阶段范围；②季报级披露有 45 天以上滞后，其 PIT 处理会让「当期资产配置」实际反映的是一个季度前的持仓。
>
> **代价须明确**：一只 60/40 的偏股混合被整体计入「混合型」类别，其真实的股票暴露不进入股票类别的权重统计。**这会使资产配置的实际暴露与目标权重存在偏离**，且偏离幅度随混合型基金的持仓比例上升。
>
> **缓解方式**：将混合型细分为「偏股混合 / 平衡混合 / 偏债混合」三个子类别（依赖 `DN-4` 的分类体系），使近似粒度更细 —— 这仍是近似，但偏离幅度可控。

---

## 4. Allocation Types

### 4.1 三种类型

| 类型 | 说明 | 第一阶段 |
|---|---|---|
| **Strategic Asset Allocation（SAA）** | 长期目标权重 | ✅ **实现** |
| **Tactical Asset Allocation（TAA）** | 在 SAA 基础上允许一定范围偏离 | **框架预留** |
| **Dynamic Allocation** | 按规则动态调整目标 | ❌ 不实现 |

### 4.2 第一阶段只实现 SAA

> **TAA 与 Dynamic Allocation 都需要一个"何时偏离、偏离多少"的判断依据，而该依据在第一阶段不存在。**

```
TAA 需要：对各类别相对吸引力的判断
    → 这是一种 Return Estimate 的类别层版本
    → 07-return-risk 第一阶段只做基金层估计
```

**框架预留方式**：`Allocation Range`（§6）的 `min` / `max` 区间本身就是 TAA 的容器 —— 未来引入 TAA 时，它在区间内调整 `target`，不需要改变数据结构。

### 4.3 Dynamic Allocation 不等于 ML

> 需澄清：不实现 Dynamic Allocation 的理由**不是**"它涉及 ML"。基于规则的动态配置（如按波动率调整权益仓位）是纯 Quant 的，与上游的 ML 排除无关。

**真实理由**：第一阶段缺少类别层的估计输入，且引入动态目标会使 `Portfolio Rule Version` 的语义复杂化（目标本身随时间变化，需额外记录"当时的目标是怎么算出来的"）。

---

## 5. Target Weight

### 5.1 定义

```
Target Weight (Asset Class i) = 该类别在组合中的目标占比
```

### 5.2 取值

```
Equity        = TBD
Fixed Income  = TBD
Money Market  = TBD
Cash          = TBD
```

> **以上参数当前均为 TBD，投产前必须由业务负责人确认。** 本域不自行指定比例。

`<TBD-AA-4: 各风险档位（risk_profile）下的资产类别目标权重，待投研确认>`

### 5.3 目标权重随 `risk_profile` 变化

> **同一套资产类别，不同风险偏好的组合应有不同的目标配比。**

```
Conservative  → 权益低配
Balanced      → 均衡
Aggressive    → 权益高配
```

因此 `Allocation Policy` 的目标权重是 **`risk_profile` 的函数**，而非单一取值。

---

## 6. Allocation Range

### 6.1 三元组

> 每个 Asset Class 定义三个值，而非单一目标：

| 值 | 作用 |
|---|---|
| **`min_weight`** | 下限 —— 硬约束 |
| **`target_weight`** | 目标 —— SAA 的中枢 |
| **`max_weight`** | 上限 —— 硬约束 |

```
Asset Class:
  Min    = TBD
  Target = TBD
  Max    = TBD
```

### 6.2 为什么需要区间而非单点

| # | 理由 |
|---|---|
| 1 | **单点目标使问题过度受限** —— 若每个类别都是等式约束，基金层的优化空间被压缩到几乎没有 |
| 2 | **净值波动使精确配比不可维持** —— 严格等式会导致持续的微小调仓 |
| 3 | **区间是 Drift 触发的基础** —— 偏离阈值需要一个"可接受范围"的定义 |
| 4 | **区间为 TAA 预留容器**（§4.2） |

### 6.3 区间与 Drift 阈值不是同一件事 ⚠️

> **两者容易混淆，但作用完全不同。**

| | **Allocation Range** | **Drift Threshold** |
|---|---|---|
| 作用 | **优化时的硬约束** —— 解必须落在区间内 | **调仓触发条件** —— 超出才调仓 |
| 违反的后果 | 优化不可行 | 触发再平衡 |
| 归属 | 本文档 + `05-constraints` | `06-rebalancing` |
| 量级关系 | 通常**更宽** | 通常**更窄** |

```
Equity: min 50% / target 60% / max 70%
Drift Threshold: ±5%

→ 优化解必须在 [50%, 70%]
→ 实际权重漂移到 66% 时触发调仓（偏离 target 超过 5%）
→ 但 66% 仍在允许区间内，不构成违约
```

> **若把两者设成同一个值**，会出现"实际权重刚触发调仓就已违反约束"的情形，使约束校验持续报警。

---

## 7. Allocation Hierarchy Validation

### 7.1 两条校验

```
① Σ Asset Class Target Weight = 100%
② 对每个 Asset Class：Σ 成分基金权重 = 该类别权重
```

### 7.2 区间的自洽校验

> **有了区间之后，仅校验目标之和为 100% 是不够的。**

| 校验 | 条件 | 违反的后果 |
|---|---|---|
| 目标和 | `Σ target = 100%` | 配置不完整 |
| **下限和** | `Σ min ≤ 100%` | **必然不可行** |
| **上限和** | `Σ max ≥ 100%` | **必然不可行** |
| 单类别自洽 | `min ≤ target ≤ max` | 配置错误 |

> **后两条是最常见的配置错误** —— 逐个类别看都合理，加起来无解。例如四个类别各设上限 20%，加起来只有 80%，永远凑不满 100%。

这属于 `01-portfolio-construction` §13.1 的结构性可行性预检。

### 7.3 现金的处理

> 若组合允许持有现金（`01` §10.2），则：

```
Σ Asset Class Weight + Cash Weight = 100%
```

**现金是否作为一个 Asset Class 参与配置校验**，取决于 `TBD-PC-5` 的决定：

| 方案 | 校验形式 |
|---|---|
| 现金作为独立 Asset Class | `Σ（含 Cash）= 100%` |
| 现金作为余量 | `Σ（不含 Cash）≤ 100%`，余下为现金 |

### 7.4 冻结持仓使可分配空间小于 100% ⚠️

> **成分基金变为 `NOT_TRADABLE` 时其权重冻结**（`01` §9.2），此时：

```
可优化空间 = 100% − Σ 冻结权重

若冻结权重占 8%，则优化器只能在剩余 92% 中分配
    → 类别配置的目标必须按剩余空间重新解释
    → 否则"权益目标 60%" 与实际可达成的最大值冲突
```

**处理**：冻结权重必须**先计入其所属类别**，再在剩余空间内做配置。若冻结权重已超出某类别上限，该约束应转为**软约束或告警**，而非导致整个问题不可行。

> **已定案 · 2026-08-27**：按**软约束 + 告警**处理，**不强制卖出其它成分**。
>
> **依据 —— 强制卖出会放大不可控因素的影响**：
>
> ```
> 一只基金暂停赎回（外部事实，不可控）
>     → 其权重被冻结，导致所属类别超限
>     → 若强制卖出该类别的其它基金来恢复合规
>     → 一处不可交易，扰动了整个类别的持仓
>     → 且卖出的是【可交易的、本应保留的】那些
> ```
>
> **超限的原因不在决策，而在执行环境** —— 用交易去修正一个非交易原因造成的偏离，成本由组合承担而问题并未解决（冻结解除后又要调回来）。
>
> **须标记 `VIOLATED_BY_FROZEN`**（同 `05-constraints` `CS-5`），与「决策本身违反约束」区分开。前者是外部事实，后者是缺陷。

---

## 8. Allocation Policy

| 字段 | 说明 |
|---|---|
| `policy_id` | 标识 |
| `version` | 版本号 |
| `effective_from` / `effective_to` | 生效区间 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` |
| **`asset_class_set`** | 类别集合 |
| **`classification_to_asset_class_map`** | 映射规则（§3.2） |
| **`allocation_ranges`** | 按 `risk_profile` 的 `min` / `target` / `max` 三元组 |
| `hybrid_handling` | 混合型基金的归属方式（§3.4） |
| `cash_treatment` | 现金处理（§7.3） |
| `frozen_holding_handling` | 冻结持仓超限的处理（§7.4） |
| `allocation_type` | 第一阶段固定为 `SAA` |

### 8.1 Allocation Policy 属 `Portfolio Rule Version`

> 它是 Construction 的组成部分，随 `Portfolio Rule Version`（Strategy Version 第 7 项）一同版本化，**不新增版本类型**。

---

## 9. Input / Process / Output

### 9.1 Input

| 输入 | 来源 |
|---|---|
| `Fund Universe` 成分及其 `Fund Classification` | `05-fund-evaluation/05` |
| `risk_profile` | Portfolio Object（`01` §7.1） |
| `Allocation Policy` + version | 本文档 |
| 冻结持仓清单 | `06-rebalancing` / Live Portfolio |

### 9.2 Process

```
① 按映射规则把每只候选基金归入 Asset Class（PIT：用当时的分类）
② 校验映射完备性 —— 存在无法映射的基金则阻断
③ 按 risk_profile 取 allocation_ranges
④ 计入冻结持仓的类别占用
⑤ 校验区间自洽（§7.2）
⑥ 输出类别层约束，交给 05-constraints 汇总入约束集
```

### 9.3 Output

| 字段 | 说明 |
|---|---|
| `portfolio_id` + `as_of_date` | 标识 |
| **`asset_class_constraints`** | 各类别的 `min` / `target` / `max` |
| **`fund_to_asset_class_map`** | 该时点的映射结果 |
| `frozen_allocation` | 各类别的冻结权重占用 |
| `available_space` | 可分配空间（100% − 冻结） |
| `allocation_policy_version` | 政策版本 |

> **输出是约束，不是权重。**

---

## 10. Edge Cases

| 情形 | 处理 |
|---|---|
| 某基金无法映射到任何 Asset Class | **阻断** —— 映射必须完备（§3.2） |
| 某类别在 Universe 中无合格基金但有下限 | **可行性预检失败**，上报 Construction 层 |
| `Σ min > 100%` 或 `Σ max < 100%` | **配置错误，阻断**（§7.2） |
| 冻结权重超出某类别上限 | 按 `TBD-AA-5` 处理，**不得直接判为不可行** |
| 基金在持有期内转型改变分类 | 用当时的分类；转型后其 Asset Class 可能变化，触发 `Eligibility Event` 类再平衡 |
| 混合型基金占比高 | 敞口失真风险显著上升，须在组合风险分析中标注 |
| 只有一个 Asset Class | 配置校验退化为恒真；此时 Allocation 层无实质作用，但不构成错误 |

---

## 11. Explainability

> **必须能回答：Why is this asset class weighted this way?**

```
Equity 目标权重 X%，因为：
  ① 组合 risk_profile = Balanced
  ② Allocation Policy v2 对 Balanced 档的 Equity 目标为 X%
  ③ 允许区间 [X%, X%]
  ④ 当前冻结持仓在 Equity 占 X%
  ⑤ 实际可分配空间 X%
```

---

## 12. Reproducibility

```
Fund Universe（该时点）
+ Fund Classification（该时点版本，PIT）
+ Allocation Policy Version
+ risk_profile
+ 冻结持仓状态
        ↓
    相同的类别约束
```

> **`Fund Classification` 的 PIT 是本层可复现的关键** —— 用今天的分类映射历史组合，会得到与当时不同的类别敞口。

---

## 13. Auditability

### 13.1 配置决策的追溯链

```
Asset Class Constraints
    ├─ Allocation Policy Version      → 类别集合、区间、映射规则
    ├─ Fund Classification Version    → 该时点的基金分类（PIT）
    ├─ risk_profile                   → 决定用哪一档区间
    └─ 冻结持仓状态                    → 可分配空间的扣减
```

### 13.2 映射结果必须落库，不可仅保留规则

> **仅保留映射规则不足以还原历史。**

```
规则："偏股混合型 → Equity"
但某基金在 T 时点的分类是"偏债混合型"，T+1 转为"偏股混合型"
    → 只有规则时，无法判断当时它被归入了哪一类
    → 必须落库 fund_to_asset_class_map 的实际结果
```

这与 `05-fund-evaluation/01` §18.2「`Peer Group Version` 是可复现的隐含要素」是同一类问题 —— **规则加输入不等于结果可还原，除非输入本身也被完整版本化**。

---

## 14. Summary

Asset Allocation 决定**类别层**目标配比，产出的是**约束而非权重**。

三条设计判断：

- **第一阶段采用三层（Portfolio → Asset Class → Fund），不引入 Strategy / Sleeve** —— 无对应业务需求，多一层就多一组恒真校验
- **只实现 SAA** —— TAA 需要类别层的相对吸引力判断，而 `07-return-risk` 第一阶段只做基金层估计；`Allocation Range` 的区间本身就是未来 TAA 的容器
- **用区间而非单点目标** —— 单点等式会把基金层优化空间压缩到几乎没有，且净值波动使精确配比不可维持

三处容易出错的地方：

- **混合型基金的归属会造成敞口失真** —— 穿透拆分需要基金持仓明细，而 `03-data` 当前不含该数据；只能整体归类或独立成类，且必须承认失真
- **`Allocation Range` 与 `Drift Threshold` 不是同一件事** —— 前者是优化硬约束，后者是调仓触发条件；设成同值会导致"刚触发调仓就已违约"
- **仅校验目标和为 100% 不够** —— 各类别上限之和小于 100%（或下限之和大于 100%）时问题必然不可行，逐个看却都合理

---

## 15. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **Allocation 产出约束，不产出权重** | 类别配比是问题的一部分，基金权重由 `03` 求解 |
| D-2 | **第一阶段采用三层，不引入 Strategy / Sleeve** | 无业务需求；多一层多一组恒真校验 |
| D-3 | 层级校验按通用父子关系表述 | 未来插入 Sleeve 层时逻辑不变 |
| D-4 | **资产类别由 `Fund Classification` 映射而来，不新建分类体系** | 避免与 `03-data` 的分类重复定义 |
| D-5 | 映射必须显式、版本化、满足 PIT、且**完备** | 无法映射的基金会绕过配置校验 |
| D-6 | **只实现 SAA**，TAA 框架预留 | TAA 缺少类别层估计输入 |
| D-7 | 明确不实现 Dynamic Allocation 的理由**不是 ML** | 规则型动态配置是纯 Quant 的；真实理由是缺输入且使版本语义复杂化 |
| D-8 | **采用 `min` / `target` / `max` 区间而非单点** | 单点等式压缩优化空间且不可维持 |
| D-9 | 目标权重是 `risk_profile` 的函数 | 不同风险偏好应有不同配比 |
| D-10 | **`Allocation Range` 与 `Drift Threshold` 严格区分** | 设成同值会导致持续报警 |
| D-11 | 区间自洽校验（`Σ min ≤ 100% ≤ Σ max`）纳入可行性预检 | 最常见的配置错误 |
| D-12 | 冻结持仓先计入所属类别，再在剩余空间配置 | 否则目标与可达成值冲突 |

---

## 16. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 资产类别映射必须完备，无法映射则阻断 | 本文档 §3.2 |
| C-2 | `Fund Classification` 的取用必须满足 PIT | 上游 §4.2 ①-PIT、`02-business-requirements` §7.4 |
| C-3 | `Σ Asset Class Target Weight = 100%` | 本文档 §7.1 |
| C-4 | 子层权重之和必须等于父层权重 | 同上 |
| C-5 | 区间自洽（`Σ min ≤ 100% ≤ Σ max`）是可行性前提 | 本文档 §7.2 |
| C-6 | 本域**不新建**资产分类体系 | `03-data` 拥有 `Fund Classification` |
| C-7 | 配置目标不得由本域自行拍板 | `TBD-AA-4` |

---

## 17. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~AA-1~~ | ~~是否引入 Strategy / Sleeve 层~~ —— **已定案**：第一阶段【不】引入 Strategy / Sleeve 层 | — | ✅ 2026-08-27 |
| AA-2 | **资产类别集合及其与 `Fund Classification` 的映射规则** | 配置维度无法定义 | 投研 |
| ~~AA-3~~ | ~~混合型基金的归属方式；是否需引入基金持仓明细（涉及 `03-data` 扩展）~~ —— **已定案**：混合型基金按其 Fund Classification 归入【单一】资产类别，不做穿透拆分 | — | ✅ 2026-08-27 |
| AA-4 | **各 `risk_profile` 下的类别目标权重** | 配置无法投产 | 投研 |
| ~~AA-5~~ | ~~冻结持仓导致类别超限时的处理~~ —— **已定案**：冻结持仓导致类别超限时按【软约束 + 告警】处理，不强制卖出其他成分 | — | ✅ 2026-08-27 |
| AA-6 | 是否需要 TAA 及其偏离判断依据 | 未来扩展 | 投研 |

---

## 18. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§4.2 ⑥）、`02-business-requirements.md` v2.3（§19.5） |
| **本域** | `01-portfolio-construction`（Portfolio Object、现金处理）、`05-constraints`（类别约束汇总）、`06-rebalancing`（Drift Threshold） |
| **数据** | `03-data/02-data-domain-model`（`Fund Classification`） |
| **评价** | `05-fund-evaluation/05-fund-selection`（Fund Universe） |

---

## 19. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.1** | 2026-08-27 | **第二批定案（3 项）**。`AA-1` **不引入 Strategy / Sleeve 层**（三层会使约束 scope 组合数翻倍，且 Sleeve 需要待定的策略标签）；`AA-3` 混合型按 Fund Classification **归入单一类别不做穿透**，代价是实际暴露与目标权重存在偏离，缓解方式是细分为偏股/平衡/偏债三子类；`AA-5` 冻结导致类别超限按**软约束 + 告警**，不强制卖出其它成分（用交易修正非交易原因的偏离，成本由组合承担而问题并未解决）。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.0 | 2026-08-26 | 初始版本。**§2.2 第一阶段采用三层、不引入 Strategy / Sleeve** 及其三条理由；**§3.2 分类到类别的映射必须显式、版本化、PIT 且完备**；**§3.4 混合型基金归属的敞口失真问题**——穿透拆分需持仓明细而 `03-data` 当前不含，只能在整体归类与独立成类间选择；§4.2 只实现 SAA 及"区间即 TAA 容器"的预留方式；**§4.3 澄清不实现 Dynamic Allocation 的理由不是 ML**；**§6.3 `Allocation Range` 与 `Drift Threshold` 的严格区分**（设成同值会导致刚触发调仓就已违约）；**§7.2 区间自洽校验**（各类别上限之和 < 100% 时必然不可行，逐个看却都合理）；§7.4 冻结持仓使可分配空间小于 100%；**§13.2 映射结果必须落库而非仅保留规则**——规则加输入不等于结果可还原 | `01-product-overview.md` v2.5、`02-business-requirements.md` v2.3、`01-portfolio-construction.md` v1.0 |