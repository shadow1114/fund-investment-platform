# Plan-2 上游约束清单 · Peer Group / 因子 / 评价与候选池

> **用途**：为 Plan-2（M1.2 Peer Group + M1.3 因子 + M1.4 评价与候选池）的实现计划提供【精确的约束清单】。
> **性质**：这是**摘录**，不是新决策。凡文档给了确切数值/枚举/公式的，此处一字不差抄录；凡文档只给要求没给值的，标注「文档未给值」。
> **生成日期**：2026-08-31

## 出处标注约定

| 简写 | 实际文件 |
|---|---|
| `FE:<行>` | `docs/04-factor/01-fund-evaluation.md`（v1.3，827 行） |
| `FS:<行>` | `docs/04-factor/02-fund-scoring.md`（v1.2，740 行） |
| `FR:<行>` | `docs/04-factor/03-fund-ranking.md`（v1.2，610 行） |
| `FC:<行>` | `docs/04-factor/04-fund-classification.md`（v1.1） |
| `BR:<行>` | `docs/01-product/02-business-requirements.md` |

> **`docs/04-factor/` 与 `docs/05-fund-evaluation/` 逐字节相同**（`01`–`05` 五份文件大小完全一致：39640 / 31346 / 24630 / 21289 / 28276 字节）。行号在两个目录下通用。
>
> ⚠️ **重要**：`docs/04-factor/` 目录里**装的是 fund-evaluation 域的五份文档**，而不是因子域的八份文档。被反复引用的 `04-factor/01-factor-overview` ~ `08-factor-output` **一份都不在仓库里**。详见 §15。

---

## 1. Evaluation Dimensions 与五子分的映射

### 1.1 六维度 → 五子分（`FE:146-159` §6）

原文（`FE:148`）：

> **六个维度**，与上游 ③-S 五子分对齐（Drawdown 归入 Risk 子分）。

| 维度 | 对应子分 | Factor 类别 | 出处 |
|---|---|---|---|
| **Return** | Return Score | `RET` | `FE:152` |
| **Risk**（含 Drawdown） | Risk Score | `RISK` | `FE:153` |
| **Risk-adjusted Return** | Risk-Adjusted Score | `RAP` | `FE:154` |
| **Consistency** | Stability Score | `STAB` | `FE:155` |
| **Relative Performance** | Relative Performance Score | `REL` | `FE:156` |

**Drawdown 的归属**：并入 **Risk 子分**，不独立成维（`FE:148`、`FE:153`、`FS:123`「Risk Score | `RISK`（含 Drawdown）」、`FE:763` D-4「六个评价维度对齐上游 ③-S 五子分（Drawdown 并入 Risk）」）。

**「六维度」的来源**：`FE:80-90` §4 Objectives 列了 7 条目的，其中 1–6 是六个度量维度（收益 / 风险 / 风险调整后 / 回撤 / 相对 Benchmark / 稳定性），第 7 条是「为下游提供标准化的、带状态的输入」。**回撤在 Objectives 里是独立的第 4 项，但在子分结构里被并入 Risk** —— 这就是「六维度 / 五子分」的错位来源。

### 1.2 五子分命名固定（`FS:91-102` §4.1，`BR:999-1010` §15.3）

```
Total Score
 ├── Return Score                 收益表现
 ├── Risk Score                   风险水平
 ├── Risk-Adjusted Score          风险调整后收益
 ├── Stability Score              表现稳定性
 └── Relative Performance Score   相对 Benchmark 表现
```

- `FS:93`：「**沿用上游 §4.2 ③-S，命名不得更改。**」
- `FS:696` C-1：「五子分命名固定，不得增删改」
- `FS:677` D-2：「五子分命名沿用上游 ③-S，不得更改」

### 1.3 费率的归属（已定案）

`FS:129`：

> **已定案 · 2026-08-27**：费率归入 **Risk-Adjusted 子分**，**不独立成项**。

理由（`FS:131`）：①五子分命名已由上游固定，不可增删；②费率直接侵蚀风险调整后的净收益。
连带效应（`FS:133`）：「被动型基金的费率是高权重项……这会使 Passive Equity 的 Risk-Adjusted 子分实际上由费率主导。**这是符合预期的**」。

---

## 2. 进入 SCORING 的 Factor 完整清单

### 2.1 权威来源

- `FE:164`：「**只使用 `04-factor/03-factor-definition` 已定义的 26 个 Factor。** 不得引入该文档中不存在的指标。」⚠️ 该文档不存在，见 §15。
- `FE:168`：「按 `02-business-requirements` §14.2 Factor Usage Matrix，`SCORING` 列打勾的 Factor 才进入评分」
- Factor Usage Matrix 原表：`BR:953-975`

### 2.2 五种 Usage 用途枚举（`BR:939-949` §14.1）

每个 Factor 必须声明至少一种用途：

| 用途 | 含义 |
|---|---|
| `DISPLAY` | 仅展示给用户，不参与任何计算决策 |
| `SCORING` | 参与 `Fund Score` 计算 |
| `SCREENING` | 可作为 `Eligibility Rules` 或探索性筛选的条件 |
| `PORTFOLIO` | 作为组合构建/优化的输入（Stage ⑤/⑥/⑦） |
| `BACKTEST` | 参与回测结果评价 |

### 2.3 Preference Direction 四取值（`FS:177-182` §6.1，`BR:1027` §15.4 规则 2）

| 方向 | 含义 | 示例 |
|---|---|---|
| `HIGHER_IS_BETTER` | 越高越好 | 年化收益率、Sharpe、Alpha |
| `LOWER_IS_BETTER` | 越低越好 | Volatility、Maximum Drawdown、费率 |
| **`TARGET_RANGE`** | 接近目标区间越好 | **Beta** |
| **`STRATEGY_DEPENDENT`** | 随 `Evaluation Profile` 而定 | **Tracking Error** |

`FS:184`：「**注意**：上游没有 `TARGET_IS_BETTER` 这一取值。」
`FS:188`：「**严禁通过字段名称自动推断方向。**」方向由 `Evaluation Policy` 的 `preference_directions` 显式声明（`FS:197`、`FE:521`）。

### 2.4 按类别分组的 SCORING 清单

> 「进入 SCORING 的 Factor」按 `FE:170-177` §7.1 的类别归组；Usage 五列取值逐行抄自 `BR:953-975`；Preference Direction 抄自 `BR:771-777`（§10.1）、`BR:795-803`（§11.1）、`BR:817-820`（§11.3）、`BR:830-838`（§12.1）、`BR:884-893`（§13.2）、`BR:250-258`（§5.2.1 差异矩阵）。

#### RET —— Return Score（`FE:172`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST | Preference Direction | 出处 |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| 年化收益率 | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:955` / `BR:773` |
| Benchmark 超额收益 | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:957` / `BR:775` |
| Rolling Return | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:958` / `BR:777`、`BR:888` |

> ⚠️ **口径冲突（需实现方裁决）**：`Rolling Return` 在 `FE:172` 归入 `RET`，但在 `BR:888`（§13.2 稳定性类）也列为稳定性指标；`BR:242`（§5.2.1 基础指标集）把它归在「收益」类。**文档未统一**它进哪个子分。
> ⚠️ **`分周期收益率`**：`BR:242`、`BR:776` 声明其方向为 `HIGHER_IS_BETTER`，但**它在 `BR:953-975` 的 Usage Matrix 里没有独立行**，`FE:172` 的 RET SCORING 清单也没列它。**文档未给它的 Usage 取值**。

#### RISK —— Risk Score（含 Drawdown）（`FE:173`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST | Preference Direction | 出处 |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| Volatility | ✓ | ✓ | ✓ | **✓** | ✓ | `LOWER_IS_BETTER` | `BR:959` / `BR:797` |
| Downside Volatility | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:960` / `BR:798` |
| Maximum Drawdown | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:961` / `BR:799` |
| VaR 95% | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:962` / `BR:800` |
| CVaR 95% | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:962` / `BR:801` |

> `BR:962` 把 `VaR 95% / CVaR 95%` 写在**同一行**（同一组 Usage 取值）。
> `BR:807`：「**Maximum Drawdown 是第一阶段的核心风险指标**」。
> `BR:809`：「VaR 与 CVaR 必须**成对使用**——单看 VaR 会低估尾部风险」。
> `BR:960`：Volatility 是唯一 `PORTFOLIO` 打勾的风险因子（另有 Beta、Correlation/Covariance）。

#### RAP —— Risk-Adjusted Score（`FE:174`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST | Preference Direction | 出处 |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| Sharpe | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:964` / `BR:832` |
| Sortino | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:964` / `BR:833` |
| Calmar | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:964` / `BR:834` |
| **费率**（管理费 + 托管费 + 销售服务费） | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:974` / `BR:986` |

> `BR:964` 把 `Sharpe / Sortino / Calmar` 写在**同一行**。
> 费率归入 RAP 子分是 `FS:129` 的定案（见 §1.3）；`FE:177` 把它单列为「基金属性」行，注明「非计算得出的 Factor，但参与评分」。
> `BR:986` 读表规则 4：「**费率不是计算得出的 Factor**，而是 `Fund Data`（Stage ①）的基金属性……其 Preference Direction 为 `LOWER_IS_BETTER`，在 Passive Equity 画像下为高权重项」。

#### STAB —— Stability Score（`FE:175`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST | Preference Direction | 出处 |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| Win Rate | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:969` / `BR:886` |
| Rolling Sharpe | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER`；其**波动**为 `LOWER_IS_BETTER` | `BR:971` / `BR:889` |
| Rolling Volatility | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:971` / `BR:890` |
| Rolling Maximum Drawdown | ✓ | ✓ | ✓ | — | ✓ | `LOWER_IS_BETTER` | `BR:971` / `BR:891` |

> `BR:971` 把 `Rolling Sharpe / Volatility / MDD` 写在**同一行**。
> `BR:889` 的 Rolling Sharpe 方向是**双重的**：「`HIGHER_IS_BETTER`；其**波动**为 `LOWER_IS_BETTER`」——实现上这是两个派生量。
> **Win Rate 参数**（`BR:895-907` §13.3）：统计周期**可配置**（日/周/月/滚动窗口/持有期），**第一阶段默认「月度（monthly）」**；基准**已定案 = 绝对正收益**（可配置为跑赢 Benchmark），`BR:905`。
> **滚动窗口**（`BR:911` §13.4）：「第一阶段至少支持 **12 个月滚动窗口**」，且「系统必须支持**观察滚动序列本身**，而不只是最新值」。
> `BR:931` §13.6：「稳定性指标的作用是**惩罚不稳定**，而非奖励高收益。」

