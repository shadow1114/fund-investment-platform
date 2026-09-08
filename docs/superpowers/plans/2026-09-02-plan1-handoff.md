
# Plan-1 → Plan-2 交接

> Plan-1（M1.0 地基 + M1.1 数据接入）已合并进 main。本文件记录**必须被 Plan-2
> 接住的东西**。它不是完整的 deferred 清单（那份随 SDD 工作区一起废弃了），
> 而是整分支最终评审明确要求「写进 Plan-2 开场任务、而不是留在清单里」的部分。
>
> **后续状态（2026-09-08）**：`../specs/2026-09-08-plan2-evaluation-pipeline-design.md`
> 已接管本交接内容，并将版本化人工 Benchmark、REL 因子和最小 OOS 有效性检验纳入
> Plan-2。下文保留的是 Plan-1 完成时的真实边界，不应再作为 Plan-2 的最终范围说明。

## 一、排在 Plan-2 最前面的两条

这两条都是「**第三个实现出现时才会分叉**」的形态，而 Plan-2 恰好就是那个会写出
第二、第三个 PIT repository 和第二批区间表的批次。等到分叉发生就晚了。

### H-1　`decision_at → visible_until` 的翻译规则被复制成两份

`repositories/nav.py` 与 `normalization/backfill.py` 各有一份逐字相同的

```python
visible_until = dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
```

这是把 `decision_at`（`date`）翻译成 `available_at <= ?`（`timestamptz`）的**唯一**规则，
也就是全平台唯一可见性规则的落地形式。它现在住在两个不同的层，**没有共同归属、
没有任何测试断言两者相等**。

失败场景：Plan-2 为 `risk_free_rate` / `fund_classification_history` 写第二、第三个 PIT
repository，第三份拷贝写成 `dt.time.min`，两条路径对同一个 `decision_at` 解析出不同的
可见集合 —— 不报错、不告警，回测和实盘看到不同的数据。

**做法**：提到 `PitDataContext.visible_until` 属性（它持有 `decision_at`，是唯一构造入口），
两个消费方都改为取它。

### H-2　没有任何机制强制「IntervalMixin 表必须用 interval 生成器」

`platform/db/mixins.py` 有两个生成器：`temporal_check_constraints`（版本化事实表，五子句）
与 `interval_temporal_check_constraints`（区间型状态表，三子句）。选哪个**完全靠作者手工**。
当前 11 张表全部选对。

失败场景：Plan-2 新增一张区间型表（如 `fund_subscription_status`），作者复制粘贴时抓了
版本化的那个 → 所有**提前公告**的行（公告 8-25、生效 9-01）在写入时被 CHECK 直接拒收。
而这正是 Plan-1 花了一整轮修掉的问题。

黄金快照抓不到它：新表本来就应该新增约束，快照给出的是一条完全正常的信号。

**做法**（约 15 行）：遍历 `Base` 子类，凡继承 `IntervalMixin` 的，断言其 `__table_args__`
里的 `ck_*_time_order` 文本等于 `INTERVAL_TIME_ORDER_SQL`，反之亦然。

## 二、打包成一个「收紧 PIT 数据契约」任务

以下四条改的是**同一个 dataclass**（`NavPoint`）与同一处契约，分开做会改四次：

1. **`availability_quality` 不沿链路传播** —— 现算后一个点的复权值依赖调用方在返回值里
   根本看不到的行（`date_from` 之前的全部历史）。逐行 quality 标记因此比以前更容易误导：
   调用方看到 `VERIFIED` 却不知道上游有 `INFERRED`。需要先定聚合规则
   （min-over-chain？还是新开 `chain_quality` 字段？）—— 这是策略决定，不是 bug 修复。
2. **`NavPoint.adjusted_nav` 的类型仍是 `Decimal | None`**，但现算路径已不可能返回 `None`
   （要么全有值要么抛 `AdjustedNavUnavailable`）。下游的 `is None` 分支已是死代码。
3. **读路径 fail-closed 的粒度** —— 现算把 C-6 从「逐行 None」提到了「整条序列抛异常」。
   方向安全（信息偏少不偏多），但「前缀可用性」值得作为后续项。
4. **`visible_until` 判到 UTC 日终** —— 若披露时刻按 UTC+8 记，相当于允许 `decision_at`
   当天看到最多 8 小时后的披露。是既有约定，非现算改造引入。

## 三、Plan-2 第一段任务描述里要点名的

**`AdjustedNavUnavailable` 只在 CLI 的单只调用点被捕获**，`IngestService` 自身无保护。
Plan-1 没有批处理循环所以不构成缺陷，但 **Plan-2 第一次写多只基金的批处理循环就会
重新踩到**：一只基金复权不可算会中断整个循环。保护应下沉到 service 层。

## 四、趁表还空着就做

