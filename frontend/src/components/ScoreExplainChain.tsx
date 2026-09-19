import type { ScoreAttribution } from "../api/generated/m17.schemas";
import { MetricValue } from "./MetricValue";
import { formatPercent } from "./Formatters";
export const ScoreExplainChain = ({
  attribution,
}: {
  attribution: ScoreAttribution[];
}) => (
  <div>
    {attribution.map((item) => (
      <div key={item.factor_id}>
        <span>{item.factor_id}</span>
        {item.window && <div>窗口：{item.window}</div>}
        {item.direction && <div>方向：{item.direction}</div>}
        {item.sub_score && <div>子评分：{item.sub_score}</div>}
        <MetricValue
          value={item.raw_value}
          status={item.status}
          reason={item.reason_code}
        />
        {item.weight != null && <span>{formatPercent(item.weight)}</span>}
        {item.original_weight !== undefined && (
          <div>原始权重：{formatPercent(item.original_weight)}</div>
        )}
        {item.weight_source && <div>权重来源：{item.weight_source}</div>}
        {item.effectiveness_verdict && (
          <div>有效性判定：{item.effectiveness_verdict}</div>
        )}
        {item.normalized_value !== undefined && (
          <div>
            归一化值：
            <MetricValue
              value={item.normalized_value}
              status={item.status}
              reason={item.exclusion_reason ?? item.reason_code}
            />
          </div>
        )}
        {item.weighted_contribution !== undefined && (
          <div>加权贡献：{item.weighted_contribution.toFixed(2)}</div>
        )}
        {item.exclusion_reason && (
          <div>
            排除原因：<span>{item.exclusion_reason}</span>
          </div>
        )}
        {item.reallocated_to && item.reallocated_to.length > 0 && (
          <div>
            权重再分配：
            {item.reallocated_to.map((allocation) => (
              <div key={allocation.factor_id}>
                {allocation.factor_id} +{formatPercent(allocation.delta_weight)}
              </div>
            ))}
          </div>
        )}
      </div>
    ))}
  </div>
);
