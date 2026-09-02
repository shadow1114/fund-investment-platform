# Plan-2 设计定案 · M1.2 Peer Group + M1.3 因子 + M1.4 评价与候选池

**上游**：`docs/01-product/02-business-requirements.md`、`docs/04-factor/*`（实为
`05-fund-evaluation` 副本）、`docs/11-database/*`
**M1 设计**：`docs/superpowers/specs/2026-08-31-fund-platform-m1-design.md`
**Plan-1 交接**：`docs/superpowers/plans/2026-09-02-plan1-handoff.md`
**抽取清单**：`plan2-digest-factor-scoring.md`（1735 行）、`plan2-digest-universe-schema.md`（1749 行）

---

## 0. 本文档的定位

Plan-2 遇到的问题与 Plan-1 不同。Plan-1 的上游是完整的，难点在把它做对；
Plan-2 的上游**有整整一个域缺失**——因子域的八份文档
（`02-factor-taxonomy`、`03-factor-definition`、`05-factor-normalization`、
`06-factor-versioning`、`07-factor-validation`、`08-factor-output` 等）
在仓库里一份都不存在，`docs/04-factor/` 目录实际装的是 `05-fund-evaluation/` 的逐字节副本。

因此本文档**既要裁定，也要补齐**。两者严格分开标注：

| 标注 | 含义 |
|---|---|
| **【裁定】** | 上游有话说但自相矛盾/被 spec 抵触，我在两者之间做的选择。**可被上游文档推翻。** |
| **【补齐】** | 上游根本没有说，我自己定义的。**一旦拿到真正的因子域文档，应整体替换。** |

所有【补齐】项在代码里必须标注 `PROVISIONAL` 并写明本文档为来源，
沿用 Plan-1 已建立的 `value / status / source` 三元组机制。

---

## 1. 与 M1 设计 spec 的冲突

### D-1【裁定】因子有效性检验拉进 Plan-2，修正 spec 的 M1 边界

**冲突**：

- 上游 `02-fund-scoring.md:342,346`：「检验尚未产出 → 该 Profile 的 Score **不产出**，
  `score_status = VALIDATION_PENDING`」「`factor_effectiveness` 的存在性是 Score 产出的
  **前置条件，不是可选的补充信息**」。并明确堵死捷径：「❌『先按等权上线，等检验出来再调』
  → 与『未经检验就拍权重』**完全等价** → 差别只是拍的值恰好是等权」。
- M1 设计 spec §6.1：因子有效性检验（IC / ICIR / 分层单调性）与 `factor_effectiveness` 表
  **推到 M2**。

**裁定：上游胜，把最小可用的因子有效性检验纳入 Plan-2。**

理由不是「上游层级更高」，而是 **spec 在这里自相矛盾**：同一份 spec 的 M1.4 验收标准要求
「五子分 + 归因 + `Data Completeness`；排名 / 分位 / Tier」，而 Fund Tier 是**按总分的
Peer Group 分位**分层（`04-fund-classification.md` §6.2）。没有 `factor_effectiveness`
就没有总分，没有总分就没有 Tier，M1.4 的验收标准自己通不过。
而 spec 的定位是「只细化，不重定义」上游（§0.2），它无权推翻那条前置。

上游还把归属讲明了：`02-fund-scoring.md:350`「本域是消费方不是定义方：阈值属
`validation_policy`，**由 `04-factor` 产出检验数值**」——检验本就属于因子域，即 M1.3，
正在 Plan-2 范围内。所以这是**把一件本该在这儿的事收回来**，不是扩张范围。

**代价与边界**：Plan-2 只做「能让 Score 合法产出」的最小检验——IC、ICIR、以及按
`validation_policy` 阈值判定 `VALID` / `INVALID`。**不做**分层单调性、因子间相关性剔除
（`相关系数 > 0.8 视为冗余`）、Rolling 因子全家族——那些仍属 M2/M3。

### D-2【裁定】数据量前提：Plan-2 必须包含一次更大范围的净值灌入

IC / ICIR 是**横截面**统计量：同一时点全体基金的因子值与其后续收益的相关系数。
Plan-1 只灌了 3 只基金的净值，算出来的 IC 无意义（自由度不足，且 `MIN_PEER_GROUP_SIZE = 30`
根本达不到）。

**裁定**：Plan-2 包含一个批量灌数任务，目标量级 **≥ 300 只份额类别**。
这同时是 Plan-1 交接项 T19-3 的第一次真实检验——「`AdjustedNavUnavailable` 只在 CLI
单只调用点捕获，第一次写批处理循环就会重新踩到」。**该保护必须在本任务中下沉到
service 层**，而不是在 CLI 再包一层。

### D-3【裁定】`libs/` 两层在 src-layout 下的落位

spec §2.1 的目录树写的是顶层 `libs/quant_engine`、`libs/strategy_library`，但 Plan-1 实际
采用了 src-layout（`src/fip/platform`、`src/fip/services`）。

**裁定**：落位为 `src/fip/libs/quant_engine` 与 `src/fip/libs/strategy_library`。
一致性优先于字面路径；spec 的目录树表达的是**分层关系**，不是文件系统路径。

三条硬约束原样保留，并**各配一条适应度测试**：

| # | 约束 | 适应度断言 |
|---|---|---|
| SDL-1 | Strategy Library 不含数据访问实现 | 不得 import `sqlalchemy` / `psycopg` / `fip.services.*.repositories` |
| SDL-2 | 无 `runtime_mode` 分支 | AST 扫描：不得出现 `RuntimeMode` 的比较或分支 |
| SDL-3 | 纳入 Code Version | 该包的版本参与 Code Version 计算 |
| QE-1 | Quant Engine 不含业务语义 | 不得 import `fip.libs.strategy_library` / `fip.services` / `fip.platform`；标识符不得出现基金业务词汇 |

### D-4【裁定】补上 SB-1（每个 schema 写入权唯一）的适应度测试

Plan-1 的最终评审指出 SB-1「既没有实现，也没有出现在『明确不覆盖』清单里——它是**静默缺席**的」。
M1 只有一个写入方（`IngestService`）时它是空洞的。

Plan-2 引入 `factor_service`（写 `factor` schema）与 `fund_service`（写 `evaluation` schema）
之后，它**第一次有真实约束力**。裁定：本 Plan 补上该适应度测试。

---

## 2. Fund Classification（BLOCK-1，阻塞整个 M1.2）

### D-5【补齐】Fund Classification 采用 AKShare 的 `基金类型`，scheme 记为 `AKSHARE_FUND_TYPE`

**问题**：Peer Group 的划分维度是 `Fund Classification × Currency`
（`03-fund-ranking.md:105`），但 **Fund Classification 的层级结构在全仓文档中没有定义**。
名为 `04-fund-classification.md` 的文档，其 §1.2 开宗明义：「本文档定义的是 `Fund Tier`，
**不是** `Fund Classification`」——它讲的是按分位的五档分层。

**补齐**：用 AKShare `fund_name_em` 的 `基金类型` 列。依据有三：

1. **它已在数据契约里**：`datasets.py` 的 `fund_list.required_columns` 已包含 `基金类型`，
   只是 `ingest_fund_list` 读了却丢弃——与 Task 19 修掉的「`code` 被丢弃」同一个模式。
2. **Plan-1 已经建好承接它的表**：`fund.fund_classification_history` 是区间型表，
   字段恰为 `classification_scheme` + `classification_code`——scheme 限定的编码，
   正适合层级未固定的分类体系；区间型则对应「基金转型会改变分类，回测必须使用当时的分类」。
