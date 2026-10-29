import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { App } from "../app/App";
import { queryClient } from "../app/queryClient";
import { errorEnvelope, universeDetailEnvelope } from "./contractFixtures";
import { requestLog, resetRequestLog, server } from "./mswServer";

const renderRoute = (initialEntry: string) => {
  window.history.replaceState({}, "", initialEntry);
  const view = render(<App />);
  return { ...view, client: queryClient };
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
    window.history.replaceState({}, "", "/home");
    const user = userEvent.setup();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "工作台" }),
    ).toBeVisible();
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.getByRole("form", { name: "基金快速定位" })).toBeVisible();

    const links = ["工作台", "基金研究", "候选池", "组合管理", "策略回测"].map(
      (name) =>
        within(screen.getByRole("navigation", { name: "主导航" })).getByRole(
          "link",
          { name },
        ),
    );
    for (
      let step = 0;
      step < 20 && !links.includes(document.activeElement as HTMLAnchorElement);
      step += 1
    ) {
      await user.tab();
    }
    expect(links[0]).toHaveFocus();
    for (const link of links.slice(1)) {
      await user.tab();
      expect(link).toHaveFocus();
    }
    expect(
      screen.queryByRole("link", { name: "分类复核" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "数据抓取" }),
    ).not.toBeInTheDocument();
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
      expect(
        await screen.findByText(`请求失败 · ${status} ${code}`),
      ).toBeVisible();
      expect(screen.getByText(`Contract fixture for ${code}`)).toBeVisible();
    },
  );

  it.each([
    ["/api/v1/funds/000001/nav-series", "净值"],
    ["/api/v1/funds/000001/evaluations", "业绩风险"],
    ["/api/v1/funds/000001/scores", "评分归因"],
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
        await screen.findByText("请求失败 · 422 DEPENDENT_DATA_FAILED"),
      ).toBeVisible();
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
      ["/backtests", "回测分析"],
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
