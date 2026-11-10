import { expect, test, type Page, type Route } from "@playwright/test";
import { classificationCatalog } from "../src/test/classificationFixtures";
import { responseMeta, sessionEnvelope } from "../src/test/contractFixtures";

async function installFundResearchFixtures(page: Page, canManage = false) {
  const requestedPages: number[] = [];
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/session") {
      await route.fulfill({
        json: canManage
          ? {
              ...sessionEnvelope,
              data: {
                ...sessionEnvelope.data,
                capabilities: {
                  ...sessionEnvelope.data.capabilities,
                  can_manage_data_ingestion: true,
                },
              },
            }
          : sessionEnvelope,
      });
    } else if (url.pathname === "/api/v1/fund-classifications/catalog") {
      await route.fulfill({ json: classificationCatalog });
    } else if (url.pathname === "/api/v1/fund-management-companies") {
      await route.fulfill({
        json: {
          data: [{ fund_company: "测试基金管理有限公司" }],
          meta: responseMeta,
          error: null,
        },
      });
    } else if (url.pathname === "/api/v1/fund-ingestions") {
      await route.fulfill({
        json: {
          data: { items: [], page: 1, page_size: 20, total: 0 },
          meta: responseMeta,
          error: null,
        },
      });
    } else if (url.pathname === "/api/v1/funds") {
      const pageNumber = Number(url.searchParams.get("page") ?? "1");
      requestedPages.push(pageNumber);
      const pageSize = Number(url.searchParams.get("page_size") ?? "20");
      const itemCount = Math.max(
        0,
        Math.min(pageSize, 100 - (pageNumber - 1) * pageSize),
      );
      const data = Array.from({ length: itemCount }, (_, index) => {
        const id = String((pageNumber - 1) * pageSize + index + 1).padStart(
          6,
          "0",
        );
        return {
          fund_id: id,
          fund_code: id,
          fund_name: `测试基金 ${id}`,
          share_class: "A",
          share_class_id: `SC-${id}`,
          fund_classification: "EQUITY",
          management_company_id: "MC-1",
          fund_company: "测试基金管理有限公司",
          inception_date: "2020-01-01",
          lifecycle_status: "NORMAL",
          investment_eligibility: "FULLY_ELIGIBLE",
          sub_status: "开放",
          manager_ids: [],
        };
      });
      await route.fulfill({
        json: {
          data,
          meta: {
            ...responseMeta,
            as_of_date: "2026-10-01",
            data_version: "funds-layout",
            versions: { classification_version: "class-v1" },
            is_point_in_time: false,
            pagination: {
              page: pageNumber,
              page_size: pageSize,
              total_items: 100,
              total_pages: Math.ceil(100 / pageSize),
            },
            availability_quality_distribution: {
              EXACT: 100,
              DERIVED: 0,
              INFERRED: 0,
            },
            subscription_status_source: "PLACEHOLDER",
          },
          error: null,
        },
      });
    } else {
      throw new Error(`Unexpected API request: ${url.pathname}`);
    }
  });
  return requestedPages;
}

