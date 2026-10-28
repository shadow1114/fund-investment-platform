import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { App } from "./App";
import { queryClient } from "./queryClient";
import {
  errorEnvelope,
  fundListEnvelope,
  portfolioListEnvelope,
  sessionEnvelope,
} from "../test/contractFixtures";
import { server, requestLog, resetRequestLog } from "../test/mswServer";
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  queryClient.clear();
  server.resetHandlers();
  resetRequestLog();
  window.history.replaceState({}, "", "/");
});
afterAll(() => server.close());
const visit = (path = "/") => {
  window.history.replaceState({}, "", path);
  render(<App />);
};
const privilegedSession = {
  ...sessionEnvelope,
  data: {
    ...sessionEnvelope.data,
    capabilities: {
      ...sessionEnvelope.data.capabilities,
      can_manage_data_ingestion: true,
      can_review_classifications: true,
    },
  },
};
describe("Customer workspace", () => {
  it.each(["/", "/home"])("opens the overview from %s", async (path) => {
    visit(path);
    expect(
      await screen.findByRole("heading", { name: "工作台" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/home");
    const nav = within(screen.getByRole("navigation", { name: "主导航" }));
    expect(nav.getByRole("link", { name: "工作台" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    for (const [name, href] of [
      ["基金研究", "/funds"],
      ["候选池", "/universes"],
      ["组合管理", "/portfolios"],
      ["策略回测", "/backtests"],
    ])
      expect(nav.getByRole("link", { name })).toHaveAttribute("href", href);
  });
  it("hides privileged navigation while identity loads", () => {
    server.use(
      http.get("/api/v1/session", async () => {
        await delay("infinite");
        return HttpResponse.json(privilegedSession);
      }),
    );
    visit();
    expect(screen.getByText("身份读取中")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "分类复核" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "数据抓取" }),
    ).not.toBeInTheDocument();
  });
  it("shows privileged menus only for explicit capabilities", async () => {
    server.use(
      http.get("/api/v1/session", () => HttpResponse.json(privilegedSession)),
    );
    visit();
    expect(
      await screen.findByRole("link", { name: "数据抓取" }),
    ).toHaveAttribute("href", "/data-ingestion");
    expect(screen.getByRole("link", { name: "分类复核" })).toHaveAttribute(
      "href",
      "/classification-reviews",
    );
  });
  it("keeps privileged menus hidden when identity fails", async () => {
    server.use(
      http.get("/api/v1/session", () =>
        HttpResponse.json(errorEnvelope("FORBIDDEN"), { status: 403 }),
      ),
    );
    visit();
    expect(await screen.findByText("身份不可用")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "分类复核" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "数据抓取" }),
    ).not.toBeInTheDocument();
  });
  it("uses API totals rather than page length", async () => {
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json({
          ...fundListEnvelope,
          meta: {
            ...fundListEnvelope.meta,
            pagination: {
              ...fundListEnvelope.meta.pagination,
              total_items: 127,
            },
          },
        }),
      ),
      http.get("/api/v1/portfolios", () =>
        HttpResponse.json({
          ...portfolioListEnvelope,
          meta: {
            ...portfolioListEnvelope.meta,
            pagination: {
              ...portfolioListEnvelope.meta.pagination,
              total_items: 23,
            },
          },
        }),
      ),
    );
    visit();
    expect(await screen.findByText("127")).toBeVisible();
    expect(await screen.findByText("23")).toBeVisible();
    expect(screen.queryByText("正在运行的抓取作业")).not.toBeInTheDocument();
  });
  it("shows retryable overview errors", async () => {
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json(errorEnvelope("FORBIDDEN"), { status: 403 }),
      ),
    );
    visit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Contract fixture for FORBIDDEN",
    );
    expect(screen.getByRole("button", { name: "重新读取" })).toBeVisible();
  });
  it("searches funds and submits encoded fund_name", async () => {
    visit();
    fireEvent.change(screen.getByRole("combobox", { name: "基金快速定位" }), {
      target: { value: "华夏" },
    });
    expect(
      await screen.findByRole("option", {
        name: "Alpha 稳健基金",
        hidden: true,
      }),
    ).toBeInTheDocument();
    expect(
      requestLog.some(
        (url) =>
          url.pathname === "/api/v1/funds" &&
          url.searchParams.get("fund_name") === "华夏",
      ),
    ).toBe(true);
    fireEvent.submit(screen.getByRole("form", { name: "基金快速定位" }));
    expect(window.location.pathname + window.location.search).toBe(
      "/funds?fund_name=%E5%8D%8E%E5%A4%8F",
    );
  });
  it("toggles navigation and closes the drawer after navigation", () => {
    visit();
    fireEvent.click(
      screen.getByRole("button", { name: "打开导航", hidden: true }),
    );
    expect(
      screen.getByRole("button", { name: "关闭导航", hidden: true }),
    ).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(
      within(screen.getByRole("navigation", { name: "主导航" })).getByRole(
        "link",
        { name: "基金研究" },
      ),
    );
    expect(
      screen.getByRole("button", { name: "打开导航", hidden: true }),
    ).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(
      screen.getByRole("button", { name: "折叠侧栏", hidden: true }),
    );
    expect(
      screen.getByRole("button", { name: "展开侧栏", hidden: true }),
    ).toBeInTheDocument();
  });
  it("offers a workspace return from 404", async () => {
    visit("/missing");
    expect(
      await screen.findByRole("heading", { name: "页面不存在" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "返回工作台" })).toHaveAttribute(
      "href",
      "/home",
    );
  });
});
