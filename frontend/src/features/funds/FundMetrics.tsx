import { ResearchDataTable } from "../../components/ResearchDataTable";
import {
  Accordion,
  Badge,
  SimpleGrid,
  Stack,
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

type factorRow = FundEvaluation["factor_results"][number];
type entryRow = {
  label: string;
  valueKey: (typeof subScoreLabels)[number][1];
  statusKey: (typeof subScoreLabels)[number][2];
  reasonKey: (typeof subScoreLabels)[number][3];
};

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
      <ResearchDataTable
        caption="基金评估因子"
        layoutKey="fund-evaluation"
        rowData={evaluation.factor_results}
        getRowId={({ data }) => `${data.factor_id}-${data.window}`}
        columnDefs={[
          {
            field: "factor_id",
            headerName: "因子",
            autoHeight: true,
            wrapText: true,
            cellRenderer: ({ data: factor }: { data: factorRow }) => (
              <>{factor.factor_id}</>
            ),
          },
          {
            field: "window",
            headerName: "窗口",
            autoHeight: true,
            wrapText: true,
            cellRenderer: ({ data: factor }: { data: factorRow }) => (
              <>{factor.window}</>
            ),
          },
          {
            field: "raw_value",
            headerName: "原始值",
            autoHeight: true,
            wrapText: true,
            cellRenderer: ({ data: factor }: { data: factorRow }) => (
              <>
                <MetricValue
                  value={factor.raw_value}
                  status={factor.status}
                  reason={factor.reason_code}
                />
              </>
            ),
          },
          {
            field: "direction",
            headerName: "方向",
            autoHeight: true,
            wrapText: true,
            cellRenderer: ({ data: factor }: { data: factorRow }) => (
              <>
                {factor.direction === "HIGHER_IS_BETTER"
                  ? "越高越好"
                  : factor.direction === "LOWER_IS_BETTER"
                    ? "越低越好"
                    : "方向未知"}
              </>
            ),
          },
          {
            field: "status",
            headerName: "状态",
            autoHeight: true,
            wrapText: true,
            cellRenderer: ({ data: factor }: { data: factorRow }) => (
              <>
                {factor.status === "VALID"
                  ? "有效"
                  : factor.status === "UNAVAILABLE"
                    ? "不可用"
                    : factor.status === "EXCLUDED"
                      ? "已排除"
                      : `未知（${factor.status}）`}
              </>
            ),
          },
        ]}
        pagination
        paginationPageSize={20}
        paginationPageSizeSelector={[20, 50, 100]}
      />
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
    <ResearchDataTable
      caption="基金分项评分"
      layoutKey="fund-sub-scores"
      rowData={subScoreLabels.map(
        ([label, valueKey, statusKey, reasonKey]) => ({
          label,
          valueKey,
          statusKey,
          reasonKey,
        }),
      )}
      getRowId={({ data }) => data.valueKey}
      columnDefs={[
        {
          field: "label",
          headerName: "维度",
          autoHeight: true,
          wrapText: true,
          cellRenderer: ({ data: entry }: { data: entryRow }) => (
            <>{entry.label}</>
          ),
        },
        {
          colId: "score",
          valueGetter: ({ data }) =>
            data ? score.sub_scores[data.valueKey] : null,
          headerName: "评分",
          autoHeight: true,
          wrapText: true,
          cellRenderer: ({ data: entry }: { data: entryRow }) => (
            <>
              <MetricValue
                value={score.sub_scores[entry.valueKey]}
                status={score.sub_scores[entry.statusKey]}
                reason={score.sub_scores[entry.reasonKey]}
              />
            </>
          ),
        },
        {
          colId: "status",
          valueGetter: ({ data }) =>
            data ? score.sub_scores[data.statusKey] : null,
          headerName: "状态",
          autoHeight: true,
          wrapText: true,
          cellRenderer: ({ data: entry }: { data: entryRow }) => (
            <>
              {score.sub_scores[entry.statusKey] === "VALID"
                ? "有效"
                : score.sub_scores[entry.statusKey] === "UNAVAILABLE"
                  ? "不可用"
                  : score.sub_scores[entry.statusKey] === "EXCLUDED"
                    ? "已排除"
                    : `未知（${score.sub_scores[entry.statusKey]}）`}
            </>
          ),
        },
      ]}
      pagination
      paginationPageSize={20}
      paginationPageSizeSelector={[20, 50, 100]}
    />
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