3. **它自带两级层次**（实测全市场 27718 只的取值分布）：

```
L1（大类，连字符前）: 混合型 指数型 债券型 股票型 货币型 FOF QDII Reits 商品 其他
L2（细分，完整串）  : 混合型-偏股 5693 · 指数型-股票 5589 · 债券型-长债 2797
                     混合型-灵活 2402 · 债券型-混合二级 1902 · 混合型-偏债 1451 …
```

**编码约定**：`classification_scheme = "AKSHARE_FUND_TYPE"`；
`classification_code` 存**完整原串**（L2）；L1 由 `code.split("-")[0]` 派生，
**不另存一列**——派生规则属 Strategy Library，不属数据。

> **这是【补齐】不是【裁定】**：AKShare 的类型划分是数据供应商的商业分类，
> 不是投研定义的资产类别体系。一旦有正式分类体系，应整体替换 scheme 值而非改代码。

### D-6【补齐】空 `基金类型` 映射为 `UNCLASSIFIED`，且不构成 Peer Group

实测全市场有 **99 只**基金的 `基金类型` 为空串。

**补齐**：空值映射为 `classification_code = "UNCLASSIFIED"`，如实落库（不丢弃、不猜测），
但**不得构成任何 Peer Group**——它不是一个类别，是「我们不知道它属于哪个类别」。
这两件事的区别正是 Plan-1 在 `grouping_status` 上反复吃过亏的那一条
（「没识别出后缀」≠「确认没有后缀」）。

落在这一类的基金：Evaluation Status 为 `NOT_ELIGIBLE`，理由 `UNCLASSIFIED`，
**不进入任何横截面计算**。

### D-7【补齐】Peer Group 粒度默认取 L1，登记为 `PROVISIONAL`

这正是 spec 的待定项 `IMP-TBD-2`（「Peer Group 的划分粒度：基金分类的哪一层」，标注
「M1.2 前 · 投研」）。层次已由 D-5 确定为两级，选择在 L1 与 L2 之间。

**补齐（PROVISIONAL）**：默认 **L1**。理由是与 `MIN_PEER_GROUP_SIZE = 30` 的相互作用——
判定基数是 `n_effective`（某指标的有效参与数）而非组规模。按 D-2 的 300 只量级，
L2 分组会落在 10~60 只区间、大量组触发 `INSUFFICIENT_SAMPLE`；L1 分组约 30~100 只，
才能让横截面派生量真正产出。

配置项 `peer_group.classification_level`，取值 `L1` / `L2`，`status: PROVISIONAL`，
`source` 指向本节。**不得硬编码。**

---

## 3. 因子清单与公式（整个因子域文档缺失的补齐）

### D-8【补齐】M1 因子清单：10 个

上游 `02-business-requirements.md` §14.2 的 Factor Usage Matrix 给了 `SCORING` 列打勾的
因子清单，但公式在缺失的 `03-factor-definition` 里。M1 设计 spec §6.1 要求「8~10 个因子
（收益 / 风险 / 风险调整 / 稳定性四类）」。

从 SCORING 清单出发，扣除两类**在 M1 结构上不可算**的：

| 扣除 | 原因 |
|---|---|
| REL 全类（Alpha、Beta、Information Ratio、Tracking Error、Benchmark 超额收益） | Benchmark 四层建模推到 M2（spec §6.2）。**这不是缺陷**——Relative Performance Score 正确呈现为 `UNAVAILABLE`，正是 M1 用来跑通 `Data Completeness` 机制的设计（spec §6.2 明载） |
| 费率 | `fund.fund_fee` 表 Plan-1 建了但**从未灌数**。费率是 `SCORING` 打勾项，M1 无数据源 → `UNAVAILABLE`，**不得静默填 0** |
| VaR 95% / CVaR 95% | 需先定分布方法（历史法 / 参数法 / Cornish-Fisher），属【补齐】中风险最高的一类；且 MDD + Downside Volatility 已覆盖下行风险维度。**推到 M2** |
| Rolling Volatility / Rolling MDD | 上游 spec §6.1 明确把「Rolling 因子全家族」推到 M2；本 Plan 只保留 Rolling Return 与 Rolling Sharpe 两个 |

得到 10 个：

| Factor ID | 名称 | 类别 | 子分 | Preference Direction | 依赖 |
|---|---|---|---|---|---|
| `F-RET-001` | 年化收益率 | RET | Return | `HIGHER_IS_BETTER` | 复权净值 |
| `F-RET-002` | Rolling Return | RET | Return | `HIGHER_IS_BETTER` | 复权净值 |
| `F-RISK-001` | Volatility（年化） | RISK | Risk | `LOWER_IS_BETTER` | 复权净值 |
| `F-RISK-002` | Downside Volatility | RISK | Risk | `LOWER_IS_BETTER` | 复权净值 + **MAR** |
| `F-RISK-003` | Maximum Drawdown | RISK | Risk | `LOWER_IS_BETTER` | 复权净值 |
| `F-RAP-001` | Sharpe Ratio | RAP | Risk-Adjusted | `HIGHER_IS_BETTER` | 复权净值 + **R_f** |
| `F-RAP-002` | Sortino Ratio | RAP | Risk-Adjusted | `HIGHER_IS_BETTER` | 复权净值 + **MAR** |
| `F-RAP-003` | Calmar Ratio | RAP | Risk-Adjusted | `HIGHER_IS_BETTER` | 复权净值 |
| `F-STAB-001` | Win Rate | STAB | Stability | `HIGHER_IS_BETTER` | 复权净值 |
| `F-STAB-002` | Rolling Sharpe 稳定性 | STAB | Stability | `HIGHER_IS_BETTER` | 复权净值 + **R_f** |

> `F-RAP-001` = Sharpe 与 `F-REL-002/003/004` = Alpha/Beta/IR 这四个 ID 是从现存文档中
> **泄露出来的真实 ID**（`plan2-digest-factor-scoring.md` 已标出），故编码风格照此沿用。
> 其余 ID 为【补齐】。

**MAR 依赖的连带后果**（上游 `01-fund-evaluation.md:472-481`）：`mar_policy` **必填且无默认**，
未配置时 `F-RISK-002` 与 `F-RAP-002` 一律 `UNAVAILABLE`。理由是「两者数值相同但含义相反——
设默认会让配置遗漏静默产出看起来正常的 Sortino」。**不得给 MAR 设兜底值。**

### D-9【补齐】因子公式与 Metric Version 登记

全部登记到 `config/strategy/metric/v1.yaml`，沿用 Plan-1 的三元组。
标 `DECIDED` 的是**标准无歧义**的定义；标 `PROVISIONAL` 的是**真正的口径选择**。

收益率序列一律取自**复权净值**（Plan-1 已构造性保证其 PIT 正确性），
对数收益还是简单收益是口径选择：

