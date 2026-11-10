import { expect, test, type Page } from "@playwright/test";
import { classificationCatalog } from "../src/test/classificationFixtures";
import {
  fundListEnvelope,
  fundManagementCompaniesEnvelope,
  responseMeta,
  sessionEnvelope,
} from "../src/test/contractFixtures";

// Failures caught: lost URL/API filters, client-only paging/sorting, stale totals,
// wrong 30/70 allocation, non-grid result decorations, hidden pager, and overflow.
async function installFixtures(page: Page) {
  const requests: URL[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== "GET")
      throw new Error(`Acceptance must not write: ${url.pathname}`);
    const path = url.pathname;
    if (path.endsWith("/session"))
      return route.fulfill({ json: sessionEnvelope });
    if (path.endsWith("/fund-classifications/catalog"))
      return route.fulfill({
        json: {
          ...classificationCatalog,
          data: {
            ...classificationCatalog.data,
            dimensions: {
              ...classificationCatalog.data.dimensions,
              asset_class: [
                "EQUITY",
                "BOND",
                "MIXED",
                "MONEY_MARKET",
                "FOF",
                "REIT",
                "COMMODITY",
                "OTHER",
                "UNKNOWN",
              ],
            },
          },
        },
      });
    if (path.endsWith("/fund-management-companies"))
      return route.fulfill({ json: fundManagementCompaniesEnvelope });
    if (!path.endsWith("/funds"))
      throw new Error(`Unexpected API request: ${path}`);
    requests.push(url);
    const current = Number(url.searchParams.get("page") ?? 1);
    const size = Number(url.searchParams.get("page_size") ?? 20);
    const filtered = url.searchParams.has("fund_code");
    const total = filtered ? 1 : 231;
    const start = (current - 1) * size;
    const data = Array.from(
      { length: Math.max(0, Math.min(size, total - start)) },
      (_, index) => ({
        ...fundListEnvelope.data[0],
        share_class_id: String(start + index + 101),
        fund_code: String(start + index + 1).padStart(6, "0"),
        fund_name: "同名基金",
      }),
    );
    await route.fulfill({
      json: {
        data,
        meta: {
          ...responseMeta,
          subscription_status_source: "PLACEHOLDER",
          pagination: {
            page: current,
            page_size: size,
            total_items: total,
            total_pages: Math.ceil(total / size),
          },
        },
        error: null,
      },
    });
  });
  return requests;
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
  // 1440×900 at 200% browser zoom has a 720×450 CSS-pixel viewport.
  { width: 720, height: 450 },
]) {
  test(`research workspace uses 30/70 and grid-only results at ${viewport.width}x${viewport.height}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    await installFixtures(page);
    await page.goto("/funds?page_size=200");
    const grid = page.getByRole("grid", { name: "基金研究结果" });
    await expect(
      grid.getByRole("gridcell", { name: "000001", exact: true }),
    ).toBeVisible();
    const workspace = page.locator('[data-testid="fund-research-page"] > div');
    const query = page.getByRole("region", { name: "基金查询条件" });
    const results = page.getByRole("region", { name: "基金研究结果区" });
    const workBox = (await workspace.boundingBox())!;
    const queryBox = (await query.boundingBox())!;
    const resultBox = (await results.boundingBox())!;
    console.log(
      JSON.stringify({
        viewport,
        workspace: workBox,
        query: queryBox,
        results: resultBox,
        queryRatio: queryBox.height / workBox.height,
      }),
    );
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(viewport.width);
    expect(
      queryBox.height / (queryBox.height + resultBox.height),
    ).toBeGreaterThan(0.29);
    expect(queryBox.height / (queryBox.height + resultBox.height)).toBeLessThan(
      0.31,
    );
    await expect(results.locator(":scope > *")).toHaveCount(1);
    const collapse = page.getByRole("button", { name: "收起查询条件" });
    await expect(collapse).toBeVisible();
    await collapse.click();
    await expect(query).toBeHidden();
    await expect(
      page.getByRole("button", { name: "展开查询条件" }),
    ).toBeVisible();
    await expect(grid).toBeVisible();
    await page.getByRole("button", { name: "展开查询条件" }).click();
    await expect(query).toBeVisible();
    const pager = page.getByText("每页行数：");
    console.log(
      JSON.stringify({
        pager: await pager.boundingBox(),
        grid: await grid.boundingBox(),
      }),
    );
    await expect(pager).toBeInViewport();
    await expect(
      grid.getByRole("gridcell", { name: "000001", exact: true }),
    ).toBeInViewport();
    await expect
      .poll(() =>
        grid.evaluate((node) => node.scrollHeight > node.clientHeight),
      )
      .toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`expanded-${viewport.width}.png`),
      fullPage: true,
    });
    await expect(pager).toBeInViewport();
  });
}

test("server paging 20/50/200 preserves totals, four columns, equal-name identities and URL on refresh", async ({
  page,
}) => {
  const requests = await installFixtures(page);
  await page.goto("/funds");
  const browserAddress = page.url();
  const grid = page.getByRole("grid", { name: "基金研究结果" });
  await expect(grid.locator(".ag-header-cell-text")).toHaveText([
    "基金代码",
    "基金名称",
    "管理公司",
    "申购状态",
    "详情",
  ]);
  for (const size of [50, 200, 20]) {
    await page.getByRole("combobox", { name: "Page Size" }).click();
    await page.getByRole("option", { name: String(size), exact: true }).click();
    await expect
      .poll(() =>
        requests.some(
          (url) => url.searchParams.get("page_size") === String(size),
        ),
      )
      .toBe(true);
    expect(page.url()).toBe(browserAddress);
  }
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(
    grid.getByRole("gridcell", { name: "000021", exact: true }),
  ).toBeVisible();
  await expect(page.locator('.ag-row[row-id="121"]')).toBeVisible();
  await page.getByRole("columnheader", { name: "管理公司" }).click();
  await expect
    .poll(() => requests.at(-1)?.searchParams.get("sort"))
    .toBe("fund_company");
  expect(page.url()).toBe(browserAddress);
  const saved = page.url();
  await page.reload();
  await expect(
    grid.getByRole("gridcell", { name: "000001", exact: true }),
  ).toBeVisible();
  expect(page.url()).toBe(saved);
});

test("five research filters reach API literally without changing browser URL", async ({
  page,
}) => {
  const requests = await installFixtures(page);
  await page.goto("/funds?page=3");
  const browserAddress = page.url();
  await page.getByLabel("基金名称", { exact: true }).fill("同名_%' OR 1=1");
  await page.getByLabel("基金代码", { exact: true }).fill("000001");
  await page.getByRole("combobox", { name: "管理公司", exact: true }).click();
  await page.getByRole("option", { name: "Alpha 基金管理有限公司" }).click();
  await page.getByRole("combobox", { name: "基金类别" }).click();
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(9);
  await page.getByRole("option", { name: "EQUITY", exact: true }).click();
  await page.getByRole("combobox", { name: "申购状态" }).click();
  await page.getByRole("option", { name: "开放（占位）" }).click();
  await page.getByRole("button", { name: "查询基金" }).click();
  await expect
    .poll(() => requests.at(-1)?.searchParams.get("fund_code"))
    .toBe("000001");
  for (const [key, value] of Object.entries({
    fund_name: "同名_%' OR 1=1",
    fund_code: "000001",
    fund_company: "Alpha 基金管理有限公司",
    asset_class: "EQUITY",
    sub_status: "开放",
    page: "1",
  })) {
    expect(requests.at(-1)?.searchParams.get(key)).toBe(value);
  }
  expect(page.url()).toBe(browserAddress);
});
