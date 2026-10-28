# 客户版投研平台布局与基金数据抓取中心实施计划

> **For agentic workers:** 执行本计划前先确认接口和权限方案；随后按任务顺序实现。逐项更新复选框，每项包含契约、界面和验收。此计划覆盖客户侧工作台重构和独立基金数据抓取中心。

**Goal:** 将现有开发型投研页面升级为面向外部客户的专业投研平台，并在独立“数据抓取”菜单中支持基本信息和 NAV 数据的单只、多只及全量基金任务。

**Architecture:** 以统一客户工作台外壳承载基金研究、候选池、组合、回测和数据中心；页面只调用真实 API，不提供演示数据。数据抓取采用预览快照、服务端范围解析、持久化异步作业和分页结果，保留现有单只/批量接口兼容已有调用方。

**Tech Stack:** React 18、TypeScript、Vite、Mantine、TanStack Table、React Query、React Router、ECharts、FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、Orval。

**Spec:** 本文第 1–5 节是本次重构的产品与接口基线；现有业务和安全约束继续遵循 `docs/superpowers/plans/2026-10-20-research-workbench-product-delivery.md`、`docs/acceptance/research-workbench-delivery.md`、`docs/10-api/06-m17-frontend-contracts.md` 与 `frontend/openapi/m17.yaml`。

## 全局约束

- 这是外部客户使用的客户门户体验；生产交付必须使用已验证身份和资源级授权，不新增伪登录或可编辑身份头。
- 任何全量抓取都必须先展示服务端预览数量、数据源支持情况和影响范围，再经有权限用户确认。
- 全量范围定义为“预览时基金库内符合范围条件的基金快照”，不代表上游数据源中基金库尚未登记的全部基金。
- NAV 抓取按已登记份额类别和数据源可提供的完整历史处理；AKShare 当前不支持起止日期参数，不增加虚假的日期范围控件。
- BASIC_INFO 与 NAV 是互相独立的数据集选择；一个任务只能执行一种数据集。
- 多只基金显式勾选上限为 100 只；全量基金使用服务端范围快照，不把完整基金 ID 清单传到浏览器。
- 缺少数据源映射的基金必须在预览和结果中计数并说明，不得静默丢弃或令整批任务无法查看其他成功项。
- 任务请求、范围快照、审计、幂等键、分页状态和重试均由服务端负责；浏览器不计算权威状态或虚构进度。
- 前端继续使用 Mantine、TanStack Table、React Query、React Router 和 ECharts；不新增第二套组件库。
- Orval 生成代码只能通过修改 OpenAPI 源文件并运行 `npm run api:generate` 更新，不得手改 `frontend/src/api/generated/`。
- 不在 `localStorage` 保存客户持仓、凭证、完整任务结果或授权信息；只允许保存版本化的布局和列偏好。
- 响应式目标为 1440×900、1024×768、390×844；所有页面在 200% 缩放、键盘操作和 reduced-motion 下可用。

---

## 1. 产品目标与信息架构

### 1.1 客户侧导航

建立清晰的客户工作区，顶部保留品牌、当前工作区/身份、基金快速定位、帮助入口和真实 session 状态；左侧主导航为：

1. 工作台
2. 基金研究
3. 候选池
4. 组合管理
5. 策略回测
6. 数据抓取（仅展示给有 `can_manage_data_ingestion` 权限的会话）
7. 分类复核（仅展示给有 `can_review_classifications` 权限的会话）

`/` 和 `/home` 进入工作台概览，不再直接重定向到基金列表。概览只呈现实际 API 返回的基金库数量、组合数量、近期任务状态和数据可用时间；现有 API 无法提供的字段显示“暂不可用”或从概览移除，不用静态数字、模拟行情、模拟账户或伪造资讯填充。

数据抓取成为唯一完整的操作入口。基金详情和基金列表可保留“去数据抓取”快捷入口，通过 URL 预选基金和数据集；不会在多个页面维护不同的抓取表单或结果状态。

### 1.2 数据抓取范围语义

