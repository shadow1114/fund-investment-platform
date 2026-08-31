# PostgreSQL 平台规范 · PostgreSQL Platform Standards

> 上游文档：docs/01-product/01-product-overview.md（v2.5）｜本文定位：支撑层 · 数据持久化
> 架构依赖：docs/02-architecture/06-technology-stack.md（v1.2）§4、03-data-architecture.md（v1.1）
> 数据语义来源：docs/03-data/（v1.0–v2.2，全 7 份）
>
> **文档版本**：v1.2 ｜ **产品阶段**：第一阶段

---

## 1. Purpose & Scope

### 1.1 本文档回答什么

> **系统如何使用 PostgreSQL？**

### 1.2 选型结论沿用架构层，本域不重新论证 ⚠️

> **存储产品选型属 `02-architecture/06-technology-stack` §4，本域承接结论并定义使用规范。**

```
第一阶段：单一 PostgreSQL，不引入 ClickHouse
```

**三条依据**（`06-technology-stack` §4.2，本域不重述论证）：

| # | 依据 |
|---|---|
| 1 | 数据规模远未进入列存收益区（十亿行以内、几十 GB） |
| 2 | **双库会破坏"决策快照单一事务"这条不可权衡的约束** |
| 3 | 运维成本 |

> **第 2 条是决定性的** —— 它不是性能权衡，而是质量属性约束。

### 1.3 本域已删除 `02-clickhouse.md`

> 该文件为 0 字节空文件、全库零引用，且与已定案的选型矛盾。**若未来触发 §4.4 的重评估条件而引入列存，其引入方式应为旁路只读副本，而非把快照拆到两个库** —— 一致性约束在任何阶段都不可放弃。

### 1.4 本文档不回答什么

| 不回答 | 归属 |
|---|---|
| 实体与关系 | `03-erd` |
| 具体表结构与字段 | `04-database-design` |
| 业务实体定义 | `03-data/02-data-domain-model` |
| PIT 与版本的**业务规则** | `03-data/04-data-versioning` |
| 数据口径、校验、血缘 | `03-data/05`、`06`、`07` |
| 存储选型论证 | `02-architecture/06-technology-stack` §4 |
| 备份策略的运维执行 | `12-operations` |

---

## 2. PostgreSQL Role in System Architecture

### 2.1 位置

```
Domain Service（data / factor / fund / portfolio / backtest）
        ↓  经 PIT-aware Data Access Interface
   PostgreSQL（唯一持久化存储）
```

### 2.2 五个 Domain Service 共享同一 PostgreSQL 实例

> **沿用 `02-architecture/01-system-architecture` §3：Domain Service 是逻辑边界，不是数据库边界。**

```
逻辑隔离通过 schema 实现（§4）
物理上是同一个数据库实例
    → 决策快照的单事务写入天然成立
```

### 2.3 数据访问必须经 PIT-aware 接口 ⚠️

> **沿用架构 §7.4、§11.7、`08-backtest/03` §13.4：**

```
❌ 领域逻辑直接写 SQL 查表
   → PIT 过滤靠自觉，任何一处遗漏就形成前视，且遗漏不可发现

✅ 统一经 PIT-aware Data Access Interface
   → 领域逻辑拿到的本来就只有合格数据
```

**数据库层的配套要求**：三时点字段（§10）必须存在于全部受 PIT 约束的表上，使该接口能统一实施过滤。

---

## 3. Database Responsibilities

### 3.1 PostgreSQL 保存什么

> **承载全部持久化数据**（`06-technology-stack` §4.1）。

| 类别 | 内容 | 数据层 |
|---|---|---|
| **Raw** | Provider 原始响应 payload | Raw |
| **Canonical Raw** | 完成字段映射、未做口径统一 | Canonical |
| **Normalized** | 基金主数据、净值、分类、Benchmark、可投资性、`R_f` | Normalized |
| **Analytical** | Factor、Peer Group、Score、Universe、Return Estimate、Risk / Correlation | Analytical |
| **Decision** | Portfolio 三态、Optimization Result、Investment Decision、Rebalancing | Decision |
| **Backtest / Audit** | 回测配置、逐期快照、结果、报告、审计日志 | Backtest / Audit |
| **Metadata** | 数据版本、Policy 版本、血缘、质量标记 | 贯穿 |

### 3.2 PostgreSQL 不保存什么

| 不保存 | 去向 |
|---|---|
| **实盘订单与成交明细** | 外部执行系统（上游 §6 Out of Scope） |
| 大体积二进制附件（如报告 PDF） | 见 §3.4 |
| 应用日志与指标 | `12-operations` 的可观测体系 |
| 缓存 | 见 §3.3 |

### 3.3 第一阶段不引入独立缓存层

> **不是因为不需要，而是因为引入它会带来一个新的一致性问题。**

```
缓存 Factor / Score 等 PIT 敏感数据
    → 缓存键必须包含 (decision_at, 全部相关 version)
    → 否则同一 fund_id 的缓存会跨时点串用
    → 而这类错误【在结果中不可见】
```

**第一阶段依靠 PostgreSQL 自身的 shared_buffers 与查询优化**；若 §4.6 的负载验证不达标，优先考虑物化视图与只读副本，而非应用层缓存。

`<TBD-PG-1: 是否需要独立缓存层及其 PIT 安全的键设计，待 W2/W7 负载验证后评估>`

### 3.4 报告文件的存储位置待定

> `08-backtest/06` 的报告可能需要导出为文件（`10-api` `TBD-BA-2`）。

| 方案 | 说明 |
|---|---|
| 结构化数据入库 + 文件按需生成 | **推荐** —— 数据是权威，文件是派生 |
| 文件入库（bytea / large object） | 数据库膨胀 |
| 文件入对象存储 | 引入新组件 |

`<TBD-PG-2: 报告文件的存储方案，待产品确认导出需求后决定>`

---

## 4. Schema Organization

### 4.1 八个 schema

> **按数据域组织，与 `02-architecture/03-data-architecture` §3.1 的十五个数据域对应。**

| Schema | Purpose | Write Owner | 主要实体 |
|---|---|---|---|
| **`raw`** | Provider 原始 payload 与 Canonical Raw | `data-service` | 原始响应、解析中间态 |
| **`fund`** | 基金主数据与生命周期 | `data-service` | Fund、Share Class、Manager、Classification、Fee、Eligibility |
| **`market`** | 市场与基准数据 | `data-service` | NAV、Benchmark 四层、`R_f` |
| **`factor`** | 因子定义与结果 | `factor-service` | Factor Definition、Factor Result |
| **`evaluation`** | 评价、评分、排名、分层、候选池 | `fund-service` | Peer Group、Evaluation、Score、Ranking、Tier、Universe |
| **`portfolio`** | 组合、估计、优化、约束、再平衡 | `portfolio-service` | Portfolio 三态、Return/Risk Estimate、Optimization、Decision、Rebalance |
| **`backtest`** | 回测配置、执行与结果 | `backtest-service` | Backtest、Run、逐期快照、成本、报告 |
| **`governance`** | 版本、血缘、质量、审计 | 分域写入（见 §4.3） | Policy 版本、Lineage、Quality、Audit Log |

### 4.2 Schema 边界即 Write Ownership 边界 ⚠️

