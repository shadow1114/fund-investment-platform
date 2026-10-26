import { Alert, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { getOperationQueryOptions } from "../api/queries";
import { ErrorState } from "./ErrorState";
import { StatusBadge } from "./StatusBadge";

type Props = {
  operationId: string;
  resultRef?: string | null;
  pollIntervalMs?: number;
};

export const OperationProgress = ({
  operationId,
  resultRef,
  pollIntervalMs = 1000,
}: Props) => {
  const pollCount = useRef(0);
  const [pollingPaused, setPollingPaused] = useState(false);
  const query = useQuery({
    ...getOperationQueryOptions(operationId),
    refetchInterval: (current) => {
      if (current.state.data?.status !== "RUNNING") return false;
      if (pollCount.current >= 60) {
        setPollingPaused(true);
        return false;
      }
      pollCount.current += 1;
      return pollIntervalMs;
    },
  });
  const operation = query.data;

  if (query.isPending) return <Text role="status">正在读取任务状态…</Text>;
  if (query.isError)
    return (
      <ErrorState error={query.error} onRetry={() => void query.refetch()} />
    );
  if (!operation) return null;

  const stillRunning = operation.status === "RUNNING";
  return (
    <Paper withBorder radius="sm" p="md" aria-label="操作进度">
      <Stack gap="sm">
        <Group justify="space-between">
          <Group gap="sm">
            <Text fw={600}>后台任务</Text>
            <StatusBadge domain="operation" value={operation.status} />
          </Group>
          {stillRunning && pollingPaused && (
            <Button
              type="button"
              size="xs"
              variant="default"
              onClick={() => {
                pollCount.current = 0;
                setPollingPaused(false);
                void query.refetch();
              }}
            >
              继续查询
            </Button>
          )}
        </Group>
        <Text size="sm">任务 ID：{operation.operation_id}</Text>
        {operation.progress && (
          <Text size="sm" c="dimmed">
            已完成 {operation.progress.completed} /{" "}
            {operation.progress.total ?? "未知总数"}{" "}
            {operation.progress.unit ?? "项"}
          </Text>
        )}
        {(operation.result_ref ?? resultRef) && (
          <Text size="sm">结果资源：{operation.result_ref ?? resultRef}</Text>
        )}
        {operation.failure && (
          <Alert color="red" variant="light" title="任务失败">
            {operation.failure.code}：{operation.failure.message}
          </Alert>
        )}
        {stillRunning && pollingPaused && (
          <Text size="xs" c="dimmed">
            自动查询已暂停；任务仍为运行状态，查询数量不等同于百分比进度。
          </Text>
        )}
      </Stack>
    </Paper>
  );
};
