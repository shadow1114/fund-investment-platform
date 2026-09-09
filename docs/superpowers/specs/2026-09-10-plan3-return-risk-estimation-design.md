# Plan-3 收益与风险估计设计

> 日期：2026-09-10
> 状态：待评审
> 对应主链：Stage ⑤ Risk / Correlation Analysis
> 上游：Plan-2 Fund Universe 快照
> 下游：Stage ⑥ Portfolio Construction

## 1. 目标与范围

Plan-3 从冻结的 `FundUniverseSnapshot` 和 PIT 历史序列独立产出两套不可混用的
估计结果包：

```text
EstimationBundle = (return_basis, mu, Sigma, rho, variance, volatility,
                    instrument_order, lineage, diagnostics, validation)
```

- `ABSOLUTE`：主结果包，是 M1 唯一允许进入 Stage ⑥ 的口径。
- `EXCESS`：相对各基金 PIT Benchmark 的并行对照结果包，不在 M1 进入优化器。

本计划实现当次估计及同步 Validation Gate。周期性 OOS 质量评估，包括 Return MAE、
Risk RMSE、稳定性漂移和 VaR Kupiec POF，拆分为后续 Plan-3B，不阻塞 Plan-3 核心交付。

本计划不消费 Factor Value 作为估计值，不定义组合问题，不求解权重，不实现回测
时间轴，也不实现 Plan-3B 的调度和未来实现值解析。

## 2. 前置事实

- Plan-2 已产出版本化 `FundUniverseSnapshot` 和 PIT NAV 读取路径。
- PIT 数据入口是 `PitDataContext`；领域算法不得自行接收或推导 `decision_at`。
- `portfolio_service` 与 `backtest_service` 仍为空骨架。
- `mu`、`Sigma`、`rho` 和未来的 `w` 必须使用同一基金集合与顺序。
- 只有主 `ABSOLUTE` 结果包通过当次 Validation Gate 后才能进入 Stage ⑥。
- Plan-2 的 Benchmark 相对指标尚未进入生产；Plan-3 的 EXCESS 是独立对照产物，
  不改变该事实。

## 3. 参数基线与状态

以下参数均为 Plan-3 生产基线。任何 `PROVISIONAL` 参数在 LIVE 模式下 fail closed。

| 参数 | 基线 | 状态 | 理由 |
|---|---:|---|---|
| Primary Return Basis | `ABSOLUTE` | DECIDED | 作为 M1 优化主输入 |
| Secondary Return Basis | `EXCESS` | DECIDED | 作为并行对照输出 |
| Excess Benchmark | PIT Fund Benchmark | DECIDED | 与平台 Return Basis 定义一致 |
| Return Type | `SIMPLE` | DECIDED | 可进行横截面线性加总 |
| Lookback Window | `756` 交易日 | DECIDED | 三年日频窗口 |
| Forecast Horizon | `QUARTER` | DECIDED | 与季度调仓一致 |
| Observation Frequency | `DAILY` | DECIDED | 协方差生产频率 |
| Canonical Numeric Scale | `ANNUALIZED` | DECIDED | Stage ⑥统一消费尺度 |
| Annualization | `252` | DECIDED | 平台统一口径 |
| Return Method | Historical Mean + James-Stein | DECIDED | 降低均值估计误差 |
| Risk Method | Sample Volatility | DECIDED | 与协方差对角线保持单一真值 |
| Covariance Method | Ledoit-Wolf Constant Correlation | DECIDED | 降低高维小样本不稳定性 |
| Missing Observation | Complete case, no fill | DECIDED | 不制造虚假低波动与相关性 |
| Outlier Handling | None | DECIDED | 不修改输入收益尾部 |
| Mu Bound | Cross-sectional mean +/- 2 sigma | DECIDED | 仅约束最终期望收益并留痕 |

`Forecast Horizon=QUARTER` 表示估计的适用持有期和失效周期；生产数值统一存为年化
尺度。日频算术均值乘 `252` 得到年化 `mu`，日频协方差乘 `252` 得到年化
`Sigma`，`volatility = sqrt(diag(Sigma))`。不得再乘季度交易日数。Stage ⑥必须使用
同一结果包中的年化 `mu` 和年化 `Sigma`，风险厌恶参数也必须按该尺度解释。
`ApprovedEstimationProvider` 不做季度换算；若未来需要持有期数值，必须在独立版本化
适配器中同时按 `63 / 252` 缩放 `mu` 和 `Sigma`，不得只转换其中一个。

## 4. 核心裁定

### D-1：估计层拥有独立版本闭包

