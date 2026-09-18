import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { PortfolioDecisionPage } from "../../pages/PortfolioDecisionPage";

const requests: Array<{ url: URL; body?: unknown; headers: Headers }> = [];
let canReview = false;
let operationCalls = 0;

const responseMeta = {
  request_id: "REQ-PORTFOLIO",
  as_of_date: "2026-09-16",
  data_version: "portfolio-data-v4",
  versions: {
    portfolio_rule_version: "rule-v7",
    risk_model_version: "risk-v3",
  },
  is_point_in_time: true,
  availability_quality_distribution: { EXACT: 2, DERIVED: 0, INFERRED: 0 },
};

const portfolio = {
  portfolio_id: "P001",
  portfolio_name: "稳健组合",
  portfolio_type: "MUTUAL_FUND",
  status: "ACTIVE",
  base_currency: "CNY",
  portfolio_version: "portfolio-v12",
  risk_profile: "BALANCED",
  portfolio_benchmark: { benchmark_id: "CSI300", benchmark_name: "沪深300" },
  portfolio_rule_version: "rule-v7",
};

const optimization = {
  optimization_id: "OPT-1042",
  optimization_status: "INFEASIBLE",
  target_weights: null,
  objective_value: null,
  objective_value_status: "UNAVAILABLE",
  objective_value_reason: "NO_FEASIBLE_SOLUTION",
  binding_constraints: ["MAX_FUND_WEIGHT:F001"],
  conflicting_constraints: ["MIN_HOLDINGS", "MAX_FUND_WEIGHT"],
  shadow_prices: {},
  post_optimization_risk: {
    portfolio_volatility: null,
    portfolio_volatility_status: "UNAVAILABLE",
    portfolio_volatility_reason: "NO_FEASIBLE_SOLUTION",
  },
  excluded_candidates: [
    { fund_id: "000002", reason: "COVARIANCE_UNAVAILABLE" },
  ],
  solve_path: "STRUCTURAL_FEASIBILITY_CHECK",
};

const proposedDecision = {
  decision_id: "D-001",
  portfolio_id: "P001",
  optimization_id: "OPT-0001",
  decision_status: "PROPOSED",
  proposed_weights: [{ fund_id: "000001", weight: 0.6 }],
  review: null,
  final_weights: null,
};

const server = setupServer(
  http.get("/api/v1/session", () =>
    HttpResponse.json({
      data: {
        user_id: "USR-001",
        roles: canReview ? ["Portfolio Manager"] : ["Researcher"],
        capabilities: { can_review_decisions: canReview },
      },
      meta: { request_id: "REQ-SESSION" },
      error: null,
    }),
  ),
  http.get("/api/v1/portfolios", () =>
    HttpResponse.json({
      data: [portfolio],
      meta: {
        ...responseMeta,
        pagination: { page: 1, page_size: 20, total: 1 },
      },
      error: null,
    }),
  ),
  http.get("/api/v1/portfolios/:portfolioId", () =>
    HttpResponse.json({ data: portfolio, meta: responseMeta, error: null }),
  ),
  http.post(
    "/api/v1/portfolios/:portfolioId/optimizations",
    async ({ request }) => {
      requests.push({
        url: new URL(request.url),
        body: await request.json(),
        headers: request.headers,
      });
      return HttpResponse.json(
        {
          data: {
            operation_id: "OP-8f3c",
            optimization_id: "OPT-1042",
            status: "RUNNING",
          },
          meta: { request_id: "REQ-SUBMIT" },
          error: null,
        },
        { status: 202 },
      );
    },
  ),
  http.get("/api/v1/operations/:operationId", () => {
    operationCalls += 1;
    const completed = operationCalls > 1;
    return HttpResponse.json({
      data: {
        operation_id: "OP-8f3c",
        status: completed ? "COMPLETED" : "RUNNING",
        progress: { completed: completed ? 10 : 3, total: 10, unit: "steps" },
        result_ref: completed
          ? "/api/v1/portfolios/P001/optimizations/OPT-1042"
          : null,
        failure: null,
      },
      meta: { request_id: "REQ-OPERATION" },
      error: null,
    });
  }),
  http.get(
    "/api/v1/portfolios/:portfolioId/optimizations/:optimizationId",
    () =>
      HttpResponse.json({
        data: optimization,
        meta: {
          ...responseMeta,
          portfolio_rule_version: "rule-v7",
          return_estimate_version: "return-v5",
          risk_model_version: "risk-v3",
          code_version: "optimizer-1.4.0",
        },
        error: null,
      }),
  ),
  http.get("/api/v1/decisions/:decisionId", () =>
    HttpResponse.json({
      data: proposedDecision,
      meta: responseMeta,
      error: null,
    }),
  ),
  http.post("/api/v1/decisions/:decisionId/review", async ({ request }) => {
    requests.push({
      url: new URL(request.url),
      body: await request.json(),
      headers: request.headers,
    });
    return HttpResponse.json({
      data: {
        ...proposedDecision,
        decision_status: "OVERRIDDEN",
        review: {
          action: "OVERRIDDEN",
          reason: "降低单一基金集中度",
          reviewed_by: "USR-001",
          reviewed_at: "2026-09-16T09:00:00Z",
        },
        final_weights: [{ fund_id: "000001", weight: 0.5 }],
      },
      meta: responseMeta,
      error: null,
    });
  }),
);

