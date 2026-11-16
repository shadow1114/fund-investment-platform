import { ResearchDataTable } from "../../components/ResearchDataTable";
import { Button, SegmentedControl } from "@mantine/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Ban,
  CircleAlert,
  CircleCheck,
  CircleX,
  FileText,
  ListChecks,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { useState } from "react";

import type {
  FundIngestionTask,
  ListFundIngestionHistoryParams,
} from "../../api/generated/m17.schemas";
import { useRetryIngestionFailures } from "../../api/mutations";
import { getIngestionHistoryQueryOptions } from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";
import styles from "./DataIngestion.module.css";
import {
  datasetLabels,
  scopeLabels,
  type IngestionDataset,
} from "./IngestionScopeForm";

type Tone = "running" | "good" | "warning" | "critical" | "muted";

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

const statusTone = (task: FundIngestionTask): Tone =>
  task.status === "RUNNING"
    ? "running"
    : task.task_status === "PARTIAL_SUCCESS"
      ? "warning"
      : task.status === "COMPLETED"
        ? "good"
        : task.status === "CANCELLED"
          ? "muted"
          : "critical";

const statusIcon: Record<Tone, typeof CircleCheck> = {
  running: Loader2,
  good: CircleCheck,
  warning: CircleAlert,
  critical: CircleX,
  muted: Ban,
};

export const processedCount = (task: FundIngestionTask) => {
  const counts = [
    task.success_count,
    task.failure_count,
    task.skipped_count,
    task.cancelled_count,
  ];
  return counts.every((value) => typeof value === "number")
    ? counts.reduce<number>((sum, value) => sum + (value ?? 0), 0)
    : null;
};

export const IngestionCounts = ({ task }: { task: FundIngestionTask }) => (
  <span className={styles.cellSub}>
    成功 {task.success_count ?? "—"} · 失败 {task.failure_count ?? "—"} · 跳过{" "}
    {task.skipped_count ?? "—"} · 取消 {task.cancelled_count ?? "—"}
  </span>
);

const time = (value?: string | null) =>
  value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";

