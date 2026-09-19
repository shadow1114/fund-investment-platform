import type { Decision } from "../api/generated/m17.schemas";
import { formatDate } from "./Formatters";
import { formatPercent } from "./Formatters";

export const WeightExplainChain = ({
  originalWeights,
  finalWeights,
  review,
  auditId,
}: {
  originalWeights: Decision["proposed_weights"];
  finalWeights: Decision["final_weights"];
  review: Decision["review"];
  auditId?: string;
}) => (
  <div>
    <section aria-label="原始建议权重">
      <h3>原始建议权重</h3>
      {originalWeights.map((w) => (
        <div key={w.fund_id}>{`${w.fund_id} ${formatPercent(w.weight)}`}</div>
      ))}
    </section>
    <section aria-label="最终权重">
      <h3>最终权重</h3>
      {finalWeights === null ? (
        <div>{review ? "复核后无可执行最终权重" : "尚未复核，无最终权重"}</div>
      ) : (
        finalWeights.map((w) => (
          <div key={w.fund_id}>{`${w.fund_id} ${formatPercent(w.weight)}`}</div>
        ))
      )}
    </section>
    {review && (
      <section aria-label="PM 复核记录">
        <div>复核动作：{review.action}</div>
        <div>复核原因：{review.reason}</div>
        <div>复核人：{review.reviewed_by}</div>
        <div>复核时间：{formatDate(review.reviewed_at)}</div>
        {auditId && <div>审计 ID：{auditId}</div>}
      </section>
    )}
  </div>
);
