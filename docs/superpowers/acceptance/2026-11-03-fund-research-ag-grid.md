# 基金研究与 AG Grid 迁移验收记录

文档版本：v1.0。日期：2026-11-04。实施计划：`docs/superpowers/plans/2026-11-03-fund-research-mantine-react-table-implementation.md` v1.3。本记录不改写历史设计结论。

本轮验收只使用本地冻结 API fixtures、Vitest/MSW 和本地 Vite。没有运行 `data-ingestion-live.spec.ts`，没有启动真实抓取、Worker、生产迁移或数据回填，也没有 commit、push 或 deploy。完整证据和失败/中断记录位于 `.superpowers/sdd/2026-11-03-fund-research-mantine-react-table-implementation/task-8-report.md`。

## 交付语义

- 列表一行是份额，稳定 `share_class_id` 用于详情、NAV、评价、评分、因子分析；产品公开 `fund_id` 用于产品抓取/基本信息历史；六位 `fund_code` 始终是字符串。
- 当前公司列是产品可空展示投影，来源为已验证“基金管理人”；历史公司取不可变基本信息快照，当前投影不是 PIT 历史或规范化公司实体 ID。
- PostgreSQL 负责筛选、每份额唯一计数、稳定排序和分页；公司选项来自全库独立端点。浏览器 fixtures 验证的是客户端请求/展示边界，真实 SQL 证据来自 Task 3/4 的专用 PostgreSQL 测试报告，二者不混同。
- 四个业务数据列为代码、名称、管理公司、申购状态；另保留详情动作列，以及有权限用户的选择/抓取动作。Community Infinite Row Model 没有跨未加载行的内建全选；批量抓取上限仍为 100。
- `开放` 与 `subscription_status_source: PLACEHOLDER` 只表示显示占位，不是实际申购能力，也不改写生命周期或可投资性。

## 版本与治理

| 文档 | 版本 | 本轮同步 |
|---|---|---|
| `docs/03-data/02-data-domain-model.md` | v1.8 → v1.9 | 份额/代码身份，公司当前投影与历史边界，占位申购限制 |
| `docs/10-api/02-fund-api.md` | v1.6 → v1.7 | 精确请求参数、响应身份、独立公司选项、SQL 分页/排序、旧筛选兼容 |
| `docs/11-database/04-database-design.md` | v1.10 → v1.11 | 可空列迁移 0040、来源与安全回填、正确份额关联与 SQL 查询 |
| `docs/11-database/03-erd.md` | v1.3 不变 | 没有新增实体/关系；公司字段只是现有 Fund 的投影 |

上游声明已核对本 checkout：产品总纲 v2.6、需求 v2.8、数据架构 v1.2、API 总纲 v1.3、PostgreSQL 规范 v1.2、技术栈 v1.5。变更记录逐项注明受影响下游，历史变更记录保留。

## 本地依赖兼容证据

`frontend/package.json` / `package-lock.json` 固定 React/React DOM **19.3.1**、Mantine core/form/hooks **9.7.4**、AG Grid Community/React **36.2.0**；没有 TanStack Table 或 AG Grid Enterprise。`npm ls --all` 已实跑，依赖树无 invalid peer。

已安装包的 peer 声明：Mantine 要求 React/DOM `^19.2.0`，AG Grid React 支持 `^19.0.0`，React Query 5.103.1 支持 `^18 || ^19`，react-resizable-panels 2.1.9 支持 React/DOM 19，ECharts 6.1.0 + echarts-for-react 3.0.6 的 peers 支持本版本，lucide-react 1.61.0、react-router-dom 6.30.6 与 Testing Library React 16.3.3 的 peers 均接受 React 19。兼容结论仅基于本地锁文件、peer 检查、构建和实测，不作外部官方认证声明。

## 迁移与回填

`0040_fund_company_name.py` 在 0039 后添加 `fund.fund.company_name VARCHAR(128) NULL`；降级只删除该列，不删除基金。迁移不包含回填。CLI `backfill-fund-company-names` 默认 dry-run，只从本地保留快照分批补齐 NULL 当前投影；审阅输出后才可显式 `--apply`，不会覆盖已填值，不会改写历史。交付仍需运维在获授权的环境执行迁移/审阅回填；本轮没有执行。

