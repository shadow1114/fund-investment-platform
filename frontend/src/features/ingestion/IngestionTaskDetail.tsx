import { ResearchDataTable } from "../../components/ResearchDataTable";
import { Button, Group, Modal, NativeSelect, Stack, Text } from "@mantine/core";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type {
  FundIngestionRunItem,
  ListFundIngestionItemsParams,
} from "../../api/generated/m17.schemas";
import {
  useCancelIngestion,
  useRetryIngestionFailures,
} from "../../api/mutations";
import {
  getIngestionItemsQueryOptions,
  getIngestionTaskQueryOptions,
  ingestionKeys,
  invalidateIngestionFundData,
} from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";
import styles from "./DataIngestion.module.css";
import {
  IngestionCounts,
  ingestionStatusLabel,
  processedCount,
} from "./IngestionHistoryTable";
import {
  datasetLabels,
  scopeLabels,
  type IngestionDataset,
} from "./IngestionScopeForm";

type itemRow = FundIngestionRunItem;

const itemStatusLabels: Record<string, string> = {
  PENDING: "待处理",
  RUNNING: "处理中",
  SUCCESS: "成功",
  FAILED: "失败",
  SKIPPED: "跳过",
  CANCELLED: "取消",
};
const itemTone: Record<string, string> = {
  PENDING: "muted",
  RUNNING: "running",
  SUCCESS: "good",
  FAILED: "critical",
  SKIPPED: "warning",
  CANCELLED: "muted",
};

const resultLabels: Record<string, string> = {
  source: "数据来源",
  dataset: "数据集",
  row_count: "返回行数",
  inserted_count: "新增版本",
  unchanged_count: "未变化",
  first_date: "起始日期",
  last_date: "截止日期",
  error_code: "错误代码",
  retryable: "可重试",
};