#### REL —— Relative Performance Score（`FE:176`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST | Preference Direction | 出处 |
|---|:-:|:-:|:-:|:-:|:-:|---|---|
| Alpha | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER`（**Passive Equity 下不进评分**） | `BR:965` / `BR:835`、`BR:253` |
| Beta | ✓ | ✓ | ✓ | **✓** | ✓ | **`TARGET_RANGE`** | `BR:966` / `BR:836`、`BR:819` |
| Information Ratio | ✓ | ✓ | ✓ | — | ✓ | `HIGHER_IS_BETTER` | `BR:967` / `BR:837` |
| Tracking Error | ✓ | ✓ | ✓ | — | ✓ | **`STRATEGY_DEPENDENT`** | `BR:968` / `BR:838`、`BR:820` |

### 2.5 四类画像下的方向/权重差异矩阵（`BR:250-258` §5.2.1，**已定案，不得改动**）

| 指标 | Active Equity | Passive Equity | Bond | Hybrid |
|---|---|---|---|---|
| **Tracking Error** | 中性 · 配合 IR 判读 | **`LOWER_IS_BETTER` · 核心** | 不适用 | `STRATEGY_DEPENDENT` |
| **Alpha** | **`HIGHER_IS_BETTER` · 核心** | **不进评分** | `HIGHER_IS_BETTER` | `HIGHER_IS_BETTER` |
| **Information Ratio** | **`HIGHER_IS_BETTER` · 核心** | 不适用 | 中等权重 | 中等权重 |
| **Beta** | `TARGET_RANGE` | `TARGET_RANGE` ≈ 1 | `TARGET_RANGE` | `TARGET_RANGE` |
| **Maximum Drawdown** | 高权重 | 中 · 随指数波动 | **最高权重** | 高权重 |
| **费率** | 中等权重 | **高权重** | 中等权重 | 中等权重 |
| **R²** | 仅 `DISPLAY` | 仅 `DISPLAY` · 高即跟踪良好 | 仅 `DISPLAY` | 仅 `DISPLAY` |

**三处反直觉之处（`BR:260-269`，`FE:536-542` §17.3 要求必须保留）**：

1. **被动型基金的 Alpha 不进入评分** —— 「显著正 Alpha 说明跟踪偏离，把它当正向指标等于奖励跟踪不好的指数基金」（`FE:540`）
2. **被动型基金的费率是高权重项** —— 「同质 ETF 的长期差异主要来自费率与跟踪误差」（`FE:541`）
3. **债券型基金的 Maximum Drawdown 权重最高** —— 「否则评分会系统性偏好高信用下沉产品」（`FE:542`）

`FE:787` C-8：「四类画像的指标集合与方向已定案，本域不得改动」。

**四类 Evaluation Profile 枚举**（`BR:233`、`FE:518`）：`Active Equity` · `Passive Equity` · `Bond` · `Hybrid`。

### 2.6 两个非单调方向的处理（`FS:201-208` §6.3）

| Factor | 方向 | 处理 |
|---|---|---|
| **Beta** | `TARGET_RANGE` | 转换为**偏离目标区间的程度**再取分位；目标区间未定义时 `UNAVAILABLE`，**不得默认按越低越好** |
| **Tracking Error** | `STRATEGY_DEPENDENT` | 按画像分治：Passive Equity 为 `LOWER_IS_BETTER`；Active Equity 中性、配合 IR 判读；Bond 不适用；Hybrid 待定 |

⚠️ **Beta 目标区间的具体取值：文档未给值** —— `FS:208` `<TBD-FS-2>` = `BR:2555` `P1-22`（见 §14）。

---

## 3. 明确不进入 SCORING 的 Factor

### 3.1 清单（`FE:179-189` §7.2，逐行抄录）

| Factor | 原因 |
|---|---|
| 累计收益率 | 与年化收益率重复 |
| Drawdown / Recovery Duration | 仅 `DISPLAY` / `SCREENING` |
| **R²** | 仅 `DISPLAY` |
| **Skewness / Kurtosis** | 仅 `DISPLAY`（`<TBD-P1-6>` 待确认） |
| **Correlation / Covariance** | 是基金**之间**的关系，不是单只基金属性，无法进入单基金评分 |
| **Fund Score 自身** | Score 不能参与计算自己 |

### 3.2 Usage Matrix 中对应的 SCORING 列取值（`BR:956-975`）

| Factor | DISPLAY | SCORING | SCREENING | PORTFOLIO | BACKTEST |
|---|:-:|:-:|:-:|:-:|:-:|
| 累计收益率 | ✓ | **—** | ✓ | — | ✓ |
| Drawdown / Recovery Duration | ✓ | **—** | ✓ | — | ✓ |
| **R²** | ✓ | **—** | ✓ | — | ✓ |
| **Skewness / Kurtosis** | ✓ | **—** | ✓ | — | ✓ |
| **Correlation / Covariance** | ✓ | **—** | — | **✓** | ✓ |
| **Fund Score** | ✓ | — | ✓ | **权重映射规则**（§19.2） | ✓ |

### 3.3 补充理由

- **R²**（`BR:917-927` §13.5）：「**R² 高不代表基金"稳定"或"优秀"**」；「**R² 不得直接作为基金优劣的判断指标**，只作为描述性指标与风格分析的辅助」；「R² 的 `Factor Usage` 第一阶段建议为 `DISPLAY` + `SCREENING`，**不建议**直接进入 `SCORING`」。
- **Skewness / Kurtosis**（`BR:977-979` **已定案 · 2026-08-27**）：「Skewness / Kurtosis **第一阶段不纳入 SCORING**，仅 `DISPLAY`。」依据：「**分布类指标进入评分的前提是先确定其 Preference Direction**，而偏度的方向依策略而异（正偏对进取型是优点、对稳健型未必），峰度则几乎总是「越低越好」但其区分度在基金层面很弱。在方向未定之前纳入评分，等于给一个方向不明的量赋权重。」
  > ⚠️ 注意：`BR:892-893` 仍给出了 Skewness = `HIGHER_IS_BETTER`、Kurtosis = `LOWER_IS_BETTER` 的方向声明，但这**不改变**它们不入 SCORING 的结论。`FE:186` 仍把它标为 `<TBD-P1-6>` 待确认 —— **该 TBD 实际已在 `BR:2539` 关闭**，`FE` 未同步。
- **Correlation / Covariance**（`BR:983` 读表规则 1）：「它们是基金**之间**的关系，不是单只基金的属性，无法进入单基金评分。它们的用途在 `PORTFOLIO`。」
- **Fund Score**（`BR:984` 读表规则 2）：「**`Fund Score` 自身不是 Factor**，但可作为 SCREENING 条件与组合层的权重映射规则输入。它在 SCORING 列为空——Score 不能参与计算自己。」
- `BR:985` 读表规则 3：「**`PORTFOLIO` 列极少打勾是正常的**——组合构建消费的主要是 `Return Estimate` 与 `Σ`，而非单基金评分类指标。」

---

## 4. Factor Result 的 Status 语义与评价域处理规则

### 4.1 核心原则（`FE:190-199` §7.3）

`FE:192`：

> **本域消费的不是裸数值，而是带 `Status` 的 Factor Result**（`04-factor/08-factor-output` §2）。

⚠️ `04-factor/08-factor-output` **不存在**，Status 枚举的**权威定义缺失**，此处四值仅从消费方反推。见 §15。

### 4.2 四种 Status 与本域处理（`FE:194-199`，逐行抄录）

| Status | 本域处理 |
|---|---|
| `VALID` | 正常参与 |
| `WARNING` | 参与，但标记须随评价结果传递 |
| `INVALID` | **不参与**，且触发告警 |
| `UNAVAILABLE` | **不参与**，按 §12 缺失规则处理 |

### 4.3 Status 向 Evaluation Status 的传导

| Factor Status | 后果 | 出处 |
|---|---|---|
| 任一 Factor `INVALID` | `evaluation_status = FAILED`，**须告警** | `FE:391`、`FE:659` |
| 部分 Factor `UNAVAILABLE` | `evaluation_status = PARTIAL`，须带 `data_completeness` | `FE:390` |
| 全部要求的 Factor 可得 | `evaluation_status = COMPLETED` | `FE:389` |

### 4.4 Status 在评分层的处理（`FS:573` §13.2 步骤 ③）

> ③ 剔除 UNAVAILABLE / INVALID 的因子，记录排除原因

`FS:458-467` §10.4：「被排除的因子必须记录**为什么被排除**，而非从归因中消失。」示例格式（`FS:462-467`）：

```
Sortino Ratio : UNAVAILABLE
  原因        : MAR 未配置
  原权重      : X%
  重分配至    : Sharpe（+X%）、Calmar（+X%）
```

`FS:469`：「否则用户无法解释"为什么 Sharpe 的贡献比配置的权重高"。」

### 4.5 `UNAVAILABLE` 不参与分位计算（`FS:241-250` §7.4）

```
Peer Group 有 N 只基金
其中 M 只的 3Y Sharpe 为 UNAVAILABLE（成立不足 3 年）
    → 分位在剩余 (N − M) 只中计算
    → 那 M 只的 3Y Sharpe 标准化值同样为 UNAVAILABLE
```

`FS:250`：「**不得**把 `UNAVAILABLE` 当作最差值参与排名。」

### 4.6 必须区分 `0` 与 `UNAVAILABLE`（`FS:368-377` §9.1）

```
Factor Value = 0        →  该指标算出来就是 0（如 Alpha = 0，正常结果）
Factor = UNAVAILABLE    →  该指标算不出来（成立不足、除零、Benchmark 缺失）
```

`FS:377`：「把后者当作前者，等于宣称"数据不足 = 表现最差"。」

---

## 5. Analysis Period 的精确语义

### 5.1 支持的周期（`BR:701-711` §9.1）

```
1M · 3M · 6M · 1Y · 3Y · 5Y
```

| 层次 | 周期 | 参考价值 |
|---|---|---|
| 短期 | 1M / 3M | 低——易受单次市场波动影响 |
| 中期 | 6M / 1Y | 中 |
| 长期 | 3Y / 5Y | 高——更能反映持续能力 |

`FE:206-211` §8 沿用同一组，分为「短周期 `1M`/`3M`/`6M`」与「中长周期 `1Y`/`3Y`/`5Y`」，并声明「**沿用 `02-business-requirements` §9 已定义的周期，不新增。**」

### 5.2 每个 Period 必须显式声明的五项语义（`BR:717-725` §9.2）

| 语义项 | 需要定义的内容 |
|---|---|
| **周期类型** | Calendar Period（自然日历）还是 Trading-day Period（交易日计数） |
| **起止日包含规则** | 区间是 `[start, end]`、`(start, end]` 还是其他 |
| **年化规则** | 年化因子取值（252 交易日 / 365 自然日 / 12 月），必须全平台统一 |
| **非交易日处理** | 区间端点落在非交易日时，前移还是后移 |
| **基金成立日处理** | 成立日当天是否计入；成立日净值是否作为起点 |

### 5.3 第一阶段口径（`BR:727-737` §9.2.1，**已定案 · 2026-08-25**，P0-1）

`BR:729`：「**全部指标统一采用 Trading-day Period，年化因子 `252`。**」

| 项 | 取值 |
|---|---|
| 周期类型 | **Trading-day Period**（交易日计数） |
| 年化因子 | **252** |
| 起止日包含规则 | `(start, end]`——区间收益不含起始日当日 |
| 非交易日处理 | 区间端点落在非交易日时**向前取最近交易日** |
| 基金成立日 | 成立日净值作为序列起点，成立日当日不计入收益区间 |

**为什么不用混合口径**（`BR:739`）：「Sharpe 的分子是超额收益、分母是波动率。若收益按 365 年化、波动率按 252 年化，两者年化基准不同，Sharpe 会产生约 `√(365/252) ≈ 1.20` 倍的系统性错配，Sortino、Calmar、Information Ratio 同理。」

**日历口径的例外用途**（`BR:741`）：「系统必须在展示层**额外提供一份日历口径收益**（自然月/自然年），专用于与基金公司公布数据核对。该口径**仅用于展示与核对，不参与任何评分、筛选、组合构建或回测计算**（见 §29.1）。」

**不可逆性**（`BR:743`）：「口径变更会使全部历史回测结果与新口径不可比。变更须按 §23.2 的 **Major** 级处理——重新完整回测并重走 Approval。」

`FE:232`：「全平台统一 **252 交易日**（P0 已定案，`02-business-requirements` §9.2.1）。本域不重复定义。」

### 5.4 成立时间不足的处理（`BR:751-762` §9.4）

`BR:753`：「**绝对禁止补齐数据。**」

| 做法 | 是否允许 |
|---|---|
| 标记该周期指标为 `UNAVAILABLE` | ✅ 必须 |
| 该指标不参与依赖它的评分项 | ✅ 必须 |
| 用起始日至今的数据"年化"当作 3Y 指标 | ❌ 严禁 |
| 用同类平均值 / 零 / 行业均值填充 | ❌ 严禁 |

**理由**（`BR:762`）：「人为填充会让新基金在长期指标上获得虚假数值，且这类失真**在回测中完全不可见**——因为填充逻辑在历史和当下是一致的，回测无法暴露它。」

`FE:320`：「基金成立时长 < 周期长度 → 该周期全部 Factor **`UNAVAILABLE`**，**不得**用成立至今年化冒充」
`FE:651`（Edge Case）：「基金成立时长 < 评价周期 → 该周期全部 Factor `UNAVAILABLE`，`evaluation_status = NOT_ELIGIBLE`；**不得用成立至今年化冒充**」

### 5.5 长期与短期的权重关系（`BR:745-749` §9.3）

`BR:747`：

> **默认评分方案应体现长期表现的重要性。**

`BR:749`：「**但不要求**所有长期指标的权重逐项高于短期指标——不同策略中，短期指标可能承担不同作用（如短期动量因子）。具体权重由 `Strategy Version` 配置，这与 §32 的可配置性要求一致。」

⚠️ **具体权重数值：文档未给值。**

### 5.6 本域的周期推荐（`FE:212-228` §8.1）

`FE:214`：「不同 `Evaluation Profile` 可声明不同的周期集合与权重。短周期噪声大，长周期覆盖基金少——两者的取舍属评价政策，不在本文档拍板。」

`FE:216`：

> **推荐默认 · 2026-08-27**：各 Profile 统一采用 **{1Y, 3Y, 5Y}** 三周期，权重 **3Y > 1Y > 5Y**。业务方可改。

| 周期 | 作用 | 权重考虑 | 出处 |
|---|---|---|---|
| 1Y | 反映近期表现与当前管理状态 | 中 —— 有效但噪声较大 | `FE:222` |
| **3Y** | 覆盖一轮完整市场周期 | **最高** —— 噪声与时效性的平衡点 | `FE:223` |
| 5Y | 检验长期一致性 | 低 —— 覆盖率下降明显（成立满 5 年的基金显著少于满 3 年） | `FE:224` |

`FE:226`：「**不含 1M / 3M / 6M**：短于 1Y 的周期噪声主导（`FE-3` 已论证），纳入评分会引入随机性。」
`FE:228`：「**5Y 权重最低的实际原因是覆盖率** —— 给它高权重会让大量成立 3~5 年的基金因缺该周期而触发权重重分配，使不同基金的实际周期结构不一致。」

> ⚠️ 这是**「推荐默认」而非定案**：`FE:798` 的 `FE-2`「各 Evaluation Profile 的周期集合与周期间权重」**仍未关闭**，责任方为投研。**周期间的具体权重数值：文档未给值。**

### 5.7 最少可评价周期（`FE:324-338`，**已定案 · 2026-08-27**，`FE-3` 关闭）

`FE:324`：

> **已定案 · 2026-08-27**：**至少需 1Y 周期可评价**才产出总分；仅 1M / 3M / 6M 可算时该基金 `NOT_ELIGIBLE`。

依据（`FE:328-331`）：

```
1M 收益 ≈ 21 个交易日
    → 单日极端行情即可主导整月表现
    → 据此产出的「总分」是在给运气打分
```

`FE:334`：「**1Y 是最短的可承载完整评价的周期**：它覆盖至少一个完整的申赎周期与分红周期，且与 `04-factor` 多数因子的最短有意义窗口一致。」
`FE:336`：「**`NOT_ELIGIBLE` 而非「低置信总分」**：与 §14.1 的语义一致 —— 成立不足是「不该评」而非「该评但评坏了」，因此不产出、不告警。新基金天然如此，不是异常。」
`FE:338`：「**短周期因子仍照常计算与展示** —— 本条限制的是**总分**的产出，不是因子的产出。」

### 5.8 排名必须显式声明周期（`FR:132-140` §4.1）

```
同一只基金：
  1Y  Rank = 5 / 120
  3Y  Rank = 80 / 95
```

`FR:140`：「**两个排名都正确**，但含义完全不同。不声明周期的排名是无意义的。」

---

## 6. Fund Score 的结构

### 6.1 五子分名称

见 §1.2（`FS:91-102`、`BR:999-1010`）。命名固定，不得增删改。

### 6.2 子分与 Factor 类别的对应（`FS:117-125` §4.3）

| 子分 | Factor 类别 |
|---|---|
| Return Score | `RET` |
| Risk Score | `RISK`（含 Drawdown） |
| Risk-Adjusted Score | `RAP` |
| Stability Score | `STAB` |
| Relative Performance Score | `REL` |

### 6.3 Score Scale（`FS:139-151` §5.1）

```
0 – 100
100 = Best
  0 = Worst
```

`BR:1019` / `FS:150` 示例：「某基金 3Y Sharpe 在 Peer Group 内位于前 10% → Sharpe Score = 90 / 100」

**分数的含义是相对位置**（`FS:153-167` §5.2）：

```
80 分 ≠ "这只基金很好"
80 分 =  "在这个 Peer Group 内，它排在约前 20%"
```

推论两条（`FS:165-167`）：

| 推论 | 说明 |
|---|---|
| 跨 Peer Group 不可比 | 弱组的 80 分与强组的 80 分含义不同 |
| **必须与组内绝对水平同屏展示** | 否则读者无法判断"80 分在这一组意味着什么"（沿用 `02-business-requirements` §16.3.1 对 Tier 的强制要求） |

### 6.4 合成公式（`FS:256-263` §8.1，一字不差）

```
Weighted Contribution_i  =  Normalized Score_i  ×  Weight_i

Sub-Score_k              =  Σ  Weighted Contribution_i        （i ∈ 子分 k 的因子集合）

