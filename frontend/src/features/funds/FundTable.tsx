import { Button } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import type { IDatasource, IGetRowsParams, ColDef } from "ag-grid-community";

import type {
  FundListItem,
  FundListMeta,
  ListFundsParams,
} from "../../api/generated/m17.schemas";
import { fundPageQueryOptions, queryKeys } from "../../api/queries";
import { ResearchDataTable } from "../../components/ResearchDataTable";

type Props = {
  params: ListFundsParams;
  onOpenDetail: (fund: FundListItem) => void;
  onPageChange: (page: number, pageSize: number) => void;
  onSortChange: (sort: string, order: "asc" | "desc") => void;
};

export const FUND_PAGE_SIZES = [20, 50, 200] as const;

export const mapGridRequestToFundParams = (
  params: ListFundsParams,
  request: Pick<
    IGetRowsParams<FundListItem>,
    "startRow" | "endRow" | "sortModel"
  >,
): ListFundsParams => {
  const pageSize = Math.max(1, request.endRow - request.startRow);
  const sorted = request.sortModel[0];
  return {
    ...params,
    page:
      request.startRow === 0 && (params.page ?? 1) > 1
        ? params.page
        : Math.floor(request.startRow / pageSize) + 1,
    page_size: pageSize,
    ...(sorted?.colId &&
    ["fund_name", "fund_code", "fund_company", "sub_status"].includes(
      sorted.colId,
    )
      ? { sort: sorted.colId as ListFundsParams["sort"], order: sorted.sort }
      : {}),
  };
};

export type FundPageResult = { rows: FundListItem[]; meta: FundListMeta };

const formatAum = (value?: number | null) => {
  if (value == null || !Number.isFinite(value)) return "—";
  const unit =
    value >= 100_000_000 ? 100_000_000 : value >= 10_000 ? 10_000 : 1;
  const suffix = unit === 100_000_000 ? "亿" : unit === 10_000 ? "万" : "元";
  return `${Number((value / unit).toFixed(2))}${suffix}`;
};

const formatRate = (value?: number | null) =>
  value == null || !Number.isFinite(value)
    ? "—"
    : `${(value * 100).toFixed(2)}%`;

export const createFundPageDatasource = ({
  params,
  currentPageSize,
  initialPageAppliedRef,
  initialTargetPageRef,
  pageRef,
  loadPage,
}: {
  params: ListFundsParams;
  currentPageSize: number;
  initialPageAppliedRef: MutableRefObject<boolean>;
  initialTargetPageRef: MutableRefObject<number>;
  pageRef: MutableRefObject<{ page: number; pageSize: number }>;
  loadPage: (params: ListFundsParams) => Promise<FundPageResult>;
}): IDatasource => {
  let active = true;
  return {
    rowCount:
      params.page && params.page > 1
        ? (params.page - 1) * currentPageSize + 1
        : undefined,
    getRows: async (request: IGetRowsParams<FundListItem>) => {
      const requestParams = mapGridRequestToFundParams(params, request);
      try {
        const result = await loadPage(requestParams);
        if (!active) return;
        const requestedInitialPage = params.page ?? 1;
        const targetInitialPage = Math.max(
          1,
          Math.min(
            requestedInitialPage,
            result.meta.pagination.total_pages || 1,
          ),
        );
        if (!initialPageAppliedRef.current) {
          initialTargetPageRef.current = targetInitialPage;
          pageRef.current = {
            page: targetInitialPage,
            pageSize: currentPageSize,
          };
        }
        request.successCallback(
          result.rows,
          result.meta.pagination.total_items,
        );
        if (
          !initialPageAppliedRef.current &&
          targetInitialPage !== requestedInitialPage
        ) {
          request.api.paginationGoToPage(targetInitialPage - 1);
        }
      } catch {
        if (!active) return;
        request.failCallback();
      }
    },
    destroy() {
      active = false;
    },
  };
};