| 口径项 | 取值 | status | 理由 |
|---|---|---|---|
| `return_basis` | `SIMPLE`（简单收益 `r_t = P_t/P_{t-1} − 1`） | `PROVISIONAL` | 与年化、Sharpe 的行业惯例一致；对数收益不可横截面相加，但时序可加。两者在长窗口下差异可观 |
| `annualization.trading_days_per_year` | `252` | `DECIDED`（Plan-1 已登记） | `10-api/01 §12.3` 明确 |
| `volatility.ddof` | `1`（样本标准差） | `PROVISIONAL` | 样本 vs 总体在 n 较小时差异不可忽略；文档未给 |
| `annualized_return.method` | `GEOMETRIC`（`(P_T/P_0)^(252/N) − 1`） | `PROVISIONAL` | 与算术年化在波动大时差异显著 |
| `max_drawdown.basis` | `ADJUSTED_NAV` | `DECIDED` | 回撤必须含分红再投资，否则分红当天被记成回撤 |
| `win_rate.frequency` | `MONTHLY` | `PROVISIONAL` | 日频胜率接近 50% 无区分度；文档未给频率 |
| `rolling.window_days` / `rolling.step_days` | `252` / `21` | `PROVISIONAL` | 文档未给 |
| `sharpe.risk_free_source` | `RISK_FREE_CURVE`（按 `policy/evaluation` 的 tenor 解析） | `DECIDED` | 上游要求 R_f 走 PIT 曲线 |

公式（全部年化到 252 交易日）：

```
r_t          = adj_t / adj_{t-1} − 1                         # SIMPLE
年化收益率    = (adj_T / adj_0)^(252/N) − 1                   # GEOMETRIC
Volatility   = stdev(r, ddof=1) × sqrt(252)
Downside Vol = stdev(min(r_t − MAR_daily, 0), ddof=1) × sqrt(252)
Max Drawdown = max over t of (1 − adj_t / running_max(adj)_t)   # 取正值，越小越好
Sharpe       = (年化收益率 − R_f) / Volatility
Sortino      = (年化收益率 − MAR) / Downside Vol
Calmar       = 年化收益率 / Max Drawdown                       # MDD = 0 时 UNAVAILABLE，不填 inf
Win Rate     = count(月度收益 > 0) / count(月度收益)
Rolling Sharpe 稳定性 = −stdev(滚动窗口 Sharpe 序列, ddof=1)   # 波动越小越稳定，取负使方向统一
```

> **`Calmar` 在 `Max Drawdown = 0` 时必须 `UNAVAILABLE`**，不得填 `inf` 或极大值——
> 这是 C-6 同类原则在因子层的体现。同理 `Sharpe` 在 `Volatility = 0` 时 `UNAVAILABLE`。

### D-10【补齐】Factor Status 四值的**生产方**触发条件

上游 `01-fund-evaluation.md` §7.3 只给了**消费方**处理规则（`VALID` 参与、`WARNING` 参与但
标记须传递、`INVALID` 不参与且告警、`UNAVAILABLE` 不参与按缺失处理），
生产方何时置哪个值在缺失的 `08-factor-output` 里。

**补齐**：

| Status | 触发条件 |
|---|---|
| `VALID` | 观测数 ≥ `min_obs`，且全部输入 Factor/依赖（R_f、MAR）均可用，计算未触发任何降级 |
| `WARNING` | 观测数 ≥ `min_obs` 但落在 `[min_obs, min_obs × 1.5)`；或输入序列的 `availability_quality` 链路中含 `INFERRED` |
| `INVALID` | 计算过程产生数学上无意义的结果（分母为 0、负方差、NaN） |
| `UNAVAILABLE` | 观测数 < `min_obs`；或必需依赖缺失（无 Benchmark、无 MAR 配置、无 R_f） |

`min_obs`【补齐，PROVISIONAL】：日频因子 `252`，Rolling 类 `504`（两个窗口），
月频（Win Rate）`36`。上游 `03-factor-definition` 的缺省值本身就标着 `<TBD-FD-3>`。

> `WARNING` 的第二个触发条件把 Plan-1 交接项「`availability_quality` 不沿链路传播」
> 接了起来——但**需要先做 Plan-1 交接的「收紧 PIT 数据契约」任务**（H-2 打包项），
> 否则 `NavPoint` 逐行的 quality 无法聚合成链路 quality。**任务顺序上必须在其后。**

### D-11【补齐】标准化与方向转换

缺失的 `05-factor-normalization` 被引用 9 次。三个必须自己拍板的点：

1. **标准化方法**：Peer Group 内 **Percentile Rank**，公式与 ranking 统一为
   `p = (N − Rank) / (N − 1) × 100`，`N = 1` 时 `UNAVAILABLE`（不是 50 也不是 100）。
   **【裁定】统一使用同一公式**——文档从未说两者一致，但用两套分位公式会让
   「因子分位」与「排名分位」对同一只基金给出不同的数，无法解释。
2. **`LOWER_IS_BETTER` 的方向转换**：**先取负再排分位**，而非排完再 `100 − p`。
   两者在**有并列时结果不同**（`COMPETITION_RANK` 下并列占用相同名次）。
   先取负使并列关系在同一侧保持，语义更干净。
3. **「中性」方向**：上游提到 Tracking Error 在 Active Equity 画像下方向为「中性」，
   而「中性」不属于四个方向枚举之一。M1 无 Benchmark、TE 恒 `UNAVAILABLE`，
   **本 Plan 不实现「中性」方向**，并在枚举注释里写明这是已知缺口。

---

## 4. 表设计裁定

### D-12【裁定】`factor_value` 的时点列统一为 `effective_at`（BLOCK-6）

`04-database-design.md` 内部矛盾：PK / 分区键写 `as_of_date`，而同一文件**已定案**的两个
部分唯一索引用 `effective_at`。

**裁定：统一为 `effective_at`。** 理由：`as_of_date` 在 Plan-1 落地的全部 20 张表中
**一次都没出现过**；版本化事实表的七列标准（`effective_at` / `available_at` /
`availability_quality` / `version` / `published_at` / `provider_available_at` / `ingested_at`）
是 Plan-1 已建成的地基，`factor_value` 作为版本化事实表必须与之一致。
`as_of_date` 是 API 层的查询参数名（PIT 语义），不是存储列名——两者混用是文档笔误。

### D-13【裁定】`factor_value` 的两个部分唯一索引原样采纳

上游已定案（SQL 已逐字抄入 digest），本 Plan 照抄。其中一对**相反的处理最容易做错**，
在此显式记录：

- `evaluation_policy_version` **是标识的一部分**（进唯一约束）——同一因子在不同评价政策下
  是不同的值；
- `risk_free_rate_ref` **是溯源，不进唯一约束**——它记录用了哪条 R_f，但不构成身份。
- `window` **不能省**——窗口不进 Factor ID，所以必须进唯一键。

### D-14【裁定】`peer_group_member` 不分区（BLOCK-7）

上游的 `peer_group_member` PK 不含分区键 `effective_at`，**在 PostgreSQL 层面不成立**
（分区表的 PK 必须包含分区键）。

**裁定：M1 不对该表分区。** 理由：分区是为数据量准备的，而 Peer Group 成员表的量级是
`快照数 × 组内基金数`，M1 规模（数百只基金 × 每日快照）远未到需要分区的程度。
Plan-1 已经证明分区表会带来真实成本（`fund_nav` 的 31 张子表在约束递归、TRUNCATE 级联、
迁移往返上都需要额外处理）。**不为了对齐一个本身不成立的文档设计而引入这份成本。**
若将来需要分区，届时 PK 必须包含 `effective_at`。

### D-15【裁定】`fund_universe_member.investment_eligibility` 存**版本引用**，不存取值副本（BLOCK-10）

上游未裁决。字面表述倾向存副本（§17.6 快照字段清单），架构偏好倾向引用（「引用而非复制」）。

**裁定：存指向 `fund.investment_eligibility` 的版本引用**
（`(share_class_id, effective_at, version)` 三元组，或其代理键）。

