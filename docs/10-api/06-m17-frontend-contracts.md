# M1.7 前端接口契约冻结

> 上游文档：docs/01-product/01-product-overview.md（v2.6）｜本文细化环节：支撑层
> 分类数据依赖：docs/03-data/02-data-domain-model.md（v1.7）。

> 本文冻结范围：M1.7 的四个前端页面与横切组件所消费的 `/api/v1` 契约。
> 本文不冻结全部 API，不替代各领域 API 文档；路径、业务字段和状态语义以本文及所引用章节为准。
> 上游：`docs/superpowers/specs/2026-08-31-fund-platform-m1-design.md` §6.5、`docs/10-api/01-api-overview.md`。

**文档版本**：v1.2 ｜ **状态**：M1.7 前端消费范围已冻结 ｜ **日期**：2026-10-26

---

## 1. 冻结规则

1. 下表所列路径、HTTP 方法和页面用途对 M1.7 固定。原领域文档中“路径待评审”的声明仅对表中路径关闭；未列出的路径仍按原状态处理。
2. 字段、状态、错误、分页、PIT、版本元数据和数值语义沿用所列领域文档章节。此文未重述的字段不可由前端自行改名、推导或改变含义。
3. 所有成功与失败响应遵循 `01-api-overview.md` §5–§6 的统一 envelope；列表遵循 §7–§8；业务日期、时间、PIT、数值与 `null` 语义遵循 §10–§12。
4. 前端不能作为授权边界。服务端必须实施认证、操作级授权和资源级授权；前端根据当前用户角色隐藏/禁用操作，并仍须正确呈现 `401`、`403`。
5. 长任务以 `202 Accepted` 返回独立 `operation_id`，随后使用统一 `GET /api/v1/operations/{operation_id}` 查询。优化和回测执行固定为异步；不在 M1.7 期间按前端等待时间切换同步模式。
6. OpenAPI 3.1.0 是后续 client 生成的机器可读投影，必须与本冻结契约一致；生成的 client 不得成为另一份手工维护的契约。

## 2. 页面与端点映射

| M1.7 页面 | 固定端点 | 契约来源 |
|---|---|---|
| 基金检索与详情 | `GET /api/v1/funds`；`GET /api/v1/funds/{fund_id}`；`GET /api/v1/funds/{fund_id}/nav-series`；`GET /api/v1/funds/{fund_id}/evaluations`；`GET /api/v1/funds/{fund_id}/scores`；`POST /api/v1/funds/{fund_id}/ingestions`；`POST /api/v1/fund-ingestions`；`GET /api/v1/funds/{fund_id}/ingestions`；`GET /api/v1/funds/{fund_id}/basic-info-history`；`GET /api/v1/ingestions/{operation_id}` | `02-fund-api.md` §3、§4.1–§4.5，以及本文件 §9 |
| 候选池快照 | `GET /api/v1/fund-universes`；`GET /api/v1/fund-universes/{universe_id}` | `02-fund-api.md` §3、§4.8–§4.9 |
| 组合决策 | `GET /api/v1/portfolios`；`GET /api/v1/portfolios/{id}`；`POST /api/v1/portfolios/{id}/optimizations`；`GET /api/v1/portfolios/{id}/optimizations/{optimization_id}`；`GET /api/v1/decisions/{decision_id}`；`POST /api/v1/decisions/{decision_id}/review`；`GET /api/v1/operations/{operation_id}` | `04-portfolio-api.md` §3、§4.1、§4.6、§4.8，以及本文件 §3 |
| 回测 | `POST /api/v1/backtests`；`POST /api/v1/backtests/{id}/validate-configuration`；`POST /api/v1/backtests/{id}/runs`；`GET /api/v1/backtests/{id}/status`；`GET /api/v1/backtests/{id}/result`；`GET /api/v1/backtests/{id}/performance`；`GET /api/v1/backtests/{id}/bias-check`；`GET /api/v1/operations/{operation_id}` | `05-backtest-api.md` §3–§4.7，以及 `01-api-overview.md` §16 |
| 全局身份与权限呈现 | `GET /api/v1/session` | 本文件 §3.1 |

`GET /api/v1/operations/{operation_id}` 是组合优化与回测共同的进度查询端点。回测的业务结果仍通过其 `backtest_id` 对应的回测查询端点读取；优化结果通过其 `optimization_id` 对应的优化查询端点读取。

