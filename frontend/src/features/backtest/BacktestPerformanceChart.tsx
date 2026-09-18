import ReactECharts from "echarts-for-react";

import type {
  BacktestPerformance,
  SeriesPoint,
} from "../../api/generated/m17.schemas";

const valid = (points: SeriesPoint[]) =>
  points
    .filter((point) => point.value_status === "VALID" && point.value !== null)
    .map((point) => [point.date, Number(point.value)]);

export const BacktestPerformanceChart = ({
  performance,
}: {
  performance: BacktestPerformance;
}) => {
  const cumulative = performance.series.cumulative_return;
  const series = [
    {
      name: "组合",
      type: "line",
      data: valid(cumulative.portfolio),
      showSymbol: false,
    },
    {
      name: "基准",
      type: "line",
      data: valid(cumulative.benchmark),
      showSymbol: false,
    },
    ...(cumulative.equal_weight_baseline
      ? [
          {
            name: "等权基线",
            type: "line",
            data: valid(cumulative.equal_weight_baseline),
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
    </section>
  );
};
