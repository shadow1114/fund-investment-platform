import { MantineProvider } from "@mantine/core";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { forwardRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);
import { FundNavChart } from "./FundNavChart";

const captured = vi.hoisted(() => ({
  option: null as {
    xAxis: { data: string[] };
    series: {
      name: string;
      type: string;
      data: unknown[];
      connectNulls: boolean;
    }[];
  } | null,
}));
vi.mock("echarts-for-react/lib/core", () => ({
  default: forwardRef<
    HTMLDivElement,
    { option: NonNullable<typeof captured.option> }
  >((_props, ref) => {
    captured.option = _props.option;
    return <div ref={ref} aria-label="净值图" />;
  }),
}));

describe("FundNavChart", () => {
  it("支持单独隐藏和恢复曲线，其他曲线不变", async () => {
    const user = userEvent.setup();
    render(
      <MantineProvider>
        <FundNavChart
          points={[
            {
              date: "2026-01-01",
              nav: 1,
              nav_status: "VALID",
              nav_reason: null,
            },
            {
              date: "2026-01-02",
              nav: 1.2,
              nav_status: "VALID",
              nav_reason: null,
            },
          ]}
          benchmarkName="指数A"
          benchmarkSeries={[
            {
              benchmark_id: "1",
              benchmark_name: "指数A",
              weight: 1,
              points: [
                { date: "2026-01-01", value: 100 },
                { date: "2026-01-02", value: 110 },
              ],
            },
          ]}
        />
      </MantineProvider>,
    );
    const fund = captured.option?.series[0].data;
    const control = screen.getByRole("checkbox", { name: "指数A (%)" });
    await user.click(control);
    expect(captured.option?.series[1].data).toEqual([]);
    expect(captured.option?.series[0].data).toEqual(fund);
    await user.click(control);
    expect(captured.option?.series[1].data).toHaveLength(2);
    expect(control).toBeChecked();
  });
  it("keeps missing dates on the axis and breaks the series at unavailable values", () => {
    render(
      <MantineProvider>
        <FundNavChart
          points={[
            {
              date: "2026-01-01",
              nav: 1,
              nav_status: "VALID",
              nav_reason: null,
            },
            {
              date: "2026-01-02",
              nav: null,
              nav_status: "UNAVAILABLE",
              nav_reason: "MISSING",
            },
            {
              date: "2026-01-03",
              nav: 2,
              nav_status: "VALID",
              nav_reason: null,
            },
          ]}
        />
      </MantineProvider>,
    );
    expect(
      screen.getByRole("region", { name: "净值数值表", hidden: true }),
    ).toHaveAttribute("tabindex", "0");
    expect(captured.option?.xAxis.data).toEqual([
      "2026-01-01",
      "2026-01-02",
      "2026-01-03",
    ]);
    expect(captured.option?.series[0].data[1]).toEqual(["2026-01-02", null]);
    expect(captured.option?.series[0].connectNulls).toBe(false);
  });
  it("renders excess return as bars while fund and benchmark remain lines", () => {
    render(
      <MantineProvider>
        <FundNavChart
          points={[
            {
              date: "2026-01-01",
              nav: 1,
              nav_status: "VALID",
              nav_reason: null,
            },
            {
              date: "2026-01-02",
              nav: 1.1,
              nav_status: "VALID",
              nav_reason: null,
            },
          ]}
          benchmarkSeries={[
            {
              benchmark_id: "1",
              benchmark_name: "指数A",
              weight: 1,
              points: [
                { date: "2026-01-01", value: 100 },
                { date: "2026-01-02", value: 105 },
              ],
            },
          ]}
        />
      </MantineProvider>,
    );
    expect(captured.option?.series.map((item) => item.type)).toEqual([
      "line",
      "line",
      "bar",
    ]);
    expect(captured.option?.series[2].name).toBe("超额收益 (%)");
    expect(captured.option?.series[2].data[0]).toEqual(["2026-01-01", 0]);
    expect(
      (captured.option?.series[2].data[1] as [string, number])[1],
    ).toBeCloseTo(5);
  });
});
