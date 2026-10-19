import { apiFetch } from "./client";

export type PositionView = {
  fund_id: string;
  state: "ACTUAL" | "TARGET" | "PENDING" | string;
  shares: number;
  cost_basis: number;
  market_price: number;
  market_value: number;
  weight: number;
  holding_days: number;
};

export type LivePortfolioView = {
  portfolio_id: string;
  as_of_date: string;
  status: string;
  cash_balance: number;
  total_equity: number;
  has_pending_execution: boolean;
  target_positions: PositionView[];
  pending_positions: PositionView[];
  actual_positions: PositionView[];
  last_rebalanced_at: string | null;
};

export type ExecutionReportPayload = {
  report_id: string;
  fund_id: string;
  direction: "BUY" | "SELL";
  requested_shares: number;
  filled_shares: number;
  filled_price: number;
  fee?: number;
  status: "SUBMITTED" | "PARTIALLY_FILLED" | "FILLED" | "REJECTED" | "EXPIRED";
  rebalance_id?: string | null;
};

export type ExecutionReportResult = {
  report_id: string;
  portfolio_id: string;
  status: string;
  has_pending_execution: boolean;
  total_equity: number;
  cash_balance: number;
};

export type EvaluateRebalancePayload = {
  decision_at: string;
  prices: Record<string, number>;
  fund_drift_threshold?: number;
  category_drift_threshold?: number;
  min_trade_threshold?: number;
  fee_rate?: number;
  expected_annualized_improvement?: number;
};

export type RebalanceTradeView = {
  fund_id: string;
  direction: string;
  target_weight: number;
  current_weight: number;
  weight_delta: number;
  target_shares: number;
  delta_shares: number;
  estimated_amount: number;
  eligibility_status: string;
  is_filtered: boolean;
  unachieved_reason?: string | null;
};

export type RebalanceProposalView = {
  is_triggered: boolean;
  trigger_types: string[];
  primary_trigger: string | null;
  recompute_scope: string | null;
  decision_outcome: string;
  turnover: number;
  estimated_cost: number;
  expected_improvement: number;
  trades: RebalanceTradeView[];
  unachieved_targets: Record<string, string>;
  explainability_summary: string;
};

export type ApiResponse<T> = {
  data: {
    data: T;
    meta: Record<string, unknown>;
    error: null | { code: string; message: string };
  };
  status: number;
};

export async function fetchLivePortfolio(
  portfolioId: string,
): Promise<LivePortfolioView> {
  const res = await apiFetch<ApiResponse<LivePortfolioView>>(
    `/api/v1/portfolios/${portfolioId}/live`,
  );
  return res.data.data;
}

export async function submitExecutionReport(
  portfolioId: string,
  payload: ExecutionReportPayload,
): Promise<ExecutionReportResult> {
  const res = await apiFetch<ApiResponse<ExecutionReportResult>>(
    `/api/v1/portfolios/${portfolioId}/execution-reports`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return res.data.data;
}

export async function evaluateRebalance(
  portfolioId: string,
  payload: EvaluateRebalancePayload,
): Promise<RebalanceProposalView> {
  const res = await apiFetch<ApiResponse<RebalanceProposalView>>(
    `/api/v1/portfolios/${portfolioId}/rebalances/evaluate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return res.data.data;
}

export async function fetchHistoricalRebalances(
  portfolioId: string,
): Promise<Array<Record<string, unknown>>> {
  const res = await apiFetch<ApiResponse<Array<Record<string, unknown>>>>(
    `/api/v1/portfolios/${portfolioId}/rebalances`,
  );
  return res.data.data;
}
