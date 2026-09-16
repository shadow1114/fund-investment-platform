# M1.7 前端接口契约冻结

> 本文冻结范围：M1.7 的四个前端页面与横切组件所消费的 `/api/v1` 契约。
> 本文不冻结全部 API，不替代各领域 API 文档；路径、业务字段和状态语义以本文及所引用章节为准。
> 上游：`docs/superpowers/specs/2026-08-31-fund-platform-m1-design.md` §6.5、`docs/10-api/01-api-overview.md`。

**文档版本**：v1.0 ｜ **状态**：M1.7 前端消费范围已冻结 ｜ **日期**：2026-09-16

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
| 基金检索与详情 | `GET /api/v1/funds`；`GET /api/v1/funds/{fund_id}`；`GET /api/v1/funds/{fund_id}/nav-series`；`GET /api/v1/funds/{fund_id}/evaluations`；`GET /api/v1/funds/{fund_id}/scores` | `02-fund-api.md` §3、§4.1–§4.5 |
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
    "capabilities": { "can_review_decisions": true }
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

复核写入仍使用 `04-portfolio-api.md` §4.8：`APPROVED` / `REJECTED` / `OVERRIDDEN`；Override 的 `reason` 必填，且需返回前后权重。业务执行失败必须依原契约通过业务状态表达，不可由前端把 HTTP 任务完成等同于决策获批。

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
| `FA-1` 基金 API 路径 | 仅 §2 列出的基金检索/详情、净值、评价/评分、候选池路径对 M1.7 冻结；不扩展到所有 Fund API |
| `PA-1` 组合 API 路径 | 仅 §2、§3 列出的组合列表/详情、优化、决策与 Operation 路径对 M1.7 冻结 |
| `BA-1` 回测 API 路径 | 仅 §2 列出的 M1.7 回测端点对 M1.7 冻结；报告导出等仍未定 |
| `API-6` 认证机制 | 保留；标准 HTTP 认证信息与 session 用户/角色读取契约已明确，具体协议不在本文范围 |
| `API-7` 资源级授权 | 保留服务端必须授权的约束；可见性规则细节未定 |
| `API-8` 异步阈值/SLA | 保留通用阈值/SLA；优化与回测执行在 M1.7 契约中明确为异步 |