## 3. 冻结的补充契约

### 3.1 当前用户与前端角色

新增 `GET /api/v1/session`，要求已认证。

```json
{
  "data": {
    "user_id": "USR-001",
    "roles": ["Portfolio Manager"],
    "capabilities": {
      "can_review_decisions": true,
      "can_review_classifications": false,
      "can_manage_data_ingestion": false
    }
  },
  "meta": { "request_id": "REQ-001" },
  "error": null
}
```

- `roles` 仅使用 `01-api-overview.md` §15.2 定义的角色值；`can_review_decisions` 是服务端计算后的展示能力，不可替代后端授权。
- 该端点不规定认证协议或凭证获取/刷新方式；调用必须携带由认证层提供的标准 HTTP 认证信息。
- 未认证返回 `401`；认证成功但用户/角色不可用时返回统一错误 envelope，不得伪造空权限后继续显示可写操作。
- 决策按钮的显示由 `capabilities.can_review_decisions` 控制；服务端仍对每次复核强制 SEC-1/SEC-2。

### 3.2 组合优化结果与决策读取

组合页面需要可从异步优化提交结果稳定导航到完整结果及决策复核对象，因此冻结以下资源读取端点：

#### `GET /api/v1/portfolios/{id}/optimizations/{optimization_id}`

成功响应使用 `04-portfolio-api.md` §4.6.3 的优化结果结构。`optimization_status` 取 §4.6.4 的五态。`target_weights` 在非 `OPTIMAL` 时为 `null`；`INFEASIBLE` 响应必须含 `binding_constraints` 和 `conflicting_constraints`，不得提供替代权重。`meta` 必须含产生结果时使用的规则、估计、风险模型与代码版本。

`POST /api/v1/portfolios/{id}/optimizations` 返回的 `optimization_id` 是此查询端点的标识。对于 `202`，响应必须同时返回 `operation_id`、`optimization_id` 与 `status`。

组合列表端点 `GET /api/v1/portfolios` 支持 `page`、`page_size`、`sort`、`order`，只返回当前用户有权访问的组合，默认按 `portfolio_name` 升序、`portfolio_id` 升序作唯一 tie-breaker。每条最小列表项包含 `portfolio_id`、`portfolio_name`、`portfolio_type`、`status`、`base_currency`、`portfolio_version`；响应 `meta.pagination` 沿用总览契约。若调用者无可见组合，返回空数组而不是 `404`。

#### `GET /api/v1/decisions/{decision_id}`

返回该决策的不可变快照概要，至少包括：

| 字段 | 约束 |
|---|---|
| `decision_id` / `portfolio_id` / `optimization_id` | 标识；决策必须引用产生它的优化 |
| `decision_status` | `PROPOSED`、`APPROVED`、`REJECTED`、`OVERRIDDEN`、`EXPIRED`、`SUPERSEDED`；`INFEASIBLE` 是优化状态，不创建 Decision 资源 |
| `proposed_weights` | 原始建议权重；不可因复核而覆盖 |
| `review` | 未复核时为 `null`；复核后含 `action`、`reason`、`reviewed_by`、`reviewed_at` |
| `final_weights` | 未形成可执行决策时为 `null`；Override 时与 `proposed_weights` 分开返回 |
| `meta.versions`、`meta.is_point_in_time` | 按 `01-api-overview.md` §5.2、§11.4 返回完整版本引用与 PIT 标记 |

复核写入仍使用 `04-portfolio-api.md` §4.8：`APPROVED` / `REJECTED` / `OVERRIDDEN`；Override 的 `reason` 必填。`POST /api/v1/decisions/{decision_id}/review` 的 200 响应沿用该文档 §7.3 的独立结构：`data` 含 `decision_id`、`decision_status`、顶层 `reviewed_by` / `reviewed_at` / `reason`、`original_weights`、`final_weights`，`meta` 含 `audit_id`；不可按 GET 的 `Decision` 快照结构解析。业务执行失败必须依原契约通过业务状态表达，不可由前端把 HTTP 任务完成等同于决策获批。

### 3.3 Operation 进度

`GET /api/v1/operations/{operation_id}` 的成功响应固定包含：

```json
{
  "data": {
    "operation_id": "OP-001",
    "status": "RUNNING",
    "progress": { "completed": 2, "total": 10, "unit": "periods" },
    "result_ref": "/api/v1/backtests/BT-001/status",
    "failure": null
  },
  "meta": { "request_id": "REQ-002" },
  "error": null
}
```

