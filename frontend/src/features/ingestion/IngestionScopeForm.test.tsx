import { QueryClient } from "@tanstack/react-query";
import {
  cleanup,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { DataIngestionPage } from "../../pages/DataIngestionPage";
import {
  FundBatchIngestionAction,
  FundBasicInfoRefreshButton,
} from "../funds/FundIngestionPanel";
import { renderWorkbench } from "../../test/render";
import { server } from "../../test/mswServer";
import {
  fundListEnvelope,
  sessionEnvelope,
  errorEnvelope,
} from "../../test/contractFixtures";

const envelope = (data: unknown) => ({ data, meta: {}, error: null });
const task = {
  operation_id: "ING-001",
  fund_id: "",
  fund_ids: [],
  dataset: "NAV",
  source: "AKSHARE",
  actor: "customer",
  status: "RUNNING",
  task_status: null,
  requested_count: 120,
  success_count: 48,
  failure_count: 1,
  skipped_count: 1,
  cancelled_count: 0,
  scope_type: "ALL",
  parent_operation_id: null,
  created_at: "2026-10-28T08:00:00Z",
  started_at: "2026-10-28T08:01:00Z",
  finished_at: null,
  items: [],
  failure: null,
};
const previews: unknown[] = [];
const submissions: { body: unknown; key: string | null }[] = [];
const itemRequests: URL[] = [];
let previewNumber = 0;
const handlers = () => [
  http.get("/api/v1/session", () =>
    HttpResponse.json({
      ...sessionEnvelope,
      data: {
        ...sessionEnvelope.data,
        capabilities: {
          ...sessionEnvelope.data.capabilities,
          can_manage_data_ingestion: true,
          can_manage_full_universe_ingestion: true,
        },
      },
    }),
  ),
  http.post("/api/v1/fund-ingestion-previews", async ({ request }) => {
    const body = (await request.json()) as {
      dataset: string;
      scope: { type: string };
    };
    previews.push(body);
    return HttpResponse.json(
      envelope({
        preview_id: `preview-${++previewNumber}`,
        dataset: body.dataset,
        scope_type: body.scope.type,
        fund_count: 120,
        supported_fund_count: 118,
        unavailable_mapping_count: 2,
        subject_count: 150,
        source: "AKSHARE",
        expires_at: "2099-10-28T09:00:00Z",
      }),
    );
  }),
  http.post("/api/v1/fund-ingestion-jobs", async ({ request }) => {
    submissions.push({
      body: await request.json(),
      key: request.headers.get("Idempotency-Key"),
    });
    return HttpResponse.json(
      envelope({
        operation_id: "ING-001",
        fund_id: "",
        fund_ids: [],
        dataset: "NAV",
        status: "RUNNING",
      }),
      { status: 202 },
    );
  }),
  http.get("/api/v1/fund-ingestions", () =>
    HttpResponse.json(
      envelope({ items: [], page: 1, page_size: 20, total: 0 }),
    ),
  ),
  http.get("/api/v1/ingestions/:operationId", () =>
    HttpResponse.json(envelope(task)),
  ),
  http.get("/api/v1/ingestions/:operationId/items", ({ request }) => {
    const url = new URL(request.url);
    itemRequests.push(url);
    return HttpResponse.json(
      envelope({
        items: [
          {
            id: 1,
            fund_id: "000001",
            share_class_id: 7,
            symbol: "000001",
            status: "FAILED",
            attempts: 1,
            result: null,
            error: "source timeout",
            started_at: null,
            finished_at: null,
          },
        ],
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: 20,
        total: 21,
      }),
    );
  }),
];
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  previews.length = 0;
  submissions.length = 0;
  itemRequests.length = 0;
  previewNumber = 0;
});
afterAll(() => server.close());
const renderPage = (
  route = "/data-ingestion?fund_id=000001&dataset=BASIC_INFO",
  client?: QueryClient,
  overrides: ReturnType<typeof http.get>[] = [],
) => {
  server.use(...handlers());
  server.use(...overrides);
  return renderWorkbench(<DataIngestionPage />, { route, queryClient: client });
};