> **沿用 `03-data-architecture` §4.2：写入权唯一、读取权开放。**

```
每个 schema 只有一个 Write Owner
    → 跨 schema 写入必须被拒绝（数据库层通过权限实施）
    → 跨 schema 读取开放
```

**数据库层的落实**：为每个 service 建立独立的数据库角色，仅授予其 Owner schema 的写权限 + 全部 schema 的读权限。

### 4.3 `governance` 是唯一多方写入的 schema

> **它是横切关注点的落点** —— 各 service 写入各自的血缘、质量标记与审计记录。

**因此它需要更细的权限粒度**：按表授权，而非按 schema 授权。

### 4.4 为什么不按 service 分 schema

> **需要澄清一处设计选择。**

```
按 service 分 → factor_service、fund_service…
    ✗ service 拆分可能变化，schema 名会失真
    ✗ 一个 service 可能写多个数据域

按数据域分 → factor、evaluation…
    ✓ 数据域来自业务定义，比服务拆分稳定
    ✓ 与 03-data-architecture §3.1 直接对应
```

> **Ownership 通过权限表达，不通过命名表达。**

### 4.5 `raw` schema 必须与其他隔离

> **沿用 `03-data-architecture` §2.3：Raw 层必须保留。**

| 特征 | 说明 |
|---|---|
| **只追加，不修改** | Provider 原始响应不可变 |
| **体量最大** | 但查询频率最低 |
| **保留策略不同** | 见 `04-database-design` §18 |

> 它与分析型数据的访问模式完全不同，**独立 schema 便于分别配置备份与保留策略**。

---

## 5. Data Type Standards

### 5.1 金融数值一律用 `NUMERIC`，禁止浮点 ⚠️

> **这是本文档最重要的一条约定。**

```
❌ FLOAT / DOUBLE PRECISION 用于金额、净值、权重、收益率
   → 二进制浮点无法精确表示十进制小数
   → 累加 1000 笔交易金额会产生可观的误差
   → 且误差不可预测、不可复现

✅ NUMERIC(p, s)
```

### 5.2 各类数值的精度约定

| 类别 | 类型 | 精度 | 说明 |
|---|---|---|---|
| **金额（Monetary）** | `NUMERIC(20, 4)` | 4 位小数 | 须配 `currency` 列 |
| **净值（NAV）** | `NUMERIC(18, 6)` | 6 位小数 | 基金净值常见 4 位，留余量 |
| **份额（Quantity）** | `NUMERIC(24, 8)` | 8 位小数 | 份额可能极小 |
| **权重（Weight）** | `NUMERIC(12, 8)` | 8 位小数 | 小数形式，`0.15` 表示 15% |
| **收益率（Return）** | `NUMERIC(12, 8)` | 8 位小数 | 小数形式 |
| **比率（Ratio）** | `NUMERIC(12, 6)` | 6 位小数 | Sharpe 等 |
| **波动率（Volatility）** | `NUMERIC(12, 8)` | 8 位小数 | 小数形式 |
| **百分比** | 同"收益率" | —— | **不单独设类型**，见 §5.3 |
| **利率（`R_f`）** | `NUMERIC(12, 8)` | 8 位小数 | 小数形式 |

> **已定案 · 2026-08-27**：见 `TBD-resolution-2.md` Policy A §A.2。
>
> | 对象 | 类型 |
> |---|---|
> | 金额 | `NUMERIC(20,4)` |
> | 净值 | `NUMERIC(18,8)` |
> | 权重 / 比率 / 利率 | `NUMERIC(12,8)` |
> | 因子值 | `NUMERIC(18,8)` |
>
> **净值用 8 位小数的理由**：披露值为 4 位，但**后复权净值是累乘结果**，复权因子的舍入会逐期累积。8 位为累乘留出余量。
>
> **容差与精度是两件事**：精度决定「能存多细」，容差决定「差多少算不一致」。存储精度不足会让本可复现的结果因截断而超差。

### 5.3 百分比统一存小数，与 API 一致

> **沿用 `10-api/01-api-overview` §12.1：`0.1523` 表示 15.23%。**

```
数据库存 0.1523
API   返回 0.1523
展示层负责 × 100
```

> **不得在数据库存 15.23 而 API 存 0.1523** —— 转换发生在哪一层必须全平台统一，否则会产生 100 倍误差。

### 5.4 时间类型

| 用途 | 类型 | 说明 |
|---|---|---|
| **业务日期**（`effective_at`、`decision_at`、`as_of_date`） | `DATE` | 与交易日对齐 |
| **可得时刻**（`available_at`） | **`TIMESTAMPTZ`** | 见 §5.5 |
| **运维时刻**（`created_at`、`updated_at`） | `TIMESTAMPTZ` | 物理时刻 |
| 有效区间（`valid_from` / `valid_to`） | `DATE` 或 `TIMESTAMPTZ` | 按实体粒度而定 |

### 5.5 `available_at` 用 `TIMESTAMPTZ` 而非 `DATE` ⚠️

> **理由与 `10-api` §10.3 一致，但数据库层必须先做选择。**

```
若上游 TBD-17 定为"以公告时间为准"
    → 同一天内的先后有意义 → 必须 TIMESTAMPTZ

若定为"以落库日期为准"
    → DATE 足够
```

**本域按 `TIMESTAMPTZ` 落库**：它能表达 `DATE` 的全部信息，反之不能。**选窄了将来无法扩展，选宽了只是略占空间。**

### 5.6 时区一律 UTC 存储

| 规则 | 说明 |
|---|---|
| **`TIMESTAMPTZ` 内部以 UTC 存储** | PostgreSQL 的原生行为 |
| 业务时区转换在应用层 | 数据库不感知业务时区 |
| **`DATE` 类型不带时区** | 它是业务日期，不是时刻 |

> **`DATE` 与 `TIMESTAMPTZ` 混用是一类隐蔽错误** —— 把业务日期存成 `TIMESTAMPTZ` 会引入时区转换，导致跨时区查询时日期偏移一天。

### 5.7 枚举用 `VARCHAR` + `CHECK`，不用原生 `ENUM`

| 方案 | 权衡 |
|---|---|
| **`VARCHAR` + `CHECK`（推荐）** | 新增枚举值只需改约束；**迁移简单** |
| 原生 `ENUM` 类型 | 类型安全，但**新增值需 `ALTER TYPE`，删除值几乎不可能** |

> **业务枚举会新增**（如 `Investment Eligibility` 未来可能加档位）。原生 `ENUM` 的演进成本在金融系统中不划算。

**约定**：枚举值一律 `UPPER_SNAKE_CASE`，与 `10-api` §4.2 一致。

### 5.8 布尔字段必须 `NOT NULL DEFAULT`

> **三态布尔（true / false / null）是错误来源。** 若确需表达"未知"，应使用独立的状态枚举而非可空布尔。

### 5.9 JSONB 的适用边界

见 §13。

---

## 6. Primary Key Strategy

### 6.1 内部主键与外部标识必须分离 ⚠️

> **这是本文档第二重要的约定。**

```
Internal Fund ID  ≠  Provider Fund ID
```

| | Internal ID | Provider ID |
|---|---|---|
| 归属 | 平台 | 数据供应商 |
| 稳定性 | **平台保证不变** | 供应商可能变更 |
| 唯一性 | 平台内唯一 | **仅在该 Provider 内唯一** |
| 作为 PK | ✅ | ❌ |

