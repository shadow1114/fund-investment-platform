import {
  Button,
  Group,
  NativeSelect,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type {
  FundIngestionTask,
  ListFundIngestionHistoryParams,
} from "../../api/generated/m17.schemas";
import { getIngestionHistoryQueryOptions } from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";
import { datasetLabels, scopeLabels } from "./IngestionScopeForm";

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
export const IngestionHistoryTable = ({
  onLatest,
}: {
  onLatest?: (task: FundIngestionTask | undefined) => void;
}) => {
  const [params, setParams] = useState<ListFundIngestionHistoryParams>({
    page: 1,
    page_size: 20,
  });
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const invalidDates = Boolean(from && to && from > to);
  const query = useQuery(getIngestionHistoryQueryOptions(params));
  const latest = query.data?.items[0];
  useEffect(() => {
    onLatest?.(latest);
  }, [latest, onLatest]);
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
            onChange={(event) =>
              setParams((current) => ({
                ...current,
                dataset: (event.currentTarget.value ||
                  undefined) as typeof params.dataset,
                page: 1,
              }))
            }
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
            onChange={(event) =>
              setParams((current) => ({
                ...current,
                status: (event.currentTarget.value ||
                  undefined) as typeof params.status,
                page: 1,
              }))
            }
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
            onChange={(event) =>
              setParams((current) => ({
                ...current,
                scope_type: (event.currentTarget.value ||
                  undefined) as typeof params.scope_type,
                page: 1,
              }))
            }
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
                created_to: to
                  ? new Date(`${to}T23:59:59.999`).toISOString()
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
        {query.data && query.data.items.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <Table>
              <Table.Caption>基金抓取任务历史</Table.Caption>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>任务 / 提交时间</Table.Th>
                  <Table.Th>数据集 / 范围</Table.Th>
                  <Table.Th>状态 / 项数</Table.Th>
                  <Table.Th>来源 / 提交人</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {query.data.items.map((task) => (
                  <Table.Tr key={task.operation_id}>
                    <Table.Td>
                      <Link
                        to={`/data-ingestion?operation_id=${encodeURIComponent(task.operation_id)}`}
                      >
                        {task.operation_id}
                      </Link>
                      <Text size="sm">
                        {new Date(task.created_at).toLocaleString("zh-CN")}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {datasetLabels[task.dataset]}
                      <Text size="sm">
                        {task.scope_type
                          ? scopeLabels[task.scope_type]
                          : "历史任务"}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {ingestionStatusLabel(task)}
                      <IngestionCounts task={task} />
                    </Table.Td>
                    <Table.Td>
                      {task.source}
                      <Text size="sm">{task.actor}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </div>
        )}
        {query.data && (
          <Group>
            <Button
              variant="default"
              disabled={query.data.page <= 1 || query.isFetching}
              onClick={() =>
                setParams((current) => ({
                  ...current,
                  page: query.data!.page - 1,
                }))
              }
            >
              历史上一页
            </Button>
            <Text>
              第 {query.data.page} 页 · 共 {query.data.total} 项任务
            </Text>
            <Button
              variant="default"
              disabled={
                query.data.page * query.data.page_size >= query.data.total ||
                query.isFetching
              }
              onClick={() =>
                setParams((current) => ({
                  ...current,
                  page: query.data!.page + 1,
                }))
              }
            >
              历史下一页
            </Button>
          </Group>
        )}
      </Stack>
    </section>
  );
};
