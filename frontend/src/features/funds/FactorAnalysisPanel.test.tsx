import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { FundFactorAnalysis } from "../../api/generated/m17.schemas";
import { FactorAnalysisPanel } from "./FactorAnalysisPanel";

const data: FundFactorAnalysis = {
  fund_id: "000001",
  evaluation_period: "1Y",
  as_of_date: "2026-10-31",
  factor_categories: [
    {
      category: "RET",
      name: "收益表现",
      factors: [
        {
          factor_id: "F-RET-001",
          name: "年化收益率",
          category: "RET",
          direction: "HIGHER_IS_BETTER",
          raw_value: 0.1234,
          normalized_value: null,
          status: "VALID",
          reason_code: null,
          observations: 252,
          series: [],
        },
      ],
    },
    {
      category: "RISK",
      name: "风险指标",
      factors: [
        {
          factor_id: "F-RISK-004",
          name: "VaR 95%",
          category: "RISK",
          direction: "LOWER_IS_BETTER",
          raw_value: null,
          normalized_value: null,
          status: "UNAVAILABLE",
          reason_code: "INSUFFICIENT_OBSERVATIONS",
          observations: 20,
          series: [],
        },
      ],
    },
  ],
};

describe("FactorAnalysisPanel", () => {
  it("groups metrics by category, explains unavailable values, and changes period", async () => {
    const user = userEvent.setup();
    const onPeriodChange = vi.fn();
    render(
      <MantineProvider>
        <FactorAnalysisPanel
          analysis={data}
          period="1Y"
          onPeriodChange={onPeriodChange}
        />
      </MantineProvider>,
    );

    expect(screen.getByRole("heading", { name: "收益表现" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "风险指标" })).toBeVisible();
    expect(await screen.findByText("12.34%", { exact: true })).toBeVisible();
    expect(
      screen.getByText("不可用（INSUFFICIENT_OBSERVATIONS）"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "近5年" }));
    expect(onPeriodChange).toHaveBeenCalledWith("5Y");
  });

  it("keeps period selection available before results load", async () => {
    const user = userEvent.setup();
    const onPeriodChange = vi.fn();
    render(
      <MantineProvider>
        <FactorAnalysisPanel period="1Y" onPeriodChange={onPeriodChange} />
      </MantineProvider>,
    );

    await user.click(screen.getAllByRole("button", { name: "近半年" }).at(-1)!);
    expect(onPeriodChange).toHaveBeenCalledWith("6M");
  });
});
