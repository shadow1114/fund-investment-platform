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

async function installFixtures(page: Page, dashboard = false) {
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
          points: dashboard
            ? Array.from({ length: 32 }, (_, index) => ({
                date: new Date(Date.UTC(2026, 7, 15 + index))
                  .toISOString()
                  .slice(0, 10),
                nav: 1.24 + index * 0.01 + Math.sin(index / 3) * 0.04,
                nav_status: "VALID",
                nav_reason: null,
              }))
            : [
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
          factor_categories: dashboard
            ? [
                [
                  "RET",
                  "收益表现",
                  ["年化收益率", "累计收益率", "区间收益率", "滚动收益率"],
                ],
                ["RAP", "风险调整收益", ["夏普比率", "索提诺比率", "卡玛比率"]],
                [
                  "REL",
                  "相对表现",
                  ["超额收益", "Alpha", "Beta", "信息比率", "跟踪误差"],
                ],
                [
                  "RISK",
                  "风险指标",
                  [
                    "年化波动率",
                    "下行波动率",
                    "最大回撤",
                    "VaR",
                    "CVaR",
                    "回撤持续期",
                    "回撤恢复期",
                  ],
                ],
                [
                  "STAB",
                  "稳定性",
                  [
                    "正收益比例",
                    "R²",
                    "偏度",
                    "峰度",
                    "滚动夏普",
                    "滚动波动率",
                    "滚动最大回撤",
                  ],
                ],
              ].map(([category, name, names]) => ({
                category,
                name,
                factors: (names as string[]).map((factorName, index) => ({
                  factor_id: `F-${category}-${String(index + 1).padStart(3, "0")}`,
                  name: factorName,
                  category,
                  raw_value:
                    index === 6
                      ? null
                      : category === "RISK" && index === 5
                        ? 42
                        : 0.12 + index * 0.01,
                  normalized_value: null,
                  status: index === 6 ? "UNAVAILABLE" : "VALID",
                  reason_code: index === 6 ? "NOT_RECOVERED" : null,
                  direction:
                    category === "RISK"
                      ? "LOWER_IS_BETTER"
                      : "HIGHER_IS_BETTER",
                  observations: 252,
                  series:
                    category === "STAB" && index === 4
                      ? Array.from({ length: 32 }, (_, point) => ({
                          date: new Date(Date.UTC(2026, 7, 15 + point))
                            .toISOString()
                            .slice(0, 10),
                          value: 0.8 + point * 0.01,
                        }))
                      : [],
                })),
              }))
            : [],
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
  await expect(dialog.getByText("2.3400", { exact: true })).toBeVisible();
  expect(
    requests.some((url) => url.pathname.endsWith("/factor-analysis")),
  ).toBe(true);
  await dialog
    .getByRole("tab", { name: "滚动指标演变 (Sharpe/波动率)" })
    .click();
  await dialog
    .getByRole("radiogroup", { name: "分析周期" })
    .getByText("5年", { exact: true })
    .click();
  await expect
    .poll(() =>
      requests.some(
        (url) =>
          url.pathname === "/api/v1/funds/102/factor-analysis" &&
          url.searchParams.get("evaluation_period") === "5Y",
      ),
    )
    .toBe(true);
  for (const suffix of ["", "/nav-series", "/factor-analysis"]) {
    const request = requests.find(
      (url) => url.pathname === `/api/v1/funds/102${suffix}`,
    );
    expect(request?.searchParams.get("as_of_date")).toBe("2026-09-16");
  }
  await expect(
    dialog.getByRole("link", { name: "在数据中心抓取基本信息" }),
  ).toHaveCount(0);
  await expect(dialog.getByText(/申购状态.*固定.*开放/)).toHaveCount(0);
  await expect(
    dialog.getByRole("link", { name: "打开独立详情页" }),
  ).toHaveCount(0);
  expect(
    requests.some((url) =>
      /\/(evaluations|scores|basic-info-history|classification-history)$/.test(
        url.pathname,
      ),
    ),
  ).toBe(false);
  expect(page.url()).toBe(backgroundUrl);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(
    row(page, "102").getByRole("button", { name: "查看详情 Alpha C" }),
  ).toBeFocused();
  await row(page, "101")
    .getByRole("button", { name: "查看详情 Alpha A" })
    .click();
  await expect(
    dialog.getByRole("tab", { name: "净值走势 vs 基准超额" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(dialog.getByText("1.2400", { exact: true })).toBeVisible();
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

test("mobile touch alternative fills the content below the header", async ({
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
  expect(box?.x).toBe(0);
  expect(box?.y).toBe(64);
  expect(box?.height).toBe(780);
  await dialog.getByRole("button", { name: "关闭基金详情" }).click();
  await expect(trigger).toBeFocused();
});

test("detail fills the desktop content area without overlapping export", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await installFixtures(page, true);
  await page.goto("/funds");
  await row(page, "101")
    .getByRole("button", { name: "查看详情 Alpha A" })
    .click();
  const dialog = page.getByRole("dialog", { name: "基金详情" });
  await expect(dialog.getByRole("heading", { name: "Alpha A" })).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box?.x).toBe(240);
  expect(box?.y).toBe(64);
  expect(box?.width).toBe(1200);
  expect(box?.height).toBe(936);
  const close = await dialog
    .getByRole("button", { name: "关闭基金详情" })
    .boundingBox();
  const exportButton = await dialog
    .getByRole("button", { name: "导出简报" })
    .boundingBox();
  expect(close).not.toBeNull();
  expect(exportButton).not.toBeNull();
  expect(close!.y + close!.height).toBeLessThanOrEqual(exportButton!.y);
  await page.screenshot({
    path: testInfo.outputPath("fund-detail-content-area.png"),
  });
});

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
]) {
  test(`prototype dashboard matches the supplied content at ${viewport.width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    await installFixtures(page, true);
    await page.goto("/funds/000001?share_class_id=101&as_of_date=2026-09-16");
    await expect(page.getByRole("heading", { name: "Alpha A" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /量化多因子多维矩阵/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "收益指标 (4)", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page.locator("canvas").first()).toBeVisible();
    await expect
      .poll(() =>
        page
          .locator("canvas")
          .first()
          .evaluate((canvas: HTMLCanvasElement) => {
            const pixels = canvas
              .getContext("2d")!
              .getImageData(0, 0, canvas.width, canvas.height).data;
            let visible = 0;
            for (let offset = 3; offset < pixels.length; offset += 4)
              if (pixels[offset] > 0) visible++;
            return visible;
          }),
      )
      .toBeGreaterThan(100);
    await expect(page.locator("dl dt")).toHaveCount(26);
    await expect(page.getByRole("tab")).toHaveCount(3);
    await expect(
      page
        .getByRole("region", { name: "多周期数值" })
        .getByRole("columnheader")
        .filter({ hasText: /^(1个月|3个月|6个月|1年|3年|5年|成立以来)/ }),
    ).toHaveCount(7);
    for (const text of [
      "五维分类与证据",
      "数据抓取",
      "评分归因",
      "点时数据：是",
      "查看图表数值",
      "加载全部周期",
      "返回基金研究",
    ]) {
      await expect(
        page.getByRole("main").getByText(text, { exact: true }),
      ).toHaveCount(0);
    }
    await expect(
      page.getByRole("region", { name: "多周期数值" }).getByText("计算中"),
    ).toHaveCount(0);
    await expect(
      page.getByRole("region", { name: "多周期数值" }).getByText("未加载"),
    ).toHaveCount(0);
    const matrix = page.locator('[data-category="RET"]').locator("..");
    await matrix.screenshot({
      path: testInfo.outputPath(`factor-matrix-${viewport.width}.png`),
    });
    if (viewport.width < 600) {
      const panorama = page.getByRole("region", { name: "多周期数值" });
      expect(
        await panorama.evaluate(
          (element) => element.scrollWidth > element.clientWidth,
        ),
      ).toBe(true);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath(`fund-dashboard-${viewport.width}.png`),
      fullPage: true,
    });
    await page
      .getByRole("tab", { name: "滚动指标演变 (Sharpe/波动率)" })
      .click();
    await expect(
      page.getByRole("tab", { name: "滚动指标演变 (Sharpe/波动率)" }),
    ).toHaveAttribute("aria-selected", "true");
  });
}

test("an exact share-class route survives reload and preserves tab, period and safe return URL", async ({
  page,
}) => {
  const requests = await installFixtures(page);
  await page.goto(
    "/funds/000001?share_class_id=102&as_of_date=2026-09-16&tab=rolling&factor_period=5Y&return_to=%2Ffunds%3Fpage%3D3",
  );
  await expect(page.getByRole("heading", { name: "Alpha C" })).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "滚动指标演变 (Sharpe/波动率)" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("link", { name: "返回基金研究" })).toHaveCount(0);
  const beforeReload = requests.filter(
    (url) =>
      url.pathname === "/api/v1/funds/102/factor-analysis" &&
      url.searchParams.get("evaluation_period") === "5Y",
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
