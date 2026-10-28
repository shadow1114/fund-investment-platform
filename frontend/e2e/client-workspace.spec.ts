import { expect, test, type Page, type Route } from "@playwright/test";
import {
  fundListEnvelope,
  portfolioListEnvelope,
  responseMeta,
  sessionEnvelope,
  errorEnvelope,
} from "../src/test/contractFixtures";

const privilegedSession = {
  ...sessionEnvelope,
  data: {
    ...sessionEnvelope.data,
    capabilities: {
      ...sessionEnvelope.data.capabilities,
      can_manage_data_ingestion: true,
      can_manage_full_universe_ingestion: true,
    },
  },
};

const emptyHistory = {
  data: { items: [], page: 1, page_size: 1, total: 0 },
  meta: responseMeta,
  error: null,
};

async function installWorkspaceFixtures(page: Page) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/session") {
      await route.fulfill({ json: privilegedSession });
    } else if (url.pathname === "/api/v1/funds") {
      await route.fulfill({ json: fundListEnvelope });
    } else if (url.pathname === "/api/v1/portfolios") {
      await route.fulfill({ json: portfolioListEnvelope });
    } else if (url.pathname === "/api/v1/fund-ingestions") {
      await route.fulfill({ json: emptyHistory });
    } else if (url.pathname === "/api/v1/ingestions/OP-RECOVER") {
      await route.fulfill({
        json: {
          data: {
            operation_id: "OP-RECOVER",
            fund_id: "000001",
            fund_ids: ["000001"],
            dataset: "BASIC_INFO",
            source: "akshare",
            actor: "USR-001",
            status: "COMPLETED",
            task_status: "SUCCESS",
            requested_count: 1,
            success_count: 1,
            failure_count: 0,
            skipped_count: 0,
            cancelled_count: 0,
            scope_type: "SINGLE",
            created_at: "2026-10-28T08:00:00Z",
            started_at: "2026-10-28T08:00:01Z",
            finished_at: "2026-10-28T08:00:02Z",
            items: [],
            failure: null,
          },
          meta: responseMeta,
          error: null,
        },
      });
    } else if (url.pathname === "/api/v1/ingestions/OP-RECOVER/items") {
      await route.fulfill({
        json: {
          data: { items: [], page: 1, page_size: 20, total: 0 },
          meta: responseMeta,
          error: null,
        },
      });
    } else {
      throw new Error(`Unexpected API request: ${url.pathname}`);
    }
  });
}

test("root opens the workspace and capability exposes the data center", async ({
  page,
}) => {
  await installWorkspaceFixtures(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/home$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "工作台" }),
  ).toBeVisible();
  await expect(page.getByRole("navigation", { name: "主导航" })).toContainText(
    "数据抓取",
  );
  await expect(page.getByRole("region", { name: "基金总数" })).toContainText(
    "1",
  );
});

test("operation deep links survive refresh without submitting another job", async ({
  page,
}) => {
  await installWorkspaceFixtures(page);
  const submissions: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") submissions.push(request.url());
  });
  await page.goto("/data-ingestion?operation_id=OP-RECOVER");
  await expect(
    page.getByRole("heading", { name: "任务 OP-RECOVER" }),
  ).toBeVisible();
  await expect(
    page.getByText("基本信息 · 单只基金 · 来源：akshare · 提交人：USR-001"),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "任务 OP-RECOVER" }),
  ).toBeVisible();
  expect(submissions).toEqual([]);
});

test("failed identity lookup hides ingestion controls", async ({ page }) => {
  test.setTimeout(120_000);
  await installWorkspaceFixtures(page);
  await page.route("**/api/v1/session", async (route) => {
    await route.fulfill({
      status: 500,
      json: errorEnvelope("INTERNAL_SERVER_ERROR"),
    });
  });
  const writes: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writes.push(request.url());
    }
  });
  await page.goto("/data-ingestion");
  await expect(
    page.getByRole("alert", { name: /500 INTERNAL_SERVER_ERROR/ }),
  ).toBeVisible({ timeout: 45_000 });
  expect(writes).toEqual([]);
  await expect(page.getByRole("button", { name: "创建抓取预览" })).toHaveCount(
    0,
  );
});

test("data center remains readable at the equivalent of 200 percent zoom", async ({
  page,
}) => {
  await installWorkspaceFixtures(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/data-ingestion");
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  await expect(
    page.getByRole("heading", { name: "基金数据中心" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  const main = page.locator("main");
  const dimensions = await main.evaluate((node) => ({
    clientWidth: node.clientWidth,
    scrollWidth: node.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(
    dimensions.clientWidth + 1,
  );
});

test("mobile navigation remains keyboard reachable with reduced motion", async ({
  page,
}) => {
  await installWorkspaceFixtures(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/home");
  await page.locator("body").press("Tab");
  await expect(page.getByRole("link", { name: "跳至主要内容" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "打开导航" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "客户投资工作区" }),
  ).toBeVisible();
  const drawer = page.getByRole("dialog", { name: "客户投资工作区" });
  await expect(drawer.getByRole("link", { name: "工作台" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "打开导航" })).toBeFocused();
});
