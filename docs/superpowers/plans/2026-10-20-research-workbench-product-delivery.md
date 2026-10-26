# 专业投研工作台完整产品体验交付计划

> **For agentic workers:** 使用 `superpowers:executing-plans` 按任务执行；只有获得委派授权后才使用子代理。逐项更新复选框，先失败测试再实现。本计划覆盖全部现有业务页面，不允许只交付外壳或几个样板页后宣布完成。

**Goal:** 将当前接口展示型前端改造成统一、专业、可操作、可追溯的浅色基金投研工作台，并通过真实业务联调、响应式、无障碍和发布验收。


**Architecture:** Mantine 提供应用外壳、表单、弹窗、主题和交互控件；CSS Grid/Flexbox 负责页面排布；TanStack Table 提供表格逻辑，由 Mantine Table 渲染；react-resizable-panels 仅用于确需并排操作的组合与回测工作区。保留现有 React Query、Router、ECharts 和生成 API 客户端，不重写金融计算。

**Tech Stack:** React 18、TypeScript、Vite、Mantine、CSS Modules、TanStack Table、react-resizable-panels、React Query、React Router、ECharts、Vitest、Testing Library、Playwright、lucide-react。

**Spec:** 本文第 1–6 节是已商定方向的执行设计基线；业务规范为 `docs/01-product/04-functional-requirements.md`、`docs/10-api/06-m17-frontend-contracts.md`、`frontend/openapi/m17.yaml` 和实盘再平衡现有契约。后端交付依赖见 `docs/superpowers/plans/2026-10-20-core-workflow-delivery.md`。

**交付状态:** 实现进行中，尚未验收。已落地应用主题/外壳、共享组件、基金/候选池/组合/回测页面改造及基金数据抓取入口；测试、真实服务联调、响应式截图和发布验收未完成。详细状态见 `docs/acceptance/research-workbench-delivery.md`。

## 1. 完整交付范围

所有任务都属于本次计划，不采用“先做样板、其余以后补”的范围安排。任务顺序只是依赖顺序，不是缩减承诺。

| 业务入口 | 必须交付的视图与操作 |
|---|---|
| 应用外壳 | 导航、面包屑、标题、身份状态、当前环境、路由恢复、404 |
| 基金研究 | 查询、中文筛选、排序、分页、列管理、日期上下文、基金基本信息抓取、进入详情和返回恢复 |
| 基金详情 | 主数据、净值、业绩风险、评分归因、来源与可用性解释、基金基本信息及 NAV 抓取操作和状态 |
| 候选池列表 | 快照检索、策略/日期/规则筛选、进入快照 |
| 候选池详情 | 入选与排除成员、条件证据、排除原因、基金详情跳转 |
| 组合列表 | 可见组合、状态、分页、详情入口 |
| 组合配置与优化 | 组合概览、合法请求表单、异步状态、权重/风险/约束/不可行诊断 |
| 决策复核 | 自动关联决策、审批/拒绝/覆盖、理由、确认、权限、审计 |
| 实盘 | Target/Pending/Actual、现金、权益、估值日期、成交回报 |
| 再平衡 | 评估、触发原因、重算范围、成本收益、交易清单、历史事件 |
| 回测 | 创建、校验、执行、任务恢复、绩效、基线、成本、偏差及可用性 |
| 通用体验 | 加载/空/错误/部分失败、格式化、表单验证、键盘操作、窄屏适配 |
| 产品交付 | 真实联调、截图、回归、安全边界、构建发布、启动与交接说明 |

不新增营销首页、假数据总览大屏、基金推荐、自动下单、账户登录协议、策略发布后台或当前无契约支持的创建/导出功能。没有下载文件或创建资源接口时，不放一个无效按钮。

## 2. 产品可交付与后端依赖

### 2.1 两套结论必须分开

- **体验实现完成:** 全部页面按本文改造，组件/契约/交互/响应式测试通过。
- **产品可交付:** 上述基础上，真实 API、数据库与 Worker 跑通业务，数据和状态可恢复，所有强制验收场景有证据。
- 后端任务处理器缺失、实盘使用固定假持仓、回测没有真实引擎时，产品验收结论必须为“不可交付”，不允许只因 UI 测试通过就宣称可上线。
- 可以继续完成不依赖阻塞的任务，但必须维护阻塞清单，不能把缺失业务移出交付范围或默默切到演示模式。

### 2.2 必须对齐的依赖

| 工作台能力 | 后端门槛 | 本计划对应任务 |
| --- | --- | --- |
| 研究/候选池 | 可读取真实 PIT 基金、评价、评分与快照 | T06–T09 |
| 优化与复核 | 核心计划 Phase A 的计算、结果、决策和权限 | T10–T12 |
| 回测 | 核心计划 Phase B 的真实引擎和报告 | T15 |
| 实盘/再平衡 | 核心计划 Phase C 的持久化、回报、重算 | T13–T14 |
| 生产身份 | 实际认证接入和资源授权 | T04、T18 |
| 基金基本信息与 NAV 抓取 | 后端提供有权限的抓取任务触发、状态/结果查询、幂等与审计；采集 Worker 可访问已配置数据源并持久化原始响应及规范化数据 | T06–T07；后端契约未就绪时列为产品阻塞 |

后端缺口记录：端点、请求、实际状态/错误码、预期行为、对应核心计划任务、复现步骤。不要重写后端计算以绕开依赖。确需扩展契约时先写明变更依据与兼容方案，获得确认后实施，不擅自发明接口。

