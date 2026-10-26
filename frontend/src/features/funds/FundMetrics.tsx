import {
  Accordion,
  Badge,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";

import type {
  FundEvaluation,
  FundEvaluationMeta,
  FundScore,
  FundScoreMeta,
} from "../../api/generated/m17.schemas";
import { MetricValue } from "../../components/MetricValue";
import { ScoreExplainChain } from "../../components/ScoreExplainChain";

const statusLabels: Record<string, string> = {
  NOT_ELIGIBLE: "不满足评估条件",
  COMPLETED: "已完成",
  PARTIAL: "部分完成",
  VALIDATION_PENDING: "等待校验",
  FAILED: "失败",
  UNKNOWN: "未知",
};

const versionEntries = (entries: Array<[label: string, value: string]>) => (
  <Accordion variant="contained">
    <Accordion.Item value="versions">
      <Accordion.Control>查看计算版本</Accordion.Control>
      <Accordion.Panel>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
          {entries.map(([label, value]) => (
            <Text key={label} size="sm">
              {label}：{value}
            </Text>
          ))}
        </SimpleGrid>
      </Accordion.Panel>
    </Accordion.Item>
  </Accordion>
);

export const EvaluationMetrics = ({
  evaluation,
  meta,
}: {
  evaluation: FundEvaluation;
  meta: FundEvaluationMeta;
}) => (
  <Stack gap="md" aria-label="基金评估指标">
    <SimpleGrid cols={{ base: 1, sm: 3 }}>
      <div>
        <Text size="xs" c="dimmed">
          评估状态
        </Text>
        <Badge
          color={
            evaluation.evaluation_status === "COMPLETED" ? "green" : "gray"
          }
          variant="light"
        >
          {statusLabels[evaluation.evaluation_status] ??
            `未知（${evaluation.evaluation_status}）`}
        </Badge>
      </div>
      <div>
        <Text size="xs" c="dimmed">
          评估周期 / 截止日
        </Text>
        <Text>
          {evaluation.evaluation_period} · {evaluation.as_of_date}
        </Text>
      </div>
      <div>
        <Text size="xs" c="dimmed">
          数据完整度
        </Text>
        <Text>
          {evaluation.data_completeness.available} /{" "}
          {evaluation.data_completeness.expected}
        </Text>
      </div>
    </SimpleGrid>
    <Text size="sm">评估配置：{evaluation.evaluation_profile}</Text>
    {evaluation.factor_results.length === 0 ? (
      <Text c="dimmed">暂无评估因子。</Text>
    ) : (
      <Table.ScrollContainer minWidth={640}>
        <Table striped withTableBorder>
          <Table.Caption>基金评估因子</Table.Caption>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>因子</Table.Th>
              <Table.Th>窗口</Table.Th>
              <Table.Th>原始值</Table.Th>
              <Table.Th>方向</Table.Th>
              <Table.Th>状态</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {evaluation.factor_results.map((factor) => (
              <Table.Tr key={`${factor.factor_id}-${factor.window}`}>
                <Table.Th scope="row">{factor.factor_id}</Table.Th>
                <Table.Td>{factor.window}</Table.Td>
                <Table.Td>
                  <MetricValue
                    value={factor.raw_value}
                    status={factor.status}
                    reason={factor.reason_code}
                  />
                </Table.Td>
                <Table.Td>
                  {factor.direction === "HIGHER_IS_BETTER"
                    ? "越高越好"
                    : factor.direction === "LOWER_IS_BETTER"
                      ? "越低越好"
                      : "方向未知"}
                </Table.Td>
                <Table.Td>
                  {factor.status === "VALID"
                    ? "有效"
                    : factor.status === "UNAVAILABLE"
                      ? "不可用"
                      : factor.status === "EXCLUDED"
                        ? "已排除"
                        : `未知（${factor.status}）`}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    )}
    {versionEntries([
      ["同类组版本", meta.peer_group_version],
      ["评估策略版本", meta.evaluation_policy_version],
      ["因子版本", meta.factor_version],
      ["数据版本", meta.data_version],
    ])}
  </Stack>
);

const subScoreLabels = [
  ["收益", "return_score", "return_score_status", "return_score_reason"],
  ["风险", "risk_score", "risk_score_status", "risk_score_reason"],
  [
    "风险调整",
    "risk_adjusted_score",
    "risk_adjusted_score_status",
    "risk_adjusted_score_reason",
  ],
  [
    "稳定性",
    "stability_score",
    "stability_score_status",
    "stability_score_reason",
  ],
  [
    "相对表现",
    "relative_performance_score",
    "relative_performance_score_status",
    "relative_performance_score_reason",
  ],
] as const;

export const ScoreMetrics = ({
  score,
  meta,
}: {
  score: FundScore;
  meta: FundScoreMeta;
}) => (
  <Stack gap="md" aria-label="基金评分指标">
    <SimpleGrid cols={{ base: 1, sm: 3 }}>
      <div>
        <Text size="xs" c="dimmed">
          总分（无量纲）
        </Text>
        <Title order={3} size="h3">
          <MetricValue
            value={score.total_score}
            status={score.total_score_status}
            reason={score.total_score_reason}
          />
        </Title>
      </div>
      <div>
        <Text size="xs" c="dimmed">
          评分状态
        </Text>
        <Badge
          color={score.score_status === "COMPLETED" ? "green" : "gray"}
          variant="light"
        >
          {statusLabels[score.score_status] ?? `未知（${score.score_status}）`}
        </Badge>
      </div>
      <div>
        <Text size="xs" c="dimmed">
          评分周期 / 截止日
        </Text>
        <Text>
          {score.evaluation_period} · {score.as_of_date}
        </Text>
      </div>
    </SimpleGrid>
    <Title order={3} size="h4">
      分项评分（无量纲）
    </Title>
    <Table.ScrollContainer minWidth={640}>
      <Table striped withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>维度</Table.Th>
            <Table.Th>评分</Table.Th>
            <Table.Th>状态</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {subScoreLabels.map(([label, valueKey, statusKey, reasonKey]) => (
            <Table.Tr key={valueKey}>
              <Table.Th scope="row">{label}</Table.Th>
              <Table.Td>
                <MetricValue
                  value={score.sub_scores[valueKey]}
                  status={score.sub_scores[statusKey]}
                  reason={score.sub_scores[reasonKey]}
                />
              </Table.Td>
              <Table.Td>
                {score.sub_scores[statusKey] === "VALID"
                  ? "有效"
                  : score.sub_scores[statusKey] === "UNAVAILABLE"
                    ? "不可用"
                    : score.sub_scores[statusKey] === "EXCLUDED"
                      ? "已排除"
                      : `未知（${score.sub_scores[statusKey]}）`}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
    <Title order={3} size="h4">
      评分归因
    </Title>
    {score.attribution.length > 0 ? (
      <ScoreExplainChain attribution={score.attribution} />
    ) : (
      <Text c="dimmed">暂无评分归因。</Text>
    )}
    {versionEntries([
      ["同类组版本", meta.peer_group_version],
      ["评分策略版本", meta.scoring_policy_version],
      ["评估策略版本", meta.evaluation_policy_version],
      ["因子版本", meta.factor_version],
      ["数据版本", meta.data_version],
    ])}
  </Stack>
);
