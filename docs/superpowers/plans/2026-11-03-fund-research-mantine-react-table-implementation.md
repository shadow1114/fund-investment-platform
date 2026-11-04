# 基金研究改版与全站 AG Grid 迁移实施计划

> 上游文档：docs/01-product/01-product-overview.md（v2.6）｜本文细化环节：支撑层
>
> **文档版本**：v1.11
> **日期**：2026-11-03
> **执行对象**：Codex 或其他代码实施代理
> **状态**：实施与定向验收已完成；全量前端/可访问性套件及全项目 Ruff 的已知限制见第 11 节和验收报告。未执行生产迁移、数据回填、抓取、提交或推送。

## 1. 目标与执行规则

**目标**：为 `fund.fund` 增加 `company_name`；使用 AG Grid Community 建立共享 React 数据表实现，并将全站现有业务表格统一迁移；基金研究页使用 30/70 固定查询/结果布局，结果区只保留 AG Grid；实现数据库端筛选、排序、计数与分页，以及双击打开基金详情窗口。

**技术栈**：React 19.3.1、TypeScript、Mantine 9、AG Grid Community 36.2.0、React Query、React Router、FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、Orval。

### 给 Codex 的执行要求

1. 执行前完整阅读产品总览，再阅读本计划及涉及目录的项目规范。
2. 按任务依赖顺序实施；每项先补失败测试，再实现，再运行相关回归。完成后更新复选框和执行记录。
3. 只修改本次需求相关内容，不重写分类规则、Factor 算法、评分、优化、回测或抓取权限体系。
4. 第一阶段仍是纯 Quant 系统，不增加 ML/AI 决策能力；只使用现有 PostgreSQL，不新增数据库产品。
5. 不手改 `frontend/src/api/generated/`；修改 OpenAPI 源文件并通过 Orval 重新生成。
6. 不提交、不推送、不部署、不执行生产数据库迁移。若后续用户要求提交，先确认工作分支并按仓库要求使用中文提交信息。
7. 保留用户已有的 `.vite/`、`.vscode/` 等无关未跟踪内容。
8. 集成测试会重置测试库 schema；必须先确认 `FIP_TEST_DATABASE_URL` 是专用可丢弃测试库，绝不能指向开发数据库或生产数据库。
9. 若安装依赖遇到不可解决的 peer dependency 冲突，或现有数据无法提供需求字段，记录具体阻塞，不能用 `--force`、伪造数据或静默忽略筛选规避。

## 2. 已核对的现状与实现基线

### 2.1 基础查询 SQL

采用以下基础查询，基金份额表别名统一为 `fsc`：

```sql
SELECT pfi.provider_fund_id, f.product_name, f.company_name, '开放' AS sub_status
FROM fund.fund f
LEFT JOIN fund.fund_share_class fsc ON fsc.fund_id = f.id
LEFT JOIN fund.provider_fund_identity pfi ON fsc.id = pfi.share_class_id;
```

**实施基线**：以该 SQL 的关联关系为基础，保持 Share Class 行粒度，不将不同份额按基金产品合并；正式分页查询按第 4 节补充供应商、有效区间与可见时点约束，并在 PostgreSQL 中完成筛选、去重后的计数、稳定排序、`LIMIT/OFFSET`，只对当前页执行必要的兼容字段补全。

### 2.2 标识与行粒度

| 字段 | 用途 | 本次要求 |
|---|---|---|
| `fund_id` | 现有公共基金标识，部分抓取接口依赖它 | 保留既有语义，不做全平台 ID 迁移 |
| `share_class_id` | 稳定的份额 ID，API 采用字符串 | 新增到列表；通过 AG Grid `getRowId` 作为行 ID 和详情定位 |
| `fund_code` | 六位标准展示代码 | 从有效 AKSHARE 映射取得，字符串类型，保留前导零 |
| `fund_name` | 既有列表名称 | 映射 `f.product_name`，不引入新的同义 DTO 字段 |
| `company_name` | 管理公司名称 | 来自本次新增主数据列；历史查询使用可见历史快照 |
| `sub_status` | 本次申购状态展示字段 | 当前需求 SQL 固定返回 `开放`，详见下节 |

列表按 `share_class_id` 唯一，AG Grid `getRowId` 返回该值；不使用 `fund_id`、名称或可为空的标准代码作为行 ID。详情、NAV、Factor 请求使用该行 `share_class_id`，现有仓库支持字符串份额 ID；抓取入口仍按现有公共 `fund_id` 使用。不得让六位展示代码直接替代详情或抓取 API 的资源 ID。

没有有效六位映射的份额仍保留，`fund_code=null`，前端显示 `—`，不退回显示 `P-...`，不伪造或盲目补零。严格使用 ASCII `[0-9]{6}`；若源端返回非标准值，记录缺失而非猜测。

### 2.3 申购状态的明确边界

本计划按用户 SQL 保留固定投影：`sub_status='开放'`。

- 查询控件提供“全部”“开放”；不新增虚假的暂停/关闭值。
- 返回 `meta.subscription_status_source='PLACEHOLDER'`，查询区及详情窗口明确提示“申购状态按当前接口固定显示为开放，非实时交易状态”。
- 后端校验 `sub_status`：省略表示全部，`开放`表示与固定投影匹配，其他值返回 422。
- `sub_status` 不修改 `FundStatusHistory.subscription_open`，不替代 `lifecycle_status` 或 `investment_eligibility`，不用于 Fund Universe 准入、回测或实际交易判断。
- 若用户后续要求真实申购状态，另行确定数据来源和状态映射，使用现有份额级状态历史及 PIT 规则实施；不得在本次任务中自行扩展状态含义。

### 2.4 基金类别使用 `asset_class`

固定选项：`EQUITY, BOND, MIXED, MONEY_MARKET, FOF, REIT, COMMODITY, OTHER, UNKNOWN`。

这些值属于现有 `classification.asset_class`，不是旧 `fund_type` 的兼容投影（后者可能是 `HYBRID`、`ACTIVE_EQUITY`、`PASSIVE_EQUITY`）。新控件发送 `asset_class`，保留旧 `fund_type` 查询支持，不修改旧枚举或把 `MIXED` 错写为 `HYBRID`。

- 对正常类别：只匹配当前可见版本、对应业务日期有效区间内，状态为 `CONFIRMED`、评价状态有效的资产类别。
- 对 `UNKNOWN`：匹配没有可见分类快照，或实际已评价且结果为 `UNKNOWN` 的份额对应产品。`CANDIDATE`、`CONFLICT`、`PAUSED`、`NOT_EVALUATED` 不自动当作 `UNKNOWN`。
- 旧多维分类/标签查询继续保持现有已确认、当前规则集与证据校验语义；不能靠 JSON 中出现一个值就认为分类已经确认。
- `UNKNOWN` 的 SQL 语义与测试应同步修正现有 `_matches` 中“只接受 CONFIRMED”的冲突；不要增加前后端不同的 UNKNOWN 判定。

