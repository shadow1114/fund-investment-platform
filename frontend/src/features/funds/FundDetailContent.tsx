import { Button, Group, SegmentedControl, Tabs, Loader } from "@mantine/core";
import {
  ChartLine,
  Clock,
  Palette,
  FileDown,
  Waves,
  Activity,
} from "lucide-react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState, type ReactNode } from "react";

import {
  getFund,
  getFundFactorAnalysis,
  getFundNavSeries,
} from "../../api/generated/m17";
import type {
  FundFactorAnalysisEvaluationPeriod,
  NavSeriesMeta,
  ResponseMeta,
} from "../../api/generated/m17.schemas";
import { unwrapResponse } from "../../api/http";
import { ErrorState } from "../../components/ErrorState";
import {
  FactorAnalysisPanel,
  analyticsPeriods,
  prototypeFactorText,
  prototypeFactorValue,
  type FundAnalyticsPeriod,
} from "./FactorAnalysisPanel";
import styles from "./FundDetailContent.module.css";

const FundNavChart = lazy(() =>
  import("./FundNavChart").then((module) => ({
    default: module.FundNavChart,
  })),
);
export type FundDetailTab = "nav" | "drawdown" | "rolling";
export const factorPeriods = analyticsPeriods.map((period) => period.value);
const apiFactorPeriods: FundFactorAnalysisEvaluationPeriod[] = [
  "1M",
  "3M",
  "6M",
  "1Y",
  "3Y",
  "5Y",
  "ALL",
];

export type FundDetailState = {
  tab: FundDetailTab;
  factorPeriod: FundAnalyticsPeriod;
  onTabChange: (value: string | null) => void;
  onFactorPeriodChange: (value: FundAnalyticsPeriod) => void;
};

type Props = {
  fundId: string;
  fundCode?: string;
  shareClassId?: string;
  asOfDate?: string;
  returnTo: string;
  state: FundDetailState;
  actions?: ReactNode;
};

