import { Checkbox, Menu, ScrollArea, Table } from "@mantine/core";
import { Columns3 } from "lucide-react";
import { useEffect, useRef } from "react";
import { flexRender, type Table as TanStackTable } from "@tanstack/react-table";

import styles from "./Workbench.module.css";

const VERSION = 1;

type Props<TData> = {
  table: TanStackTable<TData>;
  caption: string;
  emptyMessage?: string;
  requiredColumnIds?: string[];
  layoutKey: string;
};

const readVisibleIds = (
  key: string,
  validIds: Set<string>,
  requiredColumnIds: string[],
) => {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "null");
    if (
      typeof value === "object" &&
      value !== null &&
      "version" in value &&
      value.version === VERSION &&
      "visibleColumnIds" in value &&
      Array.isArray(value.visibleColumnIds)
    ) {
      const ids = value.visibleColumnIds.filter(
        (id): id is string => typeof id === "string" && validIds.has(id),
      );
      const visibleIds = new Set([...ids, ...requiredColumnIds]);
      return Object.fromEntries(
        [...validIds].map((id) => [id, visibleIds.has(id)]),
      );
    }
  } catch {
    // A stale or blocked preference should fall back to the table defaults.
  }
  return undefined;
};

export const DataTable = <TData,>({
  table,
  caption,
  emptyMessage = "暂无数据",
  requiredColumnIds = [],
  layoutKey,
}: Props<TData>) => {
  const storageKey = `fip:table:${layoutKey}:v${VERSION}`;
  const restored = useRef(false);
  const columns = table.getAllLeafColumns();
  const hideableColumns = columns.filter((column) => column.getCanHide());
  const visibility = table.getState().columnVisibility;

  useEffect(() => {
    if (!restored.current) {
      restored.current = true;
      const visible = readVisibleIds(
        storageKey,
        new Set(hideableColumns.map((column) => column.id)),
        requiredColumnIds,
      );
      if (visible) table.setColumnVisibility(visible);
      return;
    }
    try {
      const visibleColumnIds = columns
        .filter((column) => column.getIsVisible())
        .map((column) => column.id);
      localStorage.setItem(
        storageKey,
        JSON.stringify({ version: VERSION, visibleColumnIds }),
      );
    } catch {
      // Layout preferences are optional and never block table use.
    }
  }, [
    columns,
    hideableColumns,
    requiredColumnIds,
    storageKey,
    table,
    visibility,
  ]);

  return (
    <section className={styles.tableSection} aria-label={caption}>
      {hideableColumns.length > 0 && (
        <div className={styles.tableToolbar}>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <button type="button" className={styles.columnButton}>
                <Columns3 size={16} aria-hidden="true" /> 列设置
              </button>
            </Menu.Target>
            <Menu.Dropdown aria-label="列显示设置">
              {hideableColumns.map((column) => {
                const header = column.columnDef.header;
                const label = typeof header === "string" ? header : column.id;
                const required = requiredColumnIds.includes(column.id);
                return (
                  <Menu.Item key={column.id} closeMenuOnClick={false}>
                    <Checkbox
                      label={label}
                      checked={column.getIsVisible()}
                      disabled={required}
                      onChange={column.getToggleVisibilityHandler()}
                      size="xs"
                    />
                  </Menu.Item>
                );
              })}
            </Menu.Dropdown>
          </Menu>
        </div>
      )}
      <ScrollArea type="auto" offsetScrollbars>
        <Table
          striped
          highlightOnHover
          withTableBorder
          withColumnBorders
          className={styles.dataTable}
        >
          <caption className={styles.caption}>{caption}</caption>
          <Table.Thead>
            {table.getHeaderGroups().map((group) => (
              <Table.Tr key={group.id}>
                {group.headers.map((header) => (
                  <Table.Th key={header.id} scope="col">
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </Table.Th>
                ))}
              </Table.Tr>
            ))}
          </Table.Thead>
          <Table.Tbody>
            {table.getRowModel().rows.length === 0 ? (
              <Table.Tr>
                <Table.Td
                  colSpan={Math.max(1, table.getVisibleLeafColumns().length)}
                >
                  {emptyMessage}
                </Table.Td>
              </Table.Tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <Table.Tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <Table.Td key={cell.id}>
                      {cell.renderValue() == null &&
                      "accessorKey" in cell.column.columnDef
                        ? "—"
                        : flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))
            )}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </section>
  );
};