### 2.5 PIT 与公司名称

`Fund.company_name` 是便于当前查询的最新名称投影，不是历史真相。公司名称同时写入 `FundBasicInfoHistory.normalized_fields.company_name`，保留旧快照。

历史查询必须先限制 `available_at <= resolve_visible_until(as_of_date)`，再取可见的最大 `version`。旧快照若没有规范化公司字段，可从同一可见快照的已验证原始公司字段解析；不得回退到今天的 `Fund.company_name` 冒充历史值。

代码映射、分类、状态及已有历史筛选继续遵循 `available_at` 和有效区间；本次默认研究页查询当前数据。不能仅因请求带了 `as_of_date` 就返回实际使用当前数据的 `is_point_in_time=true`。

## 3. 前后端契约

### 3.1 `GET /api/v1/funds`

新增参数，保留既有参数：

| 参数 | 规则 |
|---|---|
| `fund_name` | 去除首尾空白；非空时对 `product_name` 做字面量包含查询 |
| `fund_code` | 非空时必须匹配 `[0-9]{6}`；标准代码精确匹配 |
| `company_name` | 下拉选中的公司名称，精确匹配；空值不发送 |
| `asset_class` | 复用已有 CSV 多值参数；新页面为单选 |
| `sub_status` | 省略或 `开放` |
| `page` | 一基页码，默认 1，必须 >=1 |
| `page_size` | 兼容既有正整数范围；页面仅提供 20/50/200，默认 20 |
| `sort` | 扩展为 `fund_code/fund_name/company_name/sub_status`，保留 `inception_date/aum` |
| `order` | `asc/desc` |

允许客户端已有的较小页尺寸，不将 API 强制限制为三个选项。无数据和越界页均返回空数组及真实总数，不偷偷修改请求页码。

列表 DTO 采用向后兼容扩展，在 `FundListPayloadModel` 增加字段，不要求全部详情 DTO 或其他共享摘要消费者一起提供新字段：

```json
{
  "data": [
    {
      "fund_id": "P-example",
      "share_class_id": "123",
      "fund_code": "000001",
      "fund_name": "示例基金",
      "company_name": "示例基金管理有限公司",
      "sub_status": "开放"
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 245,
      "total_pages": 13
    },
    "as_of_date": null,
    "is_point_in_time": false,
    "subscription_status_source": "PLACEHOLDER"
  }
}
```

以上是新增字段片段示例，实际响应必须保留现有 `share_class`、`fund_classification`、`management_company_id`、`inception_date`、`lifecycle_status`、`investment_eligibility`、`classification` 等契约字段，以及既有响应封装。公司名未知允许缺失/null，不能伪造管理公司 ID。

分页最大值：将全局默认 `max_page_size` 调整为至少 200，部署/测试配置不得仍覆盖为 100；保留原有明确配置的保护能力，其他路由继续按自身更低上限校验。新增测试证明默认服务接受基金列表 200 行，抓取结果等仍受其 100 行上限限制。

### 3.2 管理公司下拉数据

新增 `GET /api/v1/fund-management-companies`，`operationId=listFundManagementCompanies`。

- 返回标准 envelope，`data=[{"company_name":"…"}]`。
- 当前数据：查询 `fund.fund` 非空 `company_name` 去重、稳定排序；不从当前页基金列表提取公司，不加载全量基金到浏览器。
- 支持可选 `as_of_date`；历史模式从可见历史快照投影去重，保持筛选与选项口径一致。
- 选项独立于研究页其他筛选条件，React Query 按时点缓存；抓取更新基本信息后失效公司选项缓存。
- 未取得公司名称时不产生虚假“未知公司”选项；页面说明缺失名称显示 `—`。
- 如按真实数据规模需要选项搜索/分页，可在实现前提出具体证据，不在本次任务中预先引入复杂 autocomplete 服务。

## 4. 数据库查询设计

### 4.1 基础关联示意

下列示意只展示正确关联和有效映射选择，不能作为跳过分类及历史筛选的完整实现：

```sql
SELECT
    f.fund_code AS fund_id,
    sc.id::text AS share_class_id,
    identity.provider_fund_id AS fund_code,
    f.product_name AS fund_name,
    f.company_name,
    '开放'::text AS sub_status
FROM fund.fund f
JOIN fund.fund_share_class sc ON sc.fund_id = f.id
LEFT JOIN LATERAL (
    SELECT pfi.provider_fund_id
    FROM fund.provider_fund_identity pfi
    JOIN governance.data_provider dp ON dp.id = pfi.provider_id
    WHERE pfi.share_class_id = sc.id
      AND dp.provider_code = :provider_code
      AND pfi.provider_fund_id ~ '^[0-9]{6}$'
      AND pfi.available_at <= :visible_until
      AND pfi.valid_from <= :effective_at
      AND (pfi.valid_to IS NULL OR pfi.valid_to > :effective_at)
    ORDER BY pfi.valid_from DESC, pfi.available_at DESC, pfi.id DESC
    LIMIT 1
) identity ON TRUE;
```

`provider_code` 本次取现有 `AKSHARE`，不是任意供应商中随便找一个六位 ID。同一份额若存在多个有效 AKSHARE 六位代码，采用上述确定性选择规则，并通过测试锁定；其他供应商不能扩大列表行数。

### 4.2 必须下推的操作

