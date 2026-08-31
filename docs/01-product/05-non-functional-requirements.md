# 非功能需求 · Non-functional Requirements

> **上游文档**：docs/01-product/01-product-overview.md（v2.5）｜docs/01-product/02-business-requirements.md（v2.3）｜docs/01-product/03-user-stories.md（v1.0）｜docs/01-product/04-functional-requirements.md（v1.0）
> **文档版本**：v1.1
> **产品阶段**：第一阶段 —— 纯 Quant 基金投资组合决策支持系统（不引入 ML / AI）

---

## 1. Overview

### 1.1 本文档回答什么

> **系统应该以什么质量水平提供这些功能？**

`04-functional-requirements` 定义系统必须做什么，本文档定义这些能力必须达到的**质量标准**。

### 1.2 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 用什么技术实现这些质量目标 | `02-architecture` |
| 存储引擎、分片、索引策略 | `11-database` |
| 监控与告警的具体设计 | `12-operations` |
| 治理流程与审批门槛的阈值 | `13-governance` |

> **本文档不出现**：数据库、缓存、消息队列、编排系统、IAM 产品、接口协议、编程语言、框架名称。

### 1.3 可验证性原则

> **每条 NFR 必须可测试。**

| 反例 | 正例 |
|---|---|
| 系统必须具有高性能 | 基金检索的 P95 响应时间在既定生产负载下必须低于 `<TBD>` |
| 系统必须稳定 | 失败的批量计算任务必须被检测到，并按既定重试策略重试 |
| 系统应具有良好的扩展性 | 系统必须支持基金数量增长至 `<TBD>` 只而不改变架构层次 |

**未确定的数值一律标记 `<TBD>`，不得自行编造。**

---

## 2. 编号与优先级

### 2.1 编号规则

```
NFR-<类别>-<序号>
```

| 类别 | 前缀 | 主题 |
|---|---|---|
| Performance | `NFR-PERF` | 响应时间与吞吐 |
| Availability | `NFR-AVAIL` | 可用性 |
| Reliability | `NFR-REL` | 可靠性与容错 |
| Scalability | `NFR-SCALE` | 可扩展性 |
| Security | `NFR-SEC` | 安全与访问控制 |
| Data Quality | `NFR-DQ` | 数据质量 |
| Reproducibility | `NFR-REPRO` | 可复现性 |
| Auditability | `NFR-AUDIT` | 可审计性 |
| Explainability | `NFR-EXPL` | 可解释性 |
| Maintainability | `NFR-MAINT` | 可维护性 |
| Observability | `NFR-OBS` | 可观测性 |
| Disaster Recovery | `NFR-DR` | 灾难恢复 |
| Compliance | `NFR-COMP` | 合规与留痕 |

### 2.2 优先级

| 级别 | 定义 |
|---|---|
| **P0** | 第一阶段上线**必须**满足 |
| **P1** | 第一阶段重要能力 |
| **P2** | 后续增强 |

### 2.3 本文档特有的质量重心

本系统的质量重心与一般业务系统不同——**Reproducibility、Auditability、Explainability、Data Quality 四项为 P0 且不可妥协**，其优先级高于性能与吞吐。

理由：一个响应慢的分析结果仍然可用；一个**不可复现、不可解释**的投资决策则完全不可用，且这类缺陷往往在事后归因时才暴露。

---

## 3. Requirements

### 3.1 Performance · `NFR-PERF`

> **必须区分四类负载，不得使用统一 SLA。**

| 负载类型 | 特征 |
|---|---|
| Online Query | 用户交互式查询，人在等待 |
| Batch Calculation | 周期性批量计算，有明确的完成时间窗 |
| Backtest | 长时间运行的历史重放，可异步 |
| Data Processing | 数据采集、清洗、标准化 |

---

#### NFR-PERF-001 Online Query 响应时间 · P0

**Requirement**

在线查询类功能的响应时间必须满足既定分位数目标。

| 功能 | 对应 FR | P50 | P90 | P95 | P99 |
|---|---|---|---|---|---|
| 基金检索 | FR-FUND-005 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 基金概览 | FR-DATA-001 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 基金指标查询 | FR-FUND-001~004 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 评分与 Breakdown | FR-SCORE-001 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 排名与分层 | FR-RANK-001 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 组合与风险视图 | FR-PRISK-001 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |
| 决策解释 | FR-EXPL-001 | `<TBD>` | `<TBD>` | `<TBD>` | `<TBD>` |

**度量方式**：在既定生产负载下按分位数统计端到端响应时间。

