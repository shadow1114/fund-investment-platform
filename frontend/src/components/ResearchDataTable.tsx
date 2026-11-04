import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  ClientSideRowModelModule,
  ColumnApiModule,
  GridStateModule,
  InfiniteRowModelModule,
  LocaleModule,
  ModuleRegistry,
  PaginationModule,
  RowSelectionModule,
  RowAutoHeightModule,
  RenderApiModule,
  themeQuartz,
  type ColDef,
  type GridApi,
  type IDatasource,
  type IGetRowsParams,
} from "ag-grid-community";
import { AgGridReact, type AgGridReactProps } from "ag-grid-react";

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  InfiniteRowModelModule,
  ColumnApiModule,
  GridStateModule,
  LocaleModule,
  PaginationModule,
  RowSelectionModule,
  RowAutoHeightModule,
  RenderApiModule,
]);

type Density = "compact" | "comfortable";
type Layout = { visibleColumnIds?: string[]; density: Density };

function readLayout(key: string): Layout {
  for (const version of [2, 1]) {
    try {
      const value = JSON.parse(
        localStorage.getItem(`fip:table:${key}:v${version}`) ?? "null",
      );
      if (value?.version === version && Array.isArray(value.visibleColumnIds)) {
        return {
          visibleColumnIds: value.visibleColumnIds.filter(
            (id: unknown) => typeof id === "string",
          ),
          density: value.density === "comfortable" ? "comfortable" : "compact",
        };
      }
    } catch {
      // Preferences are optional, including when storage access is blocked.
    }
  }
  return { density: "compact" };
}

export type ResearchDataTableProps<TData> = Omit<
  AgGridReactProps<TData>,
  "columnDefs"
> & {
  columnDefs: ColDef<TData>[];
  getRowId: NonNullable<AgGridReactProps<TData>["getRowId"]>;
  caption: string;
  layoutKey: string;
  requiredColumnIds?: string[];
  showSettings?: boolean;
  emptyMessage?: string;
  containerClassName?: string;
  containerStyle?: CSSProperties;
  serverPagination?: {
    page: number;
    pageSize: number;
    total: number;
    loading: boolean;
    failed?: boolean;
    resetKey?: string;
    onPageChange: (page: number) => void;
  };
};

// Native AG Grid options remain available to each business table. In particular,
// infinite tables supply their own datasource and a stable getRowId.
export function ResearchDataTable<TData>({
  caption,
  layoutKey,
  showSettings = true,
  ...props
}: ResearchDataTableProps<TData>) {
  // Remount preferences when a route switches between tables in the same slot.
  return (
    <ResearchDataTableLayout
      key={layoutKey}
      caption={caption}
      layoutKey={layoutKey}
      showSettings={showSettings}
      {...props}
    />
  );
}