**Provider ID 必须通过独立的身份映射实体管理**（`03-erd` §14），**不得直接作为 Fund 表的主键或唯一标识**。

### 6.2 为什么不能用 Provider ID 作 PK

| # | 理由 |
|---|---|
| 1 | **多 Provider 场景下会冲突** —— 同一基金在不同 Provider 有不同 ID |
| 2 | **Provider 可能变更 ID** —— 主键变更会级联影响全部外键 |
| 3 | **Provider 可能被替换** —— 换供应商时全库主键失效 |
| 4 | 平台可能覆盖 Provider 未收录的基金 |

### 6.3 主键类型选择

| 类型 | 适用 | 理由 |
|---|---|---|
| **`BIGINT` + 序列（推荐）** | 大多数实体 | 索引紧凑、连续性好、B-tree 分裂少 |
| `UUID` | 需跨系统生成 ID 的场景 | **随机 UUID 会导致索引碎片**，若采用须用时间有序变体 |
| **复合主键** | 时序类明细表 | 见 §6.4 |

> **已定案 · 2026-08-27**：主键采用 **`BIGINT` 序列**，不用 UUID。
>
> **依据**：
>
> | 维度 | `BIGINT` 序列 | UUID |
> |---|---|---|
> | 部署形态 | 本系统为**单写入点**（`05-deployment-architecture`），序列不冲突 | 解决的是多主写入问题 —— **本系统没有这个问题** |
> | 索引 | 单调递增，B-tree 顺序插入 | 随机分布，**写放大显著**（尤其 `factor_value` 这类千万级表） |
> | 存储 | 8 字节 | 16 字节，且每个索引都要多存一倍 |
>
> **若将来引入多写入点**，可改用 `BIGINT` + 节点前缀（雪花式）而非 UUID —— 那样既避免冲突又保持单调性。

### 6.4 时序明细表用复合主键

> **`fund_nav`、`factor_value` 等时序表的天然唯一性来自业务键组合。**

```
fund_nav      : (share_class_id, effective_at, version)
factor_value  : (share_class_id, factor_id, window, as_of_date, version)
```

| 权衡 | 说明 |
|---|---|
| ✅ 无需额外代理键，索引即主键 | 分区表下尤其有利 |
| ⚠️ 主键较宽，外键引用成本高 | 但这类表**通常不被外键引用** |

### 6.5 业务唯一键与技术主键并存

> **两者是不同的东西**（提示词 §11）：

| 类型 | 例 |
|---|---|
| **Technical PK** | `fund.id BIGINT` |
| **Business Unique Key** | `fund.fund_code`（平台内业务编码） |
| **Provider Unique Key** | `(provider_id, provider_fund_id)` |
| **Temporal Unique Key** | `(share_class_id, effective_at, version)` |

---

## 7. Foreign Key Strategy

### 7.1 同 schema 内的关系必须建 FK

> 数据库能保证的完整性应交给数据库（提示词 §10）。

### 7.2 跨 schema 的关系分两类

| 类型 | 是否建 FK | 例 |
|---|---|---|
| **指向稳定主数据** | ✅ **建 FK** | `factor.factor_value.share_class_id` → `fund.fund_share_class.id` |
| **指向分析结果快照** | ⚠️ **见 §7.3** | `portfolio.optimization.universe_id` → `evaluation.fund_universe.id` |

### 7.3 快照引用建 FK，但删除策略必须是 `RESTRICT` ⚠️

> **沿用架构 §10：决策快照引用上游快照 ID 而非复制内容。**

```
Decision Snapshot → Universe Snapshot → Peer Group Snapshot

若 Universe 快照被删除
    → 历史决策的引用悬空
    → 该次决策不可重建
```

**因此**：

| 关系 | ON DELETE |
|---|---|
| 快照引用 | **`RESTRICT`** —— 被引用则不可删 |
| 明细 → 主表（如 `factor_value` → `factor_definition`） | **`RESTRICT`** |
| 纯附属明细（如 `optimization_binding_constraint` → `optimization_result`） | `CASCADE` 可接受 |

### 7.4 金融历史数据禁止级联删除 ⚠️

> **不得因业务对象删除而级联删除历史记录。**

```
❌ 删除某只基金 → CASCADE 删除其全部历史净值、因子、评分
   → 历史回测与历史决策失去数据基础
   → 且这类删除【不可恢复】

✅ 基金"删除"应表达为生命周期状态变更（LIQUIDATED），历史数据完整保留
```

**这与幸存者偏差直接相关**（`08-backtest/04` §5.1）：若数据层不保留已清盘基金的历史，该偏差在平台层无法修正。

### 7.5 逻辑外键的使用边界

> **仅在分区表跨分区引用等 PostgreSQL 限制场景下允许**，且必须：

| 要求 | 说明 |
|---|---|
| 在文档中显式标注 | `04-database-design` 的表定义中注明 |
| 由应用层保证完整性 | 并有对应的一致性巡检 |

---

## 8. Constraint Strategy

### 8.1 可由数据库保证的 invariant 优先放进数据库

| 约束 | 用途 |
|---|---|
| `PRIMARY KEY` | 实体唯一性 |
| `FOREIGN KEY` | 引用完整性 |
| **`UNIQUE`** | 业务唯一键、时点唯一键 |
| `NOT NULL` | 必填字段 |
| **`CHECK`** | 取值域、简单不变式 |
| `EXCLUDE` | 见 §8.4 |

### 8.2 `CHECK` 的适用边界 ⚠️

> **不要把复杂业务规则塞进 `CHECK`。**

| 适合 `CHECK` | 不适合 |
|---|---|
| 枚举取值域 | **权重之和为 1** —— 跨行约束 |
| `weight >= 0`（不做空） | **Peer Group 内 MAR 一致** —— 跨表跨行 |
| `max_drawdown >= 0 AND max_drawdown < 1` | **Eligibility Rules** —— 版本化的策略配置 |
| `valid_from < valid_to` | **优化可行性** |

**判据**：`CHECK` 只处理**单行内可判定**的不变式。跨行、跨表、随版本变化的规则属应用层。

### 8.3 权重之和的约束放在应用层

```
Σ weight = 1 是跨行约束
    → 数据库层可用触发器，但触发器难以调试且影响批量写入性能
    → 且该约束在含现金/冻结持仓时形态不同（06-portfolio/01 §10.2）
```

**处理**：应用层校验 + 定期一致性巡检，不用触发器。

### 8.4 `EXCLUDE` 用于时段不重叠

> **适用于有效期区间不得重叠的实体。**

```
fund_manager_assignment 中同一 (share_class_id, manager_id) 的任职区间不应重叠
    → EXCLUDE USING gist (share_class_id WITH =, manager_id WITH =, daterange(valid_from, valid_to) WITH &&)
```

> **但共管关系是允许的**（`03-data/02-data-domain-model`）—— 同一基金同时有多位经理是正常的，**不重叠约束只针对"同一经理对同一基金"**。

