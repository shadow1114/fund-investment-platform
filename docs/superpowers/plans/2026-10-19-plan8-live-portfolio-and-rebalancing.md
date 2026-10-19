# Plan-8 Live Portfolio 与再平衡引擎实施计划

> **Goal:** 实现主干链路 Stage ⑨ Live Portfolio（实盘三态模型、外部成交回报接入、每日盯市漂移计算）与 Stage ⑩ Rebalancing（四类触发器、多触发并发最深合并、调仓买卖清单生成、最小交易与受限资产过滤、成本收益把关、全流程可解释性追溯）。

---

## 任务拆解与执行清单

### Task 1: 数据库迁移与 ORM 模型
* **文件**：
  * 创建 `db/migrations/versions/0033_live_portfolio_and_rebalancing.py`
  * 修改 `src/fip/services/portfolio_service/models.py`
  * 创建 `tests/integration/test_live_portfolio_schema.py`
* **内容**：
  * 新增 6 张核心数据表：`portfolio.live_portfolio`、`portfolio.portfolio_position`、`portfolio.execution_report`、`portfolio.rebalance_event`、`portfolio.rebalance_trade`、`portfolio.rebalance_policy`。
  * 补齐外键关联、索引及状态枚举校验。
  * 编写迁移与回滚集成测试，通过 `make migrate` 落地。

### Task 2: 实盘三态状态机与外部成交回报处理
* **文件**：
  * 创建 `src/fip/services/portfolio_service/live_portfolio.py`
  * 创建 `tests/unit/test_live_portfolio_state_machine.py`
* **内容**：
  * 实现从 `Approved Investment Decision` 初始化目标组合（`Target Portfolio`）。
  * 调仓交付时生成在途标记（`Pending Execution`，`has_pending_execution=True`）。
  * 处理外部成交回报（Execution Report）：全额成交（`FILLED`）、部分成交（`PARTIALLY_FILLED`）、拒绝（`REJECTED`）。
  * 外部回报更新实际持仓（`Actual Portfolio`）：更新持仓份额、平均成本、现金余额与在途状态。
  * 处理挂单超时（5 交易日未成交标记为 `EXPIRED` 并解除锁定）。

### Task 3: 每日净值盯市与偏离度（Drift）计算
* **文件**：
  * 创建 `src/fip/services/portfolio_service/drift.py`
  * 创建 `tests/unit/test_portfolio_drift.py`
* **内容**：
  * 接入 PIT NAV 净值序列，对持仓逐日更新市值与组合真实权重。
  * 计算有符号偏离（Signed Drift，用于展示与买卖方向）与绝对偏离（Absolute Drift，用于触发判定）。
  * 分离基金个券层偏离（Fund-level Drift）与资产大类层偏离（Category-level Drift）。
  * 准确排除冻结资产（`NOT_TRADABLE`）对偏离度判定的干扰。

### Task 4: 再平衡触发引擎与多触发最深范围合并
* **文件**：
  * 创建 `src/fip/services/portfolio_service/rebalance_trigger.py`
  * 创建 `tests/unit/test_rebalance_triggers.py`
* **内容**：
  * 实现四大触发器检测：
    1. `Periodic`：基于日历/交易日周期的定期调仓。
    2. `Drift`：基于绝对偏离阈值的阈值调仓。
    3. `Eligibility Event`：基于持仓中基金失去准入资格的事件调仓。
    4. `Constraint Breach`：基于持仓触碰合规与风险预算硬约束的调仓。
  * 存在未超时的 `Pending Execution` 时执行防重复拦截。
  * 实现多触发并发深度合并：`Constraint Breach` (1) < `Drift` (2) < `Eligibility Event` (3) < `Periodic` (4)。
  * 完整记录触发原因清单 `trigger_reasons`。

### Task 5: 调仓清单生成器与约束成本把关
* **文件**：
  * 创建 `src/fip/services/portfolio_service/rebalance_proposer.py`
  * 创建 `tests/unit/test_rebalance_proposer.py`
* **内容**：
  * 计算目标权重与实际权重的净调整量及单边换手率（`0.5 * sum(|w_target - w_actual|)`）。
  * 非凸最小交易阈值（Min Trade Threshold）过滤，过滤后重新检验约束。
  * 可投资性规则拦截：`HOLD_ONLY` 仅允许卖出禁止加仓，`NOT_TRADABLE` 冻结，显式记录未达成差额。
  * 成本收益判据（Cost-Benefit Gate）：将单次交易成本按持有期年化摊薄，比较年化预期改善，未达标时放弃调仓（`SKIPPED_COST_BENEFIT`）。
  * 产出结构化买卖清单与审计说明（Explainability）。

### Task 6: API 服务集成与路由扩展
* **文件**：
  * 修改 `src/fip/api/schemas.py`（增加实盘与再平衡契约模型）
  * 创建 `src/fip/api/routers/rebalance.py`
  * 修改 `src/fip/api/app.py`
  * 创建 `tests/api/test_rebalance_endpoints.py`
* **内容**：
  * 暴露 `GET /api/v1/portfolios/{id}/live`（获取三态持仓详情）。
  * 暴露 `POST /api/v1/portfolios/{id}/execution-reports`（模拟/接收成交回报）。
  * 暴露 `POST /api/v1/portfolios/{id}/rebalances/evaluate`（触发再平衡评估）。
  * 暴露 `GET /api/v1/portfolios/{id}/rebalances` 与 `/trades`。

### Task 7: 端到端全量验收
* **内容**：
  * 运行完整测试套件：`make check`、`make api-check`、`pytest tests/integration/test_live_portfolio_postgres.py`。
  * 验证所有类型检查（mypy）、代码风格（ruff）与测试覆盖率 100% 达标。