- `status` 取 `RUNNING`、`COMPLETED`、`BLOCKED`、`FAILED`、`CANCELLED`，与 `ExecutionStatus` 一致；排队状态不作为 Calculation Job 的公开状态。
- `progress` 可为 `null`；总量未知时 `total` 为 `null`，不得伪造百分比。前端只将它作为进度提示，不将估算值解释为 SLA。
- `result_ref` 在有业务资源时为可直接请求的相对 API 路径，否则为 `null`。
- `failure` 仅在 `BLOCKED` 或 `FAILED` 时非空，含稳定 `code` 与可操作的 `message`；不得把业务上的 `INFEASIBLE` 混为 Operation 技术失败。
- Operation `COMPLETED` 只代表任务执行结束，不代表回测 `validation_status` 有效，也不代表决策已批准。

## 4. 前端必须保持的显示语义

| 契约 | 前端要求 |
|---|---|
| `null`、`status`、`reason` | 使用 `MetricValue` 呈现“不可用（原因）”；不替换为 `0`、`-` 或空字符串 |
| 收益率、权重和百分比 | API 传小数；仅展示格式化层乘以 100 |
| `meta.versions`、`is_point_in_time`、`availability_quality_distribution` | 数据视图显示来源/口径条；缺少必需元数据视为契约错误，不默默隐藏 |
| `INFEASIBLE`、`NOT_CONVERGED`、`INVALID`、`WARNING` | 保留各自的业务状态与诊断；不得只以颜色或成功/失败二分替代 |
| `REJECTED` 候选成员与未通过条件 | 候选池快照必须展示，不得只渲染入选成员 |
| 新增或未知枚举值 | 按 `01-api-overview.md` §14.5 容忍并提供中性回退显示，不得崩溃 |

## 5. 本次明确不冻结的事项

以下既有问题不阻塞 M1.7 前端契约消费，不在本文中替架构、产品或运维定案：认证协议、资源归属/可见性策略细则、生产响应时延/SLA 与通用异步阈值、全 API 错误码全集、限流配额、外部执行系统回报、报告文件导出。它们仍由 `01-api-overview.md` §29、领域 API TBD 与上游责任方处理。

对 M1.7 必需端点而言，以上未决项不得改变本文已冻结的路径、请求/响应结构、角色边界和业务语义；若确需改变，必须先修订本文和相应领域文档，再更新生成的 OpenAPI 与 client。

## 6. 领域文档状态同步

| 原待定项 | 本次处理 |
|---|---|
| `FA-1` 基金 API 路径 | §2 与 §9 列出的基金检索/详情、净值、基本信息历史、数据抓取任务和候选池路径对 M1.7 冻结；不扩展到所有 Fund API |
| `PA-1` 组合 API 路径 | 仅 §2、§3 列出的组合列表/详情、优化、决策与 Operation 路径对 M1.7 冻结 |
| `BA-1` 回测 API 路径 | 仅 §2 列出的 M1.7 回测端点对 M1.7 冻结；报告导出等仍未定 |
| `API-6` 认证机制 | 保留；标准 HTTP 认证信息与 session 用户/角色读取契约已明确，具体协议不在本文范围 |
| `API-7` 资源级授权 | 保留服务端必须授权的约束；可见性规则细节未定 |
| `API-8` 异步阈值/SLA | 保留通用阈值/SLA；优化与回测执行在 M1.7 契约中明确为异步 |

## 7. Plan-4 前端交接

前端启动、校验、浏览器路由与接口追踪表见 [`frontend/README.md`](../../frontend/README.md)。该客户端以同源 `/api/v1` 相对路径请求本文件 §2 的接口；当前仓库未提供实现这些路由的 Web server。Vitest/MSW 与 Playwright fixtures 仅用于自动测试，不代表实时 API 可用。`VITE_API_BASE_URL` 当前未接入请求客户端，部署时须由页面同源提供或代理 `/api/v1`。

验收时应区分：前端自动测试验证页面与冻结契约的消费行为；真实服务联调还需要服务端逐项实现 §2 路径、§3 补充契约、§4 显示所需的元数据和状态语义。§5 的认证协议、资源可见性细则、生产 SLA/通用异步阈值、错误码全集、限流配额、外部执行回报和报告导出仍未定案。


