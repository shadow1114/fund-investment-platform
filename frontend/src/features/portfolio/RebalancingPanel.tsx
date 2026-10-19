import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  evaluateRebalance,
  fetchHistoricalRebalances,
  type RebalanceProposalView,
} from "../../api/rebalance";
import { formatMoney, formatPercent } from "../../components/Formatters";

type Props = {
  portfolioId: string;
};

export const RebalancingPanel = ({ portfolioId }: Props) => {
  const queryClient = useQueryClient();
  const [decisionAt, setDecisionAt] = useState("2026-03-31");
  const [driftThreshold, setDriftThreshold] = useState("0.03");
  const [minTradeThreshold, setMinTradeThreshold] = useState("0.005");
  const [expectedImprovement, setExpectedImprovement] = useState("0.02");
  const [proposal, setProposal] = useState<RebalanceProposalView | null>(null);

  const { data: historicalEvents } = useQuery({
    queryKey: ["historicalRebalances", portfolioId],
    queryFn: () => fetchHistoricalRebalances(portfolioId),
  });

  const evalMutation = useMutation({
    mutationFn: () =>
      evaluateRebalance(portfolioId, {
        decision_at: decisionAt,
        prices: { "000001": 1.25, "000002": 0.85 },
        fund_drift_threshold: Number(driftThreshold) || 0.03,
        min_trade_threshold: Number(minTradeThreshold) || 0.005,
        fee_rate: 0.0015,
        expected_annualized_improvement: Number(expectedImprovement) || 0.02,
      }),
    onSuccess: (data) => {
      setProposal(data);
      queryClient.invalidateQueries({
        queryKey: ["historicalRebalances", portfolioId],
      });
      queryClient.invalidateQueries({
        queryKey: ["livePortfolio", portfolioId],
      });
    },
  });

  const handleEvaluate = (e: React.FormEvent) => {
    e.preventDefault();
    evalMutation.mutate();
  };

  const outcomeColors: Record<
    string,
    { bg: string; text: string; label: string }
  > = {
    RECOMMENDED: {
      bg: "#def7ec",
      text: "#03543f",
      label: "✅ 建议执行调仓（RECOMMENDED）",
    },
    SKIPPED_COST_BENEFIT: {
      bg: "#fef3c7",
      text: "#92400e",
      label: "⏸️ 放弃调仓：预期改善不足以覆盖交易成本（SKIPPED_COST_BENEFIT）",
    },
    SKIPPED_PENDING_EXISTS: {
      bg: "#fee2e2",
      text: "#991b1b",
      label:
        "🛑 跳过：存在未确认在途委托，防止重复下单（SKIPPED_PENDING_EXISTS）",
    },
    SKIPPED_FILTERED: {
      bg: "#f1f5f9",
      text: "#475569",
      label: "⏸️ 跳过：所有调仓量均低于最小交易门槛（SKIPPED_FILTERED）",
    },
    SKIPPED_NO_DELTA: {
      bg: "#f1f5f9",
      text: "#475569",
      label: "⏸️ 跳过：当前权重与目标完全吻合，无需调仓（SKIPPED_NO_DELTA）",
    },
  };

  return (
    <section
      aria-label="动态再平衡与调仓建议"
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: "8px",
        padding: "1.5rem",
        marginTop: "1.5rem",
        backgroundColor: "#ffffff",
      }}
    >
      <h2>动态再平衡与调仓引擎（Stage ⑩ Rebalancing）</h2>
      <p style={{ color: "#64748b", fontSize: "0.875rem" }}>
        基于偏离度（Drift）、调仓周期（Periodic）、基金受限事件与合规约束自动多触发合并计算，产出结构化调仓清单。
      </p>

      <form
        onSubmit={handleEvaluate}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "1rem",
          padding: "1rem",
          backgroundColor: "#f8fafc",
          borderRadius: "6px",
          margin: "1rem 0",
        }}
      >
        <label style={{ fontSize: "0.875rem" }}>
          决策基准日：
          <input
            type="date"
            value={decisionAt}
            onChange={(e) => setDecisionAt(e.target.value)}
            style={{
              display: "block",
              marginTop: "0.25rem",
              padding: "0.25rem 0.5rem",
              width: "100%",
            }}
            required
          />
        </label>

        <label style={{ fontSize: "0.875rem" }}>
          偏离触发阈值：
          <input
            type="number"
            step="0.005"
            value={driftThreshold}
            onChange={(e) => setDriftThreshold(e.target.value)}
            style={{
              display: "block",
              marginTop: "0.25rem",
              padding: "0.25rem 0.5rem",
              width: "100%",
            }}
            required
          />
        </label>

        <label style={{ fontSize: "0.875rem" }}>
          最小交易门槛：
          <input
            type="number"
            step="0.001"
            value={minTradeThreshold}
            onChange={(e) => setMinTradeThreshold(e.target.value)}
            style={{
              display: "block",
              marginTop: "0.25rem",
              padding: "0.25rem 0.5rem",
              width: "100%",
            }}
            required
          />
        </label>

        <label style={{ fontSize: "0.875rem" }}>
          预期年化改善：
          <input
            type="number"
            step="0.005"
            value={expectedImprovement}
            onChange={(e) => setExpectedImprovement(e.target.value)}
            style={{
              display: "block",
              marginTop: "0.25rem",
              padding: "0.25rem 0.5rem",
              width: "100%",
            }}
            required
          />
        </label>

        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button
            type="submit"
            disabled={evalMutation.isPending}
            style={{
              width: "100%",
              padding: "0.5rem 1rem",
              backgroundColor: "#059669",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
          >
            {evalMutation.isPending ? "评估计算中…" : "发起再平衡评估"}
          </button>
        </div>
      </form>

      {evalMutation.error && (
        <div role="alert" style={{ color: "#dc2626", margin: "1rem 0" }}>
          评估出错：
          {evalMutation.error instanceof Error
            ? evalMutation.error.message
            : "未知错误"}
        </div>
      )}

      {proposal && (
        <div style={{ marginTop: "1.5rem" }}>
          <div
            style={{
              padding: "1rem",
              borderRadius: "6px",
              backgroundColor:
                outcomeColors[proposal.decision_outcome]?.bg ?? "#f1f5f9",
              color:
                outcomeColors[proposal.decision_outcome]?.text ?? "#1e293b",
              border: "1px solid #e2e8f0",
              marginBottom: "1rem",
            }}
          >
            <div style={{ fontWeight: "bold", fontSize: "1.1rem" }}>
              {outcomeColors[proposal.decision_outcome]?.label ??
                proposal.decision_outcome}
            </div>
            <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.875rem" }}>
              {proposal.explainability_summary}
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "1rem",
              marginBottom: "1.5rem",
            }}
          >
            <div
              style={{
                padding: "0.75rem",
                backgroundColor: "#f8fafc",
                borderRadius: "6px",
              }}
            >
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                单边换手率 (Turnover)
              </span>
              <div
                style={{
                  fontSize: "1.2rem",
                  fontWeight: "bold",
                  color: "#1e293b",
                }}
              >
                {formatPercent(proposal.turnover)}
              </div>
            </div>
            <div
              style={{
                padding: "0.75rem",
                backgroundColor: "#f8fafc",
                borderRadius: "6px",
              }}
            >
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                预估摩擦成本
              </span>
              <div
                style={{
                  fontSize: "1.2rem",
                  fontWeight: "bold",
                  color: "#dc2626",
                }}
              >
                {formatMoney(proposal.estimated_cost)}
              </div>
            </div>
            <div
              style={{
                padding: "0.75rem",
                backgroundColor: "#f8fafc",
                borderRadius: "6px",
              }}
            >
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                预期年化改善
              </span>
              <div
                style={{
                  fontSize: "1.2rem",
                  fontWeight: "bold",
                  color: "#16a34a",
                }}
              >
                {formatPercent(proposal.expected_improvement)}
              </div>
            </div>
            <div
              style={{
                padding: "0.75rem",
                backgroundColor: "#f8fafc",
                borderRadius: "6px",
              }}
            >
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                重算范围 (Scope)
              </span>
              <div
                style={{
                  fontSize: "0.95rem",
                  fontWeight: "bold",
                  color: "#4f46e5",
                }}
              >
                {proposal.recompute_scope || "无需重算"}
              </div>
            </div>
          </div>

          <h3>建议调仓买卖交易清单（Rebalancing Trades）</h3>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.875rem",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "2px solid #e2e8f0",
                    backgroundColor: "#f1f5f9",
                  }}
                >
                  <th style={{ padding: "0.5rem" }}>基金代码</th>
                  <th style={{ padding: "0.5rem" }}>交易方向</th>
                  <th style={{ padding: "0.5rem" }}>当前权重</th>
                  <th style={{ padding: "0.5rem" }}>目标权重</th>
                  <th style={{ padding: "0.5rem" }}>权重调整 (Δw)</th>
                  <th style={{ padding: "0.5rem" }}>测算交易金额</th>
                  <th style={{ padding: "0.5rem" }}>测算交易份额</th>
                  <th style={{ padding: "0.5rem" }}>准入状态</th>
                  <th style={{ padding: "0.5rem" }}>处置说明</th>
                </tr>
              </thead>
              <tbody>
                {proposal.trades.length === 0 ? (
                  <tr>
                    <td
                      colSpan={9}
                      style={{
                        padding: "1rem",
                        textAlign: "center",
                        color: "#64748b",
                      }}
                    >
                      无调仓交易产生
                    </td>
                  </tr>
                ) : (
                  proposal.trades.map((t) => (
                    <tr
                      key={t.fund_id}
                      style={{ borderBottom: "1px solid #f1f5f9" }}
                    >
                      <td style={{ padding: "0.5rem", fontWeight: "bold" }}>
                        {t.fund_id}
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        <span
                          style={{
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontWeight: "bold",
                            fontSize: "0.75rem",
                            backgroundColor:
                              t.direction === "BUY" ? "#def7ec" : "#fee2e2",
                            color:
                              t.direction === "BUY" ? "#03543f" : "#991b1b",
                          }}
                        >
                          {t.direction === "BUY" ? "买入加仓" : "卖出减仓"}
                        </span>
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        {formatPercent(t.current_weight)}
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        {formatPercent(t.target_weight)}
                      </td>
                      <td style={{ padding: "0.5rem", fontWeight: "bold" }}>
                        {t.weight_delta > 0
                          ? `+${formatPercent(t.weight_delta)}`
                          : formatPercent(t.weight_delta)}
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        {formatMoney(t.estimated_amount)}
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        {Math.round(t.delta_shares).toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem" }}>
                        {t.eligibility_status}
                      </td>
                      <td
                        style={{
                          padding: "0.5rem",
                          color: t.is_filtered ? "#dc2626" : "#059669",
                        }}
                      >
                        {t.is_filtered
                          ? t.unachieved_reason || "被阈值过滤"
                          : "正常执行"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {historicalEvents && historicalEvents.length > 0 && (
        <div style={{ marginTop: "2rem" }}>
          <h4>历史再平衡事件记录</h4>
          <ul
            style={{
              fontSize: "0.875rem",
              paddingLeft: "1.25rem",
              color: "#475569",
            }}
          >
            {historicalEvents.map((evt, idx) => (
              <li key={idx} style={{ marginBottom: "0.35rem" }}>
                <strong>{String(evt.decision_at)}</strong> — 触发原因:{" "}
                {String(evt.primary_trigger || "手动评估")}, 结果:{" "}
                {String(evt.outcome)}, 换手率:{" "}
                {typeof evt.turnover === "number"
                  ? formatPercent(evt.turnover)
                  : "0%"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};
