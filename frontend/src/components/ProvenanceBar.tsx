import { Alert, Badge, Group, Paper, Stack, Text } from "@mantine/core";
import type { ResponseMeta } from "../api/generated/m17.schemas";

type Props = {
  meta?: Pick<
    ResponseMeta,
    | "as_of_date"
    | "data_version"
    | "versions"
    | "is_point_in_time"
    | "availability_quality_distribution"
  >;
};

const qualityLabels: Record<string, string> = {
  EXACT: "精确",
  DERIVED: "派生",
  INFERRED: "推断",
};

export const ProvenanceBar = ({ meta }: Props) => {
  const missing = [
    meta?.versions === undefined ? "versions" : null,
    meta?.is_point_in_time === undefined ? "is_point_in_time" : null,
    meta?.availability_quality_distribution === undefined
      ? "availability_quality_distribution"
      : null,
  ].filter((field): field is string => field !== null);

  return (
    <Paper withBorder radius="sm" p="sm" aria-label="数据溯源">
      <Stack gap="xs">
        {missing.length > 0 && (
          <Alert
            color="yellow"
            variant="light"
            title="来源契约不完整"
            role="alert"
          >
            缺少字段：{missing.join("、")}
          </Alert>
        )}
        <Group gap="md" wrap="wrap" align="center">
          <Text size="sm">数据截止：{meta?.as_of_date ?? "未返回"}</Text>
          {meta?.data_version && (
            <Text size="sm">数据版本：{meta.data_version}</Text>
          )}
          <Badge
            color={meta?.is_point_in_time ? "green" : "yellow"}
            variant="light"
          >
            点时数据：
            {meta?.is_point_in_time === undefined
              ? "未知"
              : meta.is_point_in_time
                ? "是"
                : "否"}
          </Badge>
          <Group gap={6} aria-label="可用时间质量分布">
            {Object.entries(meta?.availability_quality_distribution ?? {}).map(
              ([quality, count]) => (
                <Badge
                  key={quality}
                  color={
                    quality === "EXACT"
                      ? "green"
                      : quality === "DERIVED"
                        ? "blue"
                        : "yellow"
                  }
                  variant="light"
                >
                  {qualityLabels[quality] ?? `未知（${quality}）`} {count}
                </Badge>
              ),
            )}
            {meta?.availability_quality_distribution &&
              Object.keys(meta.availability_quality_distribution).length ===
                0 && (
                <Text size="sm" c="dimmed">
                  未提供质量统计
                </Text>
              )}
          </Group>
        </Group>
        {meta?.versions && Object.keys(meta.versions).length > 0 && (
          <details>
            <summary>查看来源版本</summary>
            <dl>
              {Object.entries(meta.versions).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </Stack>
    </Paper>
  );
};
