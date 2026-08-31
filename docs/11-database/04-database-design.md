# 物理数据库设计 · Physical Database Design

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文定位：支撑层 · 物理模型
> 本域上游：docs/11-database/01-postgresql.md（v1.0）、03-erd.md（v1.0）
> 架构依赖：docs/02-architecture/06-technology-stack.md（v1.2）§4.6 Workload Matrix
>
> **文档版本**：v1.9 ｜ **产品阶段**：第一阶段

---

## 1. Purpose & Scope

### 1.1 本文档回答什么

> **ERD 中的实体最终如何落成 PostgreSQL 物理表？**

### 1.2 本文档不是数据字典 ⚠️

> **沿用提示词 §8：每张表必须回答"为什么存在、谁写、谁读、为什么这样设计 PK/Index/Partition"。**

```
❌ 逐表逐字段罗列类型与长度
✅ 表的存在理由 + 关键设计选择及其权衡
```

**具体的列级 DDL 属实现产物**，由迁移脚本承载（§19），本文档定义**设计标准与关键决策**。

### 1.3 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| PostgreSQL 使用规范（类型、命名、事务、PIT 支持） | `01-postgresql` |
| 实体与关系 | `03-erd` |
| 业务规则 | 各业务域 |
| 备份、监控、容量 | `12-operations` |

---

## 2. Physical Database Architecture

```
单一 PostgreSQL 实例（主）
    ├── 8 个 schema（01-postgresql §4）
    ├── 主从复制 → 只读副本（分析查询、回测）
    └── WAL 归档 → PITR
```

> 选型与复制拓扑属 `02-architecture` 与 `12-operations`，本域承接。

---

## 3. Schema Design

> **沿用 `01-postgresql` §4 的八个 schema。**

| Schema | Write Owner | 表数（约） | 分区表 |
|---|---|---|---|
| `raw` | `data-service` | 2 | ✅ |
| `fund` | `data-service` | 10 | ❌ |
| `market` | `data-service` | 7 | ✅ |
| `factor` | `factor-service` | 4 | ✅ |
| `evaluation` | `fund-service` | 9 | ✅ |
| `portfolio` | `portfolio-service` | 17 | ❌ |
| `backtest` | `backtest-service` | 8 | ✅ |
| `governance` | 多方（按表授权） | 6 | ✅ |

### 3.1 权限模型

```sql
-- 概念示意，非最终 DDL
GRANT USAGE ON SCHEMA <all> TO <all_service_roles>;
GRANT SELECT ON ALL TABLES IN SCHEMA <all> TO <all_service_roles>;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA <owned> TO <owner_role>;
```

> **写入权唯一、读取权开放**（`03-data-architecture` §4.2）。`governance` 按表授权（`01-postgresql` §4.3）。

---

## 4. Table Design Standards

### 4.1 每张核心表必须定义的项

> **沿用提示词 §7：**

| 项 | 说明 |
|---|---|
| Table Name / Purpose / Domain / Owner | 身份与职责 |
| Primary Key / Foreign Keys / Business Key | 键设计 |
| **Temporal Fields** | `effective_at` / `available_at` / `valid_from` / `valid_to` |
| Audit Fields | `created_at` / `created_by` / `updated_at` / `updated_by` |
| **Version** | 是否版本化 |
| Indexes / Constraints / Partition / Retention | 物理设计 |
| Source / Write Owner / Read Consumers | 数据流 |

### 4.2 统一的审计列

| 列 | 适用 | 说明 |
|---|---|---|
| `created_at` | **全部表** | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `created_by` | 含人工操作的表 | 系统写入时为服务账号 |
| `updated_at` | **仅允许 UPDATE 的表** | 见 §4.3 |
| `updated_by` | 同上 | —— |

### 4.3 禁止 UPDATE 的表不设 `updated_at` ⚠️

> **这是一个有意的设计信号。**

```
若某表禁止 UPDATE（01-postgresql §10.7）
    → 设 updated_at 会误导使用者以为可以更新
    → 不设它，则任何 UPDATE 尝试都缺少该列的维护，更易被发现
```

| 表类别 | `updated_at` |
|---|---|
| NAV、Factor Value、Score、Universe、Decision、Backtest 结果 | **❌ 不设** |
| 主数据（Fund、Manager 等非版本化属性） | ✅ 设 |
| 状态流转表（`backtest.run.status`） | ✅ 设 |

### 4.4 版本化表的标准列（v1.1 扩充）

```
effective_at            DATE          NOT NULL
available_at            TIMESTAMPTZ   NOT NULL   -- 解析后的权威字段，PIT 查询走它
availability_quality    availability_quality_enum NOT NULL
version                 INTEGER       NOT NULL DEFAULT 1

-- available_at 的三个来源依据（审计用，不参与查询）
published_at            TIMESTAMPTZ   NULL
provider_available_at   TIMESTAMPTZ   NULL
ingested_at             TIMESTAMPTZ   NOT NULL
```

```sql
CREATE TYPE availability_quality_enum AS ENUM ('EXACT', 'DERIVED', 'INFERRED');
```

**唯一约束**：`(business_key..., effective_at, version)`

#### 4.4.1 为什么三个来源字段可空而 `available_at` 不可空

> **`available_at` 是解析产物，三个来源是它的依据**（`03-data/01-data-source` §11）。

| 字段 | 可空性 | 理由 |
|---|---|---|
| `available_at` | **NOT NULL** | PIT 判定的唯一依据，空值等于该行永不可见或永远可见，两者都是错的 |
| `availability_quality` | **NOT NULL** | 与 `available_at` 成对，缺它则无法区分精确值与兜底值 |
| `ingested_at` | **NOT NULL** | 平台自己写入，永远可得 |
| `published_at` / `provider_available_at` | **NULL 允许** | Provider 能力差异，**拿不到就是拿不到** |

> **不得给两个可空字段设默认值** —— 用 `ingested_at` 回填 `provider_available_at` 会让 `availability_quality` 被误判为 `EXACT`，这是 `02-architecture/04-integration-architecture` §2.5 明确禁止的（Adapter 须如实留空）。

**一致性约束**：

```sql
CHECK (
  (availability_quality = 'EXACT'    AND provider_available_at IS NOT NULL) OR
  (availability_quality = 'DERIVED'  AND provider_available_at IS NULL AND published_at IS NOT NULL) OR
  (availability_quality = 'INFERRED' AND provider_available_at IS NULL AND published_at IS NULL)
)
```

> **该约束把 §11.3 的三级优先级写进了数据库** —— 它不是可选的一致性检查，而是防止「有推送时间却标成 INFERRED」这类映射错误在存储层就被拦下。

**时序约束**（`03-data/01-data-source` §11.6）：

```sql
CHECK (
  (published_at          IS NULL OR published_at          >= effective_at) AND
  (provider_available_at IS NULL OR published_at IS NULL OR provider_available_at >= published_at) AND
  (ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))
)
```

> **注意 `effective_at` 是 `DATE` 而其余是 `TIMESTAMPTZ`** —— 比较时 `effective_at` 隐式转为当日 00:00，因此「公告发生在生效日当天」仍满足约束。

### 4.5 区间型表的标准列

```
valid_from              DATE          NOT NULL
valid_to                DATE          NULL        -- NULL 表示仍生效
available_at            TIMESTAMPTZ   NOT NULL    -- 见 03-erd §15.2
availability_quality    availability_quality_enum NOT NULL
published_at            TIMESTAMPTZ   NULL
provider_available_at   TIMESTAMPTZ   NULL
ingested_at             TIMESTAMPTZ   NOT NULL
```

**约束**：`CHECK (valid_to IS NULL OR valid_from < valid_to)` + §4.4.1 的两组约束

---

## 5. Core Table Catalog

> **共约 60 张表。** 下列按 schema 归类，逐 schema 的设计要点见 §6–§14。

| Schema | 主要表 |
|---|---|
| `raw` | `raw_payload`、`canonical_raw` |
| `fund` | `fund`、`fund_share_class`、`provider_fund_identity`、`fund_management_company`、`fund_manager`、`fund_manager_assignment`、`fund_classification_history`、`fund_status_history`、`fund_fee`、`fund_subscription_status`、`investment_eligibility` |
| `market` | `fund_nav`、`fund_distribution`、`benchmark_definition`、`benchmark_component`、`benchmark_index`、`benchmark_index_value`、`benchmark_mapping`、`risk_free_rate` |
| `factor` | `factor_definition`、`factor_version`、`factor_run`、`factor_value`、**`factor_effectiveness`** |
| `evaluation` | `peer_group_snapshot`、`peer_group_member`、`fund_evaluation`、`fund_score`、`fund_score_attribution`、`fund_ranking`、`fund_tier`、`fund_universe_snapshot`、`fund_universe_member`、`selection_condition_result` |
| `portfolio` | `portfolio`、`portfolio_target`、`portfolio_pending`、`portfolio_actual`、`portfolio_position`、**`estimation_method`**、`estimation_run`、`return_estimate`、`risk_estimate`、`covariance_estimate`、`covariance_instrument`、`optimization_result`、`binding_constraint`、`investment_decision`、`decision_review`、`rebalance`、`rebalance_trade` |
| `backtest` | `backtest`、`backtest_run`、`backtest_period`、`backtest_position`、`backtest_trade`、`backtest_nav`、`backtest_metric`、`backtest_bias_check`、`backtest_report` |
| `governance` | `policy_version`、`lineage_node`、`lineage_edge`、`data_quality_result`、`audit_log`、`data_provider`、`data_provider_dataset`、`data_source_priority` |