| 范围 | 选择方式 | 服务端含义 |
|---|---|---|
| 单只基金 | 按基金名称/代码搜索并选中 1 只 | 处理此基金当前有效的数据源映射 |
| 多只基金 | 搜索并跨页勾选 2–100 只 | 仅处理明确选中的基金；预览显示映射可用/不可用数量 |
| 全量基金 | 选择基金库全量，或叠加已有基金筛选条件 | 固定预览时命中的基金成员快照；新增基金不会混入已提交任务 |

- BASIC_INFO 的目标数量按基金计数；同一基金有多个份额类别映射时按当前规则选择有效基本信息来源，并在任务详情列出实际来源。
- NAV 的目标工作量按已登记份额类别计数，同时摘要按基金聚合；结果可展开到份额类别、估值日范围和数据源。
- 预览至少返回：匹配基金数、可抓取基金数、缺少映射数、目标基金/份额类别数、数据源、范围摘要、快照 ID 和过期时间。
- 提交确认显示数据集、基金数、NAV 份额类别数（适用时）、预计范围、不可抓取项、来源及任务提交人。
- “全量”默认指平台基金库全量。用户可选择现有基金查询条件作为范围；界面必须将“基金库全量”和“当前筛选结果”分开标注。

### 1.3 客户平台视觉方向

采用“专业金融终端的清晰信息层级 + 现代客户门户的工作区氛围”：深午夜蓝导航和品牌区、明亮高对比数据画布、青绿/电蓝少量强调色，工作台头部可使用克制的蓝青渐变与细网格纹理。表格、风险指标、来源质量与图表主体保持高可读性；渐变只用于品牌和页面标题区，不遮挡数据。

