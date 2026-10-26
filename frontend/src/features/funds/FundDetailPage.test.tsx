import {
  classificationCatalog,
  emptyClassificationHistory,
} from "../../test/classificationFixtures";
import {
  fundBasicInfoHistoryEnvelope,
  fundIngestionListEnvelope,
  sessionEnvelope,
} from "../../test/contractFixtures";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
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

import { FundDetailPage } from "../../pages/FundDetailPage";

vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: { series: { data: unknown[] }[] } }) => (
    <div aria-label="基金净值图">
      图表数据点：{option.series[0].data.length}
    </div>
  ),
}));

const baseMeta = {
  request_id: "REQ-DETAIL",
  versions: { data_version: "nav-v4" },
  is_point_in_time: true,
  availability_quality_distribution: { EXACT: 1, DERIVED: 0, INFERRED: 1 },
};

const server = setupServer(
  http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
  http.get("/api/v1/funds/:fundId/ingestions", () =>
    HttpResponse.json(fundIngestionListEnvelope),
  ),
  http.get("/api/v1/funds/:fundId/basic-info-history", () =>
    HttpResponse.json(fundBasicInfoHistoryEnvelope),
  ),
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json(classificationCatalog),
  ),
  http.get("/api/v1/funds/:fundId/classification-history", () =>
    HttpResponse.json(emptyClassificationHistory),
  ),
  http.get("/api/v1/funds/000001", () =>
    HttpResponse.json({
      data: {
        fund_id: "000001",
        fund_name: "Alpha 稳健基金",
        share_class: "A",
        fund_classification: "EQUITY",
        management_company_id: "MC-1",
        inception_date: "2020-01-02",
        lifecycle_status: "NORMAL",
        investment_eligibility: "FULLY_ELIGIBLE",
        classification_version: "class-v3",
        manager_ids: ["M-1"],
        benchmark: {
          benchmark_id: "CSI300",
          benchmark_name: "沪深300",
          benchmark_type: "INDEX",
          mapping_version: "map-v2",
          components: null,
        },
        fee_structure: [],
      },
      meta: baseMeta,
      error: null,
    }),
  ),
  http.get("/api/v1/funds/000001/nav-series", () =>
    HttpResponse.json({
      data: {
        fund_id: "000001",
        points: [
          {
            date: "2026-09-15",
            nav: 1.24,
            nav_status: "VALID",
            nav_reason: null,
          },
          {
            date: "2026-09-16",
            nav: null,
            nav_status: "UNAVAILABLE",
            nav_reason: "INSUFFICIENT_SAMPLE",
            reason_code: "INSUFFICIENT_SAMPLE",
          },
        ],
      },
      meta: {
        ...baseMeta,
        nav_type: "ADJUSTED",
        adjustment_convention: "BACKWARD",
        adjustment_rule_version: "adj-v2",
        unavailable_count: 1,
      },
      error: null,
    }),
  ),
  http.get("/api/v1/funds/000001/evaluations", () =>
    HttpResponse.json({
      data: {
        fund_id: "000001",
        evaluation_period: "1Y",
        as_of_date: "2026-09-16",
        evaluation_status: "WARNING",
        evaluation_profile: "research-v1",
        data_completeness: { available: 250, expected: 252 },
        factor_results: [
          {
            factor_id: "downside_risk",
            window: "1Y",
            raw_value: null,
            normalized_value: null,
            status: "UNAVAILABLE",
            reason_code: "INSUFFICIENT_SAMPLE",
            direction: "LOWER_IS_BETTER",
          },
        ],
      },
      meta: {
        ...baseMeta,
        peer_group_id: "PG-1",
        peer_group_version: "pg-v3",
        evaluation_policy_version: "eval-v4",
        factor_version: "factor-v5",
        data_version: "eval-data-v8",
      },
      error: null,
    }),
  ),
  http.get("/api/v1/funds/000001/scores", () =>
    HttpResponse.json({
      data: {
        fund_id: "000001",
        evaluation_period: "1Y",
        as_of_date: "2026-09-16",
        total_score: null,
        total_score_status: "UNAVAILABLE",
        total_score_reason: "INSUFFICIENT_SAMPLE",
        sub_scores: {
          return_score: null,
          return_score_status: "UNAVAILABLE",
          return_score_reason: "INSUFFICIENT_SAMPLE",
          risk_score: 71.2,
          risk_score_status: "VALID",
          risk_score_reason: null,
          risk_adjusted_score: null,
          risk_adjusted_score_status: "UNAVAILABLE",
          risk_adjusted_score_reason: "INSUFFICIENT_SAMPLE",
          stability_score: 68,
          stability_score_status: "VALID",
          stability_score_reason: null,
          relative_performance_score: 63,
          relative_performance_score_status: "VALID",
          relative_performance_score_reason: null,
        },
        attribution: [
          {
            factor_id: "downside_risk",
            raw_value: null,
            normalized_value: null,
            direction: "LOWER_IS_BETTER",
            status: "EXCLUDED",
            reason_code: "INSUFFICIENT_SAMPLE",
            weight: 0.25,
          },
        ],
        data_completeness: { available: 3, expected: 5 },
        score_status: "PARTIAL",
      },
      meta: {
        ...baseMeta,
        peer_group_id: "PG-1",
        peer_group_version: "pg-v3",
        scoring_policy_version: "score-v7",
        evaluation_policy_version: "eval-v4",
        factor_version: "factor-v5",
        data_version: "score-data-v8",
      },
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
      <MemoryRouter initialEntries={["/funds/000001?as_of_date=2026-09-16"]}>
        <Routes>
          <Route path="/funds/:fundId" element={<FundDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

describe("FundDetailPage", () => {
  it("shows NAV null semantics and PIT provenance without inventing zero", async () => {
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Alpha 稳健基金" }),
    ).toBeVisible();

    const nav = await screen.findByRole("tabpanel", { name: "净值" });
    expect(within(nav).getByText("图表数据点：1")).toBeVisible();
    expect(
      within(nav).getByText("不可用（INSUFFICIENT_SAMPLE）"),
    ).toBeVisible();
    expect(within(nav).queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("点时数据：是")).toBeVisible();
  });

  it("normalizes an unknown evaluation status and keeps insufficient-sample reasons", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });

    await user.click(screen.getByRole("tab", { name: "评估" }));
    const evaluation = screen.getByRole("tabpanel", { name: "评估" });
    expect(within(evaluation).getByText("评估状态：UNKNOWN")).toBeVisible();
    expect(
      within(evaluation).getByText("不可用（INSUFFICIENT_SAMPLE）"),
    ).toBeVisible();
    expect(within(evaluation).getByText("eval-v4")).toBeVisible();
  });

  it("supports roving-tab keyboard navigation", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });
    const nav = screen.getByRole("tab", { name: "净值" });
    const evaluation = screen.getByRole("tab", { name: "评估" });
    const score = screen.getByRole("tab", { name: "评分" });
    expect(nav).toHaveAttribute("tabindex", "0");
    expect(evaluation).toHaveAttribute("tabindex", "-1");
    nav.focus();
    await user.keyboard("{ArrowRight}");
    expect(evaluation).toHaveFocus();
    expect(evaluation).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(score).toHaveFocus();
    await user.keyboard("{Home}");
    expect(nav).toHaveFocus();
  });

  it("renders dimensionless score values and the attribution chain", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });

    await user.click(screen.getByRole("tab", { name: "评分" }));
    const score = screen.getByRole("tabpanel", { name: "评分" });
    expect(within(score).getByText("总分（无量纲）")).toBeVisible();
    expect(
      within(score).getAllByText("不可用（INSUFFICIENT_SAMPLE）").length,
    ).toBeGreaterThan(0);
    expect(within(score).getByText("downside_risk")).toBeVisible();
    expect(within(score).getByText("25.00%")).toBeVisible();
    expect(within(score).queryByText("0%")).not.toBeInTheDocument();
  });

  it("shows a stable API error state when detail loading fails", async () => {
    server.use(
      http.get("/api/v1/funds/000001", () =>
        HttpResponse.json(
          {
            data: null,
            meta: {},
            error: {
              code: "FUND_NOT_FOUND",
              message: "Fund not found",
              details: {},
            },
          },
          { status: 404 },
        ),
      ),
    );
    renderPage();
    expect(await screen.findByText("HTTP 404 · FUND_NOT_FOUND")).toBeVisible();
  });
});
