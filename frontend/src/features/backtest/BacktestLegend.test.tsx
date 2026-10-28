import { MantineProvider } from "@mantine/core";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { forwardRef } from "react";
import { expect, it, vi } from "vitest";
import type { BacktestPerformance } from "../../api/generated/m17.schemas";
import { backtestPerformanceEnvelope } from "../../test/contractFixtures";
import { BacktestPerformanceChart } from "./BacktestPerformanceChart";

vi.mock("echarts-for-react/lib/core", () => ({
  default: forwardRef<HTMLDivElement>((_props, ref) => <div ref={ref} />),
}));

it("labels the plotted series and updates the legend when the metric changes", async () => {
  const user = userEvent.setup();
  render(
    <MantineProvider>
      <BacktestPerformanceChart
        performance={backtestPerformanceEnvelope.data as BacktestPerformance}
      />
    </MantineProvider>,
  );
  const legend = screen.getByRole("list", { name: "图表图例" });
  expect(within(legend).getByText("组合")).toBeVisible();
  expect(within(legend).getByText("基准")).toBeVisible();
  await user.click(screen.getByRole("tab", { name: "回撤" }));
  expect(within(legend).getByText("回撤")).toBeVisible();
  expect(within(legend).queryByText("基准")).not.toBeInTheDocument();
});