### 5.1 表数量的克制

> **沿用提示词 §21.4：一个业务实体不一定必须是一张表；一张表也不应承担多个独立业务实体。**

**本域拆表的四条依据**：生命周期不同、Ownership 不同、查询模式不同、数据量差异悬殊。

---

## 6. Fund Tables

### 6.1 `fund` 与 `fund_share_class`

| 项 | `fund` | `fund_share_class` |
|---|---|---|
| **为什么存在** | 基金产品的身份 | **全平台的计算粒度** |
| PK | `id BIGINT` | `id BIGINT` |
| Business Key | `fund_code`（平台内） | `(fund_id, share_class_code)` |
| Temporal | 非版本化属性 | 同上 |
| Write Owner | `data-service` | `data-service` |
| Read | 全部下游 | **全部下游** |
| 数据量 | 万级 | 数万级 |
| Partition | ❌ | ❌ |

> **绝大多数下游表的外键指向 `fund_share_class`，而非 `fund`** —— 这是 §6.1 的直接后果。

### 6.2 `provider_fund_identity`

| 项 | 说明 |
|---|---|
| **为什么存在** | **Provider ID 不得作为 Share Class 的属性**（`01-postgresql` §6.1） |
| PK | `id BIGINT` |
| **Unique** | `(provider_id, provider_fund_id, valid_from)` |
| FK | `share_class_id` → `fund.fund_share_class` `RESTRICT` |
| Temporal | `valid_from` / `valid_to` / `available_at` |
| Index | `idx_pfi_share_class`、`uq_pfi_provider_key` |

#### 6.2.1 为什么唯一键含 `valid_from`

> **映射关系会变化**（`03-erd` §5.3.1）。同一 `(provider_id, provider_fund_id)` 在不同时期可能指向不同的 Share Class（Provider 重新分配 ID）。

### 6.3 `fund_manager_assignment`

| 项 | 说明 |
|---|---|
| **为什么存在** | 任职是**区间**且支持**共管** |
| PK | `id BIGINT` |
| FK | `fund_id`、`manager_id` |
| Temporal | `valid_from` / `valid_to` / `available_at` |
| **Constraint** | `EXCLUDE USING gist` —— 同一 `(fund, manager)` 区间不重叠 |
| Index | `(manager_id, valid_from)`、`(fund_id, valid_from)` |

> **共管是允许的** —— 排除约束只针对同一经理对同一基金（`01-postgresql` §8.4）。

### 6.4 `investment_eligibility`

| 项 | 说明 |
|---|---|
| **为什么存在** | 派生实体，但**回测需查历史**（`03-erd` §5.6） |
| PK | `(share_class_id, effective_at, version)` |
| Temporal | 三时点 + version |
| Write Owner | `data-service` |
| Read | `fund-service`（准入）、`portfolio-service`（建仓校验）、`backtest-service`（Tradability 检查） |
| Index | `(share_class_id, available_at, version DESC)` |
| Partition | ❌（万级 × 状态变更频率低） |

#### 6.4.1 它是派生的，但不能每次重算

```
若不持久化，回测查"2022-03-31 的可投资性"需要重算
    → 依赖当时的 Subscription Status 与流动性指标是否完整
    → 且重算规则可能已变（版本前视）
```

---

### 6.5 `fund_fee`（v1.4 扩充）

> **定案 · 2026-08-27**：Policy ⑩ 要求包含关系必须落库。见 `03-data/02-data-domain-model` §8.1.1、`TBD-resolution.md` Policy ⑩。

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `share_class_id` | FK | NOT NULL | **费率是 Share Class 粒度** |
| `expense_type` | `expense_type_enum` | NOT NULL | 管理费 / 托管费 / 销售服务费 / 申购费 / 赎回费 |
| `expense_rate` | `NUMERIC` | NOT NULL | 阶梯费率见下 |
| **`included_in_nav`** | `inclusion_enum` | NOT NULL | **`TRUE` / `FALSE` / `UNKNOWN`** |
| `included_in_return` | `inclusion_enum` | NOT NULL | 同上 |
| `included_in_backtest` | `BOOLEAN` | NOT NULL | **推导列** |
| `inclusion_source` | `TEXT` | NOT NULL | 判定依据 |

```sql
CREATE TYPE inclusion_enum AS ENUM ('TRUE', 'FALSE', 'UNKNOWN');
```

#### 6.5.1 为什么 `included_in_nav` 是三值枚举而不是可空布尔

> **`UNKNOWN` 与「尚未录入」是两件事。**

| 状态 | 含义 | 处置 |
|---|---|---|
| `TRUE` / `FALSE` | 已核定 | 按值推导 |
| **`UNKNOWN`** | **已核查，数据源不声明** | 回测不扣除，**列入 `unmodeled_costs` 并披露** |
| `NULL`（若允许） | 尚未录入 | —— |

用可空布尔表示时，`NULL` 同时承担后两种含义，**回测无法区分「确认无从得知」与「还没人填」** —— 前者应当披露，后者应当阻断。因此本列 `NOT NULL`，`UNKNOWN` 是一个正式取值。

#### 6.5.2 `included_in_backtest` 是推导列但仍落库

```sql
included_in_backtest = (included_in_nav <> 'TRUE') AND occurs_at_transaction
```

> **落库而非每次计算**的理由：它是回测查询的高频过滤条件，且**推导规则本身会随 Policy 版本变化**。落库使历史回测能复现「当时是怎么推的」；每次现算则会让旧回测在规则变更后得出不同结论。

> **代价是须与来源列保持一致** —— 由触发器或应用层单一写入路径保证，不允许两处独立写入。

#### 6.5.3 阶梯费率

赎回费按持有期阶梯（`06-portfolio/06-rebalancing` §7.2），**不得取单一值**。阶梯存于独立的 `fund_fee_tier` 子表，`(fee_id, tier_lower_bound)` 为主键。

> **阶梯使赎回成本成为持有期的函数** —— 同一笔赎回在不同持有期下成本不同，因此回测的成本计算必须携带建仓日期，不能只看当期权重变化。

## 7. Market / Benchmark Tables

### 7.1 `fund_nav` — 分区表

| 项 | 说明 |
|---|---|
| **为什么存在** | 全平台一切计算的数据基础 |
| **PK** | `(share_class_id, effective_at, version)` |
| Temporal | 三时点 + version |
| **Partition** | **按 `effective_at` 年分区** |
| 数据量 | ~3,000 万行 / ~1.5 GB |
| Write Owner | `data-service` |
| Read | `factor-service`、`portfolio-service`、`backtest-service` |
| **UPDATE** | **禁止** —— 修订产生新 `version` |

**列要点**：

| 列 | 类型 | 说明 |
|---|---|---|
| `nav_raw` | `NUMERIC(18,6)` | 原始净值 |
| `nav_adjusted` | `NUMERIC(18,6)` | **复权净值 —— 默认计算基础** |
| `adjustment_rule_version` | `VARCHAR` | 复权口径版本 |

#### 7.1.1 复权方向已定案：后复权 ✅

> **定案 · 2026-08-27**：`TBD-DN-3` 关闭（`03-data/05-data-normalization` §5.3.1、`TBD-resolution.md` Policy ③）。

**双轨保存的四列必须齐备**：

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `nav_raw` | `NUMERIC` | NOT NULL | 原始净值，**不可变** |
| `nav_adjusted` | `NUMERIC` | **NULL 允许** | 后复权净值；分红或拆分记录缺失时为 `NULL` |
| `adjustment_factor` | `NUMERIC` | NULL 允许 | 与 `nav_adjusted` 同步 |
| `adjustment_policy_version` | `TEXT` | NULL 允许 | 与 `nav_adjusted` 同步 |

> **`nav_adjusted` 可空是有意的** —— 它承载 `03-data/05` §5.3.2 的 `UNAVAILABLE` 语义。**不得设默认值、不得回填 `nav_raw`**：那会在分红日制造虚假暴跌，且在净值曲线上看起来完全正常，事后无法察觉。

**一致性约束**：

```sql
CHECK (
  (nav_adjusted IS NULL     AND adjustment_factor IS NULL     AND adjustment_policy_version IS NULL) OR
  (nav_adjusted IS NOT NULL AND adjustment_factor IS NOT NULL AND adjustment_policy_version IS NOT NULL)
)
```

> **原「若最终选择前复权，历史 `nav_adjusted` 需全量重算」的条件表述已作废** —— 后复权下历史值不随新事件变化，不存在全量重算场景。规则变更时也**不追溯改写**，只对变更之后的数据生效。

#### 7.1.2 索引

| 索引 | 用途 |
|---|---|
| PK `(share_class_id, effective_at, version)` | W1 时间序列 |
| `(share_class_id, available_at, version DESC) INCLUDE (nav_adjusted)` | **PIT 点查 —— 索引覆盖，避免回表** |
| `(effective_at)` | 全市场横截面（分区内） |