## 实测结论

最终冻结浏览器套件 **40/40** 完成通过（3.0 分钟），覆盖所有四种视口、20/50/200、URL/筛选/总数/排序、Modal 身份与焦点、候选池、PM 权重和权限入口。DOM 测量与截图已保留：1440/1024/390/720 的展开查询高度分别为 136.58 / 110.17 / 126.58 / 53.78 px，扣除布局 gap 后查询/结果均为 20/80；后续定向 6/6 再验证收起后结果高度与工作区完全相等（100%）；短高度视口仍显示数据行及分页器。完整命令与失败历史见 Task 8 报告。后端 API **99/99**，研究页最后受影响文件 **17/17** 完成通过，mypy 152 个源文件通过。全前端套件没有完整通过声明：一次完整尝试在已知 home/navigation 可访问性用例 CPU 持续占用后中断；其余 27 个测试文件 **165/165** 完成通过。全量后端 Ruff 当前受已有分类文件 16 个问题阻塞；Task 8 修改的后端文件 Ruff 检查通过。前端 ESLint 0 errors / 77 generated warnings；构建完成，仍有 large-chunk notice。所有失败、过滤跳过和中断均保留在完整记录中。

## 2026-11-04 UI follow-up

后续用户调整覆盖上方历史布局要求：基金查询区展开时固定约 **30%**，下方结果区约 **70%**。结果区只包含 AG Grid，移除了保存视图、筛选/总数工具栏、来源栏、外置加载/错误说明和批量选择工具栏；授权用户的单基金基本信息抓取仍作为网格行操作列显示。查询区右上角的向上/向下箭头可收起与展开条件区；收起后结果表格扩展到工作区剩余高度。查询区域已删除申购状态占位说明和管理公司列表不可用说明。本次组件测试 **19/19**、Playwright **12/12**、构建及目标文件 ESLint 通过；四视口比例仍约29.1%–29.6%，浏览器用例新增验证折叠/展开交互。

批量抓取仍可在数据中心执行。

## 2026-11-04 UI follow-up 2

查询区收起后显示 40px 高的白底占位栏，栏内保留展开箭头；白栏和基金结果区之间留 8px 间距。箭头 hover 不出现背景高亮。基金研究页的 AG Grid 不显示“列设置”和“表格密度”控件，其他业务表仍使用共享表格设置。视觉复核后移除了结果区外层边框，避免和 AG Grid 边框叠加。研究页与共享表格测试 **30/30**、布局 Playwright **12/12**、构建及目标文件 ESLint/Prettier、`git diff --check` 通过。

## 2026-11-05 应用内路由 follow-up

全站 `BrowserRouter` 改为 `MemoryRouter`，其初始 route 从页面打开时的浏览器 path/query/hash 初始化。React Router 继续驱动侧栏导航、详情路由、筛选、排序和分页；这些内部状态变化不再 push/replace 浏览器地址。基金与组合网格翻页继续向 API 发送新的 `page/page_size`，浏览器地址保持页面打开时的值。重新加载会从浏览器地址重新初始化 route，因此仅存在内存中的后续状态不会自动恢复。

## 2026-11-05 基金公司来源修正

基本信息任务同步抓取基金详情中的“基金公司”字段，核对基金代码后写入 `Fund.company_name` 及 `FundBasicInfoHistory.normalized_fields.company_name`，原始快照字段键为 `基金公司`。不使用“基金管理人”或基金经理姓名作为公司名；PIT 原始字段回退及本地回填也只识别 `基金公司`。

验证：App/基金研究/共享表格 Vitest **40/40**；冻结 Playwright 首轮 **35/40**，未通过的 5 项是旧标题/错误文案/行选择断言，已更新并针对性复测 **5/5**；构建、目标文件 ESLint/Prettier 和 `git diff --check` 通过。修改后的整套 40 项没有再次一起运行。
