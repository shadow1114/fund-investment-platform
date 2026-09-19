import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes, useRoutes } from "react-router-dom";

import { App } from "../app/App";
import { queryClient } from "../app/queryClient";
import { routes } from "../app/routes";
import { FundResearchPage } from "../pages/FundResearchPage";
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

    for (const name of ["基金研究", "候选池", "组合决策", "回测"]) {
      await user.tab();
      expect(screen.getByRole("link", { name })).toHaveFocus();
    }
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED"],
    [403, "FORBIDDEN"],
    [409, "VERSION_CONFLICT"],
    [422, "VALIDATION_ERROR"],
    [500, "INTERNAL_ERROR"],
  ])("renders HTTP %i and its API error code", async (status, code) => {
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json(errorEnvelope(code), { status }),
      ),
    );
    const client = newClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/funds"]}>
          <Routes>
            <Route path="/funds" element={<FundResearchPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText(`HTTP ${status} · ${code}`)).toBeVisible();
  });

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
      ["/universes/UNI-001", "候选池快照"],
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

    expect(requestLog.length).toBeGreaterThanOrEqual(4);
    expect(
      requestLog.every((request) => request.pathname.startsWith("/api/v1/")),
    ).toBe(true);
  });
});