Historical Return Factor 与 Expected Return 语义不同。每个 Estimation Run 必须引用：

- `estimation_method_version_id`：算法身份、公式版本和代码入口；
- `estimation_parameter_version_id`：窗口、频率、年化、收缩目标等参数；
- `estimation_policy_version_id`：运行编排、主次口径和批准规则；
- `validation_policy_version_id`：阈值、严重级别和 Gate 规则；
- `code_version`：可部署代码版本。

`estimation_policy` 可以包含完整配置快照，但 Method 与 Parameter 仍须独立持久化，
以支持方法不变而参数升级。不得直接把 `F-RET-001` 写入 `mu`。

### D-2：Universe Snapshot 是输入身份，结果顺序显式冻结

运行从 `FundUniverseSnapshot` 读取 `SELECTED` 成员，按 `share_class_id ASC` 排序。
排序结果复制到每个结果包的 `instrument_order`；向量和矩阵只按该顺序解释。

当前 Universe 表不保存位置，因此不得依赖数据库返回顺序或成员插入顺序。Plan-3
不修改 Plan-2 快照结构，排序规则本身属于 Estimation Method Version。

### D-3：完整案例对齐必须确定且不可启发式剔除

每个 Return Basis 独立执行以下步骤：

1. 按冻结顺序加载成员；NAV 不可用、有效收益不足 2 个的基金进入该 basis 的
  `excluded_instruments`。
2. EXCESS 还要求逐日 PIT Benchmark 及 Mapping 可用；不可用只排除该基金的 EXCESS，
  不影响 ABSOLUTE。
3. 对剩余基金的有效收益日期取一次交集，形成不含 NaN 的稠密 `T x N` 矩阵；不
  forward-fill、backfill、zero-fill，不做 pairwise deletion。
4. `dropped_dates` 定义为各列有效收益日期并集减最终交集。非交易日不会进入单基金
  的有效收益序列，因而不标记为数据缺失；Plan-3 不新增交易日历依赖。
5. 对齐后若 `T < 3N`，拒绝整个 basis。不得继续按缺失率、历史长度或 ID 逐只剔除
  直到门槛通过；`3N <= T < 5N` 产生 WARNING。

ABSOLUTE 与 EXCESS 独立确定候选成员和 observation dates；两者不要求相同的 `T`、
`N` 或日期集合。每个结果包内部必须自洽，且 EXCESS 不得借用 ABSOLUTE 的矩阵、
风险或日期 fingerprint。

结果必须保存 `candidate_count`、`included_count`、`excluded_instruments`、
`dropped_dates_count`、对齐起止日期和最终 observation-date fingerprint。

### D-4：协方差对角线是风险单一真值

`variance[i] = Sigma[i, i]`，`volatility[i] = sqrt(Sigma[i, i])`。Risk Service 不得
用另一套参数重算生产值。Ledoit-Wolf constant-correlation target 必须保留样本方差
对角线；若实现不能保证这一性质，则该实现不可登记为当前 Method Version。

与 `F-RISK-001` 的交叉核对只有在窗口、日期 fingerprint、收益类型、`ddof` 和年化
规则完全相同时才是 `COMPARABLE`。`COMPARABLE` 且相对误差超过 `1e-6` 时阻断；
lineage 不同则记录 `NOT_COMPARABLE` WARNING，不得用两个不同样本强行做阻断比较。

### D-4A：收益与协方差解析式固定

令共同完整样本为 `X`，shape 为 `T x N`。样本均值 `m` 和样本协方差 `S` 均使用
float64；`S = cov(X, rowvar=False, ddof=1)`。

Expected Return 使用 positive-part James-Stein grand-mean shrinkage：

```text
target = mean(m)
mean_variance = trace(S) / (N * T)
dispersion = sum((m_i - target)^2)
delta_mu = clip((N - 3) * mean_variance / dispersion, 0, 1)
mu_daily = (1 - delta_mu) * m + delta_mu * target
mu_annual = clip_cross_section(mu_daily * 252, mean +/- 2 * sample_std)
```

要求 `N >= 4`、`T >= 2` 且 `dispersion > 0`。`dispersion == 0` 时所有样本均值已等于
target，固定 `delta_mu=1` 且结果保持不变；其他非有限或退化输入拒绝，不静默退化为
样本均值。横截面标准差使用 `ddof=1`；截断作用于收缩后的年化 `mu`。

