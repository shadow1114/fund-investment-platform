import { expect, test, type Page } from "@playwright/test";

import {
  fundListEnvelope,
  portfolioEnvelope,
  sessionEnvelope,
  universeDetailEnvelope,
} from "../src/test/contractFixtures";

const apiFixtures: Record<string, unknown> = {
  "/api/v1/funds": fundListEnvelope,
  "/api/v1/fund-universes/UNI-001": universeDetailEnvelope,
  "/api/v1/portfolios/P001": portfolioEnvelope,
  "/api/v1/session": sessionEnvelope,
};

async function installFrozenApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const fixture = apiFixtures[url.pathname];
    if (fixture === undefined) {
      throw new Error(`Unexpected API request: ${url.pathname}`);
    }
    await route.fulfill({ json: fixture });
  });
}

test.beforeEach(async ({ page }) => {
  await installFrozenApi(page);
});

for (const [path, heading] of [
  ["/funds", "基金研究"],
  ["/universes/UNI-001", "候选池快照"],
  ["/portfolios/P001", "稳健组合"],
  ["/backtests", "回测"],
] as const) {
  test(`${path} renders its accessible page heading`, async ({ page }) => {
    const dataRequests: string[] = [];
    page.on("request", (request) => {
      if (["fetch", "xhr"].includes(request.resourceType())) {
        dataRequests.push(new URL(request.url()).pathname);
      }
    });
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "主导航" }),
    ).toBeVisible();
    if (path === "/funds") {
      await expect(
        page.getByRole("link", { name: "Alpha 稳健基金" }),
      ).toBeVisible();
      await expect(page.getByText("点时数据：是")).toBeVisible();
    } else if (path === "/universes/UNI-001") {
      await expect(
        page.getByRole("heading", { name: "已排除（1）" }),
      ).toBeVisible();
      await expect(page.getByText("REJECTED")).toBeVisible();
    } else if (path === "/portfolios/P001") {
      await expect(page.getByText("当前会话无决策复核权限。")).toBeVisible();
      await expect(page.getByRole("button", { name: "批准" })).toHaveCount(0);
    } else {
      await expect(page.getByRole("form", { name: "回测配置" })).toBeVisible();
      await expect(
        page.getByRole("button", { name: "启动回测" }),
      ).toBeDisabled();
    }
    if (path !== "/backtests") {
      expect(dataRequests.length).toBeGreaterThan(0);
    }
    expect(
      dataRequests.every((request) => request.startsWith("/api/v1/")),
    ).toBe(true);
  });
}
