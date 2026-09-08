# 因子分类 · Factor Taxonomy

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文细化环节：② Factor
> 业务需求：docs/01-product/02-business-requirements.md（v2.3）§10–§14
> 本域上游：docs/04-factor/01-factor-overview.md（v1.0）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. 文档目的与边界

### 1.1 本文档回答什么

> **系统中的 Factor 如何分类、如何编号、完整清单是什么？**

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 每个 Factor 的具体定义与公式 | `03-factor-definition` |
| 如何计算 | `04-factor-calculation` |
| 如何标准化 | `05-factor-normalization` |
| 评分权重如何配置 | `05-fund-evaluation` |

---

## 2. 一级分类

### 2.1 五个一级分类

| 代码 | 分类 | 衡量 | 对应上游子分 |
|---|---|---|---|
| **RET** | Performance | 基金获得收益的能力 | **Return Score** |
| **RISK** | Risk | 基金承担风险的程度 | **Risk Score** |
| **RAP** | Risk-adjusted Performance | 单位风险对应的收益 | **Risk-Adjusted Score** |
| **STAB** | Stability | 表现是否稳定持续 | **Stability Score** |
| **REL** | Relative Performance | 相对基准的表现 | **Relative Performance Score** |

> **五个分类与上游 §4.2 ③-S 的五个子分一一对应**。这不是巧合——分类体系就是按评分结构设计的，保证 `05-fund-evaluation` 可以直接按分类聚合。

### 2.2 分类的划分依据

> **RAP 与 REL 的边界是"是否依赖 Benchmark"，而非业务名称。**

```
Sharpe / Sortino / Calmar      不依赖 Benchmark  →  RAP
Alpha / Beta / IR / TE         依赖 Benchmark    →  REL
```

**理由**：依赖 Benchmark 的 Factor 有一个共同的失效模式——Benchmark 不可得时全部 `UNAVAILABLE`（`03-data/01-data-source` §5）。按此划分，缺 Benchmark 时可整类降级，而不必逐个判断。

---

## 3. Factor ID 规范

### 3.1 格式

```
F-<CATEGORY>-<SEQ>
```

| 部分 | 说明 |
|---|---|
| `F` | 固定前缀 |
| `<CATEGORY>` | `RET` / `RISK` / `RAP` / `STAB` / `REL` |
| `<SEQ>` | 三位序号，类内递增 |

**示例**：`F-RET-001`、`F-RISK-003`、`F-RAP-001`

### 3.2 ID 规则

| # | 规则 |
|---|---|
| ID-1 | Factor ID **全局唯一** |
| ID-2 | **一经分配不再复用** —— 即使 Factor 下线，其编号也不回收 |
| ID-3 | ID 与 **Primary Category 绑定**；若某 Factor 的 Primary Category 变更，**保留原 ID**，不重新编号 |
| ID-4 | **时间窗口不体现在 ID 中** —— 见 §3.3 |
| ID-5 | ID 不含版本信息 —— 版本由 `Factor Version` 独立表达（`06-factor-versioning`） |

### 3.3 时间窗口不进 ID

> **同一个 Factor 在不同时间窗口下是同一个 Factor，不是不同 Factor。**

```
✅  F-RET-001（年化收益率）+ Window = 1Y / 3Y / 5Y
❌  F-RET-001（1Y 年化）、F-RET-002（3Y 年化）、F-RET-003（5Y 年化）
```

**理由**：

| # | 理由 |
|---|---|
| 1 | 若窗口进 ID，Factor 数量会膨胀数倍（30 个 Factor × 6 个窗口 = 180 个 ID） |
| 2 | 公式、方向、单位在不同窗口下完全相同——它们本就是同一个定义 |
| 3 | 评分方案配置时可统一引用 Factor ID 再指定窗口，配置更清晰 |

**因此**：Factor Result 的唯一键是 `(Fund/Share Class, Factor ID, Window, Version, decision_at)`（`08-factor-output`）。

### 3.4 Rolling 类 Factor 的处理

