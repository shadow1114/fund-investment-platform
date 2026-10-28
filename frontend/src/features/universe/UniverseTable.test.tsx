import { getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { DataTable } from "../../components/DataTable";
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { UniverseMember } from "../../api/generated/m17.schemas";
import { renderWorkbench } from "../../test/render";
import { universeDetailEnvelope } from "../../test/contractFixtures";
import { UniverseTable } from "./UniverseTable";

const PlainTable = () => {
  const table = useReactTable({
    data: [{ value: null }],
    columns: [{ accessorKey: "value", header: "数值" }],
    getCoreRowModel: getCoreRowModel(),
  });
  return <DataTable table={table} caption="普通值" layoutKey="test-null" />;
};

afterEach(cleanup);

it("shows unavailable and excluded score reasons instead of replacing null values", () => {
  const members = [
    ...universeDetailEnvelope.data.members,
    ...universeDetailEnvelope.data.excluded,
  ] as UniverseMember[];
  renderWorkbench(
    <UniverseTable
      members={members}
      label="候选基金"
      decisionAt="2026-09-16"
    />,
  );
  const table = screen.getByRole("table", { name: "候选基金" });
  const selected = within(table).getByRole("row", { name: /000001/ });
  const rejected = within(table).getByRole("row", { name: /000002/ });
  expect(
    within(selected).getAllByText("不可用（ELIGIBILITY_ONLY）"),
  ).toHaveLength(3);
  expect(
    within(rejected).getAllByText("不可用（FAILED_ELIGIBILITY）"),
  ).toHaveLength(3);
  expect(within(selected).getByText("不可用")).toBeVisible();
});

it("shows an em dash for a missing value without a custom renderer", () => {
  renderWorkbench(<PlainTable />);
  expect(screen.getByRole("cell", { name: "—" })).toBeVisible();
});