const renderPage = (initialEntry = "/portfolios/P001") => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/portfolios" element={<PortfolioDecisionPage />} />
          <Route
            path="/portfolios/:portfolioId"
            element={<PortfolioDecisionPage pollIntervalMs={1} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  requests.length = 0;
  operationCalls = 0;
  canReview = false;
});
afterAll(() => server.close());

describe("PortfolioDecisionPage", () => {
  it("submits only frozen version references with an idempotency key", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.type(screen.getByLabelText("决策日期"), "2026-09-16");
    await user.type(screen.getByLabelText("候选池 ID"), "UNI-001");
    await user.type(screen.getByLabelText("收益估计版本"), "return-v5");
    await user.type(screen.getByLabelText("风险模型版本"), "risk-v3");
    await user.click(screen.getByRole("button", { name: "提交优化" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({
      decision_at: "2026-09-16",
      universe_id: "UNI-001",
      portfolio_rule_version: "rule-v7",
      return_estimate_version: "return-v5",
      risk_model_version: "risk-v3",
      mode: "REBALANCE",
    });
    expect(requests[0].headers.get("Idempotency-Key")).toBeTruthy();
    expect(requests[0].body).not.toHaveProperty("expected_returns");
    expect(requests[0].body).not.toHaveProperty("covariance_matrix");
  });

  it("polls the operation, follows result_ref, and renders infeasible diagnostics without substitute weights", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.type(screen.getByLabelText("决策日期"), "2026-09-16");
    await user.type(screen.getByLabelText("候选池 ID"), "UNI-001");
    await user.type(screen.getByLabelText("收益估计版本"), "return-v5");
    await user.type(screen.getByLabelText("风险模型版本"), "risk-v3");
    await user.click(screen.getByRole("button", { name: "提交优化" }));

    expect(await screen.findByText("无可行解（INFEASIBLE）")).toBeVisible();
    expect(screen.getByText("MIN_HOLDINGS")).toBeVisible();
    expect(screen.getByText("MAX_FUND_WEIGHT")).toBeVisible();
    expect(screen.getByText("MAX_FUND_WEIGHT:F001")).toBeVisible();
    expect(screen.getByText("非 OPTIMAL 结果不产出权重。")).toBeVisible();
    expect(
      screen.queryByRole("region", { name: "目标权重" }),
    ).not.toBeInTheDocument();
    expect(operationCalls).toBeGreaterThanOrEqual(2);
  });

  it("does not expose decision review controls without the server capability", async () => {
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    expect(screen.getByText("当前会话无决策复核权限。")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "批准" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "拒绝" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "覆盖" }),
    ).not.toBeInTheDocument();
  });

  it("submits a PM override and keeps original and final weights separate", async () => {
    canReview = true;
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.type(screen.getByLabelText("决策 ID"), "D-001");
    await user.click(screen.getByRole("button", { name: "加载决策" }));
    expect(await screen.findByText("000001 60.00%")).toBeVisible();

    await user.type(screen.getByLabelText("复核原因"), "降低单一基金集中度");
    await user.type(
      screen.getByLabelText("覆盖权重（每行：基金ID,小数权重）"),
      "000001,0.5",
    );
    await user.click(screen.getByRole("button", { name: "覆盖" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({
      action: "OVERRIDDEN",
      reason: "降低单一基金集中度",
      overridden_weights: [{ fund_id: "000001", weight: 0.5 }],
    });
    expect(await screen.findByText("000001 50.00%")).toBeVisible();
    expect(screen.getByRole("region", { name: "原始建议权重" })).toBeVisible();
    expect(screen.getByRole("region", { name: "最终权重" })).toBeVisible();
  });
});