1. 建立每份额一行的基础 CTE/subquery，包括时点可见的公司/分类/已有筛选数据。
2. 以 SQLAlchemy 条件表达式或 SQL `text()` 绑定参数构建 `WHERE`；用户值不得进入 SQL 字符串拼接。
3. `fund_name` 使用转义后的 ILIKE 包含匹配，`%/_/\\` 按字面量处理，不能意外成为全库通配符。
4. 既有 `manager_id` 使用 `EXISTS`，不能经理共管 JOIN 导致重复；其他历史维度同样先解出唯一可见行。
5. `asset_class` 从最大可见 revision 及其有效 interval 中读取；旧 `fund_type` 使用原有兼容投影语义。不要只过滤 `valid_to IS NULL` 或跳过可见 revision 选择。
6. 标签和其他旧筛选的 SQL 实现必须与现有 `_matches`、分类 policy/证据校验等价；确有复杂兼容投影无法直接表达时，可在 data-service 层提供复用查询组件，但不能加载全库后再分页，也不能对当前页补筛选导致总数错误。
7. 缺乏真实来源的旧公司 ID/AUM 条件继续按明确“不可用”契约报错，不静默忽略，也不混同 `management_company_id` 与 `company_name`。
8. 总数查询从完成同一组筛选的唯一份额集合计数，不能对原始一对多 JOIN 直接 `COUNT(*)`。
9. 排序字段通过服务端白名单映射；稳定末级键为 `fund_id`、`share_class_id`，标准代码为空时 NULLS LAST。升降序及同名基金都必须稳定。
10. 数据查询使用 `LIMIT :page_size OFFSET :offset`；计数和数据读取采用同一请求事务中的一致快照，避免并发更新造成单次响应内部不一致。
11. 分页前不调用逐基金 `_summary`；兼容字段可对当前页进行批量补全，查询数不能随全库基金数线性增长。
12. 增加 `FundRepository.list_page(...)` 明确返回当前页与总数；`FundQueries.list` 仅委派和组装 meta，不再 Python 全量过滤/切片。不要更改其他内部调用所依赖的非分页 `list()` 返回类型。
13. 测试 fake/seeded repository 也实现相同分页边界，避免仅生产实现走 SQL、测试却继续验证旧全量 Python 路径。

索引按查询计划评估：优先复用现有份额/供应商/PIT 索引；公司等值或排序索引如需要，必须同时加入 ORM metadata 与 Alembic。不要默认引入 trigram 扩展；用专用测试数据执行 `EXPLAIN (ANALYZE, BUFFERS)` 后记录结论。

## 5. 前端产品与布局要求

### 5.1 基金研究页

桌面工作区以扣除顶栏与外部 padding 后的可用内容高度作为基准，不直接使用整屏 `100vh`。

- 查询区固定约 30%，下方结果区约 70%；查询区包括名称、六位代码、管理公司、基金类别、申购状态、查询和重置按钮。
- 结果区只渲染基金结果 AG Grid；移除结果工具栏、保存视图入口、筛选标签、来源/状态说明、外置加载/错误文案及批量选择工具栏，并隐藏列设置和表格密度控件。结果区外层不绘制第二层卡片边框。查询区右上角提供通用折叠/展开箭头；展开时查询/结果约 30/70，收起后查询区折叠为白底占位栏，和结果区保留间距，结果表格扩展到其余可用高度。
- 页面顶部、父容器、section、共享表格容器与 table container 连续设置可用高度、`min-height:0`；表头和底部分页可见，中间表体内部滚动。表格无数据或加载时同样撑满结果区。
- 授权用户的单基金基本信息入口作为 AG Grid 行操作列保留；批量抓取入口由数据中心承载。
- 不套多层卡片，不让分页器随 200 行表体滚到视口之外；只保留一个表格分页器。
- 手机宽度及 200% 缩放允许查询控件自然换行或内部滚动，必要时放宽严格 20% 高度以保证可操作；不截断字段或制造整个页面横向滚动。

### 5.2 查询与 URL 状态

继续采用 URL 表示已应用的筛选、页码、排序，React Query key 包含完整参数。

- 新字段 `fund_code/company_name/sub_status` 纳入 URL、重置和请求。
- 基金代码用文本输入框，不用数字输入框；校验空值或 ASCII 六位数字，保留 `000001`。
- 公司与类别使用可搜索、可清除的 Mantine Select，清除即全部。
- 未支持的历史 URL 参数不因本次重构突然传给当前分类查询；保持已有相关测试定义的行为。
- 保留 `keepPreviousData`，但更新期间明确标注；关闭旧页行的选择/详情操作，避免把旧页数据当新页结果。
- 查询、排序及分页只更新应用内存路由；研究结果区不呈现保存视图控件。全站页面导航使用 React Router 内存路由，浏览器地址保持打开应用时的 path/query/hash。

### 5.3 基金结果 AG Grid

默认四个业务数据列：六位基金代码、基金名称、管理公司、申购状态。另保留详情动作列及授权用户的基本信息抓取行操作；不把旧分类/评分/规模等业务列继续塞进默认结果表。

- 使用 AG Grid Community `Infinite Row Model` 与 `datasource`；AG Grid 请求的 `startRow/endRow` 映射到现有 API 的一基 `page/page_size`。`cacheBlockSize` 与分页页尺寸保持一致，使用 AG Grid 自带分页面板，不另建外部分页器。
- datasource 成功响应同时传入当前页行与 API 的 `meta.pagination.total_items`，保证真实总数、最后一页及空/越界页正确显示。结果区不在 grid 外显示加载/错误工具区；Infinite Row Model 不依赖默认 loading overlay。
- AG Grid 的页索引为零基；URL/API 页码为一基。页码变化、页尺寸变化、服务端排序及应用筛选都同步更新 URL/React Query 参数，分页页尺寸只显示 20、50、200；排序或筛选回第 1 页。
- 服务端支持的四列可排序；将 AG Grid `sortModel` 白名单映射为 API `sort/order`。不启用 AG Grid 本地过滤、quick filter、分组或聚合，避免只对已加载数据操作而冒充全库查询。
- 用 `getRowId` 返回 `share_class_id`。Infinite Row Model 不提供内建全选；不显示误导性的全选框。每行选择保持由现有权限控制，页切换、筛选、排序后清空选择；即使当前页为 200 行，抓取操作最多提交 100 个去重后的 `fund_id`，达到上限时显示明确提示。
- 在共享 AG Grid 适配层提供中文文案、列隐藏、密度、列宽调整、粘性表头、分页、空态、错误态和加载状态；分页、排序与行操作可由业务组件受控，不封装第二套表格框架。
- 标准代码/名称为必需列，列布局偏好应迁移旧 key 或版本化，去除旧列 ID，并确保必需列不可全被隐藏。
- 保持目前翻页/更改已应用条件后清空选中的行为，不擅自新增跨页选择；批量抓取上限仍为 100，即使页面显示 200 行也不能全选提交 200 只。对同一产品不同份额选择，按既有抓取 `fund_id` 去重和计数。

### 5.4 双击详情窗口

本次新增的是站内 Mantine Modal，不使用 `window.open`，不新增浏览器弹窗依赖。