export const FundDetailContent = ({
  fundId,
  fundCode,
  shareClassId,
  asOfDate,
  state,
}: Props) => {
  const { tab, factorPeriod, onTabChange, onFactorPeriodChange } = state;
  const [colorMode, setColorMode] = useState<"CN" | "INTL">("CN");
  const [frequency, setFrequency] = useState<"DAILY" | "WEEKLY" | "MONTHLY">(
    "DAILY",
  );
  const identifier = shareClassId || fundId;
  const fund = useQuery({
    queryKey: ["fund-detail", identifier, asOfDate],
    enabled: Boolean(identifier),
    queryFn: async ({ signal }) => {
      const response = await getFund(
        identifier,
        { as_of_date: asOfDate },
        { signal },
      );
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as ResponseMeta,
      };
    },
  });
  const nav = useQuery({
    queryKey: ["fund-nav", identifier, asOfDate],
    enabled: Boolean(identifier),
    queryFn: async ({ signal }) => {
      const response = await getFundNavSeries(
        identifier,
        {
          as_of_date: asOfDate,
          nav_type: "ADJUSTED",
        },
        { signal },
      );
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as NavSeriesMeta,
      };
    },
  });
  const rawNav = useQuery({
    queryKey: ["fund-unit-nav", identifier, asOfDate],
    enabled: Boolean(identifier),
    queryFn: async ({ signal }) => {
      const response = await getFundNavSeries(
        identifier,
        {
          as_of_date: asOfDate,
          nav_type: "RAW",
        },
        { signal },
      );
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as NavSeriesMeta,
      };
    },
  });
  const factorOptions = (period: FundFactorAnalysisEvaluationPeriod) => ({
    queryKey: ["fund-factor-analysis", identifier, period, asOfDate],
    enabled: Boolean(identifier) && fund.isSuccess,
    queryFn: async ({ signal }: { signal: AbortSignal }) => {
      const response = await getFundFactorAnalysis(
        identifier,
        {
          evaluation_period: period,
          as_of_date: asOfDate,
        },
        { signal },
      );
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as ResponseMeta,
      };
    },
  });
  const supported = apiFactorPeriods.includes(
    factorPeriod as FundFactorAnalysisEvaluationPeriod,
  );
  const factorAnalysis = useQuery({
    ...factorOptions(
      supported ? (factorPeriod as FundFactorAnalysisEvaluationPeriod) : "1Y",
    ),
    enabled: fund.isSuccess && supported,
  });
  const panorama = useQueries({
    queries: apiFactorPeriods.map((period) => ({
      ...factorOptions(period),
      enabled: Boolean(identifier) && fund.isSuccess,
    })),
  });

  if (!identifier) return <ErrorState error={new Error("缺少基金 ID")} />;
  if (fund.isPending)
    return (
      <div className={styles.loading}>
        <Loader aria-label="正在加载基金详情" />
      </div>
    );
  if (fund.isError)
    return (
      <ErrorState error={fund.error} onRetry={() => void fund.refetch()} />
    );

  const fundData = fund.data.data;
  const analysis = supported ? factorAnalysis.data?.data : undefined;
  const navPoints = nav.data?.data.points ?? [];
  const endDate = asOfDate ?? navPoints.at(-1)?.date;
  const startDate =
    endDate && factorPeriod !== "ALL"
      ? new Date(`${endDate}T00:00:00Z`)
      : undefined;
  if (startDate) {
    const day = startDate.getUTCDate();
    startDate.setUTCDate(1);
    startDate.setUTCMonth(
      startDate.getUTCMonth() -
        { "1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60, ALL: 0 }[
          factorPeriod
        ],
    );
    const lastDay = new Date(
      Date.UTC(startDate.getUTCFullYear(), startDate.getUTCMonth() + 1, 0),
    ).getUTCDate();
    startDate.setUTCDate(Math.min(day, lastDay));
  }
  const cutoff = startDate?.toISOString().slice(0, 10);
  const periodPoints = navPoints.filter(
    (point) =>
      (!cutoff || point.date >= cutoff) && (!endDate || point.date <= endDate),
  );
  const rawPoints = rawNav.data?.data.points ?? [];
  const validRawPoints = rawPoints.filter(
    (point) =>
      point.nav_status === "VALID" &&
      point.nav !== null &&
      (!endDate || point.date <= endDate),
  );
  const latestNav = [...validRawPoints]
    .reverse()
    .find((point) => point.nav_status === "VALID" && point.nav !== null);
  const previousNav = validRawPoints.at(-2)?.nav;
  const change =
    latestNav?.nav != null && previousNav && previousNav > 0
      ? latestNav.nav / previousNav - 1
      : null;
  const benchmarkName = fundData.benchmark.benchmark_name || "—";
  const changeText =
    change === null
      ? "—"
      : `${change >= 0 ? "+" : ""}${(change * 100).toFixed(2)}%`;
  const changeClass =
    change === null
      ? ""
      : change >= 0 === (colorMode === "CN")
        ? styles.up
        : styles.down;
  const returnClass = (factorId: string) => {
    const value = prototypeFactorValue(analysis, factorId);
    return value === null
      ? ""
      : value >= 0 === (colorMode === "CN")
        ? styles.up
        : styles.down;
  };
  const code =
    fundCode ?? (/^\d{6}$/.test(fundData.fund_id) ? fundData.fund_id : "—");

  return (
    <div className={styles.dashboard}>
      <header className={styles.fundHeader}>
        <div className={styles.identity}>
          <div className={styles.brandIcon}>
            <ChartLine size={20} />
          </div>
          <div>
            <div className={styles.headline}>
              <span className={styles.codeBadge}>{code}</span>
              <h1>{fundData.fund_name}</h1>
              <span className={styles.classificationBadge}>
                {fundData.fund_classification}
              </span>
              <span className={styles.rating}>晨星 —</span>
            </div>
            <div className={styles.fundFacts}>
              <span>
                对比基准:{" "}
                <strong>
                  {benchmarkName} ({fundData.benchmark.benchmark_id})
                </strong>
              </span>
              <span>
                成立日: <strong>{fundData.inception_date ?? "—"}</strong>
              </span>
              <span>
                管理规模: <strong>— 亿元</strong>
              </span>
            </div>
          </div>
        </div>
        <div className={styles.headerActions}>
          <div className={styles.quickStats}>
            <div>
              <span>单位净值 ({latestNav?.date ?? "—"})</span>
              <div>
                <strong>{latestNav?.nav?.toFixed(4) ?? "—"}</strong>
                <b className={changeClass}>{changeText}</b>
              </div>
            </div>
            <div>
              <span>近1年同类排名</span>
              <div>
                <strong>—</strong> / — (前—%)
              </div>
            </div>
          </div>
          <Button
            size="xs"
            variant="default"
            leftSection={<Palette size={14} />}
            onClick={() => setColorMode(colorMode === "CN" ? "INTL" : "CN")}
          >
            {colorMode === "CN" ? "A股红涨绿跌" : "国际绿涨红跌"}
          </Button>
          <Button
            size="xs"
            leftSection={<FileDown size={14} />}
            onClick={() => window.print()}
          >
            导出简报
          </Button>
        </div>
      </header>
      <section className={styles.periodBar} aria-label="分析周期">
        <Group gap="xs" className={styles.periodControl}>
          <span className={styles.controlLabel}>
            <Clock size={14} />
            分析周期:
          </span>
          <SegmentedControl
            value={factorPeriod}
            onChange={(value) =>
              onFactorPeriodChange(value as FundAnalyticsPeriod)
            }
            data={analyticsPeriods}
            aria-label="分析周期"
            size="xs"
          />
        </Group>
        <div className={styles.secondaryControls}>
          <label>
            对比基准:
            <select aria-label="对比基准" defaultValue="current">
              <option value="current">{benchmarkName} (基准)</option>
              <option disabled>中证500</option>
              <option disabled>中证1000</option>
              <option disabled>指数增强同类平均</option>
            </select>
          </label>
          <label>
            采样频率:
            <select
              aria-label="采样频率"
              value={frequency}
              onChange={(event) =>
                setFrequency(event.target.value as typeof frequency)
              }
            >
              <option value="DAILY">日频 (Daily)</option>
              <option value="WEEKLY">周频 (Weekly)</option>
              <option value="MONTHLY">月频 (Monthly)</option>
            </select>
          </label>
        </div>
      </section>
      <section className={styles.trendSection} aria-label="趋势分析">
        <Tabs value={tab} onChange={onTabChange} keepMounted={false}>
          <div className={styles.trendHeader}>
            <Tabs.List aria-label="趋势视图">
              <Tabs.Tab value="nav" leftSection={<ChartLine size={14} />}>
                净值走势 vs 基准超额
              </Tabs.Tab>
              <Tabs.Tab value="drawdown" leftSection={<Waves size={14} />}>
                动态回撤 (Underwater)
              </Tabs.Tab>
              <Tabs.Tab value="rolling" leftSection={<Activity size={14} />}>
                滚动指标演变 (Sharpe/波动率)
              </Tabs.Tab>
            </Tabs.List>
            <div className={styles.trendSummary}>
              <span>
                本基金:{" "}
                <strong className={returnClass("F-RET-003")}>
                  {prototypeFactorText(analysis, "F-RET-003")}
                </strong>
              </span>
              <span>
                {benchmarkName}: <strong>—</strong>
              </span>
              <span>
                超额收益:{" "}
                <strong className={returnClass("F-REL-001")}>
                  {prototypeFactorText(analysis, "F-REL-001")}
                </strong>
              </span>
            </div>
          </div>
          {["nav", "drawdown", "rolling"].map((value) => (
            <Tabs.Panel key={value} value={value}>
              <Suspense
                fallback={
                  <div className={styles.chartCanvas}>
                    <Loader aria-label="正在加载图表" />
                  </div>
                }
              >
                <FundNavChart
                  points={periodPoints}
                  mode={value as FundDetailTab}
                  analysis={analysis}
                  frequency={frequency}
                  benchmarkName={benchmarkName}
                  colorMode={colorMode}
                />
              </Suspense>
            </Tabs.Panel>
          ))}
        </Tabs>
      </section>
      <FactorAnalysisPanel
        analysis={analysis}
        period={factorPeriod}
        benchmarkName={benchmarkName}
        colorMode={colorMode}
        comparisons={panorama.map((query, index) => ({
          period: apiFactorPeriods[index],
          analysis: query.data?.data,
          loading: query.isPending,
          error: query.isError,
        }))}
      />
    </div>
  );
};