> **已定案 · 2026-08-27**：任职区间不重叠约束**仅适用于「单一主管理人」字段**，**共管场景不适用**。
>
> **依据**：`03-data` 的共管语义**允许同期多经理** —— 一只基金可以由 2~3 人共同管理，其任职区间必然重叠。对全部经理任职记录施加不重叠约束会直接拒绝合法数据。
>
> **正确的约束形式**：
>
> ```
> ❌ UNIQUE EXCLUDE (fund_id WITH =, tstzrange(start, end) WITH &&)
> ✅ 仅对 role = 'LEAD' 的记录施加上述排他约束
> ```
>
> **`role` 字段须先存在** —— 若 `03-data` 的模型中尚未区分主管理人与共管，本约束无法实施，此时应**不设约束**而非退化为「全部不重叠」。

---

## 9. Transaction & Consistency

### 9.1 决策快照必须单事务写入（不可权衡）⚠️

> **沿用上游 §8.4 与架构 §10 —— 这是产品级约束，不是技术偏好。**

```
Decision Snapshot 的全部组成部分（Universe 引用、Score、μ、Σ、约束集、
风险预算、优化目标、优化结果、目标权重）必须在【单一事务】内完整写入

→ 全有或全无（All-or-Nothing）
```

### 9.2 单库使这条约束天然成立

> **沿用 `06-technology-stack` §4.3：** 在单库下，这从"需要额外机制保证"变成"天然成立"。**这是本次选型最大的收益，超过性能考量。**

### 9.3 三级一致性边界

> 沿用架构 §10.3：

| 边界 | 内容 | 一致性 |
|---|---|---|
| **B1** | 单次决策的全部产出 | **单事务，强一致** |
| **B2** | 决策与其引用的上游快照 | 引用完整性（FK `RESTRICT`） |
| **B3** | 跨决策周期 | 最终一致 |

### 9.4 隔离级别

| 场景 | 隔离级别 | 理由 |
|---|---|---|
| **决策快照写入** | **`READ COMMITTED`** | PostgreSQL 默认；单事务内写入无并发冲突 |
| 批量计算写入 | `READ COMMITTED` | 幂等键保证重复执行安全 |
| 一致性巡检 | `REPEATABLE READ` | 需要一致的快照视图 |

> **不使用 `SERIALIZABLE`** —— 本系统的写入按 `(decision_at, Strategy Version)` 幂等键天然隔离，串行化的开销不必要。

### 9.5 批量写入的幂等实现

> **沿用 `04-integration-architecture` §4.4 的幂等键。**

| 阶段 | 数据库层实现 |
|---|---|
| 数据更新 | 按 `version` 唯一约束去重 |
| Factor / Score / Universe | `(decision_at, strategy_version)` 唯一约束 + `INSERT ... ON CONFLICT DO NOTHING` |
| **决策快照** | 同键已存在时**拒绝写入**（`DO NOTHING` 而非 `DO UPDATE`），避免产生两份"当期决策" |

### 9.6 长事务的风险

> **W5（决策快照写入）是单次数千行的多表写入**（`06-technology-stack` §4.6.1）。

| 风险 | 缓解 |
|---|---|
| 长事务阻塞 vacuum | 控制事务时长；监控 `xmin` 推进 |
| 锁等待 | 写入顺序统一，避免死锁 |
| **不可拆分** | **不得为缩短事务而拆分快照** —— 那会破坏 §9.1 |

---

## 10. Temporal / PIT Data Support

### 10.1 数据库只提供存储能力，业务规则属 `03-data`

> **沿用提示词 §4.8：本文件只定义数据库如何支持 PIT，不重新定义 PIT 规则。**

### 10.2 三类时间必须分开存储 ⚠️

| 类别 | 字段 | 类型 | 含义 |
|---|---|---|---|
| **Business Time** | `effective_at` | `DATE` | 事实在业务上生效的日期 |
| **Availability Time** | **`available_at`** | `TIMESTAMPTZ` | **首次对平台可见的时刻 —— PIT 判定的唯一依据** |
| **System Time** | `created_at` / `updated_at` | `TIMESTAMPTZ` | 记录的物理写入时刻 |

### 10.3 `updated_at` 不能代替 PIT ⚠️

> **提示词 §14 特别强调，本域必须落实。**

```
❌ 用 updated_at 判断"当时能看到什么"
   → updated_at 是记录被修改的时刻
   → 它随任何字段变更而变，包括与业务无关的修正
   → 且它无法表达"同一事实的多个版本"

✅ available_at + version 共同确定 PIT 视图
```

### 10.4 版本化表的结构

> **受 PIT 约束的表必须具备四列**：

```
effective_at   DATE           NOT NULL   -- 业务生效日
available_at   TIMESTAMPTZ    NOT NULL   -- 可得时刻
version        INTEGER        NOT NULL   -- 修订序号
is_current     BOOLEAN                   -- 见 §10.6
```

**唯一约束**：`(business_key..., effective_at, version)`

### 10.5 PIT 查询的标准形态

```
候选版本集 = { v | v.available_at <= decision_at }
选取       = 候选集中 version 序号最大者
```

> **判定依据是 `version` 序号，不是 `available_at` 的最大值** —— 两者通常一致，但数据回补场景下可能不一致（`03-data-architecture` §5.2）。

**索引支持**见 §11.4。

### 10.6 `is_current` 是冗余字段，须谨慎 ⚠️

> **它是性能优化，不是真相来源。**

| 用途 | 说明 |
|---|---|
| ✅ 加速"当前视图"查询 | 无 `as_of_date` 的查询走它 |
| ❌ **不得用于 PIT 查询** | PIT 必须走 `available_at` + `version` |
| ⚠️ **必须由触发器或应用层严格维护** | 不一致会导致当前视图错误 |

> **风险**：`is_current` 与 `version` 不一致时，两种查询路径会得到不同结果，且**不会报错**。

`<TBD-PG-6: 是否引入 `is_current` 冗余列，待 W1/W2 负载验证后评估其必要性>`

### 10.7 禁止 UPDATE 覆盖需保留历史的数据 ⚠️

> **数据修订必须产生新版本行，不得原地更新。**

| 表类别 | UPDATE 策略 |
|---|---|
| **NAV、Factor、Score、Universe、Decision、Backtest 结果** | **禁止 UPDATE 业务字段** —— 修订产生新 `version` |
| 主数据的非版本化属性（如基金全称的笔误修正） | 允许 UPDATE，但须审计 |
| 状态流转（如 `backtest.status`） | 允许 UPDATE，状态历史另表记录 |

### 10.8 有效区间（`valid_from` / `valid_to`）与三时点的关系

> **需要澄清一处容易混淆的地方。**

| 模式 | 适用 | 例 |
|---|---|---|
| **三时点 + version** | **事实型数据**（可被修订） | NAV、Factor、Score |
| **`valid_from` / `valid_to`** | **状态型数据**（有明确起止） | 经理任职、分类归属、Benchmark 映射 |

```
NAV 的"2026-08-24 净值"不是一个区间，是一个点 + 可能的修订
经理任职是一个区间：2020-03-15 至 2023-06-30
```

> **两种模式不可互换。** 状态型数据同样需要 `available_at`（公告日晚于生效日是常态）。

---

## 11. Indexing Principles

### 11.1 索引必须有访问模式依据

> **不为"常用字段"建索引，为 §11.3 的实际查询建索引。**

### 11.2 索引的代价

