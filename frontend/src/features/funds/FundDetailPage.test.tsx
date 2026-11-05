import {
  classificationCatalog,
  emptyClassificationHistory,
} from "../../test/classificationFixtures";
import {
  fundDetailEnvelope,
  fundNavEnvelope,
  fundEvaluationEnvelope,
  fundScoreEnvelope,
  fundBasicInfoHistoryEnvelope,
  fundIngestionListEnvelope,
  sessionEnvelope,
} from "../../test/contractFixtures";
import { MantineProvider } from "@mantine/core";
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

import { FundDetailPage } from "../../pages/FundDetailPage";
import { prototypeFactorText } from "./FactorAnalysisPanel";

const chartOptions: { series: { data: unknown[] }[] }[] = [];

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: { series: { data: unknown[] }[] } }) => {
    chartOptions.push(option);
    return (
      <div aria-label="基金净值图">
        图表数据点：{option.series[0].data.length}
      </div>
    );
  },
}));

const baseMeta = {
  request_id: "REQ-DETAIL",
  versions: { data_version: "nav-v4" },
  is_point_in_time: true,
  availability_quality_distribution: { EXACT: 1, DERIVED: 0, INFERRED: 1 },
};
const factorPeriodsRequested: string[] = [];

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
        evaluation_status: "LEGACY_UNKNOWN",
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
  http.get("/api/v1/funds/000001/factor-analysis", ({ request }) => {
    const period =
      new URL(request.url).searchParams.get("evaluation_period") ?? "1Y";
    factorPeriodsRequested.push(period);
    return HttpResponse.json({
      data: {
        fund_id: "000001",
        evaluation_period: period,
        as_of_date: "2026-09-16",
        factor_categories: [
          {
            category: "RET",
            name: "收益表现",
            factors: [
              {
                factor_id: "F-RET-001",
                name: "年化收益率",
                category: "RET",
                direction: "HIGHER_IS_BETTER",
                raw_value: 0.1,
                normalized_value: null,
                status: "VALID",
                reason_code: null,
                observations: 250,
                series: [],
              },
            ],
          },
        ],
      },
      meta: {
        ...baseMeta,
        calculation_mode: "ON_DEMAND",
        factor_count: 26,
      },
      error: null,
    });
  }),
);

const renderPage = (entry = "/funds/000001?as_of_date=2026-09-16") => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <MantineProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path="/funds/:fundId" element={<FundDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
};

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  factorPeriodsRequested.length = 0;
  chartOptions.length = 0;
});
afterAll(() => {
  server.close();
});

