import { describe, expect, it } from "vitest";
import {
  benchmarkComparison,
  type BenchmarkSeries,
} from "./benchmarkComparison";
import type { NavPoint } from "../../api/generated/m17.schemas";

const points: NavPoint[] = [1, 1.1, 1.21].map((nav, i) => ({
  date: `2026-01-0${i + 1}`,
  nav,
  nav_status: "VALID",
  nav_reason: null,
}));
const series: BenchmarkSeries[] = [
  {
    benchmark_id: "1",
    benchmark_name: "指数A",
    weight: 0.7,
    points: [100, 110, 121].map((value, i) => ({
      date: points[i].date,
      value,
    })),
  },
  {
    benchmark_id: "2",
    benchmark_name: "指数B",
    weight: 0.3,
    points: [1000, 1000, 1000].map((value, i) => ({
      date: points[i].date,
      value,
    })),
  },
];

describe("基准收益比较", () => {
  it("按收益率权重连乘而非直接加权不同基点", () => {
    const result = benchmarkComparison(points, series);
    expect(result[1].benchmark).toBeCloseTo(7);
    expect(result[2].benchmark).toBeCloseTo(14.49);
    expect(result[2].excess).toBeCloseTo(6.51);
  });
  it("accepts decimal-string weights returned by the fund detail API", () => {
    const result = benchmarkComparison(
      points,
      series.map((item) => ({ ...item, weight: String(item.weight) })),
    );
    expect(result[2].benchmark).toBeCloseTo(14.49);
  });
  it("单项选择按100%计算", () => {
    expect(
      benchmarkComparison(points, [{ ...series[0], weight: 1 }])[2].benchmark,
    ).toBeCloseTo(21);
  });
  it("指数缺少某日行情时沿用最近可用值，保持期间累计收益", () => {
    const missing = {
      ...series[1],
      points: series[1].points.filter((_, i) => i !== 1),
    };
    const result = benchmarkComparison(points, [series[0], missing]);
    expect(result[1].benchmark).toBeCloseTo(7);
    expect(result[2].benchmark).toBeCloseTo(14.49);
    expect(result[2].fund).toBeCloseTo(21);
  });
  it("只按基金净值日期对齐指数，指数单独出现的日期不截断曲线", () => {
    const shifted: BenchmarkSeries[] = [
      {
        ...series[0],
        points: [
          { date: "2026-01-01", value: 100 },
          { date: "2026-01-02", value: 110 },
          { date: "2026-01-03", value: 110 },
        ],
      },
      {
        ...series[1],
        points: [
          { date: "2026-01-01", value: 1000 },
          { date: "2026-01-03", value: 1000 },
        ],
      },
    ];
    expect(
      benchmarkComparison([points[0], points[2]], shifted)[1].benchmark,
    ).toBeCloseTo(7);
  });
  it("无配置不伪造基准，基金仍展示", () => {
    expect(benchmarkComparison(points, [])[2]).toMatchObject({
      benchmark: null,
      excess: null,
    });
    expect(benchmarkComparison(points, [])[2].fund).toBeCloseTo(21);
  });
  it("共同有效起点之前不画对比曲线", () => {
    const later = series.map((item) => ({
      ...item,
      points: item.points.slice(1),
    }));
    const result = benchmarkComparison(points, later);
    expect(result[0].fund).toBeNull();
    expect(result[1].fund).toBe(0);
    expect(result[1].benchmark).toBe(0);
  });
  it("缺失整个组成序列或非法权重时不可用", () => {
    expect(
      benchmarkComparison(points, [{ ...series[0], weight: 0.7 }])[2].benchmark,
    ).toBeNull();
    expect(
      benchmarkComparison(points, [series[0], { ...series[1], points: [] }])[2]
        .benchmark,
    ).toBeNull();
  });
});