**验证方式**：负载测试 + 生产环境持续度量。

> `<TBD-NFR-1: 各在线查询的分位数目标待产品与运维确认>`

---

#### NFR-PERF-002 Batch Calculation 完成时间 · P0

**Requirement**

批量计算必须在既定时间窗内完成，且完成时间可度量、可告警。

| 批量任务 | 对应 FR | 目标完成时间 | 失败率上限 | 重试率上限 |
|---|---|---|---|---|
| 每日 Factor 计算 | FR-FACTOR-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| Peer Group 构建 | FR-PEER-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| Fund Score 计算 | FR-SCORE-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| Universe 生成 | FR-UNIV-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| Return Estimate 计算 | FR-RET-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| 风险与协方差计算 | FR-RISK-001 | `<TBD>` | `<TBD>` | `<TBD>` |
| 组合优化求解 | FR-OPT-001 | `<TBD>` | `<TBD>` | `<TBD>` |

**关键约束**：全链路从数据就绪到 `Proposed Investment Decision` 产出的端到端时间必须可度量，目标值 `<TBD>`。

> `<TBD-NFR-2: 各批量任务的完成时间窗与失败率上限待运维与投研确认>`

---

#### NFR-PERF-003 Backtest 执行 · P1

**Requirement**

回测执行必须支持异步提交与进度查询，且执行时间可度量。

| 度量项 | 目标 |
|---|---|
| 单次回测执行时间（标准配置：`<TBD>` 只基金 × `<TBD>` 年 × 季度调仓） | `<TBD>` |
| 并发回测数 | `<TBD>` |
| 历史数据加载时间 | `<TBD>` |
| 结果持久化时间 | `<TBD>` |

**关键约束**：回测执行时间的增长必须与「基金数 × 期数」近似线性，不得出现随规模超线性恶化。

> `<TBD-NFR-3: 回测标准配置与执行时间目标待投研确认>`

---

#### NFR-PERF-004 Data Processing · P1

| ID | Requirement | 度量 | 优先级 |
|---|---|---|---|
| **NFR-PERF-004** | 每日数据采集、清洗与标准化必须在数据源可得后的既定时间窗内完成 | 完成时间、延迟到达比例 | P1 |

> `<TBD-NFR-4: 数据处理时间窗待运维确认>`

---

### 3.2 Availability · `NFR-AVAIL`

> **在线服务与批量服务不适用同一可用性目标。**

---

#### NFR-AVAIL-001 Online Services 可用性 · P0

**Requirement**

面向用户的在线查询服务必须达到既定可用性目标。

| 服务类别 | 可用性目标 | 计划内维护窗口 |
|---|---|---|
| 基金查询与分析 | `<TBD>` | `<TBD>` |
| 组合与风险视图 | `<TBD>` | `<TBD>` |
| 决策复核 | `<TBD>` | `<TBD>` |

**度量方式**：按可用时间占比统计，计划内维护不计入。

> > **推荐默认 · 2026-08-27**：在线服务可用性 **99.5%**；**决策时段 99.9%**。产品与运维可改。
>
> **两档而非一档的理由**：本系统是**内部决策支持**而非 7×24 交易系统 —— 非决策时段的短暂不可用不造成实质损失，而决策时段（每日调仓窗口、每季度调仓日）的不可用会推迟决策。
>
> **99.5% 对应每月约 3.6 小时的允许不可用**，99.9% 对应每月约 43 分钟。分档使运维资源集中在真正关键的时段。

---

#### NFR-AVAIL-002 ~ NFR-AVAIL-003 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-AVAIL-002** | 批量计算服务的可用性以**按时完成率**度量，而非在线可用率 | 批量服务短时不可用若不影响按时完成，不计为可用性事件 | P0 |
| **NFR-AVAIL-003** | 决策日的关键路径服务（数据 → 因子 → 评分 → Universe → 优化）必须具备比非关键路径更高的可用性保障 | 决策日窗口内的降级会直接导致当期无法调仓 | P0 |

---

### 3.3 Reliability · `NFR-REL`

---

#### NFR-REL-001 计算任务的可靠性 · P0

**Requirement**

批量计算任务必须具备失败检测、重试与幂等保证。

| # | 要求 |
|---|---|
| REL-1 | 失败任务必须被**检测到**并按既定重试策略重试 |
| REL-2 | 任务必须**幂等**——重复执行同一任务不产生重复或错误的结果 |
| REL-3 | 部分失败必须可识别到**具体对象级别**（哪只基金、哪个指标），而非整批标记失败 |
| REL-4 | 重复执行必须被识别并阻止产生重复数据 |
| REL-5 | 服务重启后，未完成任务的状态必须可恢复且不丢失 |

