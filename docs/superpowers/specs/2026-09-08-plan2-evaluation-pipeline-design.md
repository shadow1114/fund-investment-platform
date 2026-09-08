# Plan-2 评价闭环设计

> 文档版本：v1.1 | 日期：2026-09-08 | 阶段：M1.2–M1.4
>
> 上游：`2026-08-31-fund-platform-m1-design.md`
>
> 交接：`../plans/2026-09-02-plan1-handoff.md`

## 1. 目标

Plan-2 在 Plan-1 的 PIT 数据底座上交付可复现的评价闭环：

```text
Fund Data + Benchmark + Rf + Evaluation Policy
  -> Peer Group Snapshot
  -> Raw Factor
  -> OOS Effectiveness
  -> Normalized Factor
  -> Score / Rank / Tier
  -> Universe Snapshot
```

正式 Score 必须依赖 OOS 有效性结论；任何 `UNAVAILABLE` 均不得填 0、均值或上期值。

## 2. 范围

### 2.1 纳入

- Plan-1 交接中的 PIT 契约、区间约束、批处理错误隔离与缺失索引修复。
- 基金分类、费率、无风险利率和指数净值的接入及 PIT Repository。
- 版本化人工 Benchmark：基金级配置优先，内部分类默认配置兜底。
- Peer Group：内部标准二级分类 × `base_currency`，M1 支持四类。
- 15 个因子：M1 原 10 项，加 Alpha、Beta、Information Ratio、Tracking Error、R²。
- OOS IC、ICIR、分层单调性、Spearman 冗余检查。
- 五子分归因、正式总分、排名、Tier、Eligibility Rules 和 Universe 快照。
- Policy YAML 装载入库并由结果、快照引用版本 ID。

### 2.2 不纳入

- 招募说明书 Benchmark 自动解析、官方基准自动拆分与商业数据源。
- 完整 Walk-forward、市场状态分段和因子研究工作台。
- 组合优化、回测编排、前端和对外 API 实现。
- QDII、货币基金及无法映射到四类 Profile 的基金。

## 3. 已定案口径

### 3.1 分类与 Profile

内部标准二级分类码：

| Classification Code | Evaluation Profile | M1 |
|---|---|---:|
| `ACTIVE_EQUITY` | Active Equity | 是 |
| `PASSIVE_EQUITY` | Passive Equity | 是 |
| `BOND` | Bond | 是 |
| `HYBRID` | Hybrid | 是 |

Peer Group Key 为 `(classification_code, base_currency)`。上游分类先通过版本化映射转换为
内部码；无法映射时标记 `UNSUPPORTED_CLASSIFICATION`，不得动态创建新组。

### 3.2 Benchmark

解析优先级：基金级人工配置 > 内部分类默认配置 > `UNAVAILABLE`。

| Profile | 默认 Benchmark |
|---|---|
| Active Equity | 沪深 300 全收益指数 |
| Passive Equity | 沪深 300 全收益指数；基金级配置可覆盖为实际跟踪指数的全收益版本 |
| Bond | 中债综合全价指数 |
| Hybrid | 60% 沪深 300 全收益指数 + 40% 中债综合全价指数 |

Benchmark ID 是平台逻辑标识，Provider symbol 由版本化映射维护。配置必须记录
`effective_at`、`available_at`、来源和权重，禁止用当前映射回算历史。权益 Benchmark 必须为
`TOTAL_RETURN`；债券 M1 默认 Benchmark 为 `FULL_PRICE`，不得将“全价”误写成“全收益”。

### 3.3 MAR 与 Risk-free Rate

- MAR：显式 `ZERO`，不是缺省值。
- $R_f$：按 `fund_share_class.base_currency × evaluation_period` 解析主权收益率曲线。
- 精确期限缺失时只允许相邻期限线性插值；禁止跨币种 fallback。

### 3.4 Factor

原 10 项：`F-RET-001/002`、`F-RISK-001/002/003`、`F-RAP-001/002/003`、
`F-STAB-001/005`。

Benchmark 扩展 5 项：`F-REL-002/003/004/005`、`F-STAB-002`。R² 仅展示，不评分。

范围分为三层：长期 Catalog 共 26 项；M1 enabled 共上述 15 项；M1 scoring 为
`F-REL-002/003/004/005`、`F-RISK-003`，另加不注册 Factor ID 的 Expense Ratio。
其余 M1 enabled Factor 用于展示、筛选、研究或解释。

最小观测统一按窗口理论交易日的 90% 判定；回归类还必须不少于 60 个共同日期配对观测；
Rolling Sharpe 每个滚动点需完整 252 个观测，序列至少 12 个有效滚动点。

### 3.5 Validation Policy v1

- 必须存在 OOS 时间切分结果。
- $|IC| \ge 0.02$ 且方向一致。
- $|ICIR| \ge 0.3$。
- 分层收益总体单调方向一致。
- $|Spearman\ \rho| > 0.8$ 标记冗余，同组只保留解释性更强者参与评分。

检验结果只决定指标是否具备评分资格，不生成权重；没有 OOS 结论时状态为
`VALIDATION_PENDING`。组合层改善验证属于后续上线治理，不阻塞 M1.2–M1.4。

### 3.6 Profile 指标权重