describe("FundDetailPage", () => {
  it("formats prototype loss values without changing the API result", () => {
    const analysis = {
      fund_id: "000001",
      evaluation_period: "1Y" as const,
      as_of_date: "2026-09-16",
      factor_categories: [
        {
          category: "RISK" as const,
          name: "风险",
          factors: [
            {
              factor_id: "F-RISK-004",
              name: "VaR",
              category: "RISK" as const,
              direction: "LOWER_IS_BETTER",
              raw_value: 0.02,
              normalized_value: null,
              status: "VALID" as const,
              reason_code: null,
              observations: 252,
              series: [],
            },
          ],
        },
      ],
    };
    expect(prototypeFactorText(analysis, "F-RISK-004")).toBe("-2.00%");
    expect(analysis.factor_categories[0].factors[0].raw_value).toBe(0.02);
  });
  it("uses the exact share class for prototype reads and never requests history or scores", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("/api/v1/funds/:id", ({ request, params }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json({
          ...fundDetailEnvelope,
          data: {
            ...fundDetailEnvelope.data,
            share_class: params.id === "102" ? "C" : "A",
          },
        });
      }),
      ...[
        ["nav-series", fundNavEnvelope],
        ["evaluations", fundEvaluationEnvelope],
        ["scores", fundScoreEnvelope],
      ].map(([suffix, envelope]) =>
        http.get(`/api/v1/funds/:id/${suffix}`, ({ request }) => {
          requests.push(new URL(request.url));
          return HttpResponse.json(envelope);
        }),
      ),
      http.get("/api/v1/funds/:id/factor-analysis", ({ request }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json({
          data: {
            fund_id: "000001",
            evaluation_period: "5Y",
            as_of_date: "2026-09-16",
            factor_categories: [],
          },
          meta: baseMeta,
          error: null,
        });
      }),
      ...["basic-info-history", "ingestions", "classification-history"].map(
        (suffix) =>
          http.get(`/api/v1/funds/:id/${suffix}`, ({ request }) => {
            requests.push(new URL(request.url));
            return HttpResponse.json(
              suffix === "basic-info-history"
                ? fundBasicInfoHistoryEnvelope
                : suffix === "ingestions"
                  ? fundIngestionListEnvelope
                  : emptyClassificationHistory,
            );
          }),
      ),
    );
    renderPage(
      "/funds/000001?share_class_id=102&as_of_date=2026-09-16&tab=rolling&factor_period=5Y&return_to=%2Ffunds%3Fpage%3D3",
    );
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });
    await screen.findByRole("tabpanel", {
      name: "滚动指标演变 (Sharpe/波动率)",
    });
    for (const suffix of ["", "/nav-series", "/factor-analysis"]) {
      const request = requests.find(
        (url) => url.pathname === `/api/v1/funds/102${suffix}`,
      );
      expect(request, suffix || "detail").toBeDefined();
      expect(request?.searchParams.get("as_of_date")).toBe("2026-09-16");
    }
    expect(
      requests
        .find((url) => url.pathname.endsWith("/factor-analysis"))
        ?.searchParams.get("evaluation_period"),
    ).toBe("5Y");
    for (const suffix of [
      "basic-info-history",
      "ingestions",
      "classification-history",
    ]) {
      expect(requests.some((url) => url.pathname.endsWith(`/${suffix}`))).toBe(
        false,
      );
    }
    expect(
      requests.some((url) => /\/(evaluations|scores)$/.test(url.pathname)),
    ).toBe(false);
    expect(
      screen.queryByRole("link", { name: "返回基金研究" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    "https://evil.test/funds",
    "//evil.test/funds",
    "/portfolios",
    "/funds/../portfolios",
  ])(
    "rejects unsafe return_to %s on a legacy detail route",
    async (candidate) => {
      renderPage(
        `/funds/000001?as_of_date=2026-09-16&return_to=${encodeURIComponent(candidate)}`,
      );
      await screen.findByRole("heading", { name: "Alpha 稳健基金" });
      expect(
        screen.queryByRole("link", { name: "返回基金研究" }),
      ).not.toBeInTheDocument();
    },
  );

  it("never adds classification, ingestion or provenance sections to the prototype", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });
    expect(screen.queryByText("五维分类与证据")).not.toBeInTheDocument();
    expect(screen.queryByText("评分归因")).not.toBeInTheDocument();
    expect(screen.queryByText("点时数据：是")).not.toBeInTheDocument();
    expect(screen.queryByText("查看图表数值")).not.toBeInTheDocument();
    expect(screen.queryByText("打开分类复核工作区")).not.toBeInTheDocument();
  });
  it("shows categorized factors below the trend and recalculates after period selection", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });
    expect(
      await screen.findByRole("heading", { name: "收益指标 (4)" }),
    ).toBeVisible();
    expect(
      (await screen.findAllByText("+10.00%", { exact: true })).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", { name: /量化多因子多维矩阵/ }),
    ).toBeVisible();
    expect(factorPeriodsRequested).toContain("1Y");
    await user.click(screen.getByRole("radio", { name: "5年" }));
    await waitFor(() => expect(factorPeriodsRequested).toContain("5Y"));
  });
  it("keeps missing NAV observations as gaps without adding a value table", async () => {
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Alpha 稳健基金" }),
    ).toBeVisible();
    const nav = await screen.findByRole("tabpanel", {
      name: "净值走势 vs 基准超额",
    });
    expect(await within(nav).findByText("图表数据点：2")).toBeVisible();
    expect(chartOptions.at(-1)?.series[0].data).toEqual([
      ["2026-09-15", 0],
      ["2026-09-16", null],
    ]);
    expect(within(nav).queryByText("查看图表数值")).not.toBeInTheDocument();
  });

  it("keeps the NAV view while changing period and renders the seven-column panorama automatically", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "收益指标 (4)" });
    await user.click(screen.getByRole("radio", { name: "5年" }));
    await waitFor(() => expect(factorPeriodsRequested).toContain("5Y"));
    expect(
      screen.getByRole("tab", { name: "净值走势 vs 基准超额" }),
    ).toHaveAttribute("aria-selected", "true");
    await waitFor(() =>
      expect(new Set(factorPeriodsRequested)).toEqual(
        new Set(["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"]),
      ),
    );
    const table = screen.getByRole("region", { name: "多周期数值" });
    await waitFor(() =>
      expect(within(table).queryByText("计算中")).not.toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(within(table).getAllByText("+10.00%")).toHaveLength(7),
    );
    expect(within(table).queryByText("未加载")).not.toBeInTheDocument();
    expect(
      within(table).getByRole("columnheader", { name: "3个月" }),
    ).toBeVisible();
    expect(
      within(table).getByRole("columnheader", { name: "成立以来" }),
    ).toBeVisible();
  });

  it("shows failed panorama periods without fabricating zero", async () => {
    server.use(
      http.get("/api/v1/funds/000001/factor-analysis", ({ request }) => {
        const period = new URL(request.url).searchParams.get(
          "evaluation_period",
        );
        if (period !== "5Y") return;
        return HttpResponse.json(
          {
            data: null,
            meta: baseMeta,
            error: {
              code: "CALCULATION_FAILED",
              message: "Calculation failed",
              details: {},
            },
          },
          { status: 500 },
        );
      }),
    );
    renderPage();
    const table = await screen.findByRole("region", { name: "多周期数值" });
    await waitFor(() =>
      expect(within(table).getAllByText("+10.00%")).toHaveLength(6),
    );
    expect(within(table).queryByText("0.00%")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "重试失败周期" }),
    ).not.toBeInTheDocument();
  });

  it("draws underwater values against the period peak and preserves missing observations", async () => {
    server.use(
      http.get("/api/v1/funds/000001/nav-series", () =>
        HttpResponse.json({
          ...fundNavEnvelope,
          data: {
            ...fundNavEnvelope.data,
            points: [
              {
                date: "2026-09-13",
                nav: 4,
                nav_status: "VALID",
                nav_reason: null,
              },
              {
                date: "2026-09-14",
                nav: 3,
                nav_status: "VALID",
                nav_reason: null,
              },
              {
                date: "2026-09-15",
                nav: null,
                nav_status: "UNAVAILABLE",
                nav_reason: "MISSING_NAV",
              },
              {
                date: "2026-09-16",
                nav: 5,
                nav_status: "VALID",
                nav_reason: null,
              },
            ],
          },
        }),
      ),
    );
    renderPage();
    await screen.findByText("图表数据点：4");
    await userEvent
      .setup()
      .click(screen.getByRole("tab", { name: "动态回撤 (Underwater)" }));
    await waitFor(() =>
      expect(chartOptions.at(-1)?.series[0].data).toEqual([
        ["2026-09-13", 0],
        ["2026-09-14", -25],
        ["2026-09-15", null],
        ["2026-09-16", 0],
      ]),
    );
  });

  it("supports roving-tab keyboard navigation", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });
    const nav = screen.getByRole("tab", { name: "净值走势 vs 基准超额" });
    const evaluation = screen.getByRole("tab", {
      name: "动态回撤 (Underwater)",
    });
    const factorTab = screen.getByRole("tab", {
      name: "滚动指标演变 (Sharpe/波动率)",
    });
    expect(nav).toHaveAttribute("tabindex", "0");
    expect(evaluation).toHaveAttribute("tabindex", "-1");
    nav.focus();
    await user.keyboard("{ArrowRight}");
    expect(evaluation).toHaveFocus();
    expect(evaluation).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(factorTab).toHaveFocus();
    await user.keyboard("{Home}");
    expect(nav).toHaveFocus();
  });

  it("offers all seven prototype periods and requests since-inception factors", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Alpha 稳健基金" });

    expect(screen.getAllByRole("radio")).toHaveLength(7);
    await user.click(screen.getByRole("radio", { name: "成立以来" }));
    await waitFor(() => expect(factorPeriodsRequested).toContain("ALL"));
    expect(
      screen.getByRole("heading", { name: /当前周期:.*成立以来/ }),
    ).toBeVisible();
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
    expect(
      await screen.findByText("请求失败 · 404 FUND_NOT_FOUND"),
    ).toBeVisible();
  });
});