### 7.2 Benchmark 四表

| 表 | 数据量 | Partition | 要点 |
|---|---|---|---|
| `benchmark_definition` | 千级 | ❌ | 基准的构成定义 |
| `benchmark_component` | 千级 | ❌ | **成分与权重 —— 复合基准必需** |
| `benchmark_index` | 千级 | ❌ | 指数本体 |
| **`benchmark_index_value`** | **百万级** | **✅ 按 `effective_at` 年分区** | 指数行情序列 |
| `benchmark_mapping` | 数万级 | ❌ | **基金 ↔ 基准，版本化** |

#### 7.2.1 `benchmark_component` 的权重约束

```
CHECK (weight >= 0 AND weight <= 1)
```

> **`Σ weight = 1` 是跨行约束，放应用层**（`01-postgresql` §8.3）。

#### 7.2.2 `benchmark_mapping` 必须有 `available_at`

> 基金转型改变基准，公告日晚于生效日 —— 用今天的映射回算历史 Alpha 是前视（`08-backtest/03` §12.3）。

### 7.3 `risk_free_rate`

| 项 | 说明 |
|---|---|
| **PK** | `(currency, tenor, effective_at, version)` |
| Temporal | 三时点 + version |
| Partition | ❌（数据量小） |
| **要点** | **不以基金为主体**；不得退化为单一序列 |

**列**：`rate_value NUMERIC(12,8)`、`quotation_basis VARCHAR`、`source VARCHAR`、**`rate_source_quality rate_quality_enum NOT NULL`**

```sql
CREATE TYPE rate_quality_enum AS ENUM ('EXACT', 'INTERPOLATED');
```

#### 7.3.1 插值点与观测点同表存储

> **插值结果落库并版本化**（`03-data/02-data-domain-model` §10.2.1）—— 它不是查询时算出来的临时值。

| 场景 | 处理 |
|---|---|
| 该 tenor 有真实观测 | `rate_source_quality = 'EXACT'` |
| 该 tenor 缺失，由相邻插值 | `rate_source_quality = 'INTERPOLATED'`，**照常落库** |
| 事后补入真实观测 | **产生新 `version`**（`EXACT`），**不覆盖**原插值行 |

> **不覆盖是 PIT 的要求** —— `decision_at` 早于补入时刻的历史查询应当取到插值版本，因为当时确实只有插值可用。覆盖会让历史因子在补数后悄然改变。

> **`rate_source_quality` 不进主键** —— 同一 `(currency, tenor, effective_at)` 的插值版本与观测版本靠 `version` 区分，quality 是该版本的属性。

---

## 8. Data Governance Tables

### 8.1 `raw_payload` — 分区表

| 项 | 说明 |
|---|---|
| **为什么存在** | Adapter 逻辑变更后可**重新解析**（`03-erd` §7.1） |
| PK | `id BIGINT` |
| **Partition** | **按接收时间月分区** —— 便于整体归档 |
| 数据量 | 大（体量最大但查询最少） |
| **Retention** | 见 §18.3 |
| 存储 | `payload JSONB` 或 `TEXT`（视 Provider 响应格式） |

### 8.2 `lineage_node` / `lineage_edge`

| 项 | 说明 |
|---|---|
| **为什么两张表** | 血缘是**有向图**，N:M 关系需边表 |
| `lineage_node` | `(node_type, node_ref)` —— 逻辑引用，不建 FK |
| `lineage_edge` | `(from_node_id, to_node_id, edge_type)` |
| **数据量** | **取决于血缘粒度 —— 见 §8.2.1** |
| Partition | 按时间分区（若采用 Record Level） |

#### 8.2.1 血缘粒度直接决定数据量 ⚠️

> **沿用 `03-data/07-data-lineage` §3 的三级血缘。**

| 级别 | 粒度 | 数据量 |
|---|---|---|
| Dataset Level | 数据集之间 | 极小 |
| **Decision Level** | **每次决策的输入闭包** | **中等 —— 第一阶段必需** |
| Record Level | 每条记录 | **爆炸式** —— 与 `factor_value` 同量级甚至更大 |

> **第一阶段采用 Decision Level**（`03-data/07` 已定）。若未来需要 Record Level，须重新评估存储与分区策略。

> **已定案 · 2026-08-27**：血缘粒度见 `03-data/07-data-lineage` `DL-1` —— **Record Level 仅覆盖决策链路**，非决策链路保留 Dataset Level；保留期 **7 年**（Policy C · L3）。
>
> **本域的存储影响**：`lineage_edge` 表的规模由此从「与 `factor_value` 同量级」降到「与 `investment_decision` 同量级」，即千万级降到十万级。

### 8.3 `audit_log`

| 项 | 说明 |
|---|---|
| **为什么存在** | `NFR-SEC-004` 不可篡改的审计日志 |
| PK | `id BIGINT` |
| **FK** | **无** —— 被审计对象删除后仍须存在（`03-erd` §7.3） |
| 引用 | `(resource_type, resource_id)` 逻辑引用 |
| **权限** | **仅 INSERT**，禁止 UPDATE / DELETE |
| Partition | 按 `created_at` 月分区 |
| Retention | 长期（合规决定） |

### 8.4 `policy_version`

| 项 | 说明 |
|---|---|
| **为什么存在** | 各类 Policy 的版本注册表 |
| Business Key | `(policy_type, policy_id, version)` |
| 覆盖 | **五类 Policy**：Evaluation / Ranking / Classification / Estimation / Validation（收敛规则见 §8.4.1） |
| **要点** | 见 §8.4.1 |

#### 8.4.1 `policy_version` 表由兜底升为决策快照的正式外键来源 ✅

> **定案 · 2026-08-27**。原为多个域各自登记的「某某 Policy Version 不在九项 Strategy Version 之内」缺口（`02-architecture` §8.5、`05-fund-evaluation/01` §21.3、`07-return-risk/01` §14.3、`10-api/05` §10.1），现已随第 10 类 `Policy Version` 一并关闭。

**治理侧定案**：版本模型由四类扩为**五类**，`Policy Version` 与 `Strategy Version` **并列**，含五个子项（`02-architecture/01-system-architecture` §8.2.1）。

**对本表的影响** —— 本表原为"兜底可追溯性"而设，现升为正式来源：

| 项 | 定案前 | 定案后 |
|---|---|---|
| 表的定位 | 兜底注册表，快照**可选**引用 | 决策快照的**正式外键来源** |
| `policy_type` 取值 | 各域自行登记的 11 种 | **收敛为 5 种**：`evaluation` / `ranking` / `classification` / `estimation` / `validation` |
| 快照引用 | 无强制 | 快照的 `policy_version_ref` **非空约束** |

**`policy_type` 收敛的映射**（原 11 种 → 5 子项）：

| 原类型 | 归入 |
|---|---|
| `evaluation` | `evaluation` |
| `ranking` | `ranking` |
| `classification` | `classification` |
| `estimation` | `estimation` |
| `scoring` | **不归入** —— 属第 4 项 `Scoring Version`，是 Strategy 不是 Policy |
| `portfolio_rule` / `rebalance_rule` | **不归入** —— 属第 7、8 项 Strategy Version |
| `validation` / `methodology` / `report` | `validation` |
| `transaction_cost` | **不归入** —— 属第 7 项 `Portfolio Rule Version` 的成本模型部分 |

> **收敛后 `policy_version` 表只存 Policy，不再混入 Strategy 配置** —— 后者由各 Owner Service 的自有配置表持有，快照通过 `strategy_version_ref` 引用。混存会让「这一版是策略变更还是标准变更」在存储层就无法区分，而这正是两类版本要分开的理由。

---

## 9. Factor Tables

### 9.1 `factor_value` — 最大的表

| 项 | 说明 |
|---|---|
| **为什么存在** | 全部因子结果 |
| **PK** | `(share_class_id, factor_id, window, as_of_date, version)` |
| **数据量** | **~1.5 亿行 / ~6 GB** |
| **Partition** | **按 `as_of_date` 月分区** |
| Write Owner | `factor-service` |
| Read | `fund-service`、`backtest-service` |
| **UPDATE** | 禁止 |

### 9.2 关键列

| 列 | 类型 | 说明 |
|---|---|---|
| **`raw_value`** | `NUMERIC(18,8)` | 可为 NULL（`UNAVAILABLE` 时） |
| **`normalized_value`** | `NUMERIC(12,8)` | 同上 |
| **`status`** | `VARCHAR` + CHECK | `VALID`/`WARNING`/`INVALID`/`UNAVAILABLE` |
| **`unavailable_reason`** | `VARCHAR` | 八类之一（`10-api/03` §4.3.5） |
| `peer_group_id` + `peer_group_version` | —— | **标准化上下文** |
| `risk_free_rate_ref` | JSONB 或列组 | 溯源 —— **须含 `currency`、`tenor`、`version`、`rate_source_quality`**（§9.2.1） |
| **`evaluation_policy_version`** | `VARCHAR` NULL | **见 §9.3** |
| `factor_version` | `VARCHAR` | 因子口径版本 |
| `data_version` | `VARCHAR` | 数据版本 |