export const FundTable = ({
  params,
  onOpenDetail,
  onPageChange,
  onSortChange,
}: Props) => {
  const queryClient = useQueryClient();
  const fundDataRevision = useQuery({
    queryKey: queryKeys.fundDataRevision,
    queryFn: async () => 0,
    initialData: 0,
    staleTime: Infinity,
  }).data;
  const currentPageSize = params.page_size ?? 20;
  const pageRef = useRef({ page: params.page ?? 1, pageSize: currentPageSize });
  const gridReadyRef = useRef(false);
  const initialTargetPageRef = useRef(params.page ?? 1);
  const initialPageAppliedRef = useRef((params.page ?? 1) <= 1);
  const datasource = useMemo<IDatasource>(
    () =>
      createFundPageDatasource({
        params,
        currentPageSize,
        initialPageAppliedRef,
        initialTargetPageRef,
        pageRef,
        loadPage: (requestParams) =>
          queryClient.fetchQuery(
            fundPageQueryOptions(requestParams, fundDataRevision),
          ),
      }),
    [
      currentPageSize,
      initialPageAppliedRef,
      initialTargetPageRef,
      params,
      fundDataRevision,
      queryClient,
    ],
  );

  const columns = useMemo<ColDef<FundListItem>[]>(
    () => [
      {
        field: "fund_code",
        colId: "fund_code",
        headerName: "基金代码",
        minWidth: 120,
        sort: params.sort === "fund_code" ? params.order : null,
        cellRenderer: ({ value }: { value?: string | null }) => value || "—",
      },
      {
        field: "fund_name",
        colId: "fund_name",
        headerName: "基金名称",
        minWidth: 180,
        sort: params.sort === "fund_name" ? params.order : null,
        cellRenderer: ({ value }: { value?: string }) => value || "—",
      },
      {
        field: "asset_type",
        colId: "asset_type",
        headerName: "基金类型",
        minWidth: 120,
        sortable: false,
        valueFormatter: ({ value }) => value || "—",
      },
      {
        field: "fund_company",
        colId: "fund_company",
        headerName: "管理公司",
        minWidth: 160,
        sort: params.sort === "fund_company" ? params.order : null,
        valueFormatter: ({ value }) => value || "—",
      },
      {
        field: "fund_manager",
        colId: "fund_manager",
        headerName: "基金经理",
        minWidth: 140,
        sortable: false,
        valueFormatter: ({ value }) => value || "—",
      },
      {
        field: "fund_aum",
        colId: "fund_aum",
        headerName: "基金规模",
        minWidth: 120,
        sortable: false,
        valueFormatter: ({ value }) => formatAum(value),
      },
      {
        field: "fund_management_fee",
        colId: "fund_management_fee",
        headerName: "管理费率",
        minWidth: 110,
        sortable: false,
        valueFormatter: ({ value }) => formatRate(value),
      },
      {
        field: "fund_custody_fee",
        colId: "fund_custody_fee",
        headerName: "托管费率",
        minWidth: 110,
        sortable: false,
        valueFormatter: ({ value }) => formatRate(value),
      },
      {
        colId: "detail",
        headerName: "详情",
        minWidth: 110,
        sortable: false,
        cellRenderer: ({ data }: { data?: FundListItem }) =>
          data ? (
            <Button
              size="compact-xs"
              variant="subtle"
              data-fund-detail-trigger
              aria-label={`查看详情 ${data.fund_name}`}
              onClick={() => onOpenDetail(data)}
            >
              查看详情
            </Button>
          ) : null,
      },
    ],
    [onOpenDetail, params.order, params.sort],
  );

  const paginationChanged = useCallback(
    (event: {
      api: {
        paginationGetCurrentPage: () => number;
        paginationGetPageSize: () => number;
      };
    }) => {
      if (!gridReadyRef.current) return;
      const page = event.api.paginationGetCurrentPage() + 1;
      const pageSize = event.api.paginationGetPageSize();
      if (!initialPageAppliedRef.current) {
        if (pageSize !== pageRef.current.pageSize) {
          initialPageAppliedRef.current = true;
          pageRef.current = { page: 1, pageSize };
          onPageChange(1, pageSize);
          return;
        }
        if (page !== initialTargetPageRef.current) return;
        initialPageAppliedRef.current = true;
        pageRef.current = { page, pageSize };
        if (page !== (params.page ?? 1)) onPageChange(page, pageSize);
        return;
      }
      if (
        pageRef.current.page !== page ||
        pageRef.current.pageSize !== pageSize
      ) {
        pageRef.current = { page, pageSize };
        onPageChange(page, pageSize);
      }
    },
    [onPageChange, params.page],
  );
  const sortChanged = useCallback(
    (event: {
      api: {
        getColumnState: () => { colId: string; sort?: "asc" | "desc" | null }[];
      };
    }) => {
      const sorted = event.api.getColumnState().find((item) => item.sort);
      if (!sorted?.sort) {
        if (params.sort !== "fund_name" || params.order !== "asc") {
          queryClient.removeQueries({
            queryKey: queryKeys.fundPages(params, fundDataRevision),
            exact: true,
          });
          onSortChange("fund_name", "asc");
        }
        return;
      }
      if (
        ["fund_name", "fund_code", "fund_company", "sub_status"].includes(
          sorted.colId,
        ) &&
        (sorted.colId !== params.sort || sorted.sort !== params.order)
      ) {
        queryClient.removeQueries({
          queryKey: queryKeys.fundPages(params, fundDataRevision),
          exact: true,
        });
        onSortChange(sorted.colId, sorted.sort);
      }
    },
    [fundDataRevision, onSortChange, params, queryClient],
  );

  return (
    <>
      <ResearchDataTable<FundListItem>
        key={`funds:${fundDataRevision}`}
        caption="基金研究结果"
        layoutKey="funds"
        showSettings={false}
        columnDefs={columns}
        rowModelType="infinite"
        datasource={datasource}
        cacheBlockSize={currentPageSize}
        pagination
        paginationPageSize={currentPageSize}
        paginationPageSizeSelector={[...FUND_PAGE_SIZES]}
        getRowId={({ data }) => data.share_class_id}
        onRowDoubleClicked={({ data, event }) => {
          const target = event?.target;
          if (!data || !(target instanceof Element)) return;
          if (
            target.closest(
              'a, button, input, select, textarea, [role="button"], [role="link"], [contenteditable="true"]',
            )
          )
            return;
          target
            .closest('[role="row"]')
            ?.querySelector<HTMLButtonElement>("[data-fund-detail-trigger]")
            ?.focus({ preventScroll: true });
          onOpenDetail(data);
        }}
        onPaginationChanged={paginationChanged}
        onSortChanged={sortChanged}
        onGridReady={(event) => {
          gridReadyRef.current = true;
          if ((params.page ?? 1) > 1)
            event.api.paginationGoToPage((params.page ?? 1) - 1);
        }}
        suppressMultiSort
        suppressColumnVirtualisation
        suppressCellFocus
        containerStyle={{ height: "100%", minHeight: 0 }}
        requiredColumnIds={[
          "fund_code",
          "fund_name",
          "asset_type",
          "fund_company",
          "fund_manager",
          "fund_aum",
          "fund_management_fee",
          "fund_custody_fee",
          "detail",
        ]}
        emptyMessage="没有符合条件的基金。"
      />
    </>
  );
};