**`fund_manager_assignment` 缺设计文档要求的 `EXCLUDE USING gist` 重叠约束**（及两个索引）。
表当前为空，加约束的迁移很便宜；有数据之后成本高一个量级。
注意它与 spec §6.3「M1 一次建对，M2+ 只加表不改既有结构」有张力 —— 建议 Plan-2 开头就补。

同理：另外四张区间表（`fund_fee` / `fund_status_history` / `fund_classification_history` /
`fund_manager_assignment`）都缺「至多一条开放区间」的部分唯一索引，
`provider_fund_identity` 已有（`uq_pfi_open_interval`）。但**开放区间的唯一性键不一定只是
外键**（如 `fund_fee` 可能每种费率类型各有一条开放区间），需逐表判断，不可一刀切。

## 五、诚实登记的已知限制

这些**不是待办**，是 Plan-1 数据与设计的真实边界，Plan-2 必须知道：

- **标识数据无历史**：只知道今天的 provider 代码映射，所以灌数日之前的回测**无法做 PIT
  标识解析**。`cli._resolve` 因此刻意不做 PIT 过滤（净值/分红本身的可见性不受影响）。
  这是数据本身的限制，不能靠放宽约束粉饰。
- **披露时滞住在代码里**：`cli.DISCLOSURE_LAG_DAYS = 1`。它决定了 100% 数据的
  `available_at`（AKShare 全是 INFERRED）。已有测试钉住生产装配路径的取值，但**尚未登记进
  `governance.data_source_priority`** —— 该表建了、从不读写。spec DS-2 要求它版本化且
  「回测报告必须复述它」，以当前存储形态**报告无从复述**。引入第二个 provider 前必须补上。
- **clause 5 对 INFERRED 是真空满足的**：`available_at >= COALESCE(provider_available_at,
  published_at)` 在两个来源皆 NULL 时不生效。数据库能挡「EXACT/DERIVED 声称比来源更早
  知道」，**挡不住「时滞配错了」**。
- **`ParsedYieldPoint` 没有生产调用方**：`risk_free_rate` 的灌数属 Plan-2。`curve_code` 与
  `RiskFreeRate.curve_code` 只在结构上对齐，未端到端跑通。
  另：未登记的曲线名被静默跳过，只有「一条都认不出来」才报错 —— 若上游只给国债曲线改名，
  它会静默消失。彻底堵住需要「必须存在 `CN_TREASURY`」这类断言，属灌数编排层策略。
- **`grouping_status` 现在有信息量了**（`fip_dev` 20 个份额类别里 5 个 `UNCONFIRMED`），
  但**仍无消费方、无人工确认工作流**。Plan-2 不接上就会变成另一种死字段。
  另：它只在 `Fund` 首次创建时写入，已存在的 `Fund` 不会刷新 —— 重建数据要先清库。
- **归组只用了名称主干**：spec §4.5 的归组键是「名称主干 + 管理人」，
  `FundManagementCompany` 建了表但从不写入，管理人维度在结构上不可用。
- **Plan-1 的 Relative Performance Score 恒为 `UNAVAILABLE`**：Plan-1 完成时 Benchmark
   尚未实现；Plan-2 新设计已纳入版本化人工 Benchmark，因此该限制只描述 Plan-1 历史状态。
  （官方业绩比较基准的成分与权重需解析招募说明书文本，AKShare 不提供结构化形式）。
  这是**刻意的**：正好在 M1 把 `UNAVAILABLE` 与 `Data Completeness` 跑通 ——
  基于 4 个子分的 85 分与基于 5 个子分的 85 分必须可区分。

## 六、流程上必须继承的三条

1. **「只由阅读/推理保证的性质等于没有保护」**。Plan-1 被这条咬了至少六次，
   最后一次是 `ROUND_HALF_UP` 的选择理由完全正确、却没有任何断言守着它
   （换成 `ROUND_HALF_EVEN` 全部测试照样绿）。**证伪是唯一的验收方式**：
   每条新测试都要在修复前实际跑一遍确认失败。
2. **比「没有测试」更坏的是「有一条自称是 oracle、实际恒真的测试」**。
   Plan-1 出现过三条把错误行为焊死的测试，还有一条 docstring 写着「保护物化列不跑偏的网」
   而在真实数据上恒不成立的测试。写断言时要问：**什么情况下它会红？**
3. **`alembic autogenerate` 对 CHECK 表达式失明**。实测把整条时序 CHECK 换成 `CHECK (1=1)`
   （等于废掉全平台 PIT 强制），它仍报零操作。CHECK 的防线是
   `tests/integration/check_constraints.snapshot` 黄金快照，不是 autogenerate。
   两者互补：快照管 CHECK 表达式，autogenerate 管表/列/索引/唯一键。
   **autogenerate 这道闸门目前完全是手工的，CI 不跑** —— 用
   `alembic.autogenerate.compare_metadata` 写成集成测试约 15 行，值得在 Plan-2 补上。