#### 9.2.1 `risk_free_rate_ref` 的四个必备字段（v1.5 定案）

> **定案 · 2026-08-27**：见 `04-factor/04-factor-calculation` §3.4 TR-2、`TBD-resolution.md` Policy ①。

| 字段 | 为什么必须 |
|---|---|
| `currency` | 同一因子在不同计价币种基金上用的是不同曲线 |
| **`tenor`** | **同一基金的 1Y 与 3Y Sharpe 用不同 tenor** —— 缺它则无法验证期限匹配是否正确 |
| `version` | PIT 复现的依据 |
| **`rate_source_quality`** | 区分「这只基金确实差」与「它的 `R_f` 是插出来的」 |

> **`risk_free_rate_ref` 是溯源信息，不是标识的一部分** —— 这一点与 `evaluation_policy_version` 相反（§9.3）。`R_f` 由 `(currency, tenor, decision_at)` **唯一确定**，因此不进唯一约束；而 `MAR` 由 Policy 版本决定，同一 `(Fund, Factor, Window, Date)` 在不同 Policy 版本下有不同的值。

> **`R_f` 是序列而非标量**（`04-factor/04` §3.4.2），因此 `version` 记的是**解析基准**（截至 `decision_at` 的可见版本），不是窗口内每一期的 version 列表 —— 后者可由基准 + PIT 规则唯一重建，无需冗余存储。

### 9.3 依赖 MAR 的因子使唯一约束成为条件性的 ⚠️

> **沿用 `03-erd` §8.2.1 —— 这是本域最棘手的一处建模难点。**

```
不依赖 MAR 的因子：evaluation_policy_version IS NULL
依赖 MAR 的因子  ：evaluation_policy_version 必填

PostgreSQL 中 NULL 不参与唯一性比较
    → UNIQUE(share_class_id, factor_id, window, as_of_date, version, evaluation_policy_version)
    → 对 NULL 行【不生效】→ 可插入重复
```

**三个候选方案**：

| 方案 | 说明 | 权衡 |
|---|---|---|
| **A：用哨兵值代替 NULL（推荐）** | 不依赖 MAR 时填 `'N/A'` | ✅ 唯一约束正常工作<br/>⚠️ 引入魔法值 |
| B：两个部分唯一索引 | `WHERE ... IS NULL` 与 `WHERE ... IS NOT NULL` 各一个 | ✅ 无魔法值<br/>⚠️ 两个索引，维护成本 |
| C：`NULLS NOT DISTINCT`（PG 15+） | 让 NULL 参与唯一性 | ✅ 最简洁<br/>⚠️ **依赖 PG 版本** |

> **已定案 · 2026-08-27**：采用**方案 A —— 部分唯一索引**（Partial Unique Index）。
>
> ```sql
> -- 不依赖 MAR 的因子
> CREATE UNIQUE INDEX ux_factor_value_no_policy
>   ON factor.factor_value (share_class_id, factor_id, window, effective_at, version)
>   WHERE evaluation_policy_version IS NULL;
>
> -- 依赖 MAR 的因子
> CREATE UNIQUE INDEX ux_factor_value_with_policy
>   ON factor.factor_value (share_class_id, factor_id, window, effective_at, version, evaluation_policy_version)
>   WHERE evaluation_policy_version IS NOT NULL;
> ```
>
> **依据**：PostgreSQL **原生支持**部分索引，无需触发器（方案 B）或生成列（方案 C）。本系统已定 PostgreSQL 且版本可控（`06-technology-stack`），不存在可移植性顾虑。
>
> **两个方案的问题**：触发器方案把约束逻辑放进过程代码，无法被查询计划器利用；生成列方案需要为 `NULL` 造一个哨兵值（如 `'__NONE__'`），而哨兵值会泄漏到查询条件中。

### 9.4 `factor_effectiveness`（v1.7 新增）

> **由 Policy ⑥ 引入**（`11-database/03-erd` §8.4）：因子权重由有效性检验结果产出，检验结果须可查询、可版本化。

| 项 | 说明 |
|---|---|
| **PK** | `id BIGINT` |
| **Business Key** | `(factor_version_id, peer_group_snapshot_id, evaluation_window, sample_split, validation_policy_version)` |
| 数据量 | **万级** —— 因子数 × 组数 × 窗口数 × 2（IS/OOS） |
| Partition | ❌ |

**关键列**：

```
sample_split                    sample_split_enum NOT NULL   -- 'IS' / 'OOS'
ic, icir, rank_ic               NUMERIC(10,6)
monotonicity_score              NUMERIC(10,6)
stability_score                 NUMERIC(10,6)
max_correlation_with_existing   NUMERIC(10,6)
effectiveness_verdict           verdict_enum NOT NULL        -- 'VALID' / 'INVALID'
validation_policy_version       VARCHAR NOT NULL
```

#### 9.4.1 `validation_policy_version` 进 Business Key

> **同一份检验数值在不同阈值下会得出不同 `effectiveness_verdict`。**

把阈值版本纳入唯一键，使阈值调整**产生新行而非覆盖旧行** —— 否则一次阈值放宽会让历史上「当时被判无效」的记录消失，而依赖那次判定的历史 Score 无从解释。

> **与 `factor_value` 的 `evaluation_policy_version` 同源**（§9.3）：两者都是「结论依赖策略版本」的情形，处理方式一致。

#### 9.4.2 IS 与 OOS 必须是不同的行

```
sample_split 进 Business Key
    → 同一 (因子, 组, 窗口) 有两行：IS 与 OOS
    → 权重由 IS 行产出，OOS 行用于验证
```

> **不合并为一行的两列** —— 合并会让「只做了 IS 没做 OOS」与「两者都做了」在结构上不可区分，而前者恰恰是 Policy ⑥ 明令禁止的做法。

### 9.5 索引设计

| 索引 | 对应负载 | 说明 |
|---|---|---|
| PK | W1 | 单基金单因子时间序列 |
| **`(as_of_date, factor_id, share_class_id) INCLUDE (raw_value, normalized_value)`** | **W2** | **横截面 —— 索引覆盖** |
| `(peer_group_id, as_of_date, factor_id)` | W3 | Peer Group 内分位 |
| `(factor_run_id)` | 批次追溯 | —— |

#### 9.5.1 W2 的索引可能仍不够 ⚠️

> **沿用 `01-postgresql` §11.5：这是选型的主要风险点。**

```
单时点全市场 = 1.2 万基金 × 50 因子 = 60 万行
    → 即使分区裁剪到单月分区
    → 索引覆盖扫描 60 万行仍需可观时间
```

**必须由 `TBD-TECH-7` 的压测确定是否达标**；不达标时按 `01-postgresql` §11.5 的候选优化处理。

### 9.6 分区策略的权衡

> **沿用 `01-postgresql` §12.4：按 `as_of_date` 分区优化 W2，代价是 W1 跨分区。**

```
W1（单基金 3 年序列）→ 跨 36 个月分区 → 略慢
W2（单时点横截面）  → 命中单分区   → 显著快

选择优化 W2，因为它是选型的风险点
```

---

## 10. Evaluation Tables

### 10.1 `peer_group_snapshot` + `peer_group_member`

| 项 | 说明 |
|---|---|
| **为什么两张表** | 快照是实体，成员是明细；**成员列表必须完整留存** |
| `peer_group_snapshot` PK | `id BIGINT` |
| Business Key | `(classification_key, effective_at, version)` |
| `peer_group_member` PK | `(peer_group_snapshot_id, share_class_id)` |
| **数据量** | 快照千级；**成员 = 快照数 × 组规模** |
| Partition | 成员表按 `effective_at` 年分区 |

#### 10.1.1 为什么不能只存构建规则

> **沿用 `03-erd` §9.1、`FR-PEER-002`：** 规则加输入不等于结果可还原 —— 输入（分类数据）本身会变。

#### 10.1.2 `fund_ranking` 与 `fund_tier` 的横截面状态列（v1.6 定案）

> **定案 · 2026-08-27**：`MIN_PEER_GROUP_SIZE = 30`（`02-business-requirements` §7.3.1、`TBD-resolution.md` Policy ⑤）。

| 表 | 新增列 | 类型 |
|---|---|---|
| `fund_ranking` | **`ranking_status`** | `cross_section_status_enum NOT NULL` |
| `fund_ranking` | `n_effective` | `INTEGER NOT NULL` |
| `fund_tier` | **`classification_status`** | `cross_section_status_enum NOT NULL` |
| `fund_tier` | `n_effective` | `INTEGER NOT NULL` |

```sql
CREATE TYPE cross_section_status_enum AS ENUM ('NORMAL', 'INSUFFICIENT_SAMPLE');
```

**联动约束**：

```sql
-- fund_ranking
CHECK (
  (ranking_status = 'NORMAL'              AND rank IS NOT NULL AND percentile IS NOT NULL) OR
  (ranking_status = 'INSUFFICIENT_SAMPLE' AND rank IS NULL     AND percentile IS NULL)
)
```

> **`INSUFFICIENT_SAMPLE` 的行仍然落库，不是不写行** —— 「该组该期该指标样本不足」本身是需要留存的事实。不落库会让历史查询无法区分「当时样本不足」与「当时根本没算」。

