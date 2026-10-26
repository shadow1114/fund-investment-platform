import { Checkbox, Group, Text } from "@mantine/core";
import {
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FundSummary } from "../../api/generated/m17.schemas";
import { DataTable } from "../../components/DataTable";
import { ClassificationView } from "../classifications/ClassificationView";
import {
  FundBasicInfoRefreshButton,
  FundBatchIngestionAction,
} from "./FundIngestionPanel";

const column = createColumnHelper<FundSummary>();

export const FundTable = ({
  funds,
  asOfDate,
  returnTo,
  canManageIngestion = false,
  sort,
  order,
  onSort,
}: {
  funds: FundSummary[];
  asOfDate?: string;
  returnTo: string;
  canManageIngestion?: boolean;
  sort: string;
  order: string;
  onSort: (sort: string, order: "asc" | "desc") => void;
}) => {
  const [selectedFundIds, setSelectedFundIds] = useState<string[]>([]);
  const visibleIds = funds.map((fund) => fund.fund_id);
  const allVisibleSelected =
    visibleIds.length > 0 &&
    visibleIds.every((id) => selectedFundIds.includes(id));
  const columns = useMemo(
    () => [
      column.display({
        id: "select",
        header: () => (
          <Checkbox
            aria-label={allVisibleSelected ? "清除本页选择" : "选择本页基金"}
            checked={allVisibleSelected}
            indeterminate={
              !allVisibleSelected &&
              visibleIds.some((id) => selectedFundIds.includes(id))
            }
            onChange={(event) => {
              setSelectedFundIds((current) => {
                const keepOtherPages = current.filter(
                  (id) => !visibleIds.includes(id),
                );
                return event.currentTarget.checked
                  ? [...keepOtherPages, ...visibleIds]
                  : keepOtherPages;
              });
            }}
          />
        ),
        enableHiding: false,
        cell: ({ row }) => {
          const fund = row.original;
          return (
            <Checkbox
              aria-label={`选择 ${fund.fund_name}`}
              checked={selectedFundIds.includes(fund.fund_id)}
              onChange={(event) =>
                setSelectedFundIds((current) =>
                  event.currentTarget.checked
                    ? [...new Set([...current, fund.fund_id])]
                    : current.filter((id) => id !== fund.fund_id),
                )
              }
            />
          );
        },
      }),
      column.accessor("fund_name", {
        id: "fund_name",
        header: () => (
          <button
            type="button"
            onClick={() =>
              onSort(
                "fund_name",
                sort === "fund_name" && order === "asc" ? "desc" : "asc",
              )
            }
          >
            基金名称{" "}
            {sort === "fund_name" ? (order === "asc" ? "↑" : "↓") : "↕"}
          </button>
        ),
        cell: ({ row, getValue }) => (
          <Link
            to={`/funds/${row.original.fund_id}?return_to=${encodeURIComponent(returnTo)}${asOfDate ? `&as_of_date=${encodeURIComponent(asOfDate)}` : ""}`}
          >
            {getValue()}
          </Link>
        ),
      }),
      column.accessor("fund_id", { header: "基金代码" }),
      column.accessor("fund_classification", { header: "主要分类" }),
      column.display({
        id: "classification",
        header: "五维分类",
        cell: ({ row }) => (
          <ClassificationView classification={row.original.classification} />
        ),
      }),
      column.accessor("share_class", { header: "份额类别" }),
      column.accessor("lifecycle_status", { header: "生命周期" }),
      column.accessor("investment_eligibility", { header: "投资资格" }),
      column.accessor("inception_date", {
        id: "inception_date",
        header: () => (
          <button
            type="button"
            onClick={() =>
              onSort(
                "inception_date",
                sort === "inception_date" && order === "asc" ? "desc" : "asc",
              )
            }
          >
            成立日期{" "}
            {sort === "inception_date" ? (order === "asc" ? "↑" : "↓") : "↕"}
          </button>
        ),
      }),
      column.display({
        id: "data-ingestion",
        header: "基本信息",
        cell: ({ row }) => (
          <FundBasicInfoRefreshButton
            fundId={row.original.fund_id}
            canManage={canManageIngestion}
          />
        ),
      }),
    ],
    [
      allVisibleSelected,
      asOfDate,
      canManageIngestion,
      onSort,
      order,
      returnTo,
      selectedFundIds,
      sort,
      visibleIds,
    ],
  );
  const table = useReactTable({
    data: funds,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
  });

  return (
    <>
      <Group justify="space-between" mb="sm" wrap="wrap">
        <Group gap="xs">
          <Text size="sm" c="dimmed">
            已选择本页 {selectedFundIds.length} 只（批量上限 100）
          </Text>
        </Group>
        <FundBatchIngestionAction
          fundIds={selectedFundIds}
          canManage={canManageIngestion}
        />
      </Group>
      <DataTable
        table={table}
        caption="基金研究结果"
        emptyMessage="没有符合条件的基金。"
        layoutKey="funds"
        requiredColumnIds={["fund_name", "fund_id", "select"]}
      />
    </>
  );
};
