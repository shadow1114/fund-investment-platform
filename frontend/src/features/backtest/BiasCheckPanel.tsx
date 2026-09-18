import type {
  BacktestBiasCheck,
  BiasCheck,
} from "../../api/generated/m17.schemas";

const names: Record<string, string> = {
  look_ahead_bias: "前视偏差",
  survivorship_bias: "幸存者偏差",
  tradability_bias: "可交易性偏差",
  point_in_time: "点时数据",
  transaction_cost: "交易成本",
  subscription_redemption_lag: "申购赎回滞后",
};
const unsafeStatuses = new Set([
  "FAIL",
  "NOT_VERIFIED",
  "PARTIALLY_MODELED",
  "NOT_MODELED",
  "UNKNOWN",
]);

export const BiasCheckPanel = ({ bias }: { bias: BacktestBiasCheck }) => {
  const entries = Object.entries(bias.checks) as [string, BiasCheck][];
  const incomplete =
    entries.length !== Object.keys(names).length ||
    entries.some(([, check]) => !check || unsafeStatuses.has(check.status));
  return (
    <section role="region" aria-label="偏差检查">
      <h2>偏差检查</h2>
      {incomplete && (
        <p role="alert">缺少验证或未建模证据，本回测不可作为决策依据。</p>
      )}
      {entries.map(([key, check]) => (
        <article key={key}>
          <h3>{names[key] ?? key}</h3>
          <strong>{check.status}</strong>
          {check.reason && <p>{check.reason}</p>}
          {check.affected_periods !== undefined && (
            <p>受影响期数：{check.affected_periods}</p>
          )}
          {check.violations && check.violations.length > 0 && (
            <ul>
              {check.violations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          {check.unmodeled_costs && check.unmodeled_costs.length > 0 && (
            <>
              <p>未建模成本：</p>
              <ul>
                {check.unmodeled_costs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {check.availability_quality_distribution && (
            <p>
              质量分布：
              {Object.entries(check.availability_quality_distribution)
                .map(([quality, value]) => `${quality} ${value}`)
                .join("；")}
            </p>
          )}
        </article>
      ))}
      <p>
        快照 {bias.snapshot_summary.snapshot_periods} 期；重建{" "}
        {bias.snapshot_summary.rebuilt_periods}/
        {bias.snapshot_summary.total_periods} 期
      </p>
      {bias.data_limitations.length > 0 && (
        <>
          <h3>数据局限</h3>
          <ul>
            {bias.data_limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};
