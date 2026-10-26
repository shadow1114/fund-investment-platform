import { Alert, Loader, Stack, Text } from "@mantine/core";
import type { ReactNode } from "react";

import { ErrorState } from "./ErrorState";

type Props = {
  loading?: boolean;
  refreshing?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: boolean;
  emptyMessage?: string;
  children: ReactNode;
};

export const QueryState = ({
  loading,
  refreshing,
  error,
  onRetry,
  empty,
  emptyMessage = "暂无数据",
  children,
}: Props) => {
  if (loading) {
    return (
      <Stack role="status" align="center" py="xl">
        <Loader size="sm" />
        <Text size="sm" c="dimmed">
          正在加载…
        </Text>
      </Stack>
    );
  }
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (empty)
    return (
      <Alert color="gray" variant="light">
        {emptyMessage}
      </Alert>
    );
  return (
    <>
      {refreshing && (
        <Text role="status" size="sm" c="dimmed" mb="xs">
          正在更新；下方保留的是上一次查询结果。
        </Text>
      )}
      {children}
    </>
  );
};