**Acceptance Criteria**

```
Given  某日 Factor 计算任务在处理到第 500 只基金时失败
When   任务重试
Then   系统能识别已完成部分，不产生重复结果
And    最终结果与一次性成功执行完全一致
```

**Priority** · P0

---

#### NFR-REL-002 ~ NFR-REL-004 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-REL-002** | 数据损坏必须可检测，且不得静默传播至下游 | 与 `FR-DQ-001` 的三级阻断粒度配合 | P0 |
| **NFR-REL-003** | 计算失败不得导致部分写入的中间状态被下游消费 | 结果对下游可见前必须完整 | P0 |
| **NFR-REL-004** | 优化求解失败必须被记录为业务事件（`INFEASIBLE`），而非系统异常 | 求解不可行是业务结果，不是故障——见 `FR-OPT-002` | P0 |

---

### 3.4 Scalability · `NFR-SCALE`

> **必须给出可验证的规模维度，不得仅声明"具有良好扩展性"。**

---

#### NFR-SCALE-001 规模维度 · P0

**Requirement**

系统必须在下列各维度达到既定规模而不改变架构层次。

| 维度 | 第一阶段目标 | 增长预期 |
|---|---|---|
| 覆盖基金数量 | `<TBD>` | `<TBD>` |
| 历史数据年限 | `<TBD>` | `<TBD>` |
| Factor 数量 | `<TBD>` | `<TBD>` |
| 单日 Factor 计算量（基金 × 因子） | `<TBD>` | `<TBD>` |
| 并发在线用户数 | `<TBD>` | `<TBD>` |
| 并发回测数 | `<TBD>` | `<TBD>` |
| 组合策略数量 | `<TBD>` | `<TBD>` |
| 历史决策快照留存量 | `<TBD>` | `<TBD>` |

> `<TBD-NFR-6: 各规模维度的第一阶段目标与增长预期待产品确认>`

---

#### NFR-SCALE-002 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-SCALE-002** | 协方差矩阵计算量随 Universe 规模呈平方增长，系统必须明确单次优化可支持的最大 Universe 规模 | 超出规模时必须显式拒绝并提示，不得静默截断 Universe | P0 |

---

### 3.5 Security · `NFR-SEC`

---

#### NFR-SEC-001 角色与权限 · P0

**Requirement**

系统必须实施基于角色的访问控制，至少区分五类角色。

| 角色 | 可读 | 可写 | 特有权限 |
|---|---|---|---|
| **Researcher** | 基金数据、Factor、Score、排名、Universe | 探索性筛选配置 | — |
| **Portfolio Manager** | 全部分析数据、组合、决策 | 组合策略配置 | **复核决策：Approve / Reject / Override** |
| **Quant Researcher** | 全部分析数据、回测 | 评分方案、准入规则、策略配置 | 提交策略进入 VALIDATING |
| **Operations** | 数据状态、任务状态、系统状态 | 任务重试、数据修复触发 | — |
| **Administrator** | 全部 | 用户与角色配置 | 授权管理 |

**关键约束**

| # | 要求 |
|---|---|
| SEC-1 | **决策的 Approve / Reject / Override 权限仅限 Portfolio Manager 角色**——这是投资决策责任的技术边界 |
| SEC-2 | 策略配置变更权限与决策放行权限**必须分离**——同一人不应既定规则又批准其产出 |
| SEC-3 | 全部写操作必须记录操作人与时刻 |

**Priority** · P0

---

#### NFR-SEC-002 ~ NFR-SEC-004 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-SEC-002** | 系统必须对所有访问进行身份认证 | 具体认证机制属 `02-architecture` | P0 |
| **NFR-SEC-003** | 敏感配置（数据源凭据等）不得以明文形式存在于配置或日志中 | — | P0 |
| **NFR-SEC-004** | 全部用户操作必须记入不可篡改的审计日志 | 与 `NFR-AUDIT-002` 配合 | P0 |

---

### 3.6 Data Quality · `NFR-DQ`

> 本系统的核心质量维度之一。

---

#### NFR-DQ-001 五个质量维度 · P0

**Requirement**

数据质量必须在五个维度上可度量、可告警。