理由：快照闭包的目的是**可复现**，而引用 + Plan-1 的三时点 + version 已经构造性地保证了
「按 `available_at ≤ decision_at` 取当时那一版」。存副本则引入第二份真值，
两者一旦分叉无法判定谁对——这正是 Plan-1 在 `adjusted_nav` 标量列上花了三轮才想明白的教训
（标量副本装不下 `(行, decision_at)` 的二元函数）。

**但必须补一条**：`fund.investment_eligibility` 的行**永不删除、永不原地修改**
（已由三时点 + version 保证），且快照的 FK 为 `ON DELETE RESTRICT`。

### D-16 三张 `factor` 表的字段设计属【补齐】

`factor_definition` / `factor_version` / `factor_run` 在**全仓没有任何字段清单**
（`factor_value` 是唯一有的）。本 Plan 自行设计，形状随实现计划给出，遵循：

- `factor_definition`：因子的**身份**（`factor_id` 如 `F-RAP-001`、名称、类别、
  `preference_direction`、`factor_usage` 五列）。纯维度表，不带时序列。
- `factor_version`：因子的**口径版本**（公式版本、`min_obs`、依赖声明）。
  引用 `factor_definition`。属 Strategy Version 第 1 项，纳入版本化。
- `factor_run`：一次**计算批次**（`decision_at`、`code_version`、
  `evaluation_policy_version`、状态、耗时）。`factor_value` 引用它。
- `factor_effectiveness`（由 D-1 拉入）：`(profile, factor_id, valid/invalid, IC, ICIR, 检验区间)`。

### D-17【裁定】`REJECTED` 成员与逐条件结果全量落库

上游三处互相印证且明确「这不是可选项」「记录未通过的**全部**条件，而非首个」
「若只存入池成员 → 错误排除正是**幸存者偏差**的表现形式」。数据量从 50 行/次涨到
约 9600 行/次，文档明说「但这是必需的」。

**裁定：原样采纳，不做任何短路优化。** 并补一条测试：条件求值**不得短路**——
即第一个条件不通过时，其余条件仍须求值并落库。这是最容易被「优化」掉的一处。

### D-18 快照原子性：B1 与 B2 各自原子，不要求同一事务

`01-system-architecture.md:855`「三个边界各自原子」。B1 = `peer_group_snapshot` +
全部 `peer_group_member` 一并提交；B2 = `fund_universe_snapshot` + 含 `REJECTED` 的全部
member + 全部 `condition_result` 一并提交，并**引用已提交的 B1 快照 ID**。
B2 写入不完整 → 整体回滚，本次决策视为未产生。

---

## 5. 上游文档自身不自洽的裁定

### D-19【裁定】`score_status` 枚举统一为五值

文档有三种说法：`FS:590` 列三值（`COMPLETED` / `PARTIAL` / `UNAVAILABLE`）、
`FS:342` 引入 `VALIDATION_PENDING`、`FS:336` 又提到 `NOT_AVAILABLE`。

**裁定**：`NOT_AVAILABLE` 与 `UNAVAILABLE` 是同一概念的两种拼写，统一取 `UNAVAILABLE`
（与 Factor Status 的枚举一致）。最终五值：

```
COMPLETED           五子分齐全
PARTIAL             部分子分 UNAVAILABLE（M1 常态：Relative Performance Score 恒缺）
UNAVAILABLE         无任何子分可产出
VALIDATION_PENDING  factor_effectiveness 未产出（D-1 的前置未满足）
INSUFFICIENT_FACTORS 某子分内有效因子数低于阈值（FS:344）
```

> M1 的**常态是 `PARTIAL`**——因为 REL 子分恒 `UNAVAILABLE`。这必须被测试显式断言，
> 否则「`PARTIAL` 是正常的」这个事实会在下游被当成异常处理。

### D-20【裁定】Tie Method = `COMPETITION_RANK`

`03-fund-ranking.md` 的 D-9 仍写「Tie Method = TBD」，但同文件 §8.2 已定案
`COMPETITION_RANK`。**裁定：以 §8.2 为准**——决策登记表未同步更新是编辑遗漏，
正文的定案条目更晚且更具体。

### D-21【裁定】`Rolling Return` 归 RET

三处说法不一（RET / STAB）。**裁定归 RET**：它度量的是**收益水平**在滚动窗口下的取值，
而 STAB 度量的是**稳定性**（离散度）。`F-STAB-002` 用的是滚动 Sharpe 的**标准差**，
那才是稳定性。按「量纲」判断：Rolling Return 的量纲是收益率，Rolling Sharpe 稳定性的
量纲是无量纲比率的离散度。

---

## 6. Plan-2 的 Global Constraints

以下每一条都是**可验收项**，非建议：

| # | 约束 | 来源 |
|---|---|---|
| G-1 | `available_at ≤ decision_at` 是唯一可见性规则 | Plan-1 承重机制 |
| G-2 | 因子值 / Score 的可复现性容差 **1e-10**；同一输入重算必须一致 | spec §9.3 |
| G-3 | `UNAVAILABLE` 不得被任何填充值替代（0、上期值、inf、组内均值） | C-6 / 上游 §12 |
| G-4 | `data_completeness` 是**输出必备字段**，必须随 Score 一起呈现 | `FS` §13.1 |
| G-5 | Peer Group 构建**不得** import 评分 / Universe 模块（消除循环依赖） | C-4 / `FR-PEER-001` |
| G-6 | `mar_policy` 必填无默认；未配置则依赖 MAR 的因子 `UNAVAILABLE` | `FE:472-481` |
| G-7 | `MIN_PEER_GROUP_SIZE = 30`，判定基数是 `n_effective` **不是**组规模；三处（标准化 / 排名 / 分层）必须同一配置源 | `FR:105` |
| G-8 | `Rank` / `n_effective` / `Percentile` **三者都必须落库**——只存 Rank 则历史分位不可还原 | `FR` |
| G-9 | `Fund Tier` 不得单独输出，必须与组内 **Sharpe 中位数 + Maximum Drawdown 中位数**同屏；仅展示 Tier「视为违反本条」 | `04-fund-classification.md` §9.1 |
| G-10 | 同一 Peer Group 内多个 Evaluation Profile 时**按 Profile 拆分子排名**，不产出跨 Profile 统一排名 | `BR:569-597`（P1-2 已定案） |
| G-11 | `REJECTED` 成员与**全部**条件结果落库，条件求值不得短路 | `FS` §14.3/14.4 |
| G-12 | Strategy Library 三约束（SDL-1/2/3）+ Quant Engine 无业务语义，各配适应度测试 | spec §2.2 |
| G-13 | SB-1：每个 schema 写入权唯一（`factor` ← factor_service，`evaluation` ← fund_service） | spec §2.3 |
| G-14 | 所有【补齐】项在配置中标 `PROVISIONAL` 并指向本文档 | IMP-4 |

## 7. 已知缺口（如实登记，不掩饰）

1. **整个因子域文档缺失**，本文档 §3 全部为【补齐】。拿到正式文档后应整体替换。
2. **`Data Completeness` 的确切计算式**上游未给，本 Plan 定义为
   「实际参与评分的因子数 / 该 Profile 声明的因子数」，标 `PROVISIONAL`。
3. **Evaluation Profile 的定义**（四类画像的基础指标集与差异矩阵）在
   `02-business-requirements.md` §5.2.1，M1 只实现**一个** Profile，
   多 Profile 推到 M2（spec §6.1 已声明）。故 G-10 在 M1 是**空洞成立**的——
   必须写测试锁住它，否则 M2 加第二个 Profile 时会静默出错。