设计取材为公开产品特征的归纳，不复制品牌商标或具体页面：Interactive Brokers Client Portal 把账户概览、可配置仪表组件与深入的 Portfolio 页面联通；Morningstar Direct 将投资筛选、组合分析和风险暴露纳入同一研究工作流；Koyfin 展示自定义 dashboard、watchlist 和可复用表格视图。[IBKR Client Portal 导航说明](https://www.interactivebrokers.com/campus/trading-lessons/navigating-and-trading-using-ibkrs-client-portal/)、[Morningstar Direct 组合管理](https://www.morningstar.com/business/products/direct/portfolio-management-tool)、[Koyfin 自定义 Dashboard](https://www.koyfin.com/features/custom-dashboards/)。本计划据此推导出“概览到详情的连续导航、可配置但有权限边界的工作区、可保存的表格视图、真实数据来源可追溯”；该推导是设计选择，不代表这些产品披露了本系统的业务需求。

### 1.4 布局规则

- 桌面采用 240px 深色侧栏、64px 顶栏和 12 栏内容画布；主内容最大宽度 1600px，页边距 28px。
- 侧栏支持收起；移动端改为抽屉式导航。顶栏保留品牌、快速定位、当前身份和帮助/通知入口；只有有真实功能的入口才渲染。
- 每页只有一个 h1；标题、说明、面包屑、日期/来源上下文和主操作占固定位置，加载时不跳动。
- 工作台概览使用“欢迎/工作区上下文 + 研究入口 + 真实任务动态”结构。模块点击后进入对应详情；不展示缺少 API 支持的 P&L 或持仓收益。
- 数据表采用可配置列、紧凑但易读的密度、状态语义、来源/数据日期和局部横向滚动。列视图保存带 schema 版本。
- 页面背景使用 `#F3F6FB`，主内容 `#FFFFFF`，侧栏 `#101827`，主文字 `#17243A`，青绿强调色 `#14B8A6`，蓝色辅助强调 `#3B82F6`。全部颜色必须实测 WCAG AA；涨跌颜色沿用中国市场红涨绿跌并同时标明正负号。
- 圆角 4–8px，表单/表格/内容区不嵌套卡片；用分区标题、留白、细分隔线组织信息。过渡动画不超过 160ms 且遵循 `prefers-reduced-motion`。
- 字体使用 `Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif` 回退；数值使用 tabular nums，金额/日期/比例沿用现有格式器。

## 2. API 和作业契约

当前有 `POST /api/v1/funds/{fund_id}/ingestions`、最大 100 只的 `POST /api/v1/fund-ingestions`、按基金读取历史、以及单任务 `GET /api/v1/ingestions/{operation_id}`。没有范围预览、全量基金快照、全局任务列表、任务结果分页或取消接口；当前 Worker 一次把整份 `subjects` 列表处理完并写入单个 JSON `result_payload`。全量范围不能直接复用现有 100 只批量请求或无限增大的 `result_payload`。

新增兼容端点，保留现有单只/批量端点和生成客户端调用，供新数据中心使用：

```python
class FundIngestionFilters(StrictModel):
    fund_name: str | None = None
    fund_type: list[str] | None = None
    lifecycle_status: list[str] | None = None
    investment_eligibility: list[str] | None = None
    asset_class: str | None = None
    strategy: str | None = None
    geography: str | None = None
    product_structure: str | None = None
    market_attributes: str | None = None
    classification_status: str | None = None

class SingleFundScope(StrictModel):
    type: Literal["SINGLE"]
    fund_id: str

class SelectedFundsScope(StrictModel):
    type: Literal["SELECTED"]
    fund_ids: list[str] = Field(min_length=2, max_length=100)

class AllFundsScope(StrictModel):
    type: Literal["ALL"]
    filters: FundIngestionFilters | None = None

FundIngestionScope = Annotated[
    SingleFundScope | SelectedFundsScope | AllFundsScope,
    Field(discriminator="type"),
]

class FundIngestionPreviewRequest(StrictModel):
    dataset: Literal["BASIC_INFO", "NAV"]
    scope: FundIngestionScope

class FundIngestionPreview(StrictModel):
    preview_id: str
    dataset: Literal["BASIC_INFO", "NAV"]
    scope_type: Literal["SINGLE", "SELECTED", "ALL"]
    fund_count: int
    supported_fund_count: int
    unavailable_mapping_count: int
    subject_count: int
    source: str
    expires_at: datetime

class FundIngestionJobRequest(StrictModel):
    preview_id: str
```

OpenAPI `oneOf` 范围变体示例：`{"type":"SINGLE","fund_id":"000001"}`、`{"type":"SELECTED","fund_ids":["000001","000002"]}`、`{"type":"ALL","filters":{"lifecycle_status":["NORMAL"],"asset_class":"EQUITY"}}`。`filters` 只接受现有 `listFunds` 已支持的筛选字段；不另造基金分类语义。

新增路由：

- `POST /api/v1/fund-ingestion-previews`：授权后计算只读范围预览，创建短时、绑定用户/数据集/范围摘要的 `preview_id`。
- `POST /api/v1/fund-ingestion-jobs`：携带 `preview_id` 和 `Idempotency-Key` 提交任务。服务端验证 token 属于当前用户、未过期且范围未变化；变化时返回 409 并要求重新预览。
- `GET /api/v1/fund-ingestions`：带页码、状态、数据集和范围类型过滤的全局任务历史；普通用户仅见本人有权查看的任务，管理员按现有 capability 读取更大范围。
- `GET /api/v1/ingestions/{operation_id}/items`：按基金/份额类别状态分页返回项级结果，支持筛选 `PENDING|RUNNING|SUCCESS|FAILED|SKIPPED|CANCELLED`。
- `POST /api/v1/ingestions/{operation_id}/cancel`：请求取消；Worker 完成当前份额类别后停止剩余项，保留已完成数据和审计记录。
- `POST /api/v1/ingestions/{operation_id}/retry-failed`：创建关联的新操作，仅重试失败项；成功项不重新抓取。

全量/大批量操作以 `CalculationJob` 作为父操作，使用 Alembic 新迁移建立项级持久化表，例如 `fund_ingestion_run_items`：外键到 operation、基金/份额类别、项状态、尝试数、成功摘要/错误码、开始/结束时间；唯一约束为 `(operation_id, fund_id, share_class_id)`。范围成员在提交时固化，运行期间按 keyset 分页读取。修改 `JobOutcome`/`JobExecutor` 使一次 claim 只处理一个有界 chunk，更新真实 `completed/total` 进度并以 RUNNING 重新释放租约；无项剩余时写入 SUCCESS/PARTIAL_SUCCESS/FAILED 业务摘要，取消时把未处理项标记 CANCELLED。原始响应和基金/NAV 修订继续使用现有追加式存储及幂等规则。

新增权限 `can_manage_full_universe_ingestion`（默认 false），覆盖 ALL 范围和取消/重试全量父任务；现有 `can_manage_data_ingestion` 仍控制单只与不超过 100 只的 selected 操作。API 每个读写端点都验证用户和 operation 资源归属；前端隐藏菜单仅是体验层防护。

## 3. 文件组织与公共接口

| 文件 | 职责 |
|---|---|
| `frontend/src/app/theme.ts` | 午夜蓝工作台 theme、颜色、字体和密度 token |
| `frontend/src/app/global.css` | 文本、焦点环、页面背景、溢出、reduced-motion |
| `frontend/src/components/PageLayout.tsx` | 角色/权限导航、客户工作区顶栏、移动抽屉和 route frame |
| `frontend/src/components/PageLayout.module.css` | 深色侧栏、顶栏和主内容网格 |
| `frontend/src/app/routes.tsx` | `/home`、`/data-ingestion` 和权限路由 |
| `frontend/src/pages/WorkspaceHomePage.tsx` | 使用真实摘要/任务数据的客户工作台首页 |
| `frontend/src/pages/DataIngestionPage.tsx` | 独立数据中心页面和 URL 状态 |
| `frontend/src/features/ingestion/IngestionScopeForm.tsx` | BASIC_INFO/NAV、单只/多只/全量范围表单和预览确认 |
| `frontend/src/features/ingestion/IngestionHistoryTable.tsx` | 全局分页任务表、状态过滤和来源/提交人 |
| `frontend/src/features/ingestion/IngestionTaskDetail.tsx` | 进度、项级结果分页、取消和失败项重试 |
| `frontend/src/api/queries.ts`, `frontend/src/api/mutations.ts` | 预览/提交/历史/详情/取消/重试 React Query hooks |
| `src/fip/api/schemas.py` | 预览、scope、submission 和分页任务响应模型 |
| `src/fip/api/routers/fund_ingestions.py` | 新数据中心路由；保留原端点兼容 |
| `src/fip/api/context.py`, `src/fip/api/auth.py` | full-universe capability 来源和授权策略 |
| `src/fip/platform/jobs/models.py`, `executor.py`, `worker.py` | 有界、可恢复、可取消的批次处理 |
| `src/fip/platform/jobs/fund_ingestion.py` | 项级处理、重试边界、增量计数和任务结束摘要 |
| `src/fip/services/data_service/models/fund_ingestion.py` | 抓取范围快照及项级运行模型；在 `db/migrations/env.py` 注册 ORM 模型 |
| `db/migrations/versions/0038_fund_ingestion_scopes.py` | 预览/范围项/结果分页所需的持久化表和索引 |
| `frontend/openapi/m17.yaml` | 新接口源契约 |
| `frontend/src/api/generated/*` | 通过 Orval 生成，禁止手工改 |
| `docs/STARTUP_GUIDE.md`, `docs/acceptance/research-workbench-delivery.md` | 启动 Worker、权限、真实数据与验收门槛 |

`IngestionScopeForm` 与 API 共用的 TypeScript 表单类型：

```ts
type FundIngestionDataset = "BASIC_INFO" | "NAV";
type FundIngestionFilters = Pick<
  ListFundsParams,
  | "fund_name"
  | "fund_type"
  | "lifecycle_status"
  | "investment_eligibility"
  | "asset_class"
  | "strategy"
  | "geography"
  | "product_structure"
  | "market_attributes"
  | "classification_status"
>;
type FundIngestionScope =
  | { type: "SINGLE"; fund_id: string }
  | { type: "SELECTED"; fund_ids: string[] }
  | { type: "ALL"; filters?: FundIngestionFilters };
```

表单先调用 preview；用户确认后只提交 `preview_id`，不提交 UI 自行拼装的全量基金清单。路由 query 参数只传 `dataset`、`scope_type`、单只 `fund_id` 或短期 selected IDs（最多 100）；preview token 与任务结果不得放 URL。

## 4. 实施任务

### Task 1：客户工作区外壳与视觉系统

**文件:** 修改 `frontend/src/app/theme.ts`、`global.css`、`routes.tsx`、`components/PageLayout.tsx`、`PageLayout.module.css`；新增 `pages/WorkspaceHomePage.tsx`、`pages/WorkspaceHomePage.module.css`。

- [x] 写路由/壳层验收覆盖主导航、active state、能力菜单、移动 drawer、身份加载/错误、404 和 `/` 到 `/home`。
- [x] 建立前述主题 token 和 sidebar/header/content layout；内容 max-width 1600px，侧栏桌面宽 240px、收起宽 68px、顶栏高 64px。
- [x] 顶栏基金快速定位使用现有基金搜索 API；提交后以 URL 编码的 `fund_name` 参数进入基金研究页，例如 `/funds?fund_name=%E5%8D%8E%E5%A4%8F`，不显示不存在的证券/全平台搜索结果。
- [x] 按 session capability 条件显示“数据抓取”“分类复核”；权限未读取时显示 loading，读取失败时不暴露写操作。
- [x] 新建 `/home` 工作台：基金总数、组合数、正在运行的抓取作业仅消费真实 API；无数据/接口错误显示统一状态，不使用静态 KPI。
- [x] 对新壳和首页运行 `cd frontend && npm test -- --run src/app/App.test.tsx src/test/accessibility.test.tsx`、`npm run lint`、`npm run build`。
- [x] 提交：`feat(ui): add customer investment workspace shell`。

### Task 2：基金数据抓取范围预览和持久化契约

**文件:** 新增 `tests/api/test_fund_ingestion_scope_contract.py`、`tests/unit/test_fund_ingestion_scope.py`、`tests/integration/test_fund_ingestion_batch_worker.py`；修改 `src/fip/api/schemas.py`、`src/fip/api/routers/fund_ingestions.py`、`src/fip/api/auth.py`、`src/fip/api/context.py`、`src/fip/platform/jobs/models.py`、`src/fip/platform/jobs/executor.py`、`src/fip/platform/jobs/worker.py`、`src/fip/platform/jobs/fund_ingestion.py`、`db/migrations/env.py`、`frontend/openapi/m17.yaml`；新增 `src/fip/services/data_service/models/fund_ingestion.py` 和迁移 `db/migrations/versions/0039_fund_ingestion_scopes.py`。

- [x] 在 API tests 中覆盖 scope oneOf 校验、单只/selected 1–100、all filters allowlist、预览过期/跨用户使用、未知基金/无映射、full-universe 无权限、重复幂等提交和 409 范围变化。
- [x] 新建 preview storage：绑定 actor、dataset、规范化 scope、命中的基金/份额映射摘要、过期时间和稳定 scope hash；查询只返回计数，不向客户端返回全量成员。
- [x] 新建项级 run model/migration；创建时冻结预览成员，按 `(operation_id, fund_id, share_class_id)` 唯一键保存项状态。
- [x] 将 worker 从整份 `subjects` 一次处理改为每次最多 50 个项；每个 chunk 后提交进度与项结果，租约过期后从下一项恢复；临时服务异常保留可重试状态。
- [x] 在 `JobExecutor` 中支持 RUNNING chunk outcome；只有所有成员终态时写入 operation 完成状态和 SUCCESS/PARTIAL_SUCCESS/FAILED 摘要。
- [x] 实现 item 分页、取消和 retry-failed；取消只停止未处理项，失败重试创建新 operation 并引用原 operation。
- [x] 保留旧单只及旧 100 只批量路由；在 `/api/v1/fund-ingestion-previews`、`/api/v1/fund-ingestion-jobs` 和新增 GET history/item routes 添加 typed response models。
- [x] 在 `frontend/openapi/m17.yaml` 更新契约，运行 `cd frontend && npm run api:generate`；不得改生成结果手稿。
- [x] 运行目标 API/unit tests、`ruff check src tests`、`mypy`，以及 `npm run build`；数据库集成测试只能在隔离数据库运行。
- [x] 提交：`feat(api): add scoped fund ingestion jobs`。

### Task 3：独立数据抓取中心

**文件:** 新增 `frontend/src/features/ingestion/IngestionScopeForm.test.tsx`；新增 `frontend/src/pages/DataIngestionPage.tsx`、`frontend/src/pages/DataIngestionPage.module.css`、`frontend/src/features/ingestion/IngestionScopeForm.tsx`、`IngestionHistoryTable.tsx`、`IngestionTaskDetail.tsx`；修改 `frontend/src/app/routes.tsx`、`frontend/src/components/PageLayout.tsx`、`frontend/src/api/queries.ts`、`frontend/src/api/mutations.ts`、`frontend/src/features/funds/FundIngestionPanel.tsx`。

- [x] 在 MSW/组件验收中覆盖两种 dataset、三个范围、preview、取消确认、过期 token、无权限、全量长任务、部分成功、项级重试和详情刷新恢复。
- [x] 将 `/data-ingestion` 加为有权限客户的独立菜单；用户直接打开无权限 URL 时显示 403 解释和返回工作台入口。
- [x] 页面头部显示“基金数据中心”、数据源和最近更新时间；设置两个 dataset 控件：“基本信息”和“NAV 与分红/拆分”。
- [x] 实现单只基金搜索、跨页 100 只 selected 管理、全量基金及已有筛选范围；每次变更范围或 dataset 都重新预览。
- [x] Preview 区展示基金数量、NAV 份额类别数、缺少来源映射数、快照过期时间和来源；全量/selected 提交前用 Modal 显示提交范围、历史抓取语义和不可抓取数量。
- [x] 历史列表支持按数据集/状态/范围/时间筛选、服务端分页和打开 operation；全量任务显示真实完成数/总数、成功/失败/跳过，不把处理项数伪装成百分比。
- [x] 任务详情以列表分页查看 fund/share-class 结果；支持取消未完成项和仅重试失败项；成功后刷新基本信息/NAV 查询缓存。
- [x] 基金详情的抓取区改为“在数据中心抓取”链接，带预选 `fund_id` 和 `dataset`；基金列表的批量操作转为“将所选基金加入数据抓取”，不在旧页面直接提交另一套任务。
- [x] 运行 `cd frontend && npm test -- --run src/features/ingestion/IngestionScopeForm.test.tsx`、`npm run lint`、`npm run build`。
- [x] 提交：`feat(ui): add dedicated fund ingestion center`。

### Task 4：现有投研页面统一改为客户平台视觉语言

**文件:** 修改 `pages/FundResearchPage.tsx`、`FundDetailPage.tsx`、`UniverseSnapshotPage.tsx`、`PortfolioDecisionPage.tsx`、`BacktestPage.tsx`、`features/funds/*`、`features/universe/*`、`features/portfolio/*`、`features/backtest/*` 及共享表格/图表样式。

- [x] 建立逐路由截图和断言：标题层级、来源/日期、主要动作、状态标签、错误/空/部分失败、侧栏 active state 和客户 capability。
- [x] 基金研究改为筛选栏 + 保存视图/列偏好 + 结果表；表格行使用收益/风险状态和来源上下文，不增加 API 不支持的收益统计。
- [x] 基金详情按“基金身份与分类、净值、业绩风险、评分归因、数据来源”分区；指标 tab 保留 URL 恢复、有效日期和无数据原因。
- [x] 候选池、组合决策、回测页面共用统一 PageHeader、工作区间距、明确主次动作和一致的状态/数值展示；保持已有业务 API 与返回 URL 语义。
- [x] 图表使用模块化 ECharts import、有效数据源标识、键盘可读表格和空值断线；图表与表格颜色满足 AA 对比度。
- [x] 删除客户界面中仅服务开发人员的假身份/模拟实盘/再平衡入口；按权限将分类复核作为操作菜单展示。
- [x] 在 1440/1024/390px 检查基金研究、详情、组合各 tab、回测和数据中心；运行相关 frontend component tests、`npm run lint`、`npm run build`。
- [x] 提交：`feat(ui): restyle research workflows for client portal`。

### Task 5：安全、启动、性能和客户验收

**文件:** 修改 `docs/STARTUP_GUIDE.md`、`docs/acceptance/research-workbench-delivery.md`、必要的 `start.sh` 和部署配置；新增 `frontend/e2e/client-workspace.spec.ts` 与隔离环境 `frontend/e2e/data-ingestion-live.spec.ts`。

- [x] 建立身份/租户验证清单：全量抓取 capability 默认拒绝、task/item 资源授权、审计 actor、管理菜单可见规则；测试不得使用生产身份或生产数据库。
- [x] 静态 fixture 测试覆盖 401/403/409/422/429/500、preview 过期、all scope 未映射、Worker 中断后恢复和取消后剩余项状态。
- [ ] 隔离 live 场景验证：单只基本信息、单只 NAV、多只 selected、全量 preview/提交/进度/分页结果/失败重试，确认数据库修订、audit actor 和 operation 状态一致。
- [x] 检查直接打开/刷新 `/home`、`/data-ingestion`、operation URL，确认不会重复提交任务；端口已占用时启动脚本不复用未知服务。
- [x] 运行 Playwright `1440×900`、`1024×768`、`390×844`、200% zoom 和键盘路径；检查 reduced-motion、focus return、局部表格滚动与长错误文本。
- [x] 运行 `npm run format:check`、`npm run lint`、`npm run build`、定向 Vitest 和 fixture E2E；记录版本、服务 URL、数据集和截图路径。
- [ ] 隔离 live E2E：需真实身份、数据源凭证与明确隔离的可写验收库，当前未运行。
- [x] 更新启动文档：`./start.sh --with-worker` 需要 PostgreSQL、migration head 和数据源网络；列出客户权限配置和所有真实业务缺口。
- [x] 仅在全部验收证据齐全且真实身份/隔离 API/Worker/DB 可用后标记客户发布可交付；否则明确列出受阻项。
- [x] 提交：`docs: record client workspace rollout and acceptance`。

## 5. 验收清单

- [x] 新客户工作区拥有一致、清晰、响应式的全站布局；主导航按 capability 展示，主要页面无散落的内部工具视觉。
- [x] 工作台首页只显示 API 支持的真实数据；无数据、无权限、失败和过期数据都有明确状态。
- [x] “数据抓取”是独立主菜单；基本信息和 NAV 两种类型均可独立选择。
- [x] 单只、2–100 只明确选择、平台基金库全量/筛选全量三种范围均能预览和创建任务。
- [x] 全量请求不提交庞大基金 ID 数组；预览成员快照和 actor 绑定，过期/变化必须重新预览。
- [x] 全量任务按项分页、能显示真实计数、重启后可恢复、可取消剩余项、仅失败项可重试。
- [x] 任务失败或无来源映射不会隐藏成功项，也不会将缺失值当作成功或零值。
- [x] 直接 URL、刷新、前进/后退、导航返回均保留用户可恢复的列表筛选/选中基金；不把授权信息写到 URL。
- [ ] 生产身份提供方、资源/租户授权、Worker、PostgreSQL、Alembic head 和数据源网络通过隔离环境验证。
- [ ] 每条验收由实际输出、DB/worker 证据或截图支撑；未验证项保持未通过，不能以视觉完成替代 API/数据交付。

## 当前验收边界（2026-10-29）

Task 1–4 的实现、定向回归和 fixture 浏览器验收已完成。Task 5 的本地 fixture/API、启动入口、缩放/键盘/刷新验收和文档更新已完成；`client-workspace.spec.ts` 5/5 通过，live spec 默认 1 skipped。隔离 live 抓取测试已实现为 `frontend/e2e/data-ingestion-live.spec.ts`，仅当显式开启 `FIP_INGESTION_LIVE_TESTS=true`、数据库 URL 指向 `fip_test`、提供隔离基金代码、当前 actor 拥有的失败操作 ID（`FIP_LIVE_FAILED_OPERATION_ID`）并设置 `FIP_LIVE_CONFIRM_WRITES=true` 时执行；当前未运行，因此生产身份、真实数据源网络及写入/重试链路尚无 live 证据。客户发布状态保持未验收。