| 维度 | 要求 | 度量方式 |
|---|---|---|
| **Completeness** | 不得存在未被识别的大量缺失 | 关键字段非空率、覆盖基金数占比 |
| **Accuracy** | 数据必须符合来源与校验规则 | 校验规则通过率、异常值检出数 |
| **Timeliness** | 数据必须在规定时间内可用 | 到达时间 vs 约定时点、延迟到达比例 |
| **Consistency** | 多源数据必须一致，或差异必须可解释 | 多源比对差异率、差异仲裁记录完整性 |
| **Historical Integrity** | 历史数据不得被无审计地覆盖 | 版本链完整性、无版本覆盖事件数 |

**关键约束**

| # | 要求 |
|---|---|
| DQ-1 | `Historical Integrity` 是**最高优先级**——历史数据被覆盖会同时破坏可复现性与可审计性，且往往不可恢复 |
| DQ-2 | 质量异常必须**显式暴露、可告警、可追溯**，禁止静默降级 |
| DQ-3 | 质量状态必须随计算结果**逐级向上传递**至最终输出 |

**Acceptance Criteria**

```
Given  某净值数据被修订
When   系统写入修订
Then   生成新 version，旧 version 完整保留
And    不存在任何原地覆盖操作
And    版本链可完整回溯
```

**Priority** · P0

---

#### NFR-DQ-002 ~ NFR-DQ-003 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-DQ-002** | 数据质量目标值必须可配置并可度量 | 各维度阈值 `<TBD-NFR-7: 待数据与运维确认>` | P0 |
| **NFR-DQ-003** | 数据质量状态必须支持按 Fund-level / Metric-level / Global-level 三级粒度定位 | 与 `FR-DQ-001` 对应 | P0 |

---

### 3.7 Reproducibility · `NFR-REPRO`

> **本系统不可妥协的质量属性之一。**

---

#### NFR-REPRO-001 全链路可复现 · P0

**Requirement**

```
相同输入数据版本  +  相同 Strategy Version  +  相同配置
                    ↓
              完全相同的结果
```

**适用范围**（全部必须满足）

| 对象 | 对应 FR |
|---|---|
| Factor | FR-FACTOR-001 |
| Peer Group | FR-PEER-001 |
| Fund Score | FR-SCORE-001 |
| Fund Universe | FR-UNIV-001 |
| Return Estimate | FR-RET-001 |
| Risk / Correlation | FR-RISK-001 |
| Portfolio Optimization | FR-OPT-001 |
| Backtest | FR-BT-001 |

**关键约束**

| # | 要求 |
|---|---|
| REPRO-1 | 随机性必须被消除或固定（随机种子、求解器版本） |
| REPRO-2 | 任何"重跑结果不一样"的环节视为**缺陷**，而非可接受的浮动 |
| REPRO-3 | 复现验证必须可自动化执行，作为发布前的强制检查 |
| REPRO-4 | 数值精度差异必须在既定容差内，容差值须显式定义 |

**Acceptance Criteria**

```
Given  一次历史决策的完整快照
When   以相同版本重跑
Then   全部中间结果与最终权重完全一致（在既定数值容差内）
And    任一环节不一致即判定为不满足本需求
```

**Priority** · P0

> **已定案 · 2026-08-27**：数值容差体系见 `TBD-resolution-2.md` Policy A，本处摘要。

| 对象 | 相对误差容差 |
|---|---|
| Factor 值 / Score | **1×10⁻¹⁰** |
| 协方差矩阵 | **1×10⁻⁸** |
| 优化权重 `w` | **1×10⁻⁶**（且**非零集合必须完全一致**） |
| 绩效指标 | **1×10⁻⁸** |

> **为什么这不需要业务判断**：容差量级由 float64 的机器精度（约 2.2×10⁻¹⁶）与运算链长度决定。业务能决定的是「差异多大算缺陷」，而该问题的答案是「超过数值方法本身能保证的精度就是缺陷」—— 这是工程事实。

> **权重的容差比因子松四个数量级**，因为优化器的解是迭代逼近的，其精度上限就是求解器的终止容差（通常 1e-8~1e-6）。要求权重复现到 1e-10 等于要求每次走完全相同的迭代路径 —— 那是对实现细节的要求，不是对结果的要求。

> **REPRO-2 与容差不矛盾**：「重跑不一样即缺陷」指的是**超出容差**的不一样。容差内的差异不是「可接受的浮动」，而是**数值方法的定义域** —— 位级一致在浮点运算下本就不是可达目标。

---

#### NFR-REPRO-002 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-REPRO-002** | 复现能力必须覆盖跨越配置变更的历史时点 | 当前配置变化**不得**使历史结果失去可复现性——须按当时的版本快照重建 | P0 |

---

### 3.8 Auditability · `NFR-AUDIT`

---

#### NFR-AUDIT-001 完整审计链 · P0

