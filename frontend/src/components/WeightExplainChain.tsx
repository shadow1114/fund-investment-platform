import { formatPercent } from "./Formatters";
type Weight = { fund_id: string; weight: number };
type Review = {
  action: string;
  reason?: string;
  reviewed_by?: string;
  reviewed_at?: string;
};
export const WeightExplainChain = ({
  proposedWeights,
  finalWeights,
  review,
}: {
  proposedWeights: Weight[];
  finalWeights: Weight[];
  review?: Review;
}) => (
  <div>
    <section>
      <h3>原始建议权重</h3>
      {proposedWeights.map((w) => (
        <div key={w.fund_id}>{`${w.fund_id} ${formatPercent(w.weight)}`}</div>
      ))}
    </section>
    <section>
      <h3>最终权重</h3>
      {finalWeights.map((w) => (
        <div key={w.fund_id}>{`${w.fund_id} ${formatPercent(w.weight)}`}</div>
      ))}
    </section>
    {review?.reason && <div>复核原因：{review.reason}</div>}
  </div>
);
