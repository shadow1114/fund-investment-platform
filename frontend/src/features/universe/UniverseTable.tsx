import { Badge } from "@mantine/core";
import {
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Link } from "react-router-dom";

import type { UniverseMember } from "../../api/generated/m17.schemas";
import { DataTable } from "../../components/DataTable";
import { MetricValue } from "../../components/MetricValue";
import { statusTextColors } from "../../components/StatusBadge";
import { ConditionList } from "./ConditionList";

type Props = {
  members: UniverseMember[];
  label: string;
  decisionAt: string;
};

const column = createColumnHelper<UniverseMember>();

export const UniverseTable = ({ members, label, decisionAt }: Props) => {
  const columns = [
    column.accessor("fund_id", {
      header: "基金代码",
      cell: ({ getValue }) => (
        <Link
          to={`/funds/${encodeURIComponent(getValue())}?as_of_date=${encodeURIComponent(decisionAt)}`}
        >
          {getValue()}
        </Link>
      ),
      enableHiding: false,
    }),
    column.accessor("selection_status", {
      header: "选择状态",
      cell: ({ getValue }) => {
        const status = getValue();
        const labels = {
          SELECTED: "已入选",
          REJECTED: "已排除",
          UNKNOWN: "未知状态",
        };
        const colors = {
          SELECTED: "green",
          REJECTED: "gray",
          UNKNOWN: "yellow",
        };
        return (
          <Badge
            color={colors[status] ?? "gray"}
            style={{ color: statusTextColors[colors[status] ?? "gray"] }}
            variant="light"
          >
            {labels[status] ?? `未知（${status}）`}
          </Badge>
        );
      },
    }),
    column.accessor("investment_eligibility", {
      header: "投资资格",
      cell: ({ getValue }) => getValue() ?? "未提供",
    }),
    column.accessor("total_score", {
      header: "总分",
      cell: ({ row }) => (
        <MetricValue
          value={row.original.total_score}
          status={row.original.total_score_status}
          reason={row.original.total_score_reason}
        />
      ),
    }),
    column.accessor("rank", {
      header: "排名",
      cell: ({ row }) => (
        <MetricValue
          value={row.original.rank}
          status={row.original.rank_status}
          reason={row.original.rank_reason}
        />
      ),
    }),
    column.accessor("percentile", {
      header: "百分位",
      cell: ({ row }) => (
        <MetricValue
          value={row.original.percentile}
          status={row.original.percentile_status}
          reason={row.original.percentile_reason}
          format="percent"
        />
      ),
    }),
    column.accessor("fund_tier", {
      header: "层级",
      cell: ({ getValue }) => getValue() ?? "不可用",
    }),
    column.display({
      id: "conditions",
      header: "筛选证据",
      cell: ({ row }) => (
        <>
          <ConditionList
            fundId={row.original.fund_id}
            kind="passed"
            conditions={row.original.passed_conditions}
          />
          <ConditionList
            fundId={row.original.fund_id}
            kind="failed"
            conditions={row.original.failed_conditions}
          />
          {row.original.selection_status === "REJECTED" &&
            row.original.failed_conditions.length === 0 && (
              <p>接口未返回具体排除原因。</p>
            )}
        </>
      ),
    }),
  ];
  const table = useReactTable({
    data: members,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <DataTable
      table={table}
      caption={label}
      emptyMessage={`${label}：无成员`}
      layoutKey={`universe-${label}`}
      requiredColumnIds={["fund_id"]}
    />
  );
};
