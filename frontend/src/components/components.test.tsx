import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Decision, Operation } from "../api/generated/m17.schemas";
import { ApiError } from "../api/http";
import { ErrorState } from "./ErrorState";
import { formatDate, formatMoney, formatPercent } from "./Formatters";
import { MetricValue } from "./MetricValue";
import { OperationProgress } from "./OperationProgress";
import { ProvenanceBar } from "./ProvenanceBar";
import { ScoreExplainChain } from "./ScoreExplainChain";
import { WeightExplainChain } from "./WeightExplainChain";

const getOperationMock = vi.hoisted(() => vi.fn());

vi.mock("../api/generated/m17", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/generated/m17")>()),
  getOperation: getOperationMock,
}));

const responseFor = (operation: Operation) =>
  Promise.resolve({
    status: 200,
    data: { data: operation, meta: {}, error: null },
    headers: new Headers(),
  });

const withQueryClient = (children: ReactNode) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  );
};

describe("cross-page semantics", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    getOperationMock.mockReset();
  });

  it("does not turn a null metric into zero or a dash", () => {
    render(
      <MetricValue
        value={null}
        status="UNAVAILABLE"
        reason="INSUFFICIENT_SAMPLE"
      />,
    );

    expect(screen.getByText("不可用（INSUFFICIENT_SAMPLE）")).toBeVisible();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.queryByText("-")).not.toBeInTheDocument();
  });

  it("formats decimal percentages only at display time", () => {
    expect(formatPercent(0.0742)).toBe("7.42%");
    expect(formatPercent(-0.01)).toBe("-1.00%");
    // @ts-expect-error null metrics must be handled by MetricValue first
    formatPercent(null);
  });

  it("formats money and dates without changing their transport values", () => {
    expect(formatMoney("1234.5", "CNY")).toBe("¥1,234.50");
    expect(formatDate("2026-09-17")).toBe("2026/09/17");
  });

  it("shows versions, PIT state, and the full quality distribution", () => {
    render(
      <ProvenanceBar
        meta={{
          versions: {
            scoring_policy_version: "score-v3",
            data_version: "dv-9",
          },
          is_point_in_time: true,
          availability_quality_distribution: {
            EXACT: 7,
            DERIVED: 2,
            INFERRED: 1,
          },
        }}
      />,
    );

    expect(screen.getByText("点时数据：是")).toBeVisible();
    expect(screen.getByText("scoring_policy_version: score-v3")).toBeVisible();
    expect(screen.getByText("data_version: dv-9")).toBeVisible();
    expect(screen.getByText("精确 7")).toBeVisible();
    expect(screen.getByText("派生 2")).toBeVisible();
    expect(screen.getByText("推断 1")).toBeVisible();
  });

  it("reports missing provenance fields as a contract error", () => {
    render(<ProvenanceBar meta={{}} />);

    expect(screen.getByRole("alert")).toHaveTextContent("数据溯源契约错误");
    expect(screen.getByText("点时数据：未知")).toBeVisible();
  });

  it("polls a running operation and stops after completion", async () => {
    getOperationMock
      .mockImplementationOnce(() =>
        responseFor({
          operation_id: "OP-1",
          status: "RUNNING",
          progress: { completed: 1, total: 3, unit: "periods" },
          result_ref: null,
          failure: null,
        }),
      )
      .mockImplementationOnce(() =>
        responseFor({
          operation_id: "OP-1",
          status: "COMPLETED",
          progress: { completed: 3, total: 3, unit: "periods" },
          result_ref: "/api/v1/backtests/BT-1/status",
          failure: null,
        }),
      );

    withQueryClient(
      <OperationProgress
        operationId="OP-1"
        resultRef={null}
        pollIntervalMs={10}
      />,
    );

    expect(await screen.findByText("运行中")).toBeVisible();
    expect(await screen.findByText("已完成")).toBeVisible();
    expect(screen.getByText("/api/v1/backtests/BT-1/status")).toBeVisible();
    await waitFor(() => expect(getOperationMock).toHaveBeenCalledTimes(2));
  });

  it("renders operation API envelopes through ErrorState", async () => {
    getOperationMock.mockResolvedValue({
      status: 422,
      data: {
        data: null,
        meta: {},
        error: {
          code: "INVALID_OPERATION",
          message: "Operation cannot be read",
          details: {},
        },
      },
      headers: new Headers(),
    });

    withQueryClient(<OperationProgress operationId="OP-ERR" />);

    expect(
      await screen.findByText("HTTP 422 · INVALID_OPERATION"),
    ).toBeVisible();
    expect(screen.getByText("Operation cannot be read")).toBeVisible();
  });

  it("renders terminal operation failures with stable diagnostics", async () => {
    getOperationMock.mockImplementation(() =>
      responseFor({
        operation_id: "OP-2",
        status: "BLOCKED",
        progress: null,
        result_ref: null,
        failure: { code: "RULE_CONFLICT", message: "Rules conflict" },
      }),
    );

    withQueryClient(<OperationProgress operationId="OP-2" />);

    expect(await screen.findByText("已阻塞")).toBeVisible();
    expect(screen.getByText("RULE_CONFLICT：Rules conflict")).toBeVisible();
    await waitFor(() => expect(getOperationMock).toHaveBeenCalledTimes(1));
  });

  it("preserves HTTP status and API error code", () => {
    render(
      <ErrorState
        error={
          new ApiError(422, {
            code: "INVALID_CONFIGURATION",
            message: "Configuration is invalid",
            details: {},
          })
        }
      />,
    );

    expect(screen.getByText("HTTP 422 · INVALID_CONFIGURATION")).toBeVisible();
    expect(screen.getByText("Configuration is invalid")).toBeVisible();
  });

  it("keeps score attribution statuses and reasons visible", () => {
    render(
      <ScoreExplainChain
        attribution={[
          {
            factor_id: "quality",
            raw_value: null,
            status: "EXCLUDED",
            reason_code: "INSUFFICIENT_SAMPLE",
            weight: 0.25,
          },
        ]}
      />,
    );

    expect(screen.getByText("quality")).toBeVisible();
    expect(screen.getByText("不可用（INSUFFICIENT_SAMPLE）")).toBeVisible();
    expect(screen.getByText("25.00%")).toBeVisible();
  });

  it("shows proposed and final weights with complete PM review details", () => {
    const decision = {
      proposed_weights: [{ fund_id: "000001", weight: 0.15 }],
      final_weights: [{ fund_id: "000001", weight: 0.08 }],
      review: {
        action: "OVERRIDDEN",
        reason: "流动性收紧",
        reviewed_by: "PM-1",
        reviewed_at: "2026-09-17T08:00:00Z",
      },
    } satisfies Pick<Decision, "proposed_weights" | "final_weights" | "review">;

    render(
      <WeightExplainChain
        proposedWeights={decision.proposed_weights}
        finalWeights={decision.final_weights}
        review={decision.review}
      />,
    );

    const proposed = screen.getByRole("region", { name: "原始建议权重" });
    const final = screen.getByRole("region", { name: "最终权重" });
    expect(within(proposed).getByText("000001 15.00%")).toBeVisible();
    expect(within(final).getByText("000001 8.00%")).toBeVisible();
    expect(screen.getByText("复核动作：OVERRIDDEN")).toBeVisible();
    expect(screen.getByText("复核原因：流动性收紧")).toBeVisible();
    expect(screen.getByText("复核人：PM-1")).toBeVisible();
    expect(screen.getByText("复核时间：2026/09/17")).toBeVisible();
  });

  it("renders an unreviewed decision without inventing final weights", () => {
    render(
      <WeightExplainChain
        proposedWeights={[{ fund_id: "000001", weight: 0.15 }]}
        finalWeights={null}
        review={null}
      />,
    );

    expect(screen.getByText("尚未复核，无最终权重")).toBeVisible();
  });
});