## 3. 技术与安全约束

- Mantine 替代此前 Ant Design 建议；不安装 Ant Design、MUI、AG Grid 或第二套表格封装框架。
- 安装前核对 Mantine、React 18、TypeScript 与 panels 的 peerDependencies 和公开 API；锁定经过验证的兼容版本，更新已有包管理锁文件。不能照抄另一个版本的组件 API。
- 最小依赖为 `@mantine/core`、`@mantine/hooks`、`@mantine/form`、`react-resizable-panels`、`lucide-react`。日期优先原生 date input；需要日期选择器时再安装同版本 `@mantine/dates` 及其所需依赖。
- 使用项目现有 npm。若存在锁文件采用 npm ci 验证干净安装；不得删除锁文件解决依赖冲突，也不升级 React 大版本。
- 保留现有 URL 和 API 请求口径；不得手改 `src/api/generated/`。Mantine 只替换呈现，不改变权限和金融语义。
- 不在浏览器计算权威评分、PIT、可投资性、目标权重、交易成本或审批权限。
- 默认真实模式，无自动回退 fixture；MSW 仅测试启用。不得在生产 bundle 引入测试数据。
- 不以 localStorage 保存认证令牌、持仓、审批内容和完整请求响应；可保存版本化的列宽、列显隐、侧栏状态和分栏比例。
- 金额、百分数和权重传输口径保持不变，不能在提交时重复乘除 100。
- 不添加“这是某种设计风格”“如何使用本系统”等可见功能介绍。业务标签、风险原因、校验说明和必要操作确认应清楚准确。
- 修改前确认用户已有改动；不重置、不自动建分支、不提交、不合并。
- 仅前端工作不需要数据库迁移或清库。真实联调用隔离环境；后端集成测试会清空测试库 schema，未确认隔离不得运行。
- 缺少认证提供方时，不新增伪登录页或把可编辑身份头当成生产认证。

## 4. 设计系统基线

### 4.1 视觉令牌

| 项目 | 定值或规则 |
|---|---|
| 主背景 | `#F4F6F8` |
| 主内容 | `#FFFFFF` |
| 主文字/次文字 | `#20262D` / `#596572` |
| 分隔线 | `#DCE2E7` |
| 主强调色 | `#087F8C`，深色 hover，浅色仅作少量选中背景 |
| 成功/警告/危险 | `#237A50` / `#9A6700` / `#B42318`；文字/图标共同表达 |
| 收益涨跌 | 默认中国市场红涨绿跌；明确正负号，不把收益下跌等同业务错误 |
| 图表系列 | 青绿主线、蓝色 Benchmark、灰色等权基线、红色回撤；不依赖颜色区分 |
| 圆角 | 输入 4px，个别框定工具/弹窗不超过 8px |
| 间距 | 4/8/12/16/24/32px |
| 字号 | 正文/表格 14px，辅助 12px，区块 16px，页标题 22px，行高不小于 1.4 |
| 字体 | 优先思源黑体/Noto Sans SC，回退 PingFang SC/Microsoft YaHei/sans-serif；离线回退不阻断 |
| 数字 | `font-variant-numeric: tabular-nums`，数值右对齐 |
| 字距 | 0；不按 viewport 缩放字号 |
| 表格密度 | 默认行高约 44px，紧凑模式约 36px，控件高度 32–36px |

用 Mantine theme 覆盖组件 token，CSS Modules 负责业务布局，不堆叠任意内联像素。主题检查以 WCAG AA 为准，色值并非豁免；不达标时调整色阶并记录。

### 4.2 布局与响应式

- 桌面侧栏 224px，可折叠至 64px，顶部 56px；内容 padding 24px，窄屏 16px。
- `>=1280px` 组合/回测可用双栏；`768–1279px` 单主栏或紧凑两栏，不能把表单压到不可读；`<768px` 抽屉导航、单栏与 Tabs。
- 全局禁止横向溢出；仅表格和相关性矩阵等固定格式区域允许局部横向滚动。
- 不使用卡片嵌卡片。页面区块用标题、分隔线、Grid/Flex 排布，只有真正框定的工具和弹窗使用边框容器。
- 页面只保留一个 h1；主操作固定在标题操作区，不随数据加载跳动。
- panels 默认组合左侧配置约 35%、右侧结果约 65%；以安装版本对应的公开 API 定义比例和最小尺寸。窄屏卸载分栏而非强行保留拖动线。
- 分隔线可键盘调整、有可访问名称；保存布局需要 schema version，非法值、旧版本和存储异常均能恢复默认。

## 5. 页面与路由契约

保留 `/funds`、`/funds/:fundId`、`/universes`、`/universes/:universeId`、`/portfolios`、`/portfolios/:portfolioId`、`/backtests`。

- 列表筛选、页码、排序保留 URL 语义；详情选项卡可增加 `tab` 查询参数。
- 返回列表恢复原筛选、页码和日期；优先通过合法内部 returnTo 或已保留的查询参数，禁止任意外部跳转。
- 组合详情可使用 `tab=optimization|decision|live|rebalance`；回测使用 `backtest_id`、`operation_id` 恢复服务端资源。ID 参数必须验证与当前资源关联，不把 URL 当授权依据。
- 优化结果如有决策关联，直接提供复核入口；没有关联字段时按契约明确查询，不让用户把猜测出的 ID 当业务流程。
- 当前日期和数据截止日期不是同一个值。全局显示只读业务日期摘要，筛选日期只影响当前支持该参数的页面；不假装所有端点共享一个全局 PIT 日期。
- 当前无回测列表接口时，不伪造历史列表；恢复已知回测 ID 支持直链，另提供明确的“打开已有回测”入口。

