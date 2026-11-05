import { Button, Group, Table, Tooltip } from "@mantine/core";
import {
  ChevronDown,
  Coins,
  Scale,
  Target,
  Shield,
  ChartNoAxesCombined,
  Table2,
  LayoutGrid,
} from "lucide-react";
import { useState } from "react";
import styles from "./FundDetailContent.module.css";

import type {
  FundFactorAnalysis,
  FundFactorAnalysisEvaluationPeriod,
} from "../../api/generated/m17.schemas";

export type FundAnalyticsPeriod = FundFactorAnalysisEvaluationPeriod;
export const analyticsPeriods: { value: FundAnalyticsPeriod; label: string }[] =
  [
    { value: "1M", label: "1个月" },
    { value: "3M", label: "3个月" },
    { value: "6M", label: "6个月" },
    { value: "1Y", label: "1年" },
    { value: "3Y", label: "3年" },
    { value: "5Y", label: "5年" },
    { value: "ALL", label: "成立以来" },
  ];

export const prototypeCategories = [
  {
    code: "RET",
    title: "收益指标 (4)",
    english: "Absolute Return",
    icon: Coins,
    metrics: [
      ["F-RET-001", "年化收益率", "基准 —"],
      ["F-RET-002", "累计收益率", "跑赢同类 —"],
      ["F-RET-003", "区间收益率", "最新收盘对齐"],
      ["F-RET-004", "滚动收益 (中位数)", "跨窗口稳健度"],
    ],
  },
  {
    code: "RAP",
    title: "风险调整 (3)",
    english: "Risk-Adjusted",
    icon: Scale,
    metrics: [
      ["F-RAP-001", "夏普比率 (Sharpe)", "无风险利率 rf=—"],
      ["F-RAP-002", "索提诺比率 (Sortino)", "仅惩罚下行波动"],
      ["F-RAP-003", "卡玛比率 (Calmar)", "年化收益 / 最大回撤"],
    ],
  },
  {
    code: "REL",
    title: "相对基准表现 (5)",
    english: "",
    icon: Target,
    metrics: [
      ["F-REL-001", "超额收益", ""],
      ["F-REL-002", "Alpha (詹森)", ""],
      ["F-REL-003", "Beta (贝塔)", ""],
      ["F-REL-004", "信息比率 (IR)", ""],
      ["F-REL-005", "跟踪误差 (Tracking Error)", "年化增强策略主动风险敞口"],
    ],
  },
  {
    code: "RISK",
    title: "风险指标 (7)",
    english: "Risk Profile",
    icon: Shield,
    metrics: [
      ["F-RISK-001", "年化波动率", "基准 —"],
      ["F-RISK-002", "下行波动率", "仅计负收益"],
      ["F-RISK-003", "历史最大回撤", "基准 —"],
      ["F-RISK-004", "在险价值 (VaR 95%)", "日频置信度"],
      ["F-RISK-005", "CVaR (95% 条件在险)", ""],
      ["F-RISK-006", "回撤持续期", ""],
      ["F-RISK-007", "回撤恢复期", ""],
    ],
  },
  {
    code: "STAB",
    title: "稳定性指标 (7)",
    english: "Stability & Dispersion",
    icon: ChartNoAxesCombined,
    metrics: [
      ["F-STAB-001", "正收益比例", "交易日胜率"],
      ["F-STAB-002", "判定系数 (R²)", "高拟合基准"],
      ["F-STAB-003", "偏度 (Skewness)", "接近正态分布"],
      ["F-STAB-004", "峰度 (Kurtosis)", "轻度厚尾"],
      ["F-STAB-005", "滚动 Sharpe 区间", ""],
      ["F-STAB-006", "滚动波动率均值", ""],
      ["F-STAB-007", "滚动最大回撤均值", ""],
    ],
  },
] as const;

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

export const formatFactorValue = (factorId: string, value: number | null) => {
  if (value === null) return "—";
  if (percentFactors.has(factorId)) return `${(value * 100).toFixed(2)}%`;
  if (factorId === "F-RISK-006" || factorId === "F-RISK-007")
    return `${value.toFixed(0)} 个交易日`;
  return value.toFixed(2);
};

