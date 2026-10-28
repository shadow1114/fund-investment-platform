import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { forwardRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { FundNavChart } from "./FundNavChart";

const captured = vi.hoisted(() => ({
  option: null as {
    xAxis: { data: string[] };
    series: { data: unknown[]; connectNulls: boolean }[];
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
});
