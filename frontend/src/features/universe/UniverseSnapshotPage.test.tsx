import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { UniverseSnapshotPage } from "../../pages/UniverseSnapshotPage";
import { renderWithMantine as render } from "../../test/render";

const requests: URL[] = [];

const meta = {
  request_id: "REQ-UNIVERSE",
  as_of_date: "2026-09-16",
  data_version: "fund-data-v12",
  versions: {
    classification_version: "class-v3",
    factor_version: "factor-v8",
  },
  is_point_in_time: true,
  availability_quality_distribution: { EXACT: 1, DERIVED: 1, INFERRED: 0 },
  eligibility_rules_version: "eligibility-v4",
  scoring_policy_version: null,
};

const detailEnvelope = {
  data: {
    universe_id: "UNI-ELIGIBILITY-1",
    decision_at: "2026-09-16T08:30:00Z",
    universe_strategy: "A",
    members: [
      {
        fund_id: "000001",
        selection_status: "SELECTED",
        total_score: null,
        total_score_status: "UNAVAILABLE",
        total_score_reason: "ELIGIBILITY_ONLY",
        rank: null,
        rank_status: "UNAVAILABLE",
        rank_reason: "ELIGIBILITY_ONLY",
        percentile: null,
        percentile_status: "UNAVAILABLE",
        percentile_reason: "ELIGIBILITY_ONLY",
        fund_tier: null,
        investment_eligibility: "FULLY_ELIGIBLE",
        passed_conditions: [
          {
            condition: "minimum_track_record_years",
            actual: 5.2,
            result: "PASS",
            gap: 2.2,
          },
        ],
        failed_conditions: [],
      },
    ],
    excluded: [
      {
        fund_id: "000002",
        selection_status: "REJECTED",
        total_score: null,
        total_score_status: "EXCLUDED",
        total_score_reason: "FAILED_ELIGIBILITY",
        rank: null,
        rank_status: "EXCLUDED",
        rank_reason: "FAILED_ELIGIBILITY",
        percentile: null,
        percentile_status: "EXCLUDED",
        percentile_reason: "FAILED_ELIGIBILITY",
        fund_tier: null,
        investment_eligibility: "NOT_TRADABLE",
        passed_conditions: [],
        failed_conditions: [
          {
            condition: "minimum_aum",
            actual: 8000000,
            result: "FAIL",
            gap: -2000000,
          },
          {
            condition: "minimum_track_record_years",
            actual: 0.8,
            result: "FAIL",
            gap: -2.2,
          },
        ],
      },
    ],
  },
  meta,
  error: null,
};

const listEnvelope = {
  data: [
    {
      universe_id: "UNI-ELIGIBILITY-1",
      strategy_id: "low-volatility",
      decision_at: "2026-09-16T08:30:00Z",
      universe_strategy: "A",
      member_count: 1,
      eligibility_rules_version: "eligibility-v4",
      scoring_policy_version: null,
    },
  ],
  meta,
  error: null,
};

const server = setupServer(
  http.get("/api/v1/fund-universes", ({ request }) => {
    requests.push(new URL(request.url));
    return HttpResponse.json(listEnvelope);
  }),
  http.get("/api/v1/fund-universes/:universeId", () =>
    HttpResponse.json(detailEnvelope),
  ),
);

const renderPage = (initialEntry: string) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/universes" element={<UniverseSnapshotPage />} />
          <Route
            path="/universes/:universeId"
            element={<UniverseSnapshotPage />}
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
});
afterAll(() => server.close());

describe("UniverseSnapshotPage", () => {
  it("keeps selected and rejected members visible with null score reasons and every failed condition", async () => {
    const user = userEvent.setup();
    renderPage("/universes/UNI-ELIGIBILITY-1");

    expect(
      await screen.findByRole("heading", {
        name: "候选池快照 UNI-ELIGIBILITY-1",
      }),
    ).toBeVisible();
    expect(screen.getByRole("tab", { name: "已入选（1）" })).toBeVisible();
    expect(screen.getByText("000001")).toBeVisible();
    expect(screen.getByText("已入选")).toBeVisible();
    expect(screen.getAllByText("不可用（ELIGIBILITY_ONLY）")).toHaveLength(3);

    await user.click(screen.getByRole("tab", { name: "已排除（1）" }));
    expect(screen.getByText("000002")).toBeVisible();
    expect(screen.getByText("已排除")).toBeVisible();

    expect(screen.getAllByText("不可用（FAILED_ELIGIBILITY）")).toHaveLength(3);

    await user.click(
      screen.getByRole("button", { name: "展开 000002 的未通过条件" }),
    );
    expect(screen.getByText("minimum_aum")).toBeVisible();
    expect(screen.getByText("minimum_track_record_years")).toBeVisible();
    expect(screen.getByText("-2000000")).toBeVisible();
    expect(screen.getByText("-2.2")).toBeVisible();

    expect(screen.getByText("资格规则版本：eligibility-v4")).toBeVisible();
    expect(
      screen.getByText("评分策略版本：未使用（仅资格筛选）"),
    ).toBeVisible();
    expect(screen.getByText("点时数据：是")).toBeVisible();
    await user.click(screen.getByText("查看来源版本"));
    expect(screen.getByText("factor_version")).toBeVisible();
    expect(screen.getByText("factor-v8")).toBeVisible();
  });

  it("sends the frozen list filters and links to the returned snapshot", async () => {
    renderPage(
      "/universes?strategy_id=low-volatility&decision_at=2026-09-16&eligibility_rules_version=eligibility-v4",
    );

    expect(screen.getByRole("textbox", { name: "策略 ID" })).toHaveValue(
      "low-volatility",
    );
    expect(screen.getByLabelText("决策日期")).toHaveAttribute("type", "date");
    expect(screen.getByLabelText("决策日期")).toHaveValue("2026-09-16");
    expect(screen.getByRole("textbox", { name: "资格规则版本" })).toHaveValue(
      "eligibility-v4",
    );

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(Object.fromEntries(requests[0].searchParams)).toEqual({
      strategy_id: "low-volatility",
      decision_at: "2026-09-16",
      eligibility_rules_version: "eligibility-v4",
    });
    expect(
      await screen.findByRole("link", { name: "UNI-ELIGIBILITY-1" }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("/universes/UNI-ELIGIBILITY-1?return_to="),
    );
  });
});
