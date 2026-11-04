import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithMantine as render } from "../test/render";
import { ResearchDataTable } from "./ResearchDataTable";

import type { ColDef, GridApi, IDatasource } from "ag-grid-community";
import { StrictMode, useState } from "react";
import { MemoryRouter, useSearchParams } from "react-router-dom";

type Fund = { id: string; name: string; score: number };
const columns: ColDef<Fund>[] = [
  { field: "id", headerName: "基金代码" },
  { field: "name", headerName: "基金名称" },
  { field: "score", headerName: "评分" },
];
const props = {
  columnDefs: columns,
  rowData: [],
  caption: "基金研究结果",
  layoutKey: "research-test",
  requiredColumnIds: ["id"],
  getRowId: ({ data }: { data: Fund }) => data.id,
};
afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("ResearchDataTable", () => {
  it("lets a page size the grid container to its available height", async () => {
    render(
      <ResearchDataTable
        {...props}
        containerClassName="research-grid"
        containerStyle={{ height: "100%", minHeight: 0 }}
      />,
    );
    const grid = await screen.findByRole("grid", { name: "基金研究结果" });
    expect(grid.closest(".research-grid")).toHaveStyle({
      height: "0px",
      minHeight: "0",
      flex: "1 1 0px",
    });
  });
  it("gives the grid a Chinese accessible name and empty state", async () => {
    render(
      <StrictMode>
        <ResearchDataTable {...props} />
      </StrictMode>,
    );
    expect(
      await screen.findByRole("grid", { name: "基金研究结果" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("暂无数据")).toBeVisible();
    expect(screen.getByRole("button", { name: "列设置" })).toBeVisible();
  });

  it.each([
    ["v1", { version: 1, visibleColumnIds: ["name", "obsolete"] }],
    ["v2", { version: 2, visibleColumnIds: ["name"], density: "comfortable" }],
  ])(
    "restores %s layouts while retaining required columns",
    async (version, value) => {
      localStorage.setItem(
        `fip:table:research-test:${version}`,
        JSON.stringify(value),
      );
      render(<ResearchDataTable {...props} />);
      await userEvent.click(screen.getByRole("button", { name: "列设置" }));
      const settings = screen.getByRole("group", { name: "列显示设置" });
      expect(
        within(settings).getByRole("checkbox", { name: "基金代码" }),
      ).toBeChecked();
      expect(
        within(settings).getByRole("checkbox", { name: "基金代码" }),
      ).toBeDisabled();
      expect(
        within(settings).getByRole("checkbox", { name: "基金名称" }),
      ).toBeChecked();
      expect(
        within(settings).getByRole("checkbox", { name: "评分" }),
      ).not.toBeChecked();
      await userEvent.click(
        within(settings).getByRole("checkbox", { name: "评分" }),
      );
      await waitFor(() =>
        expect(
          JSON.parse(localStorage.getItem("fip:table:research-test:v2")!)
            .visibleColumnIds,
        ).toEqual(["id", "name", "score"]),
      );
    },
  );
});

it("connects the grid pager to controlled API pages without paginating the loaded slice", async () => {
  function ApiPages() {
    const [page, setPage] = useState(2);
    return (
      <ResearchDataTable
        {...props}
        rowData={[{ id: String(page), name: `API 第 ${page} 页`, score: page }]}
        serverPagination={{
          page,
          pageSize: 20,
          total: 41,
          onPageChange: setPage,
          loading: false,
        }}
      />
    );
  }
  render(<ApiPages />);
  expect(await screen.findByText("API 第 2 页")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(await screen.findByText("API 第 3 页")).toBeVisible();
  expect(screen.getByRole("button", { name: "下一页" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await userEvent.click(screen.getByRole("button", { name: "上一页" }));
  expect(await screen.findByText("API 第 2 页")).toBeVisible();
});

it("keeps a missing plain value as an em dash", async () => {
  render(
    <ResearchDataTable
      caption="普通值"
      layoutKey="plain-null"
      rowData={[{ id: "missing", value: null }]}
      getRowId={({ data }) => data.id}
      columnDefs={[{ field: "value", headerName: "数值" }]}
    />,
  );
  expect(await screen.findByRole("gridcell", { name: "—" })).toBeVisible();
});

it("keeps API pagination unavailable until a fetching page has settled", async () => {
  function FetchingPage() {
    const [loading, setLoading] = useState(true);
    return (
      <>
        <button onClick={() => setLoading(false)}>完成读取</button>
        <ResearchDataTable
          {...props}
          rowData={[{ id: "1", name: "已返回的 API 行", score: 1 }]}
          serverPagination={{
            page: 1,
            pageSize: 20,
            total: 21,
            loading,
            onPageChange: () => undefined,
          }}
        />
      </>
    );
  }
  render(<FetchingPage />);
  await screen.findByRole("grid", { name: "基金研究结果" });
  expect(
    screen.queryByRole("button", { name: "下一页" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "完成读取" }));
  expect(await screen.findByRole("button", { name: "下一页" })).toHaveAttribute(
    "aria-disabled",
    "false",
  );
  expect(await screen.findByText("已返回的 API 行")).toBeVisible();
});

it.each(["history", "filter"] as const)(
  "does not overwrite an external %s change with a deferred outgoing-page request",
  async (change) => {
    const writes: number[] = [];
    let outgoing: IDatasource | undefined;
    let gridApi: GridApi<Fund> | undefined;
    function ControlledNavigation() {
      const [page, setPage] = useState(3);
      const [filter, setFilter] = useState("original");
      return (
        <>
          <button
            onClick={() => {
              setPage(1);
              if (change === "filter") setFilter("filtered");
            }}
          >
            外部跳至第一页
          </button>
          <output aria-label="外部页码">{page}</output>
          <ResearchDataTable
            {...props}
            rowData={[
              {
                id: `${filter}-${page}`,
                name: `${filter} API 第 ${page} 页`,
                score: page,
              },
            ]}
            onGridReady={({ api }) => {
              gridApi = api;
              outgoing = api.getGridOption("datasource");
            }}
            serverPagination={{
              page,
              pageSize: 20,
              total: 61,
              loading: false,
              resetKey: filter,
              onPageChange: (next) => {
                writes.push(next);
              },
            }}
          />
        </>
      );
    }
    render(<ControlledNavigation />);
    expect(await screen.findByText("original API 第 3 页")).toBeVisible();
    expect(writes).toEqual([]);
    await userEvent.click(
      screen.getByRole("button", { name: "外部跳至第一页" }),
    );
    // InfiniteBlock.loadFromDatasource defers getRows with setTimeout(0).
    // Drain that boundary so an outgoing request cannot escape this assertion.
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });
    expect(screen.getByLabelText("外部页码")).toHaveTextContent("1");
    expect(writes).toEqual([]);
    expect(
      await screen.findByText(
        `${change === "filter" ? "filtered" : "original"} API 第 1 页`,
      ),
    ).toBeVisible();
    const failCallback = vi.fn();
    const successCallback = vi.fn();
    // Deliver a queued outgoing request after the controlled move has settled.
    act(() =>
      outgoing!.getRows({
        api: gridApi!,
        startRow: 40,
        endRow: 60,
        sortModel: [],
        filterModel: {},
        context: undefined,
        successCallback,
        failCallback,
      }),
    );
    expect(writes).toEqual([]);
    expect(successCallback).not.toHaveBeenCalled();
    expect(failCallback).toHaveBeenCalledOnce();
  },
);

it("ignores delayed requests from a datasource retired by a filter reset", async () => {
  let outgoing: IDatasource | undefined;
  let gridApi: GridApi<Fund> | undefined;
  function FilterReset() {
    const [filter, setFilter] = useState("original");
    return (
      <>
        <button onClick={() => setFilter("filtered")}>重置筛选</button>
        <ResearchDataTable
          {...props}
          rowData={[{ id: filter, name: `${filter} 结果`, score: 1 }]}
          onGridReady={({ api }) => {
            gridApi = api;
            outgoing = api.getGridOption("datasource");
          }}
          serverPagination={{
            page: 1,
            pageSize: 20,
            total: 21,
            loading: false,
            resetKey: filter,
            onPageChange: () => undefined,
          }}
        />
      </>
    );
  }
  render(<FilterReset />);
  expect(await screen.findByText("original 结果")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "重置筛选" }));
  expect(await screen.findByText("filtered 结果")).toBeVisible();
  const successCallback = vi.fn();
  const failCallback = vi.fn();
  act(() =>
    outgoing!.getRows({
      api: gridApi!,
      startRow: 0,
      endRow: 20,
      sortModel: [],
      filterModel: {},
      context: undefined,
      successCallback,
      failCallback,
    }),
  );
  expect(successCallback).not.toHaveBeenCalled();
  expect(failCallback).toHaveBeenCalledOnce();
});

it("keeps a pending history destination when an outgoing request arrives during loading", async () => {
  const writes: number[] = [];
  let outgoing: IDatasource | undefined;
  let gridApi: GridApi<Fund> | undefined;
  let resolveDestination!: (rows: Fund[]) => void;
  const destinationResponse = new Promise<Fund[]>((resolve) => {
    resolveDestination = resolve;
  });
  function PendingHistory() {
    const [search, setSearch] = useSearchParams();
    const page = Number(search.get("page"));
    const [loading, setLoading] = useState(false);
    const [rows, setRows] = useState([
      { id: "3", name: "读取完成的第 3 页", score: 3 },
    ]);
    return (
      <>
        <button
          onClick={() => {
            setSearch({ page: "1" });
            setLoading(true);
            void destinationResponse.then((data) => {
              setRows(data);
              setLoading(false);
            });
          }}
        >
          后退并等待接口
        </button>
        <output aria-label="受控 URL">{search.toString()}</output>
        <ResearchDataTable
          {...props}
          rowData={rows}
          onGridReady={({ api }) => {
            gridApi = api;
            outgoing = api.getGridOption("datasource");
          }}
          serverPagination={{
            page,
            pageSize: 20,
            total: 61,
            loading,
            onPageChange: (next) => {
              writes.push(next);
              setSearch({ page: String(next) });
            },
          }}
        />
      </>
    );
  }
  render(
    <MemoryRouter initialEntries={["/?page=3"]}>
      <PendingHistory />
    </MemoryRouter>,
  );
  expect(await screen.findByText("读取完成的第 3 页")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "后退并等待接口" }));
  await act(async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  });
  const successCallback = vi.fn();
  const failCallback = vi.fn();
  act(() =>
    outgoing!.getRows({
      api: gridApi!,
      startRow: 40,
      endRow: 60,
      sortModel: [],
      filterModel: {},
      context: undefined,
      successCallback,
      failCallback,
    }),
  );
  expect(writes).toEqual([]);
  expect(screen.getByLabelText("受控 URL")).toHaveTextContent("page=1");
  expect(gridApi!.paginationGetCurrentPage()).toBe(0);
  expect(successCallback).not.toHaveBeenCalled();
  expect(failCallback).toHaveBeenCalledOnce();
  expect(screen.queryByText("读取完成的第 3 页")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "下一页" }),
  ).not.toBeInTheDocument();
  await act(async () => {
    resolveDestination([{ id: "1", name: "等待后返回的第 1 页", score: 1 }]);
    await destinationResponse;
  });
  expect(await screen.findByText("等待后返回的第 1 页")).toBeVisible();
  expect(gridApi!.paginationGetCurrentPage()).toBe(0);
  expect(screen.getByRole("button", { name: "上一页" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  expect(screen.getByLabelText("受控 URL")).toHaveTextContent("page=1");
  expect(writes).toEqual([]);
});