const duration = (task: FundIngestionTask, now: number) => {
  if (!task.started_at) return task.status === "RUNNING" ? "排队中" : "—";
  const end = task.finished_at ? Date.parse(task.finished_at) : now;
  const seconds = Math.max(
    0,
    Math.round((end - Date.parse(task.started_at)) / 1000),
  );
  const text =
    seconds >= 3600
      ? `${Math.floor(seconds / 3600)} 小时 ${Math.floor((seconds % 3600) / 60)} 分`
      : seconds >= 60
        ? `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
        : `${seconds} 秒`;
  return task.finished_at ? `耗时 ${text}` : `运行中（${text}）`;
};

const rangeText = (task: FundIngestionTask) => {
  if (task.dataset === "BENCHMARK")
    return `${task.start_date ?? "全部历史"} ~ ${task.end_date ?? "—"}`;
  return task.dataset === "NAV" ? "完整历史" : "最新快照";
};

const filters = [
  { value: "ALL", label: "全部" },
  { value: "RUNNING", label: "执行中" },
  { value: "COMPLETED", label: "已完成" },
  { value: "FAILED", label: "异常失败" },
];

export const IngestionHistoryTable = ({
  canManageAll,
  onOpen,
}: {
  canManageAll: boolean;
  onOpen: (operationId: string) => void;
}) => {
  const [params, setParams] = useState<ListFundIngestionHistoryParams>({
    page: 1,
    page_size: 20,
  });
  const query = useQuery({
    ...getIngestionHistoryQueryOptions(params),
    placeholderData: keepPreviousData,
    // 有运行中的任务时轮询，进度与计数由服务端返回。
    refetchInterval: (state) =>
      state.state.data?.items.some((task) => task.status === "RUNNING")
        ? 3000
        : false,
  });
  const retry = useRetryIngestionFailures();
  const now = query.dataUpdatedAt || Date.now();
  const items = query.data?.items ?? [];
  const running = items.filter((task) => task.status === "RUNNING").length;
  const canAct = (task: FundIngestionTask) =>
    task.scope_type !== "ALL" || canManageAll;

  return (
    <section className={styles.card} aria-labelledby="ingestion-history-title">
      <div className={styles.cardHeader}>
        <h2 className={styles.cardTitle} id="ingestion-history-title">
          <ListChecks size={16} />
          数据抓取任务执行状态
          {running > 0 && (
            <span className={styles.runningBadge} role="status">
              <Loader2 size={11} aria-hidden="true" />
              本页 {running} 个任务运行中
            </span>
          )}
        </h2>
        <div className={styles.gridFilters}>
          <SegmentedControl
            size="xs"
            aria-label="任务状态筛选"
            value={params.status ?? "ALL"}
            data={filters}
            onChange={(value) =>
              setParams((current) => ({
                ...current,
                page: 1,
                status:
                  value === "ALL"
                    ? undefined
                    : (value as ListFundIngestionHistoryParams["status"]),
              }))
            }
          />
        </div>
      </div>
      {query.isError && (
        <div className={styles.notice}>
          <ErrorState
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        </div>
      )}
      {retry.isError && (
        <div className={styles.notice}>
          <ErrorState error={retry.error} />
        </div>
      )}
      {query.data && (
        <div className={styles.gridBody}>
          <ResearchDataTable
            caption="数据抓取任务执行状态"
            showSettings={false}
            layoutKey="ingestion-history-v2"
            rowData={items}
            rowHeight={56}
            emptyMessage="当前筛选条件下暂无抓取任务记录"
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
                colId: "operation",
                headerName: "任务 ID",
                minWidth: 180,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.cellStack}>
                      <button
                        type="button"
                        className={styles.linkButton}
                        style={{ fontSize: 12, textAlign: "left" }}
                        onClick={() => onOpen(task.operation_id)}
                        aria-label={`查看任务 ${task.operation_id}`}
                      >
                        <span className={styles.mono}>{task.operation_id}</span>
                      </button>
                      <span className={styles.cellSub}>
                        提交人 {task.actor}
                      </span>
                    </div>
                  ) : null,
              },
              {
                colId: "dataset",
                headerName: "抓取数据类型",
                width: 130,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.cellStack}>
                      <span>
                        <span
                          className={styles.typeBadge}
                          data-dataset={task.dataset}
                        >
                          {datasetLabels[task.dataset as IngestionDataset] ??
                            task.dataset}
                        </span>
                      </span>
                    </div>
                  ) : null,
              },
              {
                colId: "scope",
                headerName: "目标标的",
                minWidth: 140,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.cellStack}>
                      <span>
                        {task.dataset === "BENCHMARK"
                          ? "基准指数"
                          : task.scope_type
                            ? scopeLabels[task.scope_type]
                            : "历史任务"}
                        <span className={styles.cellSub}>
                          {" "}
                          · 共 {task.requested_count} 项
                        </span>
                      </span>
                      <span className={styles.cellSub}>来源 {task.source}</span>
                    </div>
                  ) : null,
              },
              {
                colId: "range",
                headerName: "时间区间",
                width: 190,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.cellStack}>
                      <span className={styles.mono}>{rangeText(task)}</span>
                    </div>
                  ) : null,
              },
              {
                colId: "status",
                headerName: "任务状态",
                width: 140,
                cellRenderer: ({
                  data: task,
                }: {
                  data?: FundIngestionTask;
                }) => {
                  if (!task) return null;
                  const tone = statusTone(task);
                  const Icon = statusIcon[tone];
                  return (
                    <div className={styles.cellStack}>
                      <span>
                        <span className={styles.statusBadge} data-tone={tone}>
                          <Icon size={11} aria-hidden="true" />
                          {ingestionStatusLabel(task)}
                        </span>
                      </span>
                    </div>
                  );
                },
              },
              {
                colId: "progress",
                headerName: "抓取进度",
                minWidth: 200,
                cellRenderer: ({
                  data: task,
                }: {
                  data?: FundIngestionTask;
                }) => {
                  if (!task) return null;
                  const done = processedCount(task);
                  const percent =
                    done !== null && task.requested_count > 0
                      ? Math.round((done / task.requested_count) * 100)
                      : null;
                  return (
                    <div className={styles.cellStack}>
                      <div className={styles.progress}>
                        <div
                          className={styles.progressTrack}
                          role="progressbar"
                          aria-label={`任务 ${task.operation_id} 进度`}
                          aria-valuemin={0}
                          aria-valuemax={task.requested_count}
                          aria-valuenow={done ?? undefined}
                        >
                          <div
                            className={styles.progressFill}
                            data-tone={statusTone(task)}
                            style={{ width: `${percent ?? 0}%` }}
                          />
                        </div>
                        <span className={styles.progressText}>
                          {percent === null ? "—" : `${percent}%`}
                        </span>
                      </div>
                      <IngestionCounts task={task} />
                    </div>
                  );
                },
              },
              {
                colId: "time",
                headerName: "提交时间 / 耗时",
                width: 180,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.cellStack}>
                      <span className={styles.mono}>
                        {time(task.created_at)}
                      </span>
                      <span className={styles.cellSub}>
                        {duration(task, now)}
                      </span>
                    </div>
                  ) : null,
              },
              {
                colId: "actions",
                headerName: "操作",
                width: 190,
                cellRenderer: ({ data: task }: { data?: FundIngestionTask }) =>
                  task ? (
                    <div className={styles.rowActions}>
                      <Button
                        size="compact-xs"
                        variant="default"
                        leftSection={<FileText size={12} />}
                        onClick={() => onOpen(task.operation_id)}
                        aria-label={`查看任务 ${task.operation_id} 的日志`}
                      >
                        日志
                      </Button>
                      {canAct(task) &&
                        task.status !== "RUNNING" &&
                        (task.failure_count ?? 0) > 0 && (
                          <Button
                            size="compact-xs"
                            variant="light"
                            color="orange"
                            leftSection={<RotateCcw size={12} />}
                            loading={
                              retry.isPending &&
                              retry.variables === task.operation_id
                            }
                            onClick={() =>
                              retry.mutate(task.operation_id, {
                                onSuccess: (submission) =>
                                  onOpen(submission.operation_id),
                              })
                            }
                            aria-label={`重试任务 ${task.operation_id} 的失败项`}
                          >
                            重试
                          </Button>
                        )}
                    </div>
                  ) : null,
              },
            ]}
          />
        </div>
      )}
      {query.isPending && (
        <div className={styles.notice} role="status">
          正在读取抓取任务…
        </div>
      )}
    </section>
  );
};