## 6. 文件组织与共享接口

新增文件都应先检查是否已有等价模块；复用现有的 `PageLayout`、`ErrorState`、`MetricValue`、`ProvenanceBar`、`OperationProgress` 与两个解释链组件，不并行再造一套。

| 文件 | 职责 |
|---|---|
| `frontend/src/app/theme.ts` | Mantine theme、业务状态和图表令牌 |
| `frontend/src/app/global.css` | 基础字体、根节点、焦点、全局溢出与 reduced-motion |
| `frontend/src/components/PageLayout.module.css` | AppShell 内容与标题布局 |
| `frontend/src/components/PageHeader.tsx` | 页面标题、面包屑、主操作区 |
| `frontend/src/components/QueryState.tsx` | 加载、空状态与部分数据刷新状态 |
| `frontend/src/components/StatusBadge.tsx` | 中文枚举与语义状态呈现 |
| `frontend/src/components/DataTable.tsx` | TanStack Table + Mantine Table 基础渲染 |
| `frontend/src/components/ChartFrame.tsx` | 固定图表高度、尺寸观察、错误/空数据与文本替代 |
| `frontend/src/components/WorkbenchPanels.tsx` | 桌面可调分栏、窄屏单栏、布局偏好 |
| `frontend/src/components/Workbench.module.css` | 表格、工具条与通用工作区样式 |
| `frontend/src/test/render.tsx` | 带 Mantine/Query/Router 的测试包装 |
| `frontend/e2e/workbench.spec.ts` | 可控响应下的交互与布局回归 |
| `frontend/e2e/workbench-live.spec.ts` | 不拦截业务 API 的真实联调 |
| `docs/acceptance/research-workbench-delivery.md` | 执行证据、截图索引、阻塞与最终结论 |

新增组件公共接口以如下签名为实现起点；消费方不得各自改出不兼容版本：

```tsx
type PageHeaderProps = {
  title: string;
  breadcrumbs: { label: string; href?: string }[];
  actions?: React.ReactNode;
  context?: React.ReactNode;
};

type StatusBadgeProps = {
  domain: "lifecycle" | "eligibility" | "operation" | "optimization" | "decision" | "backtest";
  value: string;
};

type WorkbenchPanelsProps = {
  layoutKey: "portfolio" | "backtest";
  primary: React.ReactNode;
  secondary: React.ReactNode;
  primaryLabel: string;
  secondaryLabel: string;
};
```

DataTable 接收 TanStack `Table<TData>`、可访问名称和空状态；业务模块自行创建 columns、手动/客户端分页状态。不要在共享表格内发送 API 请求或隐式二次排序。

## 7. 执行顺序与测试约定

`T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → T17 → T18`。

除 T00 基线与 T18 交付外，各任务均执行：先写指定反例并确认失败 → 最小实现 → 重跑目标测试 → lint/typecheck/build 相关检查 → 更新验收记录。测试环境无法运行时明确阻塞，不能用静态阅读代替通过。

下文 `npm run` 命令均在 `frontend` 目录执行。`npm run build` 包含现有 TypeScript 检查；不要编造仓库不存在的 typecheck 脚本。

### Task T00：安全基线与能力清单

**文件:** 阅读 `frontend/package.json`、`playwright.config.ts`、`src/app/routes.tsx`、`src/api/http.ts`、冻结契约及核心交付计划；创建验收记录。

- [ ] 记录工作区改动、Node/npm、已有依赖和锁文件；不输出环境密钥。
- [ ] 运行 `npm run check`，逐项记录旧失败，禁止先删断言求绿。
- [ ] 为所有路由记录已有功能、API、权限、状态、恢复方式和后端阻塞。打开真实界面留存改造前桌面/窄屏截图。
- [ ] 检查 Playwright 当前会启动或复用 8000/4173 的配置，验证服务身份；不得把其他项目的同端口服务当本项目后端。
- [ ] 创建 `docs/acceptance/research-workbench-delivery.md`，按路由和任务记录证据，初始结论为未验收。

**验收:** 清楚区分代码存在、fixture 可展示与真实 API 可用；已知后端缺口逐项关联核心计划。

### Task T01：依赖、主题与统一测试包装

**文件:** 修改 `package.json`、实际锁文件、`src/main.tsx`、`src/testSetup.ts`、`src/app/App.tsx`；新增 theme/global.css/test render；扩展 `src/app/App.test.tsx`。

- [ ] 核对 peerDependencies 后安装兼容 Mantine/form/hooks、lucide 和 panels，不安装另一套 UI 库。
- [ ] 先写 Provider 环境下路由渲染与错误状态测试，确认新 Provider/样式尚未接入导致的失败。
- [ ] 导入 Mantine 必需样式后导入 global.css，MantineProvider 放到应用统一入口，保留 QueryClientProvider 和 Router，禁止重复 Router。
- [ ] 建立主题令牌与共享图表 palette。配置中文字体回退、tabular nums、焦点环、reduced-motion，不下载无许可字体。
- [ ] 更新现有测试的 render 包装和 ResizeObserver/matchMedia 必要模拟；不能把图表或交互组件全 mock 掉掩盖问题。
- [ ] 执行 `npm test -- --run src/app/App.test.tsx src/test/accessibility.test.tsx`、`npm run lint`、`npm run build`。

