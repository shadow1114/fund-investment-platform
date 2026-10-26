import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { MemoryRouter, useRoutes } from "react-router-dom";

import { App } from "../app/App";
import { queryClient } from "../app/queryClient";
import { routes } from "../app/routes";
import { errorEnvelope, universeDetailEnvelope } from "./contractFixtures";
import { requestLog, resetRequestLog, server } from "./mswServer";

const newClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

const RouteHarness = () => useRoutes(routes);

const renderRoute = (initialEntry: string) => {
  const client = newClient();
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <RouteHarness />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, client };
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  queryClient.clear();
  server.resetHandlers();
  resetRequestLog();
  window.history.replaceState({}, "", "/");
});
afterAll(() => server.close());

describe("M1.7 accessibility and contract verification", () => {
  it("reaches every named primary navigation link with the keyboard", async () => {
    window.history.replaceState({}, "", "/funds");
    const user = userEvent.setup();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "基金研究" }),
    ).toBeVisible();
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.getByRole("form", { name: "基金筛选" })).toBeVisible();

    for (const name of ["基金研究", "分类复核", "候选池", "组合决策", "回测"]) {
      await user.tab();
      expect(screen.getByRole("link", { name })).toHaveFocus();
    }
  });

  const statuses = [
    [401, "AUTHENTICATION_REQUIRED"],
    [403, "FORBIDDEN"],
    [409, "VERSION_CONFLICT"],
    [422, "VALIDATION_ERROR"],
    [500, "INTERNAL_ERROR"],
  ] as const;
  const readEndpoints = [
    ["/funds", "/api/v1/funds"],
    ["/funds/000001", "/api/v1/funds/000001"],
    ["/universes", "/api/v1/fund-universes"],
    ["/universes/UNI-001", "/api/v1/fund-universes/UNI-001"],
    ["/portfolios", "/api/v1/portfolios"],
    ["/portfolios/P001", "/api/v1/portfolios/P001"],
    ["/portfolios/P001", "/api/v1/session"],
  ] as const;

  it.each(
    readEndpoints.flatMap(([path, endpoint]) =>
      statuses.map(([status, code]) => ({ path, endpoint, status, code })),
    ),
  )(
    "$path exposes HTTP $status from $endpoint with API code",
    async ({ path, endpoint, status, code }) => {
      server.use(
        http.get(endpoint, () =>
          HttpResponse.json(errorEnvelope(code), { status }),
        ),
      );
      renderRoute(path);
      expect(await screen.findByText(`HTTP ${status} · ${code}`)).toBeVisible();
      expect(screen.getByText(`Contract fixture for ${code}`)).toBeVisible();
    },
  );

  it.each([
    ["/api/v1/funds/000001/nav-series", "净值"],
    ["/api/v1/funds/000001/evaluations", "评估"],
    ["/api/v1/funds/000001/scores", "评分"],
  ] as const)(
    "fund detail exposes dependent %s errors",
    async (endpoint, tab) => {
      server.use(
        http.get(endpoint, () =>
          HttpResponse.json(errorEnvelope("DEPENDENT_DATA_FAILED"), {
            status: 422,
          }),
        ),
      );
      renderRoute("/funds/000001");
      await screen.findByRole("heading", { name: "Alpha 稳健基金" });
      fireEvent.click(screen.getByRole("tab", { name: tab }));
      expect(
        await screen.findByText("HTTP 422 · DEPENDENT_DATA_FAILED"),
      ).toBeVisible();
    },
  );

  it.each(statuses)(
    "backtest creation exposes HTTP %i and its API code",
    async (status, code) => {
      server.use(
        http.post("/api/v1/backtests", () =>
          HttpResponse.json(errorEnvelope(code), { status }),
        ),
      );
      renderRoute("/backtests");
      for (const [label, value] of [
        ["策略 ID", "STRATEGY-1"],
        ["开始日期", "2020-01-01"],
        ["结束日期", "2026-06-30"],
        ["基准 ID", "CSI300"],
        ["再平衡政策版本", "rebalance-v3"],
        ["组合规则版本", "portfolio-v4"],
        ["收益估计版本", "return-v5"],
        ["风险模型版本", "risk-v7"],
        ["资格规则版本", "eligibility-v4"],
        ["交易成本模型版本", "cost-v2"],
      ]) {
        fireEvent.change(screen.getByLabelText(label), {
          target: { value },
        });
      }
      fireEvent.click(screen.getByRole("button", { name: "创建回测" }));
      expect(await screen.findByText(`HTTP ${status} · ${code}`)).toBeVisible();
      expect(screen.getByRole("button", { name: "启动回测" })).toBeDisabled();
    },
  );

  it("keeps unknown enums, null reasons, and PIT provenance visible", async () => {
    server.use(
      http.get("/api/v1/fund-universes/:universeId", () =>
        HttpResponse.json({
          ...universeDetailEnvelope,
          data: {
            ...universeDetailEnvelope.data,
            universe_strategy: "FUTURE_STRATEGY",
          },
        }),
      ),
    );
    renderRoute("/universes/UNI-001");

    expect(await screen.findByText("UNKNOWN")).toBeVisible();
    expect(screen.getAllByText("不可用（ELIGIBILITY_ONLY）")).not.toHaveLength(
      0,
    );
    expect(screen.getByText("点时数据：是")).toBeVisible();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("keeps all page API traffic inside the frozen /api/v1 boundary", async () => {
    const visits = [
      ["/funds", "基金研究"],
      ["/funds/000001", "Alpha 稳健基金"],
      ["/universes", "候选池快照"],
      ["/universes/UNI-001", "候选池快照"],
      ["/portfolios", "组合决策"],
      ["/portfolios/P001", "稳健组合"],
      ["/backtests", "回测"],
    ] as const;

    for (const [path, heading] of visits) {
      const view = renderRoute(path);
      expect(
        await screen.findByRole("heading", { name: heading }),
      ).toBeVisible();
      view.unmount();
      view.client.clear();
    }

    expect(requestLog.length).toBeGreaterThanOrEqual(6);
    expect(
      requestLog.every((request) => request.pathname.startsWith("/api/v1/")),
    ).toBe(true);
  });
});
