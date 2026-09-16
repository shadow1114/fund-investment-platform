# Plan-4 M1.7 前端接口契约冻结设计

## 1. 目标与范围

为 M1.7 四个前端页面建立可直接消费、可生成类型客户端的稳定 API 边界：基金检索与详情、候选池快照、组合决策、回测。复用现有 `docs/10-api` 领域契约，只补齐页面依赖的路径与跨域交互，不重写整个 API 体系。

本设计冻结的是 M1.7 客户端消费切片，不代表对应 Web server 已实现，也不冻结其他 API。字段和业务语义继续由 `docs/10-api/01-api-overview.md` 与领域 API 文档定义。

## 2. 方案选择

采用“窄范围消费者契约”方案：以 `docs/10-api/06-m17-frontend-contracts.md` 为 M1.7 页面到端点的绑定清单，以 `02-fund-api.md`、`04-portfolio-api.md`、`05-backtest-api.md` 的字段级契约为细节权威。OpenAPI 3.1.0 是这些契约的机器可读投影，供生成式 API client 消费。

不采用一次冻结全部 API 的方案：全局认证协议、资源授权细则、错误码全集、生产 SLA、限流和外部交易回报均超出四个页面所需范围，仍交由各自责任方处理。也不要求等 API server 完成后才启动前端；契约与 OpenAPI 可先冻结，server 后续实现须符合它们。

## 3. 关键契约决策

1. M1.7 前端所列 Fund、Universe、Portfolio、Decision、Backtest 路径固定；未列端点路径不随之冻结。
2. 新增 `GET /api/v1/session`，返回已认证用户的角色和 `can_review_decisions` 能力，供界面呈现 RBAC。认证协议保持架构 TBD；客户端不得仅靠隐藏按钮实施授权。
3. 组合优化与回测执行在 M1.7 固定异步：命令返回 `202`，统一轮询 `GET /api/v1/operations/{operation_id}`。Operation 技术状态与优化、决策、回测业务状态分离；业务结果由稳定的 `result_ref` 导向相应资源。
4. 增加组合优化结果读取与决策快照读取端点，使页面不依赖 Operation 响应内嵌业务结果，也不覆盖原始建议权重。
5. 所有响应保留统一 envelope、版本/PIT 元数据、明确的 `null` 与状态/原因、十进制传输语义。候选池页必须同时呈现 `SELECTED` 和 `REJECTED` 成员。

## 4. 影响文件与责任边界

| 文件 | 职责 |
|---|---|
| `docs/10-api/06-m17-frontend-contracts.md` | M1.7 的冻结端点清单、补充 session/Operation/决策读取契约、显示语义及未冻结事项 |
| `docs/10-api/01-api-overview.md` | 全局认证/Operation 契约的引用入口，继续记录尚未决定的 API-6/7/8 等事项 |
| `docs/10-api/02-fund-api.md` | 关闭仅针对 M1.7 端点的 FA-1 路径待定项 |
| `docs/10-api/04-portfolio-api.md` | 关闭 M1.7 路径范围，加入优化结果/决策读取，并明确优化的异步模式 |
| `docs/10-api/05-backtest-api.md` | 关闭仅针对 M1.7 回测端点的 BA-1 路径待定项 |
| `docs/superpowers/plans/2026-09-16-plan4-frontend.md` | 下一阶段的实施步骤；契约审核通过后创建 |

前端不得承载业务计算、PIT 授权判断或服务端权限边界。M1.7 实施计划将单独安排 OpenAPI 文档构建/校验和生成 client，不在本次冻结阶段创建 API server 或 UI 代码。

## 5. 验收标准

- 四个页面的每个 API 调用均映射到一个固定路径、方法和领域契约章节。
- 所有页面依赖的权限、长任务轮询、结果读取、空值和版本/PIT 呈现行为都有唯一说明。
- M1.7 消费范围内不存在“路径待接口评审”的冲突文本；范围外 TBD 仍明确保留。
- 计划任务可据此生成 OpenAPI 3.1.0 客户端，并通过构建期契约一致性检查。

## 6. 非目标与继续保留的待定项

认证协议与凭证生命周期、资源级可见性细则、全局异步时延/SLA、全 API 错误代码表、限流配额、外部执行系统回报以及回测报告文件导出不在此次设计中裁决。它们不得悄然改变 M1.7 已冻结的接口结构或语义。