| 代价 | 说明 |
|---|---|
| 写入放大 | 每个索引都增加插入成本 —— W4 每日 60 万行写入 |
| 存储 | 大表的索引可能超过表本身 |
| **vacuum 负担** | 索引膨胀需定期维护 |

### 11.3 典型访问模式与对应索引

> **对应 `06-technology-stack` §4.6.1 的 Workload Matrix。**

| 负载 | 访问模式 | 索引设计 |
|---|---|---|
| **W1** 单基金单因子时间序列 | `(share_class_id, factor_id, as_of_date)` 范围扫描 | 复合索引，`as_of_date` 置末 |
| **W2** 单时点全市场横截面 | `(as_of_date, factor_id)` + 大范围扫描 | **见 §11.5** |
| **W3** Peer Group 内分位 | `(peer_group_id, as_of_date)` + 组内排序 | 复合索引 |
| **W6** 历史决策重建 | 多表按 `decision_at` 关联 | 各表 `decision_at` 索引 |
| **W7** 回测逐期读取 | 重复的 W2 模式 | 同 W2；**吞吐优先** |
| **W8** 快照读写 | `(strategy_id, decision_at)` | 复合唯一索引 |

### 11.4 PIT 查询的索引设计 ⚠️

```
查询：WHERE share_class_id = ? AND available_at <= ? ORDER BY version DESC LIMIT 1
```

| 方案 | 说明 |
|---|---|
| **`(share_class_id, effective_at, available_at, version DESC)`** | 覆盖点查 + 版本选择 |
| 加 `INCLUDE (value)` | **索引覆盖扫描**，避免回表 |

> **`available_at` 必须在索引中**，否则 PIT 过滤需回表逐行判断。

### 11.5 W2 横截面扫描是最大的索引挑战 ⚠️

> **它是列存的优势场景，也是本选型的主要风险点**（`06-technology-stack` §4.6.2）。

```
取 1.2 万只基金 × 50 个因子在某一时点的值
    → 按 (as_of_date) 分区裁剪后仍是 60 万行的扫描
    → B-tree 索引对全量扫描帮助有限
```

**候选优化**：

| 手段 | 说明 |
|---|---|
| **按 `as_of_date` 分区** | 分区裁剪是第一道优化 |
| **BRIN 索引** | 对时序有序数据体积极小；但对随机访问无效 |
| **物化视图** | 预计算横截面；但需处理刷新与 PIT 语义 |
| 列存扩展 | 触发 §4.4 重评估 |

#### 11.5.1 优化顺序已定案，方案选择仍待压测（v1.1）

> **定案 · 2026-08-27**：`TBD-TECH-7` 的**验收框架**已定（`06-technology-stack` §4.6.2），本节的优化**顺序**随之确定；仍待压测的是「哪一档够用」。见 `TBD-resolution.md` Policy ⑦。

```
① 分区裁剪 + 索引 / 物化优化      ← 本域范围内
      ↓ 仍不达标
② 列存旁路（只读副本）             ← 触发 §4.4 重评估
```

**W2 的验收判据**：**P95 latency < X**，且系统峰值 **CPU < 70%、Memory < 75%**（`06-technology-stack` §4.6.2）。

> **资源余量是独立判据** —— W2 在 95% CPU 下达标不算通过。本域的候选优化中，**物化视图是最典型的「用资源换延迟」手段**：它把扫描成本前移到刷新时，延迟指标会好看，但整体 CPU 与存储占用上升。因此它的评估必须连同资源余量一起看，不能只比 P95。

**四个候选的顺序不是任意的**：

| 顺序 | 手段 | 为什么排这个位置 |
|---|---|---|
| 1 | 按 `as_of_date` 分区 | **无副作用** —— 不增加写入成本，不引入一致性问题 |
| 2 | BRIN 索引 | 体积极小，但**只在时序有序时有效**，无效时也无害 |
| 3 | 物化视图 | **有副作用** —— 需处理刷新时机与 PIT 语义（刷新后的视图代表哪个时点的信息集？） |
| 4 | 列存扩展 | **触发架构重评估**，成本最高 |

> **物化视图与 PIT 的冲突须先解决再评估**：一个在 `T+1` 刷新的横截面视图，若被 `T` 时点的回测查询读到，就是前视。可行的形态是**按 `decision_at` 物化**（每个决策时点一份，只增不改），而非「最新横截面」。这一约束使物化视图的存储成本远高于直觉估计。

`<OPEN-14: W2 的 P95 门槛值 X，待压测与产品共同确定>`
`<TBD-PG-7: W2 的优化方案选择（四档中哪一档够用），待压测确定 —— 顺序已定，见 §11.5.1>`

### 11.6 部分索引用于稀疏条件

```
CREATE INDEX ... WHERE status = 'ACTIVE'
CREATE INDEX ... WHERE is_current = true
```

> 适用于**查询高度偏向少数取值**的场景，可显著缩小索引体积。

### 11.7 索引命名

```
idx_<table>_<col1>_<col2>[_partial]
uq_<table>_<col1>_<col2>
```

---

## 12. Partitioning Principles

### 12.1 不为"性能"默认分区 ⚠️

> **分区有明确代价**：跨分区查询变慢、外键受限、维护复杂度上升。

### 12.2 分区的判据

| 判据 | 说明 |
|---|---|
| **数据量** | 单表预期超千万行 |
| **时序性** | 有天然的时间维度 |
| **生命周期** | 需要按时间归档或删除 |
| **查询裁剪** | 绝大多数查询带时间条件 |

> **四条同时满足才分区。**

### 12.3 候选表的评估

| 表 | 预期行数 | 分区判定 |
|---|---|---|
| **`fund_nav`** | ~3,000 万 | **✅ 按 `effective_at` 年/月分区** |
| **`factor_value`** | ~1.5 亿 | **✅ 按 `as_of_date` 月分区** |
| **`fund_score`** | ~3,000 万 | ✅ 按 `as_of_date` 年分区 |
| `backtest_period_snapshot` | ~400 万 | ⚠️ 见 §12.5 |
| `raw_payload` | 大 | ✅ 按接收时间分区（便于归档） |
| `fund` / `fund_share_class` | 万级 | ❌ 不分区 |
| `portfolio` / `optimization_result` | 十万级 | ❌ 不分区 |

### 12.4 分区键必须是查询的常用过滤条件

> **否则分区裁剪不生效，反而变慢。**

```
factor_value 按 as_of_date 分区
    → W1（单基金时间序列）跨多个分区 → 略慢
    → W2（单时点横截面）命中单分区 → 显著快

选择取决于哪类负载更关键 → W2/W7 是风险点，因此按 as_of_date 分区
```

> **这是一个真实的权衡** —— 按 `share_class_id` 哈希分区会让 W1 更快但 W2 更慢。**本域选择优化 W2，因为它是选型的风险点。**

### 12.5 回测结果的分区依据是隔离而非体量 ⚠️

```
backtest_period_snapshot 的行数不大（~400 万）
但单次回测会产生数百期 × 数千行的写入

按 backtest_id 分区（LIST 或 HASH）
    → 单次回测的数据物理聚集
    → 删除某次回测的数据 = DROP PARTITION，避免大批量 DELETE
```

> **这是一个"按生命周期分区"而非"按体量分区"的例子。**

`<TBD-PG-8: 回测结果表的分区策略（按 backtest_id 还是按时间），待回测数据量与保留策略确认>`

