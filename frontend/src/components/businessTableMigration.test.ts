import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";

const tables = [
  "pages/UniverseSnapshotPage.tsx",
  "features/universe/UniverseTable.tsx",
  "features/portfolio/PortfolioList.tsx",
  "features/ingestion/IngestionHistoryTable.tsx",
  "features/ingestion/IngestionTaskDetail.tsx",
  "features/funds/FactorAnalysisPanel.tsx",
  "features/funds/FundMetrics.tsx",
  "features/funds/FundNavChart.tsx",
  "features/backtest/BacktestPerformanceChart.tsx",
  "features/portfolio/DecisionReviewPanel.tsx",
  "features/portfolio/LivePortfolioPanel.tsx",
  "features/portfolio/RebalancingPanel.tsx",
];

it.each(tables)("%s uses the single shared AG Grid renderer", (file) => {
  const source = readFileSync(resolve("src", file), "utf8");
  expect(source).toContain("<ResearchDataTable");
  expect(source).not.toMatch(
    /<Table[.\s>]|<table[\s>]|useReactTable|@tanstack\/react-table/,
  );
});