Covariance 使用 Ledoit-Wolf constant-correlation analytic shrinkage。实现固定采用
Ledoit-Wolf 2003 的 `pi_hat`、`rho_hat`、`gamma_hat` 解析式；样本矩阵 `S` 使用
`ddof=1`，目标矩阵 `F` 的对角线严格复制 `diag(S)`，非对角线为平均样本相关系数乘
对应标准差。`delta_sigma = clip((pi_hat - rho_hat) / (gamma_hat * T), 0, 1)`，最终
`Sigma = ((1 - delta_sigma) * S + delta_sigma * F) * 252`。

`gamma_hat == 0` 表示 `S` 已等于目标，固定 `delta_sigma=1`；任何非有限输入、
`N < 2`、`T < 2` 或非正样本方差均拒绝。不做最近 PSD 投影；超出 D-7 数值容差的
负特征值由 Validation Gate 拒绝。算法只依赖 NumPy，并将 NumPy 声明为项目运行依赖；
不得引入 sklearn 或其他 ML 依赖。

### D-5：相关矩阵只由协方差矩阵推导

不独立估计 `rho`：

`rho[i,j] = Sigma[i,j] / sqrt(Sigma[i,i] * Sigma[j,j])`

零方差会使相关矩阵未定义，因此包含零方差资产的 basis 必须被 Validation Gate
拒绝，而不是填 0 或 1。

### D-6：ABSOLUTE 与 EXCESS 是两个完整结果包

EXCESS 定义为基金简单收益减去该日有效 PIT Fund Benchmark 简单收益。Benchmark
Mapping 按 `effective_from <= date < effective_to` 且 `available_at <= visible_until`
解析。映射变化时，各段使用对应 Benchmark；变化后的首个日期因无法跨两个指数计算
同口径单期 Benchmark Return 而删除。结果记录 WARNING、删除日期和全部 Mapping /
Index version lineage。Composite Benchmark 必须保留各 Component 及其权重。

切换日删除发生在单基金 EXCESS Return 序列生成阶段；该日期随后通过 D-3 的日期交集
自然从整个 EXCESS 矩阵删除，不影响 ABSOLUTE。Benchmark 或 Component 权重变化均视为
Mapping segment 变化；segment 内权重固定，边界日使用新 segment 且删除该日收益。

每个 basis 独立生成 `mu`、`Sigma`、`rho`、风险、顺序、排除清单和 Validation。
禁止共享矩阵或把一个 basis 的任一向量与另一 basis 的矩阵组合。

M1 的 `ApprovedEstimationProvider`：

- 只接受 `return_basis=ABSOLUTE`；
- 只返回同一 Run、同一 basis、同一 `instrument_order` 的 `mu` 与 `Sigma`；
- EXCESS 即使校验通过也保持 `approved_for_optimization=false`。

### D-7：Validation Gate 只处理当次可观测事实

阻断校验：

- 输入质量、最小样本和 `T >= 3N`；
- 所有数值有限；
- `Sigma` 维度正确、对称、对角线严格为正；
- `Sigma` 的最小特征值不低于 `-1e-8 * max(lambda_max, 1e-16)`；
- `rho` 维度正确、对称、对角线为 1 且元素位于 `[-1, 1]`；
- Risk 与 `Sigma` 对角线恒等；
- 可比较的 Factor 风险交叉核对通过；
- Method、Parameter、Policy、Validation Policy 均可用于当前 Runtime Mode。

WARNING：

- `3N <= T < 5N`；
- Benchmark Mapping 在窗口内变化；
- Factor 风险 `NOT_COMPARABLE`；
- 条件数 `> 1e4`。
- 数据覆盖率或横截面分布达到告警阈值。

条件数 `> 1e6` 属阻断校验；非有限条件数同样阻断。

Return MAE、Risk RMSE、稳定性漂移和 VaR Kupiec POF 属 Plan-3B，不改变历史 Run 的
批准状态。

### D-8：PIT 与血缘是构造性约束

输入组装只接收已绑定 `decision_at` 的 `DecisionExecutionContext`，并通过
`PitDataContext` 访问 NAV、Benchmark 和交易日历。每个 basis 保存：

- NAV effective date、version、availability quality；
- Benchmark Mapping 和 Index version lineage（EXCESS）；
- adjustment policy version；
- Universe Snapshot ID；
- Method、Parameter、Policy、Validation Policy 和代码版本；
- observation window、forecast horizon、return basis、numeric scale；
- excluded instruments、data completeness 和 observation fingerprint。

### D-9：运行状态、批准状态与事务边界分离

运行状态：`PENDING` / `RUNNING` / `COMPLETED` / `COMPLETED_WITH_WARNING` /
`REJECTED` / `FAILED`。不存在 `APPROVED` 运行状态。

