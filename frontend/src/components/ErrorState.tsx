import { Alert, Button, Group, Stack, Text } from "@mantine/core";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { ApiError } from "../api/http";

export const ErrorState = ({
  error,
  onRetry,
  retryLabel = "重新读取",
}: {
  error: unknown;
  onRetry?: () => void;
  retryLabel?: string;
}) => {
  const apiError = error instanceof ApiError ? error : undefined;
  const message =
    apiError?.message ??
    (error instanceof Error ? error.message : "未知错误，请稍后重试。");

  return (
    <Alert
      color="red"
      variant="light"
      icon={<AlertTriangle size={18} aria-hidden="true" />}
      title={
        apiError ? `请求失败 · ${apiError.status} ${apiError.code}` : "请求失败"
      }
      role="alert"
    >
      <Stack gap="xs">
        <Text size="sm">{message}</Text>
        {apiError?.retryAfterSeconds != null && (
          <Text size="xs" c="dimmed">
            服务端建议 {apiError.retryAfterSeconds} 秒后重试。
          </Text>
        )}
        {apiError?.requestId && (
          <Text size="xs" c="dimmed">
            请求 ID：{apiError.requestId}
          </Text>
        )}
        {onRetry && (
          <Group>
            <Button
              type="button"
              size="xs"
              variant="default"
              leftSection={<RefreshCw size={14} aria-hidden="true" />}
              onClick={onRetry}
            >
              {retryLabel}
            </Button>
          </Group>
        )}
      </Stack>
    </Alert>
  );
};