4. **因子有效性检验只做最小集**（IC / ICIR），不做分层单调性与相关性剔除。

---

## 8. 计划起草期的修正（pre-flight 扫描发现）

起草 Task 1–6 的过程中发现本文档与计划骨架的 10 处问题，逐条裁定如下。
**其中 P2-1 撤销了 D-3、P2-2 修正了一条前提错误的既有测试。**

### P2-1【撤销 D-3】`quant_engine` / `strategy_library` 留在 Plan-1 的落位

D-3 裁定这两个包落在 `src/fip/libs/`。**撤销。**

事实：Plan-1 **已经建好** `src/fip/quant_engine/` 与 `src/fip/strategy_library/`（空包），
且三处测试硬编码了这两个路径（`tests/unit/test_package_layout.py`、
`tests/fitness/test_architecture.py` 的 `_py_files(...)` 与 `GUARDED_ROOTS`）。
搬迁是纯粹的 churn，还要改三处测试。

spec §2.1 的目录树表达的是**分层关系**，不是文件系统路径——这一点 D-3 自己就写了，
却又反过来要求搬迁。**保持 `src/fip/quant_engine`、`src/fip/strategy_library`。**

### P2-2【严重】Peer Group 的落位会让 G-5 全程空洞

C-4 适应度测试 `test_peer_group_module_does_not_depend_on_scoring_or_universe` 扫描的是
`src/fip/services/fund_service/peer_group`，禁的前缀是
`fip.services.fund_service.{scoring,ranking,universe}`。而按分层，Peer Group 与 score /
ranking / universe **全都属 Strategy Library**。

更严重的是旁边那条「可见不静默」的守卫测试
（`test_peer_group_guard_is_visible_not_silent`）写着「该模块要到 **Plan-3（M1.5）**
才会创建」——**这个前提是错的**：spec §0.3 明定 M1.2 Peer Group 属 **Plan-2**，
M1.5（组合与决策）才是 Plan-3。Plan-1 留下了一条前提错误的守卫。

照原布局做下去的后果：Task 11 建完 Peer Group 之后，C-4 仍扫一个空目录恒真、
守卫仍 skip——**G-5 在整个 Plan-2 静默缺席**。这与 D-4 指责 SB-1「静默缺席」是同一种病。

**裁定**：Peer Group 逻辑落 `src/fip/strategy_library/peer_group/`；
**Task 11 必须同时改写这两条测试**（把扫描根指向真实位置、把守卫的 Plan-3 前提改正），
并且**先证伪**——在 Peer Group 建好后故意让它 import 评分模块，确认 C-4 会红。
不改这两条测试的 Task 11 视为未完成。

### P2-3 迁移编号顺延 + Plan-1 交接项四的归属

Task 5 是 `fund_classification_history` 的第一个写入方（实测 0 行），
正是 Plan-1 交接项四「趁表还空着」的时机，故它占用 **0016**。
**Task 7 顺延为 0017，Task 8 顺延为 0018。**

交接项四点名的另外三件事（`fund_manager_assignment` 的 `EXCLUDE USING gist` +
两个索引、`fund_fee` / `fund_status_history` 的开放区间唯一索引）在 18 个任务里
**一个都没有归属**。**裁定：并入 Task 1**（Plan-1 交接任务），与 H-1/H-2 一起做完。

### P2-4 现存配置直接违反 G-6

`config/policy/evaluation/v1.yaml` 里躺着 `mar.default: 0.0 (PROVISIONAL)`，
而 G-6 与 D-8 明写「`mar_policy` 必填无默认」「不得给 MAR 设兜底值」。
**裁定：Task 10 负责删除它**，并在 Task 10 的验收里显式断言「未配置 `mar_policy` 时
`F-RISK-002` / `F-RAP-002` 为 `UNAVAILABLE`」。

### P2-5 接口契约补四组缺失定义

契约自称唯一权威却漏了四组跨任务名字，一律补入：

1. **Code Version 计算入口**——SDL-3 要求「该包的版本参与 Code Version 计算」，
   而全仓 `code_version` 只是 `DecisionExecutionContext` 上一个 `str`，CLI 填字面量
   `"cli"`，**没有任何计算机制存在**。新增
   `fip.platform.versioning.compute_code_version()` 与 `CODE_VERSION_ROOTS`（Task 4）。
2. **分类编码常量与派生函数**——`CLASSIFICATION_SCHEME`、`UNCLASSIFIED_CODE`、
   `level_1(code)`、`is_groupable(code)`，住在 `strategy_library/peer_group/`
   （放 data_service 会让 Task 11 反向依赖）。**因此 Task 5 依赖 Task 4**，
   任务总览的「—」改为「4」。
3. **Task 2 的产出类型**——`NavSeries(points, chain_quality)` 与 `weakest_quality()`。
4. **quant_engine 的异常类型**——`compute_factor` 要把「观测不足 / 数学无定义」
   映射为 `UNAVAILABLE` / `INVALID`，契约里没有任何异常名。

### P2-6【采纳偏离】`chain_quality` 允许 `None` 以表达空序列

空 NavSeries 没有链路也就没有 quality，填任何默认值都违反 G-3。
**裁定**：`NavSeries.chain_quality: str | None`，并用 `__post_init__` 双向锁死
「空序列 ⟺ None」；`FactorInput.chain_quality` 保持 `str`
（无观测的因子输入根本不会被构造）。

### P2-7【补齐 D-5/D-6】分类的粒度落差与冲突归并规则

`fund_classification_history.fund_id` 指向 `fund.fund`（产品级），而 AKShare 的
`基金类型` 是**一行一个基金代码**（份额类别级）。实测 27718 行 / 15350 个产品主干中，
**有 4 个产品的份额类别给出不同的 `基金类型`**：

```
兴全盈禧多元配置三个月持有混合(FOF)   A=FOF-稳健型  C=FOF-均衡型
恒生ETF华夏                        指数型-海外股票 / 指数型-股票
中信建投民享稳健养老…发起式(FOF)      A=FOF-稳健型  Y=（空）
```

**归并规则（补齐）**：

| 情形 | 处置 |
|---|---|
| 恰好一个非空取值 | 取它（一个份额类别没给类型 ≠ 这只基金没有类型） |
| 全空 | `UNCLASSIFIED` |
| **两个及以上不同的非空取值** | **不写、如实上报**——照搬 `IdentityReassignment` 的先例，绝不静默挑一个 |

### P2-8 D-7 的分组规模假设到 Task 6 才可验证

D-7 假设「L1 分组约 30~100 只」。实测 L2 分布是重尾的（混合型-偏股 5693、
指数型-股票 5589），按 `--limit` 取列表前 N 行之后 L1 分组落在哪里**完全未知**。
**裁定**：Task 6 必须把真实的 L1 分组规模抄进任务报告，
且**不得为了凑够 `MIN_PEER_GROUP_SIZE = 30` 而调整任何东西**——
达不到就如实产出 `INSUFFICIENT_SAMPLE`，那正是该机制存在的意义。

### P2-9 `test_pit_repository_exposes_only_the_time_bounded_query` 会挡路

