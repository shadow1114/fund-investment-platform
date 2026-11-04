import { Badge } from "@mantine/core";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import { Link } from "react-router-dom";

import type { UniverseMember } from "../../api/generated/m17.schemas";
import { ResearchDataTable } from "../../components/ResearchDataTable";
import { MetricValue } from "../../components/MetricValue";
import { statusTextColors } from "../../components/StatusBadge";
import { ConditionList } from "./ConditionList";

type Props = {
  members: UniverseMember[];
  label: string;
  decisionAt: string;
};

export const UniverseTable = ({ members, label, decisionAt }: Props) => {
  const columns: ColDef<UniverseMember>[] = [
    {
      field: "fund_id",
      headerName: "基金代码",
      cellRenderer: ({ value }: ICellRendererParams<UniverseMember>) => (
        <Link
          to={`/funds/${encodeURIComponent(value)}?as_of_date=${encodeURIComponent(decisionAt)}`}
        >
          {value}
        </Link>
      ),
      lockVisible: true,
    },
    {
      field: "selection_status",
      headerName: "选择状态",
      cellRenderer: ({ value }: ICellRendererParams<UniverseMember>) => {
        const status = value;
        const labels: Record<string, string> = {
          SELECTED: "已入选",
          REJECTED: "已排除",
          UNKNOWN: "未知状态",
        };
        const colors: Record<string, string> = {
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
    },
    {
      field: "investment_eligibility",
      headerName: "投资资格",
      cellRenderer: ({ value }: ICellRendererParams<UniverseMember>) =>
        value ?? "未提供",
    },
    {
      field: "total_score",
      headerName: "总分",
      cellRenderer: ({ data }: ICellRendererParams<UniverseMember>) => (
        <MetricValue
          value={data!.total_score}
          status={data!.total_score_status}
          reason={data!.total_score_reason}
        />
      ),
    },
    {
      field: "rank",
      headerName: "排名",
      cellRenderer: ({ data }: ICellRendererParams<UniverseMember>) => (
        <MetricValue
          value={data!.rank}
          status={data!.rank_status}
          reason={data!.rank_reason}
        />
      ),
    },
    {
      field: "percentile",
      headerName: "百分位",
      cellRenderer: ({ data }: ICellRendererParams<UniverseMember>) => (
        <MetricValue
          value={data!.percentile}
          status={data!.percentile_status}
          reason={data!.percentile_reason}
          format="percent"
        />
      ),
    },
    {
      field: "fund_tier",
      headerName: "层级",
      cellRenderer: ({ value }: ICellRendererParams<UniverseMember>) =>
        value ?? "不可用",
    },
    {
      colId: "conditions",
      autoHeight: true,
      wrapText: true,
      minWidth: 320,
      headerName: "筛选证据",
      cellRenderer: ({ data }: ICellRendererParams<UniverseMember>) => (
        <>
          <ConditionList
            fundId={data!.fund_id}
            kind="passed"
            conditions={data!.passed_conditions}
          />
          <ConditionList
            fundId={data!.fund_id}
            kind="failed"
            conditions={data!.failed_conditions}
          />
          {data!.selection_status === "REJECTED" &&
            data!.failed_conditions.length === 0 && (
              <p>接口未返回具体排除原因。</p>
            )}
        </>
      ),
    },
  ];

  return (
    <ResearchDataTable
      columnDefs={columns}
      rowData={members}
      getRowId={({ data }) => data.fund_id}
      pagination
      paginationPageSize={20}
      paginationPageSizeSelector={[20, 50, 100]}
      caption={label}
      emptyMessage={`${label}：无成员`}
      layoutKey={`universe-${label}`}
      requiredColumnIds={["fund_id"]}
    />
  );
};
