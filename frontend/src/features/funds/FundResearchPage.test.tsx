import {
  classificationCatalog,
  emptyClassificationHistory,
} from "../../test/classificationFixtures";
import { sessionEnvelope } from "../../test/contractFixtures";
import { QueryClient } from "@tanstack/react-query";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import type { ChangeEvent } from "react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { renderWorkbench } from "../../test/render";

import { FundResearchPage } from "../../pages/FundResearchPage";
import {
  createFundPageDatasource,
  FUND_PAGE_SIZES,
  type FundPageResult,
  mapGridRequestToFundParams,
} from "./FundTable";
import { emptyFundFilters } from "./FundFilters";
import {
  fundPageQueryOptions,
  invalidateIngestionFundData,
} from "../../api/queries";

vi.mock("@mantine/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@mantine/core")>();
  const NativeMultiSelect = ({
    label,
    "aria-label": ariaLabel,
    data,
    value,
    onChange,
  }: {
    label: string;
    "aria-label"?: string;
    data: { value: string; label: string }[];
    value: string[];
    onChange: (value: string[]) => void;
  }) => (
    <label>
      {label}
      <select
        aria-label={ariaLabel ?? label}
        multiple
        value={value}
        onChange={(event) =>
          onChange(
            Array.from(
              event.currentTarget.selectedOptions,
              (option) => option.value,
            ),
          )
        }
      >
        {data.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
  const NativeSelect = ({
    label,
    "aria-label": ariaLabel,
    data,
    value,
    onChange,
  }: {
    label: string;
    "aria-label"?: string;
    data: { value: string; label: string }[];
    value: string | null;
    onChange: (value: string | null) => void;
  }) => (
    <label>
      {label}
      <select
        aria-label={ariaLabel ?? label}
        value={value ?? ""}
        onChange={(event) => onChange(event.currentTarget.value || null)}
      >
        {data.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
  const NativeInput = ({
    label,
    "aria-label": ariaLabel,
    value,
    onChange,
    error,
  }: {
    label: string;
    "aria-label"?: string;
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
    error?: string;
  }) => (
    <label>
      {label}
      <input
        aria-label={ariaLabel ?? label}
        value={value}
        onChange={onChange}
      />
      {error && <span>{error}</span>}
    </label>
  );
  const NativeTagsInput = ({
    label,
    "aria-label": ariaLabel,
    value,
    onChange,
  }: {
    label: string;
    "aria-label"?: string;
    value: string[];
    onChange: (value: string[]) => void;
  }) => (
    <label>
      {label}
      <input
        aria-label={ariaLabel ?? label}
        value={value.join(",")}
        onChange={(event) =>
          onChange(event.currentTarget.value.split(",").filter(Boolean))
        }
      />
    </label>
  );
  return {
    ...actual,
    MultiSelect: NativeMultiSelect,
    Select: NativeSelect,
    TagsInput: NativeTagsInput,
    TextInput: NativeInput,
  };
});

const requests: URL[] = [];
const companyRequests: URL[] = [];

const listEnvelope = {
  data: [
    {
      fund_id: "000001",
      fund_name: "Alpha 稳健基金",
      share_class: "A",
      fund_classification: "EQUITY",
      management_company_id: "MC-1",
      inception_date: "2020-01-02",
      lifecycle_status: "NORMAL",
      investment_eligibility: "FULLY_ELIGIBLE",
      share_class_id: "101",
      fund_code: "000001",
      fund_company: "永赢基金",
      sub_status: "开放",
      manager_ids: [],
    },
  ],
  meta: {
    request_id: "REQ-LIST",
    as_of_date: "2026-09-16",
    data_version: "funds-v7",
    versions: { classification_version: "class-v3" },
    is_point_in_time: true,
    pagination: {
      page: 2,
      page_size: 10,
      total_items: 21,
      total_pages: 3,
    },
    availability_quality_distribution: { EXACT: 18, DERIVED: 2, INFERRED: 1 },
    subscription_status_source: "PLACEHOLDER",
  },
  error: null,
};

const companyOptionsEnvelope = {
  data: [{ fund_company: "永赢基金" }, { fund_company: "易方达基金" }],
  meta: {
    request_id: "REQ-COMPANIES",
    as_of_date: "2026-09-16",
    data_version: "companies-v1",
    versions: {},
    is_point_in_time: false,
    availability_quality_distribution: { EXACT: 0, DERIVED: 0, INFERRED: 0 },
  },
  error: null,
};

const server = setupServer(
  http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json(classificationCatalog),
  ),
  http.get("/api/v1/fund-management-companies", ({ request }) => {
    companyRequests.push(new URL(request.url));
    return HttpResponse.json(companyOptionsEnvelope);
  }),
  http.get("/api/v1/funds/:fundId/classification-history", () =>
    HttpResponse.json(emptyClassificationHistory),
  ),
  http.get("/api/v1/funds", ({ request }) => {
    requests.push(new URL(request.url));
    return HttpResponse.json(listEnvelope);
  }),
);

const renderPage = (initialEntry: string) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return renderWorkbench(<FundResearchPage />, {
    route: initialEntry,
    queryClient: client,
  });
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  requests.length = 0;
  companyRequests.length = 0;
  localStorage.clear();
});
afterAll(() => server.close());