**验收:** 页面在真实 MantineProvider 下渲染，原有请求/路由测试不退化，锁文件可重复安装。

### Task T02：应用外壳与导航

**文件:** 修改 `src/components/PageLayout.tsx`、`src/app/App.tsx`、`src/app/routes.tsx`；新增 PageHeader、布局 CSS；扩展 App/accessibility 测试。

- [ ] 先测试当前路由导航高亮、嵌套路由归属、折叠、移动抽屉和未知路由。
- [ ] 用 AppShell 实现侧栏、顶部、内容区；四个主入口为基金研究、候选池、组合决策、回测分析。
- [ ] 业务页面使用统一 PageHeader；不再每个页面重复生成主导航，避免双 main 或重复 h1。
- [ ] 图标使用 lucide；纯图标操作提供 aria-label 和 Tooltip；导航键盘可达，进入页面关闭移动抽屉。
- [ ] 显示真实 session 身份状态与开发环境标识；无 session 能力时诚实显示未知，不伪造用户或登录成功。
- [ ] 增加可键盘访问的跳至内容链接和 404 返回入口；移动 Drawer 有正确焦点回收。
- [ ] 执行 `npm test -- --run src/app/App.test.tsx src/test/accessibility.test.tsx`，浏览器验证宽屏与 390px。

### Task T03：状态、数值、来源与错误组件

**文件:** 修改 `MetricValue.tsx`、`Formatters.ts`、`ErrorState.tsx`、`ProvenanceBar.tsx`、`OperationProgress.tsx`；新增 QueryState/StatusBadge；扩展 components/http 测试。

- [ ] 测试数值 0、负值、null、未知枚举、UNAVAILABLE、数据不足、401/403/404/409/422/429/5xx 与网络错误。
- [ ] 统一金额/比例/日期/评分显示，不用 truthy 判断隐藏零；null 显示状态和原因，不画为零点。
- [ ] 英文状态映射为中文标签，未知值中性回退并可查看原值；不把所有非成功状态渲染成红色。
- [ ] 来源默认保留日期、PIT 和质量摘要，展开显示版本；重要质量警告与缺失契约字段不能藏在默认折叠区。
- [ ] 错误提供对应恢复动作、请求 ID 和安全详情，显示 Retry-After；不把错误转空列表。只读查询可重试，写操作不可盲目重试。
- [ ] 异步任务同时呈现作业状态和业务状态，真实进度未知时用不定进度，禁止编造百分比。
- [ ] 执行 `npm test -- --run src/components/components.test.tsx src/api/http.test.ts src/api/helpers.test.ts`。

### Task T04：表单、确认与安全写操作

**文件:** 改造已有各业务表单；共享反馈复用 Mantine Alert/Modal，不创建万能表单生成器；扩展各 feature 测试。

- [ ] 先写失败测试覆盖字段错误、服务端 422、双击提交、取消确认、无权限、提交后返回失败。
- [ ] 用 Mantine useForm 和有标签的输入控件；英文枚举改 Select/MultiSelect，数值用 NumberInput，二元选项用 Checkbox/Switch。
- [ ] 明确 required 与可选项、数值范围、时间顺序和百分比显示/提交转换；不能为通过表单而填入假的策略版本。
- [ ] 审批、拒绝、覆盖和成交回报有确认页或 Modal，展示资源、动作和影响；只有实际成功后才显示成功反馈。
- [ ] pending 时防重复点击；重试同一语义写入应复用幂等键，新的请求生成新键，不把每次重试变成新交易。
- [ ] 未保存改动离开时按风险级别提示，提交成功清理草稿；不把持仓或复核内容持久化到浏览器。
- [ ] 检查真实鉴权与 403；前端隐藏/禁用仅作体验，不能替代服务端校验。

**验收:** 所有写表单都遵循相同错误、确认与 pending 规则，不留下可绕过验证的替代按钮。

### Task T05：共享表格与可访问分栏

**文件:** 新增 DataTable/WorkbenchPanels/Workbench.module.css；复用 TanStack；新增 `src/components/workbench.test.tsx`。

- [ ] 测试固定表头、空状态、列显隐、排序方向、分页回调、长名称、横向滚动与键盘分隔线。
- [ ] 表格使用 Mantine Table 渲染 TanStack 行模型；数字右对齐，名称和 ID 分层，状态列一致，交互按钮阻止误触行导航。
- [ ] 服务器分页列表采用 manualPagination/manualSorting，只发送服务端声明支持的 sort 值；不把当前页排序误呈现为全市场排序。
- [ ] 列显隐不能隐藏必要的名称/主要动作；偏好键带表格类型和版本，损坏存储能恢复默认。
- [ ] panels 仅用于组合与回测；支持最小宽度、可见拖动柄、键盘调整和布局重置；窄屏改为单栏/标签。
- [ ] 运行 `npm test -- --run src/components/workbench.test.tsx`，再跑 `npm run build` 验证泛型与组件版本 API。

### Task T06：基金研究完整工作页