export const IngestionTaskDetail = ({
  operationId,
  canManageAll,
  onOperation,
}: {
  operationId: string;
  canManageAll: boolean;
  onOperation: (id: string) => void;
}) => {
  const client = useQueryClient();
  const query = useQuery(getIngestionTaskQueryOptions(operationId));
  const task = query.data;
  const [params, setParams] = useState<ListFundIngestionItemsParams>({
    page: 1,
    page_size: 20,
  });
  const items = useQuery({
    ...getIngestionItemsQueryOptions(
      task ? operationId : "",
      params,
      task?.status === "RUNNING",
    ),
    placeholderData: keepPreviousData,
  });
  const cancel = useCancelIngestion();
  const retry = useRetryIngestionFailures();
  const [confirmCancel, setConfirmCancel] = useState(false);
  const refreshedTerminal = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (
      !task ||
      task.status === "RUNNING" ||
      refreshedTerminal.current === operationId
    )
      return;
    refreshedTerminal.current = operationId;
    // 前缀失效覆盖所有观察日、NAV、基本信息及基准对比变体；全量任务不在浏览器枚举基金。
    void Promise.all([
      invalidateIngestionFundData(client),
      client.invalidateQueries({ queryKey: ingestionKeys.history }),
      client.invalidateQueries({ queryKey: ingestionKeys.items(operationId) }),
    ]);
  }, [task, operationId, client]);
  const canAct = Boolean(task && (task.scope_type !== "ALL" || canManageAll));
  const done = task ? processedCount(task) : null;

  return (
    <section aria-labelledby="ingestion-task-title">
      <h2 id="ingestion-task-title" className={styles.visuallyHidden}>
        任务 {operationId}
      </h2>
      <Stack gap="sm">
        {query.isPending && <Text role="status">正在恢复任务详情…</Text>}
        {query.isError && (
          <ErrorState
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        )}
        {task && (
          <>
            <dl className={styles.previewList}>
              <dt>任务状态</dt>
              <dd>
                <strong>{ingestionStatusLabel(task)}</strong>
              </dd>
              <dt>数据类型</dt>
              <dd>
                {datasetLabels[task.dataset as IngestionDataset] ??
                  task.dataset}
                {" · "}
                {task.dataset === "BENCHMARK"
                  ? "基准指数"
                  : task.scope_type
                    ? scopeLabels[task.scope_type]
                    : "历史任务"}
              </dd>
              {task.dataset === "BENCHMARK" && (
                <>
                  <dt>时间区间</dt>
                  <dd>
                    {task.start_date ?? "全部可得历史"} 至{" "}
                    {task.end_date ?? "—"}
                  </dd>
                </>
              )}
              <dt>来源 / 提交人</dt>
              <dd>
                {task.source} · {task.actor}
              </dd>
              <dt>时间</dt>
              <dd>
                提交 {new Date(task.created_at).toLocaleString("zh-CN")}
                {task.finished_at
                  ? ` · 结束 ${new Date(task.finished_at).toLocaleString("zh-CN")}`
                  : ""}
              </dd>
              <dt>处理进度</dt>
              <dd>
                已处理 {done ?? "暂不可用"} / {task.requested_count} 项 ·{" "}
                <IngestionCounts task={task} />
              </dd>
              {task.parent_operation_id && (
                <>
                  <dt>失败重试来源</dt>
                  <dd>
                    <button
                      type="button"
                      className={styles.linkButton}
                      onClick={() => onOperation(task.parent_operation_id!)}
                    >
                      {task.parent_operation_id}
                    </button>
                  </dd>
                </>
              )}
            </dl>
            {task.status === "RUNNING" && (
              <Text size="xs" c="dimmed">
                后台分批处理；已完成计数由服务端返回。取消后保留当前项和已写入的数据。
              </Text>
            )}
            {task.failure && (
              <Text role="alert" size="sm" c="red">
                {task.failure}
              </Text>
            )}
            {!canAct && (
              <Text role="status" size="sm">
                当前身份没有管理全量任务的权限。
              </Text>
            )}
            <Group gap="xs">
              <Button
                size="xs"
                variant="default"
                loading={query.isFetching}
                onClick={() => {
                  void query.refetch();
                  void items.refetch();
                }}
              >
                刷新任务
              </Button>
              {canAct && task.status === "RUNNING" && (
                <Button
                  size="xs"
                  variant="default"
                  disabled={cancel.isPending}
                  onClick={() => setConfirmCancel(true)}
                >
                  取消未完成项
                </Button>
              )}
              {canAct &&
                task.status !== "RUNNING" &&
                (task.failure_count ?? 0) > 0 && (
                  <Button
                    size="xs"
                    loading={retry.isPending}
                    onClick={() =>
                      retry.mutate(operationId, {
                        onSuccess: (submission) =>
                          onOperation(submission.operation_id),
                      })
                    }
                  >
                    仅重试失败项
                  </Button>
                )}
            </Group>
            {cancel.isSuccess && (
              <Text role="status" size="sm">
                取消请求已接收，后台完成当前项后停止未处理项。
              </Text>
            )}
            {cancel.isError && <ErrorState error={cancel.error} />}
            {retry.isError && <ErrorState error={retry.error} />}
            <Group justify="space-between" align="end">
              <h3 style={{ margin: 0, fontSize: 13 }}>
                {task.dataset === "BENCHMARK"
                  ? "基准指数结果"
                  : "基金 / 份额类别结果"}
              </h3>
              <NativeSelect
                size="xs"
                label="项级结果状态"
                value={params.status ?? ""}
                data={[
                  { value: "", label: "全部结果" },
                  ...Object.entries(itemStatusLabels).map(([value, label]) => ({
                    value,
                    label,
                  })),
                ]}
                onChange={(event) =>
                  setParams({
                    ...params,
                    page: 1,
                    status: (event.currentTarget.value ||
                      undefined) as typeof params.status,
                  })
                }
              />
            </Group>
            {items.isFetching && (
              <Text role="status" size="xs" c="dimmed">
                正在读取项级结果…
              </Text>
            )}
            {items.isError && (
              <ErrorState
                error={items.error}
                onRetry={() => void items.refetch()}
              />
            )}
            {items.data && (
              <ResearchDataTable
                caption="抓取项级结果"
                layoutKey="ingestion-items-v2"
                rowData={items.data.items}
                rowHeight={96}
                emptyMessage="暂无符合条件的项级结果"
                serverPagination={{
                  page: params.page ?? 1,
                  pageSize: items.data.page_size,
                  total: items.data.total,
                  loading: items.isFetching,
                  failed: items.isError,
                  resetKey: `${operationId}:${params.status ?? ""}`,
                  onPageChange: (page) =>
                    setParams((current) => ({ ...current, page })),
                }}
                getRowId={({ data }) => String(data.id)}
                columnDefs={[
                  {
                    colId: "subject",
                    headerName:
                      task.dataset === "BENCHMARK"
                        ? "基准指数"
                        : "基金 / 份额类别",
                    minWidth: 200,
                    cellRenderer: ({ data: item }: { data?: itemRow }) =>
                      item ? (
                        <div className={styles.cellStack}>
                          {item.subject_type === "BENCHMARK" ? (
                            <span>
                              {item.subject_name ?? item.symbol ?? "—"}
                            </span>
                          ) : item.fund_id ? (
                            <Link
                              to={`/funds/${encodeURIComponent(item.fund_id)}`}
                            >
                              {item.fund_id}
                            </Link>
                          ) : (
                            <span>—</span>
                          )}
                          <span className={styles.cellSub}>
                            {item.subject_type === "BENCHMARK"
                              ? `代码 ${item.symbol ?? "—"}`
                              : `份额 ${item.share_class_id ?? "不适用"} · 来源代码 ${item.symbol ?? "—"}`}
                          </span>
                        </div>
                      ) : null,
                  },
                  {
                    colId: "status",
                    headerName: "状态 / 尝试次数",
                    width: 140,
                    cellRenderer: ({ data: item }: { data?: itemRow }) =>
                      item ? (
                        <div className={styles.cellStack}>
                          <span>
                            <span
                              className={styles.statusBadge}
                              data-tone={itemTone[item.status]}
                            >
                              {itemStatusLabels[item.status] ?? item.status}
                            </span>
                          </span>
                          <span className={styles.cellSub}>
                            尝试 {item.attempts} 次
                          </span>
                        </div>
                      ) : null,
                  },
                  {
                    colId: "result",
                    headerName: "来源结果 / 错误",
                    minWidth: 260,
                    flex: 1,
                    cellRenderer: ({ data: item }: { data?: itemRow }) =>
                      item ? (
                        <div
                          className={styles.cellStack}
                          style={{
                            overflow: "auto",
                            justifyContent: "flex-start",
                            paddingBlock: 6,
                          }}
                        >
                          {item.error && (
                            <Text size="xs" c="red">
                              {item.error}
                            </Text>
                          )}
                          {item.result && (
                            <dl
                              className={styles.previewList}
                              style={{ fontSize: 11 }}
                            >
                              {Object.entries(item.result)
                                .filter(([key]) => key !== "error")
                                .map(([key, value]) => (
                                  <div
                                    key={key}
                                    style={{ display: "contents" }}
                                  >
                                    <dt>{resultLabels[key] ?? key}</dt>
                                    <dd>
                                      {value == null
                                        ? "—"
                                        : typeof value === "object"
                                          ? JSON.stringify(value)
                                          : String(value)}
                                    </dd>
                                  </div>
                                ))}
                            </dl>
                          )}
                          {!item.error && !item.result && (
                            <span className={styles.cellSub}>等待结果</span>
                          )}
                        </div>
                      ) : null,
                  },
                ]}
              />
            )}
          </>
        )}
      </Stack>
      <Modal
        opened={confirmCancel}
        onClose={() => {
          if (!cancel.isPending) setConfirmCancel(false);
        }}
        title="取消未完成抓取项"
        centered
      >
        <Stack>
          <Text size="sm">
            后台完成当前项后，停止剩余未处理项。已完成的数据会保留。
          </Text>
          <Group justify="flex-end">
            <Button
              variant="default"
              disabled={cancel.isPending}
              onClick={() => setConfirmCancel(false)}
            >
              继续抓取
            </Button>
            <Button
              loading={cancel.isPending}
              onClick={() =>
                cancel.mutate(operationId, {
                  onSuccess: () => setConfirmCancel(false),
                })
              }
            >
              确认取消
            </Button>
          </Group>
        </Stack>
      </Modal>
    </section>
  );
};