> **`n_effective` 在两种状态下都必填** —— 它是判定依据，也是事后分析「哪些分类长期低于 30」（`OPEN-10`）的唯一数据来源。

> **阈值本身不落在这两张表** —— 它属 `governance.policy_version` 的 Peer Group Policy（`min_sample_size`），三处（标准化 / 排名 / 分层）共用同一配置来源。表里存的是判定**结果**，不是判定**参数**。

### 10.2 `fund_score` + `fund_score_attribution`

| 表 | 数据量 | 要点 |
|---|---|---|
| `fund_score` | ~3,000 万 | 总分 + 五子分 |
| **`fund_score_attribution`** | **~3,000 万 × 因子数** | **归因明细 —— 见 §10.2.1** |

#### 10.2.1 归因表的数据量需要评估 ⚠️

```
若每个 Score 有 15 个因子的归因
    → 3,000 万 × 15 = 4.5 亿行
    → 【超过 factor_value】
```

**三个选项**：

| 选项 | 权衡 |
|---|---|
| **完整存储（明细表）** | ✅ 可按因子聚合分析<br/>❌ 数据量最大 |
| **JSONB 存储** | ✅ 量小<br/>❌ 无法按因子聚合（违反 `03-erd` §9.3） |
| **仅存当前 + 决策时点** | ✅ 量可控<br/>⚠️ 历史归因不完整 |

`<TBD-DBD-3: `fund_score_attribution` 的存储策略与保留期，待归因查询需求与数据量实测确认>`

> **本域倾向完整明细表**（`03-erd` §9.3 的理由成立），但**必须先确认数据量可接受**。

### 10.3 `fund_universe_snapshot` + `fund_universe_member` + `selection_condition_result`

| 表 | 要点 |
|---|---|
| `fund_universe_snapshot` | 一次 Universe 生成 |
| **`fund_universe_member`** | **含 `SELECTED` 与 `REJECTED` 两类** |
| **`selection_condition_result`** | **逐条件的通过/未通过明细** |

#### 10.3.1 存 `REJECTED` 成员使数据量翻数倍 ⚠️

```
Universe 最终 50 只，但候选集可能 1,200 只
    → 存全部候选的判定结果 = 1,200 行/次，而非 50 行
    → 再乘以逐条件明细（假设 8 个条件）= 9,600 行/次
```

**但这是必需的**（`05-fund-evaluation/05` §14.3）：

```
若 90% 基金因同一条件被排除，说明该条件可能设置不当
    → 只有留痕才能发现
```

**优化**：`selection_condition_result` 可只存**未通过**的条件（通过的可由"未出现在失败列表中"推断），使数据量降低约一个数量级。

> **已定案 · 2026-08-27**：`selection_condition_result` **存全部条件**，不只存未通过项。
>
> **依据 —— `05-fund-selection` §14.4 已确立「记录未通过的全部条件不短路」**，本条是其存储侧的对应要求。
>
> ```
> 只存未通过项
>     → 无法回答「这只基金通过了哪些条件」
>     → 也无法区分「通过了」与「根本没评估」
>     → 而后者会在条件集变更时大量出现
> ```
>
> **存储量可控**：条件数为个位数到十几个，乘以 Universe 规模与决策周期数，量级远低于 `factor_value`。
>
> **须一并存 `condition_version`** —— 条件集本身会变更，不记录版本则历史结果无法解释。

---

## 11. Portfolio Tables

### 11.1 三态三表

| 表 | 要点 |
|---|---|
| `portfolio_target` | 决策产出的目标权重 |
| `portfolio_pending` | 已交付未回报的调整 |
| **`portfolio_actual`** + `portfolio_position` | **实际持仓 —— 以份额为主** |

#### 11.1.1 为什么不用一张表加 `state` 字段

> **沿用 `03-erd` §10.1：三者同时存在，不是状态流转。**

### 11.2 `portfolio_position`

| 列 | 说明 |
|---|---|
| `share_class_id` | 标的 |
| **`shares`** | `NUMERIC(24,8)` —— **主字段** |
| `cost_basis` | 成本（赎回费阶梯需要） |
| **`lot_detail`** | **见 §11.2.1** |
| `is_frozen` + `frozen_reason` | 冻结标记 |

#### 11.2.1 批次明细的存储取决于是否建模赎回费阶梯

> **沿用 `08-backtest/05` §4.5、`TBD-TC-3`。**

```
若建模持有期阶梯 → 需存每只基金的 [(买入日期, 份额), ...]
    → 单独的 position_lot 表，或 JSONB
若不建模 → 只需当前份额
```

> **已定案 · 2026-08-27**：**建 `position_lot` 表**。
>
> **依据**：`08-backtest/05` `TC-3` 已定案**建模赎回费的持有期阶梯**，而阶梯依赖持有批次 —— 必须逐批次记录建仓时点与份额，才能在赎回时按 FIFO（`TC-2`）确定各批次的持有期与适用费率。
>
> **表结构要点**：
>
> | 项 | 说明 |
> |---|---|
> | Business Key | `(portfolio_id, share_class_id, acquired_at, run_context)` |
> | 关键列 | `units`、`cost_basis`、`acquired_at`、`remaining_units` |
> | 数据量 | 与 `rebalance_trade` 同量级 —— 每次买入产生一个 lot |
> | 生命周期 | `remaining_units = 0` 后保留（成本归因需要），不删除 |
>
> **回测与实盘同表**，以 `run_context` 区分（同 `ERD-3`）。

### 11.3 `covariance_estimate` + `covariance_instrument`

| 表 | 说明 |
|---|---|
| `covariance_estimate` | **一行 = 一个矩阵**；`matrix JSONB` + 诊断量列 |
| **`covariance_instrument`** | **`(estimate_id, ordinal, share_class_id)` —— 保证顺序与成员可校验** |

#### 11.3.1 为什么矩阵用 JSONB 而成员用明细表 ⚠️

> **沿用 `01-postgresql` §13.3 与 `07-return-risk/04` §9.1。**

```
矩阵数值：整体读写，不做字段级查询 → JSONB
成员顺序：需要外键校验成员有效性，需要按 ordinal 排序 → 明细表

两者组合：顺序可校验，数值可整体存取
```

**失配的后果**：`w'Σw` 算出无意义的数，**且不会报错** —— 明细表的外键至少保证成员存在。

### 11.4 `optimization_result` + `binding_constraint`

| 表 | 要点 |
|---|---|
| `optimization_result` | **含 `INFEASIBLE` 的情形 —— 无决策但仍留存** |
| `binding_constraint` | 紧约束清单（`06-portfolio/03` §10.2） |

**关键列**：`optimization_status`、`objective_value`、`solve_path`、`random_seed`、`code_version`、`target_weights JSONB`

#### 11.4.1 `target_weights` 用 JSONB 还是明细表

| 方案 | 权衡 |
|---|---|
| **JSONB（推荐）** | ✅ 与优化结果原子；✅ 权重是整体，不单独查询 |
| 明细表 | ⚠️ 可按基金聚合分析历史权重，但**需额外保证与 `binding_constraint` 的一致性** |

> **已定案 · 2026-08-27**：`target_weights` 采用**行式存储**（每基金一行），不用 JSONB。
>
> **依据 —— 「按基金查历史权重」需要索引到基金维度**：
>
> ```
> JSONB：{"F001": 0.05, "F002": 0.03, ...}
>     → 查「F001 在过去 3 年的目标权重变化」
>     → 须全表扫描 + JSONB 解包
>     → GIN 索引可加速存在性查询，但无法高效支持【范围 + 排序】
>
> 行式：(portfolio_id, as_of_date, share_class_id, target_weight)
>     → 索引 (share_class_id, as_of_date) 直接命中
> ```
>
> **JSONB 的优势场景不适用于此**：它适合结构不固定的稀疏属性，而目标权重是结构完全固定的二维数据。
>
> **存储量代价可接受**：组合数 × 持仓数 × 决策周期数，量级在百万级。

### 11.5 `decision_review`

| 列 | 说明 |
|---|---|
| `action` | `APPROVED` / `REJECTED` / `OVERRIDDEN` |
| **`reason`** | **`NOT NULL`** —— 上游 §7.1.1 |
| **`original_weights` / `final_weights`** | Override 时必须同时保留 |
| `reviewed_by` / `reviewed_at` | 责任人与时刻 |

> **`reason NOT NULL` 是数据库层能保证的 invariant**，应交给数据库（`01-postgresql` §8.1）。

---

## 12. Return & Risk Tables

### 12.1 `return_estimate` / `risk_estimate`

| 项 | 说明 |
|---|---|
| PK | `(estimation_run_id, share_class_id)` 或代理键 |
| **关键列** | `return_basis`、`forecast_horizon`、`lookback_window`、`method_id`、`method_version`、`parameter_version`、`status` |
| 数据量 | 每决策时点 × Universe 规模 |
| Partition | 按 `estimation_as_of_date` 年分区 |

#### 12.1.1 `return_basis` 是 `NOT NULL`

> **沿用 `07-return-risk/02` §5.5.1：** 不记录则下游无法判断是否需要还原。

### 12.2 `estimation_method` — Method Registry