> Rolling 类是**例外**：它们不是"某个 Factor 加窗口"，而是**独立的 Factor**。

```
F-STAB-005  Rolling Sharpe（252 个交易日滚动窗口的 Sharpe 序列）
    ≠
F-RAP-001   Sharpe（单一区间的 Sharpe 标量）
```

**区别**：前者产出**序列**（可进一步计算其均值、标准差、趋势），后者产出**标量**。两者的输出结构不同，因此是不同 Factor。

---

## 4. 分类原则

### 4.1 唯一 Primary Category

| # | 规则 |
|---|---|
| CAT-1 | 每个 Factor 有且仅有**一个 Primary Category** |
| CAT-2 | 可有若干 **Secondary Category**，用于表达业务关联 |
| CAT-3 | **评分聚合按 Primary Category 进行** —— Secondary 不参与聚合 |

### 4.2 为什么 Primary 必须唯一

> 若一个 Factor 同时属于多个一级分类，评分聚合时会**重复计入**，且权重配置无法确定。

```
❌  Alpha 同时属于 RAP 与 REL
    → Risk-Adjusted Score 与 Relative Performance Score 都算它
    → 该 Factor 的实际权重翻倍，且无人察觉
```

### 4.3 Secondary Category 的用途

| 用途 | 说明 |
|---|---|
| 业务检索 | "列出全部与风险相关的 Factor"可跨 Primary 检索 |
| 相关性分析 | 同 Secondary 的 Factor 通常高度相关（`07-factor-validation` §Correlation） |
| **不用于评分聚合** | —— |

---

## 5. Factor Catalog

> 完整定义见 `03-factor-definition`。本表为索引，含 ID、分类、方向、单位、用途。

**图例**：
- Direction：`H↑`= HIGHER_IS_BETTER ｜ `L↓`= LOWER_IS_BETTER ｜ `TR`= TARGET_RANGE ｜ `SD`= STRATEGY_DEPENDENT
- Usage：`D`=DISPLAY ｜ `SC`=SCORING ｜ `SR`=SCREENING ｜ `B`=BACKTEST。Catalog Usage 是长期能力标签，不代表 M1 已启用或进入总分。
- BM：是否依赖 Benchmark

### 5.1 RET · Performance（4 项）

| ID | Factor | Direction | Unit | Usage | BM |
|---|---|---|---|---|---|
| `F-RET-001` | Annualized Return | `H↑` | 百分比 | D·SC·SR·B | — |
| `F-RET-002` | Cumulative Return | `H↑` | 百分比 | D·SR·B | — |
| `F-RET-003` | Period Return | `H↑` | 百分比 | D·SC·SR·B | — |
| `F-RET-004` | Rolling Return | `H↑` | 百分比 | D·SC·SR·B | — |

### 5.2 RISK · Risk（7 项）

| ID | Factor | Direction | Unit | Usage | BM |
|---|---|---|---|---|---|
| `F-RISK-001` | Volatility | `L↓` | 百分比 | D·SC·SR·B | — |
| `F-RISK-002` | Downside Volatility | `L↓` | 百分比 | D·SC·SR·B | — |
| `F-RISK-003` | Maximum Drawdown | `L↓` | 百分比 | D·SC·SR·B | — |
| `F-RISK-004` | VaR 95% | `L↓` | 百分比 | D·SC·SR·B | — |
| `F-RISK-005` | CVaR 95% | `L↓` | 百分比 | D·SC·SR·B | — |
| `F-RISK-006` | Drawdown Duration | `L↓` | 天数 | D·SR·B | — |
| `F-RISK-007` | Recovery Duration | `L↓` | 天数 | D·SR·B | — |

> Portfolio 与 `07-return-risk` 不消费 Factor。它们直接消费 PIT 收益序列，独立计算组合所需的波动率、相关性与协方差。

### 5.3 RAP · Risk-adjusted Performance（3 项）