**文件:** 修改 `pages/FundResearchPage.tsx`、`features/funds/FundFilters.tsx`、`FundTable.tsx`；扩展 `FundResearchPage.test.tsx`。

- [ ] 先测 URL 初始化、提交筛选重置页码、返回恢复、空结果/错误、服务端排序和中文多选序列化。
- [ ] 实现搜索主栏、类型/生命周期/资格多选、日期和高级筛选；查询/重置使用明确命令，已选条件可单独移除。
- [ ] 保留逗号分隔参数作为 HTTP 序列化细节，不要求用户输入逗号或英文枚举。
- [ ] 工具条显示真实结果数量、刷新状态、列设置；不能增加接口没有返回的收益/评分统计。
- [ ] 表格只展示真实可用字段；基金名称可进入详情，保留日期和返回列表上下文。
- [ ] 查询中保留旧数据时标记正在更新，禁止让用户误认为旧结果已符合新筛选。
- [ ] 增加基金基本信息抓取入口：可按单只基金触发，也可对当前查询结果中明确勾选的基金批量抓取（单次最多 100 只）；展示授权范围、来源、触发人、开始/结束时间、处理数量、成功/失败数量和失败原因。
- [ ] 抓取采用服务端任务契约，界面展示排队/运行/成功/部分成功/失败状态；支持查看结果和安全重试。重复点击、并发任务和重试由服务端幂等控制，前端不伪造进度或成功结果。
- [ ] 基本信息更新保留来源与 `available_at`/抓取时间，按字段记录原始值、规范化值和校验状态；不得用缺失值覆盖已有有效值，冲突或未映射字段进入可追溯的异常结果。
- [ ] 后端尚无任务触发、状态查询或权限契约时，不添加无效按钮；将所缺端点、权限、任务状态及数据源能力登记为产品阻塞，并继续完成可独立交付的读取体验。
- [ ] 执行 `npm test -- --run src/features/funds/FundResearchPage.test.tsx`，Playwright 验证筛选与返回恢复。

### Task T07：基金详情、净值和评分归因

**文件:** 修改 `pages/FundDetailPage.tsx`、`FundNavChart.tsx`、`FundMetrics.tsx`、`ScoreExplainChain.tsx`；扩展 FundDetailPage 测试。

- [ ] 先测直链、未知 tab 回退、返回上下文、不同模块独立失败、null 指标与日期一致性。
- [ ] 头部呈现基金名称/代码/份额/分类/状态/Benchmark；信息按业务含义分组，不平铺全部版本号。
- [ ] 使用 Mantine Tabs 组织净值、业绩风险、评分归因；每个 tab 直接链接且可刷新恢复。
- [ ] 只有服务端支持的周期可发请求；切换后 queryKey、请求参数与标题同步，不通过前端编造缺失周期。
- [ ] 净值图区分复权口径与估值日期；指标标注单位、周期与不可用原因；回撤和恢复时长、VaR/CVaR按业务要求联合展示。
- [ ] 增加该基金 NAV 抓取操作：默认补齐数据源可提供的完整历史；明确份额类别、数据源与抓取范围，提交前展示影响范围并确认。当前 AKShare 接口没有起止日期参数，不提供虚假的区间控件。
- [ ] 展示 NAV 任务状态、请求区间、成功/失败条数、最新有效估值日、来源与失败原因；可查看任务结果，失败时仅按服务端幂等键安全重试，不重复写入相同业务事实。
- [ ] NAV 以份额类别和估值日为业务键保存；上游修订生成新版本并保留 `available_at`/版本历史，不能覆盖历史可见状态。图表和指标按当前可见版本读取，必要时可查看修订记录及来源。
- [ ] 原始 NAV 与复权 NAV 分开呈现；复权值或调整因子不可用时明确标注不可用，不以原始 NAV 回填。抓取完成不代表复权已完成，也不代表数据已通过质量校验。
- [ ] 后端尚无 NAV 抓取任务和历史查询契约时，不发明前端接口或显示虚构结果；登记缺少的任务、状态、版本/修订历史及权限契约为交付阻塞。
- [ ] 评分展示五个子分、完整度、同类群体、归因链与不可用项，不把高分说成买入建议。
- [ ] 执行 `npm test -- --run src/features/funds/FundDetailPage.test.tsx src/components/components.test.tsx`。

### Task T08：候选池列表

**文件:** 修改 `pages/UniverseSnapshotPage.tsx` 列表部分和 `UniverseFilters.tsx`；复用 DataTable；扩展 UniverseSnapshotPage 测试。

- [ ] 测试策略/日期/规则筛选 URL、空结果、接口失败和返回恢复。
- [ ] 快照列表由无样式 ul 改为结构化表格，显示 ID、策略、日期、真实成员数、规则版本和详情入口。
- [ ] 没有完整策略目录接口时，保留有标签的策略 ID 输入，不生成假选项；若选项来自已加载列表明确其覆盖范围。
- [ ] 没有服务端分页时，只能对完整已返回集合做本地分页，并明确总数来自该集合；不伪造分页请求。
- [ ] 执行 `npm test -- --run src/features/universe/UniverseSnapshotPage.test.tsx`。

### Task T09：候选池详情与排除证据

**文件:** 修改 UniverseSnapshotPage 详情部分、`UniverseTable.tsx`、`ConditionList.tsx`；扩展同一测试文件。