它用**集合相等**断言 `NavPitRepository` 的公开方法只有 `adjusted_nav_series`
（这条写得好，锁住了 PIT-A3）。但 Plan-2 要为 `risk_free_rate` 与
`fund_classification_history` 写第二、第三个 PIT 读取口——**正是 H-1 预警的场景**。
**裁定**：Task 10 / Task 11 必须显式修改这条断言，并在报告里说明新增的方法为何
仍然满足 PIT-A3（无时点参数、无 `get_latest`）。

### P2-10 autogenerate 闸门自动化

G-16 把「收工时 autogenerate 报告零操作」列为可验收项，但它至今**完全是手工的、
CI 不跑**。按 Plan-1 交接项六.1「只由阅读/推理保证的性质等于没有保护」，
这条目前没有保护。**裁定：Task 1 用 `alembic.autogenerate.compare_metadata`
把它写成集成测试**（约 15 行），与黄金快照互补——快照管 CHECK 表达式，
它管表/列/索引/唯一键。

---

## 9. 表设计起草期的追加裁定（Task 7–8）

### P2-11【采纳】`factor_value` 改用代理主键

**这是 BLOCK-6 之外的第二处矛盾，D-12 没覆盖到**：上游给的五列 PK 与它自己已定案的
两个部分唯一索引**互相抵消**——`ux_factor_value_with_policy` 存在的全部意义
就是让五元组相同、仅 `evaluation_policy_version` 不同的两行共存（D-13 前半句），
而五列 PK 会把这条定案索引变成**永不触发的死代码**；六列 PK 又不成立
（该列对非 MAR 因子必须为 NULL，NULL 不能进 PK）。

**裁定：代理主键，身份完全交给那两个部分唯一索引。**

### P2-12【采纳，补 BLOCK-4】`factor_value → factor_version` 用 FK，不留 VARCHAR 副本

D-16 只说了 `factor_version` 引用 `factor_definition`，没说 `factor_value` 怎么引。
**裁定：FK。** 与 D-15「引用而非复制」同一条原则。

### P2-13【采纳，补 BLOCK-14】`risk_free_rate_ref` 用列组而非 JSONB

并记一处**对不上的地方**：上游提到 `rate_source_quality` 的取值 `INTERPOLATED`，
而 Plan-1 的 `market.risk_free_rate` 用的是 `availability_quality_enum`
（EXACT / DERIVED / INFERRED），既没有插值路径也没有这个值。
**裁定：复用 Plan-1 的枚举**（一致性优先），并标为待重审——
若将来真的引入期限插值，那是一个新的 quality 维度，不应硬塞进 availability。

### P2-14【扩大 D-14 的授权】`factor_value` 与 `fund_score` 同样不分区

D-14 只授权了 `peer_group_member`。起草方把这两张也取消了分区，超出字面授权。

**裁定：批准扩大。** 理由：M1 量级（约 300 只 × 10 因子 × 少数决策日）远未到需要分区；
Plan-1 已证明分区表在约束递归、TRUNCATE 级联、迁移往返上都要额外处理。

**并记一条起草方的实测结论**：我原先担心的「部分唯一索引 + 分区表不兼容」
**在 PG 17 上不成立**（已在 `fip_dev` 上含子分区验证）——所以将来补分区没有结构性障碍。
**触发阈值**：若走向全市场（27718 只 × 10 因子 × 252 日 ≈ 7000 万行/年），
`factor_value` 必须分区；M1 规模不必。

### P2-15【采纳，补 BLOCK-9 前半】组内 Sharpe / MDD 中位数落 `fund_tier`

上游没说这两个中位数（G-9 要求与 Tier 同屏的那两个）落哪张表。

**裁定：落 `fund_tier`。** 起草方的理由正确且是 G-5 的直接推论：这两个中位数是
**因子派生量**，放进 `peer_group_snapshot` 会让 **B1 依赖因子计算**——
而 Peer Group 构建不得依赖评分链路。

**副作用如实登记**：组内 Sharpe 全 `UNAVAILABLE` 时该组不产出 Tier。
这是诚实的，符合 G-3。

### P2-16【采纳】副本 vs 引用按「会不会分叉」分别处理

D-15 定的是「引用而非复制」，但起草方指出这条不能无差别套用，并给出了正确的判据：

| 场景 | 处置 | 理由 |
|---|---|---|
| `fund_score_attribution.raw_value` | **保留副本** | `factor_value` 禁 UPDATE + version 钉死，**结构上不可能分叉**。与 `adjusted_nav` 不是一类问题——后者是 `(行, decision_at)` 的二元函数，标量列装不下；前者是一个已冻结的标量 |
| `fund_universe_member.investment_eligibility` | **复合 FK 版本引用** | 按 D-15 |

**并采纳一处起草方的额外发现**：复合 FK 复用 `share_class_id` 那一列，
能让**数据库自己保证**「引用的那一版确实属于这只份额类别」——代理键做不到这件事。

### P2-17【采纳，补 BLOCK-11】`selection_condition_result` 增加 `NOT_EVALUABLE`

上游除 `condition_version` 外**一个字段名都没给**，六列全属补齐。
起草方在 `PASS` / `FAIL` 之外加了第三个 outcome 值 `NOT_EVALUABLE`。

**裁定：采纳。** 理由正确：把「输入 `UNAVAILABLE` 所以判不了」记成 `FAIL`，
就是 G-3 在条件层的同一个错误——那是**编造了一个否定结论**，
而事实是「不知道」。

### P2-18【采纳】`fund_tier` 的分位阈值刻意不进 CHECK

阈值 5/20/50/80 属配置（C-1 明令阈值配置化）。写进 CHECK 的后果：
业务方改一次阈值就要发一支迁移，且**历史行会被新阈值判为违规**（C-8）。
**裁定：不进 CHECK。**

### P2-19 迁移编号最终确定

P2-3 已把 0016 给了 Task 5。起草稿用的是 0016/0017，**整合时统一顺延**：

| 迁移 | 归属 |
|---|---|
| `0016` | Task 5 —— `fund_classification_history` 开放区间唯一索引 |
| `0017` | Task 7 —— `factor` schema 五张表 |
| `0018` | Task 8 —— `evaluation` schema 九张表 |

---

## 10. 计算流起草期的追加裁定（Task 9–13）

### P2-20【修订 D-10】「分母为 0」不是 INVALID，是 UNAVAILABLE

D-10 把「分母为 0」列在 `INVALID`，而 D-9 与上游 `10-api/03` §4.3.5 把
`ZERO_MAX_DRAWDOWN` 明标为「**好消息型不可用**」。差别是实质的：
`INVALID` 会传导到 `evaluation_status = FAILED` **并须告警**——
按原 D-10 实现，**一只从未回撤的基金会触发告警**。

**修订 D-10 的表格**：

| Status | 触发条件（修订后） |
|---|---|
| `INVALID` | 计算过程产生**数学上无意义**的结果：NaN、负方差、序列自相矛盾 |
| `UNAVAILABLE` | 观测数 < `min_obs`；必需依赖缺失；**或分母为 0 这类良性不可算**（`ZERO_MAX_DRAWDOWN`、`ZERO_VOLATILITY`） |

### P2-21【修订 D-10】链路 quality 移出 `FactorStatus`，改为独立 `quality_flag`

D-10 的 `WARNING` 第二触发条件是「输入序列的链路含 `INFERRED`」。
而 **AKShare 链路 100% 是 `INFERRED`**（G-15）——两者相乘的结果是
**每个因子、每只基金、每个时点都是 `WARNING`，`VALID` 在 M1 完全不可达**。
下游若把 `WARNING` 当异常处理，M1 会表现为「什么都不正常」。

