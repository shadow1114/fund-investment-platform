import { Badge } from "@mantine/core";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import { Link } from "react-router-dom";

import type { PortfolioSummary } from "../../api/generated/m17.schemas";
import {
  ResearchDataTable,
  type ResearchDataTableProps,
} from "../../components/ResearchDataTable";

const statusLabels: Record<string, string> = {
  DRAFT: "草稿",
  ACTIVE: "运行中",
  SUSPENDED: "已暂停",
  CLOSED: "已关闭",
  UNKNOWN: "未知",
};

export const PortfolioList = ({
  portfolios,
  serverPagination,
}: {
  portfolios: PortfolioSummary[];
  serverPagination: NonNullable<
    ResearchDataTableProps<PortfolioSummary>["serverPagination"]
  >;
}) => {
  const columns: ColDef<PortfolioSummary>[] = [
    {
      field: "portfolio_name",
      headerName: "组合名称",
      cellRenderer: ({ data, value }: ICellRendererParams<PortfolioSummary>) =>
        data ? (
          <Link to={`/portfolios/${encodeURIComponent(data.portfolio_id)}`}>
            {value}
          </Link>
        ) : null,
      lockVisible: true,
    },
    { field: "portfolio_id", headerName: "组合 ID" },
    { field: "portfolio_type", headerName: "组合类型" },
    {
      field: "status",
      headerName: "状态",
      cellRenderer: ({ value }: ICellRendererParams<PortfolioSummary>) => {
        if (value == null) return null;
        const status = value;
        return (
          <Badge
            color={
              status === "ACTIVE"
                ? "green"
                : status === "DRAFT"
                  ? "blue"
                  : "gray"
            }
            variant="light"
          >
            {statusLabels[status] ?? `未知（${status}）`}
          </Badge>
        );
      },
    },
    { field: "base_currency", headerName: "基准币种" },
    { field: "portfolio_version", headerName: "组合版本" },
  ];
  return (
    <ResearchDataTable
      columnDefs={columns}
      rowData={portfolios}
      getRowId={({ data }) => data.portfolio_id}
      serverPagination={serverPagination}
      caption="可见组合列表"
      emptyMessage="当前用户没有可见组合。"
      layoutKey="portfolios"
      requiredColumnIds={["portfolio_name"]}
    />
  );
};