- [ ] 测试 SELECTED/REJECTED 两类成员、未知状态、条件缺失和基金详情跳转日期。
- [ ] 快照摘要展示策略、决策时间、资格规则与是否使用评分；不把“未使用评分”误标异常。
- [ ] 入选/排除采用带数量 Tabs；条件详情通过行展开或 Drawer 展示条件、实际值、阈值、结果与来源。
- [ ] 排除原因必须能读到具体失败项，不能只显示红色“未入选”；未返回条件值时明确不可用。
- [ ] 执行 `npm test -- --run src/features/universe/UniverseSnapshotPage.test.tsx` 并验证长条件文本窄屏不遮挡。

### Task T10：组合列表与概览

**文件:** 修改 PortfolioDecisionPage 列表/概览、`PortfolioList.tsx`、`PortfolioOverview.tsx`；扩展 PortfolioDecisionPage 测试。

- [ ] 测试列表分页、无可见资源、权限失败、详情 404 和长组合名。
- [ ] 列表显示组合、类型、状态、基准、风险画像、版本和详情，不添加无契约创建组合按钮。
- [ ] 详情统一资源摘要与 optimization/decision/live/rebalance Tabs，URL 恢复选项。
- [ ] M2 实盘路由未启用时保留明确不可用状态，不无条件请求返回 404 后当作“空持仓”。
- [ ] 当前能力不足以判定路由开关时记录配置依赖，不把存在接口响应等同真实持仓。
- [ ] 执行 `npm test -- --run src/features/portfolio/PortfolioDecisionPage.test.tsx`。

### Task T11：组合优化工作区

**文件:** 修改 `OptimizationForm.tsx`、`OptimizationResult.tsx`、PortfolioDecisionPage、`WeightExplainChain.tsx`；扩展 PortfolioDecisionPage 测试。

- [ ] 先测必填版本、合法 mode、重复提交、任务失败/阻断、INFEASIBLE、非预期 result_ref 和结果资源失败。
- [ ] 左侧为分组配置，右侧为结果；默认桌面分栏，窄屏顺序展示。所有版本/候选池输入来自真实资源或明确手填，不写入假默认值。
- [ ] 提交后显示 operation 和业务资源标识；挂载/离开不重复提交，轮询终态停止，429按服务端建议退避。
- [ ] 结果展示权重表和实际权重图、组合风险、风险贡献、约束 binding、预算状态及解释链。
- [ ] INFEASIBLE 用具体诊断替代空白图表；没有结果时不画默认饼图，不把任务 COMPLETED 当有效决策。
- [ ] 优化/operation ID 写入合法直链状态以便恢复；验证 ID 与当前组合关联，不靠 URL 参数越权读取。
- [ ] 执行 `npm test -- --run src/features/portfolio/PortfolioDecisionPage.test.tsx` 和对应浏览器场景。

### Task T12：完整决策复核体验

**文件:** 修改 `DecisionReviewPanel.tsx`、PortfolioDecisionPage、WeightExplainChain；扩展 PortfolioDecisionPage/accessibility 测试。

- [ ] 测试 session 无复核权限、过期/终态、理由为空、覆盖非法、409竞争、成功后刷新。
- [ ] 从优化结果关联决策后进入详情，不把手输 decision ID 作为正常主流程；保留受支持的已有资源打开入口。
- [ ] 呈现建议权重、风险/约束、来源、状态和已有审计；批准/拒绝/覆盖各有清晰操作。
- [ ] 覆盖使用可编辑权重表，展示合计、相对原建议差异；提交前确认原方案和变更，最终以服务端校验为准。
- [ ] 成功后 invalidate 对应决策/组合查询；失败不乐观改成已批准，Modal 保留输入便于修正。
- [ ] 执行 `npm test -- --run src/features/portfolio/PortfolioDecisionPage.test.tsx src/test/accessibility.test.tsx`。

### Task T13：实盘持仓与成交回报

**文件:** 修改 `LivePortfolioPanel.tsx`、`api/rebalance.ts` 现有读写边界；扩展 `LiveAndRebalancing.test.tsx`。

- [ ] 测试三态不混淆、真实零持仓、接口不可用、无权限、回报 pending/失败/重复及刷新。
- [ ] 摘要显示实际权益、现金、估值时间和在途标志；Target/Pending/Actual 分开表格，不用目标数字充当实际资产。
- [ ] 各表标注份额、成本、价格、市值、权重、时间与状态；缺价格显示不可用，不默认 1。
- [ ] 成交回报使用结构化 Modal，校验报告/委托/基金关联、方向、状态、份额、价格与费用；提交前确认影响。
- [ ] 只做输入层合理性校验，记账、去重和现金约束依赖服务端。响应成功后重新读取实际持仓。
- [ ] 后端仍返回固定初始化数据时记录产品阻塞，不能为截图把它叫做真实实盘。
- [ ] 执行 `npm test -- --run src/features/portfolio/LiveAndRebalancing.test.tsx`。

### Task T14：再平衡评估、历史与交易详情

**文件:** 修改 `RebalancingPanel.tsx`、`api/rebalance.ts`、PortfolioDecisionPage；扩展 LiveAndRebalancing 测试。