**Requirement**

系统必须支持从最终决策回溯至原始数据的完整链路。

```
Approved Investment Decision
      ↓  Human Review 记录（Status + Override 五字段）
Proposed Investment Decision
      ↓
Post-Optimization Risk（⑦-R）
      ↓
Optimization Run（输入 · 状态 · 输出 · 诊断）
      ↓
Constraint Set + Risk Budget + Objective
      ↓
Return Estimate + Covariance / Correlation
      ↓
Fund Universe（+ Eligibility Rules 版本）
      ↓
Fund Score（+ 五个子分 + Scoring 版本）
      ↓
Peer Group（+ Classification 版本）
      ↓
Factor（+ Metric 版本）
      ↓
Data Snapshot（available_at / effective_at / version）
      ↓
Raw Data
```

**链上每一环必须可回答四个问题**

| # | 问题 |
|---|---|
| 1 | **谁**产生的 |
| 2 | **什么时候**产生的 |
| 3 | 使用了**什么版本** |
| 4 | 使用了**什么规则与数据** |

**关键约束**

| # | 要求 |
|---|---|
| AUDIT-1 | **Human Review 环节必须在链上**——否则无法回答"系统算出 10%，为什么最后是 7%" |
| AUDIT-2 | 审计链必须在决策发生时**同步落库**，事后无法重建 |
| AUDIT-3 | 快照不完整时，对应的指令不得下发 |

**Priority** · P0

---

#### NFR-AUDIT-002 ~ NFR-AUDIT-003 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-AUDIT-002** | 全部配置变更、策略版本变更与用户操作必须记入不可篡改的历史 | 含操作人、时刻、变更前后内容 | P0 |
| **NFR-AUDIT-003** | 审计记录的保留期限必须满足既定要求 | `<TBD-NFR-9: 保留期限待合规确认>` | P0 |

---

### 3.9 Explainability · `NFR-EXPL`

---

#### NFR-EXPL-001 两条解释链 · P0

**Requirement**

系统必须支持两条完整的解释链，且每一环可下钻。

```
链一 · 评分解释
Fund Score → 五个子分 → 各 Factor 贡献 → Factor 原始值 → Raw Data

链二 · 权重解释
Portfolio Weight → Optimization Objective + binding 约束 + Risk Budget
                 → Return Estimate + Risk / Correlation
                 → Fund Universe 准入原因 → Fund Score
```

**关键约束**

| # | 要求 |
|---|---|
| EXPL-1 | 解释必须以**业务语言**呈现，可被非技术使用者理解 |
| EXPL-2 | **禁止**输出无法拆解到指标与规则的结论 |
| EXPL-3 | 解释必须基于**当时的**版本与数据，而非当前配置 |
| EXPL-4 | 输出必须区分五个层级（Analysis / Score / Screening / Candidate / Portfolio），不得跨级解释 |

**Priority** · P0

---

#### NFR-EXPL-002 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-EXPL-002** | 系统输出中不得出现以下表述："AI 认为""模型认为""综合评估为推荐"，以及在统计判定阈值确定前使用"显著优于" | 第一阶段无 ML / AI 模型，此类表述无对应实体 | P0 |

---

### 3.10 Maintainability · `NFR-MAINT`

---

#### NFR-MAINT-001 配置与代码分离 · P0

**Requirement**

以下内容必须以**配置**而非代码形式存在，且变更不需要重新发布。

```
评分指标集合与权重  ·  标准化方式  ·  Preference Direction
分层阈值  ·  筛选条件与阈值  ·  组合约束  ·  风险预算
风险告警阈值  ·  调仓阈值  ·  Benchmark 映射规则
Evaluation Profile 定义  ·  Peer Group 参与规则
```

**关键约束**

| # | 要求 |
|---|---|
| MAINT-1 | 上述内容**严禁硬编码** |
| MAINT-2 | 全部配置必须版本化并留痕 |
| MAINT-3 | 投资观点的调整应只需改配置，不需改代码——这是 `Factor` / `Score` / `Construction` 三层解耦的工程意义 |

**Priority** · P0

---

#### NFR-MAINT-002 单一策略实现 · P0

**Requirement**

`Backtest` 与 `Live` 必须共用同一套 **Strategy Domain Logic**。

| # | 要求 |
|---|---|
| MAINT-4 | 不得存在两套策略实现 |
| MAINT-5 | 允许的差异仅限于：数据获取实现、日志与监控、是否产生实盘指令 |
| MAINT-6 | 任何 `if (is_backtest)` 形式的**策略逻辑分支**都是本要求的破坏信号，必须在代码评审中拒绝 |
| MAINT-7 | 本文档只规定"必须共用同一套领域逻辑"这一产品级约束，**不规定其技术形态**——具体分层由 `02-architecture` 决定 |

