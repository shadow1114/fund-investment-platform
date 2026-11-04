import { expect, test, type Page } from "@playwright/test";
import {
  classificationCatalog,
  emptyClassificationHistory,
} from "../src/test/classificationFixtures";
import {
  fundBasicInfoHistoryEnvelope,
  fundDetailEnvelope,
  fundEvaluationEnvelope,
  fundIngestionListEnvelope,
  fundListEnvelope,
  fundNavEnvelope,
  fundScoreEnvelope,
  responseMeta,
  sessionEnvelope,
} from "../src/test/contractFixtures";

async function installFixtures(page: Page) {
  const requests: URL[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    const path = url.pathname;
    let body: unknown;
    if (path.endsWith("/session"))
      body = {
        ...sessionEnvelope,
        data: {
          ...sessionEnvelope.data,
          capabilities: {
            ...sessionEnvelope.data.capabilities,
            can_manage_data_ingestion: true,
          },
        },
      };
    else if (path.endsWith("/fund-classifications/catalog"))
      body = classificationCatalog;
    else if (path.endsWith("/fund-management-companies"))
      body = { data: [], meta: responseMeta, error: null };
    else if (path.endsWith("/funds"))
      body = {
        ...fundListEnvelope,
        data: Array.from({ length: 30 }, (_, index) => ({
          ...fundListEnvelope.data[0],
          share_class_id: String(101 + index),
          fund_name:
            index === 0
              ? "Alpha A"
              : index === 1
                ? "Alpha C"
                : `Alpha ${index}`,
          share_class: index === 1 ? "C" : "A",
        })),
        meta: {
          ...fundListEnvelope.meta,
          pagination: {
            page: 1,
            page_size: 200,
            total_items: 30,
            total_pages: 1,
          },
        },
      };
    else if (path.endsWith("/basic-info-history"))
      body = fundBasicInfoHistoryEnvelope;
    else if (path.endsWith("/fund-ingestions"))
      body = {
        data: { items: [], page: 1, page_size: 20, total: 0 },
        meta: responseMeta,
        error: null,
      };
    else if (path.endsWith("/ingestions")) body = fundIngestionListEnvelope;
    else if (path.endsWith("/classification-history"))
      body = emptyClassificationHistory;
    else if (path.endsWith("/nav-series"))
      body = {
        ...fundNavEnvelope,
        data: {
          ...fundNavEnvelope.data,
          points: [
            {
              ...fundNavEnvelope.data.points[0],
              nav: path.includes("/102/") ? 2.34 : 1.24,
            },
          ],
        },
      };
    else if (path.endsWith("/evaluations")) body = fundEvaluationEnvelope;
    else if (path.endsWith("/scores")) body = fundScoreEnvelope;
    else if (path.endsWith("/factor-analysis"))
      body = {
        data: {
          fund_id: "000001",
          evaluation_period: url.searchParams.get("evaluation_period"),
          as_of_date: "2026-09-16",
          factor_categories: [],
        },
        meta: responseMeta,
        error: null,
      };
    else if (/\/funds\/\w+$/.test(path))
      body = {
        ...fundDetailEnvelope,
        data: {
          ...fundDetailEnvelope.data,
          fund_name: path.endsWith("/102") ? "Alpha C" : "Alpha A",
          share_class: path.endsWith("/102") ? "C" : "A",
        },
      };
    else throw new Error(`Unexpected API request ${path}`);
    await route.fulfill({ json: body });
  });
  return requests;
}

const row = (page: Page, id: string) => page.locator(`.ag-row[row-id="${id}"]`);