- [ ] 测试无触发、Pending 拦截、多触发、成本收益不通过、过滤、冻结资产、历史空/错误与详情失败。
- [ ] 评估输入采用版本化业务来源；当前契约要求客户端价格/改善值时清楚标识输入假设，禁止伪装为系统已验证估计。
- [ ] 展示全部触发原因、主触发、重算范围、结论、换手、成本和改善口径；跳过是合法结果，不是一律红色异常。
- [ ] 买卖清单显示当前/目标/差额、预估金额、资格、过滤和未达成原因，冻结资产不能从风险披露中消失。
- [ ] 历史列表支持打开具体交易详情并恢复选择；没有确认/交付契约时不提供“执行调仓”按钮。
- [ ] 有交付契约时，人工确认后交付并刷新 Pending；不得调用自动下单或直接把建议写成 Actual。
- [ ] 执行 `npm test -- --run src/features/portfolio/LiveAndRebalancing.test.tsx`，真实联调验证 Pending 防重复由服务端执行。

### Task T15：回测完整工作台

**文件:** 修改 `pages/BacktestPage.tsx` 及 `features/backtest/` 全部组件；扩展 BacktestPage/BacktestPerformanceChart 测试。

- [ ] 先测创建/校验/启动顺序、校验阻断、重复启动、刷新恢复、失败/INVALID/ABORTED、空曲线和不完整统计。
- [ ] 配置按策略版本、期间资金、执行与费用、偏差与基线分组；默认展开核心项，高级配置可折叠，不能藏住必填错误。
- [ ] 桌面参数/结果双栏；运行期间配置为只读快照，提供明确“新建回测”动作重置创建流程，不能一直 disabled 无法再次使用。
- [ ] URL 保存服务端 backtest/operation 标识；刷新后查询状态，不重复 create/run。没有 operation ID 时按契约读取已知回测状态。
- [ ] 校验区显示有效区间、warm-up、IS/OOS、warning/blocking；有阻断不可启动，服务端仍需重复校验。
- [ ] 结果按总览、绩效、成本与归因、偏差与来源组织；仅展示接口已有数据，缺少归因则显式标不可用并登记产品需求缺口。
- [ ] 图表区分策略/Benchmark/等权基线、净收益与区间；回撤恢复、交易成本和跳期不能省略。
- [ ] 统计报告保留显著性状态和方法限制；未通过条件不能渲染“显著优于”。
- [ ] 执行 `npm test -- --run src/features/backtest/BacktestPage.test.tsx src/features/backtest/BacktestPerformanceChart.test.tsx`。

### Task T16：图表、性能、响应式与无障碍全覆盖

**文件:** 新增 ChartFrame，改造两个现有 ECharts 图及新权重/风险图；扩展 accessibility 测试和 workbench.spec。

- [ ] 图表固定合理高度与宽度约束；ResizeObserver 驱动 resize，Tabs 激活与 panels 调整后重新测量，卸载正确释放实例。
- [ ] 为关键图表提供数值表/文本等价信息；Tooltip 不只靠鼠标，空值断线不归零，长图例和坐标轴不遮挡。
- [ ] 尊重 reduced-motion，图表不启用无限动画，不用装饰图像替代真实业务图表。
- [ ] 全部路由检查 1440×900、1024×768、768×1024、390×844；至少对 320px 宽验证不发生页面级溢出。
- [ ] 键盘完成导航、筛选、Tabs、表格动作、分栏和弹窗确认，焦点可见且关闭后回到触发位置。
- [ ] 测试 200% 放大、长基金名/组合名、长错误文本、低速加载与大列表；主体不被 sticky 工具条覆盖。
- [ ] 只在完整大集合确有性能风险时引入虚拟化，不给 20 行服务器分页表增加复杂性。
- [ ] 检查 Vite bundle 与图表依赖，按路由/图表适度拆包；性能阈值记录实测环境，禁止为提速移除关键业务校验。
- [ ] 执行 `npm test -- --run src/test/accessibility.test.tsx`、`npm run build` 与工作台 Playwright 用例。

### Task T17：契约回归、真实联调与视觉验收

**文件:** 新增/扩展 `frontend/e2e/workbench.spec.ts`、`workbench-live.spec.ts`、Playwright 配置、`package.json` 和验收记录。

- [ ] 区分 fixture 交互测试与真实联调脚本；新增 `test:e2e:live` 使用隔离 API/Worker，禁止 page.route/MSW 伪造业务结果。
- [ ] 调整原有 playwright config 的测试选择，普通 UI 门禁不意外触发真实写操作；live 用例不因普通脚本 exclude 而漏验。
- [ ] fixture 可构造空、长文本、401/403/409/422/429/500、UNAVAILABLE 和未知枚举，断言正确 UI，不把 fixtures 当产品可运行证据。
- [ ] 真实场景覆盖：基金查询到评分、候选池排除解释、优化到决策复核、真实回测完成、实盘回报与再平衡。最终计算结果不能预灌。
- [ ] 刷新/直链/前进后退/重复点击/服务短暂断连均有验证；确认业务状态、数据库变化和界面一致。
- [ ] 截图覆盖每个路由及组合各 Tab、回测配置/运行/结果、空/错误/受限状态；固定环境与数据，人工审查后才建立截图基线。
- [ ] ECharts 做非空 canvas 像素检查与实际数值断言，不能仅检查 canvas 元素存在。
- [ ] 执行 `npm run check`、`npm run test:e2e:live`；后端不足则如实失败/阻塞，不跳过后仍宣称产品通过。

**必须保留的行为测试示例:** 使用现有 fixture 文件的真实字段，在对应测试文件内构造场景，不照抄不存在的测试 helper。