## 8. 分类扩展契约（2026-10-26）

`GET /funds` 新增 asset_class、strategy、geography、product_structure、market_attributes、classification_status 逗号多值参数。维度间 AND、同维度内 ANY；只用已确认最终值命中分类筛选，候选不命中。原 fund_type 保留。列表和详情可带 classification，包含逐维证据、规则/枚举版本、真实 revision_id/version/valid_from。原 classification_version 日期字符串保留兼容并弃用；前端使用新结构。

新增 `/fund-classifications/catalog`、`/funds/{fund_id}/classification-history`、`/classification-reviews`、`/classification-reviews/{case_id}` 及其 `/review` POST。历史的 decision_at 控制可见修订；复核按 details.valid_from/valid_to 指定区间，不按页面所示单一证据修改所有历史时期。复核请求含 expected_revision、维度 action/value/evidence 及 reason；REJECT 保持 UNKNOWN，并保留驳回证据和审计。409 需重新加载，403 不允许提交。Session 新增 can_review_classifications capability；生产从验证身份读取，开发头仅供开发使用。

Web 增加字典驱动筛选、证据/可见历史及分类复核页；CLI 的 classify-funds、refresh-classification、list-classification-reviews、review-classification 调用相同写入服务。CLI 复核使用可信操作环境配置的 FIP_CLASSIFICATION_REVIEWERS，不构造 HTTP 身份。OpenAPI 投影与 Orval 客户端同步生成。名称归组复核事项只供身份调查，不接受分类维度表单进行合并/拆分。

## 9. 基金基本信息与 NAV 抓取扩展（2026-10-26）

工作台可以为单只基金提交 `BASIC_INFO` 或 `NAV` 抓取任务；`POST /api/v1/fund-ingestions` 接受明确勾选的 `fund_ids`（1–100 只）提交批次。两个提交端点都要求 `Idempotency-Key`，返回 `202` 与 `operation_id`。只有 `can_manage_data_ingestion` 身份可以提交；用户只能读取自己提交的任务，数据维护角色可以读取全部任务。请求审计记录触发人、基金、数据集和任务 ID。

`GET /api/v1/funds/{fund_id}/ingestions` 返回最近任务，`GET /api/v1/ingestions/{operation_id}` 返回逐份额处理结果，包含来源 `source`、触发人 `actor`、成功/失败数量、失败原因和新增修订数量。抓取由 durable worker 执行；处理中百分比未知时保持未知。相同幂等键重试复用同一任务。上游部分失败以任务结果 `PARTIAL_SUCCESS` 呈现。

`BASIC_INFO` 原始响应先落入 raw payload，再保存只追加的字段快照；读取 `GET /api/v1/funds/{fund_id}/basic-info-history` 可查看原始字段、规范化字段、来源适配器版本、`available_at` 和可用时间质量。相同内容不产生新快照；字段变化产生新版本。AKShare 未提供公告/可用时刻时，按抓取时刻标记为 `INFERRED`，不回填更早时间。

`NAV` 对该产品所有已登记的 AKShare 份额类别补齐上游可提供的完整历史，并连同分红/拆分数据抓取。按份额类别和估值日比较内容；重复值不增加修订，值变化增加 NAV 版本。复权值按现有后复权规则重建，不可用时保持不可用。当前数据源接口返回完整历史，不支持传起止日期；页面因此展示“补齐上游可用完整历史”，不提供会造成误解的日期范围控件。

数据库升级需应用后续 Alembic migrations。此接口仅接受真实持久化 worker 模式；worker 未启用时返回 `503`，不会显示虚构的成功任务。生产 `can_manage_data_ingestion` 必须由已验证身份提供，开发环境角色映射不能作为生产授权。

| 版本 | 日期 | 变更 | 影响范围 |
|---|---|---|---|
| v1.1 | 2026-10-26 | 增补五维筛选、真实分类修订/证据/历史和复核 capability/CAS 接口 | Fund API、Web、OpenAPI/Orval、CLI；其余 M1.7 路径语义保持 |
| v1.2 | 2026-10-26 | 增加基金基本信息快照历史、NAV/基本信息异步抓取任务与 capability | Fund API、data worker、数据库迁移、Web、OpenAPI/Orval |
| v1.3 | 2026-10-27 | 抓取任务查询响应公开数据来源与触发人，供有权限用户审计操作 | Fund ingestion task response、Web、OpenAPI/Orval |