function ResearchDataTableLayout<TData>({
  caption,
  layoutKey,
  columnDefs,
  showSettings = true,
  requiredColumnIds = [],
  emptyMessage = "暂无数据",
  containerClassName,
  containerStyle,
  serverPagination,
  ...gridProps
}: ResearchDataTableProps<TData>) {
  const api = useRef<GridApi<TData> | null>(null);
  const current = useRef({ serverPagination, rows: gridProps.rowData });
  current.current = { serverPagination, rows: gridProps.rowData };
  const pending = useRef(new Map<number, IGetRowsParams>());
  const pageSize = serverPagination?.pageSize;
  const resetKey = serverPagination?.resetKey;
  const datasource = useMemo<IDatasource | undefined>(() => {
    if (pageSize === undefined) return undefined;
    let active = true;
    // The endpoint owns each page. Never sort or paginate a returned slice.
    return {
      getRows(request) {
        const state = current.current;
        const paging = state.serverPagination!;
        const page = Math.floor(request.startRow / pageSize) + 1;
        // AG Grid defers getRows. A retired datasource or outgoing block must
        // never turn a controlled URL/filter change back into a pager action.
        if (
          !active ||
          paging.pageSize !== pageSize ||
          paging.resetKey !== resetKey ||
          (paging.loading && page !== paging.page) ||
          page !== (api.current?.paginationGetCurrentPage() ?? -1) + 1
        ) {
          request.failCallback();
          return;
        }
        if (page === paging.page && !paging.loading) {
          if (paging.failed) request.failCallback();
          else request.successCallback(state.rows ?? [], paging.total);
        } else {
          pending.current.set(page, request);
          if (page !== paging.page) paging.onPageChange(page);
        }
      },
      destroy() {
        active = false;
        for (const request of pending.current.values()) request.failCallback();
        pending.current.clear();
      },
    };
    // A filter change replaces the datasource and invalidates old page callbacks.
  }, [pageSize, resetKey]);

  useEffect(() => {
    if (!serverPagination) return;
    const grid = api.current;
    if (!grid) return;
    const destination = serverPagination.page - 1;
    if (grid.paginationGetCurrentPage() !== destination) {
      // Reconcile external navigation before loading anything. Refreshing the
      // outgoing block here queues a delayed request for the previous URL page.
      for (const request of pending.current.values()) request.failCallback();
      pending.current.clear();
      grid.setRowCount(serverPagination.total, true);
      grid.paginationGoToPage(destination);
      return;
    }
    // Navigation is controlled immediately; only destination rows wait for the
    // API response. Never serve keepPreviousData rows as the destination page.
    if (serverPagination.loading) return;
    const request = pending.current.get(serverPagination.page);
    if (request) {
      pending.current.delete(serverPagination.page);
      if (serverPagination.failed) request.failCallback();
      else
        request.successCallback(
          gridProps.rowData ?? [],
          serverPagination.total,
        );
    } else {
      // Polling/refetch results must replace cached rows, including status changes.
      grid.refreshInfiniteCache();
    }
    grid.setRowCount(serverPagination.total, true);
  }, [serverPagination, gridProps.rowData]);

  const fullHeight = containerStyle?.height === "100%";
  const [layout, setLayout] = useState(() => readLayout(layoutKey));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const requiredColumnIdsKey = JSON.stringify(requiredColumnIds);
  const columns = useMemo(
    () =>
      columnDefs.map((column) => {
        const id = column.colId ?? column.field;
        const required =
          id !== undefined &&
          (JSON.parse(requiredColumnIdsKey) as string[]).includes(id);
        return {
          ...column,
          hide: required
            ? false
            : layout.visibleColumnIds && id
              ? !layout.visibleColumnIds.includes(id)
              : column.hide,
          lockVisible: required || column.lockVisible,
        };
      }),
    [columnDefs, requiredColumnIdsKey, layout.visibleColumnIds],
  );

  useEffect(() => {
    try {
      localStorage.setItem(
        `fip:table:${layoutKey}:v2`,
        JSON.stringify({
          version: 2,
          density: layout.density,
          visibleColumnIds: columns
            .filter((column) => !column.hide)
            .map((column) => column.colId ?? column.field)
            .filter(Boolean),
        }),
      );
    } catch {
      // Storage failure must never prevent research work.
    }
  }, [columns, layout.density, layoutKey]);

  const selection =
    typeof gridProps.rowSelection === "object"
      ? {
          ...gridProps.rowSelection,
          headerCheckbox: false,
        }
      : gridProps.rowSelection;

  return (
    <section
      aria-label={caption}
      style={
        fullHeight
          ? {
              display: "flex",
              flexDirection: "column",
              height: "100%",
              minHeight: 0,
            }
          : undefined
      }
    >
      {showSettings && (
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            marginBottom: 8,
            flex: "0 0 auto",
          }}
        >
          <button
            type="button"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen(!settingsOpen)}
          >
            列设置
          </button>
          <label>
            表格密度{" "}
            <select
              aria-label="表格密度"
              value={layout.density}
              onChange={(event) =>
                setLayout({ ...layout, density: event.target.value as Density })
              }
            >
              <option value="compact">紧凑</option>
              <option value="comfortable">舒适</option>
            </select>
          </label>
        </div>
      )}
      {showSettings && settingsOpen && (
        <div role="group" aria-label="列显示设置">
          {columns.map((column) => {
            const id = column.colId ?? column.field;
            if (!id) return null;
            return (
              <label key={id} style={{ marginRight: 12 }}>
                <input
                  type="checkbox"
                  checked={!column.hide}
                  disabled={column.lockVisible}
                  onChange={(event) => {
                    const ids = new Set(
                      columns
                        .filter((item) => !item.hide)
                        .map((item) => item.colId ?? item.field),
                    );
                    if (event.target.checked) ids.add(id);
                    else ids.delete(id);
                    setLayout({
                      ...layout,
                      visibleColumnIds: [...ids].filter(
                        (value): value is string => value !== undefined,
                      ),
                    });
                  }}
                />
                {column.headerName ?? id}
              </label>
            );
          })}
        </div>
      )}
      <div
        className={containerClassName}
        style={{
          height: fullHeight ? 0 : 480,
          width: "100%",
          ...(fullHeight ? { flex: "1 1 0", minHeight: 0 } : {}),
          ...containerStyle,
          ...(fullHeight ? { height: 0 } : {}),
        }}
      >
        <AgGridReact<TData>
          theme={themeQuartz.withParams({
            fontFamily: "inherit",
            fontSize: 14,
            accentColor: "#087F8C",
          })}
          rowHeight={layout.density === "compact" ? 36 : 44}
          headerHeight={40}
          defaultColDef={{
            sortable: true,
            resizable: true,
            flex: 1,
            minWidth: 100,
            valueFormatter: ({ value }) =>
              value == null ? "—" : String(value),
          }}
          localeText={{
            noRowsToShow: emptyMessage,
            loadingOoo: "加载中…",
            page: "页",
            of: "/",
            to: "至",
            more: "更多",
            nextPage: "下一页",
            previousPage: "上一页",
            firstPage: "第一页",
            lastPage: "最后一页",
            pageSizeSelectorLabel: "每页行数：",
          }}
          {...gridProps}
          {...(serverPagination
            ? {
                rowData: undefined,
                rowModelType: "infinite" as const,
                datasource,
                pagination: true,
                suppressPaginationPanel: serverPagination.loading,
                paginationPageSize: serverPagination.pageSize,
                paginationPageSizeSelector: false,
                infiniteInitialRowCount: Math.max(
                  serverPagination.total,
                  serverPagination.page * serverPagination.pageSize,
                ),
                initialState: {
                  pagination: {
                    page: serverPagination.page - 1,
                    pageSize: serverPagination.pageSize,
                  },
                },
                maxBlocksInCache: 1,
                maxConcurrentDatasourceRequests: 1,
              }
            : {})}
          onGridReady={(event) => {
            api.current = event.api;
            event.api.setGridAriaProperty("label", caption);
            gridProps.onGridReady?.(event);
          }}
          columnDefs={
            serverPagination
              ? columns.map((column) => ({
                  ...column,
                  sortable: false,
                  filter: false,
                }))
              : columns
          }
          rowSelection={selection}
          cacheBlockSize={
            serverPagination
              ? serverPagination.pageSize
              : gridProps.rowModelType === "infinite"
                ? (gridProps.paginationPageSize ?? 50)
                : gridProps.cacheBlockSize
          }
          onPaginationChanged={(event) => {
            event.api.deselectAll();
            gridProps.onPaginationChanged?.(event);
          }}
          onSortChanged={(event) => {
            event.api.deselectAll();
            gridProps.onSortChanged?.(event);
          }}
          onFilterChanged={(event) => {
            event.api.deselectAll();
            gridProps.onFilterChanged?.(event);
          }}
        />
      </div>
    </section>
  );
}
