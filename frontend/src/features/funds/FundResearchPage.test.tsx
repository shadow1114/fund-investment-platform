import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { FundResearchPage } from "../../pages/FundResearchPage";

const requests: URL[] = [];

const listEnvelope = {
  data: [
    {
      fund_id: "000001",
      fund_name: "Alpha 稳健基金",
      share_class: "A",
      fund_classification: "EQUITY",
      management_company_id: "MC-1",
      inception_date: "2020-01-02",
      lifecycle_status: "NORMAL",
      investment_eligibility: "FULLY_ELIGIBLE",
    },
  ],
  meta: {
    request_id: "REQ-LIST",
    as_of_date: "2026-09-16",
    data_version: "funds-v7",
    versions: { classification_version: "class-v3" },
    is_point_in_time: true,
    pagination: {
      page: 2,
      page_size: 10,
      total_items: 21,
      total_pages: 3,
    },
    availability_quality_distribution: { EXACT: 18, DERIVED: 2, INFERRED: 1 },
  },
  error: null,
};

const server = setupServer(
  http.get("/api/v1/funds", ({ request }) => {
    requests.push(new URL(request.url));
    return HttpResponse.json(listEnvelope);
  }),
);

const renderPage = (initialEntry: string) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/funds" element={<FundResearchPage />} />
          <Route path="/funds/:fundId" element={<div>基金详情路由</div>} />
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

describe("FundResearchPage", () => {
  it("passes frozen filters through unchanged and renders PIT provenance", async () => {
    renderPage(
      "/funds?fund_name=Alpha&fund_type=EQUITY%2CBOND&lifecycle_status=NORMAL&investment_eligibility=FULLY_ELIGIBLE&as_of_date=2026-09-16&page=2&page_size=10&sort=fund_name&order=asc",
    );

    expect(await screen.findByText("Alpha 稳健基金")).toBeVisible();
    await waitFor(() => expect(requests).toHaveLength(1));
    const query = requests[0].searchParams;
    expect(Object.fromEntries(query)).toEqual({
      fund_name: "Alpha",
      fund_type: "EQUITY,BOND",
      lifecycle_status: "NORMAL",
      investment_eligibility: "FULLY_ELIGIBLE",
      as_of_date: "2026-09-16",
      page: "2",
      page_size: "10",
      sort: "fund_name",
      order: "asc",
    });
    expect(screen.getByText("点时数据：是")).toBeVisible();
    expect(screen.getByText("classification_version: class-v3")).toBeVisible();
    expect(screen.getByText("精确 18")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Alpha 稳健基金" }),
    ).toHaveAttribute("href", "/funds/000001?as_of_date=2026-09-16");
  });

  it("uses server pagination metadata and preserves filters on the next page", async () => {
    const user = userEvent.setup();
    renderPage("/funds?fund_name=Alpha&page=2&page_size=10");

    expect(await screen.findByText("第 2 / 3 页，共 21 只基金")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].searchParams.get("page")).toBe("3");
    expect(requests[1].searchParams.get("fund_name")).toBe("Alpha");
  });

  it("submits combined lifecycle and eligibility filters as comma-separated values", async () => {
    const user = userEvent.setup();
    renderPage("/funds");

    expect(await screen.findByText("Alpha 稳健基金")).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: "生命周期状态（逗号分隔）" }),
      "NORMAL,LIQUIDATED",
    );
    await user.type(
      screen.getByRole("textbox", { name: "投资资格（逗号分隔）" }),
      "FULLY_ELIGIBLE,HOLD_ONLY",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].searchParams.get("lifecycle_status")).toBe(
      "NORMAL,LIQUIDATED",
    );
    expect(requests[1].searchParams.get("investment_eligibility")).toBe(
      "FULLY_ELIGIBLE,HOLD_ONLY",
    );
  });

  it("renders empty and API error states explicitly", async () => {
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json({
          data: [],
          meta: {
            ...listEnvelope.meta,
            pagination: {
              page: 1,
              page_size: 20,
              total_items: 0,
              total_pages: 0,
            },
          },
          error: null,
        }),
      ),
    );
    const first = renderPage("/funds");
    expect(await screen.findByText("没有符合条件的基金")).toBeVisible();
    first.unmount();

    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json(
          {
            data: null,
            meta: {},
            error: {
              code: "FUNDS_UNAVAILABLE",
              message: "Fund service unavailable",
              details: {},
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderPage("/funds");
    expect(
      await screen.findByText("HTTP 503 · FUNDS_UNAVAILABLE"),
    ).toBeVisible();
  });
});
