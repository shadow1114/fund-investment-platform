import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { BacktestPage } from "../../pages/BacktestPage";

vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: { series: { name: string }[] } }) => (
    <div aria-label="回测绩效图">
      {option.series.map((series) => series.name).join("、")}
    </div>
  ),
}));

const requests: Array<{
  method: string;
  url: URL;
  body?: unknown;
  headers: Headers;
}> = [];
let operationCalls = 0;

const meta = {
  request_id: "REQ-BACKTEST",
  versions: { data_version: "market-v12", metric_version: "metric-v8" },
  is_point_in_time: true,
  availability_quality_distribution: {
    EXACT: 0.62,
    DERIVED: 0.31,
    INFERRED: 0.07,
  },
};

const metric = {
  total_return: 0.12,
  annualized_return: 0.0742,
  volatility: 0.13,
  max_drawdown: 0.08,
  sharpe_ratio: null,
  sharpe_ratio_status: "UNAVAILABLE",
  sharpe_ratio_reason: "INSUFFICIENT_SAMPLE",
};

const unavailableLayer = {
  passed: null,
  passed_status: "UNAVAILABLE",
  passed_reason: "THRESHOLDS_PENDING",
};

const result = {
  backtest_id: "BT-001",
  status: "COMPLETED",
  validation_status: "INVALID",
  backtest_mode: "CURRENT_RULE",
  period: {
    start_date: "2020-01-01",
    end_date: "2026-06-30",
    warm_up_end_date: "2021-01-04",
  },
  initial_capital: { amount: "1000000.00", currency: "CNY" },
  final_value: { amount: "1120000.00", currency: "CNY" },
  summary: {
    portfolio: metric,
    benchmark: { ...metric, annualized_return: 0.061 },
    equal_weight_baseline: null,
    equal_weight_baseline_status: "UNAVAILABLE",
    equal_weight_baseline_reason: "BASELINE_DISABLED",
  },
  excess_return: {
    vs_benchmark: 0.018,
    vs_benchmark_status: "VALID",
    vs_benchmark_reason: null,
    vs_equal_weight: null,
    vs_equal_weight_status: "UNAVAILABLE",
    vs_equal_weight_reason: "BASELINE_DISABLED",
  },
  significance_verdict: {
    overall: "CANNOT_DETERMINE",
    thresholds_status: "PENDING_CALIBRATION",
    layers: {
      statistical: {
        ...unavailableLayer,
        bootstrap_ci_lower_vs_benchmark: null,
        bootstrap_ci_lower_vs_benchmark_status: "UNAVAILABLE",
        bootstrap_ci_lower_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
        bootstrap_ci_lower_vs_equal_weight: null,
        bootstrap_ci_lower_vs_equal_weight_status: "UNAVAILABLE",
        bootstrap_ci_lower_vs_equal_weight_reason: "BASELINE_DISABLED",
      },
      effect_size: {
        ...unavailableLayer,
        ir_vs_benchmark: null,
        ir_vs_benchmark_status: "UNAVAILABLE",
        ir_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
        ir_vs_equal_weight: null,
        ir_vs_equal_weight_status: "UNAVAILABLE",
        ir_vs_equal_weight_reason: "BASELINE_DISABLED",
        delta_sharpe_vs_benchmark: null,
        delta_sharpe_vs_benchmark_status: "UNAVAILABLE",
        delta_sharpe_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
        delta_sharpe_vs_equal_weight: null,
        delta_sharpe_vs_equal_weight_status: "UNAVAILABLE",
        delta_sharpe_vs_equal_weight_reason: "BASELINE_DISABLED",
      },
      robustness: {
        ...unavailableLayer,
        outperform_ratio_vs_benchmark: null,
        outperform_ratio_vs_benchmark_status: "UNAVAILABLE",
        outperform_ratio_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
        outperform_ratio_vs_equal_weight: null,
        outperform_ratio_vs_equal_weight_status: "UNAVAILABLE",
        outperform_ratio_vs_equal_weight_reason: "BASELINE_DISABLED",
      },
      economic: {
        ...unavailableLayer,
        annualized_return_improvement_vs_benchmark: null,
        annualized_return_improvement_vs_benchmark_status: "UNAVAILABLE",
        annualized_return_improvement_vs_benchmark_reason:
          "INSUFFICIENT_SAMPLE",
        annualized_return_improvement_vs_equal_weight: null,
        annualized_return_improvement_vs_equal_weight_status: "UNAVAILABLE",
        annualized_return_improvement_vs_equal_weight_reason:
          "BASELINE_DISABLED",
        max_drawdown_improvement_vs_benchmark: null,
        max_drawdown_improvement_vs_benchmark_status: "UNAVAILABLE",
        max_drawdown_improvement_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
        max_drawdown_improvement_vs_equal_weight: null,
        max_drawdown_improvement_vs_equal_weight_status: "UNAVAILABLE",
        max_drawdown_improvement_vs_equal_weight_reason: "BASELINE_DISABLED",
      },
    },
  },
  validation_summary: {
    warnings: ["TRADABILITY_NOT_VERIFIED"],
    invalid_reasons: ["BIAS_CHECK_INCOMPLETE"],
  },
};