| 项 | 说明 |
|---|---|
| **为什么存在** | **历史估计必须能查到当时方法的完整定义**（`07-return-risk/05` §2.1） |
| PK | `id BIGINT` |
| Business Key | `(method_id, version)` |
| 列 | `method_type`、`formula_ref`、`required_parameters`、`applicable_horizon`、`min_observation_count`、`status` |
| **UPDATE** | 定义不可变；变更产生新 `version` |
| Retention | **永久** —— 已 `DEPRECATED` / `RETIRED` 的方法定义仍须可查 |

#### 12.2.1 方法版本与参数版本分离

> **沿用 `07-return-risk/05` §3.3：** 参数不并入方法版本，否则每次调 `λ` 都产生一个公式相同的"新方法"。

```
estimation_method   : 公式变了 → 新 version
policy_version      : 参数取值变了 → 新 parameter_version（§8.4）
```

> **两者组合唯一确定一次估计** —— `estimation_run` 同时引用两者。

### 12.3 `estimation_run`

> 批次实体，承载幂等键 `(decision_at, strategy_version)` 与方法/参数版本。

---

## 13. Backtest Tables

### 13.1 `backtest` / `backtest_run` 分离

| 表 | 说明 |
|---|---|
| `backtest` | 配置（含 `backtest_mode`、IS/OOS 划分、九项版本引用） |
| **`backtest_run`** | **一次执行** —— 重跑产生新 Run，不覆盖 |

### 13.2 `backtest_period` 与 `backtest_nav` 分离

> **沿用 `03-erd` §12.2：决策时间线与估值时间线。**

| 表 | 频率 | 数据量 |
|---|---|---|
| `backtest_period` | 离散、不均等 | 数十~数百 / Run |
| **`backtest_nav`** | **逐交易日** | 数千 / Run |

### 13.3 `backtest_bias_check`

| 项 | 说明 |
|---|---|
| **为什么独立** | 它是 **Gate**，不是报告附录（`03-erd` §12.3） |
| 列 | 逐项检查的 `status`（含 **`NOT_VERIFIED`**）、违规明细、快照/重建统计、未建模成本清单 |

#### 13.3.1 `NOT_VERIFIED` 必须是独立枚举值

> **沿用 `08-backtest/06` §12.1、`10-api/05` §4.6.1：不得折叠进 `PASS`。**

### 13.4 分区策略

> **沿用 `01-postgresql` §12.5：按 `backtest_id` 分区是"按生命周期"而非"按体量"。**

```
删除某次回测 = DROP PARTITION
    → 避免大批量 DELETE 产生的膨胀与 vacuum 压力
```

`<TBD-DBD-7: 回测表的分区键（`backtest_id` HASH / LIST vs 时间），待回测频率与保留策略确认（= `01-postgresql` `TBD-PG-8`）>`

---

## 14. Audit / Version Tables

> 见 §8.3、§8.4。

---

## 15. Index Design

### 15.1 索引清单的组织原则

> **每个索引必须标注其服务的负载**（`01-postgresql` §11.1）。

| 负载 | 涉及表 | 索引 |
|---|---|---|
| **W1** 单基金单因子序列 | `factor_value` | PK |
| **W2** 单时点横截面 | `factor_value` | `(as_of_date, factor_id, share_class_id) INCLUDE (...)` |
| **W3** Peer Group 分位 | `factor_value`、`peer_group_member` | `(peer_group_id, as_of_date, factor_id)` |
| **W5** 决策快照写入 | `portfolio.*` | PK 为主；**写入路径应尽量少索引** |
| **W6** 历史决策重建 | 多表 | 各表 `decision_at` |
| **W7** 回测逐期 | 同 W2 | 同 W2 |
| **W8** 快照读写 | `*_snapshot` | `(strategy_id, decision_at)` |
| **PIT 点查** | 全部版本化表 | `(business_key, available_at, version DESC) INCLUDE (value)` |

### 15.2 W5 的索引应当克制 ⚠️

> **决策快照是写入路径，索引会放大写入成本。**

```
W5 = 单事务数千行的多表写入
    → 每个索引都增加写入时间
    → 而快照写入的读取需求很低（W6 是低频的历史重建）
```

**因此快照相关表只建必要的 PK 与 FK 索引**，不为"可能的查询"预建。

### 15.3 索引维护

| 事项 | 说明 |
|---|---|
| **大表建索引必须 `CONCURRENTLY`** | `01-postgresql` §16.5 |
| 分区表的索引 | 每个分区各自建；全局唯一约束须含分区键 |
| 定期检查未使用索引 | 通过 `pg_stat_user_indexes` |

---

## 16. Constraint Design

### 16.1 数据库层承担的 invariant

| 约束类型 | 典型应用 |
|---|---|
| `PRIMARY KEY` | 全部表 |
| `FOREIGN KEY` + `RESTRICT` | **快照引用、明细→主表** |
| `UNIQUE` | 业务键、时点键、Provider 键 |
| `NOT NULL` | 必填字段（含 `decision_review.reason`） |
| `CHECK` | 枚举域、`weight >= 0`、`valid_from < valid_to` |
| **`EXCLUDE`** | 任职区间不重叠 |

### 16.2 应用层承担的规则

| 规则 | 理由 |
|---|---|
| `Σ weight = 1` | 跨行；且形态随现金/冻结持仓变化 |
| Peer Group 内 MAR 一致 | 跨表跨行 |
| Eligibility Rules | 版本化的策略配置 |
| 优化可行性 | 需要求解 |

> **判据**：`CHECK` 只处理单行内可判定的不变式（`01-postgresql` §8.2）。

### 16.3 `ON DELETE` 策略汇总

| 关系 | 策略 | 理由 |
|---|---|---|
| **快照引用** | **`RESTRICT`** | 被引用则不可删 |
| 明细 → 主表 | `RESTRICT` | —— |
| 纯附属明细（`binding_constraint` → `optimization_result`） | `CASCADE` | 无独立意义 |
| **业务对象 → 历史数据** | **禁止级联** | 见 §16.4 |

### 16.4 历史数据的删除保护 ⚠️

> **沿用 `01-postgresql` §7.4：**

```
❌ 删除基金 → CASCADE 删除全部历史 NAV、Factor、Score
   → 历史回测与决策失去数据基础，且不可恢复

✅ 基金"删除"表达为 lifecycle_status = LIQUIDATED
```

**数据库层的落实**：`fund` / `fund_share_class` 表**不设 DELETE 权限**（仅 INSERT / UPDATE）。

---

## 17. Partition Design

### 17.1 分区表汇总

| 表 | 分区键 | 间隔 | 依据 |
|---|---|---|---|
| **`factor_value`** | `as_of_date` | **月** | 1.5 亿行 + W2 裁剪 |
| `fund_nav` | `effective_at` | 年 | 3,000 万行 |
| `fund_score` | `as_of_date` | 年 | 3,000 万行 |
| `fund_score_attribution` | `as_of_date` | **月** | 见 §10.2.1 |
| `benchmark_index_value` | `effective_at` | 年 | 百万级 |
| `peer_group_member` | `effective_at` | 年 | 快照 × 组规模 |
| `raw_payload` | 接收时间 | 月 | 归档便利 |
| `audit_log` | `created_at` | 月 | 长期保留 |
| `lineage_edge` | 时间 | 月 | 视粒度 |
| **`backtest_*`** | **`backtest_id`** | HASH/LIST | **生命周期隔离** |

### 17.2 不分区的表

| 表 | 理由 |
|---|---|
| `fund` / `fund_share_class` | 万级 |
| `portfolio` / `optimization_result` | 十万级 |
| Benchmark 定义三表 | 千级 |
| `risk_free_rate` | 小 |

> **沿用 `01-postgresql` §12.2：四条判据（数据量、时序性、生命周期、查询裁剪）同时满足才分区。**

### 17.3 分区预创建是运维要求

> **新分区必须提前创建**，否则写入会失败。属 `12-operations` 的定期任务。

---

## 18. Data Retention

### 18.1 保留策略的分层

| 类别 | 保留期 | 理由 |
|---|---|---|
| **业务历史数据**（NAV、Factor、Score、Decision） | **永久** | 可复现性与审计要求 |
| **已清盘基金的历史** | **永久** | **幸存者偏差的消除依赖它** |
| 审计日志 | 长期（合规决定） | `NFR-SEC-004` |
| **Raw Payload** | 见 §18.3 | |
| 回测结果 | 见 §18.4 | |
| 血缘 | 视粒度 | §8.2.1 |

### 18.2 业务历史数据永久保留的代价与必要性 ⚠️

```
factor_value 每年增长约 1,500 万行
    → 10 年后 1.5 亿行（当前估算已含 10 年）
    → 20 年后 3 亿行

但删除历史因子值意味着：
    → 该时段的历史决策不可重建
    → 该时段的回测不可复现
```

> **可复现性是 P0 质量属性**（`NFR-REPRO-001`），**保留成本远低于失去它的代价**。

### 18.3 Raw Payload 的保留期需要权衡

```
它的价值：Adapter 逻辑变更后可重新解析
它的代价：体量最大
```