### 12.6 分区维护

| 事项 | 说明 |
|---|---|
| **新分区预创建** | 必须提前创建，不能等到写入时 |
| 旧分区归档 | 按 `04-database-design` §18 的保留策略 |
| **分区表的索引** | 每个分区各自建索引；全局唯一约束须含分区键 |

---

## 13. JSONB Usage

### 13.1 适合 JSONB

| 场景 | 理由 |
|---|---|
| **Provider 原始 payload** | 结构随 Provider 变化，且**只需整体存取** |
| **协方差 / 相关性矩阵** | `N × N` 数组，**整体读写、不做字段级查询** |
| Policy 配置的扩展属性 | 结构演进频繁 |
| 优化器诊断信息 | 非结构化 |

### 13.2 不适合 JSONB

| 字段 | 理由 |
|---|---|
| `fund_id` / `share_class_id` | 关联键 |
| `effective_at` / `available_at` | **PIT 过滤字段** |
| NAV / Factor Value / Weight | 需要范围查询与聚合 |
| Manager / Classification | 需要关联与统计 |

> **判据：任何进入 `WHERE`、`JOIN` 或 `ORDER BY` 的字段必须结构化。**

### 13.3 协方差矩阵用 JSONB 的理由与代价 ⚠️

> **沿用 `06-technology-stack` §4.5：JSONB 用于"可整体序列化的结构"。**

| 方案 | 权衡 |
|---|---|
| **JSONB 整体存储（推荐）** | ✅ 一次读写；✅ 与 `instrument_ids` 顺序天然绑定<br/>❌ 无法按元素查询 |
| 三元组表（`i`, `j`, `value`） | ✅ 可查单个元素<br/>❌ `N=100` 时单个矩阵 5,050 行；❌ **顺序需额外维护** |

**选择 JSONB 的关键理由**：`07-return-risk/04` §9.1 明确 **`instrument_ids` 的顺序是矩阵语义的一部分** —— 整体序列化天然保持该顺序，而三元组表需要额外的顺序表且容易失配。

> **失配的后果**：`w'Σw` 算出一个无意义的数，**且不会报错**。

### 13.4 JSONB 的大小限制

> 单个 JSONB 值理论上限 1GB，但**实际应控制在 MB 级**。

```
N = 1000 只基金的协方差矩阵 → 100 万个数字 → 约 10–20 MB
    → 已接近实用上限
```

`<TBD-PG-9: 协方差矩阵的 Universe 规模上限及超限时的替代方案，待 `06-portfolio` 的 Universe 规模确认>`

---

## 14. PostgreSQL Extensions

| 扩展 | 用途 | 第一阶段 |
|---|---|---|
| **`btree_gist`** | `EXCLUDE` 约束（§8.4） | ✅ 需要 |
| `pg_stat_statements` | 慢查询分析 | ✅ 运维必备 |
| `pg_trgm` | 基金名称模糊检索（`10-api/02` §4.1） | ⚠️ 待确认 |
| `pgcrypto` | 敏感字段加密 | ⚠️ 见 §14.1 |
| 列存扩展 | 触发 §4.4 重评估后再议 | ❌ |

### 14.1 敏感数据的处理

> **沿用 `NFR-SEC-003`：敏感配置（数据源凭据等）不得以明文形式存在于配置或日志中。**

**数据库层的落实**：凭据类数据**不入业务库** —— 应由密钥管理服务托管（属 `02-architecture` / `12-operations`）。

`<TBD-PG-10: 是否有需要列级加密的业务字段，待合规确认>`

---

## 15. Naming Conventions

| 对象 | 约定 | 例 |
|---|---|---|
| Schema | `snake_case` 单数 | `fund`、`factor` |
| **表** | `snake_case` **单数** | `fund_share_class` |
| 列 | `snake_case` | `effective_at` |
| 主键 | `id` | —— |
| 外键列 | `<referenced_table>_id` | `share_class_id` |
| 索引 | `idx_<table>_<cols>` | —— |
| 唯一约束 | `uq_<table>_<cols>` | —— |
| CHECK | `ck_<table>_<rule>` | —— |
| 外键约束 | `fk_<table>_<ref_table>` | —— |
| 分区 | `<table>_p<suffix>` | `factor_value_p202608` |

### 15.1 表名用单数

> **一致性优先于偏好。** 单数与实体名对应（`fund` 表存 Fund 实体），且避免"是 `fund` 还是 `funds`"的反复讨论。

### 15.2 时间字段命名与 `03-data` 保持一致

> **不得改名**：`effective_at`、`available_at`、`decision_at`、`version` —— 与 `03-data/04-data-versioning` 完全一致。

---

## 16. Migration Strategy

### 16.1 工具

```
Migration Tool = TBD
```

> **架构层未指定迁移工具**（`06-technology-stack` 未涉及）。本域给出**要求**而非选型。

**要求**：

| # | 要求 |
|---|---|
| 1 | 版本化的迁移脚本，可重放 |
| 2 | 与代码同仓管理，与 `code_version` 关联 |
| 3 | 支持 forward-only（见 §16.2） |

`<TBD-PG-11: 迁移工具选型（Flyway / Liquibase / Alembic 等），待技术评审 —— 建议与 `06-technology-stack` `TBD-TECH-2` 的后端语言选型一并决定>`

### 16.2 Forward-only 原则

> **生产环境不做 rollback，只做 forward fix。**

```
❌ 出问题 → 回滚迁移 → 数据可能已按新结构写入 → 回滚导致数据丢失
✅ 出问题 → 编写新的修正迁移
```

### 16.3 迁移命名

```
V<序号>__<描述>.sql
例：V0042__add_available_at_to_factor_value.sql
```

### 16.4 大表迁移的特殊要求 ⚠️

> **`factor_value`（1.5 亿行）的结构变更不能用普通 `ALTER TABLE`。**

| 操作 | 风险 | 做法 |
|---|---|---|
| 加列（无默认值） | 低 | 直接 `ALTER TABLE`（PG 11+ 元数据操作） |
| **加列（有默认值）** | **PG 11 前会重写全表** | 确认版本；或分步：加列 → 回填 → 加默认 |
| **建索引** | **锁表** | **必须 `CREATE INDEX CONCURRENTLY`** |
| 改列类型 | 重写全表 | 新列 + 回填 + 切换 + 删旧列 |
| **加 NOT NULL** | 全表扫描 | 先加 `CHECK ... NOT VALID` → `VALIDATE` |

### 16.5 `CREATE INDEX CONCURRENTLY` 的注意事项

| 注意 | 说明 |
|---|---|
| **不能在事务块内执行** | 迁移工具需支持 |
| 失败会留下 `INVALID` 索引 | 须检测并清理 |
| 耗时更长 | 但不阻塞写入 |

### 16.6 Schema 变更的兼容性

> **数据库变更必须与应用发布解耦。**

```
① 加新列（可空）        → 兼容，先发布
② 应用同时写新旧列      → 过渡期
③ 回填历史数据          → 后台任务
④ 应用只读新列          → 发布
⑤ 删除旧列              → 最后
```

> **这与 `10-api` §14.3 的向后兼容规则同理** —— 删除是最后一步，且必须在确认无引用后。

---

## 17. Backup & Recovery

### 17.1 数据库层的要求

