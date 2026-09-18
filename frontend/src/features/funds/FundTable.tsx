import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Link } from "react-router-dom";

import type { FundSummary } from "../../api/generated/m17.schemas";

const column = createColumnHelper<FundSummary>();

export const FundTable = ({
  funds,
  asOfDate,
}: {
  funds: FundSummary[];
  asOfDate?: string;
}) => {
  const columns = [
    column.accessor("fund_name", {
      header: "基金",
      cell: ({ row, getValue }) => (
        <Link
          to={`/funds/${row.original.fund_id}${asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : ""}`}
        >
          {getValue()}
        </Link>
      ),
    }),
    column.accessor("fund_id", { header: "基金代码" }),
    column.accessor("fund_classification", { header: "分类" }),
    column.accessor("share_class", { header: "份额类别" }),
    column.accessor("lifecycle_status", { header: "生命周期" }),
    column.accessor("investment_eligibility", { header: "投资资格" }),
    column.accessor("inception_date", { header: "成立日期" }),
  ];
  const table = useReactTable({
    data: funds,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <table>
      <thead>
        {table.getHeaderGroups().map((group) => (
          <tr key={group.id}>
            {group.headers.map((header) => (
              <th key={header.id} scope="col">
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext(),
                )}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <td key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