- 对数据行双击打开对应份额详情 Modal；点击选择框、按钮、链接或输入框不触发行级双击行为。
- 保留基金名称可键盘触达的详情入口；提供“查看详情”按钮作为双击的键盘/触屏等效操作。
- 从 `FundDetailPage.tsx` 提取可复用详情内容（建议新增 `FundDetailContent.tsx`），独立路由和 Modal 共享查询/Tab/因子分析内容，禁止复制整套详情实现。
- Modal 传入 `share_class_id` 及当前 `as_of_date`；窗口内不把 `product fund_id` 或六位代码错用于份额 NAV/Factor 查询。
- 现有产品级抓取和基本信息历史入口应保留正确 `fund_id`；提取内容时显式区分详情份额 ID 与产品公共 ID。
- Modal 有自己的受控 Tab/分析周期状态，不修改背景研究页 URL；独立详情路由仍保留原有 `tab/factor_period/return_to` 深链行为。
- 懒加载详情，关闭时停止窗口专属轮询和不必要查询；保留已有请求的取消/错误处理。
- 支持 Esc、关闭按钮、焦点陷阱和关闭后焦点恢复；手机可全屏呈现，Modal 内滚动不挤占背景表格。

## 6. 全站表格迁移清单

全站迁移必须包括列表、权限功能、详情、折叠区与图表数值替代，不能只改基金表。

| 文件 | 迁移对象 | 必须保留 |
|---|---|---|
| `frontend/src/components/DataTable.tsx` | 旧 TanStack/Mantine 自建渲染器 | 重构为共享 AG Grid React 适配层；列偏好、空态、grid 可访问名称与描述 |
| `frontend/src/features/funds/FundTable.tsx` | 基金结果 | 后端分页/排序、权限选择、抓取、详情窗口 |
| `frontend/src/pages/UniverseSnapshotPage.tsx` | `UniverseList` | 快照详情链接、完整集合说明 |
| `frontend/src/features/universe/UniverseTable.tsx` | 入选/排除成员 | 分数状态/原因、筛选证据、基金链接 |
| `frontend/src/features/portfolio/PortfolioList.tsx` | 组合列表 | 既有服务端分页、排序、授权可见性 |
| `frontend/src/features/ingestion/IngestionHistoryTable.tsx` | 任务历史 | 服务端分页、状态、任务详情操作 |
| `frontend/src/features/ingestion/IngestionTaskDetail.tsx` | 项级结果 | 服务端分页、尝试次数、来源/错误、轮询 |
| `frontend/src/features/funds/FundMetrics.tsx` | `EvaluationMetrics`、`ScoreMetrics` 两张表 | null/status/reason、数值格式与量纲 |
| `frontend/src/features/funds/FactorAnalysisPanel.tsx` | 每个 Accordion 分类中的表 | 因子周期、缺失原因、类别名称 |
| `frontend/src/features/funds/FundNavChart.tsx` | 隐藏的 NAV 数值表 | 图表可访问数值替代，不修改图表计算 |
| `frontend/src/features/backtest/BacktestPerformanceChart.tsx` | 隐藏的图表数值表 | 各视图真实数值、可访问展开入口 |
| `frontend/src/features/portfolio/DecisionReviewPanel.tsx` | 可编辑权重表 | 0–1 数据口径、百分比显示、校验、PM 权限与审计 |
| `frontend/src/features/portfolio/LivePortfolioPanel.tsx` | 三态数据可用性表 | Target/Pending/Actual 边界与来源缺失提示 |
| `frontend/src/features/portfolio/RebalancingPanel.tsx` | 再平衡能力/来源表 | 真实能力状态，不编造交易明细 |

`ClassificationReviewPage.tsx` 当前是列表/按钮/表单而非 table/grid，不强制改造成表格。CSS Grid、布局分栏、卡片布局不是数据表，不在“替换 grid”范围内。

迁移原则：完整已加载的小集合使用 AG Grid Client-Side Row Model 客户端分页/排序；已有 API 分页或大数据集使用 Community Infinite Row Model 与 datasource，将区块请求映射到服务端 API。小型静态状态/评分表可关闭分页和工具栏。图表数值替代表如分页，应明确可浏览全量已返回点；不能仅暴露首屏数值。`UNAVAILABLE`/null 不渲染成 0。权重编辑状态存在业务组件中，以稳定 fund/份额 ID 为键，不能因排序或翻页丢失。

## 7. 分任务实施步骤

### Task 1：升级 React/Mantine 并建立 AG Grid Community 底座

**修改**：`frontend/package.json`、`frontend/package-lock.json`、`frontend/src/main.tsx`（仅当入口样式或 Provider 需要调整）。

**新增建议**：`frontend/src/components/ResearchDataTable.tsx`、对应组件测试。

- [x] 将 `react` 与 `react-dom` 对齐到 `19.3.1`；将 `@types/react` 与 `@types/react-dom` 对齐到 `19.3.0`。
- [x] 将 `@mantine/core`、`@mantine/form`、`@mantine/hooks` 对齐到 `9.7.4`。Mantine 9 的官方最低 peer 要求为 React 19.2+；已核对 core 要求 `react/react-dom ^19.2.0` 且 hooks 精确为 `9.7.4`。
- [x] 将 `@testing-library/react` 对齐到 `16.3.3`；其 peer 范围包含 React/React DOM 19 和 React 类型 19。
- [x] 安装 `ag-grid-react` 与 `ag-grid-community`，二者固定同一准确版本 `36.2.0`；该版 `ag-grid-react` peer 范围包含 React/React DOM `^19.0.0`，与 `19.3.1` 相容。版本与 peer 依据在 2026-11-03 通过 npm registry 核验。
- [x] 只采用 AG Grid Community，不安装 `ag-grid-enterprise`、不启用需商业许可的模块；使用 Community 支持的 Infinite Row Model 支撑服务端分页。
- [x] 共享底座允许业务组件接入 AG Grid Infinite Row Model datasource；具体 `startRow/endRow`、排序、`rowCount` 到现有 API 的映射在 Task 5 实现，不用客户端全量加载来模拟服务端分页。
- [x] 遵守 Infinite Row Model 的选择限制：使用稳定 row ID；不提供网格自带 header select-all；选择操作只针对当前页并在页、筛选或排序变化时清空。
- [x] 审核 `frontend/package.json` 中直接依赖及开发依赖的 peerDependencies；只升级因 React 19、Mantine 9 或类型版本变化而不兼容的包，并记录升级前后版本及依据。不要把无关依赖机械升级到最新。
- [x] 保持 Mantine family 包版本一致；按 AG Grid 官方模块化安装说明注册实际使用的 Community modules，并使用官方 Quartz theme API；不新增无关日期或图标库。
- [x] 阅读 Mantine 官方 8.x → 9.x 迁移指南，修正迁移涉及的组件 API、样式和主题用法；不要顺带升级需要 Vite 主版本升级的插件。
- [x] 更新 `package-lock.json`，用 `npm ls` 核对无 peer dependency 冲突，并验证 MantineProvider、主题、入口样式与 React StrictMode。
- [x] 共享组件只提供中文文案、空态、密度、布局偏好、样式及默认功能；允许业务覆写 columns、pagination、sorting、row actions 和受控状态，避免封装成第二套表格框架。
- [x] 做一个最小表格测试，验证中文、空态、必需列、grid 可访问名称与新/旧列偏好恢复。
- [x] 暂时保留现有 `@tanstack/react-table`；完成 Task 7 全站迁移后，只有源码确认已无消费者才将其从 package.json/lockfile 删除。

