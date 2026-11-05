import ReactEChartsCore from "echarts-for-react/lib/core";

import type {
  FundFactorAnalysis,
  NavPoint,
} from "../../api/generated/m17.schemas";
import { echarts } from "../charts/echarts";
import styles from "./FundDetailContent.module.css";

export const FundNavChart = ({
  points,
  mode = "nav",
  analysis,
  frequency = "DAILY",
  benchmarkName = "基准",
  colorMode = "CN",
}: {
  points: NavPoint[];
  mode?: "nav" | "drawdown" | "rolling";
  analysis?: FundFactorAnalysis;
  frequency?: "DAILY" | "WEEKLY" | "MONTHLY";
  benchmarkName?: string;
  colorMode?: "CN" | "INTL";
}) => {
  const factors =
    analysis?.factor_categories.flatMap((category) => category.factors) ?? [];
  const sharpe =
    factors.find((factor) => factor.factor_id === "F-STAB-005")?.series ?? [];
  const volatility =
    factors.find((factor) => factor.factor_id === "F-STAB-006")?.series ?? [];
  const dates =
    mode === "rolling"
      ? [
          ...new Set([...sharpe, ...volatility].map((point) => point.date)),
        ].sort()
      : points.map((point) => point.date);
  const sharpeValues = new Map(
    sharpe.map((point) => [point.date, point.value]),
  );
  const volatilityValues = new Map(
    volatility.map((point) => [point.date, point.value]),
  );
  const firstNav = points.find(
    (point) =>
      point.nav_status === "VALID" && point.nav !== null && point.nav > 0,
  )?.nav;
  let peak: number | undefined;
  const values = points.map((point) => {
    if (point.nav_status !== "VALID" || point.nav === null || point.nav <= 0)
      return null;
    peak = peak === undefined ? point.nav : Math.max(peak, point.nav);
    return mode === "drawdown"
      ? (point.nav / peak - 1) * 100
      : firstNav
        ? (point.nav / firstNav - 1) * 100
        : null;
  });
  const sampled = new Map<string, number>();
  dates.forEach((date, index) => {
    const calendar = new Date(`${date}T00:00:00Z`);
    if (frequency === "WEEKLY")
      calendar.setUTCDate(
        calendar.getUTCDate() - ((calendar.getUTCDay() + 6) % 7),
      );
    const key =
      frequency === "MONTHLY"
        ? date.slice(0, 7)
        : frequency === "WEEKLY"
          ? calendar.toISOString().slice(0, 10)
          : date;
    sampled.set(key, index);
  });
  const indexes = [
    ...new Set([...(dates.length ? [0] : []), ...sampled.values()]),
  ];
  const line = (
    name: string,
    data: (number | null)[],
    color: string,
    axis = 0,
  ) => ({
    name,
    type: "line",
    showSymbol: false,
    connectNulls: false,
    data: indexes.map((index) => [dates[index], data[index]]),
    yAxisIndex: axis,
    lineStyle: { color, width: 2 },
    itemStyle: { color },
  });
  const series =
    mode === "rolling"
      ? [
          line(
            "滚动夏普比率 (1年窗口)",
            dates.map((date) => sharpeValues.get(date) ?? null),
            "#e5a600",
          ),
          line(
            "滚动年化波动率 (%)",
            dates.map((date) =>
              volatilityValues.get(date) == null
                ? null
                : volatilityValues.get(date)! * 100,
            ),
            "#8b5cf6",
            1,
          ),
        ]
      : mode === "drawdown"
        ? [
            {
              ...line("动态回撤率 (%)", values, "#e03131"),
              areaStyle: { color: "#e03131", opacity: 0.12 },
            },
          ]
        : [
            {
              ...line("本基金收益率 (%)", values, "#0891b2"),
              areaStyle: { color: "#0891b2", opacity: 0.06 },
            },
            {
              ...line(
                `${benchmarkName} (%)`,
                dates.map(() => null),
                "#94a3b8",
              ),
              lineStyle: { color: "#94a3b8", type: "dashed", width: 1.5 },
            },
            {
              name: "超额收益 (%)",
              type: "bar",
              data: dates.map(() => null),
              yAxisIndex: 1,
              itemStyle: { color: colorMode === "CN" ? "#e03131" : "#059669" },
            },
          ];
  const option = {
    animation: false,
    aria: {
      enabled: true,
      description:
        mode === "drawdown"
          ? "动态回撤"
          : mode === "rolling"
            ? "滚动指标演变"
            : "净值走势与基准超额",
    },
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: unknown) =>
        typeof value === "number" ? value.toFixed(2) : "—",
    },
    grid: { left: 56, right: 56, top: 36, bottom: 30 },
    legend: {
      top: 0,
      textStyle: { fontSize: 11 },
      data: series.map((item) => item.name),
    },
    xAxis: {
      type: "category",
      data: indexes.map((index) => dates[index]),
      axisLabel: { fontSize: 10, hideOverlap: true },
    },
    yAxis: [
      {
        type: "value",
        ...(mode === "drawdown" ? { max: 0 } : {}),
        axisLabel: {
          formatter: mode === "rolling" ? "{value}" : "{value}%",
          fontSize: 10,
        },
      },
      {
        type: "value",
        position: "right",
        axisLabel: { formatter: "{value}%", fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series,
  };
  return (
    <div className={styles.chartCanvas} aria-label="基金趋势图">
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        notMerge
        autoResize
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
};

export const FundFactorTrendChart = ({
  analysis,
}: {
  analysis?: FundFactorAnalysis;
}) => {
  return <FundNavChart points={[]} mode="rolling" analysis={analysis} />;
};
