import { Badge } from "@mantine/core";
import {
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Link } from "react-router-dom";

import type { PortfolioSummary } from "../../api/generated/m17.schemas";
import { DataTable } from "../../components/DataTable";

const column = createColumnHelper<PortfolioSummary>();
const statusLabels: Record<string, string> = {
  DRAFT: "草稿",
  ACTIVE: "运行中",
  SUSPENDED: "已暂停",
  CLOSED: "已关闭",
  UNKNOWN: "未知",
};

export const PortfolioList = ({
  portfolios,
}: {
  portfolios: PortfolioSummary[];
}) => {
  const columns = [
    column.accessor("portfolio_name", {
      header: "组合名称",
      cell: ({ row, getValue }) => (
        <Link
          to={`/portfolios/${encodeURIComponent(row.original.portfolio_id)}`}
        >
          {getValue()}
        </Link>
      ),
      enableHiding: false,
    }),
    column.accessor("portfolio_id", { header: "组合 ID" }),
    column.accessor("portfolio_type", { header: "组合类型" }),
    column.accessor("status", {
      header: "状态",
      cell: ({ getValue }) => {
        const status = getValue();
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
    }),
    column.accessor("base_currency", { header: "基准币种" }),
    column.accessor("portfolio_version", { header: "组合版本" }),
  ];
  const table = useReactTable({
    data: portfolios,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <DataTable
      table={table}
      caption="可见组合列表"
      emptyMessage="当前用户没有可见组合。"
      layoutKey="portfolios"
      requiredColumnIds={["portfolio_name"]}
    />
  );
};
