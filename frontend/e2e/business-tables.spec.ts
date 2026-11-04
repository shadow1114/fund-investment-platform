import { expect, test } from "@playwright/test";
import {
  portfolioListEnvelope,
  portfolioEnvelope,
  responseMeta,
  sessionEnvelope,
  universeDetailEnvelope,
  universeListEnvelope,
} from "../src/test/contractFixtures";

test("candidate grids retain score reasons and expandable exclusion evidence", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path.endsWith("/session")
      ? sessionEnvelope
      : path.endsWith("/fund-universes")
        ? universeListEnvelope
        : path.endsWith("/fund-universes/UNI-001")
          ? universeDetailEnvelope
          : null;
    if (!json) throw new Error(`Unexpected API request: ${path}`);
    await route.fulfill({ json });
  });
  await page.goto("/universes");
  await expect(
    page.getByRole("grid", { name: "候选池快照列表" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "UNI-001", exact: true }).click();
  await expect(page.getByRole("grid", { name: "已入选成员" })).toContainText(
    "不可用（ELIGIBILITY_ONLY）",
  );
  await page.getByRole("tab", { name: "已排除（1）" }).click();
  const grid = page.getByRole("grid", { name: "已排除成员" });
  await expect(grid).toContainText("不可用（FAILED_ELIGIBILITY）");
  await grid.getByRole("button", { name: "展开 000002 的未通过条件" }).click();
  await expect(grid).toContainText("minimum_aum");
});

test("portfolio pagination requests new pages without changing the browser URL", async ({
  page,
}) => {
  const requests: URL[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/session"))
      return route.fulfill({ json: sessionEnvelope });
    if (!url.pathname.endsWith("/portfolios"))
      throw new Error(`Unexpected API request: ${url.pathname}`);
    requests.push(url);
    const current = Number(url.searchParams.get("page"));
    await route.fulfill({
      json: {
        ...portfolioListEnvelope,
        data: [
          {
            ...portfolioListEnvelope.data[0],
            portfolio_id: `P${current}`,
            portfolio_name: `组合第 ${current} 页`,
          },
        ],
        meta: {
          ...portfolioListEnvelope.meta,
          pagination: {
            page: current,
            page_size: 20,
            total_items: 41,
            total_pages: 3,
          },
        },
      },
    });
  });
  await page.goto(
    "/portfolios?page=2&page_size=20&sort=portfolio_id&order=desc",
  );
  const browserAddress = page.url();
  await expect(page.getByRole("link", { name: "组合第 2 页" })).toBeVisible();
  const table = page.getByRole("region", { name: "可见组合列表" });
  await expect(table.getByRole("button", { name: "下一页" })).toHaveCount(1);
  await table.getByRole("button", { name: "下一页" }).click();
  await expect(page.getByRole("link", { name: "组合第 3 页" })).toBeVisible();
  expect(page.url()).toBe(browserAddress);
  expect(Object.fromEntries(requests.at(-1)!.searchParams)).toEqual({
    page: "3",
    page_size: "20",
    sort: "portfolio_id",
    order: "desc",
  });
  await expect(table.getByRole("button", { name: "下一页" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(table.getByRole("button", { name: "下一页" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
});

test("PM weight editor keeps decimal edits attached to fund identity through sort and paging", async ({
  page,
}) => {
  const weights = Array.from({ length: 21 }, (_, index) => ({
    fund_id: String(index + 1).padStart(6, "0"),
    weight: index === 0 ? 0.5 : 0.025,
  }));
  const writes: unknown[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== "GET") {
      writes.push(route.request().postDataJSON());
      throw new Error(`No review submission expected in acceptance: ${path}`);
    }
    if (path.endsWith("/session"))
      return route.fulfill({
        json: {
          ...sessionEnvelope,
          data: {
            ...sessionEnvelope.data,
            capabilities: {
              ...sessionEnvelope.data.capabilities,
              can_review_decisions: true,
            },
          },
        },
      });
    if (path.endsWith("/portfolios/P001"))
      return route.fulfill({ json: portfolioEnvelope });
    if (path.endsWith("/decisions/D1"))
      return route.fulfill({
        json: {
          data: {
            decision_id: "D1",
            portfolio_id: "P001",
            optimization_id: "O1",
            decision_status: "PROPOSED",
            proposed_weights: weights,
            final_weights: null,
            review: null,
          },
          meta: responseMeta,
          error: null,
        },
      });
    throw new Error(`Unexpected API request: ${path}`);
  });
  await page.goto("/portfolios/P001?tab=decision&decision_id=D1");
  const grid = page.getByRole("grid", { name: "决策覆盖权重" });
  await expect(grid).toBeVisible();
  await grid.getByRole("columnheader", { name: "基金", exact: true }).click();
  await grid.getByRole("columnheader", { name: "基金", exact: true }).click();
  await page.getByRole("textbox", { name: "000021 覆盖权重" }).fill("0.03");
  await page
    .getByRole("textbox", { name: "复核理由" })
    .fill("浏览器验收权重编辑");
  await expect(page.getByRole("button", { name: "确认覆盖" })).toBeDisabled();
  const editor = page.getByRole("region", { name: "可编辑覆盖权重" });
  await editor.getByRole("button", { name: "下一页" }).click();
  await page.getByRole("textbox", { name: "000001 覆盖权重" }).fill("0.495");
  await expect(
    page.getByText("覆盖权重合计：100.00%（提交要求约为 100%）"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "确认覆盖" })).toBeEnabled();
  await editor.getByRole("button", { name: "上一页" }).click();
  await expect(
    page.getByRole("textbox", { name: "000021 覆盖权重" }),
  ).toHaveValue("0.03（小数）");
  expect(writes).toEqual([]);
});
