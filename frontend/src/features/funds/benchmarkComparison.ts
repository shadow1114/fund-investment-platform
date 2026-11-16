import type { NavPoint } from "../../api/generated/m17.schemas";

export type BenchmarkSeries = {
  benchmark_id: string;
  benchmark_name: string;
  weight: number | string;
  points: { date: string; value: number | null }[];
};
export type ComparisonPoint = {
  date: string;
  fund: number | null;
  benchmark: number | null;
  excess: number | null;
};

const valid = (value: number | null | undefined): value is number =>
  value != null && Number.isFinite(value) && value > 0;

/** 固定权重每日再平衡；按基金净值日期对齐，并沿用该日之前最近的指数收盘值。 */
export function benchmarkComparison(
  points: NavPoint[],
  series: BenchmarkSeries[],
): ComparisonPoint[] {
  const weights = series.map((item) => Number(item.weight));
  const configured =
    series.length > 0 &&
    weights.every((weight) => Number.isFinite(weight) && weight > 0) &&
    Math.abs(weights.reduce((sum, weight) => sum + weight, 0) - 1) < 1e-8;
  const quotes = series.map((item) =>
    [...item.points]
      .filter((point) => valid(point.value))
      .sort((left, right) => left.date.localeCompare(right.date)),
  );
  const latestValues: (number | undefined)[] = series.map(() => undefined);
  const quoteIndexes = series.map(() => 0);
  const alignedValues = new Map<string, (number | undefined)[]>();
  for (const point of [...points].sort((left, right) =>
    left.date.localeCompare(right.date),
  )) {
    for (let i = 0; i < quotes.length; i += 1) {
      while (
        quoteIndexes[i] < quotes[i].length &&
        quotes[i][quoteIndexes[i]].date <= point.date
      ) {
        latestValues[i] = quotes[i][quoteIndexes[i]].value ?? undefined;
        quoteIndexes[i] += 1;
      }
    }
    alignedValues.set(point.date, [...latestValues]);
  }
  const baseline = configured
    ? points.find(
        (p) =>
          p.nav_status === "VALID" &&
          valid(p.nav) &&
          alignedValues.get(p.date)?.every(valid),
      )
    : undefined;
  const firstFund =
    baseline?.nav ??
    points.find((p) => p.nav_status === "VALID" && valid(p.nav))?.nav;
  const levels = new Map<string, number | null>();
  if (baseline) {
    let previous = alignedValues.get(baseline.date) as number[];
    let cumulative = 1;
    for (const point of points.filter((item) => item.date >= baseline.date)) {
      const current = alignedValues.get(point.date);
      if (!current?.every(valid)) {
        levels.set(point.date, null);
        continue;
      }
      const currentValues = current as number[];
      if (point.date !== baseline.date) {
        cumulative *=
          1 +
          currentValues.reduce(
            (sum, value, i) => sum + weights[i] * (value / previous![i] - 1),
            0,
          );
      }
      levels.set(point.date, (cumulative - 1) * 100);
      previous = currentValues;
    }
  }
  return points.map((point) => {
    const fund =
      point.nav_status === "VALID" &&
      valid(point.nav) &&
      valid(firstFund) &&
      (!baseline || point.date >= baseline.date)
        ? (point.nav / firstFund - 1) * 100
        : null;
    const benchmark = levels.get(point.date) ?? null;
    return {
      date: point.date,
      fund,
      benchmark,
      excess: fund !== null && benchmark !== null ? fund - benchmark : null,
    };
  });
}