| 方案 | 权衡 |
|---|---|
| 永久保留 | ✅ 任何时候可重解析<br/>❌ 体量持续增长 |
| **保留 N 年后归档到冷存储** | ✅ 平衡<br/>⚠️ 归档后重解析需先恢复 |
| 保留 N 年后删除 | ❌ **丧失重解析能力** |

> **已定案 · 2026-08-27**：`raw_payload` **在线保留 2 年，之后压缩归档**（Policy C · L4，同 `03-data/01-data-source` `DS-11`）。
>
> **分区策略配合**：已按接收时间月分区（§8.1），归档即整分区 detach 后转储，无需逐行删除。

### 18.4 回测结果的保留期

```
每次回测产生数千至数万行
    → 研究阶段可能每天多次
    → 但绝大多数是探索性的，无长期价值
```

**建议**：区分**探索性回测**（保留 N 个月）与**用于策略上线评估的回测**（永久保留）。后者由 `13-governance` 的策略审批流程标记。

> **已定案 · 2026-08-27**：回测结果**分级保留**（Policy C）：
>
> | 内容 | 保留期 |
> |---|---|
> | `backtest` 主记录 + `backtest_metric` + `backtest_report` | **10 年** |
> | `backtest_position` / `backtest_trade` 逐期明细 | **2 年**在线 + 归档 |
>
> **依据 —— 主记录与明细的用途不同**：主记录回答「这个策略当年测出来什么结果」，是长期的决策依据；逐期明细回答「第 37 期为什么这样调仓」，其查询集中在回测完成后的数月内。
>
> **10 年覆盖策略的完整生命周期** —— 一个策略从回测、上线到退役的跨度通常在这个量级。

---

## 19. Migration Strategy

> **沿用 `01-postgresql` §16。本节补充与表设计相关的要点。**

### 19.1 迁移脚本是 DDL 的权威来源

```
本文档定义【设计与决策】
迁移脚本承载【具体 DDL】
    → 两者不重复，避免发散
```

### 19.2 大表变更的操作清单

| 操作 | 做法 |
|---|---|
| 加列（有默认值） | 确认 PG 版本；或分步 |
| **建索引** | **`CONCURRENTLY`** |
| 加 `NOT NULL` | `CHECK ... NOT VALID` → `VALIDATE` |
| 改类型 | 新列 + 回填 + 切换 |
| **加分区** | 提前创建；已有大表转分区表需重建 |

### 19.3 分区表的引入时机 ⚠️

```
若初期不分区，后期转分区表需要【重建整表】
    → 1.5 亿行的重建代价很高

因此 factor_value 等确定要分区的表，【应在首次建表时就分区】
```

> **这是一个不可推迟的决策** —— 与"先简单实现，需要时再优化"的常规做法相反。

---

## 20. Query Pattern & Performance

### 20.1 典型查询与其表现

| 模式 | 表 | 预期 |
|---|---|---|
| **Point Lookup** | `fund_share_class` | 索引点查，快 |
| **PIT Query** | 版本化表 | 索引覆盖，快 |
| **Range Query**（W1） | `factor_value` | 跨分区，中等 |
| **Cross-section**（W2） | `factor_value` | **风险点** |
| **Aggregation**（W3） | `factor_value` + `peer_group_member` | 中等 |
| **Batch Insert**（W4） | `factor_value` | 关注索引写放大 |
| **Multi-table Transaction**（W5） | `portfolio.*` | **不可拆分** |
| **Backtest Loop**（W7） | 同 W2 × 期数 | **总耗时主要来源** |

### 20.2 性能门槛由架构层定义

> **沿用 `06-technology-stack` §4.6.2 的验证门槛。本域不自行设定 SLA。**

**架构层已定案的验收框架**（v1.8 同步，见 `TBD-resolution.md` Policy ⑦）：

```
PostgreSQL Architecture ACCEPTED
    IF  W2 P95   < X          ← 数值待压测（OPEN-14）
    AND W5 P95   < Y
    AND W7 total < Z
    AND W7 随「基金数 × 期数」近似线性
    AND CPU    < 70%          ← 已定案
    AND Memory < 75%          ← 已定案
```

| 已定案 | 待压测 |
|---|---|
| 指标口径（W2/W5 用 P95、W7 用总耗时） | 三个门槛值 X / Y / Z |
| 资源余量门槛（CPU 70% / Memory 75%） | 生产并发量预估（`OPEN-15`） |
| 未达标的升级路径（优化 → 列存旁路） | 各优化档位的实际效果 |

> **本域的设计须为这个框架服务，而不是等它** —— 分区策略（§9.6）、索引设计（§9.5）、W7 的读取优化（§20.3）都是「优化 → 列存旁路」路径中第①步的具体内容。压测的作用是判定第①步是否够用，不是决定要不要做第①步。

### 20.3 W7 的特殊性 ⚠️

```
回测 = W2 重复数十至数百次
    → 单次 W2 若需 2 秒，200 期回测仅数据读取就需 400 秒
    → 且回测可能并发多个
```

**优化方向**（不改变一致性）：

| 手段 | 说明 |
|---|---|
| **只读副本** | 回测走从库（`01-postgresql` §18.3） |
| 单次回测内的结果缓存 | 同一 Run 内的重复读取 |
| 批量预取 | 一次取多期而非逐期 |

---

## 21. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **本文档不是数据字典**，DDL 由迁移脚本承载 | 避免两处维护发散 |
| D-2 | **禁止 UPDATE 的表不设 `updated_at`** | 设它会误导可更新 |
| D-3 | 下游外键指向 `fund_share_class` 而非 `fund` | 计算粒度是 Share Class |
| D-4 | `provider_fund_identity` 唯一键含 `valid_from` | 映射关系会变化 |
| D-5 | **`investment_eligibility` 持久化而非每次重算** | 回测需查历史，且重算规则可能已变 |
| D-6 | `fund_nav` 同时保留 raw 与 adjusted | 复权方向仍是上游 TBD |
| D-7 | **PIT 索引用 `INCLUDE` 覆盖** | 避免回表 |
| D-8 | **血缘采用 Decision Level** | Record Level 数据量爆炸 |
| D-9 | **`audit_log` 不建 FK 且仅 INSERT** | 被审计对象删除后仍须存在 |
| D-10 | **统一 `policy_version` 表** | 使全部 Policy 版本可查，不论是否在九项内 |
| D-11 | **`factor_value` 按 `as_of_date` 月分区** | 优化 W2（选型风险点） |
| D-12 | **条件性唯一约束需专门方案** | NULL 不参与唯一性比较 |
| D-13 | **`peer_group_member` 完整留存成员** | 规则加输入不等于结果可还原 |
| D-14 | **`fund_universe_member` 含 `REJECTED`** | 否则无法发现错误排除 |
| D-15 | `selection_condition_result` 可只存未通过项 | 数据量降一个数量级 |
| D-16 | **三态三表** | 三者同时存在 |
| D-17 | **持仓以份额为主** | 权重无法反推交易数量 |
| D-18 | **矩阵用 JSONB + 成员用有序明细表** | 顺序可校验且数值可整体存取 |
| D-19 | `optimization_result` 含 `INFEASIBLE` 情形 | 无决策但仍需留存 |
| D-20 | **`decision_review.reason NOT NULL`** | 数据库能保证的 invariant 交给数据库 |
| D-21 | `backtest_period` 与 `backtest_nav` 分离 | 两条时间线 |
| D-22 | **`backtest_bias_check` 独立成表** | 它是 Gate 不是报告附录 |
| D-23 | 回测表按 `backtest_id` 分区 | 生命周期隔离，删除用 DROP PARTITION |
| D-24 | **W5 写入路径的索引应当克制** | 索引放大写入成本，而读取需求低 |
| D-25 | **`fund` 表不设 DELETE 权限** | 从数据库层阻断历史数据的级联删除 |
| D-26 | **业务历史数据永久保留** | 可复现性是 P0，保留成本远低于失去它 |
| D-27 | **确定要分区的表首次建表就分区** | 后期转换需重建整表 |

---

## 22. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | 表设计必须与 `03-erd` 一致（六条一致性规则） | `03-erd` §16 |
| C-2 | **决策快照必须单事务写入，不得拆分** | 上游 §8.4 |
| C-3 | 金融数值一律 `NUMERIC` | `01-postgresql` §5.1 |
| C-4 | **需保留历史的表禁止 UPDATE** | `01-postgresql` §10.7 |
| C-5 | **禁止级联删除历史数据** | `01-postgresql` §7.4 |
| C-6 | 每个 schema 只有一个 Write Owner | `03-data-architecture` §4.2 |
| C-7 | 索引必须有访问模式依据 | `01-postgresql` §11.1 |
| C-8 | 分区必须满足四条判据 | `01-postgresql` §12.2 |
| C-9 | 本域**不重新定义**业务规则 | 提示词 §1 |
| C-10 | 已清盘基金的历史必须永久保留 | `08-backtest/04` §5.1 |

---