**完成条件**：React、Mantine 与 AG Grid 依赖完成版本对齐，直接依赖 peer 检查无冲突；AG Grid Community 最小共享组件可构建并通过组件测试。

### Task 2：基金公司字段、采集同步与历史数据回填

**修改**：

- `src/fip/services/data_service/models/fund.py`
- `src/fip/services/data_service/ingest.py`
- 如需源字段映射：`src/fip/services/data_service/adapters/akshare/datasets.py`
- `tests/integration/test_fund_core.py`
- `tests/integration/test_ingest_service.py`
- `tests/integration/test_autogenerate_gate.py`

**新增建议**：`db/migrations/versions/0040_fund_company_name.py`、公司数据采集/回填专项测试。执行时先核对 Alembic head，目前为 `0039`；若变化使用新的唯一 revision。

- [x] 先测试旧基金可迁移、未知公司可为空、重复抓取幂等及历史版本保持。
- [x] 增加 `Fund.company_name: Mapped[str | None]`，`String(128)`、nullable，不使用伪“未知”默认值；超过长度的源值显式报数据问题，不能静默截断。
- [x] Alembic upgrade 添加列，downgrade 删除本迁移新增对象；不能重写已执行迁移。
- [x] 基本信息抓取同步获取基金详情源“基金公司”，验证六位基金代码一致后映射；不把“基金管理人”或基金经理自然人姓名当公司。
- [x] 抓取标准化在 `raw_fields["基金公司"]` 和 `normalized_fields.company_name` 中留存来源值，与历史快照/当前投影在同一事务提交；保留 `available_at`、原始数据引用与 hash/version 幂等机制。
- [x] 缺失/空白/NaN 公司字段不覆盖已有有效名称；源明确发生公司变更时生成新历史版本并更新最新投影。
- [x] 回填仅使用本地已留存历史快照，不访问网络；按每基金最新有效公司证据更新空投影，保留现有非空公司值，不修改旧 snapshot JSON。
- [x] 回填支持已规范化字段及已验证 raw 公司字段；无证据保持 NULL，不从无关联的管理公司维表猜测。
- [x] 如果回填量需要单独作业，提供显式 dry-run/批处理脚本与执行说明，不在迁移中发起全量网络抓取。
- [x] 本次未新增索引；迁移 autogenerate gate 通过。

**完成条件**：迁移/降级在专用测试库可验证；采集、缺失、变更、幂等及回填测试通过。

### Task 3：数据库端基金查询与公司选项端点

**修改**：

- `src/fip/api/repositories.py`
- `src/fip/api/fund_queries.py`
- `src/fip/api/routers/reads.py`
- `src/fip/settings.py`
- 如需分类查询复用：`src/fip/services/data_service/repositories/classification.py`
- `tests/api/test_fund_routes.py`
- `tests/api/test_repository_contracts.py`
- `tests/integration/test_api_fund_universe_repositories.py`

**新增建议**：`tests/integration/test_fund_list_sql_pagination.py`、公司选项 API 测试。

- [x] 测试错误关联不能匹配：供应商 ID 恰巧与某基金 ID 相同也不能串基金。
- [x] 覆盖多供应商、多历史映射、无映射、共管经理、多份额，确认唯一行与 total 一致。
- [x] 按第 4 节建立分页 SQL/SQLAlchemy 查询，可将复杂语句提取到专用查询模块，不继续膨胀公共 adapter。
- [x] 新增 repository 分页边界；将 `FundQueries.list` 迁移为真实委派；更新 seeded fake，保留 `list()` 非分页内部调用兼容。
- [x] 新参数校验、转义匹配和排序白名单，所有用户值绑定参数；旧筛选不能遗漏。
- [x] 按第 2.4 节测试九个类别和 UNKNOWN；当前可见最大 revision、有效区间及标签证据语义与现有实现一致。
- [x] 公司当前/历史投影与独立选项端点使用一致的数据口径。
- [x] 调整实际全局分页上限，使 200 行在默认 app 和预期运行配置可用；不放宽抓取等路由的特定限制。
- [x] 只对分页后的行补全兼容 DTO 字段，证明无全库 Python 切片和全库逐条 `_summary`。
- [x] 对查询计划、总数和数据快照一致性进行验证并记录；性能测试使用专用合成数据，不改真实业务数据。

**完成条件**：真实 PostgreSQL 测试证明代码/公司/类别/状态筛选、20/50/200 分页和稳定排序有效；旧详情/分类/抓取回归不失败。

### Task 4：契约同步及客户端生成

**修改**：

- `src/fip/api/schemas.py`
- `src/fip/api/app.py`（strict contracts 模型绑定）
- `src/fip/api/contract_registry.py`
- `frontend/openapi/m17.yaml`
- `frontend/src/api/http.ts`、`frontend/src/api/queries.ts`（按实际需要）
- `frontend/src/test/contractFixtures.ts`
- `tests/api/test_openapi_parity.py`、契约清单/嵌套/响应绑定测试
- 前端 `contract.test.ts`、`response-contracts.test.ts`、`http.test.ts`

- [x] 列表 payload 新字段与可空规则、分页 meta 标记、公司端点严格响应模型同步定义。
- [x] 为新端点补 strict binding/registry/契约 inventory，不仅修改 frozen YAML。
- [x] 保留 served frozen OpenAPI 与源契约一致；新增查询参数、sort 值和中文状态必须出现在契约中。
- [x] 生成客户端：`npm --prefix frontend run api:generate`；检查生成差异只来自规范变更。
- [x] API transport 解包保持现有 `{data,status,headers}` 方式，不把列表当裸数组；更新 meta 校验和未知值处理。
- [x] 更新所有消费基金列表的快搜、抓取范围表单和 fixture，旧参数继续可调用；CSV 多值参数不手改为另一编码形式。研究页最终不显示保存视图入口。

**完成条件**：接口契约/parity/strict 响应测试及前端客户端契约测试通过。