**Priority** · P0

---

#### NFR-MAINT-003 ~ NFR-MAINT-004 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-MAINT-003** | 业务规则必须可独立测试，不依赖外部数据源即可验证 | 支撑回归验证与发布前检查 | P0 |
| **NFR-MAINT-004** | 服务边界必须与业务链路 Stage 对应，职责单一 | 概念的**定义权**唯一；实现权与存储权可分散（上游原则八） | P1 |

---

### 3.11 Observability · `NFR-OBS`

---

#### NFR-OBS-001 四层可观测性 · P0

**Requirement**

系统必须在四个层面可观测。

| 层面 | 观测对象 |
|---|---|
| **Application** | 请求量、错误率、响应时间分布 |
| **Calculation** | 任务状态、执行时长、失败与重试、部分失败明细 |
| **Data** | 数据新鲜度、完整性、质量状态分布、延迟到达 |
| **Strategy** | 回测执行状态、策略版本分布、优化求解状态（收敛 / 可行 / INFEASIBLE）、Override 频率 |

**关键约束**

| # | 要求 |
|---|---|
| OBS-1 | **优化 `INFEASIBLE` 事件必须可观测并计数**——持续不可行意味着约束设置过紧 |
| OBS-2 | **Override 频率必须可观测**——频繁 override 意味着策略与判断存在系统性分歧 |
| OBS-3 | **Backtest-Live Deviation 必须可观测**——持续系统性偏离意味着回测与实盘存在未识别的差异 |
| OBS-4 | 具体监控指标与告警规则设计属 `12-operations`，本文档只定义**必须可观测的对象** |

**Priority** · P0

---

#### NFR-OBS-002 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-OBS-002** | 决策日关键路径的各阶段进度必须可实时观测 | 便于在时间窗内判断是否需要人工介入 | P1 |

---

### 3.12 Disaster Recovery · `NFR-DR`

---

#### NFR-DR-001 备份与恢复 · P0

**Requirement**

系统必须具备备份与恢复能力，并达到既定的恢复目标。

| 数据类别 | 备份频率 | RPO | RTO |
|---|---|---|---|
| 基金主数据与净值序列 | `<TBD>` | `<TBD>` | `<TBD>` |
| Factor 与 Score 历史 | `<TBD>` | `<TBD>` | `<TBD>` |
| Peer Group / Universe 快照 | `<TBD>` | `<TBD>` | `<TBD>` |
| **决策快照与审计记录** | `<TBD>` | `<TBD>` | `<TBD>` |
| 策略与配置版本 | `<TBD>` | `<TBD>` | `<TBD>` |

**关键约束**

| # | 要求 |
|---|---|
| DR-1 | **决策快照与审计记录的 RPO 应当为最严格的一档**——丢失将导致历史决策永久不可解释，且无法通过重算恢复 |
| DR-2 | 备份必须定期验证可恢复性，而非仅验证备份任务成功 |

> > **推荐默认 · 2026-08-27**：**RPO ≤ 1 个决策周期**，**RTO ≤ 4 小时**。运维与合规可改。
>
> **RPO 以决策周期为界的理由**：**决策快照不可丢** —— 它是审计对象且不可重建（`01-system-architecture` §8.3 的可复现性依赖它）。丢失一个决策周期的数据意味着该周期的决策永久无法复现。
>
> **RTO 4 小时**：本系统可容忍小时级恢复 —— 决策日内 4 小时中断会推迟当期决策，但不造成交易损失（区别于实时交易系统）。
>
> **备份频率与保留期限是两件事**：本条定「丢多少」（RPO）与「多久恢复」（RTO）；「留多久」属 `NFR-9` 与 `TBD-resolution-2.md` Policy C。

**Priority** · P0

---

### 3.13 Compliance · `NFR-COMP`

---

#### NFR-COMP-001 历史可解释性的持久保证 · P0

**Requirement**

> **历史投资决策不得因当前配置变化而失去可解释性。**

| # | 要求 |
|---|---|
| COMP-1 | 评分方案、准入规则、组合规则的变更**不得**影响历史决策的解释能力 |
| COMP-2 | 历史决策的解释必须基于**当时的**版本快照重建 |
| COMP-3 | 配置版本一经用于生产决策，**不得删除** |

**Acceptance Criteria**