test("double-click opens the exact share class; local tabs preserve background URL/scroll, close restores focus", async ({
  page,
}) => {
  const requests = await installFixtures(page);
  await page.goto("/funds?as_of_date=2026-09-16&page_size=200");
  await expect(row(page, "102")).toBeVisible();
  const backgroundUrl = page.url();
  expect(
    requests.some((url) => /\/funds\/101(?:\/|$)/.test(url.pathname)),
  ).toBe(false);
  await row(page, "102").locator('[col-id="fund_code"]').dblclick();
  const dialog = page.getByRole("dialog", { name: "基金详情" });
  await expect(dialog.getByRole("heading", { name: "Alpha C" })).toBeVisible();
  await dialog.getByText("查看图表数值").click();
  await expect(
    dialog.getByRole("gridcell", { name: "2.34", exact: true }),
  ).toBeVisible();
  expect(
    requests.some((url) => url.pathname.endsWith("/factor-analysis")),
  ).toBe(false);
  await dialog.getByRole("tab", { name: "因子分析" }).click();
  await dialog.getByRole("button", { name: "近5年" }).click();
  await expect
    .poll(() =>
      requests.some(
        (url) =>
          url.pathname === "/api/v1/funds/102/factor-analysis" &&
          url.searchParams.get("evaluation_period") === "5Y",
      ),
    )
    .toBe(true);
  for (const suffix of [
    "",
    "/nav-series",
    "/evaluations",
    "/scores",
    "/factor-analysis",
  ]) {
    const request = requests.find(
      (url) => url.pathname === `/api/v1/funds/102${suffix}`,
    );
    expect(request?.searchParams.get("as_of_date")).toBe("2026-09-16");
  }
  await expect(
    dialog.getByRole("link", { name: "在数据中心抓取基本信息" }),
  ).toHaveAttribute(
    "href",
    "/data-ingestion?fund_id=000001&dataset=BASIC_INFO",
  );
  await expect(dialog.getByText(/申购状态.*固定.*开放/)).toBeVisible();
  await expect(
    dialog.getByRole("link", { name: "打开独立详情页" }),
  ).toHaveAttribute(
    "href",
    /\/funds\/000001\?.*share_class_id=102.*tab=factors.*factor_period=5Y/,
  );
  expect(page.url()).toBe(backgroundUrl);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(
    row(page, "102").getByRole("button", { name: "查看详情 Alpha C" }),
  ).toBeFocused();
  await row(page, "101")
    .getByRole("button", { name: "查看详情 Alpha A" })
    .click();
  await expect(dialog.getByRole("tab", { name: "净值" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await dialog.getByText("查看图表数值").click();
  await expect(
    dialog.getByRole("gridcell", { name: "1.24", exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "关闭基金详情" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(
    row(page, "101").getByRole("button", { name: "查看详情 Alpha A" }),
  ).toBeFocused();
  const viewport = page.getByRole("grid", { name: "基金研究结果" });
  await viewport.evaluate((element) => {
    element.scrollTop = 300;
  });
  await expect
    .poll(() => viewport.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0);
  const scrolledTrigger = row(page, "110").getByRole("button", {
    name: "查看详情 Alpha 9",
  });
  await scrolledTrigger.scrollIntoViewIfNeeded();
  const scrollTop = await viewport.evaluate((element) => element.scrollTop);
  await scrolledTrigger.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(scrolledTrigger).toBeFocused();
  expect(await viewport.evaluate((element) => element.scrollTop)).toBe(
    scrollTop,
  );
  expect(page.url()).toBe(backgroundUrl);
});

test("row links never trigger the modal; keyboard button opens it and traps focus", async ({
  page,
}) => {
  await installFixtures(page);
  await page.goto("/funds");
  const first = row(page, "101");
  for (const name of ["Alpha A", "在数据中心抓取基本信息"]) {
    const link = first.getByRole("link", { name, exact: true });
    await link.evaluate((element) =>
      element.addEventListener("click", (event) => event.preventDefault()),
    );
    await link.dblclick();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  const trigger = first.getByRole("button", { name: "查看详情 Alpha A" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "基金详情" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Alpha A" })).toBeVisible();
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(
    first.getByRole("link", { name: "Alpha A", exact: true }),
  ).toHaveAttribute("href", /share_class_id=101/);
});

test("mobile touch alternative opens a full-screen detail dialog", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installFixtures(page);
  await page.goto("/funds");
  const trigger = row(page, "101").getByRole("button", {
    name: "查看详情 Alpha A",
  });
  await trigger.scrollIntoViewIfNeeded();
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "基金详情" });
  await expect(dialog.getByRole("heading", { name: "Alpha A" })).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box?.width).toBe(390);
  await dialog.getByRole("button", { name: "关闭基金详情" }).click();
  await expect(trigger).toBeFocused();
});

test("an exact share-class route survives reload and preserves tab, period and safe return URL", async ({
  page,
}) => {
  const requests = await installFixtures(page);
  await page.goto(
    "/funds/000001?share_class_id=102&as_of_date=2026-09-16&tab=factors&factor_period=5Y&return_to=%2Ffunds%3Fpage%3D3",
  );
  await expect(page.getByRole("heading", { name: "Alpha C" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "因子分析" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("link", { name: "返回基金研究" }),
  ).toHaveAttribute("href", "/funds?page=3");
  const beforeReload = requests.filter(
    (url) => url.pathname === "/api/v1/funds/102/factor-analysis",
  ).length;
  await page.reload();
  await expect(page.getByRole("heading", { name: "Alpha C" })).toBeVisible();
  await expect
    .poll(
      () =>
        requests.filter(
          (url) =>
            url.pathname === "/api/v1/funds/102/factor-analysis" &&
            url.searchParams.get("evaluation_period") === "5Y",
        ).length,
    )
    .toBeGreaterThan(beforeReload);
});