Total Score              =  Σ  Sub-Score_k × Weight_k          （k = 五个子分）
```

### 6.5 权重从哪来

#### 6.5.1 两层权重（`FS:266-273` §8.2）

| 层 | 内容 |
|---|---|
| **因子层** | 子分内部各 Factor 的相对权重 |
| **子分层** | 五个子分在总分中的相对权重 |

#### 6.5.2 归一化约定（`FS:283` §8.3，**已定案 · 2026-08-27**，`FS-3`）

> **已定案 · 2026-08-27**：权重归一化约定 **`Σ = 1`**（小数），不用 `Σ = 100`。

依据（`FS:285`）：「与 `10-api/01-api-overview` §12.1「百分比统一用小数」一致。**同一份 API 响应内不能有两种量纲**」；`FS:287`：「**展示层可乘 100 呈现为百分比**，但那是渲染，不是存储与传输的约定。」

#### 6.5.3 权重取值的产生流程（`FS:289-304` §8.4，`BR:274-361` §5.2.1.1）

`FS:293-297`：

```
先有验证数据（IC / ICIR / 分层单调性）
        ↓
再定权重
```

`FS:299`：「**不得事先拍板权重**。本节定义的是权重的**结构与约束**，不是取值。」

`FS:301-304`：

```
Factor Weight     = EQUAL_WITHIN_VALID     ← 第一版方案，已定案 2026-08-27
Sub-Score Weight  = 由 Profile 定义         ← 见 §8.5 已定案的相对高低
```

`BR:278`：「**明确禁止**：现在拍一个 25% / 25% / 25% / 25%。」
`BR:280-286` 的正确流程：

```
❌ 反向流程
Profile → 人工给 25% → 找因子证明合理

✅ 正确流程
Factor → 有效性检验 → 因子筛选 → 剔除冗余 → 权重优化 → 版本化
```

#### 6.5.4 第一版：有效因子内等权（`FS:306-325` §8.4.1，**已定案**）

```
某子分的候选因子经有效性检验后：
    Sharpe        valid
    Sortino       valid
    Max Drawdown  valid
    Calmar        invalid

→ 各 valid 因子权重 = 1 / (valid 因子数) = 33.33%
→ Calmar 权重 = 0，且【在归因中留痕】
```

| # | 规则 | 出处 |
|---|---|---|
| 1 | 权重之和为 1，**在有效因子内**归一 | `FS:322` |
| 2 | `invalid` 因子权重恰为 **0**，但**必须出现在归因链中**并标注失效原因（§10.4）—— 否则无法回答「为什么这只基金的 Calmar 没影响分数」 | `FS:323` |
| 3 | **权重来源须落库为 `EQUAL_WITHIN_VALID`**，与第二版的 `OPTIMIZED` 区分 | `FS:324` |

#### 6.5.5 检验未产出时 Score 不可投产（`FS:327-346` §8.4.2）⚠️

```
❌ 「先按等权上线，等检验出来再调」
   → 与「未经检验就拍权重」完全等价
   → 差别只是拍的值恰好是等权

✅ 检验未产出 → Score 状态 NOT_AVAILABLE，不产出总分
```

| 情形 | 处置 | 出处 |
|---|---|---|
| 有效性检验已产出 | 按 §8.4.1 计算 | `FS:341` |
| **检验尚未产出** | **该 Profile 的 Score 不产出**，`score_status = VALIDATION_PENDING` | `FS:342` |
| 某子分内全部因子 `invalid` | 该子分 `UNAVAILABLE`，总分按剩余子分处理 | `FS:343` |
| 有效因子数低于阈值 | 该子分标 `INSUFFICIENT_FACTORS`（§9.3） | `FS:344` |

`FS:346`：「`factor_effectiveness` 的存在性是 Score 产出的前置条件，不是可选的补充信息。」

**有效性阈值（推荐默认，非定案）**：`FS:348`「IC ≥ 0.02、|ICIR| ≥ 0.3」；`BR:345` 展开为「**IC 均值 ≥ 0.02** 且 **|ICIR| ≥ 0.3**；检验区间 = **全历史滚动 + 最近 3 年双段均须通过**。业务方可改。」`BR:350`：「因子间**相关系数 > 0.8** 视为冗余，保留 **|ICIR| 较高者**。业务方可改。」
`FS:350`：「**本域是消费方不是定义方**：阈值属 `validation_policy`，由 `04-factor` 产出检验数值、由该 Policy 判定 `VALID` / `INVALID`，本域只按判定结果分配权重。」

#### 6.5.6 权重差异化已定案的部分（`FS:356-362` §8.5，**本域不得改动**）

| Factor | 已定案的权重要求 |
|---|---|
| **费率** | Passive Equity 下为**高权重**项 |
| **Maximum Drawdown** | Bond 下为**最高权重** |
| **Alpha / IR** | Active Equity 下为**核心**项 |
| **Tracking Error** | Passive Equity 下为**核心**项 |
| **Alpha** | Passive Equity 下**不进评分**（权重为 0） |

⚠️ **具体权重数值：文档未给值**（`BR:361`：「**权重属于 `Scoring Version` 的配置项**……应由因子有效性检验结果决定，而非事先拍板」）。

### 6.6 缺失因子处理策略（`FS:379-411` §9.2 / §9.3，`BR:1030-1039` §15.5）

| 处理方式 | 是否允许 | 对应策略名 |
|---|---|---|
| 该指标不参与评分，**权重按比例重分配**给同组其他可用指标 | ✅ **推荐** | `EXCLUDE_AND_RENORMALIZE` |
| 该子分标记 `UNAVAILABLE`，总分标注 `Data Completeness` | ✅ 允许 | `PARTIAL_SCORE` |
| 用同类均值 / 中位数填充 | ❌ **严禁** | —— |
| 按 0 分参与评分 | ❌ **严禁** | —— |

`FS:390`：「**这不是 TBD** —— 上游已定案推荐 `EXCLUDE_AND_RENORMALIZE`。待定的只是**触发降级的阈值**。」

**降级阈值已定案**（`FS:405`）：

> **已定案 · 2026-08-27**：子分内有效指标数 **< 2** 时该子分 `UNAVAILABLE`，**不做权重重分配**。

依据（`FS:407`）：「**单一指标构成的子分等于该指标本身** —— 「Risk-Adjusted 子分」若只剩 Sharpe 一项，它就不再是一个聚合度量，而是被重命名的 Sharpe。」
`FS:411`：「**阈值取 2 而非更高**：两个指标已构成最小的「聚合」，且提高阈值会让数据不全的基金大面积失去子分。」

### 6.7 `Data Completeness` 的定义与呈现要求

**定义**（`FS:418`，一字不差）：

```
data_completeness = 可用指标数 / 应有指标数
```

`FE:372`（Evaluation Output 字段表）：「`data_completeness` | 可用指标数 / 应有指标数」

**必须如何随输出呈现**：

| 要求 | 原文 | 出处 |
|---|---|---|
| 必须随**评价结果**呈现 | 「基于 3 个指标与基于 12 个指标的评价，可信度完全不同（上游术语表）。它是**输出的一部分**，不是可选的附加信息。」 | `FE:380` §13.1 |
| 必须随**评分**呈现 | 「**基于 3 个指标的 85 分与基于 12 个指标的 85 分，可信度完全不同**（上游术语表）」「它是**输出的必备字段**，不是可选的附加信息。」 | `FS:415`、`FS:421` §9.4 |
| 上游硬要求 | 「**`Data Completeness` 必须随评分一同呈现**」 | `BR:1039` §15.5 |
| 约束条目 | C-5「`Data Completeness` 必须随评价结果一同呈现」；C-6「`Data Completeness` 必须随评分呈现」 | `FE:784`、`FS:701` |
| `PARTIAL` 时强制 | 「`PARTIAL` … ✅ 须带 `data_completeness`」 | `FE:390` |
| Tier 场景 | 「`evaluation_status = PARTIAL` → 可产出 Tier，但 `data_completeness` 必须同屏呈现」 | `FC:373` |

### 6.8 评分的六项要求（`BR:991-993` §15.1，`FS:69` §3.1）

`BR:993`：

> `Fund Score`（Stage ③）必须同时满足：**可解释、可重复、可配置、可回测、可比较、可追溯**。

### 6.9 每个子分必须能回答的六个问题（`FS:104-115` §4.2，`BR:1012` §15.3）

`FS:106`：「**无法回答任一问题的评分方案不得上线**」

| # | 问题 |
|---|---|
| 1 | 使用了哪些指标 |
| 2 | 各自权重 |
| 3 | 如何标准化 |
| 4 | `Preference Direction` 是什么 |
| 5 | 缺失数据如何处理 |
| 6 | 如何汇总 |

> ⚠️ **§6.8 与 §6.9 是两组不同的「六项」**，实现计划中不要混为一谈。

### 6.10 归因链与逐因子必留的六项（`FS:431-456` §10.2 / §10.3）

归因链（`FS:435-443`）：

```
Total Score
    ↓  拆解
五个 Sub-Score + 各自权重
    ↓  拆解
各 Factor 的 Normalized Score × Weight = Weighted Contribution
    ↓  拆解