## 23. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| ~~DBD-1~~ | ~~血缘的具体粒度与保留期~~ —— **已定案**：见 Policy C 保留期限体系 | — | ✅ 2026-08-27 |
| ~~DBD-2~~ | ~~条件性唯一约束的方案选择~~ —— **已定案**：条件性唯一约束采用**方案 A：部分唯一索引**（`WHERE evaluation_policy_version IS NULL` 与其反面各建一个） | — | ✅ 2026-08-27 |
| DBD-3 | **`fund_score_attribution` 的存储策略** | 可能超过 `factor_value` 的数据量 | 技术 + 投研 |
| ~~DBD-4~~ | ~~`selection_condition_result` 是否只存未通过项~~ —— **已定案**：`selection_condition_result` **存全部条件**，不只存未通过项 | — | ✅ 2026-08-27 |
| ~~DBD-5~~ | ~~是否建 `position_lot` 表~~ —— **已定案**：**建 `position_lot` 表** | — | ✅ 2026-08-27 |
| ~~DBD-6~~ | ~~`target_weights` 的存储形态~~ —— **已定案**：`target_weights` 采用**行式存储**（每基金一行），不用 JSONB | — | ✅ 2026-08-27 |
| DBD-7 | 回测表的分区键 | 生命周期管理 | 技术 + 运维 |
| ~~DBD-8~~ | ~~Raw Payload 的保留期与归档方案~~ —— **已定案**：见 Policy C 保留期限体系 | — | ✅ 2026-08-27 |
| ~~DBD-9~~ | ~~回测结果的分级保留策略~~ —— **已定案**：见 Policy C 保留期限体系 | — | ✅ 2026-08-27 |

> **本域的关键前提**：`TBD-TECH-7`（各负载的性能门槛）与 `TBD-PG-7`（W2 优化方案）—— **它们决定本设计是否成立**。

---

## 24. Related Documents

| 关系 | 文档 |
|---|---|
| **本域上游** | `11-database/01-postgresql.md` v1.0（平台规范）、`03-erd.md` v1.0（实体与关系） |
| **架构** | `02-architecture/06-technology-stack.md` v1.2 §4.6（Workload Matrix 与验证门槛）、`03-data-architecture.md` v1.1、`01-system-architecture.md` v2.3 §10 |
| **业务语义来源** | `03-data`、`04-factor`、`05-fund-evaluation`、`06-portfolio`、`07-return-risk`、`08-backtest` |
| **相关** | `10-api`（查询模式来源）、`12-operations`（备份、分区维护、监控） |

---

## 25. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.9** | 2026-08-27 | **第二批定案（7 项）**。`DBD-2` 条件性唯一约束采用**部分唯一索引**（PostgreSQL 原生，触发器方案无法被查询计划器利用、生成列方案的哨兵值会泄漏到查询条件）；`DBD-5` **建 `position_lot` 表**（`TC-3` 的赎回费阶梯依赖持有批次）；`DBD-6` `target_weights` **行式存储不用 JSONB**（「按基金查历史权重」需索引到基金维度）；`DBD-4` `selection_condition_result` 存全部条件并带 `condition_version`；`DBD-1`/`DBD-8`/`DBD-9` 保留期见 Policy C，回测主记录 10 年、逐期明细 2 年 + 归档。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.8** | 2026-08-27 | **Policy ⑦ 同步**。§20.2 补架构层已定案的完整验收条件表达式与「已定案 vs 待压测」对照；指出本域的分区、索引、W7 读取优化都是升级路径中第①步的具体内容，**须为框架服务而非等待压测结果**。详见 `TBD-resolution.md` Policy ⑦ | `02-architecture/06-technology-stack` v1.3 |
| **v1.7** | 2026-08-27 | **Policy ⑥ 落库**。`factor` schema 新增表 **`factor_effectiveness`**（§9.4）—— Business Key 含 `sample_split` 与 `validation_policy_version`；§9.4.1 说明阈值版本进唯一键使阈值调整**产生新行而非覆盖**（否则历史「当时被判无效」的记录消失，依赖它的历史 Score 无从解释）；§9.4.2 说明 IS 与 OOS 必须是不同的行（合并会让「只做了 IS」与「两者都做了」结构上不可区分）。原 §9.4/§9.5 顺移为 §9.5/§9.6。详见 `TBD-resolution.md` Policy ⑥ | `11-database/03-erd` v1.1、`04-factor/07-factor-validation` v1.2 |
| **v1.6** | 2026-08-27 | **Policy ⑤ 落库**。新增 §10.1.2 —— `fund_ranking` / `fund_tier` 补 `ranking_status` / `classification_status`（枚举 `NORMAL`/`INSUFFICIENT_SAMPLE`）与 `n_effective`，附联动 `CHECK`；明确 `INSUFFICIENT_SAMPLE` 的行**仍落库**（否则历史查询无法区分「当时样本不足」与「当时根本没算」），`n_effective` 两种状态下都必填；阈值本身属 `governance.policy_version`，表里只存判定结果。详见 `TBD-resolution.md` Policy ⑤ | `05-fund-evaluation/03` v1.1、`05-fund-evaluation/04` v1.1 |
| **v1.5** | 2026-08-27 | **Policy ① 落库**。①§7.3 `risk_free_rate` 补 `rate_source_quality`（枚举 `EXACT`/`INTERPOLATED`），新增 §7.3.1 —— 插值点与观测点**同表存储**，事后补入真实观测**产生新 `version` 而不覆盖**（覆盖会让历史因子在补数后悄然改变）。②新增 §9.2.1 —— `risk_free_rate_ref` 的四个必备字段，并厘清它是**溯源而非标识**（与 `evaluation_policy_version` 相反）；`version` 记解析基准而非逐期版本列表。详见 `TBD-resolution.md` Policy ① | `03-data/02-data-domain-model` v1.5、`04-factor/04-factor-calculation` v1.2 |
| **v1.4** | 2026-08-27 | **Policy ⑩ 落库**。新增 §6.5 `fund_fee` —— 补 `included_in_nav` / `included_in_return`（**三值枚举 `inclusion_enum`**）、`included_in_backtest`（推导列，仍落库）、`inclusion_source` 四列；§6.5.1 说明为何用三值枚举而非可空布尔（`NULL` 会让「确认无从得知」与「还没人填」不可区分）；§6.5.2 说明推导列落库的理由（历史回测须能复现当时的推导规则）；§6.5.3 阶梯费率存独立子表。详见 `TBD-resolution.md` Policy ⑩ | `03-data/02-data-domain-model` v1.4 |
| **v1.3** | 2026-08-27 | **`TBD-DN-3` 关闭后的同步**。§7.1.1 改写 —— 复权方向定为后复权；明确 `nav_adjusted` **可空是有意的**（承载 `UNAVAILABLE` 语义），不得设默认值或回填 `nav_raw`；补四列的联动 `CHECK` 约束；作废「若选前复权需全量重算」的条件表述。详见 `TBD-resolution.md` Policy ③ | `03-data/05-data-normalization` v1.2 |
| **v1.2** | 2026-08-27 | **§4.4 / §4.5 标准列扩充**。版本化表与区间型表新增四列 —— `availability_quality`（枚举，NOT NULL）与三个来源依据字段 `published_at` / `provider_available_at`（可空）/ `ingested_at`（NOT NULL）；新增 §4.4.1 给出**可空性理由**、把三级优先级写成 `CHECK` 一致性约束、以及四时间字段的时序 `CHECK`。详见 `TBD-resolution.md` Policy ④ | `03-data/01-data-source` v2.3 |
| **v1.1** | 2026-08-27 | **§8.4.1 改写**。`governance.policy_version` 表由「兜底可追溯性」升为**决策快照的正式外键来源**，快照 `policy_version_ref` 加非空约束；`policy_type` 由各域自行登记的 11 种**收敛为 5 种**（evaluation / ranking / classification / estimation / validation），`scoring` / `portfolio_rule` / `rebalance_rule` / `transaction_cost` 四类剔除 —— 它们属 Strategy Version 而非 Policy。详见 `TBD-resolution.md` Policy ⑧ | `02-architecture/01-system-architecture` v2.4 |
| v1.0 | 2026-08-27 | 初始版本。**§1.2 本文档不是数据字典**，DDL 由迁移脚本承载；**§4.3 禁止 UPDATE 的表不设 `updated_at`**（有意的设计信号）；**§6.4.1 `investment_eligibility` 须持久化**；§7.1.1 复权方向 TBD 下的表结构安排；**§8.2.1 血缘粒度直接决定数据量**、**§8.4.1 统一 `policy_version` 表解决跨域版本可追溯问题**；**§9.3 依赖 MAR 的因子使唯一约束成为条件性的**及三个候选方案；**§9.4.1 W2 的索引可能仍不够**；**§10.2.1 归因表数据量可能超过 `factor_value`**、**§10.3.1 存 `REJECTED` 成员使数据量翻数倍但必需**；**§11.3.1 矩阵 JSONB + 成员明细表的组合理由**；**§15.2 W5 写入路径的索引应当克制**；**§16.4 从权限层阻断历史数据级联删除**；**§18.2 业务历史永久保留的代价与必要性**、§18.3 Raw Payload 保留期的权衡；**§19.3 分区是不可推迟的决策**；§20.3 W7 是回测总耗时的主要来源；**§12.2 补充 `estimation_method`（Method Registry）表**，并说明方法版本与参数版本分离 | `11-database/01-postgresql.md` v1.0、`03-erd.md` v1.0、`02-architecture/06-technology-stack.md` v1.2 |