import type { Portfolio } from "../../api/generated/m17.schemas";
import { Badge, Group, Paper, Stack, Text, Title } from "@mantine/core";

const statusLabel: Record<string, string> = {
  DRAFT: "草稿",
  ACTIVE: "运行中",
  SUSPENDED: "已暂停",
  CLOSED: "已关闭",
  UNKNOWN: "未知",
};

export const PortfolioOverview = ({ portfolio }: { portfolio: Portfolio }) => (
  <Paper withBorder radius="sm" p="md" aria-label="组合概览">
    <Stack gap="sm">
      <Group justify="space-between" wrap="wrap">
        <Title order={2} size="h3">
          组合概览
        </Title>
        <Badge
          color={portfolio.status === "ACTIVE" ? "green" : "gray"}
          variant="light"
        >
          {statusLabel[portfolio.status] ?? `未知（${portfolio.status}）`}
        </Badge>
      </Group>
      <dl>
        <div>
          <dt>组合 ID</dt>
          <dd>{portfolio.portfolio_id}</dd>
        </div>
        <div>
          <dt>组合类型</dt>
          <dd>{portfolio.portfolio_type}</dd>
        </div>
        <div>
          <dt>基准币种</dt>
          <dd>{portfolio.base_currency}</dd>
        </div>
        <div>
          <dt>风险画像</dt>
          <dd>{portfolio.risk_profile}</dd>
        </div>
        <div>
          <dt>基准</dt>
          <dd>{portfolio.portfolio_benchmark.benchmark_name}</dd>
        </div>
        <div>
          <dt>组合版本</dt>
          <dd>{portfolio.portfolio_version}</dd>
        </div>
        <div>
          <dt>组合规则版本</dt>
          <dd>{portfolio.portfolio_rule_version}</dd>
        </div>
      </dl>
      <Text size="xs" c="dimmed">
        风险画像及基准来自组合服务返回。
      </Text>
    </Stack>
  </Paper>
);
