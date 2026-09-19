import ReactECharts from "echarts-for-react";

import type {
  BacktestPerformance,
  SeriesPoint,
} from "../../api/generated/m17.schemas";

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
  const cumulative = performance.series.cumulative_return;
  const allSeries: Array<{ label: string; points: SeriesPoint[] }> = [
    { label: "组合净值", points: performance.series.portfolio_value },
    { label: "组合累计收益", points: cumulative.portfolio },
    { label: "基准累计收益", points: cumulative.benchmark },
    ...(cumulative.equal_weight_baseline
      ? [
          {
            label: "等权基线累计收益",
            points: cumulative.equal_weight_baseline,
          },
        ]
      : []),
    { label: "回撤", points: performance.series.drawdown },
    { label: "滚动夏普", points: performance.series.rolling_sharpe },
    { label: "滚动超额收益", points: performance.series.rolling_excess_return },
  ];
  const unavailable = allSeries.flatMap(({ label, points }) =>
    points
      .filter((point) => point.value_status !== "VALID" || point.value === null)
      .map((point) => ({ label, point })),
  );
  const series = [
    {
      name: "组合",
      type: "line",
      data: chartPoints(cumulative.portfolio),
      showSymbol: false,
    },
    {
      name: "基准",
      type: "line",
      data: chartPoints(cumulative.benchmark),
      showSymbol: false,
    },
    ...(cumulative.equal_weight_baseline
      ? [
          {
            name: "等权基线",
            type: "line",
            data: chartPoints(cumulative.equal_weight_baseline),
            showSymbol: false,
          },
        ]
      : []),
  ];
  return (
    <section aria-label="回测绩效">
      <h2>绩效序列（{performance.segment}）</h2>
      <ReactECharts
        option={{
          aria: { enabled: true, description: "组合、基准与等权基线累计收益" },
          tooltip: { trigger: "axis" },
          xAxis: { type: "time" },
          yAxis: { type: "value" },
          series,
        }}
        style={{ height: 360 }}
      />
      {!cumulative.equal_weight_baseline && (
        <p>
          等权基线不可用（
          {cumulative.equal_weight_baseline_reason ??
            cumulative.equal_weight_baseline_status}
          ）
        </p>
      )}
      {unavailable.length > 0 && (
        <section aria-label="不可用绩效点位">
          <h3>不可用绩效点位</h3>
          <ul>
            {unavailable.map(({ label, point }) => (
              <li key={`${label}-${point.date}`}>
                {label} · {point.date} · {point.value_status} ·{" "}
                {point.value_reason ?? "未提供原因"}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
};