```
Given  评分方案已从 v1.0 升级至 v2.0
When   请求解释一次基于 v1.0 产生的历史决策
Then   系统按 v1.0 的规则与权重给出解释
And    解释结果与该决策发生时的解释完全一致
```

**Priority** · P0

---

#### NFR-COMP-002 · 紧凑条目

| ID | Requirement | 说明 | 优先级 |
|---|---|---|---|
| **NFR-COMP-002** | 系统必须支持决策审计、配置历史、策略版本历史、用户操作历史、数据溯源五类查询 | 支撑事后合规检查 | P0 |

---

## 4. Requirement Traceability Matrix

> 建立 `User Story → Functional Requirement → Non-functional Requirement` 的追溯关系。
> 本表按业务链路组织，列出主要追溯路径；未列出的 FR 均可通过其所属域追溯至对应的 US 与 NFR。

| Epic | User Story | Functional Requirement | Non-functional Requirement |
|---|---|---|---|
| 1 Fund Discovery | US-FUND-001 ~ 004 | FR-DATA-001 ~ 005 | NFR-PERF-001、NFR-DQ-001 |
| 2 Fund Analysis | US-FUND-005 ~ 010 | FR-FUND-001 ~ 005 | NFR-PERF-001、NFR-REPRO-001 |
| 3 Factor Analysis | US-FACTOR-001 ~ 005 | FR-FACTOR-001 ~ 005 | NFR-REPRO-001、NFR-PERF-002 |
| 4 Fund Evaluation | US-SCORE-001、003 | FR-PEER-001 ~ 004、FR-SCORE-001 ~ 002 | NFR-REPRO-001、NFR-EXPL-001 |
| 4 Fund Evaluation | US-SCORE-004、006 | FR-RANK-001、FR-SCORE-003 | NFR-EXPL-001、NFR-MAINT-001 |
| 5 Candidate Universe | US-UNIV-001 ~ 004 | FR-UNIV-001 ~ 004、FR-ELIG-004 | NFR-AUDIT-001、NFR-REPRO-002 |
| 6 Portfolio Construction | US-PORT-001 ~ 004 | FR-CONS-001 ~ 004 | NFR-MAINT-001、NFR-EXPL-001 |
| 7 Portfolio Optimization | US-PORT-006、007 | FR-OPT-001、FR-EXPL-001 | NFR-REPRO-001、NFR-EXPL-001 |
| 7 Portfolio Optimization | US-PORT-008、009 | FR-OPT-002 ~ 003 | NFR-REL-004、NFR-OBS-001 |
| 8 Risk Analysis | US-RISK-001 ~ 003 | FR-RET-001、FR-RISK-001、FR-PRISK-001 | NFR-REPRO-001、NFR-PERF-002 |
| 8 Risk Analysis | US-RISK-005 | FR-PRISK-003 | NFR-OBS-001 |
| 9 Backtesting | US-BT-001、005 | FR-BT-001 ~ 002 | NFR-PERF-003、NFR-REPRO-001 |
| 9 Backtesting | US-BT-002 ~ 004 | FR-BIAS-001 ~ 004 | NFR-DQ-001、NFR-AUDIT-001 |
| 9 Backtesting | US-BT-006、007 | FR-BTR-001 ~ 004 | NFR-EXPL-002 |
| 10 Decision Review | US-DEC-001 ~ 003 | FR-DEC-001 | NFR-SEC-001、NFR-AUDIT-001 |
| 10 Decision Review | US-DEC-004 | FR-DEC-002 | NFR-SEC-001、NFR-AUDIT-001 |
| 10 Decision Review | US-DEC-005 | FR-DEC-003 ~ 004 | NFR-REPRO-001、NFR-COMP-001 |
| 11 Live Portfolio | US-LIVE-001 ~ 004 | FR-LIVE-001 ~ 004 | NFR-AVAIL-001、NFR-OBS-001 |
| 12 Rebalancing | US-REBAL-001 ~ 004 | FR-REBAL-001 ~ 004 | NFR-EXPL-001、NFR-MAINT-001 |
| 13 Data Quality | US-DQ-001 ~ 005 | FR-DQ-001 ~ 005 | NFR-DQ-001 ~ 003、NFR-REL-001 |
| 14 Strategy Management | US-STRAT-001 ~ 002 | FR-STRAT-001 ~ 002 | NFR-REPRO-001、NFR-AUDIT-002 |
| 14 Strategy Management | US-STRAT-004 ~ 005 | FR-STRAT-003 ~ 004 | NFR-SEC-001、NFR-MAINT-001 |

### 4.1 反向追溯：每条 NFR 支撑哪些能力