Factor Raw Value + Direction + Peer Group 内分位
```

逐因子必须保留六项（`FS:447-454`）：

| 字段 | 说明 |
|---|---|
| `factor_id` + `window` | 哪个因子、哪个窗口 |
| **`raw_value`** | 原始值（带量纲），用于人工核对 |
| **`normalized_score`** | 标准化后的分数 |
| **`direction`** | 该因子在本 Profile 下的方向 |
| **`weight`** | 权重 |
| **`weighted_contribution`** | `normalized_score × weight` |

`FS:456`：「**`raw_value` 不可省略** —— 只有标准化值时用户看不懂"0.83 分"从何而来」。

### 6.11 Normalization 归属与方法

- **归属**（`FS:44-54` §2.1）：「标准化与方向转换**已在 `04-factor/05-factor-normalization` 完成**，本域消费的是**已标准化、已统一方向**的值。」⚠️ 该文档不存在，见 §15。
- **方法已定案**（`FS:216`、`BR:1016`）：**Percentile Rank / Peer Group 内排名**。`FS:225`：「**这不是 TBD。**……未来若引入 Z-Score 或 Min-Max，属 Scoring Version 的 Major 变更。」
- **三条强制规则**（`FS:229-233` §7.2 / `BR:1024-1028` §15.4）：
  1. **标准化必须在 `Peer Group` 内进行**，且 Peer Group 独立于 Score 产生
  2. 必须按各 Factor 声明的 `Preference Direction` 转换，使**分数越高一律代表越优秀**
  3. `TARGET_RANGE` 与 `STRATEGY_DEPENDENT` 的转换规则必须由 `Evaluation Profile` 显式定义，**不得套用单调方向**
- **第一阶段默认不做异常值处理**（`FS:239`）：因为 Percentile Rank 对极值不敏感；「若未来改用 Z-Score，异常值处理将成为必需项——这是方法选择的连带后果，不可分开决策。」

### 6.12 Score 的边界（严禁项）

| 误用 | 后果 | 出处 |
|---|---|---|
| 把 Score 作为收益估计输入优化器 | **严禁**——Score 是无量纲相对量，`μ` 是有量纲绝对量 | `FS:83`、`FS:702` C-7、`FE:113` |
| 把 Score 直接映射为持仓权重 | 权重由 `Portfolio Optimization` 求解 | `FS:84` |
| 跨 Peer Group 比较 Score | **默认不可比**——股票型 80 分与债券型 80 分不是同一件事 | `FS:85`、`FS:703` C-8 |
| `收益率排名 = 基金评分` | **严禁** | `BR:997`、`FS:73`、`FR:158` |

### 6.13 Scoring Output 字段（`FS:583-591` §13.3）

| 字段 | 说明 |
|---|---|
| `fund_id` / `evaluation_period` / `as_of_date` | 标识 |
| **`total_score`** | 0–100 |
| **五个 `sub_score`** | 各自 0–100，命名固定 |
| **归因明细** | 逐因子六项（§10.3） |
| **`data_completeness`** | 可信度 |
| `score_status` | `COMPLETED` / `PARTIAL` / `UNAVAILABLE` |
| 五项版本引用 | §12.2 |

> ⚠️ **`score_status` 枚举不自洽**：`FS:590` 列 `COMPLETED` / `PARTIAL` / `UNAVAILABLE` 三值，但 `FS:342` 引入了第四个值 `VALIDATION_PENDING`，`FS:336` 还提到 `NOT_AVAILABLE`。**实现时需统一**（本digest不替你裁决）。

**五项版本引用**（`FS:528-534` §12.2）：`scoring_policy_version`、`evaluation_policy_version`、`factor_version`（Metric Version）、**`peer_group_version`**、`data_version`。
`FS:536`：「**缺 `peer_group_version` 则分数不可复现**」。

### 6.14 Scoring Process 八步（`FS:570-579` §13.2）

```
① 按 Evaluation Profile 取 Scoring Policy
② 逐因子取 Normalized Score（已由 04-factor 完成标准化与方向转换）
③ 剔除 UNAVAILABLE / INVALID 的因子，记录排除原因
④ 按 Missing Factor Policy 重分配权重（或标记子分 UNAVAILABLE）
⑤ 逐子分加权求和 → Sub-Score
⑥ 五子分加权求和 → Total Score
⑦ 计算 Data Completeness
⑧ 落归因明细
```

---

## 7. Evaluation Eligibility 与 Minimum Data Requirement

### 7.1 八项准入检查（`FE:279-290` §10.1，逐行抄录）

| # | 检查 | 不通过 |
|---|---|---|
| 1 | 基金在 `as_of_date` 存在于 `Fund Coverage` | `NOT_ELIGIBLE` |
| 2 | 基金在该时点存续（按当时的 `Fund Lifecycle Status`） | `NOT_ELIGIBLE` |
| 3 | 必需的 NAV 数据存在且质量非 `INVALID` | `NOT_ELIGIBLE` |
| 4 | 历史长度满足该 Evaluation Period 的最低要求 | `NOT_ELIGIBLE` |
| 5 | 该 Profile 要求的 Factor 可得 | 部分不可得 → `PARTIAL` |
| 6 | `REL` 类所需的 Benchmark 可得 | `REL` 子分 `UNAVAILABLE` |
| 7 | 需要 `R_f` 时其可得 | 相关 Factor `UNAVAILABLE` |
| 8 | 需要 `MAR` 时其可得 | 相关 Factor `UNAVAILABLE` |

### 7.2 「缺失数据不得转换为 0」的确切表述

**`FE:292-303` §10.2 全文**：

> ### 10.2 缺失数据不得转换为 0
>
> > **这是本域最容易犯的错误，且后果严重。**
>
> ```
> 把 UNAVAILABLE 当作 0 分参与评分
>     → "数据不足" 被表达为 "表现最差"
>     → 成立不足 3 年的优秀新基金，其 3Y Sharpe 得 0 分
>     → 系统性歧视新基金
> ```
>
> （`02-business-requirements` §15.5、`04-factor/05-factor-normalization` §5.3）

**其他等价表述**：

| 出处 | 原文 |
|---|---|
| `BR:1037` | 「按 0 分参与评分 \| ❌ 严禁——这把"数据不足"错误地等同于"表现最差"」 |
| `BR:1036` | 「用同类均值/中位数填充 \| ❌ 严禁」 |
| `FE:783` C-4 | 「缺失数据**严禁**转换为 0 或用均值填充」 |
| `FS:700` C-5 | 「缺失数据**严禁**按 0 分参与或用均值填充」 |
| `FS:377` | 「把后者当作前者，等于宣称"数据不足 = 表现最差"。」 |
| `FS:600`（Edge Case） | 「**全部五个子分均 `UNAVAILABLE`** → `total_score = UNAVAILABLE`，**不得输出 0 分**」 |
| `FS:688` D-13 | 「全部子分 `UNAVAILABLE` 时总分 `UNAVAILABLE`，**不输出 0**」 |
| `FE:746` | 「**缺失数据不得转换为 0** —— 会把"数据不足"表达为"表现最差"，系统性歧视新基金」 |

### 7.3 Minimum Data Requirement（`FE:313-338` §11）

`FE:315`：「**各 Evaluation Period 的最低观测要求，沿用 `04-factor/03-factor-definition` 各 Factor 的 `Min Obs` 声明。**」⚠️ 该文档不存在，见 §15。

| Period | 最低要求 | 出处 |
|---|---|---|
| 全部周期 | 该周期内各 Factor 各自的 `Min Obs`（多数为 `<TBD-FD-3>`） | `FE:319` |
| 基金成立时长 < 周期长度 | 该周期全部 Factor **`UNAVAILABLE`**，**不得**用成立至今年化冒充 | `FE:320` |

`FE:322`：「**本域不新增最低数据要求** —— 它是 Factor 层的属性，本域只消费其结果。」

⚠️ **`Min Obs` 的具体数值：文档未给值**，且被标记为 `<TBD-FD-3>`（该 TBD 定义在缺失文档中）。

**总分产出的最低周期要求**：见 §5.7（至少 1Y 周期可评价，`FE:324`）。

### 7.4 可投资性不影响评价资格（`FE:305-309` §10.3）

`FE:307`：

> **暂停申购的基金仍应被评价**（`02-business-requirements` §7.3）。

`FE:309`：「`Investment Eligibility` 是**筛选**维度，不是**评价**维度。两者正交——一只基金可以同时"评价优秀"且"当前不可买入"。可投资性在 `05-fund-selection` 处理。」
`FE:766` D-7：「**可投资性不影响评价资格**」。

### 7.5 Evaluation Input / Output 字段清单

**Input**（`FE:344-356` §12）：

| 输入 | 来源 | 必需 |
|---|---|---|
| `Fund ID`（Share Class 粒度） | `03-data` | ✅ |
| `Evaluation Period` | 请求参数 | ✅ |
| `as_of_date` | 请求参数 | ✅ |
| **Factor Results**（带 Status 与 Threshold Context） | `04-factor/08-factor-output` | ✅ |
| **Peer Group**（该时点构成） | 本域构建 | ✅ |
| **Evaluation Profile** | 本域，按基金判定 | ✅ |
| **Evaluation Policy Version** | 本域 | ✅ |
| Benchmark Results | `03-data` | `REL` 类必需 |
| `Risk-free Rate` 引用 | `03-data`，经 Threshold Resolver | 相关 Factor 必需 |
| `MAR` 引用 | 本域 Evaluation Policy，经 Threshold Resolver | 相关 Factor 必需 |
| Data Version | `03-data` | ✅ |

**Output**（`FE:362-374` §13）：`fund_id`、`evaluation_period`、`as_of_date`、**`evaluation_status`**、**Factor Results（原始值 + 标准化值 + Status）**、**`peer_group_id` + `peer_group_version`**、**`evaluation_profile`**、**`evaluation_policy_version`**、**`data_completeness`**、`data_version`、`factor_version`（Metric Version）。

`FE:376`：「**本输出不含 Total Score。** 合成属 `02-fund-scoring`。」

### 7.6 评价对象粒度（`FE:117-142` §5）

`FE:119`：「**评价对象是 `Fund`，粒度为 `Fund Share Class`。**」

| 情形 | 处理 | 出处 |
|---|---|---|
| 同一基金的多个 Share Class | **分别评价**，各自进入 Peer Group | `FE:127` |
| 展示层需要合并呈现 | 属展示层职责，不改变评价粒度 | `FE:128` |

`FE:130`（**已定案 · 2026-08-27**，`FE-1` 关闭）：「**同时进入**同一 Peer Group 参与排名；去重发生在 **Universe 层**（`05-fund-selection` `FSEL-6`）。」

三层的不同答案（`FE:134-137`）：

```
数据层：全部纳入      （Share Class 是最小数据单位，费率差异只能在此表达）
评价层：分别评价      （A/C 类费率不同 → 净值不同 → 因子值不同）
建仓层：去重          （组合不应同时持有同一产品的两个份额类别）
```

`FE:140`：「**把去重提前到评价层是错的** —— 那等于在不知道哪一类更优之前就先删掉一类。」
`FE:142`：「处理方式是**展示层提供「按基金去重」的视图开关**，不在数据层去重 —— 后者会改变分位的分母，破坏与其它横截面统计量的一致性。」

---

## 8. Evaluation Status

### 8.1 四态枚举（`FE:384-391` §14，逐行抄录）

| 状态 | 含义 | 可进入 Scoring |
|---|---|---|
| **`NOT_ELIGIBLE`** | 未通过 §10 的准入检查 | ❌ |
| **`COMPLETED`** | 全部要求的 Factor 均可得 | ✅ |
| **`PARTIAL`** | 部分 Factor `UNAVAILABLE`，其余可用 | ✅ 须带 `data_completeness` |
| **`FAILED`** | 计算过程异常（含 Factor `INVALID`） | ❌ **须告警** |

### 8.2 `NOT_ELIGIBLE` 与 `FAILED` 必须区分（`FE:393-403` §14.1）

`FE:395`：「沿用 `04-factor/07-factor-validation` §11.2 的原则。」⚠️ 该文档不存在，见 §15。

| | `NOT_ELIGIBLE` | `FAILED` |
|---|---|---|
| 含义 | **不该评**（成立不足、已清盘） | **该评但评坏了** |
| 是否正常 | 正常业务情形 | 系统问题 |
| 是否告警 | 否 | **是** |

`FE:403`：「混淆两者会产生大量无意义告警，掩盖真正的问题。」
`FE:768` D-9：「**`NOT_ELIGIBLE`（不该评）与 `FAILED`（评坏了）严格区分**」

### 8.3 不设 `NOT_STARTED`（`FE:405-407` §14.2）

> 提示词建议的 `NOT_STARTED` 属**执行状态**而非**评价状态**。按 `02-architecture/01-system-architecture` §10.5 的两类状态区分，执行进度由 `Execution Status`（`RUNNING`/`COMPLETED`/`BLOCKED`/`FAILED`/`CANCELLED`）表达，不混入业务状态枚举。

`FE:767` D-8：「Evaluation Status 四态，**不设 `NOT_STARTED`**」

### 8.4 同族状态枚举一览（实现时勿混用）

| 枚举名 | 取值 | 出处 |
|---|---|---|
| `evaluation_status` | `NOT_ELIGIBLE` / `COMPLETED` / `PARTIAL` / `FAILED` | `FE:388-391` |
| Factor `Status` | `VALID` / `WARNING` / `INVALID` / `UNAVAILABLE` | `FE:195-199` |
| `score_status` | `COMPLETED` / `PARTIAL` / `UNAVAILABLE`（另见 `VALIDATION_PENDING`） | `FS:590`、`FS:342` |
| `ranking_status` | `INSUFFICIENT_SAMPLE`（其余取值文档未给） | `FR:354` |
| `classification_status` | `INSUFFICIENT_SAMPLE`（其余取值文档未给） | `FC:241` |
| `Execution Status` | `RUNNING` / `COMPLETED` / `BLOCKED` / `FAILED` / `CANCELLED` | `FE:407` |
| Policy `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` | `FE:517`、`FS:482`、`FR:393` |

### 8.5 Evaluation 层 Edge Cases（`FE:649-661` §20，逐行抄录）

| 情形 | 处理 |
|---|---|
| 基金成立时长 < 评价周期 | 该周期全部 Factor `UNAVAILABLE`，`evaluation_status = NOT_ELIGIBLE`；**不得用成立至今年化冒充** |
| 基金在评价期内**转型** | 用当时的 `Fund Classification` 归组、当时的 `Evaluation Profile` 评价；转型前后的评价**不可直接比较** |
| 基金在评价期内**清盘** | 历史时点仍参与评价与 Peer Group（避免生存偏差）；当前时点 `NOT_ELIGIBLE` |
| 基金**暂停申购** | 正常评价 —— 可投资性不影响评价资格（§10.3） |
| Benchmark 不可得 | `REL` 类整类 `UNAVAILABLE`，其余维度正常，`evaluation_status = PARTIAL` |
| `R_f` 不可得 | Sharpe / Alpha / Beta `UNAVAILABLE`，**不得默认 `R_f = 0`** |
| `MAR` 未配置 | Sortino / Downside Volatility `UNAVAILABLE` |
| 同一 Peer Group 内 `MAR` 不一致 | 该组该 Factor `UNAVAILABLE` **并告警**（配置粒度错配） |
| Factor `Status = INVALID` | `evaluation_status = FAILED`，**须告警** |
| Peer Group 仅 1 只基金 | 标准化无意义 → 全部标准化值 `UNAVAILABLE` |
| 同一基金多个 Share Class | 各自独立评价（是否同组见 `TBD-FE-1`，已于 `FE:130` 定案为同组） |

---

## 9. MAR Policy

### 9.1 MAR 的本质与归属（`FE:427-436` §16）

`FE:429`：「**`MAR` 是 Evaluation Policy 的参数，本域拥有。**（上游 §5.5）」

| | `Risk-free Rate` | `MAR` |
|---|---|---|
| 本质 | 市场数据（**观测所得**） | 评价标准（**规定的**） |
| 归属 | `03-data` | **本域** |
| 解析依据 | `available_at ≤ decision_at` 的最大 `version` | `Effective Date` + `Evaluation Policy Version` |
| 变更含义 | 市场变了 | **我们改变了评价标准**，须走版本治理 |

### 9.2 强制约束：不得与 `R_f` 共用字段（`FE:438-440` §16.1）

> **即使某个 Policy 中 `MAR = Risk-free Rate` 使数值完全相同，也不得在模型层面设计成同一个字段。**（上游 §5.5.1）

`FE:786` C-7：「`MAR` 与 `R_f` 不得设计成同一字段」
`FE:747`：「**`MAR` 是评价标准不是市场数据** —— 即使数值等于 `R_f` 也必须独立建模，否则评价标准的变更会伪装成数据更新而绕过版本治理」

### 9.3 配置粒度必须与 Peer Group 对齐（`FE:442-446` §16.2）⚠️

**确切表述**（`FE:444`）：

> **同一 `Peer Group` 内的全部基金必须适用同一个 `MAR`**，否则组内 `Sortino` 不在同一标尺上却被放进同一分位排名（上游 §5.5.3）。

`FE:446`：「本约束由**本域**在构建 `Evaluation Policy` 时保证；`04-factor/05-factor-normalization` §5.4 在标准化前校验，不一致时该组该 Factor `UNAVAILABLE` 并告警。」

**粒度上限**（`FE:500-502`，**已定案 · 2026-08-27**）：

> **已定案 · 2026-08-27**：保持 `fund_category × currency`，不再细分。见 `04-factor/03-factor-definition` §2.2.4。
>
> **本域的连带约束**：粒度细于 Peer Group 会直接违反 §16.2 的组内一致性要求。因此本条不只是「暂不细分」，而是**细分的上限就是 Peer Group 的粒度**。

`FE:785` C-6：「同一 `Peer Group` 内必须适用同一 `MAR`」

### 9.4 三模式 + 第一版默认（`FE:448-470` §16.3，**已定案 · 2026-08-27**，`TBD-FE-4` = `04-factor` `TBD-FD-2` 关闭）

**`Evaluation Policy` 新增 `mar_configuration` 段**（`FE:454-460`，逐行抄录）：

| 字段 | 取值 | 说明 |
|---|---|---|
| **`mar_policy`** | `ZERO` / `RISK_FREE` / `CUSTOM` | **必填，无默认** |
| `mar_value` | 数值 | 仅 `CUSTOM` 模式必填 |
| `mar_quotation_basis` | 年化口径 | 仅 `CUSTOM` 模式必填 |
| `fund_category` | 分类 | 配置粒度维度之一 |
| `currency` | 币种 | 配置粒度维度之一 |

**三模式的解析结果**（`FE:464-468`，逐行抄录）：

| 模式 | `MAR_t` | 是否随时间变化 |
|---|---|---|
| **`ZERO`**（第一版默认） | `0` | 否 |
| `RISK_FREE` | `Rf_t`（按 `04-factor/03` §2.1.1 期限匹配，逐期取值） | **是** |
| `CUSTOM` | 配置值 | 否 |

**选 `ZERO` 的理由**（`FE:470`，一字不差）：「最容易解释、不依赖外部数据、不产生额外 PIT 问题、跨资产类别一致、避免 `Sortino → R_f → Currency → Tenor` 的耦合链。」

⚠️ `CUSTOM` 模式的 `mar_value` 具体数值：**文档未给值**（`FE:770` D-11：「**`MAR = TBD`**，本域不指定具体数值」，理由「属业务决策」）。

### 9.5 `mar_policy` 必填无默认（`FE:472-481` §16.3.1）⚠️

**确切表述**（`FE:474`）：

> **`ZERO` 是「第一版推荐取值」，不是「不填时的兜底」。**

| 状态 | 处置 |
|---|---|
| `mar_policy = ZERO` | 正常计算，Sortino 可用 |
| `mar_policy` 未配置 | **依赖 MAR 的 Factor 一律 `UNAVAILABLE`**，不得默认为 0 |

`FE:481` 全文：

> **两者算出来的数值完全相同，但含义相反**：前者是有人决定了标尺，后者是标尺从未被确认。若配置层给 `mar_policy` 设默认值 `ZERO`，一次配置遗漏就会静默产出看起来完全正常的 Sortino —— **没有任何信号表明这个值背后没有决策**。因此本字段在 Evaluation Policy 中**必填且无默认值**。

**受影响的 Factor**（`FE:657`）：「`MAR` 未配置 → Sortino / Downside Volatility `UNAVAILABLE`」

### 9.6 `RISK_FREE` 模式的连带后果（`FE:483-498` §16.3.2）

```
ZERO / CUSTOM  → MAR 在窗口内是标量
RISK_FREE      → MAR 在窗口内是【序列】，且随基金计价币种不同
```

| 影响 | 说明 |
|---|---|
| §16.2 的组内一致性 | 校验对象由「同一数值」变为「同一 `mar_policy` 且同一 `(currency, tenor)` 解析路径」 |
| Sortino 的可比性 | 同组内若存在多币种基金，`RISK_FREE` 下各自的 MAR 不同 —— **此时组内 Sortino 不可比** |
| `R_f` 的 quality 传导 | `R_f` 若为 `INTERPOLATED`，Sortino 的插值误差随之引入 |

`FE:498`：「**因此 `RISK_FREE` 模式在多币种 Peer Group 中不可用** —— 若将来启用该模式，Peer Group 的构建必须先按币种细分。这是切换模式前必须处理的前置条件，不是切换后再修的问题。」

> 注：`FR:105` 已把 `Currency` 定为 Peer Group 的强制划分维度（见 §11.4），该前置条件在排名域已被满足。

### 9.7 MAR 变更的版本归属（`FS:551-553` §12.4）

> `MAR` 变更升 **Evaluation Policy Version**，**不升 Scoring Version**。沿用 `04-factor/06-factor-versioning` §4.3。`MAR` 影响的是 `Sortino` 的**因子值本身**，发生在评分之前。

---

## 10. Risk-free Rate 依赖声明

### 10.1 本域只声明依赖（`FE:411-421` §15）

`FE:413`：「**本文档不重新定义 `Risk-free Rate` 的数据模型。**」

| 层面 | 归属 |
|---|---|
| 数据来源、`currency`/`tenor`/报价口径、PIT 规则 | **`03-data/01-data-source` §3.1.5、`02-data-domain-model` §10** |
| 在 Sharpe / Alpha / Beta 中的使用 | **`04-factor/03-factor-definition` §2.1** ⚠️ 缺失 |
| 本域 | **仅声明依赖关系** |

`FE:421`：「`R_f` 是 **Market Reference Input**——观测所得，全平台唯一，随市场变化，走 PIT。」

### 10.2 直接消费方（`FE:423`，一字不差）

> `R_f` 的直接消费方是 `F-RAP-001` Sharpe、`F-REL-002` Alpha、`F-REL-003` Beta。`F-REL-004` Information Ratio **不依赖 `R_f`**。

> ⚠️ **Factor ID 命名规则**（`F-RAP-001`、`F-REL-002` …）只在此处出现一次，完整的 26 个 Factor ID 表在缺失的 `03-factor-definition` 中。见 §15。

### 10.3 消费路径与不可得处理

| 项 | 内容 | 出处 |
|---|---|---|
| 传递方式 | 「`Risk-free Rate` 引用 \| `03-data`，经 **Threshold Resolver** \| 相关 Factor 必需」 | `FE:354` |
| 准入检查 | 检查 7：「需要 `R_f` 时其可得 → 相关 Factor `UNAVAILABLE`」 | `FE:289` |
| 不可得时 | 「`R_f` 不可得 → Sharpe / Alpha / Beta `UNAVAILABLE`，**不得默认 `R_f = 0`**」 | `FE:656` |
| Policy 字段 | `Evaluation Policy` 含 `risk_free_rate_convention`：「使用的 `(currency, tenor)` 口径」 | `FE:525` |
| 与分组字段一致 | 「`R_f` 的解析键 `(currency, tenor)` 中的 `currency` 与本条的划分维度**必须取自同一字段**（`fund_share_class.base_currency`），否则会出现「按 A 币种分组、按 B 币种解析利率」的错配。」 | `FR:116` |
| 审计留痕 | 追溯链含「Threshold Context → 所用的 `R_f` 版本引用」 | `FE:677` |

⚠️ **`(currency, tenor)` 的具体取值（用哪条曲线、哪个期限）：文档未给值。**

---

## 11. Peer Group

### 11.1 定义（`BR:481-487` §7.1，`FE:268`，`FR:79-83`）

`BR:483`：「`Peer Group` 是 `Fund Score` 的**标准化、排名、分位与分层的计算样本集**。」

```
Peer Group = Fund Classification  +  effective_at  +  参与规则
```

`FR:83`：「它是**标准化、排名、分位与分层的同一个计算样本集**——四者必须用同一个 Peer Group，否则不自洽。」
`FR:574` C-2：「标准化、排名、分位、分层必须用**同一个** Peer Group」

### 11.2 【禁止依赖 Score / Universe】的确切表述

**`BR:489-513` §7.2 全文要点**：

> ### 7.2 最关键的约束：Peer Group 必须独立于 Fund Score
>
> > **`Peer Group` 的构成不得依赖 `Fund Score` 或 `Fund Universe`。**
>
> **如果违反会发生什么**——形成循环依赖：
>
> ```
> Fund Score  →  Fund Universe  →  Peer Group  →  Fund Score
>      ▲                                              │
>      └──────────────────────────────────────────────┘
> ```
>
> 分数依赖样本集，样本集又依赖分数，结果既不唯一也不可复现。这是评分体系最隐蔽的一类设计错误——它不会报错，只会让每次重算得到不同的分数。

**正确的顺序**（`BR:505-513`，一字不差）：

```
Fund Coverage
     ↓  Fund Classification（客观属性，不依赖 Score）
