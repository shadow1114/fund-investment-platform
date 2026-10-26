import { Alert, Table, Tabs, Text } from "@mantine/core";
import ReactEChartsCore from "echarts-for-react/lib/core";
import { useCallback, useMemo, useRef, useState } from "react";

import type {
  BacktestPerformance,
  SeriesPoint,
} from "../../api/generated/m17.schemas";
import { ChartFrame } from "../../components/ChartFrame";
import { echarts } from "../charts/echarts";

type SeriesView =
  | "cumulative_return"
  | "portfolio_value"
  | "drawdown"
  | "rolling_sharpe"
  | "rolling_excess_return";
const viewLabels: Record<SeriesView, string> = {
  cumulative_return: "累计收益",
  portfolio_value: "组合净值",
  drawdown: "回撤",
  rolling_sharpe: "滚动 Sharpe",
  rolling_excess_return: "滚动超额收益",
};

const chartPoints = (points: SeriesPoint[]) =>
  points.map((point) => [
    point.date,
    point.value_status === "VALID" && point.value !== null
      ? Number(point.value)
      : null,
  ]);

export const BacktestPerformanceChart = ({
  performance,
}: {
  performance: BacktestPerformance;
}) => {
  const [view, setView] = useState<SeriesView>("cumulative_return");
  const chart = useRef<ReactEChartsCore | null>(null);
  const resizeChart = useCallback(
    () => chart.current?.getEchartsInstance().resize(),
    [],
  );
  const cumulative = performance.series.cumulative_return;
  const views = useMemo<
    Record<SeriesView, Array<{ name: string; points: SeriesPoint[] }>>
  >(
    () => ({
      cumulative_return: [
        { name: "组合", points: cumulative.portfolio },
        { name: "基准", points: cumulative.benchmark },
        ...(cumulative.equal_weight_baseline
          ? [{ name: "等权基线", points: cumulative.equal_weight_baseline }]
          : []),
      ],
      portfolio_value: [
        { name: "组合资产", points: performance.series.portfolio_value },
      ],
      drawdown: [{ name: "回撤", points: performance.series.drawdown }],
      rolling_sharpe: [
        { name: "滚动 Sharpe", points: performance.series.rolling_sharpe },
      ],
      rolling_excess_return: [
        {
          name: "滚动超额收益",
          points: performance.series.rolling_excess_return,
        },
      ],
    }),
    [cumulative, performance.series],
  );
  const activeSeries = views[view];
  const unavailable = activeSeries.flatMap(({ name, points }) =>
    points
      .filter((point) => point.value_status !== "VALID" || point.value === null)
      .map((point) => ({ name, point })),
  );
  const allPoints = activeSeries.flatMap(({ name, points }) =>
    points.map((point) => ({ name, point })),
  );
  const option = {
    aria: {
      enabled: true,
      description: `${viewLabels[view]}按日期变化；有效点 ${allPoints.length - unavailable.length} 个，缺失值断线显示。`,
    },
    tooltip: { trigger: "axis" },
    xAxis: { type: "time", axisLabel: { hideOverlap: true } },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        formatter: (value: number) =>
          view === "rolling_sharpe" || view === "portfolio_value"
            ? String(value)
            : `${(value * 100).toFixed(1)}%`,
      },
    },
    series: activeSeries.map(({ name, points }) => ({
      name,
      type: "line",
      showSymbol: false,
      connectNulls: false,
      data: chartPoints(points),
    })),
  };

  return (
    <section aria-label="回测绩效">
      <Tabs
        value={view}
        onChange={(value) => value && setView(value as SeriesView)}
      >
        <Tabs.List aria-label="绩效指标">
          {Object.entries(viewLabels).map(([value, label]) => (
            <Tabs.Tab key={value} value={value}>
              {label}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      {!cumulative.equal_weight_baseline && view === "cumulative_return" && (
        <Alert color="yellow" mt="sm">
          等权基线不可用（
          {cumulative.equal_weight_baseline_reason ??
            cumulative.equal_weight_baseline_status}
          ）
        </Alert>
      )}
      <ChartFrame
        title={`${viewLabels[view]}（${performance.segment === "FULL" ? "完整区间" : performance.segment === "IN_SAMPLE" ? "样本内" : performance.segment === "OUT_OF_SAMPLE" ? "样本外" : `未知区间 ${performance.segment}`}）`}
        description={`有效序列 ${allPoints.length - unavailable.length} 点 · 缺失/不可用 ${unavailable.length} 点。缺失点保持断线，不按零绘制。`}
        onResize={resizeChart}
        chart={
          allPoints.length > unavailable.length ? (
            <ReactEChartsCore
              echarts={echarts}
              ref={chart}
              option={option}
              autoResize
              style={{ height: "100%", minHeight: 320, width: "100%" }}
            />
          ) : (
            <Text c="dimmed">该指标没有可绘制的有效点。</Text>
          )
        }
        table={
          <>
            <div
              className="table-scroll"
              role="region"
              aria-label={`${viewLabels[view]}数值表`}
              tabIndex={0}
            >
              <Table withTableBorder withColumnBorders striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">序列</Table.Th>
                    <Table.Th scope="col">日期</Table.Th>
                    <Table.Th scope="col">数值</Table.Th>
                    <Table.Th scope="col">状态</Table.Th>
                    <Table.Th scope="col">原因</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {allPoints.map(({ name, point }) => (
                    <Table.Tr key={`${name}-${point.date}`}>
                      <Table.Td>{name}</Table.Td>
                      <Table.Th scope="row">{point.date}</Table.Th>
                      <Table.Td>
                        {point.value_status === "VALID" && point.value !== null
                          ? point.value
                          : "不可用"}
                      </Table.Td>
                      <Table.Td>{point.value_status}</Table.Td>
                      <Table.Td>{point.value_reason ?? "—"}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
            {unavailable.length > 0 && (
              <Alert color="yellow" mt="sm">
                存在不可用绩效点；见表格中的状态和原因。
              </Alert>
            )}
          </>
        }
      />
    </section>
  );
};