export const prototypeFactorValue = (
  analysis: FundFactorAnalysis | undefined,
  factorId: string,
): number | null => {
  const factor = analysis?.factor_categories
    .flatMap((category) => category.factors)
    .find((item) => item.factor_id === factorId);
  if (!factor || !["VALID", "WARNING"].includes(factor.status)) return null;
  if (factorId === "F-RET-004") {
    const values = factor.series
      .map((point) => point.value)
      .filter(
        (value): value is number => value !== null && Number.isFinite(value),
      )
      .sort((left, right) => left - right);
    if (!values.length) return null;
    const middle = Math.floor(values.length / 2);
    return values.length % 2
      ? values[middle]
      : (values[middle - 1] + values[middle]) / 2;
  }
  if (factor.raw_value === null || !Number.isFinite(factor.raw_value))
    return null;
  return ["F-RISK-004", "F-RISK-005"].includes(factorId)
    ? -Math.abs(factor.raw_value)
    : factor.raw_value;
};

export const prototypeFactorText = (
  analysis: FundFactorAnalysis | undefined,
  factorId: string,
) => {
  if (factorId === "F-STAB-005") {
    const factor = analysis?.factor_categories
      .flatMap((category) => category.factors)
      .find((item) => item.factor_id === factorId);
    const values =
      factor?.series
        .map((point) => point.value)
        .filter(
          (value): value is number => value !== null && Number.isFinite(value),
        ) ?? [];
    return values.length
      ? `${Math.min(...values).toFixed(2)} ~ ${Math.max(...values).toFixed(2)}`
      : "—";
  }
  const value = prototypeFactorValue(analysis, factorId);
  const formatted = formatFactorValue(factorId, value);
  return value !== null &&
    value > 0 &&
    (factorId.startsWith("F-RET") ||
      ["F-REL-001", "F-REL-002"].includes(factorId))
    ? `+${formatted}`
    : formatted;
};

type Props = {
  analysis?: FundFactorAnalysis;
  period: FundAnalyticsPeriod;
  onPeriodChange?: (period: FundAnalyticsPeriod) => void;
  showPeriodControl?: boolean;
  comparisons?: {
    period?: FundAnalyticsPeriod;
    analysis?: FundFactorAnalysis;
    loading: boolean;
    error: boolean;
  }[];
  onLoadComparisons?: () => void;
  onRetryComparisons?: () => void;
  benchmarkName?: string;
  colorMode?: "CN" | "INTL";
};

