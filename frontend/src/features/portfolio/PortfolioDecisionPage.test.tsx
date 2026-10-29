import { MantineProvider } from "@mantine/core";
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
  proposed_weights: [
    { fund_id: "000001", weight: 0.6 },
    { fund_id: "000002", weight: 0.4 },
  ],
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
  http.get("/api/v1/fund-universes", () =>
    HttpResponse.json({ data: [], meta: responseMeta, error: null }),
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
  http.post(
    "/api/v1/decisions/:decisionId/review",
    async ({ request, params }) => {
      requests.push({
        url: new URL(request.url),
        body: await request.json(),
        headers: request.headers,
      });
      return HttpResponse.json({
        data: {
          decision_id: String(params.decisionId),
          decision_status: "OVERRIDDEN",
          reason: "降低单一基金集中度",
          reviewed_by: "USR-001",
          reviewed_at: "2026-09-16T09:00:00Z",
          original_weights: [
            { fund_id: "000001", weight: 0.6 },
            { fund_id: "000002", weight: 0.4 },
          ],
          final_weights: [
            { fund_id: "000001", weight: 0.5 },
            { fund_id: "000002", weight: 0.5 },
          ],
        },
        meta: { audit_id: "AUDIT-001" },
        error: null,
      });
    },
  ),
);

const renderPage = (initialEntry = "/portfolios/P001") => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <MantineProvider>
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
      </QueryClientProvider>
    </MantineProvider>,
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
  it("does not expose unsupported live and rebalancing controls, including on old URLs", async () => {
    renderPage("/portfolios/P001?tab=live");
    await screen.findByRole("heading", { name: "稳健组合" });
    expect(
      screen.queryByRole("tab", { name: "实盘持仓" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: "再平衡" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "组合优化" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
  it("submits only frozen version references with an idempotency key", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.type(screen.getByLabelText(/决策日期/), "2026-09-16");
    await user.type(screen.getByLabelText(/手动输入真实候选池 ID/), "UNI-001");
    await user.type(screen.getByLabelText(/收益估计版本/), "return-v5");
    await user.type(screen.getByLabelText(/风险模型版本/), "risk-v3");
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
    await user.type(screen.getByLabelText(/决策日期/), "2026-09-16");
    await user.type(screen.getByLabelText(/手动输入真实候选池 ID/), "UNI-001");
    await user.type(screen.getByLabelText(/收益估计版本/), "return-v5");
    await user.type(screen.getByLabelText(/风险模型版本/), "risk-v3");
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
    await userEvent
      .setup()
      .click(screen.getByRole("tab", { name: "决策复核" }));
    expect(screen.getByText("当前会话没有决策复核权限。")).toBeVisible();
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
    await user.click(screen.getByRole("tab", { name: "决策复核" }));
    await user.type(screen.getByLabelText("决策 ID"), "D-001");
    await user.click(screen.getByRole("button", { name: "加载决策" }));
    expect(await screen.findByText("000001 60.00%")).toBeVisible();

    await user.type(
      await screen.findByLabelText(/复核理由/),
      "降低单一基金集中度",
    );
    await user.clear(screen.getByLabelText("000001 覆盖权重"));
    await user.type(screen.getByLabelText("000001 覆盖权重"), "0.5");
    await user.clear(screen.getByLabelText("000002 覆盖权重"));
    await user.type(screen.getByLabelText("000002 覆盖权重"), "0.5");
    await user.click(screen.getByRole("button", { name: "确认覆盖" }));
    await user.click(await screen.findByRole("button", { name: "确认提交" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({
      action: "OVERRIDDEN",
      reason: "降低单一基金集中度",
      overridden_weights: [
        { fund_id: "000001", weight: 0.5 },
        { fund_id: "000002", weight: 0.5 },
      ],
    });
    expect(await screen.findByText("000001 50.00%")).toBeVisible();
    expect(screen.getByRole("region", { name: "原始建议权重" })).toBeVisible();
    expect(screen.getByRole("region", { name: "最终权重" })).toBeVisible();
    expect(screen.getByText("复核人：USR-001")).toBeVisible();
    expect(screen.getByText("审计 ID：AUDIT-001")).toBeVisible();
  });

  it("loads decision B without showing or submitting decision A's review", async () => {
    canReview = true;
    server.use(
      http.get("/api/v1/decisions/:decisionId", ({ params }) =>
        HttpResponse.json({
          data:
            String(params.decisionId) === "D-002"
              ? {
                  ...proposedDecision,
                  decision_id: "D-002",
                  proposed_weights: [
                    { fund_id: "000002", weight: 0.7 },
                    { fund_id: "000001", weight: 0.3 },
                  ],
                }
              : proposedDecision,
          meta: responseMeta,
          error: null,
        }),
      ),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.click(screen.getByRole("tab", { name: "决策复核" }));
    await user.type(screen.getByLabelText("决策 ID"), "D-001");
    await user.click(screen.getByRole("button", { name: "加载决策" }));
    await screen.findByText("000001 60.00%");
    await user.type(await screen.findByLabelText(/复核理由/), "复核 A");
    await user.clear(screen.getByLabelText("000001 覆盖权重"));
    await user.type(screen.getByLabelText("000001 覆盖权重"), "0.5");
    await user.clear(screen.getByLabelText("000002 覆盖权重"));
    await user.type(screen.getByLabelText("000002 覆盖权重"), "0.5");
    await user.click(screen.getByRole("button", { name: "确认覆盖" }));
    await user.click(await screen.findByRole("button", { name: "确认提交" }));
    await screen.findByText("000001 50.00%");

    await user.clear(screen.getByLabelText("决策 ID"));
    await user.type(screen.getByLabelText("决策 ID"), "D-002");
    await user.click(screen.getByRole("button", { name: "加载决策" }));
    expect(await screen.findByText("000002 70.00%")).toBeVisible();
    expect(screen.queryByText("000001 50.00%")).not.toBeInTheDocument();
    expect(screen.queryByText("复核人：USR-001")).not.toBeInTheDocument();
    expect(await screen.findByLabelText(/复核理由/)).toHaveValue("");
    expect(screen.getByLabelText("000001 覆盖权重")).toHaveValue("0.3（小数）");

    await user.type(await screen.findByLabelText(/复核理由/), "复核 B");
    await user.click(screen.getByRole("button", { name: "批准" }));
    await user.click(await screen.findByRole("button", { name: "确认提交" }));
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].url.pathname).toBe("/api/v1/decisions/D-002/review");
    expect(requests[1].body).toEqual({ action: "APPROVED", reason: "复核 B" });
  });

  it("keeps the current review outcome when reloading the same decision ID", async () => {
    canReview = true;
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "稳健组合" });
    await user.click(screen.getByRole("tab", { name: "决策复核" }));
    await user.type(screen.getByLabelText("决策 ID"), "D-001");
    await user.click(screen.getByRole("button", { name: "加载决策" }));
    await screen.findByText("000001 60.00%");
    await user.type(await screen.findByLabelText(/复核理由/), "复核后重新加载");
    await user.click(screen.getByRole("button", { name: "批准" }));
    await user.click(await screen.findByRole("button", { name: "确认提交" }));
    await screen.findByText("审计 ID：AUDIT-001");

    await user.click(screen.getByRole("button", { name: "加载决策" }));

    expect(await screen.findByText("审计 ID：AUDIT-001")).toBeVisible();
    expect(screen.getByText("复核人：USR-001")).toBeVisible();
  });
});
