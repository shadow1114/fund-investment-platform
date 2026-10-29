import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  BacktestPerformance,
  SeriesPoint,
} from "../../api/generated/m17.schemas";
import { BacktestPerformanceChart } from "./BacktestPerformanceChart";
import { renderWithMantine as render } from "../../test/render";

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: { series: { name: string }[] } }) => (
    <div aria-label="回测绩效图">
      {option.series.map((series) => series.name).join("、")}
    </div>
  ),
}));

const point = (
  date: string,
  value: number | null,
  value_status: SeriesPoint["value_status"],
  value_reason: string | null,
): SeriesPoint => ({ date, value, value_status, value_reason });

afterEach(cleanup);

describe("BacktestPerformanceChart", () => {
  it("keeps null dates and their status and reason visible across performance series", async () => {
    const user = userEvent.setup();
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
    await user.click(screen.getByText("查看图表数值"));

    const cumulative = screen.getByRole("region", {
      name: "累计收益数值表",
    });
    expect(within(cumulative).getByText("NAV_MISSING")).toBeVisible();
    expect(within(cumulative).getByText("UNAVAILABLE")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "滚动 Sharpe" }));
    const rollingSharpe = screen.getByRole("region", {
      name: "滚动 Sharpe数值表",
    });
    expect(
      within(rollingSharpe).getByText("INSUFFICIENT_SAMPLE"),
    ).toBeVisible();
  });
});
