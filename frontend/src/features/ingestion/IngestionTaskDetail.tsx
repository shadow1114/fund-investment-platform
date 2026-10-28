import {
  Button,
  Group,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { ListFundIngestionItemsParams } from "../../api/generated/m17.schemas";
import {
  useCancelIngestion,
  useRetryIngestionFailures,
} from "../../api/mutations";
import {
  getIngestionItemsQueryOptions,
  getIngestionTaskQueryOptions,
  ingestionKeys,
} from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";
import { IngestionCounts, ingestionStatusLabel } from "./IngestionHistoryTable";
import { datasetLabels, scopeLabels } from "./IngestionScopeForm";

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
  const items = useQuery(
    getIngestionItemsQueryOptions(
      task ? operationId : "",
      params,
      task?.status === "RUNNING",
    ),
  );
  const cancel = useCancelIngestion();
  const retry = useRetryIngestionFailures();
  const [confirmCancel, setConfirmCancel] = useState(false);
  const refreshedTerminal = useRef<string>();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [operationId, query.isSuccess]);
  useEffect(() => {
    if (
      !task ||
      task.status === "RUNNING" ||
      refreshedTerminal.current === operationId
    )
      return;
    refreshedTerminal.current = operationId;
    // Prefix invalidation reaches every as-of-date, NAV and basic-info variant.
    // ALL must not enumerate fund IDs in the browser.
    void Promise.all([
      client.invalidateQueries({ queryKey: ["api", "funds"] }),
      client.invalidateQueries({ queryKey: ["fund-research"] }),
      ...["fund-detail", "fund-nav", "fund-evaluation", "fund-score"].map(
        (prefix) => client.invalidateQueries({ queryKey: [prefix] }),
      ),
      client.invalidateQueries({ queryKey: ingestionKeys.history }),
      client.invalidateQueries({ queryKey: ingestionKeys.items(operationId) }),
    ]);
  }, [task, operationId, client]);
  const canAct = Boolean(task && (task.scope_type !== "ALL" || canManageAll));
  return (
    <section aria-labelledby="ingestion-task-title">
      <h2 id="ingestion-task-title" tabIndex={-1} ref={heading}>
        任务 {operationId}
      </h2>
      <Stack>
        <Group>
          <Button component={Link} to="/data-ingestion" variant="default">
            新建抓取任务
          </Button>
          <Button
            variant="default"
            loading={query.isFetching}
            onClick={() => {
              void query.refetch();
              void items.refetch();
            }}
          >
            刷新任务
          </Button>
        </Group>
        {query.isPending && <Text role="status">正在恢复任务详情…</Text>}
        {query.isError && (
          <ErrorState
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        )}
        {task && (
          <>
            <Text fw={600}>{ingestionStatusLabel(task)}</Text>
            <Text>
              {datasetLabels[task.dataset]} ·{" "}
              {task.scope_type ? scopeLabels[task.scope_type] : "历史任务"} ·
              来源：{task.source} · 提交人：{task.actor}
            </Text>
            <Text size="sm">
              提交：{new Date(task.created_at).toLocaleString("zh-CN")}
              {task.finished_at
                ? ` · 结束：${new Date(task.finished_at).toLocaleString("zh-CN")}`
                : ""}
            </Text>
            {task.parent_operation_id && (
              <Text>
                失败重试来源：
                <Link
                  to={`/data-ingestion?operation_id=${encodeURIComponent(task.parent_operation_id)}`}
                >
                  {task.parent_operation_id}
                </Link>
              </Text>
            )}
            <IngestionCounts task={task} />
            {task.status === "RUNNING" && (
              <Text size="sm">
                后台每批最多处理 50
                项；已完成计数由服务端返回。取消后保留当前项和已写入的数据。
              </Text>
            )}
            {task.failure && <Text role="alert">{task.failure}</Text>}
            {!canAct && (
              <Text role="status">当前身份没有管理全量任务的权限。</Text>
            )}
            <Group>
              {canAct && task.status === "RUNNING" && (
                <Button
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
              <Text role="status">
                取消请求已接收，后台完成当前项后停止未处理项。
              </Text>
            )}
            {cancel.isError && <ErrorState error={cancel.error} />}
            {retry.isError && <ErrorState error={retry.error} />}
            <h3>基金 / 份额类别结果</h3>
            <NativeSelect
              label="项级结果状态"
              value={params.status ?? ""}
              data={[
                { value: "", label: "全部结果" },
                ...[
                  { value: "PENDING", label: "待处理" },
                  { value: "RUNNING", label: "处理中" },
                  { value: "SUCCESS", label: "成功" },
                  { value: "FAILED", label: "失败" },
                  { value: "SKIPPED", label: "跳过" },
                  { value: "CANCELLED", label: "取消" },
                ],
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
            {items.isFetching && <Text role="status">正在读取项级结果…</Text>}
            {items.isError && (
              <ErrorState
                error={items.error}
                onRetry={() => void items.refetch()}
              />
            )}
            {items.data?.items.length === 0 && (
              <Text>暂无符合条件的项级结果。</Text>
            )}
            {items.data && items.data.items.length > 0 && (
              <div style={{ overflowX: "auto" }}>
                <Table>
                  <Table.Caption>抓取项级结果</Table.Caption>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>基金 / 份额类别</Table.Th>
                      <Table.Th>状态 / 尝试次数</Table.Th>
                      <Table.Th>来源结果 / 日期 / 错误</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {items.data.items.map((item) => (
                      <Table.Tr key={item.id}>
                        <Table.Td>
                          <Link
                            to={`/funds/${encodeURIComponent(item.fund_id)}`}
                          >
                            {item.fund_id}
                          </Link>
                          <Text size="sm">
                            份额 {item.share_class_id ?? "不适用"} · 来源代码{" "}
                            {item.symbol ?? "—"}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          {item.status}
                          <Text size="sm">尝试 {item.attempts} 次</Text>
                        </Table.Td>
                        <Table.Td>
                          {item.error && <Text c="red">{item.error}</Text>}
                          {item.result && (
                            <dl>
                              {Object.entries(item.result).map(
                                ([key, value]) => (
                                  <div key={key}>
                                    <dt>{key}</dt>
                                    <dd>
                                      {value == null
                                        ? "—"
                                        : typeof value === "object"
                                          ? JSON.stringify(value)
                                          : String(value)}
                                    </dd>
                                  </div>
                                ),
                              )}
                            </dl>
                          )}
                          {!item.error && !item.result && "等待结果"}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </div>
            )}
            {items.data && (
              <Group>
                <Button
                  variant="default"
                  disabled={items.data.page <= 1 || items.isFetching}
                  onClick={() =>
                    setParams({ ...params, page: items.data!.page - 1 })
                  }
                >
                  结果上一页
                </Button>
                <Text>
                  第 {items.data.page} 页 · 共 {items.data.total} 项结果
                </Text>
                <Button
                  variant="default"
                  disabled={
                    items.data.page * items.data.page_size >=
                      items.data.total || items.isFetching
                  }
                  onClick={() =>
                    setParams({ ...params, page: items.data!.page + 1 })
                  }
                >
                  结果下一页
                </Button>
              </Group>
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
          <Text>后台完成当前项后，停止剩余未处理项。已完成的数据会保留。</Text>
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