| 项 | 要求 |
|---|---|
| **备份方式** | 物理备份（基础备份 + WAL 归档） |
| **PITR（时间点恢复）** | 必须支持 —— 见 §17.2 |
| RPO / RTO | `TBD`（属 `12-operations`） |
| 备份验证 | 定期恢复演练 |

> **推荐默认 · 2026-08-27**：**RPO ≤ 1 个决策周期，RTO ≤ 4 小时**（同 `01-product/05-non-functional-requirements` `NFR-10`）。
>
> **本域是执行方不是定义方** —— 目标由 NFR 定义，本域负责给出满足该目标的技术方案（WAL 归档频率、基础备份周期、PITR 保留窗口）。
>
> **注意区分数据库 PITR 与业务 PIT**（§17.2，不变）：前者是「把数据库恢复到某个物理时刻」，后者是「查询某个决策时点可见的数据」。**RPO 说的是前者。**

### 17.2 数据库 PITR 与业务 PIT 是两个概念 ⚠️

> **同名但完全不同，必须澄清。**

| | **Database PITR** | **Business PIT** |
|---|---|---|
| 全称 | Point-in-Time **Recovery** | Point-in-Time **数据视图** |
| 解决 | 误操作后恢复到某个时刻的**数据库状态** | 查询"当时能看到什么数据" |
| 实现 | WAL 归档 + 重放 | `available_at` + `version` |
| 归属 | 运维能力 | **业务语义**（`03-data/04-data-versioning`） |

> **不得用数据库 PITR 实现业务 PIT** —— 后者需要在同一个数据库状态下查询任意历史时点，前者是把整个数据库回退到过去。

### 17.3 历史数据的不可篡改要求

> **沿用 `NFR-SEC-004`：全部用户操作必须记入不可篡改的审计日志。**

| 手段 | 说明 |
|---|---|
| 审计表只允许 INSERT | 通过权限限制 |
| 关键表禁止 UPDATE/DELETE | §10.7 |
| WAL 归档 | 提供最终的追溯能力 |

---

## 18. Operational Considerations

### 18.1 Vacuum 与膨胀

> **W4 每日 60 万行写入 + 版本化设计（只插不改）意味着表持续增长，但 dead tuple 相对较少。**

| 关注点 | 说明 |
|---|---|
| **只追加的表** | dead tuple 少，autovacuum 压力小 |
| **状态流转表**（如 `backtest.status`） | UPDATE 频繁，需关注膨胀 |
| **长事务**（W5） | 会阻塞 vacuum 回收 —— §9.6 |

### 18.2 连接管理

> 五个 Domain Service + 批量任务 + 回测并发，连接数可能成为瓶颈。

> **已定案 · 2026-08-27**：引入连接池中间件 **PgBouncer**，**transaction 模式**。
>
> **依据**：
>
> ```
> 本系统的负载是【混合】的：
>     决策日批处理 —— 少量长连接，高并发写
>     在线查询     —— 大量短连接，读为主
>     → 连接数波动大，直连会在批处理期间耗尽连接
>
> transaction 模式：连接在事务结束后即归还
>     → 与本系统的【短事务】特征匹配
> ```
>
> **为什么不用 session 模式**：它在会话结束前不归还连接，收益接近于零（等同于直连）。
>
> **transaction 模式的限制须知晓**：不支持会话级特性（预处理语句缓存、`SET` 会话变量、通知/监听）。**决策快照的单事务写入不受影响** —— 它本就是一个事务内完成的（`01-system-architecture` §10.3）。

### 18.3 读写分离

> **沿用 `06-technology-stack` §4.5：主从复制 —— 分析查询走从库。**

| 查询 | 路由 |
|---|---|
| 决策链路的读写 | **主库** —— 必须读到最新写入 |
| 展示层查询、报表 | 从库 |
| **回测（W7）** | 从库 —— 只读历史数据 |

#### 18.3.1 复制延迟对 PIT 查询无影响

> **需要澄清一处：**

```
从库有复制延迟 → 可能读不到刚写入的数据
但 PIT 查询本身就是"读历史" → 刚写入的数据其 available_at 通常晚于 decision_at
    → 本就不应被查到
```

> **例外**：回测重跑时若刚补录了某期快照，从库可能尚未同步 —— 这属 `08-backtest/01` §22.1 的可复现性问题。

### 18.4 监控指标

> 具体监控属 `12-operations`，数据库层需暴露：慢查询、锁等待、复制延迟、连接数、表膨胀率、分区数量。

---

## 19. Constraints

| # | 约束 | 来源 |
|---|---|---|
| C-1 | **决策快照必须在单一事务内完整写入** | 上游 §8.4、架构 §10 |
| C-2 | **不得为缩短事务而拆分快照** | 同上 |
| C-3 | **金融数值禁止使用浮点类型** | 本文档 §5.1 |
| C-4 | **Internal ID 与 Provider ID 必须分离** | 本文档 §6.1 |
| C-5 | **禁止因业务对象删除而级联删除历史记录** | 本文档 §7.4、`08-backtest/04` §5.1 |
| C-6 | **需保留历史的数据禁止 UPDATE 覆盖** | 本文档 §10.7 |
| C-7 | **`updated_at` 不得代替 PIT 判定** | `03-data/04-data-versioning` |
| C-8 | 数据访问必须经 PIT-aware 接口 | 架构 §7.4、§11.7 |
| C-9 | 每个 schema 只有一个 Write Owner | `03-data-architecture` §4.2 |
| C-10 | 本域**不重新定义**业务规则、数据质量规则、因子公式、投资策略、API 语义 | 提示词 §1 |
| C-11 | 时间字段命名与 `03-data` 完全一致 | 本文档 §15.2 |
| C-12 | 存储选型结论沿用 `02-architecture`，本域不改变 | 上游 §12 索引 |

---

## 20. Decisions

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **删除 `02-clickhouse.md`** | 空文件、零引用，与已定案选型矛盾 |
| D-2 | 五个 Service 共享同一 PG 实例 | 使快照单事务天然成立 |
| D-3 | **第一阶段不引入独立缓存层** | 缓存 PIT 敏感数据的键设计易错且错误不可见 |
| D-4 | **按数据域分 schema，不按 service 分** | 数据域比服务拆分稳定 |
| D-5 | `raw` schema 独立隔离 | 访问模式与保留策略完全不同 |
| D-6 | **金融数值一律 `NUMERIC`** | 浮点误差不可预测、不可复现 |
| D-7 | **百分比存小数，与 API 一致** | 转换层必须全平台统一 |
| D-8 | **`available_at` 用 `TIMESTAMPTZ`** | 能表达 `DATE` 的全部信息，反之不能 |
| D-9 | 枚举用 `VARCHAR` + `CHECK`，**不用原生 `ENUM`** | 业务枚举会新增，`ALTER TYPE` 成本高 |
| D-10 | **Provider ID 不作 PK**，通过身份映射管理 | 多 Provider 冲突、ID 可变、供应商可替换 |
| D-11 | 时序明细表用**复合主键** | 天然唯一性来自业务键；这类表不被外键引用 |
| D-12 | **快照引用的 FK 用 `RESTRICT`** | 被引用的快照删除会使历史决策不可重建 |
| D-13 | **`CHECK` 只处理单行内可判定的不变式** | 跨行约束用触发器难调试且影响批量写入 |
| D-14 | 权重之和的校验放应用层 + 巡检 | 跨行且形态随现金/冻结持仓变化 |
| D-15 | **不使用 `SERIALIZABLE`** | 幂等键已天然隔离 |
| D-16 | 决策快照同键冲突时**拒绝写入**而非更新 | 避免产生两份"当期决策" |
| D-17 | **区分"三时点+version"与"valid_from/to"两种时间模式** | 事实型与状态型数据的时间语义不同 |
| D-18 | **`is_current` 列待评估**，且不得用于 PIT 查询 | 它是冗余优化，不一致时错误不报 |
| D-19 | **`factor_value` 按 `as_of_date` 分区**（优化 W2） | W2/W7 是选型的风险点 |
| D-20 | **回测结果按 `backtest_id` 分区** | 按生命周期而非体量分区，便于整体删除 |
| D-21 | **协方差矩阵用 JSONB** | `instrument_ids` 顺序天然绑定；三元组表易失配且失配不报错 |
| D-22 | **Forward-only 迁移** | 回滚可能导致已按新结构写入的数据丢失 |
| D-23 | 大表建索引**必须 `CONCURRENTLY`** | 否则锁表 |
| D-24 | **澄清数据库 PITR 与业务 PIT 是两个概念** | 同名不同义，不得互相替代 |
| D-25 | 回测查询走从库 | 只读历史，复制延迟无影响 |