Peer Group
     ↓  Factor 在 Peer Group 内标准化
Fund Score
     ↓  Eligibility Rules（可选叠加 Score 排序）
Fund Universe
```

**其他等价表述**：

| 出处 | 原文 |
|---|---|
| `FE:76` | 「**注意 `Peer Group` 的位置**：它由 `Fund Classification`（`03-data` 的客观属性）直接构建，**不经过 Score**。这是上游 §7.2 的强制约束——违反会形成 `Score → Universe → Peer Group → Score` 的循环依赖，使评分不可复现。」 |
| `FE:780` C-1 | 「`Peer Group` 必须独立于 `Fund Score` 产生 \| 上游 §7.2、`FR-PEER-001`」 |
| `FE:745` | 「**`Peer Group` 必须独立于 `Fund Score`** —— 否则形成循环依赖，评分不可复现；这类错误不会报错，只会让每次重算得到不同的结果」 |
| `FR:87` | 「**`Peer Group` 的构成不得依赖 `Fund Score` 或 `Fund Universe`**（上游 §7.2、`FR-PEER-001`）。」 |
| `FR:89` | 「违反会形成 `Score → Universe → Peer Group → Score` 的循环依赖——**它不会报错，只会让每次重算得到不同的排名**。」 |
| `FR:573` C-1 | 「`Peer Group` 必须独立于 `Fund Score` 与 `Fund Universe`」 |
| `FS:698` C-3 | 「标准化必须在 `Peer Group` 内，且 Peer Group 独立于 Score」 |

**同源原则 —— Evaluation Policy 也不得依赖 Factor/Score**（`FE:544-553` §17.4）：

```
factor-service → fund-service ：读 Evaluation Policy（配置）
fund-service   → factor-service ：读 Factor Result（数据）
```

`FE:553`：「两条依赖指向不同对象，**不构成循环**。但若 `Evaluation Policy` 反过来依赖 Factor 或 Score，两条依赖将闭合成真正的循环（`02-architecture/02-service-architecture` DEP-6）。」

> ⚠️ **命名撞名警告**（`FC:483`）：`04-fund-classification` 定义的是 `Fund Tier`，与上游 `Fund Classification` 撞名；「混淆两者会形成 `Score → Tier → Peer Group → Score` 循环依赖」。

### 11.3 构建 / 参与规则（`BR:515-525` §7.3，逐行抄录）

| 规则 | 内容 |
|---|---|
| **基础集合** | `Fund Coverage` 中属于该分类的全部基金 |
| **最低数据要求** | 该周期指标可计算（非 `UNAVAILABLE`）的基金才参与该指标的排名 |
| **是否包含已清盘基金** | **历史时点包含**——回测在 `T` 时点的 Peer Group 必须含当时存续的全部基金，包括后来清盘的（见 §26.2） |
| **是否包含不可投资基金** | **包含**——可投资性不影响评价。暂停申购的基金仍应被评分，只是不进入可建仓集合（见 §18） |
| **最小样本量** | **`MIN_PEER_GROUP_SIZE = 30`**（已定案 2026-08-27）。样本数低于该值时**不产出横截面派生量**（标准化值、分位、Tier），标 `INSUFFICIENT_SAMPLE`；原始因子值不受影响。详见 §7.3.1 |

`FR:93-99` §3.3 的复述基本一致，另加「最小样本量 \| 低于阈值时排名不具统计意义，标记低置信」。

### 11.4 划分维度（`FR:101-116` §3.4）

`FR:103`：「**上游已定为 `Fund Classification`**，本域不自行引入新维度。」

`FR:105`（**已定案 · 2026-08-27**，`FR-1` 关闭）：

> **`Currency` 必须作为 Peer Group 的划分维度；`Market` 不作为。**

| # | Currency 必须划分的理由 |
|---|---|
| 1 | **跨币种收益含汇率成分** —— 一只 USD 计价基金对 CNY 投资者的实际收益 = 基金收益 + 汇率变动。用未经汇率调整的收益直接排名，比较的不是管理能力 |
| 2 | **MAR 的 `RISK_FREE` 模式在多币种组中不可用**（`01-fund-evaluation` §16.3.2 已论证）—— 各基金的 MAR 随其计价币种解析出不同的 `R_f`，组内 Sortino 不在同一标尺 |

`FR:114`：「**Market 不作为划分维度**：同一币种下的不同上市地（如沪深两市）不影响收益的可比性，也不影响 `R_f` 的解析。按 Market 细分只会缩小组规模，触发更多 `INSUFFICIENT_SAMPLE`。」
`FR:116`：分组用的 `currency` 与 `R_f` 解析键的 `currency` **必须取自同一字段**（`fund_share_class.base_currency`）。

**所以第一版的划分维度 = `Fund Classification` × `Currency`。**

### 11.5 最小样本量（`BR:528-549` §7.3.1，**已定案 · 2026-08-27**，`P1-1` 关闭）

`BR:532`：「**定案**：`MIN_PEER_GROUP_SIZE = 30`，**不足时降级而非报错**。」

| 条件 | 处理 |
|---|---|
| `n_effective ≥ 30` | 正常标准化 → 排名 → 分层 |
| **`n_effective < 30`** | **不做横截面标准化、不做 Ranking、不做 Percentile Classification**，输出 `INSUFFICIENT_SAMPLE` |
| `n_effective = 1` | `percentile = null` |

`BR:540`：「**为什么是 30**：10 太小、20 仍易产生极端排名；30 是横截面分析的合理最低规模，也与统计上的小样本/大样本习惯边界一致、便于向业务解释。」
`BR:542`：「**判定基数是 `n_effective`（该指标的有效参与数）而非 `peer_group_size`** —— 一个 50 只基金的组里若某指标只有 25 只可算，该指标仍属小样本。」
`BR:544`：「**Raw Value 不受影响** —— 样本不足只影响**横截面派生量**（标准化值、分位、Tier），单基金的原始因子值照常产出。」
`BR:546`：「**三处必须使用同一个值**：`04-factor/05-factor-normalization` §5.2、`05-fund-evaluation/03-fund-ranking` §9.3、`05-fund-evaluation/04-fund-classification` §8.5。**配置来源唯一**，不得三处各自定义。」
`FR:345` 同义：「**三处必须用同一个值，且配置来源唯一** —— 不得三处各自定义常量。」
`FR:564` D-11：「最小样本量三处（标准化 / 排名 / 分层）必须用同一值」

### 11.6 PIT 属性与历史构成必须可重建

**`BR:551-557` §7.4**：

> **`Peer Group` 本身必须满足 PIT。**
>
> - 基金转型会改变其分类，进而改变它所属的 Peer Group
> - 回测在 `T` 时点必须使用 `available_at ≤ T` 的分类版本构成 Peer Group
> - 每个决策时点的 Peer Group 构成必须可重建

**`FE:263-273` §9.3 全文要点**：

> ### 9.3 Peer Group 的历史构成必须可重建
>
> > **这是本域可复现性的前提，也是最容易被漏掉的一项。**
>
> ```
> Peer Group = Fund Classification + effective_at + 参与规则
> ```
>
> 三者都必须按 PIT 记录。若历史 `Peer Group` 用当前成员构造，**全部分位、排名、Tier 都被污染**——且污染不可见（数值看起来完全正常）。
>
> 参与规则须包含**当时存续但后来已清盘的基金**（`02-business-requirements` §7.3），否则产生生存偏差。

`FE:782` C-3：「`Peer Group` 的历史构成必须可重建，且含当时存续、后已清盘的基金」
`FR:575` C-3：「历史时点的 Peer Group 必须含当时存续、后已清盘的基金」

**`peer_group_version` 是可复现性的隐含第七要素**（`FE:574-584` §18.2）：

```
同一基金、同一时点、同一 Factor Version、同一 Policy Version
但 Peer Group 构成不同（如某只同类基金的分类被修订）
    → 分位不同 → 标准化值不同 → 评价结果不同
```

`FE:584`：「**因此评价输出必须记录 `peer_group_id` + `peer_group_version`**（§13）。这是本域可复现性中最容易被漏掉的一项。」
`FE:771` D-12、`FS:705` C-10 同义。

**可复现性六要素**（`FE:563-571` §18.1）：`Fund ID` + `as_of_date` + `Evaluation Period` + `Factor Version`（= Metric Version）+ `Evaluation Policy Version` + `Data Version` → 相同结果。**第七项 = `Peer Group Version`**。

### 11.7 Peer Group 与 Evaluation Profile 的关系（`BR:559-597` §7.5）

| | Peer Group | Evaluation Profile |
|---|---|---|
| 作用 | 决定**跟谁比** | 决定**用什么标准比** |
| 粒度 | 基金分类 | 主动/被动/资产类别 |
| 典型用途 | 分位排名的样本集 | 指标集合、权重、Preference Direction |

`BR:567`：「两者通常一致但不必然相同——同一 Peer Group 内可能存在不同 Evaluation Profile 的基金（如某些指数增强型基金）。」

**不一致时的处理（`BR:569-597`，已定案 · 2026-08-27，`P1-2` 关闭）**：

> **定案**：同一 Peer Group 内出现多个 Evaluation Profile 时，该组**不产出跨 Profile 的统一排名**，按 Profile 拆分为子排名集。

```
Peer Group「主动股票型」内含：
    Profile = Active Equity   的基金 120 只
    Profile = Passive Equity  的基金  15 只（指数增强型被归入该组）
        ↓
