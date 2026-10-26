import {
  classificationCatalog,
  classificationHistoryEnvelope,
} from "../src/test/classificationFixtures";
import { expect, test, type Page } from "@playwright/test";

import {
  backtestBiasEnvelope,
  backtestCreatedEnvelope,
  backtestOperationEnvelope,
  backtestPerformanceEnvelope,
  backtestResultEnvelope,
  backtestRunEnvelope,
  backtestStatusEnvelope,
  backtestValidationEnvelope,
  errorEnvelope,
  fundDetailEnvelope,
  fundEvaluationEnvelope,
  fundListEnvelope,
  fundNavEnvelope,
  fundScoreEnvelope,
  portfolioEnvelope,
  portfolioListEnvelope,
  sessionEnvelope,
  universeDetailEnvelope,
  universeListEnvelope,
} from "../src/test/contractFixtures";

const apiFixtures: Record<string, unknown> = {
  "/api/v1/fund-classifications/catalog": classificationCatalog,
  "/api/v1/funds/000001/classification-history": classificationHistoryEnvelope,
  "/api/v1/funds": fundListEnvelope,
  "/api/v1/funds/000001": fundDetailEnvelope,
  "/api/v1/funds/000001/nav-series": fundNavEnvelope,
  "/api/v1/funds/000001/evaluations": fundEvaluationEnvelope,
  "/api/v1/funds/000001/scores": fundScoreEnvelope,
  "/api/v1/fund-universes": universeListEnvelope,
  "/api/v1/fund-universes/UNI-001": universeDetailEnvelope,
  "/api/v1/portfolios": portfolioListEnvelope,
  "/api/v1/portfolios/P001": portfolioEnvelope,
  "/api/v1/session": sessionEnvelope,
  "/api/v1/backtests": backtestCreatedEnvelope,
  "/api/v1/backtests/BT-001/validate-configuration": backtestValidationEnvelope,
  "/api/v1/backtests/BT-001/runs": backtestRunEnvelope,
  "/api/v1/operations/OP-BT-1": backtestOperationEnvelope,
  "/api/v1/backtests/BT-001/status": backtestStatusEnvelope,
  "/api/v1/backtests/BT-001/result": backtestResultEnvelope,
  "/api/v1/backtests/BT-001/performance": backtestPerformanceEnvelope,
  "/api/v1/backtests/BT-001/bias-check": backtestBiasEnvelope,
};
const successStatuses: Record<string, number> = {
  "/api/v1/backtests": 201,
  "/api/v1/backtests/BT-001/runs": 202,
};

async function installFrozenApi(
  page: Page,
  overrides: Record<string, { status: number; body: unknown }> = {},
) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const override = overrides[url.pathname];
    if (override) {
      await route.fulfill({ status: override.status, json: override.body });
      return;
    }
    const fixture = apiFixtures[url.pathname];
    if (fixture === undefined) {
      throw new Error(`Unexpected API request: ${url.pathname}`);
    }
    await route.fulfill({
      status: successStatuses[url.pathname] ?? 200,
      json: fixture,
    });
  });
}

test.beforeEach(async ({ page }) => {
  await installFrozenApi(page);
});

for (const [path, heading] of [
  ["/funds", "基金研究"],
  ["/funds/000001", "Alpha 稳健基金"],
  ["/universes", "候选池快照"],
  ["/universes/UNI-001", "候选池快照"],
  ["/portfolios", "组合决策"],
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
      await expect(
        page.getByRole("listbox", { name: "资产类别", exact: true }),
      ).toContainText("EQUITY");
    } else if (path === "/funds/000001") {
      await expect(page.getByRole("tab", { name: "净值" })).toBeVisible();
      await expect(page.getByText(/调整规则：\s*adj-v2/)).toBeVisible();
      await page.getByText("可见分类历史", { exact: true }).click();
      await expect(
        page.getByRole("heading", { name: "修订 12 / v1", exact: true }),
      ).toBeVisible();
      await expect(page.getByLabel("资产类别证据")).toContainText(
        "招募书第3页",
      );
    } else if (path === "/universes") {
      await expect(
        page.getByRole("link", { name: "查看快照 UNI-001" }),
      ).toBeVisible();
    } else if (path === "/universes/UNI-001") {
      await expect(
        page.getByRole("heading", { name: "已排除（1）" }),
      ).toBeVisible();
      await expect(page.getByText("REJECTED")).toBeVisible();
    } else if (path === "/portfolios") {
      await expect(page.getByRole("link", { name: "稳健组合" })).toBeVisible();
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

test("backtest create, validate, run and inspect INVALID result with bias evidence", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") {
      mutations.push(new URL(request.url()).pathname);
    }
  });
  await page.goto("/backtests");
  for (const [label, value] of [
    ["策略 ID", "STRATEGY-1"],
    ["开始日期", "2020-01-01"],
    ["结束日期", "2026-06-30"],
    ["基准 ID", "CSI300"],
    ["再平衡政策版本", "rebalance-v3"],
    ["组合规则版本", "portfolio-v4"],
    ["收益估计版本", "return-v5"],
    ["风险模型版本", "risk-v7"],
    ["资格规则版本", "eligibility-v4"],
    ["交易成本模型版本", "cost-v2"],
  ]) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByRole("button", { name: "创建回测" }).click();
  await expect(page.getByText("已创建回测 BT-001，尚未执行。")).toBeVisible();
  await expect(page.getByRole("button", { name: "启动回测" })).toBeDisabled();
  await page.getByRole("button", { name: "校验配置" }).click();
  await expect(
    page.getByText("通过，但有警告（PASS_WITH_WARNINGS）"),
  ).toBeVisible();
  await page.getByRole("button", { name: "启动回测" }).click();
  await expect(
    page.getByText("执行已完成，但验证结果为 INVALID。"),
  ).toBeVisible();
  await expect(page.getByText(/BIAS_CHECK_INCOMPLETE/)).toBeVisible();
  await expect(
    page.getByRole("region", { name: "偏差检查" }).getByText("NOT_VERIFIED"),
  ).toBeVisible();
  expect(mutations).toEqual([
    "/api/v1/backtests",
    "/api/v1/backtests/BT-001/validate-configuration",
    "/api/v1/backtests/BT-001/runs",
  ]);
});

test("backtest creation keeps API validation errors visible", async ({
  page,
}) => {
  await installFrozenApi(page, {
    "/api/v1/backtests": {
      status: 422,
      body: errorEnvelope("INVALID_CONFIGURATION"),
    },
  });
  await page.goto("/backtests");
  for (const [label, value] of [
    ["策略 ID", "STRATEGY-1"],
    ["开始日期", "2020-01-01"],
    ["结束日期", "2026-06-30"],
    ["基准 ID", "CSI300"],
    ["再平衡政策版本", "rebalance-v3"],
    ["组合规则版本", "portfolio-v4"],
    ["收益估计版本", "return-v5"],
    ["风险模型版本", "risk-v7"],
    ["资格规则版本", "eligibility-v4"],
    ["交易成本模型版本", "cost-v2"],
  ]) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByRole("button", { name: "创建回测" }).click();
  await expect(
    page.getByText("HTTP 422 · INVALID_CONFIGURATION"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "启动回测" })).toBeDisabled();
});
