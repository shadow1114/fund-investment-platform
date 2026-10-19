import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  fetchLivePortfolio,
  submitExecutionReport,
  type ExecutionReportPayload,
} from "../../api/rebalance";
import { formatMoney, formatPercent } from "../../components/Formatters";

type Props = {
  portfolioId: string;
};

export const LivePortfolioPanel = ({ portfolioId }: Props) => {
  const queryClient = useQueryClient();
  const [fillFundId, setFillFundId] = useState("");
  const [fillShares, setFillShares] = useState("10000");
  const [fillPrice, setFillPrice] = useState("1.0");
  const [fillDirection, setFillDirection] = useState<"BUY" | "SELL">("BUY");

  const {
    data: liveData,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["livePortfolio", portfolioId],
    queryFn: () => fetchLivePortfolio(portfolioId),
  });

  const fillMutation = useMutation({
    mutationFn: (payload: ExecutionReportPayload) =>
      submitExecutionReport(portfolioId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["livePortfolio", portfolioId],
      });
    },
  });

  if (isLoading) {
    return <p role="status">正在读取实盘三态持仓…</p>;
  }

  if (isError || !liveData) {
    return (
      <div role="alert" style={{ color: "#c00", padding: "1rem" }}>
        读取实盘持仓失败：{error instanceof Error ? error.message : "未知错误"}
      </div>
    );
  }

  // Build union list of funds across Target, Actual, Pending
  const targetMap = new Map(
    liveData.target_positions.map((p) => [p.fund_id, p]),
  );
  const actualMap = new Map(
    liveData.actual_positions.map((p) => [p.fund_id, p]),
  );
  const pendingMap = new Map(
    liveData.pending_positions.map((p) => [p.fund_id, p]),
  );

  const allFundIds = Array.from(
    new Set([...targetMap.keys(), ...actualMap.keys(), ...pendingMap.keys()]),
  ).sort();

  const handleSimulateFill = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fillFundId.trim()) return;

    fillMutation.mutate({
      report_id: `FILL-${Date.now()}`,
      fund_id: fillFundId.trim(),
      direction: fillDirection,
      requested_shares: Number(fillShares) || 0,
      filled_shares: Number(fillShares) || 0,
      filled_price: Number(fillPrice) || 1.0,
      fee: 5.0,
      status: "FILLED",
    });
  };

  return (
    <section
      aria-label="实盘持仓与三态监控"
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: "8px",
        padding: "1.5rem",
        marginTop: "1.5rem",
        backgroundColor: "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h2>实盘三态持仓监控（Stage ⑨ Live Portfolio）</h2>
        <span
          style={{
            padding: "0.25rem 0.75rem",
            borderRadius: "4px",
            fontSize: "0.875rem",
            fontWeight: "bold",
            backgroundColor:
              liveData.status === "ACTIVE" ? "#def7ec" : "#fef08a",
            color: liveData.status === "ACTIVE" ? "#03543f" : "#713f12",
          }}
        >
          状态：{liveData.status}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "1rem",
          margin: "1rem 0",
          padding: "1rem",
          backgroundColor: "#f8fafc",
          borderRadius: "6px",
        }}
      >
        <div>
          <span style={{ fontSize: "0.875rem", color: "#64748b" }}>
            组合总净资产
          </span>
          <div style={{ fontSize: "1.25rem", fontWeight: "bold" }}>
            {formatMoney(liveData.total_equity)}
          </div>
        </div>
        <div>
          <span style={{ fontSize: "0.875rem", color: "#64748b" }}>
            现金可用余额
          </span>
          <div style={{ fontSize: "1.25rem", fontWeight: "bold" }}>
            {formatMoney(liveData.cash_balance)}
          </div>
        </div>
        <div>
          <span style={{ fontSize: "0.875rem", color: "#64748b" }}>
            在途挂单防护
          </span>
          <div
            style={{
              fontSize: "1rem",
              fontWeight: "bold",
              color: liveData.has_pending_execution ? "#d97706" : "#059669",
            }}
          >
            {liveData.has_pending_execution
              ? "⚠️ 存在未成交委托 (Pending)"
              : "✅ 无在途挂单"}
          </div>
        </div>
        <div>
          <span style={{ fontSize: "0.875rem", color: "#64748b" }}>
            基准日期
          </span>
          <div style={{ fontSize: "1rem", fontWeight: "500" }}>
            {liveData.as_of_date}
          </div>
        </div>
      </div>

      {liveData.has_pending_execution && (
        <div
          role="alert"
          style={{
            padding: "0.75rem 1rem",
            marginBottom: "1rem",
            backgroundColor: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: "6px",
            color: "#92400e",
            fontSize: "0.875rem",
          }}
        >
          <strong>防重复调仓约束：</strong>{" "}
          当前组合存在已交付但尚未确认回报的委托，系统已自动加锁，禁止重复生成调仓指令。
        </div>
      )}

      <h3>三态资产透视表（Target vs Actual vs Pending）</h3>
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
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
              <th style={{ padding: "0.5rem" }}>目标权重 (Target)</th>
              <th style={{ padding: "0.5rem" }}>实际权重 (Actual)</th>
              <th style={{ padding: "0.5rem" }}>权重偏离 (Drift)</th>
              <th style={{ padding: "0.5rem" }}>实际持有份额</th>
              <th style={{ padding: "0.5rem" }}>盯市现价</th>
              <th style={{ padding: "0.5rem" }}>当前市值</th>
              <th style={{ padding: "0.5rem" }}>在途委托份额 (Pending)</th>
            </tr>
          </thead>
          <tbody>
            {allFundIds.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  style={{
                    padding: "1rem",
                    textAlign: "center",
                    color: "#64748b",
                  }}
                >
                  暂无持仓或目标记录
                </td>
              </tr>
            ) : (
              allFundIds.map((fundId) => {
                const target = targetMap.get(fundId);
                const actual = actualMap.get(fundId);
                const pending = pendingMap.get(fundId);

                const targetW = target?.weight ?? 0.0;
                const actualW = actual?.weight ?? 0.0;
                const drift = actualW - targetW;

                return (
                  <tr
                    key={fundId}
                    style={{ borderBottom: "1px solid #f1f5f9" }}
                  >
                    <td style={{ padding: "0.5rem", fontWeight: "bold" }}>
                      {fundId}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {formatPercent(targetW)}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {formatPercent(actualW)}
                    </td>
                    <td
                      style={{
                        padding: "0.5rem",
                        fontWeight: "bold",
                        color:
                          Math.abs(drift) > 0.03
                            ? "#dc2626"
                            : drift >= 0
                              ? "#16a34a"
                              : "#2563eb",
                      }}
                    >
                      {drift > 0
                        ? `+${formatPercent(drift)}`
                        : formatPercent(drift)}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {actual ? Number(actual.shares).toLocaleString() : "0"}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {actual ? formatMoney(actual.market_price) : "-"}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {actual
                        ? formatMoney(actual.market_value)
                        : formatMoney(0)}
                    </td>
                    <td
                      style={{
                        padding: "0.5rem",
                        color: pending ? "#d97706" : "#64748b",
                        fontWeight: pending ? "bold" : "normal",
                      }}
                    >
                      {pending
                        ? `${Number(pending.shares).toLocaleString()} 份`
                        : "-"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          backgroundColor: "#f8fafc",
          borderRadius: "6px",
          border: "1px dashed #cbd5e1",
        }}
      >
        <h4 style={{ margin: "0 0 0.5rem 0" }}>
          ⚡️ 本地模拟成交回报注入（Execution Fill Simulator）
        </h4>
        <p
          style={{ margin: "0 0 1rem 0", fontSize: "0.8rem", color: "#64748b" }}
        >
          无需真实券商接口，可直接在本地模拟外部清算柜台推送成交回报，驱动实际持仓与现金更新。
        </p>
        <form
          onSubmit={handleSimulateFill}
          style={{
            display: "flex",
            gap: "0.75rem",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <label style={{ fontSize: "0.875rem" }}>
            基金代码：
            <input
              list="existing-funds"
              value={fillFundId}
              onChange={(e) => setFillFundId(e.target.value)}
              placeholder="如 000001"
              required
              style={{
                padding: "0.25rem 0.5rem",
                marginLeft: "0.25rem",
                width: "100px",
              }}
            />
            <datalist id="existing-funds">
              {allFundIds.map((id) => (
                <option key={id} value={id} />
              ))}
            </datalist>
          </label>

          <label style={{ fontSize: "0.875rem" }}>
            方向：
            <select
              value={fillDirection}
              onChange={(e) =>
                setFillDirection(e.target.value as "BUY" | "SELL")
              }
              style={{ padding: "0.25rem 0.5rem", marginLeft: "0.25rem" }}
            >
              <option value="BUY">买入（BUY）</option>
              <option value="SELL">卖出（SELL）</option>
            </select>
          </label>

          <label style={{ fontSize: "0.875rem" }}>
            成交份额：
            <input
              type="number"
              value={fillShares}
              onChange={(e) => setFillShares(e.target.value)}
              style={{
                padding: "0.25rem 0.5rem",
                marginLeft: "0.25rem",
                width: "90px",
              }}
              required
            />
          </label>

          <label style={{ fontSize: "0.875rem" }}>
            成交净值：
            <input
              type="number"
              step="0.0001"
              value={fillPrice}
              onChange={(e) => setFillPrice(e.target.value)}
              style={{
                padding: "0.25rem 0.5rem",
                marginLeft: "0.25rem",
                width: "70px",
              }}
              required
            />
          </label>

          <button
            type="submit"
            disabled={fillMutation.isPending || !fillFundId.trim()}
            style={{
              padding: "0.35rem 1rem",
              backgroundColor: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: "500",
            }}
          >
            {fillMutation.isPending ? "推送中…" : "推送成交"}
          </button>
        </form>
        {fillMutation.error && (
          <p
            style={{
              color: "#dc2626",
              fontSize: "0.875rem",
              margin: "0.5rem 0 0 0",
            }}
          >
            推送失败：
            {fillMutation.error instanceof Error
              ? fillMutation.error.message
              : "错误"}
          </p>
        )}
      </div>
    </section>
  );
};
