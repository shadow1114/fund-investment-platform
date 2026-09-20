# M1.7 前端交接

本目录是基金研究、候选池快照、组合决策和回测的 Vite/React 客户端。接口依据 [M1.7 冻结契约](../docs/10-api/06-m17-frontend-contracts.md)，机器可读投影为 [`openapi/m17.yaml`](openapi/m17.yaml)。仓库根目录的 FastAPI server 通过 `make api-dev` 提供这些 `/api/v1` 路由。

## 本地启动与校验

在仓库根目录运行：

```sh
cd frontend && npm install
npm run api:generate
npm run dev
```

Vite 启动后打开终端显示的本地地址。首次执行浏览器测试时还需安装 Playwright Chromium（`npx playwright install chromium`）；macOS 上测试配置默认使用已安装的 Chrome，可用 `PLAYWRIGHT_CHANNEL=chromium` 选择 Playwright Chromium。完整前端校验在 `frontend` 目录执行 `npm run check`，包括格式、ESLint、Vitest、TypeScript/Vite 构建和 Playwright 浏览器烟测；根目录可用 `make frontend-check`。仓库 Python 检查在根目录执行 `make check`，依赖已有的 `.venv`。

`npm run api:generate` 从 `openapi/m17.yaml` 重新生成 `src/api/generated/`；不要手改生成文件。修改冻结契约时先同步契约文档与 OpenAPI，再重新生成并运行检查。

若仓库位于含中文的路径、当前终端又设置了 `LC_ALL=C`，Python 虚拟环境可能在导入阶段报 ASCII 解码错误。此时在仓库根目录使用 `LC_ALL=en_US.UTF-8 make check`；这只调整本次检查进程的 locale。

### API 地址与测试数据

生成的客户端默认请求同源 `/api/v1/...`。设置 `VITE_API_BASE_URL=http://127.0.0.1:8000` 后，生成客户端会把相对路径解析到该 API 地址；未设置时仍要求页面所在 origin 提供冻结的 `/api/v1` 路由。独立运行 `npm run dev` 可以打开页面，但在没有上述 API 服务时数据请求会显示错误。非 2xx 响应保留 `status`、`error.code`、`X-Request-ID` 和 `Retry-After`，不会被转换为空列表。

`src/test/contractFixtures.ts` 和 MSW handlers 只在 Vitest 测试中使用；Playwright 烟测在浏览器测试里拦截请求并返回同一组契约 fixtures。API server 的实时契约由仓库根目录 `make api-check` 单独验收。

## 页面和接口对应

| 页面路由                                  | 冻结的主要接口                                                                                                                                                                                                                                                                  | 用途                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `/funds`、`/funds/:fundId`                | `GET /api/v1/funds`、`GET /api/v1/funds/{fund_id}`、`GET /api/v1/funds/{fund_id}/nav-series`、`GET /api/v1/funds/{fund_id}/evaluations`、`GET /api/v1/funds/{fund_id}/scores`                                                                                                   | 检索、详情、净值、评价和评分               |
| `/universes`、`/universes/:universeId`    | `GET /api/v1/fund-universes`、`GET /api/v1/fund-universes/{universe_id}`                                                                                                                                                                                                        | 快照、入选与排除成员及条件                 |
| `/portfolios`、`/portfolios/:portfolioId` | `GET /api/v1/portfolios`、`GET /api/v1/portfolios/{id}`、`POST /api/v1/portfolios/{id}/optimizations`、`GET /api/v1/portfolios/{id}/optimizations/{optimization_id}`、`GET /api/v1/decisions/{decision_id}`、`POST /api/v1/decisions/{decision_id}/review`                      | 组合、优化、决策复核                       |
| `/backtests`                              | `POST /api/v1/backtests`、`POST /api/v1/backtests/{id}/validate-configuration`、`POST /api/v1/backtests/{id}/runs`、`GET /api/v1/backtests/{id}/status`、`GET /api/v1/backtests/{id}/result`、`GET /api/v1/backtests/{id}/performance`、`GET /api/v1/backtests/{id}/bias-check` | 创建、校验、执行与检视                     |
| 跨页面                                    | `GET /api/v1/session`、`GET /api/v1/operations/{operation_id}`                                                                                                                                                                                                                  | 服务端给出的复核能力；优化与回测的异步进度 |

全部方法、字段与状态见冻结契约 §2–§4。浏览器路由中的 `fundId`、`universeId`、`portfolioId` 只是客户端参数名，HTTP 路径按契约发送。

## 集成时应核对的语义

- 所有成功与错误响应均为 `{ data, meta, error }`；错误按 HTTP 状态和 API `error.code` 显示。`401`、`403`、`409`、`422` 等不能当作空列表。
- `null` 指标必须连同 `status` 和 `reason` 展示。收益率、权重等百分数在传输中是小数，仅显示时乘以 100。
- `meta.versions`、`meta.is_point_in_time` 和 `availability_quality_distribution` 供来源条呈现；PIT 判断、业务计算和权限判断仍由服务端负责。
- 优化与回测执行返回 `202` 和 `operation_id`，轮询 `/api/v1/operations/{operation_id}`。Operation 的 `COMPLETED` 仅表示任务结束；随后读取业务资源，分别处理优化的 `INFEASIBLE` 等状态以及回测的 `INVALID`、`ABORTED` 等状态。
- 决策复核按钮受 `/api/v1/session` 的 `can_review_decisions` 控制。服务端仍必须对每次复核实施授权。候选池要同时显示 `SELECTED` 与 `REJECTED` 成员和失败条件；未知枚举应有中性回退。

## 待后续服务端和产品阶段处理

本前端范围未决定认证协议及凭证生命周期、资源归属与可见性细则、生产响应时延/SLA 和通用异步阈值、全 API 错误码全集、限流配额、外部执行系统回报、报告文件导出。冻结契约 §5 保留了这些事项；它们不得在未修订契约时改变本页列出的路径或字段。当前也没有可供实时联调的 `/api/v1` Web server。

## 当前检查中的非阻断提示

2026-09-19 的 `make frontend-check` 已通过，但工具输出仍有以下提示，后续维护时可分别处理：Orval 生成的 schema 有未使用 `eslint-disable` 警告；React Router 6 的测试提示 v7 future flags；JSDOM 中的 ECharts 没有真实容器尺寸；Vite 提示主包超过 500 kB。浏览器测试若同时继承 `NO_COLOR` 与 `FORCE_COLOR`，Node 还会提示颜色变量冲突。以上提示均未在本次检查中造成失败；不要直接修改生成文件来消除警告。