test("fund research allocates 30/70 and keeps only the grid in the lower region", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await installFundResearchFixtures(page);
  await page.goto("/funds?page_size=200");
  const grid = page.getByRole("grid", { name: "基金研究结果" });
  await expect(grid).toBeVisible();
  await expect(page.getByText("测试基金 000001")).toBeVisible();
  await expect(page.getByText("每页行数：")).toBeVisible();
  const queryPanel = await page
    .getByRole("region", { name: "基金查询条件" })
    .boundingBox();
  const results = page.getByRole("region", { name: "基金研究结果区" });
  const resultPanel = await results.boundingBox();
  const queryRatio =
    queryPanel && resultPanel
      ? queryPanel.height / (queryPanel.height + resultPanel.height)
      : 0;
  expect(queryRatio).toBeGreaterThan(0.29);
  expect(queryRatio).toBeLessThan(0.31);
  await expect(results.locator(":scope > *")).toHaveCount(1);
  const toggle = page.getByRole("button", { name: "收起查询条件" });
  await expect(toggle).toBeVisible();
  const expandedToggleBackground = await toggle.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  await toggle.hover();
  expect(
    await toggle.evaluate(
      (element) => getComputedStyle(element).backgroundColor,
    ),
  ).toBe(expandedToggleBackground);
  await toggle.click();
  await expect(page.getByRole("region", { name: "基金查询条件" })).toBeHidden();
  const expand = page.getByRole("button", { name: "展开查询条件" });
  await expect(expand).toBeVisible();
  const collapsedToggleBackground = await expand.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  await expand.hover();
  expect(
    await expand.evaluate(
      (element) => getComputedStyle(element).backgroundColor,
    ),
  ).toBe(collapsedToggleBackground);
  const workspace = page.getByTestId("fund-research-workspace");
  const workspaceBox = (await workspace.boundingBox())!;
  const resultsBox = (await results.boundingBox())!;
  expect(resultsBox.y).toBeGreaterThan(workspaceBox.y + 40);
  expect(
    await results.evaluate(
      (element) => getComputedStyle(element).borderTopWidth,
    ),
  ).toBe("0px");
  expect(
    await workspace.evaluate(
      (element) => getComputedStyle(element, "::before").backgroundColor,
    ),
  ).toBe("rgb(255, 255, 255)");
  await expect(grid).toBeVisible();
  await expect(page.getByRole("button", { name: "列设置" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "表格密度" })).toHaveCount(0);
  await expand.click();
  await expect(
    page.getByRole("region", { name: "基金查询条件" }),
  ).toBeVisible();
  await expect
    .poll(async () =>
      grid.evaluate((element) => element.scrollHeight > element.clientHeight),
    )
    .toBe(true);
  await expect(grid).toBeVisible();
  await expect(page.getByText("每页行数：")).toBeVisible();
});

test("authorized basic-info actions remain inside the research grid", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await installFundResearchFixtures(page, true);
  await page.goto("/funds");
  const grid = page.getByRole("grid", { name: "基金研究结果" });
  await expect(
    grid.getByRole("columnheader", { name: "基本信息" }),
  ).toBeVisible();
  await expect(
    grid.getByRole("link", { name: "在数据中心抓取基本信息" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "基金研究结果区" }).locator(":scope > *"),
  ).toHaveCount(1);
});

test("a direct page-three URL stays synchronized with a single initial block request", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const requestedPages = await installFundResearchFixtures(page);
  await page.goto("/funds?page=3&page_size=20");
  const browserAddress = page.url();
  await expect(page.getByText("测试基金 000041")).toBeVisible();
  expect(page.url()).toBe(browserAddress);
  expect(requestedPages).toEqual([3]);
});

test("sort cycle resets to fund-name ascending when AG Grid clears its sort", async ({
  page,
}) => {
  await installFundResearchFixtures(page);
  await page.goto("/funds?page=3&page_size=20");
  const browserAddress = page.url();
  await expect(page.getByRole("grid", { name: "基金研究结果" })).toBeVisible();
  const fundName = page.getByRole("columnheader", { name: "基金名称" });
  await fundName.click();
  expect(page.url()).toBe(browserAddress);
  await expect(fundName).toHaveAttribute("aria-sort", "descending");
  await fundName.click();
  expect(page.url()).toBe(browserAddress);
  await expect(fundName).toHaveAttribute("aria-sort", "ascending");
});

test("out-of-range deep links still allow page-size and sort changes", async ({
  page,
}) => {
  await installFundResearchFixtures(page);
  await page.goto("/funds?page=99&page_size=20");
  const browserAddress = page.url();
  await expect(page.getByRole("grid", { name: "基金研究结果" })).toBeVisible();
  const pageSizeSelector = page.getByRole("combobox", { name: "Page Size" });
  await pageSizeSelector.click();
  await page.getByRole("option", { name: "50" }).click();
  expect(page.url()).toBe(browserAddress);
  await page.getByRole("columnheader", { name: "管理公司" }).click();
  expect(page.url()).toBe(browserAddress);
});

test("fund research filters stay operable without page-wide horizontal overflow on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installFundResearchFixtures(page);
  await page.goto("/funds");
  const browserAddress = page.url();
  await expect(page.getByRole("grid", { name: "基金研究结果" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("combobox", { name: "基金类别" }).click();
  await page.getByRole("option", { name: "EQUITY" }).click();
  await page.getByRole("button", { name: "查询基金" }).click();
  expect(page.url()).toBe(browserAddress);
});