**修订**：`FactorStatus` 只反映**可计算性**，不反映**数据出处**。
链路 quality 移到 `FactorResult.quality_flag`（独立字段，取值即
`EXACT` / `DERIVED` / `INFERRED`），随结果传递但不占用 status。

`WARNING` 只保留第一个触发条件：观测数落在 `[min_obs, min_obs × 1.5)`。

> 这与 D-19「M1 常态是 `PARTIAL`」是同一类问题——**必须写测试把「常态」钉住**，
> 否则下游会把正常状态当异常。

### P2-22【修订接口契约】MAR 一律是逐期序列

契约的 `mar: Decimal | None` 是标量，**装不下 `RISK_FREE` 模式的 MAR 序列**。
取均值/首值/末值都是**伪造一个从未被决策的标尺**——与 `adjusted_nav` 标量列
那三轮的教训同型。

**裁定：`FactorInput.mar_daily: tuple[Decimal, ...] | None`，与收益率序列 1:1 对齐。**
三种模式统一产出序列，消费方**不分支**：

| 模式 | 产出 |
|---|---|
| `ZERO` | 全零序列 |
| `CUSTOM` | 常数序列（由 `mar_quotation_basis` 声明的年化口径折算到逐期） |
| `RISK_FREE` | 真实的 R_f 逐期序列 |

这样 `RISK_FREE` 在 M1 **可用**，不必登记为缺口。

### P2-23【采纳上游命名】MAR 第三模式是 `CUSTOM` 不是 `FIXED`

上游 `01-fund-evaluation.md` §16.3 逐字是 `CUSTOM`。它会进
`evaluation_policy_version` 的可复现链路，改名要带数据迁移，**现在定死**。
`CUSTOM` 模式**必填 `mar_quotation_basis`**（年化口径），一并实现。

### P2-24【补 D-16】`factor_effectiveness` 必须带 Peer Group 维度

D-16 给的是 `(profile, factor_id, valid/invalid, IC, ICIR, 检验区间)`——**漏了横截面**。
IC 是横截面统计量，而本平台的横截面**就是 Peer Group**。
同一因子在股票型有效、在债券型无效是**正常结果**；不带 `peer_group_key`
只能互相覆盖，或被迫跨组池化（把不同收益分布放进同一条相关系数）。

**裁定**：`factor_effectiveness` 增加 `peer_group_key` 与 `segment` 两列。
**Task 7 的实现者只看 D-16 不会知道这一条**，必须写进任务正文。

### P2-25【补】`peer_group_snapshot` 必须落「所用分类版本」

`FR-PEER-001` 与架构文档都要求 B1 = 组成员 + **所用分类版本**，
而 digest 明记「字段清单文档未给值」。缺了它，
「只存构建规则不存结果则历史不可重建」直接落空。

**裁定**：`peer_group_snapshot` 增加 `classification_history_ids`
（指向 `fund.fund_classification_history` 的引用集合）。

### P2-26【补 D-9】Rolling Return 的聚合式与两处单位

D-9 的公式表只有 9 条，`F-RET-002` 的**聚合式缺失**——滚动窗口年化收益率是个
**序列**，落成一个因子值需要一次聚合。

| 项 | 取值 | status |
|---|---|---|
| `rolling_return.aggregation` | `MEAN` | `PROVISIONAL` |
| `rolling.window_unit` | `NAV_POINTS`（净值点数，非自然日） | `PROVISIONAL` |
| `mar.daily_conversion` | `SIMPLE_DIVISION`（年化值 / 252） | `PROVISIONAL` |

### P2-27【补】`fund_share_class.base_currency` 不存在，需建

`FR:105` 把 Currency 定为 Peer Group **强制维度**、`FR:116` 要求它与 R_f 解析键
取自**同一字段** `fund_share_class.base_currency`——而 `grep base_currency src/` **零命中**。

**裁定**：Task 11 带一次 schema 变更（**迁移 0019**），新增：

- `base_currency`（如 `CNY`）
- `base_currency_source`（声明的推导规则，**不设 NOT NULL 兜底**）

AKShare 的 `fund_name_em` 不提供币种。第一版推导规则：
**全部 AKShare 场外基金以 CNY 计价**（QDII 投向海外但份额仍以 CNY 申赎），
`source = "DECLARED_RULE_ALL_AKSHARE_CNY"`，标 `PROVISIONAL`。

### P2-28【补接口契约】`normalize_peer_group`

契约的 `percentile_rank` 签名里**没有 `n_effective`、没有 Rank、没有阈值**，
单独承担不了 G-7/G-8。**裁定**：`percentile_rank` 保持纯内核不动，
接口契约补入承担那一层的函数：

```python
def normalize_peer_group(
    results: Sequence[FactorResult], direction: PreferenceDirection, min_size: int
) -> list[NormalizedFactor]:
    """排除 UNAVAILABLE/INVALID → 算 n_effective → 判 INSUFFICIENT_SAMPLE
    → 产出 (rank, n_effective, percentile) 三元组（G-8 要求三者都落库）。"""
```

### P2-29【补 File Structure】Threshold Resolver 的落点

`strategy_library/` 目录树漏了 threshold。**裁定**：
`strategy_library/threshold/mar.py`（纯函数）+
`services/factor_service/thresholds.py`（碰库的 R_f PIT 解析）。

### P2-30【补】R_f 溯源必须带 `curve_code`，`ParsedYieldPoint` 必须带 `currency`

- `risk_free_rate_ref` 的四个必备字段**不含 `curve_code`**，而 Plan-1 的
  `RiskFreeRate` 主键第一列就是它，中债同一天三条曲线（实测信用债 10Y 高约 30bp）。
  缺了它，溯源答不出「用的是哪条曲线」。**补为第五字段。**
- `ParsedYieldPoint` **不带 `currency`**，而 `RiskFreeRate` 主键含它——
  Plan-1 交接没提这个空档。**在适配器层补 `CURVE_CURRENCIES` 映射**（中债三条曲线均为 CNY）。

### P2-31 迁移编号再次顺延

| 迁移 | 归属 |
|---|---|
| `0016` | Task 5 —— `fund_classification_history` 开放区间唯一索引 |
| `0017` | Task 7 —— `factor` schema 五张表（含 P2-24 的两列） |
| `0018` | Task 8 —— `evaluation` schema 九张表（含 P2-25 的一列） |
| `0019` | Task 11 —— `fund_share_class.base_currency` + `base_currency_source` |

---

## 11. 评价流起草期的追加裁定（Task 14–18）

### D-22【严重 · Plan-1 代码 bug】`derive_eligibility` 的两个分支与上游语义互换

上游三处文档**完全一致**（`05-fund-selection.md:217-223` = `02-business-requirements.md`
§18.2 = `03-data/02-data-domain-model.md:400-406`）：

| 状态 | 含义 | 可持有 | 可减仓 |
|---|---|:---:|:---:|
| `HOLD_ONLY` | **暂停申购** | ✓ | ✓ |
| `NOT_TRADABLE` | 已清盘 / **暂停赎回** | — | ✗ |
| `EXIT_ONLY` | **即将清盘 / 转型** | ✓ | ✓ |

而 `src/fip/services/data_service/eligibility.py:56-61`：

```python
if subscription_open and not redemption_open:   # 暂停【赎回】
    return EligibilityStatus.HOLD_ONLY          # ← 上游说这是 NOT_TRADABLE
if not subscription_open and redemption_open:   # 暂停【申购】
    return EligibilityStatus.EXIT_ONLY          # ← 上游说这是 HOLD_ONLY
```