- Validation 未通过：提交结果、Validation 明细和 `REJECTED` 状态，用于审计；
  `approved_for_optimization=false`。
- 主 ABSOLUTE 结果通过：Run 为 `COMPLETED` 或 `COMPLETED_WITH_WARNING`，并设置
  `approved_for_optimization=true`。
- EXCESS 的失败不撤销已通过的 ABSOLUTE，但 Run 至少为 `COMPLETED_WITH_WARNING`。
- 未处理系统异常：计算与结果事务回滚；使用独立短事务将预先创建的 Run 更新为
  `FAILED` 并保存错误分类，不保存部分结果。

状态转换固定为：短事务 A 创建 `PENDING` Run 并立即置为 `RUNNING` 后提交；事务 B
完成输入组装、计算、Validation、结果写入，并在同一提交中写入最终状态和
`approved_for_optimization`。事务 B 异常时整体回滚，短事务 C 将该 Run 从 `RUNNING`
置为 `FAILED`。读取端只暴露最终状态；`PENDING` 和 `RUNNING` 均不可消费。

ABSOLUTE Gate 失败时 Run 固定为 `REJECTED`，无论 EXCESS 结果如何。ABSOLUTE 通过且
EXCESS 失败或产生 WARNING 时为 `COMPLETED_WITH_WARNING`；两者均无 WARNING 时为
`COMPLETED`。每个 basis 的独立结论保存在 `estimation_validation_result`，Run 上的
批准布尔值只代表 ABSOLUTE。

## 5. 模块边界

```text
strategy_library/estimation/
  returns.py       纯收益估计算法
  alignment.py     确定性完整案例对齐
  covariance.py    协方差收缩与相关矩阵推导
  validation.py    纯校验函数

services/portfolio_service/estimation/
  models.py        ORM 与持久化契约
  repositories.py  幂等写入和只读查询
  inputs.py        Universe + PIT NAV/Benchmark 输入组装
  service.py       运行生命周期与业务结果事务编排
  policy.py        配置加载与版本持久化
```

`strategy_library` 不依赖 SQLAlchemy。`portfolio_service` 不依赖 `factor_service`；Factor
交叉核对通过只读 Protocol 注入。EXCESS 数据通过 `PitDataContext.benchmarks()` 读取，
不直接依赖 Benchmark Repository 实现。

Plan-3 必须扩展两个只读端口：

```text
BenchmarkPitRepository.resolve_history(
  share_class_id, classification_code, date_from, date_to
) -> tuple[BenchmarkResolutionSegment, ...]

FactorRiskCrossCheckProvider.load_candidates(
  share_class_id, decision_id
) -> tuple[FactorRiskObservation, ...]
```

`BenchmarkResolutionSegment` 至少包含 effective interval、Mapping version、Composite
Components 和 Index versions。`FactorRiskObservation` 至少包含年化 volatility、
Factor Run/Value/Version IDs、observation fingerprint、return type、`ddof`、annualization
和 status。交叉核对在每次 Run 的 Validation Gate 中执行：按 ID 排序候选后，只有
恰好一个 AVAILABLE 候选与当前基金的 window、observation fingerprint、return type、
`ddof` 和 annualization 全部相同才为 `COMPARABLE`；零个或多个匹配均产生
`NOT_COMPARABLE` WARNING，不任意选择。采用的 Factor IDs 写入 Validation detail。

## 6. 数据模型契约

最小七表：

1. `estimation_method_version`
2. `estimation_parameter_version`
3. `estimation_run`
4. `return_estimate`
5. `risk_estimate`
6. `covariance_estimate`
7. `estimation_validation_result`

这七张是 Plan-3 新表。`estimation_policy_version_id` 和
`validation_policy_version_id` 均外键引用现有 `governance.policy_version`，其
`policy_kind` 分别为 `estimation` 和 `estimation_validation`，不新增重复 Policy 表。

`return_estimate` 和 `risk_estimate` 按 `(run_id, return_basis, share_class_id)` 一基金
一行；`covariance_estimate` 按 `(run_id, return_basis)` 一结果包一行。三者都必须包含
`return_basis`。`estimation_validation_result` 按 `(run_id, return_basis, code)` 一条规则
一行，Run 级规则允许 `return_basis` 为空。

`estimation_run.approved_for_optimization` 只表达主 ABSOLUTE 结果是否可供 Stage ⑥使用。