| 指标 | Active Equity | Passive Equity | Bond | Hybrid |
|---|---:|---:|---:|---:|
| Alpha | 0.30 | 0 | 0 | 0.20 |
| Information Ratio | 0.30 | 0 | 0 | 0.15 |
| Tracking Error | 0.05 | 0.40 | 0.10 | 0.15 |
| Beta | 0.10 | 0.30 | 0.35 | 0.15 |
| Maximum Drawdown | 0.15 | 0.05 | 0.35 | 0.25 |
| Expense Ratio | 0.10 | 0.25 | 0.20 | 0.10 |
| R² | DISPLAY | DISPLAY | DISPLAY | DISPLAY |

每列之和必须为 1。Expense Ratio 是 Fund Data，不新增 Factor ID；按管理费、托管费和销售
服务费合计，受 PIT 约束，方向为 `LOWER_IS_BETTER`。

未列入权重表的已实现因子仍用于展示、筛选、有效性研究和子分解释，不进入 v1 总分。
权重指标缺失时采用 `EXCLUDE_AND_RENORMALIZE`；少于两个有效加权指标或
`data_completeness < 0.8` 时总分 `UNAVAILABLE`。

Beta 按 Profile 目标区间计算区间外偏离度：Active Equity `[0.85,1.15]`、Passive Equity
`[0.98,1.02]`、Bond 与 Hybrid `[0.90,1.10]`。Bond Beta 是相对中债综合全价指数的回归
Beta；股票 Beta 与 Duration Tilt 不属于 M1。

Tracking Error 的 Profile 规则为：Passive Equity 越低越好；Bond 越低越好且年化 1.5%
为风险预算硬上限；Active Equity 使用 TE × IR 复合算子；Hybrid 使用 TE × Sharpe 复合算子。
两个复合算子位于评分层，产出的 `interaction_value` 替代 TE 自身加权输入且只占用 TE 权重，
IR/Sharpe 原有贡献保持不变。

Factor 单因子标准化字段统一为 `normalized_value`，范围 `[0,100]`；`normalized_score` 不用于
Factor 输出。内部使用 `float64`，计算和持久化不主动截断，重算一致性绝对误差不超过
`1e-10`，展示精度由前端决定。

## 4. 数据与版本闭包

新增或补齐以下实体：

- `benchmark_definition`、`benchmark_component`、`benchmark_mapping`、
  `benchmark_index_value`；Benchmark Index 类型至少支持 `TOTAL_RETURN` 与 `FULL_PRICE`。
- `peer_group_snapshot`、`peer_group_member`。
- `factor_definition`、`factor_version`、`factor_run`、`factor_value`、
  `factor_effectiveness`。
- `fund_evaluation`、`fund_score`、`fund_score_attribution`、`fund_ranking`、
  `fund_tier`、`fund_universe_snapshot`、`fund_universe_member`、
  `selection_condition_result`。

所有历史事实不可原地覆盖。Normalized Value 绑定 Peer Group Version；MAR 因子绑定
Evaluation Policy Version；有效性结论绑定 Validation Policy Version。

## 5. 服务边界

- data-service：分类、费率、$R_f$、Benchmark 定义/映射/指数值及 PIT 查询。
- fund-service：Profile 映射、Evaluation Policy、Peer Group、Score、Rank、Tier、Universe。
- factor-service：Raw Factor、标准化、有效性检验及结果持久化。
- strategy_library：纯计算规则，不依赖 SQLAlchemy、HTTP 或运行模式。

Peer Group 和 Policy 构建不得读取 Score 或 Universe。评分不得绕过 factor-service 自行计算
因子或标准化。portfolio-service 与 return-risk 不依赖或重算 Factor；二者直接消费 PIT 收益
序列计算组合约束、组合收益和风险，两条链路仅在报告层对照。

## 6. 状态与失败语义

- `UNAVAILABLE`：按规则无法计算，保留原因并继续其他对象。
- `INVALID`：违反计算或数据不变量，告警并阻断该对象。
- `VALIDATION_PENDING`：尚无 OOS 结论，不产出正式 Score。
- `UNSUPPORTED_CLASSIFICATION`：不属于 M1 四类闭环，不动态降级。
- `BENCHMARK_UNAVAILABLE`：REL 因子不可用，不使用未经声明的替代基准。

上游输入为 `INVALID` 时 Factor 结果必须传播为 `INVALID`；输入缺失、观测不足或数学不可计算
才使用 `UNAVAILABLE`。API 对不可用数值返回 `null + status + reason_code`，不得使用 0、-1、
`"-"` 或 `"—"` 作为哨兵值；破折号只允许作为前端渲染结果。

## 7. 验收

1. 任一历史 `decision_at` 可重建分类、Benchmark、Peer Group、Factor、Score 和 Universe。
2. Peer Group 构建路径不依赖 Score/Universe；有效样本少于 30 时不标准化、不排名。
3. 15 个因子的边界、PIT、精度和重算一致性测试通过。
4. 没有 OOS 有效性结论时 Score 为 `VALIDATION_PENDING`。
5. 四类权重逐列等于 1；R² 不进入评分；Expense Ratio 不注册为 Factor。
6. Universe 保存 `REJECTED` 成员和全部条件结果，B1 -> B2 单事务提交。
7. Plan-1 交接中的高优先级项目全部有证伪测试。

## 8. 实施切分

详细逐任务步骤在本规格评审通过后写入 Plan-2 Implementation Plan。建议按以下顺序：

1. Plan-1 契约收紧与数据维度补齐。
2. Benchmark 与 Policy 版本闭包。
3. Peer Group 快照。
4. Raw Factor 与 Threshold Resolver。
5. OOS 有效性检验与标准化。
6. Score、Rank、Tier 与 Universe 原子快照。