const point = (
  date: string,
  value: number | null,
  reason: string | null = null,
) => ({
  date,
  value,
  value_status: value === null ? "UNAVAILABLE" : "VALID",
  value_reason: reason,
});

const server = setupServer(
  http.post("/api/v1/backtests", async ({ request }) => {
    requests.push({
      method: request.method,
      url: new URL(request.url),
      body: await request.json(),
      headers: request.headers,
    });
    return HttpResponse.json(
      {
        data: {
          backtest_id: "BT-001",
          status: "CREATED",
          created_at: "2026-09-19T08:00:00Z",
        },
        meta,
        error: null,
      },
      { status: 201 },
    );
  }),
  http.post(
    "/api/v1/backtests/:backtestId/validate-configuration",
    ({ request }) => {
      requests.push({
        method: request.method,
        url: new URL(request.url),
        headers: request.headers,
      });
      return HttpResponse.json({
        data: {
          validation_result: "PASS_WITH_WARNINGS",
          warm_up_end_date: "2021-01-04",
          effective_period: { from: "2021-01-04", to: "2026-06-30" },
          in_sample_length_days: 1091,
          out_of_sample_length_days: 912,
          warnings: [{ code: "OOS_PERIOD_SHORT", message: "样本外区间偏短" }],
          blocking_issues: [],
        },
        meta,
        error: null,
      });
    },
  ),
  http.post("/api/v1/backtests/:backtestId/runs", ({ request }) => {
    requests.push({
      method: request.method,
      url: new URL(request.url),
      headers: request.headers,
    });
    return HttpResponse.json(
      {
        data: {
          operation_id: "OP-BT-1",
          backtest_id: "BT-001",
          status: "RUNNING",
        },
        meta,
        error: null,
      },
      { status: 202 },
    );
  }),
  http.get("/api/v1/operations/:operationId", () => {
    operationCalls += 1;
    const completed = operationCalls > 1;
    return HttpResponse.json({
      data: {
        operation_id: "OP-BT-1",
        status: completed ? "COMPLETED" : "RUNNING",
        progress: { completed: completed ? 6 : 2, total: 6, unit: "periods" },
        result_ref: completed ? "/api/v1/backtests/BT-001/result" : null,
        failure: null,
      },
      meta,
      error: null,
    });
  }),
  http.get("/api/v1/backtests/:backtestId/status", () =>
    HttpResponse.json({
      data: {
        backtest_id: "BT-001",
        status: "COMPLETED",
        validation_status: "INVALID",
        progress: {
          current_decision_date: "2026-06-30",
          completed_periods: 6,
          total_periods: 6,
          total_periods_is_estimate: true,
        },
        started_at: "2026-09-19T08:01:00Z",
      },
      meta,
      error: null,
    }),
  ),
  http.get("/api/v1/backtests/:backtestId/result", () =>
    HttpResponse.json({
      data: result,
      meta: {
        ...meta,
        configuration_version: "config-v1",
        data_version: "market-v12",
        strategy_versions: {
          metric_version: "metric-v8",
          scoring_version: "score-v6",
          portfolio_rule_version: "portfolio-v4",
          rebalance_rule_version: "rebalance-v3",
          return_estimate_version: "return-v5",
          risk_model_version: "risk-v7",
          eligibility_universe_version: "eligibility-v4",
          benchmark_version: "benchmark-v2",
          peer_group_classification_version: "peer-v9",
        },
        code_version: "backtest-1.4.0",
        transaction_cost_model_version: "cost-v2",
        methodology_policy_version: "method-v3",
        report_policy_version: "report-v2",
      },
      error: null,
    }),
  ),
  http.get("/api/v1/backtests/:backtestId/performance", () =>
    HttpResponse.json({
      data: {
        segment: "FULL",
        series: {
          portfolio_value: [point("2026-06-30", 1120000)],
          cumulative_return: {
            portfolio: [point("2026-06-30", 0.12)],
            benchmark: [point("2026-06-30", 0.1)],
            equal_weight_baseline: null,
            equal_weight_baseline_status: "UNAVAILABLE",
            equal_weight_baseline_reason: "BASELINE_DISABLED",
          },
          drawdown: [point("2026-06-30", -0.08)],
          rolling_sharpe: [point("2026-06-30", null, "INSUFFICIENT_SAMPLE")],
          rolling_excess_return: [point("2026-06-30", 0.02)],
        },
      },
      meta: { ...meta, warm_up_end_date: "2021-01-04" },
      error: null,
    }),
  ),
  http.get("/api/v1/backtests/:backtestId/bias-check", () =>
    HttpResponse.json({
      data: {
        backtest_id: "BT-001",
        checks: {
          look_ahead_bias: { status: "PASS", violations: [] },
          survivorship_bias: { status: "PASS", violations: [] },
          tradability_bias: {
            status: "NOT_VERIFIED",
            reason: "INVESTMENT_ELIGIBILITY_HISTORY_INCOMPLETE",
            affected_periods: 12,
          },
          point_in_time: {
            status: "PASS",
            availability_quality_distribution: {
              EXACT: 0.62,
              DERIVED: 0.31,
              INFERRED: 0.07,
            },
          },
          transaction_cost: {
            status: "PARTIALLY_MODELED",
            unmodeled_costs: ["BID_ASK_SPREAD", "MARKET_IMPACT"],
          },
          subscription_redemption_lag: { status: "NOT_MODELED" },
        },
        snapshot_summary: {
          snapshot_periods: 56,
          rebuilt_periods: 12,
          total_periods: 68,
          rebuilt_period_list: ["2019-03-29"],
        },
        data_limitations: ["历史可投资性数据不完整"],
      },
      meta,
      error: null,
    }),
  ),
);

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/backtests"]}>
        <Routes>
          <Route
            path="/backtests"
            element={<BacktestPage pollIntervalMs={1} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const fillForm = async () => {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("策略 ID"), "STRATEGY-1");
  await user.type(screen.getByLabelText("开始日期"), "2020-01-01");
  await user.type(screen.getByLabelText("结束日期"), "2026-06-30");
  await user.clear(screen.getByLabelText("初始资金"));
  await user.type(screen.getByLabelText("初始资金"), "1000000.00");
  await user.type(screen.getByLabelText("基准 ID"), "CSI300");
  await user.type(screen.getByLabelText("再平衡政策版本"), "rebalance-v3");
  await user.type(screen.getByLabelText("组合规则版本"), "portfolio-v4");
  await user.type(screen.getByLabelText("收益估计版本"), "return-v5");
  await user.type(screen.getByLabelText("风险模型版本"), "risk-v7");
  await user.type(screen.getByLabelText("资格规则版本"), "eligibility-v4");
  await user.type(screen.getByLabelText("交易成本模型版本"), "cost-v2");
  return user;
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  requests.length = 0;
  operationCalls = 0;
});
afterAll(() => server.close());

