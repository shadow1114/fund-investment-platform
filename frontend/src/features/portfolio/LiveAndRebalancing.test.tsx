import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { LivePortfolioPanel } from "./LivePortfolioPanel";
import { RebalancingPanel } from "./RebalancingPanel";
import { renderWithMantine as render } from "../../test/render";

const livePortfolioData = {
  portfolio_id: "P001",
  as_of_date: "2026-03-31",
  status: "ACTIVE",
  cash_balance: 150000.0,
  total_equity: 1000000.0,
  has_pending_execution: false,
  target_positions: [
    {
      fund_id: "000001",
      weight: 0.6,
      shares: 480000,
      market_price: 1.25,
      market_value: 600000.0,
    },
    {
      fund_id: "000002",
      weight: 0.4,
      shares: 300000,
      market_price: 0.85,
      market_value: 255000.0,
    },
  ],
  actual_positions: [
    {
      fund_id: "000001",
      weight: 0.55,
      shares: 440000,
      market_price: 1.25,
      market_value: 550000.0,
    },
    {
      fund_id: "000002",
      weight: 0.3,
      shares: 352941,
      market_price: 0.85,
      market_value: 300000.0,
    },
  ],
  pending_positions: [],
};

const rebalanceProposalData = {
  rebalance_id: "REB-20260331-001",
  portfolio_id: "P001",
  decision_at: "2026-03-31",
  primary_trigger: "DRIFT",
  secondary_triggers: [],
  recompute_scope: "NONE",
  turnover: 0.05,
  estimated_cost: 75.0,
  expected_improvement: 0.02,
  decision_outcome: "RECOMMENDED",
  explainability_summary: "偏离度触发阈值0.03，建议调仓并带来年化改善",
  trades: [
    {
      fund_id: "000001",
      direction: "BUY",
      current_weight: 0.55,
      target_weight: 0.6,
      weight_delta: 0.05,
      estimated_amount: 50000.0,
      delta_shares: 40000.0,
      eligibility_status: "NORMAL",
      is_filtered: false,
      unachieved_reason: null,
    },
  ],
};

let capturedReports: unknown[] = [];
let capturedEvaluations: unknown[] = [];

const server = setupServer(
  http.get("/api/v1/portfolios/:portfolioId/live", () => {
    return HttpResponse.json({
      data: livePortfolioData,
      meta: { request_id: "REQ-LIVE" },
      error: null,
    });
  }),
  http.post(
    "/api/v1/portfolios/:portfolioId/execution-reports",
    async ({ request }) => {
      const body = await request.json();
      capturedReports.push(body);
      return HttpResponse.json({
        data: {
          portfolio_id: "P001",
          cash_balance: 140000.0,
          total_equity: 1010000.0,
          has_pending_execution: false,
          actual_positions: [],
        },
        meta: { request_id: "REQ-REPORT" },
        error: null,
      });
    },
  ),
  http.get("/api/v1/portfolios/:portfolioId/rebalances", () => {
    return HttpResponse.json({
      data: [
        {
          rebalance_id: "REB-PREV-01",
          decision_at: "2026-03-15",
          primary_trigger: "PERIODIC",
          outcome: "RECOMMENDED",
          turnover: 0.04,
        },
      ],
      meta: { request_id: "REQ-HIST-REB" },
      error: null,
    });
  }),
  http.post(
    "/api/v1/portfolios/:portfolioId/rebalances/evaluate",
    async ({ request }) => {
      const body = await request.json();
      capturedEvaluations.push(body);
      return HttpResponse.json({
        data: rebalanceProposalData,
        meta: { request_id: "REQ-EVAL" },
        error: null,
      });
    },
  ),
);

const renderWithClient = (ui: React.ReactElement) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  capturedReports = [];
  capturedEvaluations = [];
});
afterAll(() => server.close());

describe("LivePortfolioPanel", () => {
  it("explains why live positions are unavailable without a verified source", async () => {
    renderWithClient(<LivePortfolioPanel portfolioId="P001" />);

    expect(await screen.findByLabelText("实盘持仓与三态监控")).toBeVisible();
    expect(screen.getByText("实盘数据源不可交付")).toBeVisible();
    expect(
      screen.getByRole("region", {
        name: "Target、Pending、Actual 持仓数据状态",
      }),
    ).toHaveTextContent("Target 目标仓位");
    expect(screen.getByText("无经核验的账户持仓来源")).toBeVisible();
  });

  it("keeps execution reports disabled until a durable ledger is available", async () => {
    renderWithClient(<LivePortfolioPanel portfolioId="P001" />);

    await screen.findByLabelText("实盘持仓与三态监控");

    expect(
      screen.getByRole("button", { name: "成交回报暂不可提交" }),
    ).toBeDisabled();
    expect(capturedReports).toHaveLength(0);
  });
});

describe("RebalancingPanel", () => {
  it("explains unavailable rebalancing inputs and does not create a proposal", async () => {
    renderWithClient(<RebalancingPanel portfolioId="P001" />);

    expect(await screen.findByLabelText("动态再平衡与调仓评估")).toBeVisible();
    expect(screen.getByText("再平衡服务未接入真实数据")).toBeVisible();
    expect(
      screen.getByText("持久化实际仓位、真实估值日期、已应用规则版本"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "发起再平衡评估" }),
    ).not.toBeInTheDocument();
    expect(capturedEvaluations).toHaveLength(0);
  });
});
