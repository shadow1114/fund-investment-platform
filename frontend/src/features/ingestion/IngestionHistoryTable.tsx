import { ResearchDataTable } from "../../components/ResearchDataTable";
import {
  Button,
  Group,
  NativeSelect,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import type {
  FundIngestionTask,
  ListFundIngestionHistoryParams,
} from "../../api/generated/m17.schemas";
import { getIngestionHistoryQueryOptions } from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";
import { datasetLabels, scopeLabels } from "./IngestionScopeForm";

type taskRow = FundIngestionTask;

export const ingestionStatusLabel = (task: FundIngestionTask) =>
  task.task_status === "PARTIAL_SUCCESS"
    ? "部分成功"
    : ({
        RUNNING: "排队中或抓取中",
        COMPLETED: "完成",
        FAILED: "失败",
        CANCELLED: "已取消",
        BLOCKED: "被数据质量阻断",
      }[task.status] ?? task.status);
export const IngestionCounts = ({ task }: { task: FundIngestionTask }) => {
  const counts = [
    task.success_count,
    task.failure_count,
    task.skipped_count,
    task.cancelled_count,
  ];
  const completed = counts.every((value) => typeof value === "number")
    ? counts.reduce<number>((sum, value) => sum + (value ?? 0), 0)
    : null;
  return (
    <>
      <Text>
        已处理 {completed ?? "暂不可用"} / {task.requested_count} 项
      </Text>
      <Text size="sm">
        成功 {task.success_count ?? "—"} · 失败 {task.failure_count ?? "—"} ·
        跳过 {task.skipped_count ?? "—"} · 取消 {task.cancelled_count ?? "—"}
      </Text>
    </>
  );
};
export const IngestionHistoryTable = () => {
  const [params, setParams] = useState<ListFundIngestionHistoryParams>({
    page: 1,
    page_size: 20,
  });
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const invalidDates = Boolean(from && to && from > to);
  const query = useQuery({
    ...getIngestionHistoryQueryOptions(params),
    placeholderData: keepPreviousData,
  });
  const latest = query.data?.items[0];
  return (
    <section aria-labelledby="ingestion-history-title">
      <h2 id="ingestion-history-title">抓取历史</h2>
      <Stack>
        <Group align="end">
          <NativeSelect
            label="历史数据集"
            value={params.dataset ?? ""}
            data={[
              { value: "", label: "全部数据集" },
              ...Object.entries(datasetLabels).map(([value, label]) => ({
                value,
                label,
              })),
            ]}
            onChange={(event) => {
              const value = (event.currentTarget.value ||
                undefined) as typeof params.dataset;
              setParams((current) => ({ ...current, dataset: value, page: 1 }));
            }}
          />
          <NativeSelect
            label="历史状态"
            value={params.status ?? ""}
            data={[
              { value: "", label: "全部状态" },
              { value: "RUNNING", label: "运行中" },
              { value: "COMPLETED", label: "完成（含部分成功）" },
              { value: "FAILED", label: "失败" },
              { value: "CANCELLED", label: "已取消" },
              { value: "BLOCKED", label: "阻断" },
            ]}
            onChange={(event) => {
              const value = (event.currentTarget.value ||
                undefined) as typeof params.status;
              setParams((current) => ({ ...current, status: value, page: 1 }));
            }}
          />
          <NativeSelect
            label="历史范围"
            value={params.scope_type ?? ""}
            data={[
              { value: "", label: "全部范围" },
              ...Object.entries(scopeLabels).map(([value, label]) => ({
                value,
                label,
              })),
            ]}
            onChange={(event) => {
              const value = (event.currentTarget.value ||
                undefined) as typeof params.scope_type;
              setParams((current) => ({
                ...current,
                scope_type: value,
                page: 1,
              }));
            }}
          />
        </Group>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!invalidDates)
              setParams((current) => ({
                ...current,
                page: 1,
                created_from: from
                  ? new Date(`${from}T00:00:00`).toISOString()
                  : undefined,
                // Preserve the final PostgreSQL microsecond of the selected local day.
                created_to: to
                  ? new Date(`${to}T23:59:59.999`)
                      .toISOString()
                      .replace(".999Z", ".999999Z")
                  : undefined,
              }));
          }}
        >
          <Group align="end">
            <TextInput
              type="date"
              label="提交日期从"
              value={from}
              onChange={(event) => setFrom(event.currentTarget.value)}
            />
            <TextInput
              type="date"
              label="提交日期至"
              value={to}
              onChange={(event) => setTo(event.currentTarget.value)}
            />
            <Button type="submit" variant="default" disabled={invalidDates}>
              应用时间筛选
            </Button>
          </Group>
          {invalidDates && <Text role="alert">开始日期不能晚于结束日期。</Text>}
        </form>
        {query.isFetching && <Text role="status">正在读取抓取历史…</Text>}
        {query.isError && (
          <ErrorState
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        )}
        {query.data?.items.length === 0 && (
          <Text>暂无符合条件的抓取任务。</Text>
        )}
        {latest && (
          <Text size="sm" c="dimmed">
            本页最近任务：{new Date(latest.created_at).toLocaleString("zh-CN")}
          </Text>
        )}
        {query.data && (
          <ResearchDataTable
            caption="基金抓取任务历史"
            layoutKey="ingestion-history"
            rowData={query.data.items}
            rowHeight={120}
            serverPagination={{
              page: params.page ?? 1,
              pageSize: query.data.page_size,
              total: query.data.total,
              loading: query.isFetching,
              failed: query.isError,
              resetKey: JSON.stringify({ ...params, page: undefined }),
              onPageChange: (page) =>
                setParams((current) => ({ ...current, page })),
            }}
            getRowId={({ data }) => data.operation_id}
            columnDefs={[
              {
                colId: "column0",
                headerName: "任务 / 提交时间",
                wrapText: true,
                cellRenderer: ({ data: task }: { data?: taskRow }) =>
                  task ? (
                    <div
                      style={{
                        maxHeight: 110,
                        overflow: "auto",
                        whiteSpace: "normal",
                      }}
                    >
                      <Link
                        to={`/data-ingestion?operation_id=${encodeURIComponent(task.operation_id)}`}
                      >
                        {task.operation_id}
                      </Link>
                      <Text size="sm">
                        {new Date(task.created_at).toLocaleString("zh-CN")}
                      </Text>
                    </div>
                  ) : null,
              },
              {
                colId: "column1",
                headerName: "数据集 / 范围",
                wrapText: true,
                cellRenderer: ({ data: task }: { data?: taskRow }) =>
                  task ? (
                    <div
                      style={{
                        maxHeight: 110,
                        overflow: "auto",
                        whiteSpace: "normal",
                      }}
                    >
                      {datasetLabels[task.dataset]}
                      <Text size="sm">
                        {task.scope_type
                          ? scopeLabels[task.scope_type]
                          : "历史任务"}
                      </Text>
                    </div>
                  ) : null,
              },
              {
                colId: "column2",
                headerName: "状态 / 项数",
                wrapText: true,
                cellRenderer: ({ data: task }: { data?: taskRow }) =>
                  task ? (
                    <div
                      style={{
                        maxHeight: 110,
                        overflow: "auto",
                        whiteSpace: "normal",
                      }}
                    >
                      {ingestionStatusLabel(task)}
                      <IngestionCounts task={task} />
                    </div>
                  ) : null,
              },
              {
                colId: "column3",
                headerName: "来源 / 提交人",
                wrapText: true,
                cellRenderer: ({ data: task }: { data?: taskRow }) =>
                  task ? (
                    <div
                      style={{
                        maxHeight: 110,
                        overflow: "auto",
                        whiteSpace: "normal",
                      }}
                    >
                      {task.source}
                      <Text size="sm">{task.actor}</Text>
                    </div>
                  ) : null,
              },
            ]}
          />
        )}
      </Stack>
    </section>
  );
};