---

## 21. TBD

| # | 事项 | 影响 | 责任方 |
|---|---|---|---|
| PG-1 | 是否需要独立缓存层及其 PIT 安全的键设计 | 性能 | 技术（待 W2/W7 验证） |
| PG-2 | 报告文件的存储方案 | 存储结构 | 产品 + 技术 |
| ~~PG-3~~ | ~~各类数值的最终 precision / scale~~ —— **已定案**：见 Policy A：金额 `NUMERIC(20,4)`、比率 `NUMERIC(12,8)`、净值 `NUMERIC(18,8)` | — | ✅ 2026-08-27 |
| ~~PG-4~~ | ~~`BIGINT` 序列与 UUID 的选择~~ —— **已定案**：主键用 **`BIGINT` 序列** | — | ✅ 2026-08-27 |
| ~~PG-5~~ | ~~任职区间不重叠约束的适用范围~~ —— **已定案**：任职区间不重叠约束**仅适用于「单一主管理人」字段**，共管场景不适用 | — | ✅ 2026-08-27 |
| PG-6 | 是否引入 `is_current` 冗余列 | 查询性能 vs 一致性风险 | 技术 |
| PG-7 | **W2 横截面扫描的优化方案** —— **优化顺序已定案**（§11.5.1），**哪一档够用待压测** | **选型成立的前提** | 技术（关联 `OPEN-14`） |
| PG-8 | 回测结果表的分区策略 | 生命周期管理 | 技术 + 运维 |
| PG-9 | 协方差矩阵的 Universe 规模上限 | JSONB 可行性 | 技术 + 组合 |
| PG-10 | 是否有需列级加密的业务字段 | 安全 | 合规 |
| PG-11 | **迁移工具选型** | 变更管理 | 技术评审 |
| PG-12 | RPO / RTO 与备份保留期 | 灾备 | 运维 |
| ~~PG-13~~ | ~~是否需要连接池中间件~~ —— **已定案**：引入连接池中间件（PgBouncer，transaction 模式） | — | ✅ 2026-08-27 |

---

## 22. Related Documents

| 关系 | 文档 |
|---|---|
| **上游** | `01-product/01-product-overview.md` v2.5（§8.4 存储特征要求、§12 索引） |
| **架构（选型来源）** | `02-architecture/06-technology-stack.md` v1.2 §4（PostgreSQL 选型与 Workload Matrix）、`03-data-architecture.md` v1.1（数据域、Ownership、PIT、快照）、`01-system-architecture.md` v2.3（§10 一致性边界） |
| **数据语义来源** | `03-data/02-data-domain-model`（实体）、`04-data-versioning`（PIT 业务规则）、`05-data-normalization`（口径） |
| **本域** | `03-erd`（实体与关系）、`04-database-design`（物理设计） |
| **下游** | `12-operations`（备份、监控、容量） |

---

## 23. Change Log

| 版本 | 日期 | 变更内容 | 上游依赖 |
|---|---|---|---|
| **v1.2** | 2026-08-27 | **第二批定案（4 项）**。`PG-3` 精度体系见 Policy A，净值用 8 位小数是为后复权累乘留余量；`PG-4` 主键用 **`BIGINT` 序列** —— UUID 解决的是多主写入问题而本系统是单写入点，其随机分布在千万级表上写放大显著；`PG-5` 任职不重叠约束**仅适用于主管理人**（共管场景允许区间重叠，全量施加会拒绝合法数据）；`PG-13` 引入 **PgBouncer transaction 模式**，与本系统的短事务特征匹配。 详见 `TBD-resolution-2.md` | `TBD-resolution-2.md` v1.0 |
| **v1.1** | 2026-08-27 | **Policy ⑦ 落地**。新增 §11.5.1 —— W2 的优化**顺序**定案（分区 → BRIN → 物化 → 列存），按「副作用递增」排列；补 W2 验收判据（P95 < X 且资源余量达标）并指出**物化视图是典型的「用资源换延迟」手段**，评估须连同资源余量；明确**物化视图与 PIT 的冲突须先解决**（按 `decision_at` 物化而非「最新横截面」，否则刷新后的视图被历史回测读到即前视），该约束使其存储成本远高于直觉估计。`PG-7` 性质变更为**顺序已定、档位待压测**。详见 `TBD-resolution.md` Policy ⑦ | `02-architecture/06-technology-stack` v1.3 |
| v1.0 | 2026-08-27 | 初始版本。**§1.3 删除与选型矛盾的 `02-clickhouse.md`**；**§3.3 第一阶段不引入独立缓存层**（缓存 PIT 敏感数据的键设计易错且错误不可见）；**§4.4 按数据域而非 service 分 schema**；**§5.1 金融数值禁止浮点**、**§5.5 `available_at` 用 `TIMESTAMPTZ`**（选窄了无法扩展）、**§5.7 枚举不用原生 `ENUM`**；**§6.1–6.2 Internal ID 与 Provider ID 分离**的四条理由；**§7.3–7.4 快照引用用 `RESTRICT`、禁止级联删除历史**；**§8.2 `CHECK` 只处理单行内不变式**；**§9.1–9.2 决策快照单事务在单库下天然成立**；**§10.3 `updated_at` 不能代替 PIT**、**§10.6 `is_current` 是冗余优化且不一致时不报错**、**§10.8 区分事实型与状态型两种时间模式**；**§11.5 W2 是最大索引挑战**；**§12.4 分区键选择是 W1 与 W2 的真实权衡**、**§12.5 回测按生命周期分区**；**§13.3 协方差用 JSONB 的关键理由是 `instrument_ids` 顺序绑定**；§16.4 大表迁移的五类操作风险；**§17.2 澄清数据库 PITR 与业务 PIT 是两个概念** | `02-architecture/06-technology-stack.md` v1.2、`03-data-architecture.md` v1.1、`03-data` v1.0–v2.2 |