### Task 5：基金研究布局、筛选与 AG Grid 服务端分页

**修改**：

- `frontend/src/pages/FundResearchPage.tsx`
- `frontend/src/features/funds/FundFilters.tsx`
- `frontend/src/features/funds/FundTable.tsx`
- `frontend/src/features/funds/SavedFundViews.tsx`
- `frontend/src/components/PageLayout.tsx`、`PageLayout.module.css`（仅必要的高度接口）
- `frontend/src/components/Workbench.module.css` 或新增研究页 CSS module
- `frontend/src/features/funds/FundResearchPage.test.tsx`
- `frontend/src/features/funds/classificationFilters.test.ts`

- [x] 先用 MSW 测试五种查询条件正确进入请求，错误基金代码不发请求，reset/submit/sort/pageSize 回第 1 页。
- [x] 公司端点独立查询；类别九项使用 asset_class；展示申购状态占位说明。
- [x] 按最新要求固定 30/70；结果区只呈现 AG Grid，不显示外置工具栏/状态区或查询折叠控件。
- [x] AG Grid 四个数据列、受控后端排序分页，页尺寸 20/50/200，总数来自后端 meta。
- [x] 清除外部分页器及重复页尺寸输入；关闭只筛选当前页却像全库查询的 AG Grid 控件。
- [x] 保留授权用户的单基金基本信息行操作、网格分页/排序/空态和 URL 查询恢复；批量抓取入口由数据中心承载。
- [x] 新旧列偏好恢复安全，表体内滚动，分页/表头固定可见。

**完成条件**：页码换算、五个筛选、30/70 页面比例、grid-only 结果区与 200 行页尺寸经过组件和浏览器测试。

### Task 6：共用详情内容与双击 Modal

**修改**：`frontend/src/pages/FundDetailPage.tsx`、`FundTable.tsx`、基金研究页。

**新增建议**：`frontend/src/features/funds/FundDetailContent.tsx`、`FundDetailModal.tsx`、对应测试。

- [x] 测试双击行打开对应份额，选择框/按钮/链接不会误打开。
- [x] 提取可复用详情内容，路由模式与窗口模式显式提供各自的 Tab/周期状态适配。
- [x] 使用 share_class_id 请求份额详情/因子/NAV，产品公共 ID 用于原抓取入口；补同一产品两个份额打开不同 NAV 的测试。
- [x] 保留四 Tab、现有按需 Factor 查询、权限抓取入口及历史来源解释。
- [x] 测试关闭、Esc、焦点恢复、触屏/键盘替代、日期传播、背景 URL 与滚动位置保持。
- [x] 独立详情路由的 return_to 安全校验、刷新和深链继续通过现有测试。

**完成条件**：路由和 Modal 使用同一详情逻辑，不能出现两套相互不同的 Factor/抓取行为。

### Task 7：迁移其余全部业务表格

**修改**：第 6 节剩余清单及对应测试。

- [x] 候选池快照/入选/排除表迁移，完整集合可使用 AG Grid 客户端分页。
- [x] 组合列表迁移，连接现有 URL/API 分页；移除第二套外部分页器。
- [x] 抓取历史/项级结果迁移，保留后端分页、轮询、失败结果、取消/重试权限。
- [x] 评估/评分/Factor 分类表迁移，不改变数值格式、缺失原因和展开语义。
- [x] NAV/回测图表数值表迁移，保留 `ChartFrame` 的可访问数值入口，不修改图表或其算法。
- [x] PM 权重编辑表迁移，排序/分页后输入仍绑定正确基金，0–1 量纲、合计校验及 override 记录不变。
- [x] Live/Rebalancing 状态说明表迁移，不把缺失状态变成伪持仓或伪交易数据。
- [x] 全站复核源码中的 `Table`、原生 `<table>`、旧 `useReactTable`/`DataTable` 调用，确认没有漏迁移业务表；保留非表格布局 Grid。
- [x] 旧共享 DataTable 删除或成为兼容 AG Grid 适配，不同时保留两套真实业务渲染器。

**完成条件**：所有现有业务表格均由 AG Grid 渲染；默认中文，可访问名称、数据权限、空态和原业务动作无回归。

### Task 8：端到端验收、文档同步与交付记录

**修改/新增**：

- `frontend/e2e/m17.spec.ts`
- `frontend/e2e/client-workspace.spec.ts`
- 建议新增 `frontend/e2e/fund-research-ag-grid.spec.ts`
- `docs/10-api/02-fund-api.md`
- `docs/03-data/02-data-domain-model.md`
- `docs/11-database/04-database-design.md`、必要时 `03-erd.md`
- 建议新增 `docs/superpowers/acceptance/2026-11-03-fund-research-ag-grid.md`

- [x] 更新字段、正确关联、分页、公司来源、占位申购状态及版本依赖；不顺便重写历史计划。
- [x] 涉及内容变化的文档升版本、补变更记录、更新上游依赖声明并列出受影响的下游；先核对当前版本，不机械套用旧版本号。
- [x] 桌面 1440×900、1024×768、手机 390×844 及等效 200% 缩放验收；浏览器测量查询/结果约为 30/70，结果区只含表格。
- [x] 验证查询、分页 20/50/200、四列、总数、稳定排序、双击窗口、键盘替代、窗口关闭恢复及刷新 URL。
- [x] 回归全部表格，特别是隐藏数值表、PM 权重编辑和有权限抓取入口。
- [x] 执行测试与构建命令，记录命令、结果、失败输出和跳过原因，不用“应通过”代替实际结果。
- [x] 交付修改文件清单、迁移与回填说明、React/Mantine/直接相关库的版本与兼容依据、占位状态限制、未完成事项。

## 8. 测试矩阵与执行命令

### 后端必须覆盖

- 六位字符串前导零、非法代码、无有效映射、多供应商及历史重指派。
- 同产品多份额与同名产品的 stable row ID、详情定位、分页总数。
- 名称特殊字符及 SQL 注入形态输入按字面量处理。
- 公司为空/变更/回填/重复抓取/PIT，选项不随列表当前页变化。
- 九项类别、UNKNOWN、CANDIDATE/CONFLICT/PAUSED 不混同、可见 revision。
- 占位申购状态 `开放` 与不支持值 422，不改变生命周期和可投资性。
- 空集合、越界页、20/50/200、页码<1、超上限、各排序字段与同值稳定键。
- 旧 filters、strict contract、冻结 OpenAPI、资源权限与份额 Factor/NAV 回归。
- 真实 PostgreSQL LIMIT/OFFSET/COUNT 路径；不能只以 fake API 测试证明后端分页。