describe("fund data center", () => {
  it("previews one fund and re-previews when dataset changes, submitting only the snapshot and key", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("缺少来源映射：2 只")).toBeVisible();
    expect(previews[0]).toEqual({
      dataset: "BASIC_INFO",
      scope: { type: "SINGLE", fund_id: "000001" },
    });
    await user.selectOptions(screen.getByLabelText("数据集"), "NAV");
    await waitFor(() => expect(previews).toHaveLength(2));
    expect(previews[1]).toEqual({
      dataset: "NAV",
      scope: { type: "SINGLE", fund_id: "000001" },
    });
    await user.click(await screen.findByRole("button", { name: "提交抓取" }));
    await waitFor(() => expect(submissions).toHaveLength(1));
    expect(submissions[0].body).toEqual({ preview_id: "preview-2" });
    expect(submissions[0].key).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "任务 ING-001" }),
    ).toBeVisible();
  });
  it("confirms ALL as a platform snapshot and allows keyboard cancellation without submission", async () => {
    const user = userEvent.setup();
    renderPage("/data-ingestion?scope_type=ALL&dataset=NAV");
    await screen.findByText("缺少来源映射：2 只");
    expect(previews[0]).toEqual({ dataset: "NAV", scope: { type: "ALL" } });
    await user.click(screen.getByRole("button", { name: "提交抓取" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("平台基金库");
    expect(dialog).toHaveTextContent("完整历史");
    expect(dialog).toHaveTextContent("不可抓取 2");
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(submissions).toHaveLength(0);
  });
  it("deduplicates selected IDs and requires 2–100 funds", async () => {
    const user = userEvent.setup();
    renderPage(
      "/data-ingestion?scope_type=SELECTED&fund_ids=000001,000001,000002",
    );
    await screen.findByText("缺少来源映射：2 只");
    expect(previews[0]).toEqual({
      dataset: "BASIC_INFO",
      scope: { type: "SELECTED", fund_ids: ["000001", "000002"] },
    });
    await user.click(screen.getByRole("button", { name: "移除基金 000002" }));
    expect(
      screen.getByText("多只范围需要选择 2–100 只不同基金。"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "提交抓取" }),
    ).not.toBeInTheDocument();
  });
  it("retains selection across search pages and caps it at 100", async () => {
    const user = userEvent.setup();
    renderPage(
      "/data-ingestion?scope_type=SELECTED&fund_ids=" +
        Array.from({ length: 100 }, (_, i) =>
          String(i + 1).padStart(6, "0"),
        ).join(","),
    );
    await screen.findByText("缺少来源映射：2 只");
    expect(screen.getByText("已选 100 / 100 只基金")).toBeVisible();
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json({
          ...fundListEnvelope,
          data: [
            {
              ...fundListEnvelope.data[0],
              fund_id: "999999",
              fund_name: "Other",
            },
          ],
        }),
      ),
    );
    await user.type(screen.getByLabelText("搜索基金名称或代码"), "Other");
    await user.click(screen.getByRole("button", { name: "搜索基金" }));
    expect(
      await screen.findByRole("checkbox", { name: "选择 Other（999999）" }),
    ).toBeDisabled();
  });
  it("does not expose privileged controls during loading, error, or denied sessions", async () => {
    renderPage(undefined, undefined, [
      http.get("/api/v1/session", async () => {
        await delay(50);
        return HttpResponse.json(errorEnvelope("SESSION_UNAVAILABLE"), {
          status: 503,
        });
      }),
    ]);
    expect(screen.queryByLabelText("数据集")).not.toBeInTheDocument();
    expect(
      await screen.findByText("Contract fixture for SESSION_UNAVAILABLE"),
    ).toBeVisible();
    expect(screen.queryByLabelText("数据集")).not.toBeInTheDocument();
    cleanup();
    renderPage(undefined, undefined, [
      http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
    ]);
    expect(
      await screen.findByRole("heading", { name: "403 · 无数据抓取权限" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "返回工作台" })).toHaveAttribute(
      "href",
      "/home",
    );
  });
  it("requires full-universe capability before previewing ALL", async () => {
    renderPage("/data-ingestion?scope_type=ALL", undefined, [
      http.get("/api/v1/session", () =>
        HttpResponse.json({
          ...sessionEnvelope,
          data: {
            ...sessionEnvelope.data,
            capabilities: {
              ...sessionEnvelope.data.capabilities,
              can_manage_data_ingestion: true,
              can_manage_full_universe_ingestion: false,
            },
          },
        }),
      ),
    ]);
    expect(await screen.findByText("当前身份没有全量抓取权限。")).toBeVisible();
    expect(previews).toHaveLength(0);
  });
  it("invalidates an expired preview after a 409 and requires another preview", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("缺少来源映射：2 只");
    server.use(
      http.post("/api/v1/fund-ingestion-jobs", () =>
        HttpResponse.json(errorEnvelope("PREVIEW_EXPIRED"), { status: 409 }),
      ),
    );
    await user.click(screen.getByRole("button", { name: "提交抓取" }));
    expect(
      await screen.findByText("预览已过期或范围发生变化，请重新预览后提交。"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "提交抓取" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新预览" }));
    await waitFor(() => expect(previews).toHaveLength(2));
  });
  it("resumes a long task URL with actual item counts and paginated results without submitting", async () => {
    const user = userEvent.setup();
    renderPage("/data-ingestion?operation_id=ING-001");
    expect(await screen.findByText("已处理 50 / 120 项")).toBeVisible();
    expect(
      screen.getByText("成功 48 · 失败 1 · 跳过 1 · 取消 0"),
    ).toBeVisible();
    expect(await screen.findByText("source timeout")).toBeVisible();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "结果下一页" }));
    await waitFor(() =>
      expect(itemRequests.at(-1)?.searchParams.get("page")).toBe("2"),
    );
    expect(submissions).toHaveLength(0);
    expect(previews).toHaveLength(0);
  });
  it("cancels unfinished work and retries failed items into a linked operation", async () => {
    const user = userEvent.setup();
    let cancelled = false;
    let retried = false;
    renderPage("/data-ingestion?operation_id=ING-001");
    server.use(
      http.post("/api/v1/ingestions/ING-001/cancel", () => {
        cancelled = true;
        return HttpResponse.json(envelope({ ...task, status: "CANCELLED" }), {
          status: 202,
        });
      }),
      http.post("/api/v1/ingestions/ING-001/retry-failed", () => {
        retried = true;
        return HttpResponse.json(
          envelope({
            operation_id: "ING-002",
            fund_id: "",
            fund_ids: [],
            dataset: "NAV",
            status: "RUNNING",
          }),
          { status: 202 },
        );
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "取消未完成项" }),
    );
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "确认取消",
      }),
    );
    await waitFor(() => expect(cancelled).toBe(true));
    server.use(
      http.get("/api/v1/ingestions/:operationId", () =>
        HttpResponse.json(
          envelope({
            ...task,
            status: "COMPLETED",
            task_status: "PARTIAL_SUCCESS",
          }),
        ),
      ),
    );
    await user.click(screen.getByRole("button", { name: "刷新任务" }));
    await user.click(
      await screen.findByRole("button", { name: "仅重试失败项" }),
    );
    await waitFor(() => expect(retried).toBe(true));
    expect(submissions).toHaveLength(0);
  });
  it("refreshes actual fund detail, NAV, basic info, and research caches after terminal state", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    for (const key of [
      ["api", "funds", "000001", { as_of_date: "2026-10-27" }],
      ["api", "funds", "000001", "nav-series", {}],
      ["api", "funds", "000001", "basic-info-history", undefined],
      ["fund-research", {}],
      ["fund-detail", "000001", "2026-10-27"],
      ["fund-nav", "000001", "2026-10-27"],
      ["fund-evaluation", "000001", "2026-10-27"],
      ["fund-score", "000001", "2026-10-27"],
    ])
      client.setQueryData(key, {});
    renderPage("/data-ingestion?operation_id=ING-001", client);
    server.use(
      http.get("/api/v1/ingestions/:operationId", () =>
        HttpResponse.json(
          envelope({
            ...task,
            status: "COMPLETED",
            task_status: "PARTIAL_SUCCESS",
          }),
        ),
      ),
    );
    await screen.findByText("部分成功");
    await waitFor(() =>
      expect(
        client.getQueryState(["api", "funds", "000001", "nav-series", {}])
          ?.isInvalidated,
      ).toBe(true),
    );
    expect(client.getQueryState(["fund-research", {}])?.isInvalidated).toBe(
      true,
    );
    for (const prefix of [
      "fund-detail",
      "fund-nav",
      "fund-evaluation",
      "fund-score",
    ])
      expect(
        client.getQueryState([prefix, "000001", "2026-10-27"])?.isInvalidated,
      ).toBe(true);
    expect(
      client.getQueryState([
        "api",
        "funds",
        "000001",
        { as_of_date: "2026-10-27" },
      ])?.isInvalidated,
    ).toBe(true);
  });
  it("routes legacy shortcuts to the center instead of submitting", async () => {
    renderWorkbench(
      <>
        <FundBasicInfoRefreshButton fundId="000001" canManage />
        <FundBatchIngestionAction fundIds={["000001", "000002"]} canManage />
      </>,
    );
    expect(
      screen.getByRole("link", { name: "在数据中心抓取基本信息" }),
    ).toHaveAttribute(
      "href",
      "/data-ingestion?fund_id=000001&dataset=BASIC_INFO",
    );
    expect(
      screen.getByRole("link", { name: "将所选基金加入数据抓取" }),
    ).toHaveAttribute(
      "href",
      "/data-ingestion?scope_type=SELECTED&fund_ids=000001%2C000002&dataset=BASIC_INFO",
    );
  });
  it("shows the preview source in the page context", async () => {
    renderPage();
    expect(await screen.findByText(/数据源：AKSHARE/)).toBeVisible();
  });
  it("searches an exact fund code using its detail endpoint", async () => {
    const user = userEvent.setup();
    renderPage("/data-ingestion", undefined, [
      http.get("/api/v1/funds", () =>
        HttpResponse.json({ ...fundListEnvelope, data: [] }),
      ),
    ]);
    await screen.findByLabelText("数据集");
    await user.type(screen.getByLabelText("搜索基金名称或代码"), "000001");
    await user.click(screen.getByRole("button", { name: "搜索基金" }));
    await user.click(
      await screen.findByRole("checkbox", {
        name: "选择 Alpha 稳健基金（000001）",
      }),
    );
    await waitFor(() =>
      expect(previews).toContainEqual({
        dataset: "BASIC_INFO",
        scope: { type: "SINGLE", fund_id: "000001" },
      }),
    );
  });
  it("retains selected funds when moving to the next search page", async () => {
    const user = userEvent.setup();
    renderPage("/data-ingestion?scope_type=SELECTED");
    server.use(
      http.get("/api/v1/funds", ({ request }) => {
        const second = new URL(request.url).searchParams.get("page") === "2";
        return HttpResponse.json({
          ...fundListEnvelope,
          data: [
            {
              ...fundListEnvelope.data[0],
              fund_id: second ? "000002" : "000001",
              fund_name: second ? "Beta" : "Alpha",
            },
          ],
          meta: {
            ...fundListEnvelope.meta,
            pagination: {
              page: second ? 2 : 1,
              page_size: 20,
              total_pages: 2,
              total_items: 21,
            },
          },
        });
      }),
    );
    await screen.findByLabelText("数据集");
    await user.click(screen.getByRole("button", { name: "搜索基金" }));
    await user.click(
      await screen.findByRole("checkbox", { name: "选择 Alpha（000001）" }),
    );
    await user.click(screen.getByRole("button", { name: "搜索下一页" }));
    await user.click(
      await screen.findByRole("checkbox", { name: "选择 Beta（000002）" }),
    );
    expect(
      screen.getByRole("button", { name: "移除基金 000001" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(previews).toContainEqual({
        dataset: "BASIC_INFO",
        scope: { type: "SELECTED", fund_ids: ["000001", "000002"] },
      }),
    );
    await user.click(await screen.findByRole("button", { name: "提交抓取" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "确认提交",
      }),
    );
    await waitFor(() => expect(submissions).toHaveLength(1));
  });
  it("re-previews ALL when existing fund filters change", async () => {
    const user = userEvent.setup();
    renderPage("/data-ingestion?scope_type=ALL");
    await screen.findByText("缺少来源映射：2 只");
    await user.selectOptions(screen.getByLabelText("全量范围条件"), "FILTERED");
    await user.type(screen.getByLabelText("范围筛选 · 基金名称"), "Alpha");
    await waitFor(() =>
      expect(previews.at(-1)).toEqual({
        dataset: "BASIC_INFO",
        scope: { type: "ALL", filters: { fund_name: "Alpha" } },
      }),
    );
  });
  it("disables locally expired snapshots without submitting", async () => {
    renderPage(undefined, undefined, [
      http.post("/api/v1/fund-ingestion-previews", () =>
        HttpResponse.json(
          envelope({
            preview_id: "expired",
            dataset: "BASIC_INFO",
            scope_type: "SINGLE",
            fund_count: 1,
            supported_fund_count: 1,
            unavailable_mapping_count: 0,
            subject_count: 1,
            source: "AKSHARE",
            expires_at: "2000-01-01T00:00:00Z",
          }),
        ),
      ),
    ]);
    expect(await screen.findByText("快照已过期，请重新预览。")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "提交抓取" }),
    ).not.toBeInTheDocument();
    expect(submissions).toHaveLength(0);
  });
  it("filters history on the server and preserves filters when paginating", async () => {
    const user = userEvent.setup();
    const requests: URL[] = [];
    renderPage("/data-ingestion", undefined, [
      http.get("/api/v1/fund-ingestions", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        return HttpResponse.json(
          envelope({
            items: [task],
            page: Number(url.searchParams.get("page") ?? 1),
            page_size: 20,
            total: 21,
          }),
        );
      }),
    ]);
    await screen.findByLabelText("历史数据集");
    await user.selectOptions(screen.getByLabelText("历史数据集"), "NAV");
    await user.selectOptions(screen.getByLabelText("历史状态"), "RUNNING");
    await user.selectOptions(screen.getByLabelText("历史范围"), "ALL");
    fireEvent.change(screen.getByLabelText("提交日期从"), {
      target: { value: "2026-10-28" },
    });
    fireEvent.change(screen.getByLabelText("提交日期至"), {
      target: { value: "2026-10-27" },
    });
    expect(screen.getByRole("button", { name: "应用时间筛选" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("提交日期至"), {
      target: { value: "2026-10-29" },
    });
    await user.click(screen.getByRole("button", { name: "应用时间筛选" }));
    await waitFor(() =>
      expect(requests.at(-1)?.searchParams.get("created_from")).toBeTruthy(),
    );
    await user.click(await screen.findByRole("button", { name: "历史下一页" }));
    await waitFor(() =>
      expect(requests.at(-1)?.searchParams.get("page")).toBe("2"),
    );
    expect(requests.at(-1)?.searchParams.get("dataset")).toBe("NAV");
    expect(requests.at(-1)?.searchParams.get("scope_type")).toBe("ALL");
    expect(requests.at(-1)?.searchParams.get("status")).toBe("RUNNING");
    expect(requests.at(-1)?.searchParams.get("created_to")).toBeTruthy();
  });
  it("reuses the idempotency key when the first submission response fails", async () => {
    const user = userEvent.setup();
    const attempts: { key: string | null; body: unknown }[] = [];
    renderPage(undefined, undefined, [
      http.post("/api/v1/fund-ingestion-jobs", async ({ request }) => {
        attempts.push({
          key: request.headers.get("Idempotency-Key"),
          body: await request.json(),
        });
        return attempts.length === 1
          ? HttpResponse.json(errorEnvelope("LOST_RESPONSE"), { status: 503 })
          : HttpResponse.json(
              envelope({
                operation_id: "ING-001",
                fund_id: "000001",
                fund_ids: ["000001"],
                dataset: "BASIC_INFO",
                status: "RUNNING",
              }),
              { status: 202 },
            );
      }),
    ]);
    await screen.findByText("缺少来源映射：2 只");
    await user.click(screen.getByRole("button", { name: "提交抓取" }));
    await screen.findByText("Contract fixture for LOST_RESPONSE");
    await user.click(screen.getByRole("button", { name: "提交抓取" }));
    await screen.findByRole("heading", { name: "任务 ING-001" });
    expect(attempts).toHaveLength(2);
    expect(attempts[0].key).toBeTruthy();
    expect(attempts[1]).toEqual(attempts[0]);
  });
  it("explains denied operation access without submitting or reading its items", async () => {
    renderPage("/data-ingestion?operation_id=foreign", undefined, [
      http.get("/api/v1/ingestions/foreign", () =>
        HttpResponse.json(errorEnvelope("FORBIDDEN"), { status: 403 }),
      ),
    ]);
    expect(
      await screen.findByText("Contract fixture for FORBIDDEN"),
    ).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("403");
    expect(
      screen.queryByRole("button", { name: "取消未完成项" }),
    ).not.toBeInTheDocument();
    expect(itemRequests).toHaveLength(0);
    expect(submissions).toHaveLength(0);
  });
});
