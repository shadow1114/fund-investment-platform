import { ResearchDataTable } from "../../components/ResearchDataTable";
import { Button, Group, Paper, SimpleGrid, Stack, Text } from "@mantine/core";

import type {
  FundFactorAnalysis,
  FundFactorAnalysisEvaluationPeriod,
} from "../../api/generated/m17.schemas";

type factorRow =
  FundFactorAnalysis["factor_categories"][number]["factors"][number];

const periods: { value: FundFactorAnalysisEvaluationPeriod; label: string }[] =
  [
    { value: "5Y", label: "近5年" },
    { value: "3Y", label: "近3年" },
    { value: "1Y", label: "近1年" },
    { value: "6M", label: "近半年" },
    { value: "1M", label: "近1个月" },
  ];

const percentFactors = new Set([
  "F-RET-001",
  "F-RET-002",
  "F-RET-003",
  "F-RET-004",
  "F-RISK-001",
  "F-RISK-002",
  "F-RISK-003",
  "F-RISK-004",
  "F-RISK-005",
  "F-STAB-001",
  "F-STAB-006",
  "F-STAB-007",
  "F-REL-001",
  "F-REL-002",
  "F-REL-005",
]);

const formatValue = (factorId: string, value: number | null) => {
  if (value === null) return "—";
  if (percentFactors.has(factorId)) return `${(value * 100).toFixed(2)}%`;
  if (factorId === "F-RISK-006" || factorId === "F-RISK-007")
    return `${value.toFixed(0)} 个交易日`;
  return value.toFixed(3);
};

const directionLabels: Record<string, string> = {
  HIGHER_IS_BETTER: "越高越好",
  LOWER_IS_BETTER: "越低越好",
  TARGET_RANGE: "目标区间",
  STRATEGY_DEPENDENT: "结合策略判断",
};

const statusLabel = (status: string, reason: string | null) => {
  if (status === "VALID") return "可用";
  if (status === "WARNING") return `可用，需注意（${reason ?? "WARNING"}）`;
  if (status === "INVALID") return `数据异常（${reason ?? "INVALID"}）`;
  return `不可用（${reason ?? status}）`;
};

type Props = {
  analysis?: FundFactorAnalysis;
  period: FundFactorAnalysisEvaluationPeriod;
  onPeriodChange: (period: FundFactorAnalysisEvaluationPeriod) => void;
};

export const FactorAnalysisPanel = ({
  analysis,
  period,
  onPeriodChange,
}: Props) => (
  <Stack gap="lg">
    <Paper withBorder p="md" radius="sm">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div>
          <Text fw={600}>因子表现</Text>
          <Text size="sm" c="dimmed">
            基于点时可见数据实时计算
            {analysis ? ` · 截止 ${analysis.as_of_date}` : ""} ·
            不保存期间计算结果
          </Text>
        </div>
        <Group gap="xs" role="group" aria-label="计算期间">
          {periods.map((item) => (
            <Button
              key={item.value}
              size="xs"
              variant={period === item.value ? "filled" : "default"}
              aria-pressed={period === item.value}
              onClick={() => onPeriodChange(item.value)}
            >
              {item.label}
            </Button>
          ))}
        </Group>
      </Group>
    </Paper>

    {analysis && (
      <SimpleGrid cols={{ base: 1, xl: 2 }}>
        {analysis.factor_categories.map((category) => (
          <Paper key={category.category} withBorder p="md" radius="sm">
            <Stack gap="sm">
              <Group justify="space-between">
                <Text component="h2" fw={650} size="lg" m={0}>
                  {category.name}
                </Text>
                <Text size="xs" c="dimmed">
                  {category.factors.length} 项
                </Text>
              </Group>
              <ResearchDataTable
                caption={`${category.name}因子指标`}
                layoutKey={`factor-category-${category.category}`}
                rowData={category.factors}
                getRowId={({ data }) => data.factor_id}
                columnDefs={[
                  {
                    field: "name",
                    headerName: "因子",
                    autoHeight: true,
                    wrapText: true,
                    cellRenderer: ({ data: factor }: { data: factorRow }) => (
                      <>
                        <Text size="sm">{factor.name}</Text>
                        <Text size="xs" c="dimmed">
                          {factor.factor_id}
                        </Text>
                        {factor.series.length > 0 && (
                          <Text size="xs" c="dimmed">
                            滚动序列 {factor.series.length} 点
                            {factor.series.at(-1)?.value !== null &&
                              factor.series.at(-1)?.value !== undefined &&
                              ` · 最新 ${formatValue(factor.factor_id, factor.series.at(-1)!.value)}`}
                          </Text>
                        )}
                      </>
                    ),
                  },
                  {
                    field: "raw_value",
                    headerName: "数值",
                    autoHeight: true,
                    wrapText: true,
                    cellRenderer: ({ data: factor }: { data: factorRow }) => (
                      <>{formatValue(factor.factor_id, factor.raw_value)}</>
                    ),
                  },
                  {
                    field: "direction",
                    headerName: "方向",
                    autoHeight: true,
                    wrapText: true,
                    cellRenderer: ({ data: factor }: { data: factorRow }) => (
                      <>{directionLabels[factor.direction] ?? "—"}</>
                    ),
                  },
                  {
                    field: "status",
                    headerName: "状态",
                    autoHeight: true,
                    wrapText: true,
                    cellRenderer: ({ data: factor }: { data: factorRow }) => (
                      <>{statusLabel(factor.status, factor.reason_code)}</>
                    ),
                  },
                ]}
                pagination
                paginationPageSize={20}
                paginationPageSizeSelector={[20, 50, 100]}
              />
            </Stack>
          </Paper>
        ))}
      </SimpleGrid>
    )}
  </Stack>
);
