import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { Decision } from "../../api/generated/m17.schemas";
import { renderWithMantine } from "../../test/render";
import { DecisionReviewPanel } from "./DecisionReviewPanel";

afterEach(cleanup);

it("keeps weight edits bound to fund IDs after sorting and paging, with decimal units and sum validation", async () => {
  const onReview = vi.fn();
  const proposed_weights = Array.from({ length: 21 }, (_, index) => ({
    fund_id: String(index + 1).padStart(6, "0"),
    weight: index === 0 ? 0.5 : 0.025,
  }));
  const decision: Decision = {
    decision_id: "D1",
    portfolio_id: "P1",
    optimization_id: "O1",
    decision_status: "PROPOSED",
    proposed_weights,
    final_weights: null,
    review: null,
  };
  renderWithMantine(
    <DecisionReviewPanel
      decision={decision}
      canReview
      pending={false}
      error={null}
      onReview={onReview}
    />,
  );
  const grid = await screen.findByRole("grid", { name: "决策覆盖权重" });
  await screen.findByLabelText("000001 覆盖权重");
  const header = within(grid).getByRole("columnheader", { name: "基金" });
  await userEvent.click(within(header).getByText("基金", { exact: true }));
  await userEvent.click(within(header).getByText("基金", { exact: true }));
  fireEvent.change(await screen.findByLabelText("000021 覆盖权重"), {
    target: { value: "0.03" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: /复核理由/ }), {
    target: { value: "调整权重" },
  });
  expect(screen.getByRole("button", { name: "确认覆盖" })).toBeDisabled();
  const table = screen.getByRole("region", { name: "可编辑覆盖权重" });
  await userEvent.click(within(table).getByRole("button", { name: "下一页" }));
  fireEvent.change(await screen.findByLabelText("000001 覆盖权重"), {
    target: { value: "0.495" },
  });
  expect(
    screen.getByText("覆盖权重合计：100.00%（提交要求约为 100%）"),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "确认覆盖" }));
  await userEvent.click(
    await screen.findByRole("button", { name: "确认提交" }),
  );
  expect(onReview).toHaveBeenCalledWith({
    action: "OVERRIDDEN",
    reason: "调整权重",
    overridden_weights: proposed_weights.map((item) => ({
      ...item,
      weight:
        item.fund_id === "000001"
          ? 0.495
          : item.fund_id === "000021"
            ? 0.03
            : item.weight,
    })),
  });
});