describe("FundResearchPage", () => {
  it("starts at the query panel and keeps only the grid in the lower region", async () => {
    renderPage("/funds");
    const page = screen.getByTestId("fund-research-page");
    const workspace = page.querySelector(
      "section[aria-label='基金查询条件']",
    )?.parentElement;
    const results = page.querySelector("section[aria-label='基金研究结果区']");

    expect(workspace?.firstElementChild).toBe(
      page.querySelector("section[aria-label='基金查询条件']"),
    );
    expect(page.querySelector("h1")).toBeNull();
    expect(page).not.toHaveTextContent("使用当前可见数据");
    expect(page).not.toHaveTextContent("只符合条件");
    expect(results?.children).toHaveLength(1);
    expect(results?.querySelector('[role="grid"]')).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "列设置" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "表格密度" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "收起查询条件" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByRole("button", { name: "保存当前视图" })).toBeNull();
    await waitFor(() => {
      expect(requests).toHaveLength(1);
      expect(companyRequests).toHaveLength(1);
    });
  });

  it("removes query notes for placeholder status and unavailable company options", async () => {
    server.use(
      http.get("/api/v1/fund-management-companies", () =>
        HttpResponse.json(
          {
            data: null,
            meta: {},
            error: { code: "COMPANIES_UNAVAILABLE", message: "unavailable" },
          },
          { status: 503 },
        ),
      ),
    );
    renderPage("/funds");
    await screen.findByRole("grid", { name: "基金研究结果" });

    expect(screen.queryByText(/申购状态目前固定显示/)).not.toBeInTheDocument();
    expect(screen.queryByText(/管理公司列表暂不可用/)).not.toBeInTheDocument();
  });

  it("collapses and expands the query panel with one accessible chevron button", async () => {
    const user = userEvent.setup();
    renderPage("/funds");
    const queryPanel = screen.getByRole("region", { name: "基金查询条件" });

    const collapse = screen.getByRole("button", { name: "收起查询条件" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    expect(collapse.querySelector("svg")).toBeInTheDocument();
    await user.click(collapse);
    expect(queryPanel).not.toBeVisible();

    const expand = screen.getByRole("button", { name: "展开查询条件" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    expect(expand.querySelector("svg")).toBeInTheDocument();
    await user.click(expand);
    expect(queryPanel).toBeVisible();
  });

  it("refreshes the visible list and company options after ingestion completes", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    renderWorkbench(<FundResearchPage />, {
      route: "/funds",
      queryClient: client,
    });
    await waitFor(() => {
      expect(requests).toHaveLength(1);
      expect(companyRequests).toHaveLength(1);
    });

    await invalidateIngestionFundData(client);

    await waitFor(() => {
      expect(requests).toHaveLength(2);
      expect(companyRequests).toHaveLength(2);
    });
    client.clear();
  });

  it("ignores a late successful response from a retired fund datasource", async () => {
    let resolvePage!: (value: FundPageResult) => void;
    const loadPage = vi.fn(
      () => new Promise<FundPageResult>((resolve) => (resolvePage = resolve)),
    );
    const successCallback = vi.fn();
    const failCallback = vi.fn();
    const datasource = createFundPageDatasource({
      params: { page: 1, page_size: 20 },
      currentPageSize: 20,
      initialPageAppliedRef: { current: true },
      initialTargetPageRef: { current: 1 },
      pageRef: { current: { page: 1, pageSize: 20 } },
      loadPage,
    });

    const pending = datasource.getRows({
      startRow: 0,
      endRow: 20,
      sortModel: [],
      filterModel: {},
      context: undefined,
      api: { paginationGoToPage: vi.fn() } as never,
      successCallback,
      failCallback,
    });
    datasource.destroy?.();
    resolvePage({
      rows: [],
      meta: { pagination: { total_pages: 1, total_items: 0 } },
    } as unknown as FundPageResult);
    await pending;

    expect(successCallback).not.toHaveBeenCalled();
    expect(failCallback).not.toHaveBeenCalled();
  });

  it("ignores a late failure from a retired fund datasource", async () => {
    const failCallback = vi.fn();
    const datasource = createFundPageDatasource({
      params: { page: 1, page_size: 20 },
      currentPageSize: 20,
      initialPageAppliedRef: { current: true },
      initialTargetPageRef: { current: 1 },
      pageRef: { current: { page: 1, pageSize: 20 } },
      loadPage: () => Promise.reject(new Error("stale failure")),
    });

    const pending = datasource.getRows({
      startRow: 0,
      endRow: 20,
      sortModel: [],
      filterModel: {},
      context: undefined,
      api: { paginationGoToPage: vi.fn() } as never,
      successCallback: vi.fn(),
      failCallback,
    });
    datasource.destroy?.();
    await pending;

    expect(failCallback).not.toHaveBeenCalled();
  });
  it("maps an AG Grid block to a keyed server page and reads total count from metadata", async () => {
    const pageParams = mapGridRequestToFundParams(
      { fund_name: "Alpha", fund_company: "永赢基金", page: 3, page_size: 50 },
      {
        startRow: 100,
        endRow: 150,
        sortModel: [{ colId: "fund_code", sort: "desc" }],
      },
    );
    expect(pageParams).toMatchObject({
      fund_name: "Alpha",
      fund_company: "永赢基金",
      page: 3,
      page_size: 50,
      sort: "fund_code",
      order: "desc",
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const result = await client.fetchQuery(fundPageQueryOptions(pageParams));
    expect(requests).toHaveLength(1);
    expect(requests[0].searchParams.get("page")).toBe("3");
    expect(requests[0].searchParams.get("page_size")).toBe("50");
    expect(requests[0].searchParams.get("sort")).toBe("fund_code");
    expect(result.meta.pagination.total_items).toBe(21);
    expect(result.rows[0].share_class_id).toBe("101");
    for (const sort of [
      "fund_code",
      "fund_name",
      "fund_company",
      "sub_status",
    ] as const) {
      expect(
        mapGridRequestToFundParams(
          {},
          {
            startRow: 20,
            endRow: 40,
            sortModel: [{ colId: sort, sort: "asc" }],
          },
        ),
      ).toMatchObject({ page: 2, page_size: 20, sort, order: "asc" });
    }
  });
  it("keeps selection and ingestion actions hidden without permission", async () => {
    renderPage("/funds");
    await screen.findByRole("grid", { name: "基金研究结果" });
    expect(
      screen.queryByRole("checkbox", { name: /选择/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "将所选基金加入数据抓取" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "生命周期状态" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "投资资格" }),
    ).not.toBeInTheDocument();
  });

  it("does not expose a misleading select-all control for an infinite grid", async () => {
    renderPage("/funds");
    await screen.findByRole("grid", { name: "基金研究结果" });
    expect(
      screen.queryByRole("checkbox", { name: "选择本页基金" }),
    ).not.toBeInTheDocument();
  });

  it("uses only the grid page-size choices 20, 50, and 200", async () => {
    renderPage("/funds");
    await screen.findByRole("grid", { name: "基金研究结果" });
    expect(FUND_PAGE_SIZES).toEqual([20, 50, 200]);
  });
  it("passes frozen filters through unchanged without adding result decorations", async () => {
    renderPage(
      "/funds?fund_name=Alpha&fund_type=EQUITY%2CBOND&lifecycle_status=NORMAL&investment_eligibility=FULLY_ELIGIBLE&as_of_date=2026-09-16&page=2&page_size=10&sort=fund_name&order=asc",
    );

    await screen.findByRole("grid", { name: "基金研究结果" });
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    expect(
      requests.some(
        (request) =>
          request.searchParams.get("fund_name") === "Alpha" &&
          request.searchParams.get("as_of_date") === "2026-09-16" &&
          request.searchParams.get("page_size") === "20",
      ),
    ).toBe(true);
    const results = screen.getByRole("region", { name: "基金研究结果区" });
    expect(results.children).toHaveLength(1);
    expect(results).not.toHaveTextContent("点时数据");
    expect(results).not.toHaveTextContent("查看来源版本");
    expect(
      requests.some(
        (request) => request.searchParams.get("as_of_date") === "2026-09-16",
      ),
    ).toBe(true);
  });

  it("passes supported asset class and legacy dimensions through to the API", async () => {
    renderPage(
      "/funds?asset_class=EQUITY&geography=CN&product_structure=ETF&market_attributes=QDII",
    );
    await screen.findByRole("grid", { name: "基金研究结果" });
    const request = requests.find(
      (item) => item.searchParams.get("asset_class") === "EQUITY",
    );
    expect(request).toBeDefined();
    expect(request?.searchParams.get("geography")).toBe("CN");
    expect(request?.searchParams.get("product_structure")).toBe("ETF");
    expect(request?.searchParams.get("market_attributes")).toBe("QDII");
  });

  it("uses server pagination metadata and preserves filters on the next page", async () => {
    renderPage("/funds?fund_name=Alpha&page=2&page_size=10");
    await screen.findByRole("grid", { name: "基金研究结果" });
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    expect(FUND_PAGE_SIZES).toContain(20);
    expect(
      mapGridRequestToFundParams(
        { fund_name: "Alpha", page: 2, page_size: 20 },
        { startRow: 40, endRow: 60, sortModel: [] },
      ),
    ).toMatchObject({ page: 3, fund_name: "Alpha", page_size: 20 });
  });

  it("applies the asset class filter while retaining old URL compatibility fields", async () => {
    const user = userEvent.setup();
    renderPage(
      "/funds?geography=CN&product_structure=ETF&market_attributes=QDII",
    );
    await screen.findByRole("grid", { name: "基金研究结果" });
    const category = screen.getByRole("combobox", { name: "基金类别" });
    await user.selectOptions(category, "EQUITY");
    await user.click(screen.getByRole("button", { name: "查询基金" }));
    await waitFor(() =>
      expect(
        requests.some(
          (request) => request.searchParams.get("asset_class") === "EQUITY",
        ),
      ).toBe(true),
    );
    expect(requests.at(-1)?.searchParams.get("geography")).toBe("CN");
    expect(requests.at(-1)?.searchParams.get("product_structure")).toBe("ETF");
    expect(requests.at(-1)?.searchParams.get("market_attributes")).toBe("QDII");
  });

  it("keeps empty and API error responses within the grid region", async () => {
    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json({
          data: [],
          meta: {
            ...listEnvelope.meta,
            pagination: {
              page: 1,
              page_size: 20,
              total_items: 0,
              total_pages: 0,
            },
          },
          error: null,
        }),
      ),
    );
    const first = renderPage("/funds");
    expect(
      await screen.findByRole("grid", { name: "基金研究结果" }),
    ).toBeVisible();
    first.unmount();

    server.use(
      http.get("/api/v1/funds", () =>
        HttpResponse.json(
          {
            data: null,
            meta: {},
            error: {
              code: "FUNDS_UNAVAILABLE",
              message: "Fund service unavailable",
              details: {},
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderPage("/funds");
    expect(
      await screen.findByRole("grid", { name: "基金研究结果" }),
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "基金研究结果区" }).children,
    ).toHaveLength(1);
  });

  it("loads company options independently from current research filters", async () => {
    renderPage("/funds?fund_name=Alpha&asset_class=EQUITY&page=3&page_size=50");

    await screen.findByRole("grid", { name: "基金研究结果" });
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    await waitFor(() => expect(companyRequests).toHaveLength(1));
    expect(companyRequests[0].searchParams.has("fund_name")).toBe(false);
    expect(companyRequests[0].searchParams.has("fund_code")).toBe(false);
    expect(companyRequests[0].searchParams.has("asset_class")).toBe(false);
  });

  it("submits all five research filters to the server and resets to page one", async () => {
    const user = userEvent.setup();
    renderPage("/funds?page=3&page_size=50");
    await screen.findByRole("grid", { name: "基金研究结果" });
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    const startRequestCount = requests.length;

    fireEvent.change(screen.getByLabelText("基金名称"), {
      target: { value: "Alpha" },
    });
    fireEvent.change(screen.getByLabelText("基金代码"), {
      target: { value: "000001" },
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: "管理公司" }),
      "永赢基金",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "基金类别" }),
      "EQUITY",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "申购状态" }),
      "开放",
    );
    await user.click(screen.getByRole("button", { name: "查询基金" }));

    await waitFor(() =>
      expect(requests.length).toBeGreaterThan(startRequestCount),
    );
    const submitted = requests.at(-1)!.searchParams;
    expect(submitted.get("fund_name")).toBe("Alpha");
    expect(submitted.get("fund_code")).toBe("000001");
    expect(submitted.get("fund_company")).toBe("永赢基金");
    expect(submitted.get("asset_class")).toBe("EQUITY");
    expect(submitted.get("sub_status")).toBe("开放");
    expect(submitted.get("page")).toBe("1");
    expect(submitted.get("page_size")).toBe("50");
    expect(submitted.has("fund_type")).toBe(false);
    expect(
      screen.queryByText(/申购状态目前固定显示“开放”/),
    ).not.toBeInTheDocument();
  });

  it("does not request an invalid fund code and resets to the first page", async () => {
    const user = userEvent.setup();
    renderPage("/funds?page=3&page_size=50");
    await screen.findByRole("grid", { name: "基金研究结果" });
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));

    const codeInput = screen.getByLabelText("基金代码");
    fireEvent.change(codeInput, { target: { value: "１２３４５６" } });
    await user.click(screen.getByRole("button", { name: "查询基金" }));
    expect(
      await screen.findByText("基金代码必须为 6 位半角数字"),
    ).toBeVisible();
    expect(
      requests.every(
        (request) => request.searchParams.get("fund_code") !== "１２３４５６",
      ),
    ).toBe(true);

    await user.clear(screen.getByLabelText("基金代码"));
    await user.click(screen.getByRole("button", { name: "重置" }));
    expect(screen.getByLabelText("基金名称")).toHaveValue("");
    expect(emptyFundFilters().page_size).toBe("20");
  });

  it("reset clears unapplied text/code drafts and validation errors when the URL is already default", async () => {
    const user = userEvent.setup();
    renderPage("/funds?page=1&page_size=20&sort=fund_name&order=asc");
    fireEvent.change(screen.getByLabelText("基金名称"), {
      target: { value: "draft" },
    });
    fireEvent.change(screen.getByLabelText("基金代码"), {
      target: { value: "１２３" },
    });
    await user.click(screen.getByRole("button", { name: "查询基金" }));
    expect(screen.getByText("基金代码必须为 6 位半角数字")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "重置" }));
    expect(screen.getByLabelText("基金名称")).toHaveValue("");
    expect(screen.getByLabelText("基金代码")).toHaveValue("");
    expect(
      screen.queryByText("基金代码必须为 6 位半角数字"),
    ).not.toBeInTheDocument();
  });
});