| ID | Factor | Direction | Unit | Usage | BM |
|---|---|---|---|---|---|
| `F-RAP-001` | Sharpe Ratio | `H↑` | 比率 | D·SC·SR·B | — |
| `F-RAP-002` | Sortino Ratio | `H↑` | 比率 | D·SC·SR·B | — |
| `F-RAP-003` | Calmar Ratio | `H↑` | 比率 | D·SC·SR·B | — |

> 三者均使用无风险利率但**不使用 Benchmark**，因此归 RAP 而非 REL。

### 5.4 STAB · Stability（7 项）

| ID | Factor | Direction | Unit | Usage | BM |
|---|---|---|---|---|---|
| `F-STAB-001` | Win Rate | `H↑` | 百分比 | D·SC·SR·B | 可选 |
| `F-STAB-002` | R² | `SD` | 比率 | **D·SR** | **是** |
| `F-STAB-003` | Skewness | `H↑` | 无量纲 | **D·SR** | — |
| `F-STAB-004` | Kurtosis | `L↓` | 无量纲 | **D·SR** | — |
| `F-STAB-005` | Rolling Sharpe | `H↑` | 序列 | D·SC·SR·B | — |
| `F-STAB-006` | Rolling Volatility | `L↓` | 序列 | D·SC·SR·B | — |
| `F-STAB-007` | Rolling Maximum Drawdown | `L↓` | 序列 | D·SC·SR·B | — |

> **三项刻意不进 SCORING**（`F-STAB-002/003/004`）：
> - **R²** 高不代表优秀，只说明与基准的线性关系强（`02-business-requirements` §13.5）
> - **Skewness / Kurtosis** 不进入 M1 scoring，仅保留展示与研究用途
>
> 它们仍是正式 Factor，可用于筛选与展示。

### 5.5 REL · Relative Performance（5 项）

| ID | Factor | Direction | Unit | Usage | BM |
|---|---|---|---|---|---|
| `F-REL-001` | Excess Return | `H↑` | 百分比 | D·SC·SR·B | **是** |
| `F-REL-002` | Alpha | `H↑` | 百分比 | D·SC·SR·B | **是** |
| `F-REL-003` | Beta | **`TR`** | 无量纲 | D·SC·SR·B | **是** |
| `F-REL-004` | Information Ratio | `H↑` | 比率 | D·SC·SR·B | **是** |
| `F-REL-005` | Tracking Error | **`SD`** | 百分比 | D·SC·SR·B | **是** |

> **两个非单调方向的 Factor**：
> - **`F-REL-003` Beta = `TARGET_RANGE`** —— 0.5 不必然优于 1.0；目标区间由 `Evaluation Profile` 与策略目标决定
> - **`F-REL-005` Tracking Error = `STRATEGY_DEPENDENT`** —— 被动型 `LOWER_IS_BETTER`；主动型是超额收益的来源，TE=0 的主动基金等于收了主动管理费做指数

### 5.6 特殊项：费率

| 项 | 说明 |
|---|---|
| **费率**（管理费 + 托管费 + 销售服务费） | **不是计算得出的 Factor**，而是 `Fund Data` 的基金属性（`03-data/02-data-domain-model` §8.1） |

但它**参与评分与筛选**，因此纳入 Factor Usage 管理：

| 属性 | 取值 |
|---|---|
| Direction | `LOWER_IS_BETTER` |
| Usage | `D·SC·SR·B` |
| 权重特点 | **Passive Equity 画像下为高权重项**（`02-business-requirements` §5.2.1） |

> 它在 Catalog 中**不分配 Factor ID** —— 因为它没有公式、没有时间窗口、没有最小观测数。评分方案引用它时直接使用数据字段。

### 5.7 Catalog 与 M1 范围

| 分类 | Catalog 数量 | 带 SCORING 能力标签 | 依赖 Benchmark |
|---|---|---|---|
| RET | 4 | 3 | 0 |
| RISK | 7 | 5 | 0 |
| RAP | 3 | 3 | 0 |
| STAB | 7 | 4 | 1（R²） |
| REL | 5 | 5 | **5** |
| **合计** | **26** | **20** | **6** |

M1 的实际启用和评分范围由 Metric Version 固定：

