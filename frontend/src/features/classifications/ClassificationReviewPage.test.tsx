import { QueryClient } from "@tanstack/react-query";
import { screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, it, vi } from "vitest";
import { ClassificationReviewPage } from "../../pages/ClassificationReviewPage";
import { classificationCatalog } from "../../test/classificationFixtures";
import { renderWorkbench } from "../../test/render";
let allowed = true;
let posts = 0;
let reads = 0;
let submitted: Record<string, unknown> | null = null;
const v3Evidence = {
  source: "AGGREGATOR",
  confidence: "PUBLIC_AGGREGATOR",
  rule_id: "STR001",
  classified_at: "2026-10-01T00:00:00Z",
  raw_field: "strategy",
  raw_value: "增强指数型",
};
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
const v3Snapshot = {
  rule_version: "3.0.0",
  enum_version: "3.0.0",
  asset_class: {
    status: "CONFIRMED",
    value: "EQUITY",
    candidates: [],
    evidence: [{ ...v3Evidence, raw_field: "asset_class" }],
  },
  strategy: {
    status: "CONFLICT",
    value: "UNKNOWN",
    candidates: ["PASSIVE_INDEX", "ENHANCED_INDEX"],
    evidence: [
      { ...v3Evidence, raw_value: "被动指数型", rule_id: "STR002" },
      { ...v3Evidence, raw_value: "增强指数型", rule_id: "STR001" },
    ],
  },
  geography: {
    status: "UNKNOWN",
    value: "UNKNOWN",
    evaluation_state: "PAUSED",
    evidence: [],
  },
  product_structure: {
    status: "UNKNOWN",
    value: "UNKNOWN",
    evaluation_state: "PAUSED",
    evidence: [],
  },
  market_attributes: {
    status: "UNKNOWN",
    value: "UNKNOWN",
    evaluation_state: "PAUSED",
    evidence: [],
  },
  strategy_tags: ["QUANTITATIVE"],
  strategy_tag_results: {
    QUANTITATIVE: {
      status: "CONFIRMED",
      value: "QUANTITATIVE",
      evaluation_state: "EVALUATED",
      evidence: [{ ...v3Evidence, raw_field: "strategy" }],
    },
  },
};
const item = {
  case_id: 1,
  fund_id: 7,
  expected_revision: 12,
  issue_type: "CONFLICT",
  status: "PENDING",
  details: {
    asset_class: {
      candidates: ["EQUITY"],
      evidence: [{ raw_value: "正式股票型" }],
    },
  },
  created_at: "2026-01-01",
  resolved_at: null,
  result_revision_id: null,
};
let reviewItem: Record<string, unknown> = item;
const server = setupServer(
  http.get("/api/v1/session", () =>
    HttpResponse.json({
      data: { capabilities: { can_review_classifications: allowed } },
      meta: {},
      error: null,
    }),
  ),
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json({
      ...classificationCatalog,
      data: {
        ...classificationCatalog.data,
        rule_version: "3.0.0",
        enum_version: "3.0.0",
        active_dimensions: ["asset_class", "strategy"],
        paused_dimensions: [
          "geography",
          "product_structure",
          "market_attributes",
        ],
        strategy_tags: ["QUANTITATIVE"],
        dimensions: {
          ...classificationCatalog.data.dimensions,
          asset_class: ["EQUITY", "BOND", "UNKNOWN"],
          strategy: ["ACTIVE", "PASSIVE_INDEX", "ENHANCED_INDEX", "UNKNOWN"],
        },
      },
    }),
  ),
  http.get("/api/v1/classification-reviews", () =>
    HttpResponse.json({
      data: [item],
      meta: { pagination: { page: 1, total_pages: 2 } },
      error: null,
    }),
  ),
  http.get("/api/v1/classification-reviews/1", () => {
    reads++;
    return HttpResponse.json({ data: reviewItem, meta: {}, error: null });
  }),
  http.post("/api/v1/classification-reviews/1/review", () => {
    posts++;
    return HttpResponse.json(
      {
        data: null,
        meta: {},
        error: { code: "CONFLICT", message: "stale revision", details: {} },
      },
      { status: 409 },
    );
  }),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => {
  cleanup();
  server.resetHandlers();
  allowed = true;
  posts = 0;
  reads = 0;
  submitted = null;
  reviewItem = item;
});
const show = () =>
  renderWorkbench(<ClassificationReviewPage />, {
    route: "/classification-reviews?case=1",
    queryClient: new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    }),
  });
