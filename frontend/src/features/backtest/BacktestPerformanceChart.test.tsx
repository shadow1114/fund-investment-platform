import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type {
  BacktestPerformance,
  SeriesPoint,
} from "../../api/generated/m17.schemas";
import { BacktestPerformanceChart } from "./BacktestPerformanceChart";

const point = (
  date: string,
  value: number | null,
  value_status: SeriesPoint["value_status"],
  value_reason: string | null,
): SeriesPoint => ({ date, value, value_status, value_reason });

afterEach(cleanup);

describe("BacktestPerformanceChart", () => {
  it("keeps null dates and their status and reason visible across performance series", () => {
    const performance: BacktestPerformance = {
      segment: "FULL",
      series: {
        portfolio_value: [],
        cumulative_return: {
          portfolio: [
            point("2026-06-29", 0.1, "VALID", null),
            point("2026-06-30", null, "UNAVAILABLE", "NAV_MISSING"),
          ],
          benchmark: [point("2026-06-30", 0.08, "VALID", null)],
          equal_weight_baseline: null,
          equal_weight_baseline_status: "UNAVAILABLE",
          equal_weight_baseline_reason: "BASELINE_DISABLED",
        },
        drawdown: [],
        rolling_sharpe: [
          point("2026-06-28", null, "UNAVAILABLE", "INSUFFICIENT_SAMPLE"),
        ],
        rolling_excess_return: [],
      },
    };

    render(<BacktestPerformanceChart performance={performance} />);

    const unavailable = screen.getByRole("region", { name: "不可用绩效点位" });
    expect(
      within(unavailable).getByText(/组合累计收益.*2026-06-30.*NAV_MISSING/),
    ).toBeVisible();
    expect(
      within(unavailable).getByText(
        /滚动夏普.*2026-06-28.*INSUFFICIENT_SAMPLE/,
      ),
    ).toBeVisible();
  });
});