不产出 135 只的统一排名
        ↓
产出两个子排名：Active 120 只、Passive 15 只（后者 n < 30 → INSUFFICIENT_SAMPLE）
```

`BR:583`：「不同 Profile 的 Score 由不同指标集合加权而成 —— 它们是**不同量纲的两个数**，放进同一分位排名等于比较两个不同的东西。」
`BR:585`：「**这与 §16.2 的 MAR 一致性约束同源**……**两者是同一原则在不同层次的表现** —— 横截面比较要求被比较的量出自同一口径。」
`BR:587`：「**子排名的样本量按 §7.3.1 判定** —— 拆分后某个子集不足 30 只时该子集 `INSUFFICIENT_SAMPLE`，这是正确结果而非缺陷」。

**三个被否决的替代方案**（`BR:591-595`）：强制同组同一 Profile（划分依据不同，无法强制对齐）／按主导 Profile 统一评价（少数派被用不适合的标准评价）／归一化后合并排名（归一化不解决量纲问题）。

### 11.8 Fund Classification 的 PIT 属性（`BR:376-383` §5.4）

- 分类可能随时间变化（基金转型）
- 变更必须按 `effective_at` / `available_at` 记录
- **回测必须使用当时的分类**，不得用当前分类回溯历史
- 分类变更同时触发 `Peer Group` 与 `Benchmark` 变更

---

## 12. Fund Ranking / 分位 / Fund Tier

### 12.1 派生链（`BR:1049-1061` §16.1）

```
Fund Score
    ↓  在 Peer Group 内排序
Peer Group Ranking
    ↓  转换为分位
Percentile
    ↓  按阈值分层
Fund Tier
```

`BR:1061`：「四者是**同一条派生链上的不同表示**，不是四个独立概念。任一环节的输入变化会沿链传导。」

### 12.2 Ranking Scope 必须声明的五项（`FR:120-130` §4）

`FR:122`：「**一次排名必须完整声明五项，缺一则结果无法解释。**」

| 项 | 说明 |
|---|---|
| **`as_of_date`** | 排名时点 |
| **`evaluation_period`** | 1M / 3M / 6M / 1Y / 3Y / 5Y |
| **`peer_group_id` + `peer_group_version`** | 跟谁比 |
| **`ranking_metric`** | 按什么排 |
| **`ranking_policy_version`** | 用什么规则排 |

### 12.3 Ranking Metric（`FR:146-168` §5）

| Metric | 说明 |
|---|---|
| **`Total Score`** | **默认** —— 覆盖五个维度 |
| 单项子分（如 Risk-Adjusted Score） | 支持，用于专项视角 |
| 单个 Factor（如 Annual Return、Sharpe） | 支持，用于展示与筛选 |

`FR:156`：「**单因子排名可以展示，但不得代替综合评价。**」
`FR:164`：「排名所用的 Metric，其标准化必须在**同一个** Peer Group 内完成。❌ 用 Peer Group A 标准化得到的 Score，在 Peer Group B 内排名」

### 12.4 Rank（`FR:172-203` §6）

**定义**（`FR:176-184`）：

```
Rank = 该基金在 Peer Group 内按 Ranking Metric 降序排列的序位
```

表示形式 `Rank / N`，其中 `N` 是该指标在该组内的**有效参与数**。

**`N` 是有效参与数，不是组规模**（`FR:186-197`）：

```
Peer Group 规模 = 200 只
其中 80 只的 3Y Sharpe 为 UNAVAILABLE（成立不足 3 年）

3Y Sharpe 排名的 N = 120，不是 200
```

`FR:197`：「**必须同时呈现 `N` 与组规模**」。
`FR:201`：「**统一按"越优越靠前"排列**，Rank = 1 表示最优。」

### 12.5 Percentile 公式（`FR:209-232` §7）

**本项目采用的公式**（`FR:211-213`，一字不差）：

```
Percentile = (N − Rank) / (N − 1) × 100%
```

`FR:215`：「**本公式使最优者 = 100%、最劣者 = 0%，与 Score 的 0–100 标尺方向一致。**」
示例（`FR:218-220`）：`Rank = 5，N = 120 → Percentile = (120 − 5) / 119 × 100% ≈ 96.6%`

**三种约定对照**（`FR:226-230`）：

| 约定 | 公式 | 最优者 | 最劣者 |
|---|---|---|---|
| **本项目采用** | `(N − Rank) / (N − 1)` | **100%** | **0%** |
| 常见变体 A | `(N − Rank) / N` | `(N−1)/N` | 0% |
| 常见变体 B | `(N − Rank + 0.5) / N` | 不达 100% | 不达 0% |

`FR:232`：「**为什么选第一种**：`Fund Tier` 的分位阈值是 5% / 20% / 50% / 80%（`02-business-requirements` §16.3.1），采用端点为 0/100 的约定使阈值语义直观——"前 5%"就是 `Percentile ≥ 95%`。」

**`N = 1` 的边界**（`FR:234-240`）：分母为 0，`Percentile = UNAVAILABLE`。
**Percentile ≠ Score**（`FR:242-251`）：「`Score = 85` 与 `Percentile = 85%` **不是同一件事**，不得互相替代。」

### 12.6 Tie Handling（`FR:255-308` §8）

**三种方法**（`FR:259-263`）：

| 方法 | 说明 | 示例（分数 90, 85, 85, 80） |
|---|---|---|
| **`COMPETITION_RANK`** | 并列同名次，后续跳号 | 1, 2, 2, **4** |
| **`DENSE_RANK`** | 并列同名次，后续不跳号 | 1, 2, 2, **3** |
| **`ORDINAL_RANK`** | 强制唯一名次，按次级规则打破并列 | 1, 2, 3, 4 |

`FR:273`（**已定案 · 2026-08-27**，`FR-2` 关闭）：

> **已定案 · 2026-08-27**：Tie Method = **`COMPETITION_RANK`**（并列同名次，后续名次跳过，如 1, 2, 2, 4）。

依据（`FR:277-285`）：

```
DENSE_RANK（1, 2, 2, 3）：名次不跳过
    → N 只基金的最大名次 < N
    → §7.2 的 Percentile 公式 (N − Rank)/(N − 1) 分母与实际名次范围不匹配
    → 「前 10%」实际包含的基金数随并列数量漂移

COMPETITION_RANK（1, 2, 2, 4）：名次跳过
    → 最大名次 = N，分位口径稳定
```

`FR:289`：「**浮点因子值的并列极少发生**，但**分位标准化后**（`04-factor/05`）并列会变得常见 —— 因为分位是离散化的。因此本条在实践中会被频繁触发。」

**确定性要求**（`FR:299-308` §8.4）：

```
❌ 并列时按数据库返回顺序 → 每次重算可能不同 → 违反可复现性
✅ 并列时按显式声明的次级规则（如 fund_id 升序）
```

`FR:308`：「即使采用 `COMPETITION_RANK` / `DENSE_RANK`（不强制打破并列），**结果列表的输出顺序**仍需确定性排序。」

> ⚠️ `FR:562` D-9 仍写着「**Tie Method = TBD**，但确定性是硬要求」—— **与 `FR:273` 的定案矛盾（文档内部未同步）**。以 `FR:273` / `FR:588` 的定案为准。

### 12.7 Ranking Eligibility 与样本不足（`FR:312-360` §9）

`FR:314`：「**一只基金可以完成 Evaluation，却不能参与 Ranking。**」

| 情形 | Evaluation | Ranking |
|---|---|---|
| 基金正常，Peer Group 充足 | ✅ | ✅ |
| **Peer Group 样本量低于阈值** | ✅ | ❌ / **低置信** |
| **Peer Group 内仅 1 只基金** | ✅ | ❌ `UNAVAILABLE` |
| 该指标为 `UNAVAILABLE` | ✅（其他指标） | ❌ **该指标**的排名 |
| `evaluation_status = FAILED` | ❌ | ❌ |

`FR:328`：「**不是"这只基金能否排名"，而是"这只基金的哪个指标能排名"。**」

**`Minimum Peer Group Size = 30`**（`FR:340`，已定案 2026-08-27）。

**`n_effective < 30` 时的输出**（`FR:349-354` §9.3.1，逐行抄录）：

| 输出字段 | 值 |
|---|---|
| `rank` | `null` |
| `percentile` | `null` |
| `n_effective` | 实际值（如 17） |
| **`ranking_status`** | **`INSUFFICIENT_SAMPLE`** |

`FR:356`：「**`n_effective` 仍须返回** —— 调用方需要知道「差多少」。返回 17 与返回 29 对使用方的含义不同」
`FR:358`：「**这不是错误状态** —— 样本不足是正常业务情形，`ranking_status` 与 `FAILED` 是两回事。新成立的细分类别天然样本少，不应产生告警。」

### 12.8 Ranking Output / 落库要求（`FR:461-470` §13.3，`FR:429-433` §12.3）

| 字段 | 说明 |
|---|---|
| `fund_id` / `evaluation_period` / `as_of_date` | 标识 |
| **`rank`** | 序位 |
| **`n_effective`** | **有效参与数** |
| **`peer_group_size`** | 组规模（与 `n_effective` 可能不同） |
| **`percentile`** | 分位 |
| `ranking_metric` | 按什么排的 |
| `confidence_flag` | 样本量不足时标记低置信 |
| 版本引用 | §12.1 五要素 |

`FR:431`：「**不得只存 Rank 而不存 `N` 与 Percentile。**」`FR:433`：「若不落库，历史分位无法还原。」
`FR:565` D-12：「**Rank、`N`、Percentile 三者都必须落库**」

**Ranking 可复现五要素**（`FR:409-417` §12.1）：`as_of_date` + `evaluation_period` + `peer_group_id` + `peer_group_version` + `ranking_policy_version` + `scoring_policy_version`（及其依赖的 `evaluation_policy_version`、`factor_version`、`data_version`）。

### 12.9 排名时序（`FR:364-382` §10）

排名变化的三个来源（`FR:376-380`）：**自身表现变化** / **同组其他基金表现变化** / **`Peer Group` 构成变化**（新基金成立、老基金清盘、分类调整）。
`FR:382`：「**因此排名时序必须与 Score 时序、组规模时序一同呈现**，否则无法归因。」（`FR:578` C-6）
`FR:60`：「**排名是有损压缩**，必须与 Score 一同呈现。」

### 12.10 Fund Tier 五档与分位阈值

**五档命名**（`BR:1070`，`FC:110-116`）：

```
A+  Excellent  ·  A  Very Good  ·  B  Good  ·  C  Neutral  ·  D  Weak
```

**分位区间**（`BR:1084-1090` §16.3.1，**已定案 · 2026-08-25**，`P0-2`；`FC:110-116` 沿用）：

| Tier | 分位区间 | 含义 |
|---|---|---|
| **A+** | 前 5% | Excellent |
| **A** | 5% – 20% | Very Good |
| **B** | 20% – 50% | Good |
| **C** | 50% – 80% | Neutral |
| **D** | 后 20% | Weak |

**边界条件（`>=` / `<` 明确版）**（`FC:194-200` §8.2，采用「上闭下开」即高分位端闭合）：

| Tier | 边界条件 |
|---|---|
| **A+** | `percentile >= 95` |
| **A** | `80 <= percentile < 95` |
| **B** | `50 <= percentile < 80` |
| **C** | `20 <= percentile < 50` |
| **D** | `percentile < 20` |

**分位区间 ↔ 阈值的换算**（`FC:206-212` §8.3）：

```
前 5%      →  percentile ∈ [95, 100]
5% – 20%   →  percentile ∈ [80, 95)
20% – 50%  →  percentile ∈ [50, 80)
50% – 80%  →  percentile ∈ [20, 50)
后 20%     →  percentile ∈ [0, 20)
```

`FC:214`：「**这是一处极易出错的换算** —— "前 5%"在 Rank 语义下是小序号，在 Percentile 语义下是大数值。两种表述必须能互相校验。」

**边界校验三项**（`FC:218-222` §8.4）：**完备性**（五个区间必须覆盖 `[0, 100]` 全部取值，无空隙）／**互斥性**（任一 percentile 值只能落入一个 Tier）／**单调性**（percentile 越高，Tier 越优）。

**其他 Tier 规则**：
- `BR:1075`：阈值配置化，**严禁硬编码**；`BR:1076`：须声明按绝对分数还是按分位分层；`BR:1077`：与排名同一样本集；`BR:1078`：记录当时的阈值配置版本。
- `FC:136`：「**上游已定案为分位 5 / 20 / 50 / 80**，本域沿用，**不标 TBD**。」
- `BR:1092` / `FC:126-131`：**为什么不按绝对分数分层** —— 「`Fund Score` 本身就是各 Factor 在 `Peer Group` 内做分位标准化后合成的——它已经是相对量。在相对量上再切绝对阈值，切出来仍然是分位，只是把这一事实隐藏起来，并引入各层人数随组内分布漂移的副作用。」
- `FC:165`（**已定案 · 2026-08-27**，`FC-1`）：「第一阶段**不为 A+/A 追加绝对门槛**」，理由是「会破坏跨期可比」。`BR:2557` `P1-24` 仍保留为 P1 项。
- **小样本**（`FC:235-241` §8.5，**已定案 · 2026-08-27**，`TBD-FC-2` 关闭）：`n_effective < 30` 时**不产出 Tier** —— `tier = null`、`n_effective` = 实际值、`classification_status = INSUFFICIENT_SAMPLE`。`FC:249`：选「不产出」而非「低置信标记」，因为「Tier 值仍存在，**下游会照常使用它**……标记只在展示层可见，而消费 Tier 的是代码不是人」。

### 12.11 Tier 必须与组内绝对水平同屏展示 ⚠️

**`BR:1094-1096` §16.3.1 确切表述**：

> **已知局限与强制缓解措施**：分位分层意味着无论该 Peer Group 整体质量如何，**永远有 5% 被评为 A+**。缓解手段不在分层规则内，而是强制要求：
>
> > **`Fund Tier` 必须与该 `Peer Group` 的绝对水平同屏展示**（至少含组内 Sharpe 中位数与 Maximum Drawdown 中位数），使读者能判断"A+ 在这一组意味着什么"。仅展示 Tier 而不展示组内绝对水平，视为违反本条。

**`FC:148-159` §7.2 复述**：

```
Fund Tier 必须与该 Peer Group 的绝对水平同屏展示
    至少包含：组内 Sharpe 中位数、组内 Maximum Drawdown 中位数