| NFR | 支撑的核心能力 |
|---|---|
| NFR-REPRO-001 | 全链路——任一环节不可复现即导致下游全部分析失效 |
| NFR-AUDIT-001 | 决策解释、合规检查、事后归因 |
| NFR-EXPL-001 | 评分可信度、组合决策可辩护性 |
| NFR-DQ-001 | 全链路输入质量，尤其 Historical Integrity 支撑可复现与可审计 |
| NFR-SEC-001 | 投资决策责任边界（Approve / Override 权限） |
| NFR-MAINT-002 | 回测结论对实盘的参考价值 |
| NFR-COMP-001 | 历史决策的长期可解释性 |

---

## 5. TBD

### 5.1 本文档引入的待确认项

| # | 事项 | 位置 | 责任方 |
|---|---|---|---|
| **NFR-1** | 各在线查询的 P50 / P90 / P95 / P99 目标 | §3.1 NFR-PERF-001 | 产品 + 运维 |
| **NFR-2** | 各批量任务的完成时间窗、失败率与重试率上限 | §3.1 NFR-PERF-002 | 运维 + 投研 |
| **NFR-3** | 回测标准配置与执行时间目标、并发数 | §3.1 NFR-PERF-003 | 投研 |
| **NFR-4** | 数据处理时间窗 | §3.1 NFR-PERF-004 | 运维 |
| **NFR-5** | 在线服务可用性目标与维护窗口 | §3.2 NFR-AVAIL-001 | 产品 + 运维 |
| **NFR-6** | 各规模维度的第一阶段目标与增长预期 | §3.4 NFR-SCALE-001 | 产品 |
| **NFR-7** | 数据质量各维度的阈值 | §3.6 NFR-DQ-002 | 数据 + 运维 |
| ~~NFR-8~~ | ~~可复现性的数值容差定义~~ —— **已定案**：四档相对误差容差（Factor 1e-10 / 协方差 1e-8 / 权重 1e-6 / 绩效 1e-8），见 `TBD-resolution-2.md` Policy A | §3.7 NFR-REPRO-001 | ✅ 已定案 2026-08-27 |
| **NFR-9** | 审计记录保留期限 | §3.8 NFR-AUDIT-003 | 合规 |
| **NFR-10** | 各类数据的备份频率、RPO 与 RTO | §3.12 NFR-DR-001 | 运维 + 合规 |

> 上述 10 项均为**数值型待确认项**，不阻塞 `02-architecture` 的编写——架构可先按"该维度必须可度量、可配置"设计，数值确定后作为配置注入。

### 5.2 继承自上游的待确认项

见 `02-business-requirements.md` §35.2 的 P1-1 至 P1-24，均为业务参数，不属于 NFR 范畴。

---

## 6. Related Documents

| 文档 | 关系 |
|---|---|
| `01-product-overview.md` v2.4 | 上游——设计原则与概念定义 |
| `02-business-requirements.md` v2.3 | 上游——业务规则与非功能业务约束（§32） |
| `03-user-stories.md` v1.0 | 上游——使用者视角需求 |
| `04-functional-requirements.md` v1.0 | 上游——本文为其定义质量标准 |
| `02-architecture` | 下游——如何达成这些质量目标 |
| `11-database` | 下游——存储层面的实现 |
| `12-operations` | 下游——监控、告警与灾备的具体设计 |
| `13-governance` | 下游——治理流程与审批阈值 |

---

## 7. 变更记录

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.1** | 2026-08-27 | **`NFR-8` 关闭**。§3.7 补数值容差四档取值；说明容差量级由 float64 机器精度与运算链长度决定，**不需业务判断**；权重容差比因子松四个数量级是因为优化器精度上限即求解器终止容差；并澄清 **REPRO-2 与容差不矛盾**（容差内的差异是数值方法的定义域，不是「可接受的浮动」）。详见 `TBD-resolution-2.md` Policy A | `TBD-resolution-2.md` v1.0 |
| v1.0 | 2026-08-25 | 初始版本。定义 13 个类别共 36 条 Non-functional Requirement。区分四类负载的性能要求，在线与批量服务分别定义可用性。明确 Reproducibility、Auditability、Explainability、Data Quality 四项为不可妥协的 P0。建立 User Story → FR → NFR 的追溯矩阵及反向追溯表。引入 10 项数值型待确认项，均标记 `<TBD>`，未自行编造数值 | `01-product-overview.md` v2.4、`02-business-requirements.md` v2.3、`03-user-stories.md` v1.0、`04-functional-requirements.md` v1.0 |