### 前端主要回归文件

- `frontend/src/features/funds/FundResearchPage.test.tsx`
- `frontend/src/features/funds/FundDetailPage.test.tsx`
- `frontend/src/features/funds/FactorAnalysisPanel.test.tsx`
- `frontend/src/features/funds/FundNavChart.test.tsx`
- `frontend/src/features/universe/UniverseTable.test.tsx`
- `frontend/src/features/universe/UniverseSnapshotPage.test.tsx`
- `frontend/src/features/portfolio/PortfolioDecisionPage.test.tsx`
- `frontend/src/features/portfolio/LiveAndRebalancing.test.tsx`
- `frontend/src/features/ingestion/IngestionScopeForm.test.tsx`
- `frontend/src/features/backtest/BacktestPerformanceChart.test.tsx`
- `frontend/src/components/components.test.tsx`
- `frontend/src/test/accessibility.test.tsx`
- 前端 API 契约与新共享 AG Grid/Modal 测试。

jsdom 的 ResizeObserver/mock 不能证明真实高度与虚拟滚动正确；尺寸、焦点与滚动必须通过 Playwright 验证。

### 建议命令

在仓库根目录执行，按任务选用；集成测试执行前必须确认专用测试库：

```bash
# 后端语法、类型、接口回归
make lint
make typecheck
make api-check

# 数据迁移与查询集成回归（会重置专用测试库）
LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest \
  tests/integration/test_fund_core.py \
  tests/integration/test_ingest_service.py \
  tests/integration/test_api_fund_universe_repositories.py \
  tests/integration/test_fund_list_sql_pagination.py \
  tests/integration/test_autogenerate_gate.py -q -m integration

# 客户端生成及定向前端测试
npm --prefix frontend run api:generate
npm --prefix frontend run test -- --run \
  src/features/funds/FundResearchPage.test.tsx \
  src/features/funds/FundDetailPage.test.tsx

# 前端全量检查：格式、lint、单测、build、e2e
make frontend-check

# 完整后端回归（同样涉及专用测试库）
make check
```

新建测试文件后再使用其路径运行。Playwright 默认会启动本地 API 与 Vite，并依赖项目 Python 环境和浏览器；记录环境问题，不能称为业务测试通过。`data-ingestion-live.spec.ts` 含真实写入，未经明确授权不作为普通验收执行。

## 9. 最终验收清单

- [x] `fund.fund.company_name` 存在，采集可填充，旧数据可安全回填，无来源为 NULL。
- [x] 查询通过份额映射关联，无 `f.id=pfi.provider_id` 错误连接。
- [x] 六位基金代码保持字符串；内部基金标识、份额标识和展示代码没有混用。
- [x] PostgreSQL 实际完成全部筛选、去重计数、稳定排序和分页，不加载全库后切片。
- [x] 管理公司下拉来自全库公司选项端点，不限于当前页。
- [x] 基金类别九项均可选，使用 asset_class，旧 fund_type 兼容。
- [x] 申购状态固定 `开放` 的限制有明确提示，不冒充真实可投资性。
- [x] 研究页查询区约 30%、结果区约 70%；结果区只含 AG Grid，分页器持续可见。
- [x] 基金表默认四列，页尺寸 20/50/200，200 行不被全局中间件拒绝。
- [x] 双击打开正确份额详情 Modal；键盘/触屏有等效入口，关闭恢复焦点和研究状态。
- [x] 全站所有现有业务表格均使用 AG Grid，图表数值替代和编辑表也已覆盖。
- [x] 现有授权单基金抓取、PIT、null/status/reason、权重编辑及深链无回归；研究页不再提供批量抓取选择工具栏。
- [x] OpenAPI、严格模型和生成客户端一致，文档治理步骤完成。
- [x] 实际测试和构建结果已记录；阻塞、失败或跳过事项如实列出。

## 10. 变更记录

| 版本 | 日期 | 内容 | 影响范围 |
|---|---|---|---|
| v1.0 | 2026-11-03 | 初版：公司字段与来源回填、正确供应商关联、SQL 分页、基金研究布局/筛选/详情窗口、全站数据表迁移及验收任务 | Fund Data、基金查询 API、前端表格与相关契约/数据库文档 |
| v1.1 | 2026-11-03 | 按用户修订更新基础查询，使用两次 LEFT JOIN 并统一份额别名为 fsc；删除“实际模型中”的重复说明段，保留后续实施约束 | 本计划第 2.1 节；上游依赖不变，无需级联其他文档 |
| v1.2 | 2026-11-03 | 按用户要求移除 Mantine React Table，改用仓库已有 TanStack Table；将 React/React DOM 升至 19.3.1，Mantine core/form/hooks 对齐 9.7.4，并要求审查受影响的直接依赖 | 本计划技术栈、表格迁移任务、依赖验证与验收清单 |
| v1.3 | 2026-11-03 | 按用户补充改用 AG Grid Community 替代 Mantine React Table/TanStack Table；锁定 `ag-grid-react` 与 `ag-grid-community` 36.2.0，采用 Community Infinite Row Model 服务端分页，并写明其行选择限制及无 Enterprise 依赖约束 | 本计划共享表格实现、基金服务端分页、全站表格迁移和最终验收；产品与 API 目标不变 |
| v1.4 | 2026-11-04 | 完成 Task 1–8 实施与验收记录；补记抓取后基金/公司缓存刷新、已卸载请求失效及 PIT 公司来源同快照有效值回退修复，详见第 11 节和验收报告 | 本计划执行状态、Task 8 与最终验收清单；代码实现见对应文件 |
| v1.5 | 2026-11-04 | 按后续 UI 要求将研究页固定为 30/70，并移除结果区除 AG Grid 外的工具栏/说明及查询折叠控件；批量抓取由数据中心承载 | 第 5 节研究布局、Task 5 与最终验收清单；浏览器验收四种视口 |
| v1.6 | 2026-11-04 | 按后续 UI 要求，在查询区加入向上/向下箭头折叠控件，并删除申购状态占位说明和管理公司不可用说明 | 第 5.1 节、Task 5 及基金研究页交互验收 |
| v1.7 | 2026-11-04 | 按后续 UI 要求，查询区收起后保留白底占位栏及与表格的间距；研究页网格隐藏列设置和表格密度控件，只展示 AG Grid | 第 5.1 节、Task 5 及基金研究页折叠态验收 |
| v1.8 | 2026-11-04 | 根据布局复核移除结果区外层卡片边框，避免与 AG Grid 自身边框叠加 | 第 5.1 节及基金研究页布局视觉验收 |
| v1.9 | 2026-11-04 | 按交互要求移除查询折叠箭头 hover 时的背景高亮 | 第 5.1 节及箭头交互验收 |
| v1.10 | 2026-11-05 | 按用户要求改为内存 route：全站跳页、研究筛选及网格分页留在应用路由，不更新浏览器地址栏 | App 路由、基金研究页分页状态、导航和端到端 URL 验收 |
| v1.11 | 2026-11-05 | 按用户澄清将 `company_name` 来源改为基金详情“基金公司”（华夏基金、易方达基金等），排除“基金管理人”及经理姓名，并在基本信息任务同步抓取 | Task 2 基金公司来源映射、PIT 回退键、当前投影、公司筛选/列表与来源契约 |

