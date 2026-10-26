import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, it } from "vitest";
import { ClassificationReviewPage } from "../../pages/ClassificationReviewPage";
import { classificationCatalog } from "../../test/classificationFixtures";
let allowed = true;
let posts = 0;
let reads = 0;
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
const server = setupServer(
  http.get("/api/v1/session", () =>
    HttpResponse.json({
      data: { capabilities: { can_review_classifications: allowed } },
      meta: {},
      error: null,
    }),
  ),
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json(classificationCatalog),
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
    return HttpResponse.json({ data: item, meta: {}, error: null });
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
});
const show = () =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/classification-reviews?case=1"]}>
        <ClassificationReviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
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