| 层次 | 范围 |
|---|---|
| M1 enabled（15） | `F-RET-001/002`、`F-RISK-001/002/003`、`F-RAP-001/002/003`、`F-STAB-001/005`、`F-REL-002/003/004/005`、`F-STAB-002` |
| M1 scoring（5） | `F-REL-002/003/004/005`、`F-RISK-003` |
| M1 display-only | `F-STAB-002` R² |
| M1 scoring Fund Data | Expense Ratio，不分配 Factor ID |

---

## 6. Secondary Category 映射

| Factor | Primary | Secondary | 说明 |
|---|---|---|---|
| `F-RAP-001` Sharpe | RAP | RET · RISK | 由收益与波动构成 |
| `F-RAP-003` Calmar | RAP | RET · RISK | 由收益与回撤构成 |
| `F-REL-002` Alpha | REL | RET | 超额收益的一种 |
| `F-REL-004` IR | REL | RAP | 风险调整后的相对表现 |
| `F-REL-005` TE | REL | RISK | 相对基准的波动 |
| `F-STAB-005` Rolling Sharpe | STAB | RAP | Sharpe 的滚动形式 |
| `F-STAB-006` Rolling Volatility | STAB | RISK | Volatility 的滚动形式 |
| `F-STAB-007` Rolling MDD | STAB | RISK | MDD 的滚动形式 |

> **Rolling 类的 Primary 是 STAB 而非其基础 Factor 的分类** —— 因为它们衡量的是**稳定性**（表现是否持续），而非收益或风险本身。

---

## 7. 时间窗口矩阵

> 各 Factor 支持的时间窗口。`03-factor-definition` 中逐个确认。

| Factor 类别 | 1M | 3M | 6M | 1Y | 3Y | 5Y | Rolling 12M |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| RET | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓（F-RET-004） |
| RISK | — | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RAP | — | — | ✓ | ✓ | ✓ | ✓ | — |
| STAB（非 Rolling） | — | — | ✓ | ✓ | ✓ | ✓ | — |
| STAB（Rolling） | — | — | — | — | — | — | ✓ |
| REL | — | ✓ | ✓ | ✓ | ✓ | ✓ | — |

**两条窗口约束**：

| # | 约束 |
|---|---|
| W-1 | **风险与风险调整类 Factor 不支持 1M 窗口** —— 单月约 21 个交易日，波动率与 Sharpe 的统计意义不足 |
| W-2 | 窗口全部按 **Trading-day Period** 计数，年化因子 **252**（`02-business-requirements` §9.2.1） |

> **已定案 · 2026-08-27**：各 Factor 的窗口支持范围**以 `03-factor-definition` 中每个 Factor 的 `Time Window` 字段为准**，本文档不重复声明。
>
> **依据 —— 单一事实来源**：taxonomy 的职责是分类（Factor 属哪个 Category、什么 usage），不是定义。窗口是定义的一部分。两处各存一份必然发散，且发散时无从判断哪个是权威。

---

## 8. Summary

Factor 分类体系的四个要点：

- **五个一级分类与上游五个子分一一对应** —— 分类体系按评分结构设计，`05-fund-evaluation` 可直接按分类聚合
- **RAP 与 REL 的边界是"是否依赖 Benchmark"** —— 便于 Benchmark 不可得时整类降级
- **时间窗口不进 Factor ID** —— 否则 26 个 Factor 会膨胀为 150+ 个 ID；Rolling 类是例外，因为它产出序列而非标量
- **Primary Category 必须唯一** —— 否则评分聚合会重复计入，权重实际翻倍且无人察觉

**Catalog 共 26 个 Factor**，其中 20 个带长期 SCORING 能力标签，6 个依赖 Benchmark；这不等于 M1 全部实现或进入总分。M1 enabled 为 15 项，M1 scoring 为 5 项 Factor 加 Expense Ratio。

---

