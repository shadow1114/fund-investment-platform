import { test, expect } from "@playwright/test";
import { classificationCatalog } from "../src/test/classificationFixtures";
import {
  fundListEnvelope,
  fundDetailEnvelope,
  fundNavEnvelope,
  fundEvaluationEnvelope,
  fundScoreEnvelope,
} from "../src/test/contractFixtures";
test("offline classification review preserves historical visibility", async ({
  page,
}) => {
  let reviewed = false;
  const bodies: unknown[] = [];
  const result = {
    status: "CANDIDATE",
    value: "UNKNOWN",
    candidates: ["EQUITY"],
    evidence: [
      {
        source: "NAME",
        rule_id: "name",
        confidence: "NAME_HINT",
        classified_at: "2026-01-01T00:00:00Z",
        raw_field: "name",
        raw_value: "股票",
        locator: "名称",
      },
    ],
  };
  const classification = {
    scheme: "FIP_CLASSIFICATION_V1",
    rule_version: "1.0.0",
    enum_version: "1.0.0",
    revision_id: 12,
    version: 1,
    source_summary: ["NAME"],
    available_at: "2026-01-01",
    valid_from: "2026-01-01",
    asset_class: result,
    strategy: result,
    geography: result,
    product_structure: result,
    market_attributes: result,
  };
  const review = {
    case_id: 1,
    fund_id: 7,
    expected_revision: 12,
    issue_type: "CANDIDATE",
    status: "PENDING",
    details: {},
    baseline: classification,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    let body: unknown;
    if (url.pathname.endsWith("/session"))
      body = {
        data: { capabilities: { can_review_classifications: true } },
        meta: {},
        error: null,
      };
    else if (url.pathname.endsWith("/catalog")) body = classificationCatalog;
    else if (url.pathname.endsWith("/review")) {
      bodies.push(route.request().postDataJSON());
      reviewed = true;
      body = {
        data: { revision_id: 13, version: 2, case_id: 1 },
        meta: {},
        error: null,
      };
    } else if (url.pathname.endsWith("/classification-reviews/1"))
      body = {
        data: { ...review, status: reviewed ? "RESOLVED" : "PENDING" },
        meta: {},
        error: null,
      };
    else if (url.pathname.endsWith("/classification-reviews"))
      body = {
        data: reviewed ? [] : [review],
        meta: { pagination: { page: 1, total_pages: 1 } },
        error: null,
      };
    else if (url.pathname.endsWith("/classification-history"))
      body = {
        data: [
          { revision_id: 12, version: 1, intervals: [{ classification }] },
        ],
        meta: {},
        error: null,
      };
    else if (url.pathname.endsWith("/nav-series")) body = fundNavEnvelope;
    else if (url.pathname.endsWith("/evaluations"))
      body = fundEvaluationEnvelope;
    else if (url.pathname.endsWith("/scores")) body = fundScoreEnvelope;
    else if (url.pathname.endsWith("/funds"))
      body = {
        ...fundListEnvelope,
        data: fundListEnvelope.data.map((f) => ({
          ...f,
          classification: {
            ...classification,
            asset_class: reviewed
              ? { ...result, status: "CONFIRMED", value: "EQUITY" }
              : result,
          },
        })),
      };
    else
      body = {
        ...fundDetailEnvelope,
        data: { ...fundDetailEnvelope.data, classification },
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/funds");
  await page
    .getByRole("listbox", { name: "资产类别" })
    .selectOption(["EQUITY"]);
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/asset_class=EQUITY/);
  await page
    .getByRole("link", { name: fundListEnvelope.data[0].fund_name })
    .click();
  await expect(page.getByLabel("资产类别证据")).toContainText("NAME_HINT");
  await page.getByText("可见分类历史", { exact: true }).click();
  await page.getByText("历史原始记录", { exact: true }).click();
  await expect(page.locator("pre")).toContainText('"revision_id": 12');
  await page.getByRole("link", { name: "分类待复核", exact: true }).click();
  await page.getByRole("button", { name: /基金 7/ }).click();
  await page.getByLabel("决定值").selectOption("EQUITY");
  await page.getByLabel("复核理由").fill("核实正式文件");
  await page.getByLabel("证据原文").fill("股票型");
  await page.getByLabel("资料定位").fill("招募书3页");
  await page.getByRole("button", { name: "提交复核" }).click();
  await expect(page.getByRole("status")).toContainText("复核已保存");
  expect(bodies).toHaveLength(1);
  await page.goto("/funds");
  await expect(page.getByLabel("五维分类").first()).toContainText(
    "CONFIRMED · 最终值 EQUITY",
  );
  await page.goto(
    `/funds/${fundListEnvelope.data[0].fund_id}?as_of_date=2026-01-01`,
  );
  await page.getByText("可见分类历史", { exact: true }).click();
  await page.getByText("历史原始记录", { exact: true }).click();
  await expect(page.locator("pre")).toContainText('"revision_id": 12');
});