Mantine MultiSelect 不是原生 select，T06 测试应通过 click 输入与 role=option 选择，不使用 selectOptions。`user` 由 `userEvent.setup()` 创建，组件通过 T01 包装渲染；基于实际可访问角色验证标签，不能为适配测试移除控件语义。BrowserRouter 场景采用下面的断言：

```tsx
await user.click(screen.getByRole("textbox", { name: "投资资格" }));
await user.click(screen.getByRole("option", { name: "仅可持有" }));
await user.click(screen.getByRole("button", { name: "查询", exact: true }));
expect(window.location.search).toContain("investment_eligibility=HOLD_ONLY");
```

如测试使用 MemoryRouter，不能断言 window.location，应由测试路由位置探针读取实际 search；T01 的包装必须明确 Router 类型。

### Task T18：发布、文档与完整交接

**文件:** 修改 `frontend/README.md`、`docs/STARTUP_GUIDE.md`、必要 Vite/部署配置；完成验收记录，不修改无关后端代码。

- [ ] 干净依赖安装、生产构建与预览通过；验证 SPA 直链刷新和实际 API 地址，不把开发代理假设带进生产。
- [ ] 检查生产 bundle 无 MSW、fixture、开发身份凭证、敏感配置和错误堆栈泄露；来源 ID 本身不是密钥，但响应不得暴露连接串。
- [ ] 开发服务使用空闲端口，记录前端/API/Worker 启动命令、实际 URL、必要环境变量与关闭方式。
- [ ] 更新完整页面清单、组件栈、配置/布局恢复规则、受限能力、错误排查和真实联调步骤。
- [ ] 交付桌面/窄屏截图索引、测试结果、API/Worker/数据库证据、剩余缺陷与用户验收流程。
- [ ] 对照第 8 节逐项签验；不接受“剩余页面随后补齐”“只差接口”或“组件已经写好”作为产品通过结论。

## 8. 最终验收清单

- [ ] 全部七类路由与组合内全部业务视图完成，不残留默认 HTML 表单、散落英文枚举或无样式业务区。
- [ ] Mantine、Grid/Flex、TanStack Table、按需 panels 的职责清晰，无重复组件框架。
- [ ] 每个可见按钮有真实行为、明确权限和 pending/成功/失败处理，没有无效入口。
- [ ] 所有列表/详情/任务直链、刷新和返回恢复可用，业务状态不依赖只存在组件内的临时 ID。
- [ ] null/UNAVAILABLE/未知状态、质量警告和重要来源信息完整保留。
- [ ] 优化、审批、回测、实盘回报与再平衡均由真实服务完成，不含生产模拟数据。
- [ ] 8000/4173 等端口复用前验证服务身份，测试不操作真实资金或生产数据库。
- [ ] 全部路由在约定宽度、200% 放大、键盘和 reduced-motion 下可用，无不可解释遮挡。
- [ ] 图表真实非空、容器 resize 正常，表格仅局部滚动，长名称和错误文本不破坏布局。
- [ ] 格式、ESLint、Vitest、TypeScript/Vite、fixture E2E、真实 E2E 全部有本次执行证据。
- [ ] 干净安装和生产预览通过，文档可复现启动，生产包不含测试身份/fixture。
- [ ] 阻塞级缺陷为零；后端必要能力未完成时，明确“产品不可交付”并给出具体阻塞任务。

## 9. agy 可直接执行的指令

```text
请完整执行 docs/superpowers/plans/2026-10-20-research-workbench-product-delivery.md。

目标是交付覆盖全部现有业务的专业投研工作台，不是外壳样板或首批页面。
范围包含 T00-T18。按依赖逐项实施，不把候选池、组合、复核、实盘、再平衡、回测留给以后。
组件使用 Mantine + CSS Grid/Flexbox、TanStack Table、按需 react-resizable-panels。
使用 React 19、React Query、React Router、ECharts 和真实 API 客户端。
先核对仓库现状和依赖兼容性，复用现有组件与测试，逐任务失败测试驱动。
不得用模拟计算、硬编码持仓、预灌优化/回测结果或假成功交付。
不要擅自改金融规则、后端计算或冻结契约，不创建无端点的假功能按钮。
后端阻塞需关联核心工作流计划，继续完成可独立任务，最终验收仍必须标记产品阻塞。
不清库、不覆盖已有改动、不自动建分支、不提交、不合并。
普通组件测试和真实联调分开；最终须跑真实 API/Worker/数据库与浏览器场景。
维护 docs/acceptance/research-workbench-delivery.md，给出每页截图、命令结果与真实证据。
结束时报告：全部任务状态、已交付页面与动作、测试结果、真实启动 URL、阻塞和最终可交付结论。
```

## 10. 计划覆盖自检

- [x] 覆盖所有现有路由及实盘/再平衡，不以样板页代替全量交付。
- [x] 使用用户明确指定的组件组合，未保留 Ant Design 依赖建议。
- [x] 定义视觉、布局、组件接口、路由状态、权限、错误与表单行为。
- [x] 逐页给出文件范围、执行步骤、负例与针对性测试。
- [x] 包含响应式、可访问性、图表非空、生产构建和真实联调。
- [x] 不把前端改造完成等同完整业务可投产，后端缺口是显式交付阻塞。
- [x] 完整交接指令可直接用于 agy，不要求执行者再次拆分剩余页面计划。