## 9. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | 五个一级分类对应上游五个评分子分 | 使评分聚合可直接按 Primary Category 进行 |
| D-2 | RAP 与 REL 按"是否依赖 Benchmark"划分 | 依赖 Benchmark 的 Factor 有共同失效模式，可整类降级 |
| D-3 | 时间窗口不进 Factor ID | 避免 ID 膨胀；公式与方向在各窗口下相同 |
| D-4 | Rolling 类作为独立 Factor 而非"加窗口" | 它产出序列而非标量，输出结构不同 |
| D-5 | Rolling 类 Primary Category 为 STAB | 它衡量表现的持续性，而非收益或风险本身 |
| D-6 | R² / Skewness / Kurtosis 不进 M1 SCORING | R² 高不代表优秀；后两者第一阶段仅展示与研究 |
| D-7 | 费率纳入 Usage 管理但不分配 Factor ID | 它是数据属性，无公式、无窗口、无最小观测数 |
| D-8 | Factor ID 一经分配不复用 | 历史结果引用旧 ID，复用会造成追溯错误 |

---

## 10. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 每个 Factor 有且仅有一个 Primary Category | 本文档 §4.1 |
| C-2 | Beta 为 `TARGET_RANGE`，Tracking Error 为 `STRATEGY_DEPENDENT` | `02-business-requirements` §11.3 |
| C-3 | 风险与风险调整类不支持 1M 窗口 | 统计意义不足 |
| C-4 | 窗口按 Trading-day Period 计数，年化 252 | `02-business-requirements` §9.2.1 |
| C-5 | 分类体系必须与上游五个评分子分对应 | 上游 §4.2 ③-S |

---

## 11. TBD

| # | 事项 | 阻塞 | 责任方 |
|---|---|---|---|
| ~~FT-1~~ | ~~各 Factor 的窗口支持范围逐个确认~~ —— **已定案**：各 Factor 的窗口支持范围以 `03-factor-definition` 每个 Factor 的 Time Window 字段为准，`02-factor-taxonomy` 不重复声明 | — | ✅ 2026-08-27 |
| FT-2 | Skewness / Kurtosis 是否纳入 SCORING | `05-fund-evaluation` | 投研（上游 P1-6） |
| FT-3 | Beta 的 TARGET_RANGE 取值 | `05-fund-evaluation` | 投研（上游 P1-22） |
| FT-4 | 是否需要新增其他 Factor（如换手率、持仓集中度） | 本域 | 投研 |

> **FT-4 的说明**：本 Catalog 覆盖上游 §10–§13 明确要求的全部指标。若投研需要额外 Factor（如基于持仓的指标），须先确认数据可得性（`03-data` DS-1）。

---

## 12. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.4（§4.2 ③-S 五子分、§11.2 Direction/Usage）、`01-product/02-business-requirements.md` v2.3（§10–§14） |
| **本域** | `01-factor-overview`（定位）、`03-factor-definition`（逐个定义）、`05-factor-normalization`（方向转换）、`08-factor-output`（结果结构） |
| **下游** | `05-fund-evaluation`（按分类聚合为五个子分）、Fund Universe、`08-backtest`；`07-return-risk` 不消费 Factor |

---

## 13. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-09-08 | 区分 26 项长期 Catalog、15 项 M1 enabled 与 5 项 M1 scoring；移除 Portfolio Usage，明确 Rolling Sharpe 使用 252 个交易日 | Plan-2 设计 v1.1 |
| **v1.1** | 2026-08-27 | **第二批定案（1 项）**。`FT-1` 窗口支持范围以 `03-factor-definition` 的 `Time Window` 字段为准，本文档不重复声明 —— 单一事实来源。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| v1.0 | 2026-08-25 | 初始版本。建立五个一级分类并与上游五个评分子分一一对应；确立 RAP/REL 按"是否依赖 Benchmark"划分；Factor ID 规范及**时间窗口不进 ID** 的论证；Rolling 类作为独立 Factor 的理由；Primary Category 唯一性及重复计入的风险；26 个 Factor 的完整 Catalog（含 Direction / Unit / Usage / BM 依赖）；Secondary Category 映射；时间窗口矩阵与两条窗口约束 | `01-product-overview.md` v2.4、`01-factor-overview.md` v1.0 |