```

`FC:157`：「**仅展示 Tier 而不展示组内绝对水平，视为违反本条。**」
`FC:433` D-6：「**Tier 不得单独输出**，须与 percentile、score、组内绝对水平同屏」
`FC:447` C-3：「**`Fund Tier` 必须与组内绝对水平同屏展示**，否则视为违规」
`FS:167`（同一要求延伸到 Score）：「**必须与组内绝对水平同屏展示** —— 否则读者无法判断"80 分在这一组意味着什么"」

### 12.12 Tier 的边界不稳定性（`FC:320-337` §11.2 / §11.3）

- 「**边界附近的微小波动** \| `percentile = 94.9` 与 `95.1` 分属不同 Tier」（`FC:320`）
- `FC:337`：不引入平滑机制；「Tier 是离散档位，边界附近的基金与相邻档的实质差异很小。不提示会让使用者误以为 A 与 B 之间存在实质鸿沟。」（平滑会「引入路径依赖、破坏可复现性」，`FC:483`）

### 12.13 分层的用途与边界（`BR:1100-1104` §16.4）

用途：快速发现优秀基金、排除弱势基金、作为 Eligibility Rules 的可选输入、支持组合角色划分。
`BR:1104`：「**分层不等于投资建议。** A+ 不意味着"应该买"，D 也不意味着"应该卖"。」
`FE:101` 同义：「本域全部产出同理——`A+` 不意味着"应该买"，`D` 也不意味着"应该卖"」。

### 12.14 与候选池（Fund Universe）的边界

`FE:46`：「**③ 与 ④ 之间的边界**：③ 产出的是**对基金的评价**，④ 产出的是**可投资标的集合**。两者之间隔着 `Eligibility Rules`——Score 只是 Universe 的**可选**输入（上游 §4.2 ④）。」
`FE:67-69`（链路图）：`Fund Tier` 与 `Fund Score` 都是 Universe 的**可选输入**；`Eligibility Rules` 是**必要输入**。

> ⚠️ 候选池的完整规则在 `docs/04-factor/05-fund-selection.md`（= `docs/05-fund-evaluation/05-fund-selection.md`），**本次抽取范围不含该文件**。M1.4 的「候选池」部分需另行抽取（含 `FSEL-6` 的 Share Class 去重规则，见 `FE:130`）。

---

## 13. 本域特有的四个前视来源（`FE:252-261` §9.2）—— 逐条抄录

**引文（`FE:252-261`，一字不差）**：

> ### 9.2 本域特有的四个前视来源
>
> > **前三项不涉及"未来的数据"，而涉及"未来的定义"——同样构成前视，且更隐蔽。**
>
> | # | 来源 | 说明 |
> |---|---|---|
> | 1 | **使用当前的 `Peer Group` 构成** | 基金转型会改变分类。用今天的组构成算历史分位是前视（`02-business-requirements` §7.4） |
> | 2 | **使用当前的 `Evaluation Policy`** | 评价标准变了，用新标准解释历史评价是**版本前视** |
> | 3 | **使用当前的 Benchmark Mapping** | 转型后映射变了，影响全部 `REL` 类 Factor |
> | 4 | 使用修订后的净值 | `T` 时点看到的是修订前版本（`03-data/04-data-versioning` §8） |

**配套的核心 PIT 规则（`FE:238-250` §9.1）**：

`FE:240`：

> **`evaluation_as_of_date = T` 时，全部输入必须满足 `available_at ≤ T`。**

```
❌ 前视
历史日期 T → 使用当前数据/当前配置 → Evaluation

✅ 正确
决策日期 T → 使用 available_at ≤ T 的数据 → Evaluation
```

`FE:250`：「沿用上游 §4.2 ①-PIT 的判定标准：**PIT 判定用 `available_at`，不是 `effective_at`**；同一 `(entity, effective_at)` 有多个合格版本时，取 **`version` 序号最大者**。」

`FE:781` C-2：「全部输入必须满足 `available_at ≤ as_of_date`」
`FE:752`：「**前视不只来自"未来的数据"，也来自"未来的定义"** —— 当前的 Peer Group、Evaluation Policy、Benchmark Mapping 用于历史同样构成前视」

**各来源的对应治理点**：

| # | 前视来源 | 对应的可重建要求 | 出处 |
|---|---|---|---|
| 1 | Peer Group 构成 | `peer_group_id` + `peer_group_version` 必须落库；历史构成可重建且含已清盘基金 | `FE:263-273`、`FE:584`、`BR:551-557` |
| 2 | Evaluation Policy | `evaluation_policy_version` 必须落库；「Policy 变更不改写历史」（`FE:586-588` §18.3） | `FE:370`、`FE:788` C-9 |
| 3 | Benchmark Mapping | 每条映射须记 `effective_at` / `available_at` / `source` / `mapping_rule_version`；「回测在 `T` 时点必须使用 `available_at ≤ T` 的映射版本」；「不得用转型后的基准回算转型前的超额收益」 | `BR:644-657` §8.4 |
| 4 | 修订后的净值 | `data_version` 必须落库 | `FE:356`、`FE:373` |

---

## 14. 所有 TBD / 待确认项

### 14.1 本域（fund-evaluation）三份文档的 TBD

| 编号 | 事项 | 状态 | 阻塞什么 | 出处 |
|---|---|---|---|---|
| ~~FE-1~~ | 同一基金的多个 Share Class 是否同时进入同一 Peer Group | ✅ 2026-08-27 关闭：**同时进入**，Universe 层去重 | — | `FE:797`、`FE:130` |
| **FE-2** | **各 Evaluation Profile 的周期集合与周期间权重** | ❌ **未关闭**，责任方投研 | **评价结构** —— 无法确定每个 Profile 用哪几个周期、周期间怎么加权（`FE:216` 的 {1Y,3Y,5Y} / 3Y>1Y>5Y 只是「推荐默认」） | `FE:798` |
| ~~FE-3~~ | 一只基金至少需多少个周期可评价 | ✅ 关闭：至少需 **1Y** | — | `FE:799` |
| ~~FE-4~~ | `MAR` 的取值与差异化配置 | ✅ 关闭：三模式，第一版默认 `ZERO`，`mar_policy` 必填无默认 | — | `FE:800` |
| **FE-5** | **是否需要第五类 `Evaluation Profile`（FOF、可转债等）** | ❌ **未关闭**，责任方投研 | **画像覆盖度** —— 四类画像套不上的产品无处归入（`BR:365`：「不得强行归入现有四类」） | `FE:801` |
| ~~FE-6~~ | 三个 Policy Version 不在九项 Strategy Version 之内 | ✅ 关闭：归入第 10 类 `Policy Version` | — | `FE:802` |
| ~~FS-1~~ | 费率归入哪个子分 | ✅ 关闭：**Risk-Adjusted 子分** | — | `FS:714` |
| **FS-2** | **各 Profile 的 Beta 目标区间**（= 上游 `P1-22`） | ❌ **未关闭**，责任方投研 | **Beta 无法标准化** —— `FS:203`：「目标区间未定义时 `UNAVAILABLE`，不得默认按越低越好」→ Beta 直接退出评分 | `FS:715`、`FS:208` |
| ~~FS-3~~ | 权重归一化约定 | ✅ 关闭：**Σ = 1**（小数） | — | `FS:716` |
| ~~FS-4~~ | 各 Profile 内部的具体权重分配 | ✅ 关闭流程：有效因子内等权；**剩余为检验阈值 `OPEN-11`** | — | `FS:717` |
| ~~FS-5~~ | 子分内可用指标数的下限阈值 | ✅ 关闭：**< 2 时子分 `UNAVAILABLE`**，不重分配 | — | `FS:718` |
| ~~FS-6~~ | 基金转型后历史评分的展示与不可比标注 | ✅ 关闭：继续展示但标注不可比，Rolling 序列重新起算 | — | `FS:719` |
| ~~FR-1~~ | Currency / Market 是否作为 Peer Group 附加划分维度 | ✅ 关闭：**Currency 是、Market 否** | — | `FR:587` |
| ~~FR-2~~ | Ranking Tie Method | ✅ 关闭：**`COMPETITION_RANK`** | — | `FR:588` |
| ~~FR-3~~ | Minimum Peer Group Size | ✅ 关闭：**30** | — | `FR:589` |
| **FR-4** | **排名时序的展示区间与变化告警阈值** | ❌ **未关闭**，责任方投研 + 运维 | **展示层与监控** —— 时序展示区间、排名下滑的告警阈值均无值 | `FR:590` |
| ~~FC-1~~ | Tier 是否追加绝对门槛 | ✅ 关闭：第一阶段**不追加** | — | `FC:165` |
| ~~FC-2~~ | 小样本下 Tier 的处理 | ✅ 关闭：`n_effective < 30` 时**不产出 Tier** | — | `FC:235` |

### 14.2 上游 `02-business-requirements` §35.2 的 P1 项（与本 Plan 相关的）

| 编号 | 事项 | 状态 | 阻塞什么 | 出处 |
|---|---|---|---|---|
| ~~P1-1~~ | Peer Group 最小样本量阈值 | ✅ 关闭：**30**；剩余为实证验证 `OPEN-9`/`OPEN-10` | — | `BR:2534` |
| ~~P1-2~~ | Peer Group 与 Evaluation Profile 不一致时的处理 | ✅ 关闭：按 Profile 拆分子排名 | — | `BR:2535` |
| **P1-4** | **四象限默认坐标轴与分界方式** | ❌ 未关闭（`BR:858` 已给「推荐默认」= (年化波动率, 年化收益) + Peer Group 中位数分界，业务方可改） | 四象限展示 | `BR:2537` |
| ~~P1-5~~ | Win Rate 默认基准（绝对/相对） | ✅ 关闭：**绝对正收益** | — | `BR:2538` |
| ~~P1-6~~ | Skewness / Kurtosis 是否纳入 SCORING | ✅ 关闭：**不纳入**，仅 `DISPLAY` | — | `BR:2539` |
| **P1-20** | **Fund Classification Default Benchmark 映射表（优先级 4）** | ❌ **未关闭**，责任方投研 | `REL` 类 Factor —— Benchmark 优先级 4 无映射时兜底到优先级 5；`BR:661`：无法确定 Benchmark → Alpha/Beta/IR/TE/超额收益/R²/Relative Performance Score 全部 `UNAVAILABLE` | `BR:2553` |
| **P1-22** | **Active Equity / Bond / Hybrid 的 Beta 目标区间** | ❌ **未关闭**，责任方投研 | **Beta 无法标准化**（= `FS-2`） | `BR:2555` |
| ~~P1-23~~ | 各 Evaluation Profile 内部的具体权重分配 | ✅ 关闭流程：有效因子内等权；**取值待检验产出**，剩余为 `OPEN-11`~`OPEN-13` | — | `BR:2556`、`BR:2559` |
| **P1-24** | **Fund Tier 是否追加绝对门槛** | ❌ 上游仍列为 P1（本域 `FC:165` 已定案第一阶段不追加） | Tier 语义 | `BR:2557` |

`FE:804` 的上游遗留列表：「`<TBD-P1-1>` Peer Group 最小样本量、`<TBD-P1-2>` Peer Group 与 Profile 不一致时的处理、`<TBD-P1-22>` Beta 目标区间、`<TBD-P1-23>` 画像内权重分配。」（前两项与第四项已在上游关闭，`FE` 未同步）

### 14.3 OPEN 项（阈值待实证）

| 编号 | 事项 | 阻塞什么 | 出处 |
|---|---|---|---|
| `OPEN-9` | 30 的实证验证 —— 历史上有多少比例的 (Peer Group, 期) 组合会被降级，待数据回溯 | 不阻塞实现，属上线后复核 | `BR:548` |
| `OPEN-10` | 长期低于 30 的分类是否应合并或采用更粗粒度的 Peer Group，待投研确认 | Peer Group 划分粒度 | `BR:549` |
| `OPEN-11` | 因子有效性入选下限（推荐 IC ≥ 0.02、\|ICIR\| ≥ 0.3；**业务方可改**） | **Score 产出的前置条件** —— `FS:342`：检验未产出则 `score_status = VALIDATION_PENDING`，不产出总分 | `FS:348`、`BR:345`、`BR:349` |
| `OPEN-12`（隐含） | 因子冗余阈值（推荐相关系数 > 0.8，保留 \|ICIR\| 较高者；业务方可改） | 因子筛选 | `BR:350`、`BR:354` |
| `OPEN-13` | 第二版权重优化的形式 | 第一阶段**不实现**，不阻塞 | `BR:355-359` |
| `TBD-FD-3` | 各 Factor 的 `Min Obs` | **Minimum Data Requirement 无具体值** | `FE:319` ⚠️ 定义在缺失文档中 |
| `TBD-FD-2` | = `TBD-FE-4`，已关闭 | — | `FE:450` |

### 14.4 文档未给值的参数汇总（实现前必须补齐或显式标 `TBD`）

| # | 参数 | 出处 |
|---|---|---|
| 1 | 各 Evaluation Profile 的**周期集合与周期间权重**具体数值 | `FE:798` FE-2 |
| 2 | 各 Profile 的**因子层 / 子分层权重**具体数值（只给了「有效因子内等权」的产生规则与相对高低） | `FS:299`、`FS:356-362`、`BR:361` |
| 3 | 各 Profile 的 **Beta 目标区间** | `FS:208`、`BR:2555` |
| 4 | 各 Factor 的 **`Min Obs`** | `FE:319` |
| 5 | **`R_f` 的 `(currency, tenor)` 具体口径** | `FE:525` |
| 6 | **`CUSTOM` 模式的 `mar_value`** | `FE:770` D-11 |
| 7 | **Fund Classification Default Benchmark 映射表** | `BR:2553` P1-20 |
| 8 | 排名时序**告警阈值**与展示区间 | `FR:590` |
| 9 | 因子有效性 / 冗余阈值的**最终值**（现为「推荐默认，业务方可改」） | `BR:345`、`BR:350` |
| 10 | `Hybrid` 画像下 **Tracking Error 的具体处理**（`FS:204`「Hybrid 待定」） | `FS:204` |

---

## 15. ⚠️ 引用了【不存在的文档】的地方 —— 我必须自己补齐的边界

### 15.1 缺失清单（已在仓库中核实）

`docs/04-factor/` 目录实际只包含 `01-fund-evaluation.md` / `02-fund-scoring.md` / `03-fund-ranking.md` / `04-fund-classification.md` / `05-fund-selection.md` —— **它是 `docs/05-fund-evaluation/` 的逐字节副本**。被引用的因子域八份文档**一份都不存在**：

| 被引用的文档 | 存在？ | 被引用次数（三份主文档内） |
|---|---|---|
| `04-factor/02-factor-taxonomy` | ❌ | 2（`FE:150`、`FE:158`） |
| `04-factor/03-factor-definition` | ❌ | 6（`FE:158`、`164`、`315`、`418`、`470`、`500`） |
| `04-factor/05-factor-normalization` | ❌ | 7（`FE:303`、`446`；`FS:46`、`50`、`206`、`239`；`FR:203`、`240`、`345`） |
| `04-factor/06-factor-versioning` | ❌ | 1（`FS:553`） |
| `04-factor/07-factor-validation` | ❌ | 2（`FE:395`、`FS:348`） |
| `04-factor/08-factor-output` | ❌ | 4（`FE:192`、`349`、`815`；`FS:456`、`730`） |
| `TBD-resolution.md` | ❌ | 多处（`FE:450`、`FE:708`、`FS:308`、`FR:343`、`BR:276`、`BR:530`、`FC:235`） |
| `TBD-resolution-2.md` | ❌ | 多处（`FE:130`、`FE:825`、`FS:348`、`FS:739`、`FR:609`、`BR:597`、`BR:907`、`BR:979`） |

> 另：`FE:5` 声明「**本域上游**：docs/04-factor/（v1.0–v1.1，全 8 份）」—— 这 8 份**全部缺失**。

### 15.2 逐个：引用方到底依赖它提供什么

#### A. `04-factor/02-factor-taxonomy` —— 因子分类法

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FE:150`（§6 维度表的列标题） | **`RET` / `RISK` / `RAP` / `STAB` / `REL` 五个类别码的权威定义** —— 每个 Factor 属于哪一类 |
| `FE:158` | 「**五分类与五子分一一对应**（`02-factor-taxonomy` §2）」—— 五分类 ↔ 五子分映射的**权威声明**在该文档 §2 |