it("hides mutation controls without capability", async () => {
  allowed = false;
  show();
  await screen.findByText("复核 #1 · 基线 12");
  await screen.findByText("当前会话无分类复核权限，或案件已结束。");
  expect(screen.queryByRole("button", { name: "提交复核" })).toBeNull();
  expect(posts).toBe(0);
});
it("requires evidence and reloads a stale baseline without automatic resubmission", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByRole("form", { name: "分类复核" });
  await user.selectOptions(screen.getByLabelText("决定值"), "EQUITY");
  await user.click(screen.getByRole("button", { name: "提交复核" }));
  expect(posts).toBe(0);
  await user.type(screen.getByLabelText("复核理由"), "核对正式文件");
  await user.type(screen.getByLabelText("证据原文"), "股票型");
  await user.type(screen.getByLabelText("资料定位"), "招募书第3页");
  await user.click(screen.getByRole("button", { name: "提交复核" }));
  await screen.findByText("基线已变化，已重新加载。请重新比较证据后提交。");
  await waitFor(() => expect(reads).toBe(2));
  expect(posts).toBe(1);
  expect(screen.getByLabelText("复核理由")).toHaveValue("");
});

it("reviews v1 to v3 with both active decisions, changed tag, version acceptance, and no paused controls", async () => {
  const user = userEvent.setup();
  reviewItem = {
    ...item,
    active_scope: ["asset_class", "strategy"],
    historical_scope: ["geography", "product_structure", "market_attributes"],
    evaluation_state: "EVALUATED",
    baseline: {
      ...v3Snapshot,
      rule_version: "1.0.0",
      enum_version: "1.0.0",
      strategy: {
        status: "CONFIRMED",
        value: "QUANTITATIVE",
        candidates: [],
        evidence: [],
      },
      strategy_tags: undefined,
      strategy_tag_results: undefined,
    },
    incoming: v3Snapshot,
  };
  server.use(
    http.post(
      "/api/v1/classification-reviews/1/review",
      async ({ request }) => {
        posts++;
        submitted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          data: { revision_id: 13, version: 2, case_id: 1 },
          meta: {},
          error: null,
        });
      },
    ),
  );
  show();
  await screen.findByText("新到资料（规则 3.0.0 · 枚举 3.0.0）");
  expect(screen.getByText("当前基线（规则 1.0.0 · 枚举 1.0.0）")).toBeVisible();
  expect(screen.getByText("被动指数型")).toBeVisible();
  expect(screen.getAllByText("增强指数型").length).toBeGreaterThan(0);
  expect(screen.queryByLabelText("投资地域决定值")).toBeNull();

  await user.selectOptions(screen.getByLabelText("资产类别决定值"), "EQUITY");
  await user.selectOptions(
    screen.getByLabelText("投资策略决定值"),
    "ENHANCED_INDEX",
  );
  await user.selectOptions(
    screen.getByLabelText("QUANTITATIVE 标签决定"),
    "CONFIRM",
  );
  await user.click(screen.getByLabelText(/接受规则与枚举版本/));
  await user.type(
    screen.getByLabelText("复核理由"),
    "接受规则升级并确认两个活跃维度",
  );
  await user.type(
    screen.getByLabelText("证据原文"),
    "基金使用增强指数策略和量化模型",
  );
  await user.type(screen.getByLabelText("资料定位"), "产品资料第3页");
  await user.click(screen.getByRole("button", { name: "提交复核" }));

  await screen.findByText("复核已保存，请选择下一条待复核记录。");
  expect(submitted).toMatchObject({
    accept_incoming_version: "3.0.0",
    decisions: {
      asset_class: { value: "EQUITY" },
      strategy: { value: "ENHANCED_INDEX" },
    },
    tag_decisions: { QUANTITATIVE: { action: "CONFIRM" } },
  });
});