describe("BacktestPage", () => {
  it("keeps create, validation, and run as an explicit sequence with the frozen request", async () => {
    renderPage();
    const user = await fillForm();

    expect(screen.getByRole("button", { name: "校验配置" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "启动回测" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "创建回测" }));

    expect(
      await screen.findByText("已创建回测 BT-001，尚未执行。"),
    ).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0].body).toEqual({
      strategy_id: "STRATEGY-1",
      start_date: "2020-01-01",
      end_date: "2026-06-30",
      initial_capital: { amount: "1000000.00", currency: "CNY" },
      backtest_mode: "CURRENT_RULE",
      benchmark_id: "CSI300",
      equal_weight_baseline_enabled: true,
      rebalancing_policy_version: "rebalance-v3",
      portfolio_rule_version: "portfolio-v4",
      return_estimate_version: "return-v5",
      risk_model_version: "risk-v7",
      eligibility_rules_version: "eligibility-v4",
      transaction_cost_model_version: "cost-v2",
      execution_price_rule: "NEXT_DAY_NAV",
      cash_return_assumption: "ZERO",
      infeasible_handling: "ABORT",
    });

    await user.click(screen.getByRole("button", { name: "校验配置" }));
    expect(
      await screen.findByText("通过，但有警告（PASS_WITH_WARNINGS）"),
    ).toBeVisible();
    expect(
      screen.getByText("有效区间：2021-01-04 至 2026-06-30"),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "启动回测" }));
    await waitFor(() => expect(operationCalls).toBeGreaterThanOrEqual(2));
    expect(requests.map((request) => request.url.pathname)).toEqual([
      "/api/v1/backtests",
      "/api/v1/backtests/BT-001/validate-configuration",
      "/api/v1/backtests/BT-001/runs",
    ]);
    expect(requests[2].headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("keeps COMPLETED plus INVALID inspectable and exposes missing bias evidence", async () => {
    renderPage();
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: "创建回测" }));
    await screen.findByText("已创建回测 BT-001，尚未执行。");
    await user.click(screen.getByRole("button", { name: "校验配置" }));
    await screen.findByText("通过，但有警告（PASS_WITH_WARNINGS）");
    await user.click(screen.getByRole("button", { name: "启动回测" }));

    expect(
      await screen.findByText("执行已完成，但验证结果为 INVALID。"),
    ).toBeVisible();
    expect(screen.getByText(/BIAS_CHECK_INCOMPLETE/)).toBeVisible();
    expect(
      screen.getAllByText("不可用（INSUFFICIENT_SAMPLE）").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("不可用（BASELINE_DISABLED）")).toBeVisible();
    expect(screen.getByLabelText("回测绩效图")).toHaveTextContent("组合、基准");
    expect(
      screen.getAllByText("等权基线不可用（BASELINE_DISABLED）"),
    ).toHaveLength(2);

    const bias = screen.getByRole("region", { name: "偏差检查" });
    expect(within(bias).getByText("NOT_VERIFIED")).toBeVisible();
    expect(
      within(bias).getByText("INVESTMENT_ELIGIBILITY_HISTORY_INCOMPLETE"),
    ).toBeVisible();
    expect(within(bias).getByText("BID_ASK_SPREAD")).toBeVisible();
    expect(within(bias).getByText("MARKET_IMPACT")).toBeVisible();
    expect(
      within(bias).getByText("缺少验证或未建模证据，本回测不可作为决策依据。"),
    ).toBeVisible();
    expect(screen.getByText("点时数据：是")).toBeVisible();
    expect(
      screen.getByText("transaction_cost_model_version: cost-v2"),
    ).toBeVisible();
  });
});