**两个分支都错了。** 而且该函数**自己的 docstring** 写着「『暂停申购』意味着不可加仓
但仍可持有与减仓」——与上游一致、与它自己的代码矛盾。

Plan-1 里它没有消费方，错了不显形。Task 16 一旦按 §9.3 消费它：
暂停申购（常见、良性、期满即恢复）→ 判 `EXIT_ONLY` → **不入池**；
暂停赎回（真正不可交易）→ 判 `HOLD_ONLY` → **入池并标注约束**。
**该排除的进了池，不该排除的被赶了出去**，而全部条件结果照常落库，没有一条测试会红。

**裁定**：修正为——

```python
if subscription_open and not redemption_open:
    return EligibilityStatus.NOT_TRADABLE   # 暂停赎回
if not subscription_open and redemption_open:
    return EligibilityStatus.HOLD_ONLY      # 暂停申购
```

并如实登记第二处缺口：`EXIT_ONLY`（即将清盘/转型）**根本不能由这两个布尔推出**，
它是生命周期条件。本函数**永不返回 `EXIT_ONLY`**——与既有的 `LIMITED` 缺口同类，
照那条的写法在 docstring 里写明。**并入 Task 1**（Plan-1 交接性质的修复）。

### D-23【补齐 C-2】子分层权重五项各 `0.2`，标 `PROVISIONAL`

上游只把**因子层**权重定案为 `EQUAL_WITHIN_VALID`，**子分层**推给「由 Profile 定义」，
而 `§8.5` 只定了个别因子在个别画像下的相对高低——**那四项在 M1 全都不可算**。
同时 `BR:278` 明确禁止「现在拍一个 25%/25%/25%/25%」。

于是：没有子分权重 → 没有总分 → 没有 Tier → M1.4 验收通不过。
**这正是 D-1 的同一条论证链，只是发生在上一层，而 D-1 没有处理它。**

**裁定**：`sub_score_weights` 五项各 `0.2`，`status: PROVISIONAL`，
`source` 写明「上游禁止拍板但未给值」。于是 LIVE 模式下每次取用都会发出
`ProvisionalParameterUsed` 告警——**这正是 IMP-4 的机制存在的理由**。
它与因子层的 `EQUAL_WITHIN_VALID` **性质不同**：后者已定案，前者是占位，不得混同。

### D-24【补齐 C-3】Profile 声明 13 个因子，可算 10 个，`data_completeness = 10/13`

若分母取「可算的 10 个」，则 `data_completeness ≡ 1.0`，
而 spec §6.2 与 M1.4 判据要求「Relative Performance Score 呈现为 `UNAVAILABLE`
**且 `Data Completeness` 反映之**」——理由是「基于 4 个子分的 85 分与基于 5 个子分的
85 分必须可区分」。分母取 10 会把这句话**静默抹掉**，M1 用来跑通 `UNAVAILABLE` 机制的
唯一场景随之消失。

**裁定**：区分**声明**与**可算**。Profile 声明 **13** 个（10 可算 + 3 个 REL），
分母取 13，M1 的 `data_completeness` 恒为 `10/13 = 0.76923077`。

三个 REL 取 D-8 已点名的、从现存文档中**泄露出的真实 ID**：
`F-REL-002` Alpha / `F-REL-003` Beta / `F-REL-004` IR。
Tracking Error 与 Benchmark 超额收益**不声明**——它们的真实 ID 未泄露，
凭空编号会在拿到正式文档时与真 ID 冲突。

**必须写进接口契约**：`FACTOR_IDS`（可算，10 个）与 `PROFILE_DECLARED_FACTOR_IDS`
（声明，13 个）是**两个不同的常量**。只定义前者的话，Task 14 的分母会静默变回 10。

### D-25【补齐 C-4】`score_status` 的层级与优先级

`FS:344` 说的是「某**子分**标 `INSUFFICIENT_FACTORS`」，而 D-19 把它列为
**基金层** `score_status` 的取值——两个层级被混进同一个枚举。

**裁定**：同一枚举用于两层（取值含义一致），基金层优先级钉为：

```
VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS > PARTIAL > COMPLETED
```

理由：越靠前的状态越是「这个分数**不能按字面使用**」的强信号。
M1 常态是 `PARTIAL`（REL 恒缺）——必须有测试显式断言它是**正常**的。

### D-26【裁定 C-5】`N = 1` 归入 `INSUFFICIENT_SAMPLE`

`FR §7.3` 要求 `N = 1` → `Percentile = UNAVAILABLE`（此时 `Rank = 1` 存在），
但 `fund_ranking` 的联动 CHECK 只允许两种形态，**没有第三种能容纳「有名次但无分位」**。

**裁定**：`N = 1` 归入 `INSUFFICIENT_SAMPLE`（生产配置下 `1 < 30` 恒成立，语义无损），
并用一条测试钉住。若将来 `MIN_PEER_GROUP_SIZE` 被调到 1，这条冲突会立刻显形——
测试的注释里要写明这一点。

### D-27【修正 D-3 的断言字符串】QE-1 / SDL-1

P2-1 撤销了 `libs/` 落位，但 D-3 表格里 QE-1 仍写「不得 import
`fip.libs.strategy_library`」——照抄它写出的检查**永远不会触发**（真实路径是
`fip.strategy_library`）。**这与 SB-1「静默缺席」是同一种病，只是换成了
「检查存在但永远为真」。**

**修正**：

| # | 断言（修正后） |
|---|---|
| QE-1 | `quant_engine` 不得 import `fip.strategy_library` / `fip.services` / `fip.platform` |
| SDL-1 | `strategy_library` 不得 import `sqlalchemy` / `psycopg` **以及 `fip.services.*`（含 repositories）** |

并记一处**既有实现的缺口**：现有 `tests/fitness/test_architecture.py` 查的是
`IO_LIBS`（顶层包名），**根本不检查 `fip.services.*` 前缀**。Task 4 落实 SDL-1
时必须把这一半补上。

### D-28【采纳 C-8 三条】

| # | 裁定 |
|---|---|
| BLOCK-9 | 组内 Sharpe / MDD 中位数落 `fund_tier`，**每行自带**。与 P2-15 结论一致，此处补上第二条理由：落 `peer_group_snapshot` 需要多一次 join 才能满足 G-9，而**「少 join 一次就违规」的约束活不长** |
| TBD-DBD-3 | `fund_score_attribution` 用**完整明细表**（非 JSONB）：`03-erd §9.3` 要求进入 `WHERE` / `GROUP BY` 的字段必须结构化，归因分析要按 `factor_id` 聚合 |
| — | `fund_score` / `fund_ranking` / `fund_tier` 的唯一约束**必须含 `profile_id`**。G-10 要求按 Profile 拆分子排名；不含它的唯一键会在 M2 加第二个 Profile 那天变成主键冲突，而**M1 全程不会显形** |

### D-29【采纳 C-9】A-2 判据的期望值与 D-24 联动

Task 18 的判据 A-2 期望 `data_completeness = 0.76923077`（10/13）。
这条依赖关系**是有意写出来的**：若 D-24 被改为「分母只算可算因子」，
A-2 的期望值要改成 `1.0`，而那样它就**退化成一条恒真的判据**，
M1.4 的完成判据「`Data Completeness` 反映之」随之失去被验证的对象。
**改一个必须改另一个**，任务正文要写明这条联动。
