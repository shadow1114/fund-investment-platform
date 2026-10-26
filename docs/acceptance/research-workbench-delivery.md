# 投研工作台交付验收记录

## 当前结论

**未验收，尚不具备发布结论。** 前端主要视图已有统一实现，生产构建及 TypeScript 检查通过；真实 API、数据库与 Worker 交付仍有阻塞，测试和浏览器验收未执行。代码、静态检查、fixture 行为和隔离真实服务证据分别记录；没有证据的项目不得标记通过。

## 基线环境与工作区

- 日期：2026-10-27（Asia/Shanghai）
- 分支：`feat/fund-classification-v1`；工作区存在未提交的分类、基金抓取及既有页面/API改动，全部保留。
- Node.js：`v24.4.1`；npm：`11.4.2`。
- 前端已有 React 18、React Router、React Query、TanStack Table、ECharts、Vitest、Testing Library、Playwright、MSW；基线未安装 Mantine、lucide-react、react-resizable-panels。
- 后端现有基金/候选池/组合/API操作、再平衡和分类复核路由；基金基本信息与 NAV 抓取及持久化 Worker 已实现，但数据库迁移未应用于任何环境。
- 本次未运行测试、真实联调、Playwright、数据库迁移或写操作。当前执行约束禁止新增/运行测试，相关验收保持未验证。
- 改造前/改造后截图：未采集。没有可复现的运行服务与已确认服务身份证据。

## 已落地实现（代码与静态检查）

- Mantine 主题和应用外壳已接入。导航包含基金研究、分类复核、候选池、组合决策、回测分析；session 身份/角色和构建环境标签来自真实运行上下文，含窄屏导航、跳至正文和 404。
- 增加页面标题、错误/状态/来源/异步任务组件、TanStack Table + Mantine 表格、列显隐偏好、组合/回测响应式分栏。
- 基金研究支持中文筛选、服务端分页/排序、URL 恢复、单只及批量（最多 100）基本信息抓取；基金详情支持净值/评估/评分 URL Tabs、分类证据/历史和抓取任务。
- 抓取任务接口及 OpenAPI 增加来源/触发人，客户端重新生成；任务表显示二者，NAV 单只抓取有提交确认。数据库 migration 未应用，Worker/数据源运行未验证。
- 候选池列表/详情使用表格展示服务端结果；阈值/来源字段缺失时明确标注不可用。组合列表、优化表单与结果、决策复核使用现有 API，写操作有确认/幂等处理；优化无 decision_id 时保留已有决策的受权限检查打开入口。
- 回测支持创建/校验/启动及 URL 状态恢复；后端空绩效/偏差响应明确显示不可用。实盘/再平衡页面明确标记后端数据源不可用，没有将内存样例冒充实际资产。
- 图表按需加载、容器尺寸观察并提供数据表；全局支持键盘焦点与 reduced-motion，业务页面按路由懒加载。
- `cd frontend && npm run api:generate` 成功；最终 `npm run build`（含 TypeScript 检查）成功。ECharts 改为按需注册 Line/Canvas/Grid/Tooltip/Aria 模块，图表依赖 chunk 约 334 KB（gzip 约 116 KB），构建无大包警告。
- 最终 `npm run lint` 成功，0 个错误；生成客户端有 53 条既有/生成器 `no-redeclare` unused-disable 警告。`npm run format:check` 成功；`python -m compileall -q src/fip` 成功；`git diff --check` 成功。
- `ruff` 不可用（未安装），后端 Python 静态检查未执行；未添加开发依赖。

## 路由能力盘点（代码层，不代表运行通过）

| 路由 | 当前代码能力 | 当前状态 / 主要差距 |
|---|---|---|
| `/funds` | 中文筛选、服务端分页/排序、列设置、抓取 | 已实现；自动化、窄屏和真实数据验收未执行 |
| `/funds/:fundId` | 主数据、净值、评价/评分、分类历史、抓取、URL Tabs | 已实现；自动化与真实数据验收未执行 |
| `/classification-reviews` | 分类待复核列表与提交复核 | 已纳入导航；权限/浏览器验收未执行 |
| `/universes` | 快照筛选、URL状态、数据表和分页 | 已实现；运行态验收未执行 |
| `/universes/:universeId` | 入选/排除、条件与来源 | 已实现；阈值/来源因 API 字段缺失而显示不可用 |
| `/portfolios` | 组合服务端分页、排序和详情入口 | 已实现；运行态验收未执行 |
| `/portfolios/:portfolioId` | 优化、复核、实盘/再平衡状态、URL恢复 | 优化/复核走现有 API；决策无自动关联；实盘/再平衡为明确阻塞态 |
| `/backtests` | 创建/校验/启动、URL恢复和结果 | 已实现请求流程；后端绩效/偏差为空，产品验收阻塞 |
| 未知路径 | 404 与返回入口 | 已实现；浏览器验收未执行 |

## 证据记录

| 检查 | 结果 | 证据 |
|---|---|---|
| 初始 `npm run check` | 未执行 | 测试执行受当前指令约束；不移除断言或伪造基线结果 |
| 初始桌面/窄屏浏览器截图 | 未采集 | 无已验证运行服务身份 |
| 应用/路由与API代码盘点 | 已检查代码 | `frontend/src/app/routes.tsx`、`src/fip/api/routers/`、`frontend/openapi/m17.yaml` |
| 最终格式/lint/typecheck/build | 静态门禁通过 | `frontend`: `npm run format:check`、`npm run lint`（0 错误、53 个生成客户端警告）、`npm run build`（含 tsc）；根目录 `python -m compileall -q src/fip`、`git diff --check` 均成功 |
| 真实 API/DB/Worker/E2E | 未验证 | 需要明确隔离环境和可复现数据 |

### 经源码核实的阻塞

- `src/fip/api/routers/reads.py` 的 `GET /backtests/{id}/performance` 与 `GET /backtests/{id}/bias-check` 当前只返回空对象；前端不能呈现真实绩效曲线或偏差诊断，需明确标注不可用并登记后端交付阻塞。
- `src/fip/api/routers/rebalance.py` 使用进程内 `_LIVE_PORTFOLIOS` / `_HISTORICAL_REBALANCES` / `_REBALANCE_TRADES`，并在首次读取时以固定基金代码、50/50权重、固定日期创建组合状态；不能作为真实可交付实盘持仓。按计划不把目标持仓说成实际持仓，也不伪造持久化。
- 文档声明依赖 `docs/superpowers/plans/2026-10-20-core-workflow-delivery.md`，该文件在当前工作区不存在；核心 API/Worker 的对应执行证据无法从该引用验证。
- 生产认证提供方/资源授权、本地隔离数据库、AKShare Worker 连通性和 Playwright 服务身份均未验证；需要隔离环境和可复现数据后才能进行真实联调。