## 11. Codex 执行记录（实施时填写）

| 任务 | 状态 | 修改摘要 | 验证命令与实际结果 | 阻塞/限制 |
|---|---|---|---|---|
| Task 1 | 完成 | React 19.3.1、Mantine 9.7.4 与 AG Grid Community 36.2.0；新增共享研究表格和 v1/v2 布局偏好兼容；修复 React/Mantine 迁移涉及的类型变更 | `npm ls --all` 通过；`npm run build` 通过；`npx tsc -p tsconfig.app.json` 通过；相关 ESLint/Prettier 通过；ResearchDataTable 4/4、PortfolioDecisionPage 7/7 通过；独立代码审查通过 | 全量可访问性测试曾 CPU 持续占用且未完成，已停止；Task 5 仍需接入服务端 datasource 与外部筛选选择清理；npm audit 报 44 项漏洞，未运行自动修复 |
| Task 2 | 完成 | 新增可空 `fund.fund.company_name`、可逆 0040 迁移；从已验证的“基金管理人”原始字段同步当前投影与历史快照；增加本地快照分批回填和默认 dry-run CLI | 专用数据库 `fip_task2_company_20261103`：定向单测/集成及 autogenerate gate 44/44 通过；迁移升降级保留已有基金行；`make typecheck`、Ruff 与 `git diff --check` 通过；独立代码审查通过 | 仅对 `fip_test` 做过只读来源核验（5,650 条）；没有执行回填。之后应用数据库需先审阅 dry-run 输出并显式指定 `--apply` |
| Task 3 | 完成 | 实现 PostgreSQL 一基分页、筛选/排序/唯一份额计数、PIT 分类及公司选项端点；更新公司/基金代码/占位申购状态参数和 200 行上限；严格对齐 UNKNOWN 与 ACTIVE_EQUITY 规则 | 专用库 `fip_task3_fundlist_20261103` 上 SQL/API/分类回归 59 通过；Ruff、全项目 mypy 通过；200 条合成数据 `EXPLAIN (ANALYZE, BUFFERS)` 约 2.05 ms；独立代码审查通过 | 严格 `FundListPayloadModel`、served OpenAPI 和客户端生成由 Task 4 完成；在 Task 4 前整体 API 契约尚未就绪。AUM/管理公司 ID 来源缺失时明确报错 |
| Task 4 | 完成 | 新增专用基金列表/公司选项严格 envelope；同步 strict binding、contract registry/inventory、冻结 M1.7 OpenAPI 与 Orval 客户端；保留逗号分隔筛选并更新 transport 的 placeholder metadata/UNKNOWN 处理 | 后端严格契约/OpenAPI 30 通过；Task 3 SQL 集成 18 通过；前端契约/transport/query 26 通过；构建、UTF-8 typecheck、Ruff、Prettier、`git diff --check` 通过；独立审查通过 | 完成 Task 4；完整研究页消费和保存视图交互属于 Task 5 |
| Task 5 | 完成 | 基金研究页采用 AG Grid Community Infinite Row Model；五个筛选、独立公司选项、服务端排序分页及 20/50/200 页大小；页面、筛选和分页状态留在内存路由，浏览器地址不变；查询折叠态保留白底栏/间距，网格隐藏列/密度控件及外层重复边框 | 研究页/共享表格/App Vitest 40/40；冻结浏览器套件首轮 35/40，5 项旧 UI 断言已更新，随后对这 5 项复测 5/5；build、目标 ESLint/Prettier、diff-check 通过 | 没有对修改后的 40 项冻结套件再跑一次全量；批量抓取由数据中心承载 |
| Task 6 | 完成 | 抽取路由与 Modal 共用 FundDetailContent；详情、净值、评价、评分、因子使用 share_class_id，产品级抓取和历史使用 fund_id；增加行双击及键盘/触屏详情入口，保持四 Tab、权限、PIT/来源和路由状态 | 定向 Vitest 31/31，详情可访问性/API 错误 8/8，Playwright 10/10；build、TypeScript、针对性 ESLint/Prettier、diff-check 通过；独立代码审查通过 | 扩展可访问性套件在原 home/navigation 用例 CPU 持续占用后停止；复核记录一个轻微项：切出因子 Tab 后独立详情链接不保留当前 factor_period。未启动抓取 |
| Task 7 | 完成 | 候选池、组合、抓取历史/项级结果、评估/评分/因子、NAV/回测数值、PM 权重编辑、Live/Rebalancing 表格均迁到共享 AG Grid；删除旧 DataTable 与 TanStack Table 依赖；组合/抓取保留服务端 API 分页及 URL/轮询语义 | 定向组件测试 65/65（11 个文件，无跳过）；冻结 API Playwright 6/6，最终加载期间浏览器返回 2/2；build、全量 ESLint（0 errors，77 generated warnings）、定向格式检查、源码审计及 diff-check 通过；Task 7 独立复核与两轮分页修复复核通过 | 全前端/accessibility 套件仍因既有 home/navigation CPU 持续占用无法完成；第一轮复核发现的旧页覆盖竞态已在两轮修复与复核后关闭；构建 large-chunk 与既有路由/颜色环境提示仍存在 |
| Task 8 | 完成 | 同步 API v1.7/数据域 v1.9/物理设计 v1.11；冻结浏览器验收、四视口 20/80 与收起100%、安全分页兼容及错误详情修复；独立审查后修复抓取缓存刷新/旧请求竞态与 PIT 公司名回退边界 | 冻结 Playwright40/40，精确收起高度追加6/6；其余前端27文件165/165；最终研究页17/17；最新查询/研究页测试23/23；API99/99、mypy152文件、build/ESLint/format通过；全分支审查通过 | 全量前端/可访问性未完成，既有 CPU 占用问题；全项目 Ruff16个既有分类问题；新增 PIT 集成回归因未配置专用测试库而未运行；未执行真实抓取、迁移或回填，未 commit/push/deploy |