**我必须自己补齐的**：一张「Factor → 类别码」的完整映射表（26 行）。**没有它，`FE:170-177` §7.1 的分组（本 digest §2.4）就是唯一线索** —— 而 §7.1 只给了 16 个左右的名称，且 `Rolling Return` 归 RET 还是 STAB 存在冲突（见 §2.4 的警告）。

#### B. `04-factor/03-factor-definition` —— 26 个因子的数学公式 ⭐ 最大空白

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FE:164` | **26 个 Factor 的完整清单**（「不得引入该文档中不存在的指标」——但清单本身不在） |
| `FE:158` | 全部 **Factor 数学公式**（「本域不重新定义 Factor 数学公式——全部引用」） |
| `FE:315` / `FE:319` | 各 Factor 的 **`Min Obs`（最低观测数）声明** —— 直接决定 §7.3 的 Minimum Data Requirement |
| `FE:418` | §2.1：**`R_f` 在 Sharpe / Alpha / Beta 中的使用方式**（超额收益怎么算、日频还是年化） |
| `FE:466` | §2.1.1：**`RISK_FREE` 模式下 `Rf_t` 的期限匹配规则**（「按 §2.1.1 期限匹配，逐期取值」） |
| `FE:470` / `FE:500` | §2.2.4：选 `ZERO` 的完整论证 + MAR 配置粒度 `fund_category × currency` 的定案原文 |
| `FE:423` | **Factor ID 编码规则** —— 只泄露了 4 个：`F-RAP-001` Sharpe、`F-REL-002` Alpha、`F-REL-003` Beta、`F-REL-004` Information Ratio |

**我必须自己补齐的**：
1. **26 个 Factor 的 ID + 名称 + 类别 + 公式 + `Min Obs`**（一张完整表）。本 digest §2 / §3 只能给出**名称与 Usage/Direction**，**没有一条公式**。
2. **Factor ID 命名规则**：从 `F-RAP-001` / `F-REL-002` 反推为 `F-<类别码>-<三位序号>`，但各类的序号分配未知。
3. **Sharpe / Sortino / Calmar / Alpha / Beta / IR / TE / VaR / CVaR / MDD / Rolling 系列**的确切定义（窗口、样本、分母口径）。
4. **`Min Obs`** 各值（文档只说「多数为 `<TBD-FD-3>`」—— 连缺省值都是 TBD）。

#### C. `04-factor/05-factor-normalization` —— 标准化与方向转换

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FS:46` / `FS:50` | **整个标准化与 Direction 转换环节的实现**：「本域消费的是**已标准化、已统一方向**的值」 |
| `FS:206` §6.2 | **`TARGET_RANGE` / `STRATEGY_DEPENDENT` 的具体转换算法**（Beta 如何转成「偏离目标区间的程度」） |
| `FS:239` | 异常值处理的规定（第一阶段默认不做） |
| `FE:303` §5.3 | 「缺失不得转 0」在标准化层的对应条款 |
| `FE:446` §5.4 | **MAR 组内一致性的校验实现**：「在标准化前校验，不一致时该组该 Factor `UNAVAILABLE` 并告警」 |
| `FR:203` | 「标准化已把全部因子统一为"越高越好"」 |
| `FR:240` §5.2 | 「组内仅 1 只基金 → `UNAVAILABLE`」 |
| `FR:345` §5.2.1 | **`MIN_PEER_GROUP_SIZE = 30` 三处之一的配置点** |

**我必须自己补齐的**：
1. **Percentile Rank 标准化的确切算法**（用什么分位公式把 raw value 映射到 0–100；是否与 `FR:212` 的 `(N−Rank)/(N−1)` 同一公式 —— **文档未明说两者是否一致**，这是一处必须自己拍板的关键点）。
2. **方向转换规则**：`LOWER_IS_BETTER` 是先取负再排分位，还是排完分位再 `100 − p`（两者在有并列时结果不同）。
3. **`TARGET_RANGE`（Beta）的偏离度量函数**：绝对偏离？相对偏离？区间内是否一律满分？
4. **`STRATEGY_DEPENDENT`（Tracking Error）在「中性」画像下的处理** —— 「中性」不是四个方向枚举之一，`FS:204` 说 Active Equity 下 TE「中性、配合 IR 判读」，**「中性」怎么算分文档未给**。
5. **MAR 一致性校验的判定逻辑**（`ZERO`/`CUSTOM` 比数值，`RISK_FREE` 比 `(currency, tenor)` 解析路径 —— `FE:494` 给了原则，未给实现）。

#### D. `04-factor/06-factor-versioning`

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FS:553` §4.3 | **`MAR` 变更升 Evaluation Policy Version、不升 Scoring Version 的论证与版本升级规则表** |

**我必须自己补齐的**：`factor_version`（= Metric Version）的**版本号语义与 Major/Minor 判定规则**。本 digest 只知道它必须随每条结果落库（`FE:374`、`FS:532`）。

#### E. `04-factor/07-factor-validation` —— 因子有效性检验

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FE:395` §11.2 | **`NOT_ELIGIBLE` 与 `FAILED` 区分的原始原则** |
| `FS:348` §10 | **IC / ICIR 阈值的定义方**（`validation_policy`），以及 `VALID` / `INVALID` 的判定过程 |

**我必须自己补齐的**：
1. **`factor_effectiveness` 结果对象的结构** —— 它的**存在性是 Score 产出的前置条件**（`FS:346`），所以必须先定义它长什么样：至少含 `(profile, factor_id, valid/invalid, IC, ICIR, 检验区间)`。
2. **IC / ICIR / Rank IC / t-stat / 分层单调性的计算口径**（`BR:330` 只列了名字）。
3. **IS/OOS 划分方式**（`BR:343` 要求划分，比例是 `P1-14`，责任方投研，**未给值**）。

> ⚠️ 这是**最阻塞 M1.3/M1.4 的空白**：没有 `07-factor-validation` 就没有 `factor_effectiveness`，没有它就 `score_status = VALIDATION_PENDING`，**总分根本不产出**（`FS:342`）。实现计划必须把「产出 factor_effectiveness」当作 Score 的硬前置，或显式定义一个可运行的最小检验实现。

#### F. `04-factor/08-factor-output` —— Factor Result 结构 ⭐ 第二大空白

| 引用位置 | 依赖它提供什么 |
|---|---|
| `FE:192` §2 | **`Factor Result` 的完整结构定义**，尤其 **`Status` 四值枚举的权威定义**（`VALID`/`WARNING`/`INVALID`/`UNAVAILABLE` 各自的触发条件） |
| `FE:349` | **`Threshold Context`** 的结构 —— 「Factor Results（带 Status 与 **Threshold Context**）」，Threshold Context 承载所用的 `R_f` 版本引用（`FE:677`） |
| `FS:456` §2.3 | **`raw_value` 必须随输出携带**的原始要求 |

**我必须自己补齐的**：
1. **`FactorResult` 的字段清单**：`factor_id`、`window`/`period`、`raw_value`、`normalized_value`、`status`、`threshold_context`、`factor_version`、`quality flags`（`WARNING` 的载体）……本 digest 只能从消费方（`FE:368`、`FS:447-454`）反推出**部分**字段。
2. **每种 `Status` 的确切触发条件** —— 文档只给了消费方的处理，**没给生产方的判定规则**。尤其 `WARNING` 与 `INVALID` 的分界完全未知（`FE:196`「参与，但标记须随评价结果传递」只说了怎么用，没说什么时候标）。
3. **`Threshold Context` 的结构**（`R_f` 版本引用、`MAR` 引用、Threshold Resolver 的输出形态）。
4. **`R_f` 的 quality 枚举** —— `FE:496` 提到一个值 `INTERPOLATED`（「`R_f` 若为 `INTERPOLATED`，Sortino 的插值误差随之引入」），**其余取值未知**。

#### G. `TBD-resolution.md` / `TBD-resolution-2.md`

| 引用位置 | 依赖它提供什么 |
|---|---|
| `TBD-resolution.md` Policy ② | MAR 三模式定案的完整论证（`FE:450`） |
| Policy ⑤ | `MIN_PEER_GROUP_SIZE = 30` 定案（`BR:530`、`FR:343`、`FC:235`） |
| Policy ⑥ | 有效因子内等权定案（`FS:308`、`BR:276`） |
| Policy ⑧ | 第 10 类 `Policy Version` 定案（`FE:708`） |
| `TBD-resolution-2.md` Policy D | Share Class 口径定案（`FE:130`） |
| `TBD-resolution-2.md` §3.1 | Profile 拆分子排名（`BR:597`）、Win Rate 基准（`BR:907`）、Skew/Kurt 不入评分（`BR:979`） |
| `TBD-resolution-2.md` §4.4 | IC/ICIR 阈值（`FS:348`） |

**影响评估**：这两份是**论证性文档**，其**结论已在主文档中完整复述**（本 digest 已逐条抄录）。缺失它们**不阻塞实现**，只是失去了「为什么这么定」的完整推导。

### 15.3 空白对 Plan-2 三个里程碑的影响

| 里程碑 | 可直接实现的部分 | 被缺失文档卡住的部分 |
|---|---|---|
| **M1.2 Peer Group** | ✅ **几乎全部可实现** —— 定义、划分维度（Classification × Currency）、参与规则、`MIN_PEER_GROUP_SIZE = 30`、PIT 与版本化要求全部有确切值（`BR:477-597`、`FR:73-116`、`FE:263-273`） | 仅 `05-factor-normalization` §5.2.1 是「三处同一配置源」之一 —— 配置点位置需自定 |
| **M1.3 因子** | ⚠️ **只有元数据可实现** —— Usage Matrix 五列、Preference Direction、四画像差异矩阵、周期口径（Trading-day / 252 / `(start, end]`）、缺失处理原则 | ❌ **26 个 Factor 的公式、ID、`Min Obs` 全部缺失**；❌ 标准化与方向转换算法缺失；❌ `FactorResult` / `Status` 生产方规则缺失 |
| **M1.4 评价与候选池** | ✅ 评价框架、八项准入、四态 Evaluation Status、Data Completeness、MAR 三模式、Ranking / Percentile 公式、Tie Method、Tier 五档与边界条件全部有确切值 | ❌ `factor_effectiveness` 不存在 → **总分不可产出**（`score_status = VALIDATION_PENDING`）；⚠️ 候选池部分需另抽 `05-fund-selection.md` |

---

## 16. 溯源核对清单（供回查）

| 本 digest 节 | 主要出处 |
|---|---|
| §1 维度/子分映射 | `FE:146-159`、`FE:763`、`FS:91-133`、`BR:999-1010` |
| §2 进入 SCORING 的 Factor | `FE:166-177`、`BR:935-987`、`BR:240-258`、`BR:771-893`、`FS:171-208` |
| §3 不进 SCORING | `FE:179-189`、`BR:956-985`、`BR:917-927`、`BR:977-979` |
| §4 Status 语义 | `FE:190-199`、`FS:368-377`、`FS:458-467`、`FS:241-250` |
| §5 Analysis Period | `BR:699-762`、`FE:203-233`、`FE:324-338`、`FR:132-140` |
| §6 Fund Score 结构 | `FS:89-167`、`FS:254-362`、`FS:366-421`、`FS:425-456`、`FS:557-591`、`BR:991-1043` |
| §7 Eligibility / Min Data | `FE:277-338`、`FE:342-374`、`BR:751-762`、`BR:1030-1039` |
| §8 Evaluation Status | `FE:384-407`、`FE:649-661` |
| §9 MAR Policy | `FE:427-503` |
| §10 Risk-free Rate | `FE:411-423`、`FE:354`、`FE:525`、`FR:116` |
| §11 Peer Group | `BR:477-597`、`FR:73-116`、`FE:263-273`、`FE:563-584` |
| §12 Ranking / Tier | `FR:120-482`、`FC:104-254`、`BR:1047-1104` |
| §13 四个前视来源 | `FE:236-273`、`BR:644-657` |
| §14 TBD | `FE:793-804`、`FS:710-719`、`FR:583-590`、`BR:2515-2559` |
| §15 缺失文档 | 仓库文件系统核实 + 全文引用点 grep |
