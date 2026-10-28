import {
  classificationCatalog,
  emptyClassificationHistory,
} from "../../test/classificationFixtures";
import { sessionEnvelope } from "../../test/contractFixtures";
import { QueryClient } from "@tanstack/react-query";
import { cleanup, screen, waitFor } from "@testing-library/react";
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
  }: {
    label: string;
    "aria-label"?: string;
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  }) => (
    <label>
      {label}
      <input
        aria-label={ariaLabel ?? label}
        value={value}
        onChange={onChange}
      />
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
  },
  error: null,
};

const server = setupServer(
  http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json(classificationCatalog),
  ),
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
});
afterAll(() => server.close());

describe("FundResearchPage", () => {
  it("passes frozen filters through unchanged and renders PIT provenance", async () => {
    renderPage(
      "/funds?fund_name=Alpha&fund_type=EQUITY%2CBOND&lifecycle_status=NORMAL&investment_eligibility=FULLY_ELIGIBLE&as_of_date=2026-09-16&page=2&page_size=10&sort=fund_name&order=asc",
    );

    expect(await screen.findByText("Alpha 稳健基金")).toBeVisible();
    await waitFor(() => expect(requests).toHaveLength(1));
    const query = requests[0].searchParams;
    expect(Object.fromEntries(query)).toEqual({
      fund_name: "Alpha",
      fund_type: "EQUITY,BOND",
      lifecycle_status: "NORMAL",
      investment_eligibility: "FULLY_ELIGIBLE",
      as_of_date: "2026-09-16",
      page: "2",
      page_size: "10",
      sort: "fund_name",
      order: "asc",
    });
    expect(screen.getByText("点时数据：是")).toBeVisible();
    await userEvent.setup().click(screen.getByText("查看来源版本"));
    expect(screen.getByText("classification_version")).toBeVisible();
    expect(screen.getByText("class-v3")).toBeVisible();
    expect(screen.getByText("精确 18")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Alpha 稳健基金" }),
    ).toHaveAttribute("href", expect.stringContaining("as_of_date=2026-09-16"));
  });

  it("applies only active classification filters while preserving the legacy URL state", async () => {
    const user = userEvent.setup();
    renderPage(
      "/funds?asset_class=EQUITY,BOND&strategy=ACTIVE&geography=CN,US&product_structure=ETF&market_attributes=QDII&classification_status=CONFLICT",
    );
    await screen.findByText("Alpha 稳健基金");
    expect(requests[0].searchParams.get("asset_class")).toBe("EQUITY,BOND");
    expect(requests[0].searchParams.get("geography")).toBeNull();
    expect(requests[0].searchParams.get("product_structure")).toBeNull();
    expect(requests[0].searchParams.get("market_attributes")).toBeNull();
    await user.deselectOptions(
      screen.getByRole("listbox", { name: "资产类别" }),
      ["EQUITY"],
    );
    await user.selectOptions(
      await screen.findByRole("listbox", { name: "资产类别" }),
      ["BOND"],
    );
    await user.click(screen.getByRole("button", { name: "查询基金" }));
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].searchParams.get("asset_class")).toBe("BOND");
    expect(requests[1].searchParams.get("classification_status")).toBe(
      "CONFLICT",
    );
  });

  it("uses server pagination metadata and preserves filters on the next page", async () => {
    const user = userEvent.setup();
    renderPage("/funds?fund_name=Alpha&page=2&page_size=10");

    expect(
      await screen.findByText(
        (_, element) =>
          element?.tagName === "P" &&
          (element.textContent?.includes("第 2 / 3 页 · 共 21 只基金") ??
            false),
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].searchParams.get("page")).toBe("3");
    expect(requests[1].searchParams.get("fund_name")).toBe("Alpha");
  });

  it("submits combined lifecycle and eligibility filters as comma-separated values", async () => {
    const user = userEvent.setup();
    renderPage("/funds");

    await waitFor(() => expect(requests).toHaveLength(1));
    await user.selectOptions(
      screen.getByRole("listbox", { name: "生命周期状态" }),
      ["NORMAL", "LIQUIDATED"],
    );
    await user.selectOptions(
      screen.getByRole("listbox", { name: "投资资格" }),
      ["FULLY_ELIGIBLE", "HOLD_ONLY"],
    );
    await user.click(screen.getByRole("button", { name: "查询基金" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].searchParams.get("lifecycle_status")).toBe(
      "NORMAL,LIQUIDATED",
    );
    expect(requests[1].searchParams.get("investment_eligibility")).toBe(
      "FULLY_ELIGIBLE,HOLD_ONLY",
    );
  });

  it("renders empty and API error states explicitly", async () => {
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
    expect(await screen.findByText("没有符合条件的基金")).toBeVisible();
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
    expect(await screen.findByText("Fund service unavailable")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "请求失败 · 503 FUNDS_UNAVAILABLE",
    );
  });
});
