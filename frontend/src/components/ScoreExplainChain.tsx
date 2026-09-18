import { MetricValue } from "./MetricValue";
import { formatPercent } from "./Formatters";
type Item = {
  factor_id: string;
  raw_value: number | null;
  status: string;
  reason_code?: string | null;
  weight?: number;
};
export const ScoreExplainChain = ({ attribution }: { attribution: Item[] }) => (
  <div>
    {attribution.map((item) => (
      <div key={item.factor_id}>
        <span>{item.factor_id}</span>
        <MetricValue
          value={item.raw_value}
          status={item.status}
          reason={item.reason_code}
        />
        {item.weight != null && <span>{formatPercent(item.weight)}</span>}
      </div>
    ))}
  </div>
);