矩阵使用一行一个 Run + Basis 的下三角结构化载荷，不拆成 `N x N` 行。载荷至少包含
`shape`、`instrument_order`、`lower_triangle`、`numeric_encoding_version` 和 checksum。
Repository 按 `instrument_order` 装配逐基金 Return/Risk 行，并断言成员集合完全相等；
缺行、多行或未知成员均视为持久化完整性错误。

必须保存以下可解释性数据：

- 收缩前样本均值、收缩目标、实际 shrinkage intensity；
- 截断前 `mu`、截断后 `mu` 和逐基金 `mu_clipped`；
- 收缩前样本矩阵的最小特征值、最大特征值和条件数；
- 最终矩阵相同诊断量；
- `dropped_dates_count`、排除原因和输入 fingerprint；
- 每条 Validation 的 code、severity、status 和 detail。

数据库约束至少覆盖 Run + Basis 唯一性、向量成员唯一性、合法状态、合法 basis 和
不可为负的计数。Repository 不提供业务结果 UPDATE API。

## 7. 数值编码与幂等契约

幂等键为：

```text
(decision_id, universe_snapshot_id,
 estimation_method_version_id, estimation_parameter_version_id,
 estimation_policy_version_id, validation_policy_version_id,
 code_version)
```

数据库必须用唯一约束保证并发下只有一个 Run。命中相同键时：

- 输入 lineage fingerprint 相同：返回已有 Run，不新增业务记录；
- fingerprint 不同：抛出 `EstimationRunConflict`，不覆盖旧结果；
- 已有 Run 为 `RUNNING`：返回明确的 in-progress 结果，不启动第二次计算；
- 已有 Run 为 `FAILED`：只有显式 retry 操作可在行锁保护下复用同一 `run_id`，执行
  `FAILED -> RUNNING`；普通调用返回失败状态，不隐式重算，也不新增 Run。

`estimation_run.input_lineage_fingerprint` 是两个 basis fingerprint 的 canonical
SHA-256 聚合值。每个 basis fingerprint 对以下按 key 排序后的 canonical JSON 计算：

- Universe Snapshot ID 和 `instrument_order`；
- 每个 NAV observation 的 share class、date、value、effective/version/availability；
- EXCESS 的 Mapping、Component、weight 和 Index observation lineage；
- adjustment policy version、window、horizon、basis 和 numeric scale；
- excluded instruments、最终 observation dates 和 `dropped_dates`。

输入组装完成后、任何业务结果写入前计算 fingerprint。命中已有最终 Run 时仍需重建
输入并比较 fingerprint；这用于发现迟到修订改变历史可见数据的异常。basis fingerprint
分别存入结果载荷，聚合 fingerprint 存入 `estimation_run`。

计算使用 float64。持久化采用版本化的
`FLOAT64_SHORTEST_ROUNDTRIP_V1`：每个数保存为可无损恢复同一 float64 的十进制字符串，
checksum 对 canonical UTF-8 payload 计算。不得依赖 JSON 浮点格式化器的默认行为。

相同输入重建后，解码数值的绝对误差必须 `<= 1e-10`；交叉实现业务核对使用相对
误差 `1e-6`。禁止通过在比较前粗粒度四舍五入来满足复现要求。

## 8. 验收标准

1. 任意历史 `decision_at` 可重建相同 Universe、每个 basis 的收益矩阵、`mu`、
  `Sigma`、`rho` 和 Validation 结论。
2. 每个结果包内 `mu`、`Sigma`、`rho` 的成员集合与顺序完全一致。
3. ABSOLUTE 与 EXCESS 使用各自完整的数据、矩阵和血缘，不存在跨 basis 混配路径。
4. 缺失数据不填充；日期删除和基金排除原因完整落库且算法确定。
5. 非 PSD、零方差、样本不足或配置未批准时不得进入 Stage ⑥。
6. 相同输入重跑满足 `1e-10`，且在并发下不新增重复业务记录。
7. Validation rejection 可审计；系统异常不留下部分结果，并可看到 `FAILED` Run。
8. Backtest 与 Live 使用相同 Service，只替换 `DecisionExecutionContext`。
9. Stage ⑥只能读取通过 Gate 的 ABSOLUTE 年化 `mu`、`Sigma` 和精确顺序。

## 9. 明确不做

- CAPM、Factor Model、ML 预测
- Asset Class 层估计
- EXCESS 结果进入 M1 Portfolio Construction
- Expected Benchmark Return 预测或 EXCESS 到 ABSOLUTE 的还原
- 结构性断点自动检测
- Portfolio Construction / Optimization
- Backtest timeline、交易成本与再平衡
- 周期性 OOS 质量评估、调度和未来实现值解析（Plan-3B）