export const FactorAnalysisPanel = ({
  analysis,
  period,
  comparisons,
  benchmarkName = "—",
  colorMode = "CN",
}: Props) => {
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const label =
    analyticsPeriods.find((item) => item.value === period)?.label ?? period;
  const tone = (factorId: string, source = analysis) => {
    const value = prototypeFactorValue(source, factorId);
    if (
      value === null ||
      !(
        factorId.startsWith("F-RET") ||
        ["F-REL-001", "F-REL-002"].includes(factorId)
      )
    )
      return undefined;
    return value >= 0
      ? colorMode === "CN"
        ? styles.up
        : styles.down
      : colorMode === "CN"
        ? styles.down
        : styles.up;
  };
  const tableCategories = [
    prototypeCategories[0],
    prototypeCategories[3],
    prototypeCategories[1],
    prototypeCategories[4],
    prototypeCategories[2],
  ];
  return (
    <div className={styles.factorArea}>
      <Group justify="space-between" className={styles.matrixHeading}>
        <h2>
          <LayoutGrid size={16} />
          量化多因子多维矩阵 (当前周期:{" "}
          <span>{period === "ALL" ? label : `近${label}`}</span>)
        </h2>
        <span>数据涵盖 5 大类共 26 项已实现指标</span>
      </Group>
      <div className={styles.factorGrid}>
        {prototypeCategories.map((category) => (
          <section
            key={category.code}
            className={styles.factorCategory}
            data-category={category.code}
          >
            <div className={styles.categoryHeading}>
              <h3>
                <category.icon size={14} />
                {category.title}
              </h3>
              <span>
                {category.code === "REL"
                  ? `vs. ${benchmarkName}`
                  : category.english}
              </span>
            </div>
            <dl className={styles.metricGrid}>
              {category.metrics.map(([factorId, name, note], index) => (
                <div
                  key={factorId}
                  className={styles.metric}
                  data-index={index}
                >
                  <div>
                    <dt>{name}</dt>
                    {note && <dd className={styles.metricNote}>{note}</dd>}
                  </div>
                  <dd
                    className={`${styles.metricValue} ${tone(factorId) ?? ""}`}
                    title={
                      analysis?.factor_categories
                        .flatMap((group) => group.factors)
                        .find((factor) => factor.factor_id === factorId)
                        ?.reason_code ?? undefined
                    }
                  >
                    {prototypeFactorText(analysis, factorId)}
                  </dd>
                </div>
              ))}
            </dl>
            {category.code === "RET" && (
              <div className={styles.categoryFooter}>
                <span>超额收益胜率</span>
                <strong>—</strong>
              </div>
            )}
            {category.code === "RAP" && (
              <div className={styles.categoryFooter}>
                综合风险补偿优于 — 的同类指数增强基金
              </div>
            )}
            {category.code === "REL" && (
              <div className={styles.categoryFooter}>
                <span>信息比率评价:</span>
                <strong>—</strong>
              </div>
            )}
          </section>
        ))}
      </div>
      <section
        className={styles.panoramaSection}
        aria-label="全周期多维量化因子透视表"
      >
        <Group justify="space-between" className={styles.panoramaHeading}>
          <h2>
            <Table2 size={16} />
            全周期多维量化因子透视表 (Multi-Period Panorama)
          </h2>
          <Group gap="sm">
            <span className={styles.legendGood}>优于基准</span>
            <span className={styles.legendBad}>弱于基准</span>
            <Button
              size="compact-xs"
              variant="subtle"
              onClick={() =>
                setCollapsed(
                  collapsed.length
                    ? []
                    : tableCategories.map((category) => category.code),
                )
              }
            >
              折叠/展开全部
            </Button>
          </Group>
        </Group>
        <div
          className={styles.panoramaScroll}
          tabIndex={0}
          role="region"
          aria-label="多周期数值"
        >
          <Table className={styles.panorama}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>因子指标</Table.Th>
                {analyticsPeriods.map((item) => (
                  <Table.Th
                    key={item.value}
                    data-current={item.value === period}
                  >
                    {item.label}
                    {item.value === period ? " (当前)" : ""}
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tableCategories.map((category) => [
                <Table.Tr key={category.code} className={styles.categoryRow}>
                  <Table.Th colSpan={8}>
                    <button
                      type="button"
                      aria-expanded={!collapsed.includes(category.code)}
                      onClick={() =>
                        setCollapsed(
                          collapsed.includes(category.code)
                            ? collapsed.filter((code) => code !== category.code)
                            : [...collapsed, category.code],
                        )
                      }
                    >
                      <ChevronDown size={12} />
                      {category.title}
                      <span>点击折叠</span>
                    </button>
                  </Table.Th>
                </Table.Tr>,
                ...(!collapsed.includes(category.code)
                  ? category.metrics.map(([factorId, name]) => (
                      <Table.Tr key={factorId}>
                        <Table.Th scope="row">{name}</Table.Th>
                        {analyticsPeriods.map((item) => {
                          const source =
                            item.value === analysis?.evaluation_period
                              ? analysis
                              : comparisons?.find(
                                  (comparison) =>
                                    (comparison.period ??
                                      comparison.analysis
                                        ?.evaluation_period) === item.value,
                                )?.analysis;
                          const reason = source?.factor_categories
                            .flatMap((group) => group.factors)
                            .find(
                              (factor) => factor.factor_id === factorId,
                            )?.reason_code;
                          return (
                            <Table.Td
                              key={item.value}
                              data-current={item.value === period}
                              className={tone(factorId, source)}
                            >
                              <Tooltip
                                label={reason ?? "暂无数据"}
                                disabled={
                                  !reason &&
                                  prototypeFactorText(source, factorId) !== "—"
                                }
                              >
                                <span>
                                  {prototypeFactorText(source, factorId)}
                                </span>
                              </Tooltip>
                            </Table.Td>
                          );
                        })}
                      </Table.Tr>
                    ))
                  : []),
              ])}
            </Table.Tbody>
          </Table>
        </div>
      </section>
    </div>
  );
};
